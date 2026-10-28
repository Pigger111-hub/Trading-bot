# Phase 2.5 QA record

## Scope

Local read-only dashboard over existing Batch 001 evidence. No engine/backtest, market fetch, model call, scheduler, credentials, approval update or strategy promotion was executed by dashboard verification.

## Automated checks

- Backend/API/evidence/read-only suite: **52 passed**, warnings treated as errors.
- Backend Ruff: passed.
- Frontend final suite after evidence-label correction: **14 passed across 6 files** (parent rerun).
- TypeScript and Vite production build: passed in the fix task; corrected paragraph was subsequently observed in the served production UI.
- Existing evidence verifier: **56 protected files unchanged**, **88 audit events**, **4 configurations**, **20 evaluations**, `HALTED_AWAITING_HUMAN_RESULTS_REVIEW`.
- Five actual SMA10/50 OOS1 trades: API projections equal saved ledger for timestamps, prices, quantity, commission and net P&L. All **20 raw trace rows** equal their actual archived JSON page/index with matching SHA256. Entry spread, entry/exit fees and net P&L formulas matched without running the engine.

## Browser checks

- Candlesticks, both SMA overlays and saved execution markers rendered.
- Inspector buttons #1–#5 loaded the corresponding actual closed trades.
- An actual chart-coordinate click changed inspector selection from `closed-0003` to `closed-0004`.
- Portfolio equity/drawdown rendered with Cash/BH10 and optional BH100 context.
- Corrected explicit Thai paragraph distinguishes persisted SMA equity from reconstructed BH10/BH100 curves and states no new backtest was run.
- Strategy/fold switching changed actual metrics; checked SMA20/100 OOS3.
- SMA10/50 OOS3 showed **41 closed / 1 open**. `open-0001` had no exit price, sell execution, realized net P&L or exit fee; trace contained entry signal, entry execution and terminal mark only.
- Research cards, hypotheses, open questions, Agent notebook, critic/history and source list rendered.
- Source snapshot dialog opened with archived plain text, retrieval time and SHA256, then closed. External source link used `noopener noreferrer`.
- Integrity panel showed approved identities, halted status and existing budget counts.
- Mobile viewport **390px**: document scroll width **390px** on integrity, portfolio and market views. Chart host remained **390px** high. Captured runtime error/unhandled-rejection lists were empty during final interactions.
- Captured app fetches during the instrumented navigation were GET requests to local API routes. This observation supplements, not replaces, the enforced read-only API boundary and tests.

## Defects found and corrected

1. Autosized chart host expanded continuously and emitted ResizeObserver errors. Browser measurements showed growing heights; a DOM-only fixed-height probe stopped it. Added explicit host heights 390/330/160 and regression tests, observed RED then GREEN. Subsequent browser interactions had stable heights and no captured errors.
2. Independent review blocked missing portfolio evidence-type disclosure for reconstructed B&H curves. A separate fix agent added the Thai disclosure and a rendering regression, observed RED then GREEN. No numerical calculation or chart behavior changed.

## Start / stop

The original tracked dashboard server was stopped through its exact process handle; a socket probe confirmed port 8765 closed. Then `cmd.exe /d /c dashboard\\start-dashboard.cmd` was launched from project root and the resulting server was exercised through the browser/API above. Current tracked process: `proc_40c412186056` (a temporary session handle, not a durable startup configuration).

For ordinary Windows use, run `dashboard/start-dashboard.cmd` in a foreground terminal and stop with Ctrl+C, as Uvicorn instructs. The Ctrl+C keyboard sequence itself was not automated in this QA run; the verified stop used the tracked process manager. No scheduler was installed.

## Review / delivery status

Initial independent review failed solely on item 2 above, with no security concerns. A separate fix and independent re-review resolved that blocker. Final re-review passed with explicitly empty security/logic issue lists; parent recomputation matched the reviewed 31-file source digest. See `dashboard/qa/independent-review-initial.json` and `dashboard/qa/independent-review.json`. This is software review acceptance only, not permission for another experiment or deployment.

Final candidate dashboard digest (31 source/config/lock files; excludes docs, QA, builds and dependencies):

`e7bb409a4787b64bd807933372180f4f18ff3dd0737b2eeba523ce380a16fbe3`

Known limits: no original full broker lifecycle/warnings log, no full saved stress ledger/curve or doubled-cost OOS results, no second-machine runtime validation. Do not fill these gaps with fabricated data or another batch run.
