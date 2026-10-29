# Phase3 pre-cycle validation

Actual execution checks before any research model cycle:

- Phase2.5 initial revalidation: backend52/frontend14 tests, production build and actual chart/first-trade browser check passed.
- Integrated Phase3 core suite: **46 passed in 7.33s**, warnings treated as errors; Ruff passed.
- Integrated dashboard backend suite: **59 passed in 34.35s**, warnings treated as errors; Ruff passed.
- Integrated frontend suite: **25 passed across7files**, TypeScript/Vite production build passed.
- Original evidence verifier: all56 protected files unchanged;88 audit events,4completed configurations,20engine evaluations,HALTED_AWAITING_HUMAN_RESULTS_REVIEW.
- SafeFetcher live transport preflight: Crossref query and both approved seed documents returned actual bytes using3 bounded requests. No market data or model calls were made in this preflight.
- Actual GET /api/phase3 with no database returned available=false, zero counts and unverified empty integrity. The database did not exist before or after the GET.
- Actual visible browser tab showed all zero-state collection panels, disabled execution/scheduler/credentials, original Batch00120evaluations/88events, and no Phase3 action buttons. Background/hidden tabs deliberately defer polling; browser QA used Page.bringToFront to exercise the visible path.

## Open pre-run review items

Independent code review is pending; no actual research cycle has started.

Parent inspection proved a portability defect: research.py currently pins the raw bytes of dashboard/qa/baseline-evidence.json, but Git normalizes this JSON from CRLF to LF on clone. The indexed JSON and working JSON have equal content but different raw hashes. Fix must pin canonical manifest content and continue verifying all protected file bytes, not edit original evidence.

Parent also requested explicit independent assessment of source-catalog expansion: metadata-only candidate approval does not currently provide a verified-fulltext→human-approval→future-research path. Do not claim unrestricted or full-paper discovery when only metadata is retrieved. Any added path must keep quarantine and human approval before source activation.

## Post-fix validation (before first actual cycle)

- Core suite now **98 passed in16.56s**, Ruff clean; dashboard backend **59 passed**, frontend **33 passed** and production build passed.
- Both blockers have separate TDD fixes: canonical manifest anchor plus gated full-document catalog lifecycle. Card citations bind exact source revisions/hashes. Dashboard uses persisted rankings and readable Thai summaries.
- Parent extracted the actual committed Git LF baseline and all56 protected files into an explicit scratch copy using `git archive HEAD`, then the NEW verifier passed with canonical SHA256 `5be7be8acf2c7bc348b2ac2c722614ffca6a97312f759407ea55023388c65e5c`. Exposure extraction also succeeded. Original files were not rewritten.
- Independent re-review is pending. Actual research state still has zero sources/cards/hypotheses/queue/cycles and no database created by read-only status.

No cycle, new backtest, source approval, proposal approval, schedule or trading execution has been performed. Test fixtures are synthetic software checks, not research findings.
