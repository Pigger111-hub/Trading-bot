# Autonomous Trading Research Lab

Local-first research coordinated by **Hermes Agent**. Beginner explanations are in Thai. This is not a profit-seeking execution bot.

> **PAPER-ONLY / SIMULATED. No exchange credentials, exchange orders, futures, shorts, leverage, withdrawals, scheduled jobs, or continuous paper trading.** Implementing a strategy is not permission to execute it on market data.

## สถานะปัจจุบัน

- Phase 0: isolated Python environment, deterministic safety policy, explicit approval gate, atomic batch budgets, append-only/hash-chained SQLite audit events.
- Phase 1: Binance public OHLCV ingestion, immutable raw/Parquet snapshots with SHA256; real Hermes-powered, source-backed Thai knowledge research with independent review and persistent knowledge gaps.
- Phase 2: fixed SMA research engine, next-open execution, fractional BTC units, explicit terminal marks, chronological walk-forward and final holdout, cost stress, critique/lessons/next-proposal pipeline. Development end-to-end tests use **synthetic fixtures**, not market performance evidence.
- Actual strategy experiments require a passed independent code review and **separate human approval of a concrete batch**. None are implicitly approved by installation or unit tests.

## Two learning loops

### Knowledge Loop

`Research → Source retrieval → Exact-evidence checks → Independent model review → Versioned card → Open questions → Next research cycle`

- Research uses a reviewed primary-source catalog in `sources.py`, not an unrestricted crawler. Out-of-catalog questions remain gaps requiring source-catalog review.
- Hermes Researcher and Critic run in fresh contexts through the existing CLI/provider. No exchange API key is required. Model inference may use your provider quota or incur provider charges; free market data does **not** mean free inference.
- Calls use safe mode and a verified empty text-only toolset. The model returns JSON data; the controller, not the model, writes validated artifacts.
- Each invocation has an explicit cycle limit; current policy allows at most three cycles. Each cycle has at most two model calls and two source fetches. No automatic retry of invalid model responses.
- A card is an **EVIDENCE_BACKED_CLAIM**, never automatically a universal FACT. Quote presence and model support review are provenance checks, not proof of truth.
- New cards have immutable content IDs/version references. Uncertainties remain explicit and generate new questions. Failures are recorded, not filled with fabricated text.

### Experiment Loop

`Hypothesis/spec → Human-approved bounded batch → Backtest → Walk-forward validation → Deterministic checks → Independent critique → Lessons → Next proposal`

- Only the fixed built-in SMA strategy is supported. There is no executable strategy/plugin path, `eval`, dynamic code loading, or deployment command.
- The approved batch pins code/dependency-manifest hash, dataset hash, policy hash, exact parameter configurations, costs, validation protocol and trial budget.
- One trial is one approved parameter configuration. It performs **five engine evaluations**: initial-half development, three chronological out-of-sample folds, and doubled-cost development stress. Baseline calculations are deterministic accounting comparisons. The manifest also fixes an evaluation cap.
- Reservations are atomic. Failed/interrupted reservations consume budget; they are not silently rerun. Restart skips already reserved configurations.
- A new spec's final holdout may not overlap **any previously exposed development/evaluation/holdout data**, not just earlier final folds. The entire exposed data range is recorded at reservation. Re-downloading or truncating old data with another UUID does not make it fresh evidence. Only configurations in the same originally predeclared batch share that intentional exposure.
- All predeclared configurations may be evaluated as one batch, but no winner is automatically selected from the final holdout. Subsequent research needs untouched evaluation data.
- Critique cannot promote a strategy. Suggestions outside the approved spec are inert proposals requiring a new review/approval.
- Method/skill improvements are stored as **PENDING_HUMAN_REVIEW**, never installed or activated automatically.

## Install / verify

From this project directory in Git Bash:

```bash
uv sync --python 3.12 --extra dev --locked
uv run pytest -q -W error
uv run ruff check .
uv run trading-lab status
```

The project `.venv` is separate from Hermes's runtime. `uv.lock` pins the resolved dependencies.

## Commands

All commands are foreground and bounded. No scheduler has been registered.

```bash
# One autonomous knowledge cycle; may consume model quota.
uv run trading-lab research --cycles 1

# Optional explicit provider/model overrides, if you change your model configuration.
uv run trading-lab research --cycles 1 --provider openai-codex --model gpt-6.1-sol

# Public, read-only data ingestion. ISO dates without offsets mean UTC.
# The interval is [start, end), not an inclusive end date.
uv run trading-lab ingest --start 2024-10-01 --end 2026-10-01

# Generate a proposal, NOT approval or execution. Dataset IDs are 32-character UUID hex.
uv run trading-lab spec --dataset DATASET_UUID --fast 10,20 --slow 50,100 --budget 4

# Read-only Thai report generated from actual audit records.
uv run trading-lab report
```

