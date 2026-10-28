"""Keep development test temporaries inside Hermes scratch, not OS temp."""
import os
from pathlib import Path


def pytest_configure(config):
    home = Path(os.environ.get('HERMES_HOME', str(Path.home() / 'AppData/Local/hermes')))
    scratch = home / 'cache/scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ['PYTEST_DEBUG_TEMPROOT'] = str(scratch)
