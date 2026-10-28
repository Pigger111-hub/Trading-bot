"""Read-only integration against actual Batch001; corruption uses scratch copies only."""

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_overview_verified_actual_batch():
    from dashboard_api.evidence import EvidenceStore

    result = EvidenceStore(ROOT).overview()
    assert result["integrity"]["verified"] is True
    assert result["integrity"]["event_count"] == 88
    assert result["integrity"]["dataset_rows"] == 17520
    assert result["integrity"]["engine_evaluations"] == 20
    assert (
        result["integrity"]["code_hash"] == "68878a4bf03dd9912e4970ba126858ac7c1fbbc6f995700fb8a735b681cbbec8"
    )
    assert [s["id"] for s in result["strategies"]] == ["10-50", "10-100", "20-50", "20-100"]
    assert [s["id"] for s in result["strategies"][0]["scopes"]] == ["development", "oos_1", "oos_2", "oos_3"]
    assert result["status"] == "HALTED_AWAITING_HUMAN_RESULTS_REVIEW"


def test_view_projects_saved_window_metrics_ledger_and_close_clock():
    from dashboard_api.evidence import EvidenceStore

    store = EvidenceStore(ROOT)
    report = json.loads((ROOT / "reports/batch001-metrics.json").read_text())
    view = store.view("10-50", "oos_1")
    expected = [m for m in report["metrics"] if m["configuration"] == "10/50" and m["scope"] == "oos_1"]
    assert view["metrics"] == expected
    artifact = json.loads((ROOT / view["provenance"]["artifact_path"]).read_text())
    result = artifact["walk_forward"]["folds"][0]["result"]
    from datetime import datetime

    curve = result["equity_curve"]
    assert len(view["equity"]) == len(curve) + 1  # explicit initial cash at evaluation open
    for projected, persisted in zip(view["equity"][1:], curve):
        assert projected["time"] == int(datetime.fromisoformat(persisted["time"]).timestamp()) + 3600
        assert projected["sma"] == persisted["equity"]
    assert view["equity"][-1]["buy_hold_10"] == pytest.approx(
        result["baselines"]["buy_and_hold_equal_allocation"]["terminal_equity"]
    )
    assert len(view["trades"]) == len(result["trade_ledger"]) + len(result["terminal_positions"])
    assert len(view["executions"]) == 2 * len(result["trade_ledger"]) + len(result["terminal_positions"])
    candles = view["candles"]
    assert candles[0]["time"] < int(datetime.fromisoformat(view["scope"]["start_utc"]).timestamp())
    assert candles[49]["sma_slow"] == pytest.approx(sum(c["close"] for c in candles[:50]) / 50)
    assert view["trades"][0]["net_pnl_usdt"] == result["trade_ledger"][0]["net_pnl"]


@pytest.mark.parametrize(
    "strategy,scope", [("10/50", "oos_1"), ("../x", "oos_1"), ("10-50", "all"), ("10-50", "../x")]
)
def test_view_unknown_selector(strategy, scope):
    from dashboard_api.evidence import EvidenceStore

    with pytest.raises(LookupError):
        EvidenceStore(ROOT).view(strategy, scope)


