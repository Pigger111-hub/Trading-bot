"""Synthetic scratch copies only; never rewrite original baseline evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import pytest

from lab3 import planning
from lab3.store import IntegrityError, digest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = 'dashboard/qa/baseline-evidence.json'
CANONICAL_SHA = '5be7be8acf2c7bc348b2ac2c722614ffca6a97312f759407ea55023388c65e5c'
SCRATCH = Path('C:/Users/STANDARD_DOH/AppData/Local/hermes/cache/scratch')


@pytest.fixture
def synthetic_baseline():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='synthetic-planning-baseline-', dir=SCRATCH) as folder:
        root = Path(folder)
        baseline = json.loads((ROOT / BASELINE).read_bytes())
        for name in [BASELINE, *baseline]:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        yield root


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_fresh_checkout_baseline_json_line_endings_are_equivalent(synthetic_baseline, newline):
    root = synthetic_baseline
    path = root / BASELINE
    manifest = json.loads(path.read_bytes())
    path.write_bytes((json.dumps(manifest, indent=2) + '\n').replace('\n', newline).encode())
    assert digest(manifest) == CANONICAL_SHA
    assert planning.verify_original_baseline(root) == dict(
        verified=True, file_count=56, manifest_sha256=CANONICAL_SHA)
    assert planning.exposed_windows(root) == planning.exposed_windows(ROOT)


@pytest.mark.parametrize('duplicate', ['same', 'conflicting'])
def test_duplicate_manifest_keys_are_denied(synthetic_baseline, duplicate):
    path = synthetic_baseline / BASELINE
    manifest = json.loads(path.read_bytes())
    name, expected = next(iter(manifest.items()))
    extra = expected if duplicate == 'same' else '0' * 64
    # Last value is the trusted value: ordinary json.loads would hide the duplicate.
    path.write_text('{' + json.dumps(name) + ':' + json.dumps(extra) + ',' +
                    json.dumps(manifest)[1:], encoding='utf-8')
    with pytest.raises(IntegrityError, match='Duplicate'):
        planning.verify_original_baseline(synthetic_baseline)
    with pytest.raises(IntegrityError, match='Duplicate'):
        planning.exposed_windows(synthetic_baseline)


@pytest.mark.parametrize('bad_value', [None, True, 123, [], {}, 'A' * 64, 'f' * 63, 'g' * 64])
def test_manifest_hash_schema_is_strict(synthetic_baseline, bad_value):
    path = synthetic_baseline / BASELINE
    manifest = json.loads(path.read_bytes())
    manifest[next(iter(manifest))] = bad_value
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(IntegrityError, match='SHA256'):
        planning.verify_original_baseline(synthetic_baseline)


@pytest.mark.parametrize('bad_name', ['../outside', '/absolute', 'C:/outside',
                                     'data/../outside', 'data//outside', 'data\\outside', './outside'])
def test_manifest_paths_are_strict_root_relative_posix(synthetic_baseline, bad_name):
    path = synthetic_baseline / BASELINE
    manifest = json.loads(path.read_bytes())
    expected = manifest.pop(next(iter(manifest)))
    manifest[bad_name] = expected
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(IntegrityError, match='path'):
        planning.verify_original_baseline(synthetic_baseline)


def test_semantic_hash_tamper_cannot_self_approve(synthetic_baseline):
    path = synthetic_baseline / BASELINE
    manifest = json.loads(path.read_bytes())
    name = next(iter(manifest))
    (synthetic_baseline / name).write_bytes(b'synthetic altered evidence')
    manifest[name] = hashlib.sha256((synthetic_baseline / name).read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(IntegrityError, match='trust anchor'):
        planning.verify_original_baseline(synthetic_baseline)
    with pytest.raises(IntegrityError, match='trust anchor'):
        planning.exposed_windows(synthetic_baseline)


def test_every_protected_file_is_checked_for_changed_or_missing_bytes(synthetic_baseline):
    manifest = json.loads((synthetic_baseline / BASELINE).read_bytes())
    for name in manifest:
        path = synthetic_baseline / name
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'synthetic corruption')
            with pytest.raises(IntegrityError, match='Protected baseline changed'):
                planning.verify_original_baseline(synthetic_baseline)
            path.unlink()
            with pytest.raises(IntegrityError):
                planning.verify_original_baseline(synthetic_baseline)
        finally:
            path.write_bytes(original)
    assert planning.verify_original_baseline(synthetic_baseline)['file_count'] == 56


@pytest.mark.parametrize('raw', ['[]', 'null', '{}', '{"x": NaN}', '{"x": Infinity}',
                               '{"x": -Infinity}', '{"x":', '{"x": "unterminated}'])
def test_malformed_or_wrong_shape_manifest_is_denied(synthetic_baseline, raw):
    (synthetic_baseline / BASELINE).write_text(raw, encoding='utf-8')
    with pytest.raises(IntegrityError):
        planning.verify_original_baseline(synthetic_baseline)
    with pytest.raises(IntegrityError):
        planning.exposed_windows(synthetic_baseline)


def test_original_baseline_verification_preserves_all_bytes_and_mtimes():
    manifest = json.loads((ROOT / BASELINE).read_bytes())
    names = [BASELINE, *manifest]
    def inventory():
        return {name: (hashlib.sha256((ROOT / name).read_bytes()).hexdigest(),
                       (ROOT / name).stat().st_mtime_ns) for name in names}
    before = inventory()
    assert planning.verify_original_baseline(ROOT)['manifest_sha256'] == CANONICAL_SHA
    planning.exposed_windows(ROOT)
    assert inventory() == before
