"""Fresh tool-free Hermes roles. Controller hygiene, not an OS security sandbox."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

ROLES = ('research_planner', 'knowledge_researcher', 'independent_critic')


class ModelError(RuntimeError):
    pass


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def finite_float(value):
        import math
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('nonfinite JSON float')
        return number
    return json.loads(text, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')),
                      parse_float=finite_float, object_pairs_hook=pairs)


def parse_hermes_stream(stdout):
    try:
        events = [strict_json(line) for line in stdout.splitlines() if line.strip()]
        if any(not isinstance(e, dict) for e in events):
            raise ValueError('object events required')
        def tool_activity(value):
            if isinstance(value, dict):
                if ('tool' in str(value.get('type', '')).lower() or any(
                    value.get(k) for k in ('tool_calls', 'tool_call', 'function_call', 'tool_call_id'))):
                    return True
                return any(tool_activity(v) for v in value.values())
            return isinstance(value, list) and any(tool_activity(v) for v in value)
        if any(tool_activity(e) for e in events):
            raise ValueError('unexpected tool event')
        results = [e for e in events if e.get('type') == 'result']
        if (len(results) != 1 or type(results[0].get('exit_code')) is not int
                or results[0]['exit_code'] != 0 or results[0].get('is_error')
                or results[0].get('error') or results[0].get('status') in ('failed', 'error')):
            raise ValueError('missing, duplicate or unsuccessful result')
        text = results[0].get('text')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('missing model output')
        value = strict_json(text)
        if not isinstance(value, dict):
            raise ValueError('JSON object required')
        return value, {k: results[0].get(k) for k in ('session_id', 'tokens', 'duration_ms')}
    except (ValueError, TypeError, KeyError) as exc:
        raise ModelError(f'invalid Hermes stream: {exc}') from exc


def _bounded_process(command, *, input, timeout, cwd, env, shell):
    """Drain both pipes with hard byte caps, timeout, and bounded process lifetime."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=cwd, env=env, shell=shell)
    outputs = [bytearray(), bytearray()]
    exceeded = threading.Event()
    def drain(pipe, target):
        try:
            while chunk := pipe.read(8192):
                if len(target) + len(chunk) > 1_000_000:
                    exceeded.set()
                    process.kill()
                    break
                target.extend(chunk)
        finally:
            pipe.close()
    threads = [threading.Thread(target=drain, args=(pipe, target), daemon=True)
               for pipe, target in zip((process.stdout, process.stderr), outputs)]
    for thread in threads:
        thread.start()
    def feed():
        try:
            process.stdin.write(input)
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass
    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    try:
        process.wait(timeout=timeout)
    except BaseException as exc:
        process.kill()
        process.wait()
        for thread in [writer, *threads]:
            thread.join(timeout=3)
        if isinstance(exc, subprocess.TimeoutExpired):
            exc.output, exc.stderr = bytes(outputs[0]), bytes(outputs[1])
        raise
    finally:
        for thread in [writer, *threads]:
            thread.join(timeout=3)
    if exceeded.is_set() or any(t.is_alive() for t in threads):
        raise ModelError('model output budget exceeded or pipes did not close')
    return bytes(outputs[0]), bytes(outputs[1]), process.returncode


class HermesModel:
    def __init__(self, store, cycle_id):
        self.store, self.cycle_id = store, cycle_id

    def complete(self, role, prompt):
        if role not in ROLES or not isinstance(prompt, str) or len(prompt) > 60_000:
            raise ModelError('invalid role or prompt budget')
        executable = shutil.which('hermes')
        if not executable:
            raise ModelError('Hermes CLI missing')
        reservation = self.store.reserve_model_call(self.cycle_id, role, cap=3)
        audit = {'cycle_id': self.cycle_id, 'role': role, 'reservation': reservation,
                 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                 'provider': 'openai-codex', 'model': 'gpt-6.1-sol'}
        self.store.append('model_call_started', audit)
        scratch = Path(os.environ.get('HERMES_HOME', str(Path.home() / 'AppData/Local/hermes'))) / 'cache/scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items()
               if not any(word in k.upper() for word in ('BINANCE', 'BYBIT', 'KRAKEN', 'COINBASE',
                                                          'OKX', 'KUCOIN', 'BITGET', 'EXCHANGE',
                                                          'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'))}
        env['PYTHONIOENCODING'] = 'utf-8'
        command = [executable, 'chat', '--oneshot', '--query-file', '-', '--format', 'stream-json',
                   '--safe-mode', '--toolsets', 'bot_room', '--max-turns', '1', '--run-budget', '135',
                   '--reasoning', 'low', '--provider', 'openai-codex', '--model', 'gpt-6.1-sol']
        # Installed bot_room: tools=(), includes=(); never fall back to a default toolset.
        try:
            with tempfile.TemporaryDirectory(prefix='phase3-model-', dir=scratch) as cwd:
                stdout, stderr, code = _bounded_process(command, input=prompt.encode(), timeout=150,
                                                        cwd=cwd, env=env, shell=False)
            self.store.append('model_raw_response', {**audit, 'stdout': stdout.decode('utf-8', errors='replace'),
                                                     'stderr': stderr.decode('utf-8', errors='replace'), 'exit_code': code})
            if code != 0:
                raise ModelError(f'Hermes failed with exit code {code}')
            value, usage = parse_hermes_stream(stdout.decode('utf-8', errors='strict'))
        except BaseException as exc:
            if isinstance(exc, subprocess.TimeoutExpired):
                self.store.append('model_raw_response', {**audit, 'stdout': (exc.output or b'').decode('utf-8', errors='replace'),
                                                         'stderr': (exc.stderr or b'').decode('utf-8', errors='replace'),
                                                         'exit_code': None, 'interrupted': True})
            self.store.append('model_call_failed', {**audit, 'error_type': type(exc).__name__, 'error': str(exc)[:2000]})
            raise
        self.store.append('model_call_completed', {**audit, 'response': value, 'usage': usage})
        return value
