"""End-to-end worker development test on explicitly SYNTHETIC prices only."""
import numpy as np
import pandas as pd

from trading_lab.governance import make_spec
from trading_lab.registry import canonical
from test_governance import synthetic_policy


def test_trusted_subprocess_worker_is_reproducible_with_synthetic_data(tmp_path):
    from trading_lab.runner import isolated_backtest
    values = 30000 + np.sin(np.arange(180) / 5) * 1000
    frame = pd.DataFrame({'Open': values, 'High': values+5, 'Low': values-5,
                          'Close': values, 'Volume': 1.0},
                         index=pd.date_range('2020-01-01', periods=180, freq='h', tz='UTC'))
    spec = make_spec('a'*64, 'b'*64, synthetic_policy(), [{'fast': 3, 'slow': 8}], budget=1)
    first = isolated_backtest(tmp_path, frame, spec, {'fast': 3, 'slow': 8})
    second = isolated_backtest(tmp_path, frame, spec, {'fast': 3, 'slow': 8})
    assert canonical(first) == canonical(second)
    assert first['simulation'] is True
    assert first['engine_evaluations'] == 5
    assert len(first['walk_forward']['folds']) == 3
    assert first['metrics']['trades'] >= 0
    assert first['isolation']['credentials_inherited'] is False
