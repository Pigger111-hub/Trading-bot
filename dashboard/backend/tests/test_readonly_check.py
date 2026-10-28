"""Synthetic file fingerprints; never changes real research artifacts."""
import hashlib
import importlib.util
from pathlib import Path


def test_readonly_snapshot_detects_mutations_and_missing_files(tmp_path):
    path = Path(__file__).resolve().parents[2] / 'verify_readonly.py'
    spec = importlib.util.spec_from_file_location('dashboard_readonly_check', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / 'synthetic.txt'
    target.write_bytes(b'synthetic evidence')
    baseline = {'synthetic.txt': hashlib.sha256(target.read_bytes()).hexdigest()}
    assert module.verify_files(tmp_path, baseline) == []
    target.write_bytes(b'tampered synthetic evidence')
    assert module.verify_files(tmp_path, baseline) == ['synthetic.txt']
    target.unlink()
    assert module.verify_files(tmp_path, baseline) == ['synthetic.txt']
