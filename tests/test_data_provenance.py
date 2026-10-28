"""Provenance checks use synthetic temporary snapshots; no live HTTP."""
import hashlib
import json

import pandas as pd
import pytest

from test_data import HOUR, START, SyntheticResponse, install_http, module, synthetic_kline


def snapshot(tmp_path, monkeypatch, count=2):
    api = module()
    monkeypatch.setattr(api, "_now_ms", lambda: START + 10 * HOUR)
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(i) for i in range(count)])])
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + count * HOUR)
    # Exercise legacy manifests independently of any persisted identity.
    manifest.pop("dataset_sha256", None)
    save_manifest(tmp_path, manifest)
    return api, manifest


def save_manifest(root, manifest):
    (root / manifest["dataset_id"] / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def replace_raw(root, manifest, pages):
    manifest["raw_pages"] = []
    for number, page in enumerate(pages):
        payload = json.dumps(page).encode()
        relative = f'{manifest["dataset_id"]}/raw-{number:05d}.json'
        (root / relative).write_bytes(payload)
        manifest["raw_pages"].append({"path": relative, "sha256": hashlib.sha256(payload).hexdigest()})
    save_manifest(root, manifest)


def test_raw_values_must_equal_parquet_exactly(tmp_path, monkeypatch):
    api, manifest = snapshot(tmp_path, monkeypatch)
    rows = [synthetic_kline(i) for i in range(2)]
    rows[0][4] = "10.99999999999999"  # defeats approximate comparisons
    replace_raw(tmp_path, manifest, [rows])
    with pytest.raises(ValueError, match="correspond"):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


@pytest.mark.parametrize("fault", [
    "shape", "object", "float_time", "string_time", "bool_time", "seconds", "microseconds",
    "wrong_close", "outoforder", "bool_price", "oversize", "after_empty", "after_end",
    "duplicate_pages", "unclosed_bad_price",
])
def test_all_raw_pages_obey_rest_contract(tmp_path, monkeypatch, fault):
    api, manifest = snapshot(tmp_path, monkeypatch)
    rows = [synthetic_kline(i) for i in range(2)]
    pages = [rows]
    if fault == "shape":
        rows[0].append("extra")
    elif fault == "object":
        pages = [{"error": "not klines"}]
    elif fault == "float_time":
        rows[0][0] = float(rows[0][0])
    elif fault == "string_time":
        rows[0][0] = str(rows[0][0])
    elif fault == "bool_time":
        rows[0][0] = True
    elif fault == "seconds":
        rows[0][0] //= 1000
    elif fault == "microseconds":
        rows[0][0] *= 1000
    elif fault == "outoforder":
        rows.reverse()
    elif fault == "bool_price":
        rows[0][1] = True
    elif fault == "wrong_close":
        rows[0][6] += 1
    elif fault == "oversize":
        pages = [rows + [synthetic_kline(2)] * 999]
    elif fault == "after_empty":
        pages = [[], rows]
    elif fault == "after_end":
        pages = [rows, []]
    elif fault == "duplicate_pages":
        pages = [[rows[0]], rows]
    elif fault == "unclosed_bad_price":
        manifest["fetched_at"] = pd.Timestamp(START + HOUR, unit="ms", tz="UTC").isoformat()
        rows[1][1] = "not a number"
    replace_raw(tmp_path, manifest, pages)
    with pytest.raises(ValueError):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


def test_legacy_identity_is_derived_deterministically_without_writes(tmp_path, monkeypatch):
    api, manifest = snapshot(tmp_path, monkeypatch)
    before = {p: p.read_bytes() for p in (tmp_path / manifest["dataset_id"]).iterdir()}
    _, first = api.load_snapshot(tmp_path, manifest["dataset_id"])
    _, second = api.load_snapshot(tmp_path, manifest["dataset_id"])
    assert len(first["dataset_sha256"]) == 64
    assert first["dataset_sha256"] == second["dataset_sha256"]
    assert first["sha256"] == manifest["sha256"]
    assert first["dataset_sha256"] != first["sha256"]
    assert all(p.read_bytes() == content for p, content in before.items())


def test_new_download_persists_full_identity(tmp_path, monkeypatch):
    api = module()
    monkeypatch.setattr(api, "_now_ms", lambda: START + 10 * HOUR)
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert len(manifest["dataset_sha256"]) == 64
    saved = json.loads((tmp_path / manifest["dataset_id"] / "manifest.json").read_text())
    assert saved == manifest
    assert api.load_snapshot(tmp_path, manifest["dataset_id"])[1] == saved


@pytest.mark.parametrize("provided", ["0" * 64, None, True])
def test_provided_identity_is_verified(tmp_path, monkeypatch, provided):
    api, manifest = snapshot(tmp_path, monkeypatch)
    manifest["dataset_sha256"] = provided
    save_manifest(tmp_path, manifest)
    with pytest.raises(ValueError, match="Dataset SHA256"):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


@pytest.mark.parametrize("field", ["fetched_at", "start_ms", "end_ms", "raw_bytes", "parquet_bytes", "extra_metadata"])
def test_provenance_changes_change_identity(tmp_path, monkeypatch, field):
    api, manifest = snapshot(tmp_path, monkeypatch)
    original = api.load_snapshot(tmp_path, manifest["dataset_id"])[1]["dataset_sha256"]
    if field == "fetched_at":
        manifest[field] = pd.Timestamp(START + 11 * HOUR, unit="ms", tz="UTC").isoformat()
    elif field == "start_ms":
        # A different inclusive lower bound with the same first aligned hour.
        manifest[field] -= 1
    elif field == "end_ms":
        manifest[field] += 1
    elif field == "raw_bytes":
        raw = manifest["raw_pages"][0]
        path = tmp_path / raw["path"]
        payload = path.read_bytes() + b"\n"
        path.write_bytes(payload)
        raw["sha256"] = hashlib.sha256(payload).hexdigest()
    elif field == "parquet_bytes":
        path = tmp_path / manifest["parquet_path"]
        pd.read_parquet(path).to_parquet(path, compression=None)
        manifest["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        manifest["audit_note"] = "synthetic provenance annotation"
    save_manifest(tmp_path, manifest)
    changed = api.load_snapshot(tmp_path, manifest["dataset_id"])[1]["dataset_sha256"]
    assert changed != original
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                           allow_nan=False).encode("utf-8")
    assert changed == hashlib.sha256(canonical).hexdigest()


def test_canonical_identity_ignores_json_object_order(tmp_path, monkeypatch):
    api, manifest = snapshot(tmp_path, monkeypatch)
    original = api.load_snapshot(tmp_path, manifest["dataset_id"])[1]["dataset_sha256"]
    save_manifest(tmp_path, dict(reversed(list(manifest.items()))))
    assert api.load_snapshot(tmp_path, manifest["dataset_id"])[1]["dataset_sha256"] == original


@pytest.mark.parametrize("edge", ["leading", "trailing", "internal"])
def test_matching_raw_and_parquet_still_require_complete_coverage(tmp_path, monkeypatch, edge):
    api, manifest = snapshot(tmp_path, monkeypatch, count=3)
    offsets = {"leading": [1, 2], "trailing": [0, 1], "internal": [0, 2]}[edge]
    replace_raw(tmp_path, manifest, [[synthetic_kline(i) for i in offsets]])
    path = tmp_path / manifest["parquet_path"]
    frame = pd.read_parquet(path).iloc[offsets]
    frame.to_parquet(path)
    manifest["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest["rows"] = len(frame)
    save_manifest(tmp_path, manifest)
    with pytest.raises(ValueError, match="coverage|gaps"):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


@pytest.mark.parametrize("cutoff", [START + HOUR, START + 2 * HOUR - 1])
def test_loader_reconstructs_only_candles_strictly_closed_at_fetch(tmp_path, monkeypatch, cutoff):
    api = module()
    monkeypatch.setattr(api, "_now_ms", lambda: cutoff)
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(i) for i in range(3)])])
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + 3 * HOUR)
    frame, _ = api.load_snapshot(tmp_path, manifest["dataset_id"])
    assert len(frame) == 1
    assert frame.index[0] == pd.Timestamp(START, unit="ms", tz="UTC")


@pytest.mark.parametrize("entry", [None, "not an entry", {}, {"sha256": "missing path"}, "missing_digest"])
def test_malformed_raw_manifest_entries_raise_value_error(tmp_path, monkeypatch, entry):
    api, manifest = snapshot(tmp_path, monkeypatch)
    if entry == "missing_digest":
        entry = {"path": manifest["raw_pages"][0]["path"]}
    manifest["raw_pages"][0] = entry
    save_manifest(tmp_path, manifest)
    with pytest.raises(ValueError):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


def test_empty_raw_with_updated_digest_cannot_attest_parquet(tmp_path, monkeypatch):
    api, manifest = snapshot(tmp_path, monkeypatch)
    replace_raw(tmp_path, manifest, [[]])
    with pytest.raises(ValueError):
        api.load_snapshot(tmp_path, manifest["dataset_id"])
