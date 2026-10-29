# Trading Research Lab — cross-computer handoff

## Snapshot scope

This backup contains the paper-only research code, the read-only dashboard, audited Batch001 artifacts, and the separate Phase3 research/planning code and first-cycle evidence. It is not permission to run another research cycle or market batch, start paper trading, enable a scheduler, change risk limits or promote a strategy.

- Phase 0–2: existing bounded research implementation and completed Batch 001.
- Phase 2.5: dashboard implemented; backend 52 tests and frontend 14 tests passed; TypeScript/Vite build passed. Browser QA exercised actual trades, chart-coordinate selection, terminal open positions, raw rows, portfolio, research/source dialogs, integrity and a 390px mobile viewport.
- Browser QA found an autosized chart height feedback loop. Explicit host heights and two regression tests fixed it; the subsequent browser run reported no captured runtime errors.
- Initial independent review blocked an omitted B&H reconstruction label. A separate TDD fix and independent re-review passed; review records remain separate under `dashboard/qa/`. The reviewed 31-file dashboard digest is `e7bb409a4787b64bd807933372180f4f18ff3dd0737b2eeba523ce380a16fbe3`. Software acceptance does not grant execution/deployment approval.
- Thai five-trade walkthrough: `dashboard/FIVE-TRADES-TH.md`; QA checks/limits: `dashboard/qa/report.md`. Five saved trades and their 20 indexed raw rows were directly verified without engine execution.

## Phase 3 first cycle — STOPPED awaiting human review

- Integrated software verification: 98 Phase3 tests, 59 dashboard backend tests, 33 frontend tests; build/lint and independent re-review passed.
- Current reviewed32-file code digest: `18c4f2bd9433da642d7032a015ed5e7dd3faa15f40460a5aa615fe433fbda8f6`. The Phase2.5 digest above describes the historical pre-Phase3 dashboard release, not this integrated source snapshot.
- ONE actual foreground cycle completed: `adbc4a5d-5fdc-4212-9b4f-9f1a0845baa6`. Three tool-free Hermes role calls and six completed logical HTTP retrievals. No new market backtest.
- Actual critic verdict **REVISE**. All4 queue proposals are **REJECTED** and unapproved; workflow COMPLETED must not be confused with accepted research or a completed backtest.
- State: 13sources (11pending Crossref metadata candidates +2reviewed seed documents),2REJECTED_DRAFT cards,4hypotheses,4rejected proposals,11lessons,9gaps,76Phase3events. Head `8e98addfd7ca7f9981381123db34da0a262f349b654af9cb96a287a3ec9b4101`.
- Critic exposed generic-plan/hypothesis mismatches in baselines, folds, inference, warm-up and sizing. Volatility draft proposed20% despite the unchanged10% cap; it was rejected, not executed or adopted.
- Read `phase3/reports/cycle001-report-th.md`, the immutable cycle JSON and `phase3/reports/code-review*.json`. New state is `phase3/state/lab.sqlite`, separate from original Batch001 state. Clone/install must preserve both.
- No accepted next experiment, no approved new source/document, no scheduler, and no further research cycle authorized by completion. Stop and show the results before requesting another bounded design-refinement cycle.

## Safety / authorization

`HALTED_AWAITING_HUMAN_RESULTS_REVIEW` remains the recorded batch status. There are 88 audit events, 4 completed experiment configurations and 20 consumed engine evaluations. No additional evaluation is authorized. The dashboard must remain local and read-only. No Binance credentials, real orders, futures, leverage, new executable strategy code or unattended jobs are authorized.

## Evidence and restore

Included: the existing dataset under `data/`, the four saved experiment results under `experiments/`, `storage/lab.sqlite`, knowledge cards/source snapshots, governance records and reports. These paths are normally ignored to prevent accidentally tracking future runtime output; this specific audited snapshot is tracked explicitly. `.gitattributes` disables text conversion on evidence paths so checkout does not change their hashes.

Important identities:

- Approved engine code: `68878a4bf03dd9912e4970ba126858ac7c1fbbc6f995700fb8a735b681cbbec8`
- Dataset: `2689f308c768490b6e6bb29f302f049ef06773b89c8426196de2a4c508014a10`
- Dataset directory: `data/79f63ac8f5a247be94adc04f1fa29bb3/`
- Batch report: `reports/batch001-report-th.md`
- Published artifacts: `reports/batch001-artifact-manifest.json`
- Baseline: `dashboard/qa/baseline-evidence.json` (56 protected files)

Do not regenerate missing evidence by rerunning the batch. Verify the existing evidence first:

```powershell
uv sync --project dashboard/backend --python 3.12 --extra dev --locked
uv run --project dashboard/backend --locked --no-sync python dashboard/verify_readonly.py
```

Expected verifier state: no changed protected files, 88 registry events, 20 engine evaluations, halted status.

Install/build the isolated dashboard frontend and start the local viewer using `dashboard/README.md`. Default URL is `http://127.0.0.1:8765`; a newly cloned project does not automatically start a server. Use Ctrl+C in its foreground terminal to stop it.

## Trade walkthrough entry point

Choose SMA 10/50 and OOS 1. The inspector buttons #1–#5 map to `closed-0001` through `closed-0005`. Expand RAW TRACE for signal and execution candles, the exact raw JSON page, zero-based row index and SHA256. The corresponding persisted result is:

`experiments/ec9ba548545ecd7bc16f0d7997018fdd60dbd344018b608b0d3bf11b16bf72b8.json`

Executions/equity are persisted simulation evidence. Displayed SMA/rationale and benchmark curves are labelled deterministic reconstructions, not new backtests or original model narratives. Missing full stress ledgers/curves and broker lifecycle logs must remain explicitly unavailable.

## Not transferred

No credentials, `.env`, Hermes profile/state/chat history, virtual environments, `node_modules`, frontend build output, caches or running processes. Reinstall dependencies from the separate lockfiles. This repository is not a migration of the Hermes account or conversations. Second-machine operation has not been verified.

## Resume prompt

> Read docs/HANDOFF.md, phase3/README.md and phase3/reports/cycle001-report-th.md. Verify original Batch001 and the separate Phase3 event chain without starting another cycle or market backtest. Phase3 first cycle completed but critic returned REVISE and all four proposals are REJECTED; explain the actual findings and design weaknesses in Thai. Preserve the10% cap, disabled execution/scheduler/credentials and existing approvals. Wait for explicit authorization before any further bounded design-research cycle; do not run experiments, approve sources/proposals, change risk limits or promote strategies automatically.
