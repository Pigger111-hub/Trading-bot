"""Keep pytest temporary files in Hermes scratch, never system temp."""
import os
from pathlib import Path


def pytest_configure(config):
    scratch = Path(os.environ.get('HERMES_HOME', str(Path.home() / 'AppData/Local/hermes'))) / 'cache/scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ['PYTEST_DEBUG_TEMPROOT'] = str(scratch)
