# Phase 2.5 read-only API contract

Loopback only; no network/exchange calls, model inference, backtests, approvals, scheduler, or source/registry writes. Do not modify root pyproject.toml, uv.lock, src/trading_lab/, governance/, existing reports, DB or datasets. Separate dashboard dependencies. Payloads are persisted evidence plus clearly labelled deterministic display calculations, never newly simulated fills.

Frontend: React + TypeScript + Tailwind, npm lock, local bundled assets, lightweight-charts v5 (use local types/docs), no CDN. Backend: FastAPI single origin on http://127.0.0.1:8765, serving compiled frontend. Dev proxy /api from Vite optional. Only GET/HEAD. Mutating methods return405. No arbitrary filesystem/URL endpoints.

## Endpoints (response shapes)

GET /api/overview
```
{batch_id:"001",spec_id:string,simulation:true,status:"HALTED_AWAITING_HUMAN_RESULTS_REVIEW",integrity:{verified:true,event_count:number,dataset_rows:number,artifact_count:number,engine_evaluations:number,code_hash:string,dataset_hash:string,policy_hash:string,manifest_hash:string},strategies:[{id:"10-50",label:"SMA 10/50",fast:10,slow:50,run_id:string,scopes:[{id:"development"|"oos_1"|"oos_2"|"oos_3",label_th:string,start_utc:string,end_exclusive_utc:string}]}],limitations_th:string[]}
```
GET /api/view?strategy=10-50&scope=oos_1
```
{strategy:{id,label,fast,slow,run_id},scope:{id,label_th,start_utc,end_exclusive_utc},candles:[{time:number,open:number,high:number,low:number,close:number,volume:number,sma_fast:number|null,sma_slow:number|null}],executions:[{time:number,price:number,side:"buy"|"sell",trade_id:string,label:string}],trades:[{id:string,status:"realized"|"terminal_open",entry_time:string,exit_time:string|null,quantity_btc:number,entry_price:number,exit_price:number|null,commission_usdt:number,net_pnl_usdt:number|null,mark_pnl_usdt:number|null}],equity:[{time:number,sma:number,cash:number,buy_hold_10:number,buy_hold_100:number,drawdown_pct:number}],metrics:[{portfolio:"SMA"|"Cash"|"BuyHold_10pct_initial"|"BuyHold_100pct_context",total_return_pct:number,annualized_return_pct:number,max_drawdown_pct:number,sharpe_hourly_rf0:number|null,win_rate_pct:number|null,closed_trades:number,open_positions:number}],critic:{original_verdict:string|null,batch_verdict:string|null,explanation_th:string},costs:{commission_rate:0.001,spread_rate:0.0005,spread_application_th:string},provenance:{artifact_path:string,artifact_sha256:string,dataset_hash:string,raw_source:string},limitations_th:string[]}
```
`candles` include pre-window warmup for honest trailing SMA, flag window via scope timestamps; equity clocks are candle CLOSE (open+1hour), execution markers candle OPEN. All initial cash10000. BH10 equivalent initial allocation10%; BH100 contextual only. SMA explanations are deterministic reconstructions from reviewed SMA rule+raw past closes, not persisted agent narratives. Never imply exposure/time risk matching.

GET /api/trades/{trade_id}?strategy=10-50&scope=oos_1
Trade IDs: closed `closed-0001` etc (1-based stable saved ledger order); open `open-0001` etc. No paths accepted.
```
{trade:{...same list fields,entry_signal_time:string,exit_signal_time:string|null,entry_commission_usdt:number,exit_commission_usdt:number|null,commission_rate:number,spread_rate:number,entry_spread_usdt:number,terminal_mark_time:string|null,terminal_mark_price:number|null},rationale:{kind:"DETERMINISTIC_RECONSTRUCTION_NOT_ORIGINAL_NARRATIVE",entry_th:string,exit_th:string,entry_cross:{previous_fast:number,previous_slow:number,current_fast:number,current_slow:number}|null,exit_cross: same|null,signal_timestamp_semantics_th:string},trace:[{role:"entry_signal"|"entry_execution"|"exit_signal"|"exit_execution"|"terminal_mark",candle_open_time:string,raw_path:string,raw_sha256:string,row_index:number,raw_row:array,ohlcv:{open:number,high:number,low:number,close:number,volume:number}}],provenance:{artifact_path,artifact_sha256,dataset_hash,raw_source},limitations_th:string[]}
```
commission for terminal open is paid entryfee ONLY; net_pnl=null, mark_pnl actual saved mark. Spread amount = size*(adjusted entry - raw open), incorporated in price not additional cash fee. Close position on downcross only; terminal marks not sell executions. Clearly flag missing original per-order broker lifecycle/warnings and full stress evidence.

GET /api/research
```
{cards:[{id:string,version:number,kind:"EVIDENCE_BACKED_CLAIM",topic:string,explanation_th:string,uncertainties_th:string[],claims:array,sources:[{source_id:string,url:string,retrieved_at:string}],verification_scope:string}],questions:[{topic:string,status:"OPEN"|"EVIDENCE_ADDRESSED_NOT_CERTAIN",origin:string}],sources:[{source_id:string,url:string,title:string,retrieved_at:string}],history:[{event_id:number,kind:string,created:string,summary_th:string,evidence_id:string}],agents:[{role:string,learned_th:string[],proposed_th:string[]}],critics:[{configuration:string,original_verdict:string|null,batch_verdict:string,explanation_th:string}],hypotheses:[{configuration:string,hypothesis_th:string,rationale_th:string,status:"PROPOSED_NOT_EXECUTED"}],facts:[{statement_th:string,evidence:string,kind:"VERIFIED_ARTIFACT_METADATA"}],limitations_th:string[]}
```
No universal FACT promotion: cards remain EVIDENCE_BACKED_CLAIM; findings scoped to experiment, hypotheses unexecuted. Source snapshots and cards verify IDs/content against registry; absent or invalid evidence FAIL CLOSED, no synthesized research cards.

GET /api/sources/{source_id}: verified source snapshot `{source_id,url,title,retrieved_at,text,text_sha256}`; GET /api/raw?strategy=..&scope=..&trade=closed-0001&role=entry_execution returns one of the selected trade's verified trace records, not arbitrary file access. Prefer UI inline raw-row reveal; sources navigable in research view. Source text rendered as text, never raw HTML.

Errors: bad selectors400/404; integrity503 `{"detail":{"code":"INTEGRITY_ERROR","message_th":"..."}}`; do not return cached stale "verified" after input mutation. Every data route must revalidate dependency identities/registry/artifacts on access (can memoize verified content only while all file stat fingerprints AND hashes remain validated; initial MVP prefer full revalidation). No write fallback, no Registry constructor. Read sqlite URI `mode=ro`, `PRAGMA query_only=ON`, verify hash chain. No persisted app logs in evidence directories.

## Implementation ownership

Child evidence engineer owns `dashboard/backend/dashboard_api/evidence.py` and tests/test_evidence.py only; expose `EvidenceStore(root).overview()`, `.view(strategy,scope)`, `.trade(strategy,scope,trade_id)`, `.research()`, `.source(source_id)`, `.raw(strategy,scope,trade_id,role)`, IntegrityError(ValueError). Parent owns FastAPI app/start scripts/dependencies/security tests/docs. Frontend child owns dashboard/frontend only. Every feature TDD with synthetic test fixtures explicitly labelled; integration reads real batch without strategy execution. No protected AGENTS.md write.