def test_trade_trace_actual_raw_mapping_and_reconstructed_prior_cross():
    from dashboard_api.evidence import EvidenceStore
    from datetime import datetime

    store = EvidenceStore(ROOT)
    detail = store.trade("10-50", "development", "closed-0001")
    trade = detail["trade"]
    assert detail["rationale"]["kind"] == "DETERMINISTIC_RECONSTRUCTION_NOT_ORIGINAL_NARRATIVE"
    cross = detail["rationale"]["entry_cross"]
    assert cross["previous_fast"] < cross["previous_slow"]
    assert cross["current_fast"] > cross["current_slow"]
    cross = detail["rationale"]["exit_cross"]
    assert cross["previous_fast"] > cross["previous_slow"]
    assert cross["current_fast"] < cross["current_slow"]
    assert [r["role"] for r in detail["trace"]] == [
        "entry_signal",
        "entry_execution",
        "exit_signal",
        "exit_execution",
    ]
    for row in detail["trace"]:
        payload = (ROOT / row["raw_path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["raw_sha256"]
        assert json.loads(payload)[row["row_index"]] == row["raw_row"]
        assert row["raw_row"][0] == int(datetime.fromisoformat(row["candle_open_time"]).timestamp()) * 1000
        assert row["ohlcv"]["close"] == float(row["raw_row"][4])
    entryraw = detail["trace"][1]["ohlcv"]["open"]
    assert trade["entry_spread_usdt"] == pytest.approx(
        trade["quantity_btc"] * (trade["entry_price"] - entryraw)
    )
    assert trade["commission_usdt"] == pytest.approx(
        trade["entry_commission_usdt"] + trade["exit_commission_usdt"]
    )
    assert trade["net_pnl_usdt"] == pytest.approx(
        trade["quantity_btc"] * (trade["exit_price"] - trade["entry_price"]) - trade["commission_usdt"]
    )
    assert store.raw("10-50", "development", "closed-0001", "entry_execution") == detail["trace"][1]


def test_terminal_open_never_invents_exit_or_exit_fee():
    from dashboard_api.evidence import EvidenceStore

    store = EvidenceStore(ROOT)
    detail = store.trade("10-50", "development", "open-0001")
    trade = detail["trade"]
    assert trade["status"] == "terminal_open"
    for key in ["exit_time", "exit_price", "exit_signal_time", "exit_commission_usdt", "net_pnl_usdt"]:
        assert trade[key] is None
    assert trade["commission_usdt"] == trade["entry_commission_usdt"]
    assert trade["mark_pnl_usdt"] == pytest.approx(
        trade["quantity_btc"] * (trade["terminal_mark_price"] - trade["entry_price"])
        - trade["entry_commission_usdt"]
    )
    assert [r["role"] for r in detail["trace"]] == ["entry_signal", "entry_execution", "terminal_mark"]
    assert detail["rationale"]["exit_cross"] is None


@pytest.mark.parametrize(
    "trade,role",
    [
        ("closed-0000", "entry_signal"),
        ("../x", "entry_signal"),
        ("closed-0001", "../x"),
        ("open-0001", "exit_execution"),
    ],
)
def test_trade_raw_bad_selectors(trade, role):
    from dashboard_api.evidence import EvidenceStore

    with pytest.raises(LookupError):
        EvidenceStore(ROOT).raw("10-50", "development", trade, role)


def test_research_returns_only_registry_bound_canonical_cards_and_sources():
    from dashboard_api.evidence import EvidenceStore

    store = EvidenceStore(ROOT)
    result = store.research()
    assert len(result["cards"]) == 2
    assert len(result["sources"]) == 4
    for card in result["cards"]:
        saved = json.loads((ROOT / "knowledge/cards" / f"{card['id']}.json").read_text())
        assert card["claims"] == saved["card"]["claims"]
        assert card["kind"] == "EVIDENCE_BACKED_CLAIM"
        for ref in card["sources"]:
            source = store.source(ref["source_id"])
            assert hashlib.sha256(source["text"].encode()).hexdigest() == source["text_sha256"]
    assert len(result["critics"]) == len(result["hypotheses"]) == 4
    assert all(h["status"] == "PROPOSED_NOT_EXECUTED" for h in result["hypotheses"])
    assert any(q["status"] == "OPEN" for q in result["questions"])
    assert any(q["status"] == "EVIDENCE_ADDRESSED_NOT_CERTAIN" for q in result["questions"])
    assert all(f["kind"] == "VERIFIED_ARTIFACT_METADATA" for f in result["facts"])
    assert result["history"]
    assert any(a["learned_th"] for a in result["agents"])


@pytest.mark.parametrize(
    "source", ["../x", "0" * 64, "8659bcce18e77badf14736f7bcb40efe4ace5f803469a9acb4f8d75db0784300"]
)
def test_sources_not_linked_to_verified_cards_are_not_addressable(source):
    from dashboard_api.evidence import EvidenceStore

    with pytest.raises(LookupError):
        EvidenceStore(ROOT).source(source)


def test_agent_proposals_are_text_not_nested_unexecuted_records():
    from dashboard_api.evidence import EvidenceStore

    for agent in EvidenceStore(ROOT).research()["agents"]:
        assert all(isinstance(value, str) for value in agent["learned_th"] + agent["proposed_th"])


@pytest.fixture(scope="module")
def scratch_evidence_copy():
    """Actual evidence COPY in Hermes scratch, exclusively for corruption tests."""
    import os
    import shutil
    import tempfile

    scratch = Path(os.environ["LOCALAPPDATA"]) / "hermes/cache/scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="evidence-corruption-", dir=scratch) as folder:
        root = Path(folder)
        for directory in [
            "storage",
            "data",
            "experiments",
            "reports",
            "knowledge",
            "governance",
            "src/trading_lab",
        ]:
            shutil.copytree(ROOT / directory, root / directory)
        for filename in ["pyproject.toml", "uv.lock"]:
            shutil.copy2(ROOT / filename, root / filename)
        # Published originals may have Windows read-only attributes; copies only.
        for path in root.rglob("*"):
            if path.is_file():
                path.chmod(0o600)
        yield root


def test_truncated_registry_rejected(scratch_evidence_copy):
    import sqlite3
    from dashboard_api.evidence import EvidenceStore, IntegrityError

    root = scratch_evidence_copy
    store = EvidenceStore(root)
    store.overview()
    path = root / "storage/lab.sqlite"
    original = path.read_bytes()
    try:
        db = sqlite3.connect(path)
        try:
            with db:
                db.execute("DROP TRIGGER no_delete")
                db.execute("DELETE FROM events WHERE id=88")
        finally:
            db.close()
        with pytest.raises(IntegrityError):
            store.overview()
    finally:
        path.write_bytes(original)


def _inventory(root):
    directories = ["storage", "data", "experiments", "reports", "knowledge", "governance", "src/trading_lab"]
    paths = [p for d in directories for p in (root / d).rglob("*")]
    paths += [root / "pyproject.toml", root / "uv.lock", root / ".gitattributes"]
    return {
        p.relative_to(root).as_posix(): (
            p.stat().st_size,
            p.stat().st_mtime_ns,
            hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        if p.is_file()
        else None
        for p in paths
    }


def test_every_saved_window_all_64_metrics_and_read_only_inventory():
    from dashboard_api.evidence import EvidenceStore
    from datetime import datetime

    before = _inventory(ROOT)
    store = EvidenceStore(ROOT)
    overview = store.overview()
    seen = []
    for strategy in overview["strategies"]:
        for scope in strategy["scopes"]:
            view = store.view(strategy["id"], scope["id"])
            saved = json.loads((ROOT / view["provenance"]["artifact_path"]).read_text())
            result = (
                saved["development"]
                if scope["id"] == "development"
                else saved["walk_forward"]["folds"][int(scope["id"][-1]) - 1]["result"]
            )
            assert view["equity"][-1]["sma"] == result["terminal_equity"]
            assert view["equity"][-1]["buy_hold_10"] == pytest.approx(
                result["baselines"]["buy_and_hold_equal_allocation"]["terminal_equity"]
            )
            assert view["equity"][-1]["buy_hold_100"] == pytest.approx(
                result["baselines"]["buy_and_hold"]["terminal_equity"]
            )
            assert len(view["trades"]) == result["trades"] + len(result["terminal_positions"])
            assert view["scope"]["start_utc"] == scope["start_utc"]
            seen += view["metrics"]
            detail = store.trade(strategy["id"], scope["id"], "closed-0001")
            cross = detail["rationale"]["entry_cross"]
            assert (
                cross["previous_fast"] < cross["previous_slow"]
                and cross["current_fast"] > cross["current_slow"]
            )
            stamp = int(datetime.fromisoformat(detail["trade"]["entry_signal_time"]).timestamp())
            fast = strategy["fast"]
            closes = {c["time"]: c["close"] for c in view["candles"]}
            assert cross["current_fast"] == pytest.approx(
                sum(closes[stamp - i * 3600] for i in range(fast)) / fast
            )
            if result["terminal_positions"]:
                terminal = store.trade(strategy["id"], scope["id"], "open-0001")["trade"]
                assert terminal["net_pnl_usdt"] is None and terminal["exit_price"] is None
                assert terminal["mark_pnl_usdt"] == result["terminal_positions"][0]["net_mark_pnl"]
    report = json.loads((ROOT / "reports/batch001-metrics.json").read_text())
    assert seen == report["metrics"]
    research = store.research()
    store.source(research["sources"][0]["source_id"])
    store.raw("10-50", "development", "closed-0001", "entry_signal")
    assert _inventory(ROOT) == before


MANIFEST = json.loads((ROOT / "reports/batch001-artifact-manifest.json").read_text())
TAMPER_PATHS = (
    ["reports/batch001-artifact-manifest.json"]
    + [r["path"] for r in MANIFEST["files"]]
    + [r["artifact"] for r in MANIFEST["experiment_artifacts"]]
    + [
        "data/79f63ac8f5a247be94adc04f1fa29bb3/" + f
        for f in ["manifest.json", "candles.parquet", "raw-00000.json", "raw-00017.json"]
    ]
    + ["governance/safety-policy.json", "src/trading_lab/backtest.py", "pyproject.toml", "uv.lock"]
    + [p.relative_to(ROOT).as_posix() for p in (ROOT / "knowledge/cards").glob("*.json")]
    + ["knowledge/sources/41d4e03b8a5a84f3bd52f1713902696f251127069c6a548fb3c0b0bd10ee6344.json"]
)


@pytest.mark.parametrize("relative", TAMPER_PATHS)
def test_tampered_dependency_rejected_after_successful_startup(scratch_evidence_copy, relative):
    from dashboard_api.evidence import EvidenceStore, IntegrityError

    root = scratch_evidence_copy
    store = EvidenceStore(root)
    store.overview()
    path = root / relative
    original = path.read_bytes()
    try:
        if (
            relative.startswith("knowledge/")
            or relative.endswith("/manifest.json")
            or relative == "governance/safety-policy.json"
        ):
            value = json.loads(original)
            value["unreviewed_mutation"] = True
            replacement = json.dumps(value).encode()
        else:
            replacement = original + b" "
        path.write_bytes(replacement)
        for call, args in [
            (store.overview, ()),
            (store.view, ("10-50", "oos_1")),
            (store.trade, ("10-50", "development", "closed-0001")),
            (store.raw, ("10-50", "development", "closed-0001", "entry_execution")),
            (store.research, ()),
            (store.source, ("41d4e03b8a5a84f3bd52f1713902696f251127069c6a548fb3c0b0bd10ee6344",)),
        ]:
            with pytest.raises(IntegrityError):
                call(*args)
    finally:
        path.write_bytes(original)


def test_registry_payload_tamper_rejected(scratch_evidence_copy):
    from dashboard_api.evidence import EvidenceStore, IntegrityError
    import sqlite3

    root = scratch_evidence_copy
    path = root / "storage/lab.sqlite"
    original = path.read_bytes()
    try:
        db = sqlite3.connect(path)
        try:
            with db:
                db.execute("DROP TRIGGER no_update")
                db.execute("UPDATE events SET payload='{}' WHERE id=2")
        finally:
            db.close()
        with pytest.raises(IntegrityError, match="chain"):
            EvidenceStore(root).overview()
    finally:
        path.write_bytes(original)


def test_evidence_imports_stdlib_only():
    import ast
    import sys

    source = (ROOT / "dashboard/backend/dashboard_api/evidence.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module.split(".")[0] in sys.stdlib_module_names


def test_malformed_source_fails_with_integrity_error(scratch_evidence_copy):
    from dashboard_api.evidence import EvidenceStore, IntegrityError

    path = (
        scratch_evidence_copy
        / "knowledge/sources/41d4e03b8a5a84f3bd52f1713902696f251127069c6a548fb3c0b0bd10ee6344.json"
    )
    original = path.read_bytes()
    try:
        path.write_bytes(b"\xff")
        with pytest.raises(IntegrityError):
            EvidenceStore(scratch_evidence_copy).research()
    finally:
        path.write_bytes(original)
