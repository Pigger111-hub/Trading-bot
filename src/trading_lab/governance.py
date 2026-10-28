"""Fail-closed, bounded approval checks. Human authority is external; SQLite is not an auth server."""
from itertools import product
import hashlib
import json
import math
from pathlib import Path

from .registry import Registry, digest


class SafetyError(PermissionError):
    pass


def policy_hash(policy):
    return digest(policy)


def validate_policy(policy):
    expected_false = ('allow_credentials', 'allow_live_orders', 'allow_paper_loop', 'allow_short',
                      'scheduler_enabled', 'allow_dynamic_code')
    if any(policy.get(key) is not False for key in expected_false):
        raise SafetyError('live, paper loop, credentials, scheduler and dynamic code must remain disabled')
    if (policy.get('mode') != 'research_only' or policy.get('market') != 'spot'
            or type(policy.get('leverage')) is not int or policy['leverage'] != 1
            or policy.get('symbols') != ['BTCUSDT'] or policy.get('intervals') != ['1h']):
        raise SafetyError('only BTCUSDT spot 1h long-only unleveraged research is supported')
    fraction = policy.get('max_position_fraction')
    if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 < fraction <= 0.1:
        raise SafetyError('position fraction must be finite and no larger than 0.10')
    for key, maximum in [('max_batch_runs', 8), ('max_research_cycles', 3),
                         ('max_model_calls_per_cycle', 3)]:
        if type(policy.get(key)) is not int or not 1 <= policy[key] <= maximum:
            raise SafetyError(f'invalid bounded policy: {key}')
    return policy


def load_policy(root):
    return validate_policy(json.loads((Path(root) / 'governance/safety-policy.json').read_text('utf-8')))


def code_hash(root):
    """Bind approval to executable package AND dependencies, not only strategy source."""
    root = Path(root)
    files = sorted((root / 'src/trading_lab').rglob('*.py'))
    files += [root / 'pyproject.toml', root / 'uv.lock']
    if not files or any(not file.is_file() or file.is_symlink() for file in files):
        raise SafetyError('missing or symlinked executable/dependency manifest')
    return digest([(file.relative_to(root).as_posix(), hashlib.sha256(file.read_bytes()).hexdigest())
                   for file in files])


def validate_params(params):
    if not isinstance(params, dict) or set(params) != {'fast', 'slow'}:
        raise SafetyError('only fixed built-in SMA fast/slow parameters accepted')
    fast, slow = params['fast'], params['slow']
    if type(fast) is not int or type(slow) is not int or not 2 <= fast < slow <= 500:
        raise SafetyError('SMA windows must satisfy 2 <= fast < slow <= 500')


