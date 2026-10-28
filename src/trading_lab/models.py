"""Hermes subprocess JSON adapter. Model outputs are data, never executable instructions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


class ModelError(RuntimeError):
    pass


def parse_hermes_stream(stdout):
    events = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            events.append(value)
    if any(event.get('type') in ('tool_use', 'tool_result') for event in events):
        raise ModelError('unexpected tool activity in tool-free model role')
    results = [event for event in events if event.get('type') == 'result']
    if len(results) != 1 or results[0].get('exit_code') != 0:
        raise ModelError('missing or unsuccessful Hermes result; no fabricated fallback')
    text = results[0].get('text', '').strip()
    if text.startswith('```json') and text.endswith('```'):
        text = text[7:-3].strip()
    elif text.startswith('```') and text.endswith('```'):
        text = text[3:-3].strip()
    try:
        response = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (ValueError, TypeError) as error:
        raise ModelError('model did not return strict JSON') from error
    if not isinstance(response, dict):
        raise ModelError('model JSON object required')
    return response, {key: results[0].get(key) for key in ('session_id', 'tokens', 'duration_ms')}


class HermesModel:
    def __init__(self, registry, provider='openai-codex', model='gpt-6.1-sol', timeout=150):
        if not shutil.which('hermes'):
            raise ModelError('Hermes CLI not found')
        self.registry = registry
        self.provider = provider
        self.model = model
        self.timeout = timeout

    def complete(self, role, prompt):
        if role not in ('knowledge_researcher', 'knowledge_critic', 'experiment_researcher', 'experiment_critic'):
            raise ModelError('unknown bounded model role')
        if len(prompt) > 60000:
            raise ModelError('model input character budget exceeded')
        scratch = Path(os.environ.get('HERMES_HOME', str(Path.home() / 'AppData/Local/hermes'))) / 'cache/scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        env = {key: value for key, value in os.environ.items()
               if not any(word in key.upper() for word in ('BINANCE', 'BYBIT', 'KRAKEN', 'COINBASE'))}
        env['PYTHONIOENCODING'] = 'utf-8'
        command = [shutil.which('hermes'), 'chat', '--oneshot', '--query-file', '-', '--format', 'stream-json',
                   '--safe-mode', '--toolsets', 'bot_room', '--max-turns', '1', '--run-budget',
                   str(self.timeout - 15), '--reasoning', 'low', '--provider', self.provider, '--model', self.model]
        # bot_room is a verified empty text-only toolset in the installed Hermes runtime.
        # --safe-mode disables plugins/MCP/project rules; this process has NO lab write tools.
        started = self.registry.append('model_call_started', {'role': role, 'provider': self.provider,
                                                            'model': self.model})
        with tempfile.TemporaryDirectory(prefix='lab-model-', dir=scratch) as directory:
            try:
                result = subprocess.run(command, input=prompt.encode('utf-8'), capture_output=True,
                                        timeout=self.timeout, cwd=directory, env=env, check=False)
                if result.returncode:
                    diagnostic = result.stderr.decode('utf-8', errors='replace')[-2000:]
                    raise ModelError(f'Hermes subprocess failed ({result.returncode}): {diagnostic}')
                if len(result.stdout) > 2_000_000:
                    raise ModelError('model output budget exceeded')
                value, usage = parse_hermes_stream(result.stdout.decode('utf-8', errors='replace'))
            except Exception as error:
                self.registry.append('model_call_failed', {'started': started, 'role': role,
                                                          'error_type': type(error).__name__})
                raise
        self.registry.append('model_call_completed', {'started': started, 'role': role, 'usage': usage,
                                                      'response': value})
        return value
