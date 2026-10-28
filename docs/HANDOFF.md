# Trading Research Lab — cross-computer handoff

## Snapshot scope

This backup contains the paper-only research code, the Phase 2.5 read-only dashboard, and the existing audited Batch 001 artifacts. It is not permission to execute another batch, start paper trading, enable a scheduler, or promote a strategy.

- Phase 0–2: existing bounded research implementation and completed Batch 001.
- Phase 2.5: dashboard implemented; backend 52 tests and frontend 14 tests passed; TypeScript/Vite build passed. Browser QA exercised actual trades, chart-coordinate selection, terminal open positions, raw rows, portfolio, research/source dialogs, integrity and a 390px mobile viewport.
- Browser QA found an autosized chart height feedback loop. Explicit host heights and two regression tests fixed it; the subsequent browser run reported no captured runtime errors.
- Initial independent review blocked an omitted B&H reconstruction label. A separate TDD fix and independent re-review passed; review records remain separate under `dashboard/qa/`. The reviewed 31-file dashboard digest is `e7bb409a4787b64bd807933372180f4f18ff3dd0737b2eeba523ce380a16fbe3`. Software acceptance does not grant execution/deployment approval.
- Thai five-trade walkthrough: `dashboard/FIVE-TRADES-TH.md`; QA checks/limits: `dashboard/qa/report.md`. Five saved trades and their 20 indexed raw rows were directly verified without engine execution.

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

> Read docs/HANDOFF.md, dashboard/README.md and dashboard/FIVE-TRADES-TH.md. Verify original Batch 001 evidence without running the research engine or consuming evaluations. Phase 2.5 software review passed; help the user inspect the existing results and their limitations in Thai. Preserve paper-only, read-only and halted approval boundaries. Do not begin another experiment, scheduler, continuous paper trading or strategy promotion without separate explicit approval.