def holdout_fingerprint(frame):
    """Identity of final-fold OHLCV values/time, independent of snapshot UUID/Parquet encoding."""
    count = (len(frame) - len(frame) // 2) // 3
    if count < 2:
        raise SafetyError('insufficient final holdout')
    final = frame.iloc[-count:][['Open', 'High', 'Low', 'Close', 'Volume']]
    return digest({'columns': list(final.columns), 'rows': [
        [timestamp.isoformat(), *[float(value).hex() for value in row]]
        for timestamp, row in zip(final.index, final.itertuples(index=False, name=None))]})


def parameter_grid(fast_values, slow_values):
    values = [{'fast': fast, 'slow': slow} for fast, slow in product(fast_values, slow_values)]
    for value in values:
        validate_params(value)
    if not values or len(values) > 8 or len({digest(p) for p in values}) != len(values):
        raise SafetyError('parameter grid must contain 1..8 unique explicit configurations')
    return values


def make_spec(dataset_hash, executable_hash, policy, parameters, budget=1,
              commission=0.001, spread=0.0005, dataset_id=None, holdout_hash=None, holdout_window=None,
              data_window=None):
    validate_policy(policy)
    if any(not isinstance(h, str) or len(h) != 64 or any(c not in '0123456789abcdef' for c in h)
           for h in [dataset_hash, executable_hash]):
        raise SafetyError('valid SHA256 dataset and code hashes required')
    if type(budget) is not int or not 1 <= budget <= policy['max_batch_runs']:
        raise SafetyError('run budget exceeds policy')
    if not isinstance(parameters, list) or not parameters or len(parameters) > budget:
        raise SafetyError('parameters must fit run budget')
    for params in parameters:
        validate_params(params)
    if len({digest(p) for p in parameters}) != len(parameters):
        raise SafetyError('duplicate configurations')
    for value in [commission, spread]:
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 0.02:
            raise SafetyError('invalid cost assumption')
    spec = {'version': 1, 'kind': 'BACKTEST_SIMULATED', 'strategy': 'builtin_sma_crossover_v1',
            'dataset_hash': dataset_hash, 'dataset_id': dataset_id, 'code_hash': executable_hash,
            'holdout_hash': holdout_hash or dataset_hash, 'holdout_window': holdout_window,
            'data_window': data_window or holdout_window,
            'policy_hash': policy_hash(policy), 'symbol': 'BTCUSDT', 'interval': '1h',
            'parameters': parameters, 'run_budget': budget, 'commission': commission, 'spread': spread,
            'position_fraction': policy['max_position_fraction'], 'cash': 10000,
            'validation': 'chronological_walk_forward_locked_holdout_v1',
            'hypothesis': 'SMA crossover may reduce drawdown versus equal-allocation buy-and-hold after costs.',
            'falsification': 'No consistent out-of-sample drawdown benefit across chronological folds; '
                             'report return trade-off and inadequate trade counts, never select on holdout.',
            'cost_stress_multiplier': 2,
            'max_engine_evaluations_per_trial': 12,
            'costs_note': 'Commission and spread are scenario assumptions, NOT verified account fees. '
                          'No orderbook/impact model; stressed costs in validation.'}
    return {**spec, 'spec_id': digest(spec)}


def authorize_run(registry, spec, policy, executable_hash, dataset_hash, params):
    """Atomically reserve budget BEFORE execution; failures and restarts consume reservations."""
    validate_policy(policy)
    validate_params(params)
    unsigned = {key: value for key, value in spec.items() if key != 'spec_id'}
    expected = make_spec(spec['dataset_hash'], spec['code_hash'], policy, spec['parameters'],
                         spec['run_budget'], spec['commission'], spec['spread'], spec['dataset_id'],
                         spec['holdout_hash'], spec['holdout_window'], spec['data_window'])
    if spec != expected or digest(unsigned) != spec.get('spec_id'):
        raise SafetyError('specification changed or contains unsupported fields')
    if spec['code_hash'] != executable_hash or spec['dataset_hash'] != dataset_hash:
        raise SafetyError('code or data changed after approval')
    if params not in spec['parameters']:
        raise SafetyError('parameters outside approved batch')
    registry.verify()
    with registry.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute("SELECT kind, payload FROM events WHERE kind IN ('approval','revocation',"
                          "'run_reserved') ORDER BY id").fetchall()
        approved = False
        reservations = []
        for row in rows:
            event = json.loads(row['payload'])
            if event.get('spec_id') != spec['spec_id']:
                continue
            if row['kind'] == 'approval':
                approved = (event.get('policy_hash') == policy_hash(policy)
                            and event.get('code_hash') == executable_hash
                            and bool(event.get('human')) and bool(event.get('review_id'))
                            and event.get('isolation') == 'trusted_builtin_process')
            elif row['kind'] == 'revocation':
                approved = False
            elif row['kind'] == 'run_reserved':
                reservations.append(event)
        if not approved:
            raise SafetyError('human approval and reviewed isolation evidence required')
        exposure = db.execute("SELECT payload FROM events WHERE kind='holdout_exposed'").fetchall()
        for row in exposure:
            event = json.loads(row['payload'])
            previous_window, current_window = event.get('data_window') or event.get('holdout_window'), spec.get('holdout_window')
            overlaps = bool(previous_window and current_window and
                            max(previous_window[0], current_window[0]) <= min(previous_window[1], current_window[1]))
            if (event['holdout_hash'] == spec['holdout_hash'] or overlaps) and event['spec_id'] != spec['spec_id']:
                raise SafetyError('final holdout already exposed/overlapping; new untouched data required')
        if not reservations:
            Registry.append_in(db, 'holdout_exposed', {'spec_id': spec['spec_id'],
                'holdout_hash': spec['holdout_hash'], 'holdout_window': spec.get('holdout_window'),
                'data_window': spec.get('data_window')})
        if len(reservations) >= spec['run_budget']:
            raise SafetyError('approved run budget exhausted')
        if any(event['parameters'] == params for event in reservations):
            raise SafetyError('configuration already reserved; no duplicate run')
        return Registry.append_in(db, 'run_reserved', {'spec_id': spec['spec_id'],
                                                     'parameters': params,
                                                     'ordinal': len(reservations) + 1})
