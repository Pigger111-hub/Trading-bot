# Evidence Terminal frontend

Ownership: **dashboard/frontend/** only. No source engine, datasets, registry or backend files changed. No execution, backtest, inference, scheduler or POST calls.

## Commands

```sh
npm ci --no-audit --no-fund
npm test
npm run build
```

On this Windows machine the shell `node` alias is unsuitable. Verified equivalent commands:

```sh
"C:/Program Files/nodejs/node.exe" node_modules/vitest/vitest.mjs run
"C:/Program Files/nodejs/node.exe" node_modules/typescript/bin/tsc -b
"C:/Program Files/nodejs/node.exe" node_modules/vite/bin/vite.js build
```

Production output: `dist/`; parent FastAPI serves it at the same origin as `/api`.
Optional Vite dev proxy targets `http://127.0.0.1:8765`; no server started by frontend work.

## Behavior

- Defaults to SMA 10/50 + OOS1 when available. First-five quick selection uses actual returned trades, never a hardcoded ledger.
- Candles/SMA/saved execution markers, clickable execution times, selection zoom, actual trade/rationale/trace inspection.
- Portfolio saved curves: SMA, Cash, initial-allocation BH10; optional BH100 context. Drawdown always visible. No fabricated values or production fallback fixtures.
- All transport is same-origin uncached GET. Integrity503 from any read clears every visible payload and the VERIFIED badge. Retry begins a fresh overview read. Focus and 30-second visible-tab checks revalidate overview.
- Research source snapshots are normal React text, not HTML. External links allow explicit HTTP(S) only and use `noopener noreferrer`.
- Labels distinguish candle OPEN signal timestamps, decision available at close (+1h), next-open executions, and equity CLOSE timestamps. Rationale explicitly marked reconstructed, not original agent narrative.
- Thai system fonts; no remote assets, font requests or CDN. 375/1440 responsive layouts implemented in CSS. Parent performs real-data browser QA.
- Unit fixtures are explicitly synthetic and confined to `*.test.ts(x)`.

## Attribution

Installed `lightweight-charts` version: 5.2.1 (package-lock.json pins resolved dependencies).
Read installed package README license section and official tagged NOTICE:
`https://raw.githubusercontent.com/tradingview/lightweight-charts/v5.2.1/NOTICE`.
The official notice and installed Apache-2.0 license are copied into public/ and build output.
Visible footer preserves the notice and TradingView link. Charts retain `layout.attributionLogo: true`.

## Integration boundary

API interfaces are in src/types.ts and follow ../API-CONTRACT.md. Only GET /overview, /view, /trades/{id}, /research and /sources/{id} are used; inline trade trace already provides verified raw rows, so no arbitrary path access is needed.

Live API verification attempt returned connection refused on 127.0.0.1:8765 while parent backend was not yet running. Typecheck, unit tests and production build pass; real API/browser QA remains parent-owned.
