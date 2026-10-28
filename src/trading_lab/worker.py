"""Private trusted worker. No dynamic strategy loading. Invoke via approved parent only.

Process hygiene is not an OS sandbox. Synthetic unit tests may exercise this
fixed built-in engine; real market experiments require separate human approval.
"""
import json
import os
from pathlib import Path
import socket
import sys

import pandas as pd

from .backtest import run_backtest, walk_forward
from .data import validate_frame
from .governance import validate_params
from .registry import canonical


def _blocked_network(*args, **kwargs):
    raise PermissionError('network disabled in trusted backtest worker')


def execute(request):
    path = Path(request['data_path']).resolve()
    if path != Path.cwd().resolve() / 'input.parquet' or path.is_symlink():
        raise ValueError('worker accepts only its staged input.parquet')
    frame = pd.read_parquet(path)
    validate_frame(frame)
    spec, params = request['spec'], request['params']
    validate_params(params)
    if spec.get('strategy') != 'builtin_sma_crossover_v1' or params not in spec['parameters']:
        raise PermissionError('unapproved executable strategy type or parameters')
    if spec.get('cost_stress_multiplier') != 2 or spec.get('max_engine_evaluations_per_trial') != 12:
        raise PermissionError('unsupported evaluation protocol')
    if len(frame) // 2 < params['slow'] + 2:
        raise ValueError('dataset needs enough initial-half history; no holdout fallback')
    # Defend accidental networking in TRUSTED code; not advertised as hostile-code isolation.
    socket.socket = _blocked_network
    socket.create_connection = _blocked_network
    common = {'fast': params['fast'], 'slow': params['slow'], 'commission': spec['commission'],
              'spread': spec['spread'], 'position_fraction': spec['position_fraction']}
    development = frame.iloc[:len(frame) // 2].copy()
    primary = run_backtest(development, cash=spec['cash'], **common)
    forward = walk_forward(frame, **common)
    stressed = run_backtest(development, cash=spec['cash'], **{**common,
        'commission': spec['commission'] * spec['cost_stress_multiplier'],
        'spread': spec['spread'] * spec['cost_stress_multiplier']})
    metrics = {key: primary[key] for key in ('return_pct', 'max_drawdown_pct', 'trades', 'exposure_pct')}
    return {'kind': 'BACKTEST_SIMULATED', 'simulation': True, 'metrics': metrics,
            'metrics_scope': 'initial_half_development_only_not_out_of_sample',
            'development': primary, 'baselines': primary['baselines'], 'walk_forward': forward,
            'cost_stress_development': {key: stressed[key] for key in metrics}, 'engine_evaluations': 5,
            'cost_assumptions': {'commission': spec['commission'], 'spread': spec['spread'],
                                 'stress_multiplier': 2, 'account_fees_verified': False,
                                 'market_impact_model': False},
            'isolation': {'type': 'trusted_builtin_process', 'os_sandbox': False,
                          'credentials_inherited': any(any(word in key.upper() for word in
                              ('BINANCE', 'BYBIT', 'KRAKEN', 'COINBASE', 'API_KEY', 'TOKEN', 'SECRET'))
                                                       for key in os.environ),
                          'python_network_guard': True, 'dynamic_code': False}}


def main():
    request = json.loads(sys.stdin.buffer.read(1_000_000).decode('utf-8'))
    result = execute(request)
    sys.stdout.write(canonical(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
