"""Verified read-only projections of Batch001. Standard library only; no engine imports.

Re-read and hash dependencies on every public operation. Hashes provide tamper
 evidence relative to the local registry, not protection from a same-user rewrite
 of the entire registry and all evidence. Never run research to explain a fill.
"""

from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sqlite3


class IntegrityError(ValueError):
    """Persisted evidence is missing, inconsistent, or no longer hash-bound."""


def _canonical(value, *, ascii=False):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii, allow_nan=False
    ).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value):
    return _sha(_canonical(value))


def _require(condition, message):
    if not condition:
        raise IntegrityError(message)


def _time(value):
    parsed = datetime.fromisoformat(value)
    _require(
        parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0, "Timestamp must be UTC"
    )
    return int(parsed.timestamp())


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _verified(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        try:
            snapshot = self._load()
            return method(self, snapshot, *args, **kwargs)
        except IntegrityError:
            raise
        except (OSError, sqlite3.Error, KeyError, TypeError, IndexError, ValueError, StopIteration) as exc:
            raise IntegrityError(f"Cannot verify persisted evidence: {exc}") from exc

    return wrapped


LIMITATIONS = [
    "ผลเป็นการจำลอง Batch001 เท่านั้น ไม่ใช่กำไรจริงและไม่อนุมัติการทดลองใหม่",
    "คำอธิบาย SMA คำนวณย้อนหลังเพื่อแสดงผล ไม่ใช่ข้อความเหตุผลดั้งเดิมของโมเดล",
    "ไม่มีบันทึกวงจรคำสั่ง broker/warnings ฉบับเต็ม และไม่มี stress ledger/curve หรือ OOS stress ครบถ้วน",
    "ค่าธรรมเนียมเป็นสมมติฐาน ไม่ยืนยันค่าบัญชีจริง ไม่มี market impact; เงินจัดสรรเท่ากันไม่แปลว่าความเสี่ยงหรือเวลาถือเท่ากัน",
]
SCOPES = {
    "development": "ช่วงพัฒนา",
    "oos_1": "นอกตัวอย่าง 1",
    "oos_2": "นอกตัวอย่าง 2",
    "oos_3": "นอกตัวอย่าง 3 / holdout ที่เปิดเผยแล้ว",
}


class EvidenceStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def _path(self, relative):
        _require(isinstance(relative, str) and "\\" not in relative, "Unsafe evidence path")
        token = PurePosixPath(relative)
        _require(
            not token.is_absolute() and ":" not in relative and ".." not in token.parts,
            "Unsafe evidence path",
        )
        path = self.root.joinpath(*token.parts)
        _require(path.resolve() == path and path.is_file(), f"Missing/symlinked evidence: {relative}")
        return path

    def _bytes(self, relative, expected=None):
        data = self._path(relative).read_bytes()
        if expected is not None:
            _require(_sha(data) == expected, f"SHA256 mismatch: {relative}")
        return data

    def _json(self, relative, expected=None):
        return json.loads(self._bytes(relative, expected))

    def _load(self):
        dbpath = self._path("storage/lab.sqlite")
        db = sqlite3.connect(dbpath.as_uri() + "?mode=ro", uri=True)
        try:
            db.execute("PRAGMA query_only=ON")
            rows = db.execute(
                "SELECT id,kind,payload,created,previous,hash FROM events ORDER BY id"
            ).fetchall()
        finally:
            db.close()
        previous, events = "0" * 64, []
        for number, (ident, kind, payload, created, prior, hashed) in enumerate(rows, 1):
            _require(
                ident == number
                and prior == previous
                and hashed == _digest([ident, kind, payload, created, previous]),
                f"Registry chain invalid at {number}",
            )
            events.append(
                dict(id=ident, kind=kind, payload=json.loads(payload), created=created, hash=hashed)
            )
            previous = hashed
        # Pin the reviewed Batch001 head: valid prefix truncation is not evidence.
        _require(
            len(events) >= 88
            and events[87]["hash"] == "84a4f875e7849cf6b6bdb6d786e8522e364a61bcf22a66636907709c42f6bf52",
            "Reviewed Batch001 registry head missing/changed",
        )
        publications = [
            e
            for e in events
            if e["kind"] == "batch_report_published"
            and e["payload"].get("manifest") == "reports/batch001-artifact-manifest.json"
        ]
        _require(len(publications) == 1, "Missing/ambiguous published Batch001 manifest")
        publication = publications[0]["payload"]
        manifest = self._json(publication["manifest"], publication["manifest_sha256"])
        _require(
            manifest["spec_id"] == publication["spec_id"]
            and manifest["status"] == publication["status"]
            and manifest["engine_evaluations"] == publication["engine_evaluations"] == 20,
            "Publication binding mismatch",
        )
        byhash = {e["hash"]: e for e in events}
        approval = byhash[manifest["approval_event"]]
        closed = byhash[manifest["approval_closed_event"]]
        _require(
            approval["kind"] == "approval"
            and closed["kind"] == "revocation"
            and closed["payload"]["approval_event"] == approval["hash"],
            "Approval/revocation binding mismatch",
        )
        spec = self._json("governance/specs/" + manifest["spec_id"] + ".json")
        _require(
            _digest({k: v for k, v in spec.items() if k != "spec_id"})
            == spec["spec_id"]
            == manifest["spec_id"],
            "Spec digest mismatch",
        )
        _require(
            any(e["kind"] == "experiment_spec_proposed" and e["payload"] == spec for e in events),
            "Spec absent from registry",
        )
        for key in ("spec_id", "code_hash", "dataset_hash", "policy_hash", "strategy_hash"):
            _require(approval["payload"][key] == manifest[key], f"Approved {key} mismatch")
            if key in spec:
                _require(spec[key] == manifest[key], f"Spec {key} mismatch")
        codefiles = sorted(self.root.joinpath("src/trading_lab").rglob("*.py")) + [
            self.root / "pyproject.toml",
            self.root / "uv.lock",
        ]
        codehash = _digest(
            [
                (p.relative_to(self.root).as_posix(), _sha(self._bytes(p.relative_to(self.root).as_posix())))
                for p in codefiles
            ]
        )
        _require(codehash == manifest["code_hash"], "Approved code/dependencies changed")
        _require(
            _sha(self._bytes("src/trading_lab/backtest.py")) == manifest["strategy_hash"],
            "Strategy source changed",
        )
        _require(
            _digest(self._json("governance/safety-policy.json")) == manifest["policy_hash"], "Policy changed"
        )
        files = {}
        for record in manifest["files"]:
            data = self._bytes(record["path"], record["sha256"])
            _require(len(data) == record["bytes"], "Report size mismatch")
            files[record["path"]] = data
        report = json.loads(files["reports/batch001-metrics.json"])
        _require(
            report["code_hash"] == codehash
            and report["dataset_sha256"] == manifest["dataset_hash"]
            and report["spec_id"] == spec["spec_id"],
            "Metrics report identity mismatch",
        )
        artifacts = {}
        for record in manifest["experiment_artifacts"]:
            _require(
                any(e["kind"] == "experiment_completed" and e["payload"] == record for e in events),
                "Experiment not registry-bound",
            )
            artifact = self._json(record["artifact"], record["artifact_sha256"])
            _require(
                artifact["run_id"] == record["run_id"]
                and artifact["spec_id"] == spec["spec_id"]
                and artifact["parameters"] == record["parameters"]
                and artifact["simulation"] is True,
                "Experiment identity mismatch",
            )
            artifacts[f"{record['parameters']['fast']}-{record['parameters']['slow']}"] = (record, artifact)
        _require(
            len(artifacts) == 4 and report["source_artifacts"] == manifest["experiment_artifacts"],
            "Incomplete artifact set",
        )
        dataset = self._json(f"data/{spec['dataset_id']}/manifest.json")
        identity = _sha(_canonical({k: v for k, v in dataset.items() if k != "dataset_sha256"}, ascii=True))
        _require(
            identity == dataset.get("dataset_sha256", identity) == manifest["dataset_hash"],
            "Canonical dataset digest mismatch",
        )
        _require(
            any(e["kind"] == "dataset_ingested" and e["payload"] == dataset for e in events),
            "Dataset not registry-bound",
        )
        self._bytes("data/" + dataset["parquet_path"], dataset["sha256"])
        raw, cursor = {}, dataset["start_ms"]
        for number, page in enumerate(dataset["raw_pages"]):
            _require(
                page["path"] == f"{spec['dataset_id']}/raw-{number:05d}.json", "Unexpected raw page path"
            )
            relative = "data/" + page["path"]
            values = self._json(relative, page["sha256"])
            _require(isinstance(values, list) and 0 < len(values) <= 1000, "Invalid raw page")
            for index, row in enumerate(values):
                _require(
                    isinstance(row, list)
                    and len(row) == 12
                    and type(row[0]) is int
                    and row[0] == cursor
                    and row[6] == cursor + 3599999,
                    "Invalid/discontinuous raw timestamp",
                )
                nums = [float(v) for v in row[1:6]]
                o, h, low, c, v = nums
                _require(
                    all(math.isfinite(x) for x in nums)
                    and min(o, h, low, c) > 0
                    and v >= 0
                    and h >= max(o, low, c)
                    and low <= min(o, h, c),
                    "Invalid raw OHLCV",
                )
                raw[cursor // 1000] = dict(
                    row=row, path=relative, sha256=page["sha256"], row_index=index, values=nums
                )
                cursor += 3600000
        _require(
            len(raw) == dataset["rows"]
            and cursor == dataset["end_ms"]
            and cursor <= _time(dataset["fetched_at"]) * 1000,
            "Dataset coverage mismatch",
        )
        _require(
            len(report["metrics"]) == 64 and len(report["windows"]) == 16, "Incomplete metrics/window set"
        )
        cards, sources = self._knowledge(events)
        return dict(
            cards=cards,
            sources=sources,
            events=events,
            manifest=manifest,
            publication=publication,
            spec=spec,
            report=report,
            artifacts=artifacts,
            dataset=dataset,
            raw=raw,
            review=json.loads(files["reports/batch001-independent-performance-review.json"]),
        )

    def _knowledge(self, events):
        cards, sources = [], {}
        for event in events:
            if event["kind"] != "knowledge_card":
                continue
            record = event["payload"]
            ident = record["card_id"]
            _require(len(ident) == 64 and all(c in "0123456789abcdef" for c in ident), "Invalid card ID")
            saved = self._json(f"knowledge/cards/{ident}.json")
            _require(
                saved == record and _digest({k: v for k, v in saved.items() if k != "card_id"}) == ident,
                "Card canonical/registry mismatch",
            )
            _require(saved["card"]["kind"] == "EVIDENCE_BACKED_CLAIM", "Forbidden factual promotion")
            for ref in saved["sources"]:
                sid = ref["source_id"]
                _require(len(sid) == 64 and all(c in "0123456789abcdef" for c in sid), "Invalid source ID")
                source = self._json(f"knowledge/sources/{sid}.json")
                _require(
                    _digest({k: v for k, v in source.items() if k != "source_id"})
                    == sid
                    == source["source_id"],
                    "Source canonical mismatch",
                )
                _require(
                    _sha(source["text"].encode("utf-8")) == source["text_sha256"],
                    "Source text digest mismatch",
                )
                _require(
                    all(source[k] == ref[k] for k in ("source_id", "url", "retrieved_at")),
                    "Card source reference mismatch",
                )
                _require(
                    any(e["kind"] == "source_retrieved" and e["payload"] == ref for e in events),
                    "Source absent from registry",
                )
                sources[sid] = source
            for claim in saved["card"]["claims"]:
                _require(
                    claim["source_id"] in sources
                    and " ".join(claim["quote"].split()).casefold()
                    in " ".join(sources[claim["source_id"]]["text"].split()).casefold(),
                    "Claim quote absent from source",
                )
            cards.append(
                dict(
                    id=ident,
                    version=saved["version"],
                    **saved["card"],
                    sources=saved["sources"],
                    verification_scope=saved["verification_scope"],
                )
            )
        _require(cards and sources, "Knowledge evidence missing")
        return cards, sources

    @staticmethod
    def _scope(row):
        return {
            **{k: row[k] for k in ("start_utc", "end_exclusive_utc")},
            "id": row["scope"],
            "label_th": SCOPES[row["scope"]],
        }

    def _strategies(self, s):
        result = []
        for ident, (record, artifact) in s["artifacts"].items():
            fast, slow = artifact["parameters"]["fast"], artifact["parameters"]["slow"]
            result.append(
                dict(
                    id=ident,
                    label=f"SMA {fast}/{slow}",
                    fast=fast,
                    slow=slow,
                    run_id=record["run_id"],
                    scopes=[
                        self._scope(w)
                        for w in s["report"]["windows"]
                        if w["configuration"] == ident.replace("-", "/")
                    ],
                )
            )
        return result

    def _select(self, s, strategy, scope):
        if strategy not in s["artifacts"] or scope not in SCOPES:
            raise LookupError("Unknown strategy or scope")
        record, artifact = s["artifacts"][strategy]
        window = next(
            (
                w
                for w in s["report"]["windows"]
                if w["configuration"] == strategy.replace("-", "/") and w["scope"] == scope
            ),
            None,
        )
        _require(window is not None, "Missing saved window")
        result = (
            artifact["development"]
            if scope == "development"
            else artifact["walk_forward"]["folds"][int(scope[-1]) - 1]["result"]
        )
        return record, artifact, window, result

    @staticmethod
    def _provenance(s, record):
        return dict(
            artifact_path=record["artifact"],
            artifact_sha256=record["artifact_sha256"],
            dataset_hash=s["manifest"]["dataset_hash"],
            raw_source=s["dataset"]["source"],
        )

    @staticmethod
    def _trades(result):
        trades = []
        for prefix, key in [("closed", "trade_ledger"), ("open", "terminal_positions")]:
            for number, row in enumerate(result[key], 1):
                trades.append(
                    dict(
                        id=f"{prefix}-{number:04d}",
                        status="realized" if prefix == "closed" else "terminal_open",
                        entry_time=row["entry_time"],
                        exit_time=row.get("exit_time"),
                        quantity_btc=row["size"],
                        entry_price=row["entry_price"],
                        exit_price=row.get("exit_price"),
                        commission_usdt=row["commission"] if prefix == "closed" else row["entry_commission"],
                        net_pnl_usdt=row.get("net_pnl"),
                        mark_pnl_usdt=row.get("net_mark_pnl"),
                    )
                )
        return trades

    @staticmethod
    def _candles(s, window, fast, slow):
        start, end = _time(window["start_utc"]), _time(window["end_exclusive_utc"])
        raw = [(t, r) for t, r in s["raw"].items() if start - slow * 3600 <= t < end]
        closes, candles = [], []
        for t, row in raw:
            o, h, low, c, v = row["values"]
            closes.append(c)
            candles.append(
                dict(
                    time=t,
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    volume=v,
                    sma_fast=math.fsum(closes[-fast:]) / fast if len(closes) >= fast else None,
                    sma_slow=math.fsum(closes[-slow:]) / slow if len(closes) >= slow else None,
                )
            )
        return candles

    @staticmethod
    def _equity(s, result, window):
        initial = dict(
            time=_time(window["start_utc"]),
            sma=10000.0,
            cash=10000.0,
            buy_hold_10=10000.0,
            buy_hold_100=10000.0,
            drawdown_pct=0.0,
        )
        equity, peak = [initial], 10000.0
        for row in result["equity_curve"]:
            opened = _time(row["time"])
            close = s["raw"][opened]["values"][3]
            bh = {}
            for label, key in [
                ("buy_hold_10", "buy_and_hold_equal_allocation"),
                ("buy_hold_100", "buy_and_hold"),
            ]:
                saved = result["baselines"][key]
                bh[label] = (
                    saved["spot_cash"] + saved["size"] * close
                    if opened >= _time(saved["entry_time"])
                    else 10000.0
                )
            peak = max(peak, row["equity"])
            equity.append(
                dict(
                    time=opened + 3600,
                    sma=row["equity"],
                    cash=10000.0,
                    **bh,
                    drawdown_pct=(row["equity"] / peak - 1) * 100,
                )
            )
        return equity

    @staticmethod
    def _critic(s, strategy, run_id):
        original = next(
            (
                item["critique"]["verdict"]
                for item in s["report"]["independent_model_lessons"]
                if item["run_id"] == run_id
            ),
            None,
        )
        review = next(
            r
            for r in s["review"]["per_configuration_verdicts"]
            if r["configuration"] == strategy.replace("-", "/")
        )
        return dict(
            original_verdict=original,
            batch_verdict=review["verdict"],
            explanation_th=review["explanation_th"],
        )

    @_verified
    def view(self, s, strategy, scope):
        record, artifact, window, result = self._select(s, strategy, scope)
        trades = self._trades(result)
        executions = []
        for trade in trades:
            executions.append(
                dict(
                    time=_time(trade["entry_time"]),
                    price=trade["entry_price"],
                    side="buy",
                    trade_id=trade["id"],
                    label="ซื้อจาก ledger",
                )
            )
            if trade["exit_time"] is not None:
                executions.append(
                    dict(
                        time=_time(trade["exit_time"]),
                        price=trade["exit_price"],
                        side="sell",
                        trade_id=trade["id"],
                        label="ขายจาก ledger",
                    )
                )
        selected = next(item for item in self._strategies(s) if item["id"] == strategy)
        selected.pop("scopes")
        return dict(
            strategy=selected,
            scope=self._scope(window),
            candles=self._candles(s, window, **artifact["parameters"]),
            executions=sorted(executions, key=lambda x: x["time"]),
            trades=trades,
            equity=self._equity(s, result, window),
            metrics=[
                m
                for m in s["report"]["metrics"]
                if m["configuration"] == strategy.replace("-", "/") and m["scope"] == scope
            ],
            critic=self._critic(s, strategy, record["run_id"]),
            costs=dict(
                commission_rate=s["spec"]["commission"],
                spread_rate=s["spec"]["spread"],
                spread_application_th="Spread รวมในราคาเข้าซื้อแล้ว ไม่หักซ้ำเป็นค่าธรรมเนียม; commission แยกเข้า/ออก และ terminal mark ไม่มีค่าขาย",
            ),
            provenance=self._provenance(s, record),
            limitations_th=list(LIMITATIONS),
        )

    @staticmethod
    def _trace(s, role, stamp):
        row = s["raw"][_time(stamp)]
        return dict(
            role=role,
            candle_open_time=stamp,
            raw_path=row["path"],
            raw_sha256=row["sha256"],
            row_index=row["row_index"],
            raw_row=row["row"],
            ohlcv=dict(zip(("open", "high", "low", "close", "volume"), row["values"])),
        )

    @staticmethod
    def _cross(s, stamp, fast, slow):
        current = _time(stamp)

        def average(t, n):
            return math.fsum(s["raw"][t - i * 3600]["values"][3] for i in range(n)) / n

        return dict(
            previous_fast=average(current - 3600, fast),
            previous_slow=average(current - 3600, slow),
            current_fast=average(current, fast),
            current_slow=average(current, slow),
        )

    def _trade(self, s, strategy, scope, trade_id):
        record, artifact, window, result = self._select(s, strategy, scope)
        trades = self._trades(result)
        selected = next((t for t in trades if t["id"] == trade_id), None)
        if selected is None:
            raise LookupError("Unknown trade ID")
        isclosed = selected["status"] == "realized"
        ledger = result["trade_ledger"] if isclosed else result["terminal_positions"]
        row = ledger[int(trade_id.split("-")[1]) - 1]
        trace = [
            self._trace(s, "entry_signal", row["entry_signal_time"]),
            self._trace(s, "entry_execution", row["entry_time"]),
        ]
        entry_cross = self._cross(s, row["entry_signal_time"], **artifact["parameters"])
        exit_cross = None
        if isclosed:
            trace += [
                self._trace(s, "exit_signal", row["exit_signal_time"]),
                self._trace(s, "exit_execution", row["exit_time"]),
            ]
            exit_cross = self._cross(s, row["exit_signal_time"], **artifact["parameters"])
        else:
            trace.append(self._trace(s, "terminal_mark", row["mark_time"]))
        commission = s["spec"]["commission"]
        entryfee = row["size"] * row["entry_price"] * commission if isclosed else row["entry_commission"]
        selected.update(
            entry_signal_time=row["entry_signal_time"],
            exit_signal_time=row.get("exit_signal_time"),
            entry_commission_usdt=entryfee,
            exit_commission_usdt=row["size"] * row["exit_price"] * commission if isclosed else None,
            commission_rate=commission,
            spread_rate=s["spec"]["spread"],
            entry_spread_usdt=row["size"] * (row["entry_price"] - trace[1]["ohlcv"]["open"]),
            terminal_mark_time=row.get("mark_time"),
            terminal_mark_price=row.get("mark_price"),
        )
        rationale = dict(
            kind="DETERMINISTIC_RECONSTRUCTION_NOT_ORIGINAL_NARRATIVE",
            entry_th="สร้างคำอธิบายใหม่แบบกำหนดแน่นอน: SMA เร็วตัดขึ้นเหนือ SMA ช้า ณ แท่งสัญญาณที่บันทึก ใช้ราคาปิดถึงแท่งนั้นเท่านั้น ซื้อที่เปิดแท่งถัดไปตาม ledger ไม่ใช่ข้อความโมเดลดั้งเดิม",
            exit_th="SMA เร็วตัดลงต่ำกว่า SMA ช้า ณ แท่งสัญญาณที่บันทึก ขายเปิดแท่งถัดไปตาม ledger"
            if isclosed
            else "ยังเปิดสถานะ ไม่มีคำสั่งขายหรือค่าขาย ใช้ราคาปิดสุดท้ายเพื่อประเมินมูลค่าเท่านั้น",
            entry_cross=entry_cross,
            exit_cross=exit_cross,
            signal_timestamp_semantics_th="เวลาแท่งสัญญาณคือเวลาเปิดของแท่งที่ปิดแล้ว; ทราบสัญญาณเมื่อครบหนึ่งชั่วโมง และ execution คือเวลาเปิดแท่งถัดไป ตัวเลข SMA เป็นการสร้างคำอธิบายย้อนหลัง ไม่รันกลยุทธ์",
        )
        return dict(
            trade=selected,
            rationale=rationale,
            trace=trace,
            provenance=self._provenance(s, record),
            limitations_th=list(LIMITATIONS),
        )

    @_verified
    def trade(self, s, strategy, scope, trade_id):
        return self._trade(s, strategy, scope, trade_id)

    @_verified
    def raw(self, s, strategy, scope, trade_id, role):
        detail = self._trade(s, strategy, scope, trade_id)
        selected = next((r for r in detail["trace"] if r["role"] == role), None)
        if selected is None:
            raise LookupError("Unknown trace role for selected trade")
        return selected

    @_verified
    def source(self, s, source_id):
        if source_id not in s["sources"]:
            raise LookupError("Source is not linked to a verified card")
        return {
            k: s["sources"][source_id][k]
            for k in ("source_id", "url", "title", "retrieved_at", "text", "text_sha256")
        }

    @_verified
    def research(self, s):
        addressed = {e["payload"]["gap_id"] for e in s["events"] if e["kind"] == "knowledge_addressed"}
        questions = [
            dict(
                topic=e["payload"]["topic"],
                origin=e["payload"]["origin"],
                status="EVIDENCE_ADDRESSED_NOT_CERTAIN" if e["payload"]["gap_id"] in addressed else "OPEN",
            )
            for e in s["events"]
            if e["kind"] == "knowledge_gap"
        ]
        critics = [
            dict(configuration=ident.replace("-", "/"), **self._critic(s, ident, record["run_id"]))
            for ident, (record, artifact) in s["artifacts"].items()
        ]
        hypotheses = []
        for item in s["report"]["next_proposals"]:
            proposal = item["proposal"]
            params = proposal["proposed_parameters"]
            _require(item["executed"] is False, "Unexpected executed next proposal")
            hypotheses.append(
                dict(
                    configuration=f"{params['fast']}/{params['slow']}",
                    hypothesis_th=proposal["hypothesis_th"],
                    rationale_th=proposal["rationale_th"],
                    status="PROPOSED_NOT_EXECUTED",
                )
            )
        knowledge_lessons = [
            e["payload"]["lesson_th"] for e in s["events"] if e["kind"] == "research_method_lesson"
        ]
        experiment_lessons = [
            lesson
            for item in s["report"]["independent_model_lessons"]
            for lesson in item["critique"].get("lessons_th", [])
        ]
        batch_lessons = s["review"]["lessons_th"]
        if isinstance(batch_lessons, str):
            batch_lessons = [batch_lessons]
        agents = [
            dict(
                role="knowledge_researcher",
                learned_th=knowledge_lessons,
                proposed_th=[q["topic"] for q in questions if q["status"] == "OPEN"],
            ),
            dict(role="experiment_critic", learned_th=experiment_lessons, proposed_th=[]),
            dict(
                role="experiment_researcher",
                learned_th=[],
                proposed_th=[h["hypothesis_th"] for h in hypotheses],
            ),
            dict(
                role="independent_batch_reviewer",
                learned_th=batch_lessons,
                proposed_th=[
                    item["hypothesis_th"]
                    for item in s["review"]["proposed_next_hypotheses_th"]
                    if item["executed"] is False
                ],
            ),
        ]
        history = []
        for event in s["events"]:
            payload = event["payload"]
            text = payload.get("lesson_th") or payload.get("topic") or payload.get("status") or event["kind"]
            history.append(
                dict(
                    event_id=event["id"],
                    kind=event["kind"],
                    created=event["created"],
                    summary_th="บันทึกหลักฐาน: " + text,
                    evidence_id=event["hash"],
                )
            )
        facts = [
            dict(
                statement_th=f"Batch001: {len(s['artifacts'])} configurations; {s['manifest']['engine_evaluations']} saved engine evaluations; {len(s['raw'])} archived hourly rows",
                evidence=s["publication"]["manifest_sha256"],
                kind="VERIFIED_ARTIFACT_METADATA",
            )
        ]
        return dict(
            cards=s["cards"],
            questions=questions,
            sources=[
                {k: source[k] for k in ("source_id", "url", "title", "retrieved_at")}
                for source in s["sources"].values()
            ],
            history=history,
            agents=agents,
            critics=critics,
            hypotheses=hypotheses,
            facts=facts,
            limitations_th=list(LIMITATIONS)
            + ["การตรวจ quote และ hash ไม่ใช่การรับรองความจริงทั่วไป ไม่ส่งเสริมเป็น FACT; ข้อเสนอไม่ได้ดำเนินการ"],
        )

    @_verified
    def overview(self, s):
        m = s["manifest"]
        return dict(
            batch_id="001",
            spec_id=m["spec_id"],
            simulation=True,
            status=m["status"],
            integrity=dict(
                verified=True,
                event_count=len(s["events"]),
                dataset_rows=len(s["raw"]),
                artifact_count=len(m["files"]) + len(m["experiment_artifacts"]),
                engine_evaluations=m["engine_evaluations"],
                code_hash=m["code_hash"],
                dataset_hash=m["dataset_hash"],
                policy_hash=m["policy_hash"],
                manifest_hash=s["publication"]["manifest_sha256"],
            ),
            strategies=self._strategies(s),
            limitations_th=list(LIMITATIONS),
        )