Default costs in a proposed spec are **scenario assumptions**: commission `0.001` per actual entry/exit and one-sided entry spread `0.0005`. They are not verified Binance-account fees and do not include an orderbook/market-impact model.

### Human approval workflow

1. Review source code, tests, exact data range, hypothesis, falsification criterion, parameter grid, run budget and initial risk policy.
2. Obtain a passed independent code-review JSON matching the current `code_hash`.
3. In your own interactive terminal, inspect and approve the exact spec:

```bash
uv run trading-lab approve --spec FULL_SPEC_SHA256 --review reports/code-review.json
```

The terminal prints the spec and requires an exact `APPROVE BACKTEST ...` confirmation. Agents must not supply this confirmation. A review JSON alone is **not** human approval.

After approval, the controller can run all permitted configurations without asking for each one:

```bash
uv run trading-lab experiment --spec FULL_SPEC_SHA256
```

To stop further reservations:

```bash
uv run trading-lab revoke --spec FULL_SPEC_SHA256
```

Revocation stops new runs; it does not kill an already running worker. Use Ctrl+C for a foreground run. A consumed reservation is not silently refunded. No command exists for enabling continuous paper trading or live execution.

## Storage / versioning

| Location | Meaning |
|---|---|
| `governance/safety-policy.json` | Initial proposed safety limits; policy hash is bound to approval |
| `governance/specs/<sha256>.json` | Immutable proposed experiment specifications |
| `storage/lab.sqlite` | Canonical append-only audit, approvals, reservations, gaps, lessons and proposals |
| `knowledge/sources/<sha256>.json` | Retrieved source text, URL, retrieval time, hashes |
| `knowledge/cards/<sha256>.json` | Versioned Thai knowledge cards and evidence references |
| `data/<uuid>/` | Exact raw responses, Parquet and manifest; loader reconstructs raw candles and compares them exactly to Parquet. `sha256` is the Parquet hash; `dataset_sha256` binds canonical provenance and all file digests and is the identity used by approvals. |
| `experiments/<run-id>.json` | Immutable simulation artifacts, trades, marks and evaluations; the completion event binds the canonical file SHA256 and reporting verifies it before consumption. |
| `reports/` | Timestamped projections/reviews; not the experiment source of truth |
| `src/trading_lab/` | Reviewed deterministic code, research orchestration and CLI |
| `tests/` | Explicitly synthetic fixtures; never evidence of real trading profitability |

Git versions source/configuration/dependencies/tests. Large datasets, model source snapshots and SQLite are intentionally excluded from Git; their own immutable IDs, source hashes, card versions and audit events provide project-level history. Back up these local directories separately; they are not included merely by committing the repository.

Hermes memory stores user context. Hermes skills store reusable procedures. Neither replaces this project's evidence store or experiment registry.

## Safety and modeling limitations

- **Trusted-code process isolation only:** the worker uses Python `-I`, temporary working/home directories, staged read-only input, a minimal noncredential environment, a timeout and a Python-level network guard. This is **not an OS sandbox** for hostile generated code. Docker was not available during setup. Untrusted generated code remains unsupported/unexecuted; a future OS sandbox needs separate engineering and review.
- SQLite triggers and hashes are tamper-evident controls, **not** protection against a same-user process that can rewrite code/database/approval files. Keep autonomous workers' OS permissions separate before expanding autonomy. This system must not be sold as adversarially secure.
- The `0.10` position fraction is an **entry cash-allocation cap including entry costs**, not a continuously rebalanced 10% marked exposure ceiling. Price appreciation can increase exposure afterward. No leverage or pyramiding is allowed.
- SMA signals use only closed bars and execute at the next open. OHLCV timestamps identify candle opens; signal availability is the candle close, coinciding with the next candle's open boundary in this simplified simulation.
- Bar-level fills omit latency, depth, market impact, partial fills and intrabar drawdown. There are no stops with invented intrabar ordering.
- Open terminal positions are marked at the final close, not fictitiously liquidated. Returns include unrealized marks; actual exit costs are not charged to positions that never exited. Reports must not call these realized profits.
- Baselines include cash, contextual 100%-cash buy-and-hold, and buy-and-hold with equal **initial** allocation. Equal initial allocation is not continuous risk/exposure matching.
- A maximum of three years is fetched per ingestion call. Data must be contiguous and hourly UTC, with complete closed-candle boundary coverage. REST timestamps are parsed as milliseconds; archive CSV parsing is not implemented.
- Walk-forward is fixed rolling evaluation, not model training or optimization. Advanced statistical significance, deflated Sharpe, survivorship analysis across multiple assets and independent exchange-data reconciliation are not implemented. Verdicts remain conservative; no automatic paper eligibility.
- Two roles using the same model are separate contexts, not statistically independent reviewers.

## Next phase — not enabled

Unattended schedules, continuous local paper simulation, OS-isolated generated-code experiments, broader source discovery and a read-only web dashboard require additional work and approval. None is silently activated here.
