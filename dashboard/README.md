# Phase 2.5 — Read-only Backtest Explainability Dashboard

หน้าจอนี้ใช้ **Batch 001 ที่รันและปิด approval แล้ว** เท่านั้น ไม่รัน backtest, research/model inference, paper trading, scheduler หรือ live trading ไม่มี exchange credentials และไม่มีปุ่มส่งคำสั่งซื้อขาย/อนุมัติ/เลื่อนสถานะกลยุทธ์

## Architecture / isolation

- `backend/`: FastAPI + Uvicorn ใน virtual environment และ `uv.lock` **แยก** จาก approved research engine
- `frontend/`: React + TypeScript + Tailwind + local bundled chart library; ใช้ข้อมูล GET `/api` แบบ same-origin ไม่โหลดราคา/ฟอนต์/CDN ภายนอก
- `API-CONTRACT.md`: payloads และนิยามที่มาของข้อมูล
- `qa/baseline-evidence.json`: SHA256 ก่อนพัฒนา สำหรับตรวจว่าต้นฉบับ research artifacts/DB/data/policy/code ไม่เปลี่ยน
- ไม่แก้ `src/trading_lab`, root `pyproject.toml`/`uv.lock`, safety policy, approval, experiment results หรือ Batch 001 reports
- Backend อ่าน SQLite ด้วย `mode=ro`, `query_only`; ตรวจ hash chain และ published manifest ก่อนอ่าน artifacts และปฏิเสธข้อมูลผิดด้วย HTTP 503 ไม่แสดงค่าปลอม/ข้อมูลเก่าว่า verified
- Bind เฉพาะ `127.0.0.1`; ไม่มี CORS เปิดกว้าง, foreign origins ถูกปฏิเสธ และ methods ที่เขียนข้อมูลคืน 405
- Read-only เป็นขอบเขตการทำงานของ app ไม่ใช่ OS sandbox ป้องกันโปรแกรมที่มีสิทธิ์ Windows user เดียวกันแก้ไฟล์

## Setup — Windows PowerShell หรือ Command Prompt

เริ่มที่โฟลเดอร์โครงการ:

```powershell
cd "C:\Users\STANDARD_DOH\Desktop\Herme Agent\Bot-Trading"
uv sync --project dashboard/backend --python 3.12 --extra dev --locked
cd dashboard/frontend
npm.cmd ci
npm.cmd run build
cd ../..
```

ใช้ `npm.cmd` แทน `npm.ps1` หาก PowerShell execution policy ไม่อนุญาตสคริปต์ npm ไม่ต้องลด execution policy ของเครื่อง

ใน Git Bash หาก `node` alias แจ้ง `stdin is not a tty` ให้เรียก native binaries แทน:

```bash
"/c/Program Files/nodejs/node.exe" "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js" ci
"/c/Program Files/nodejs/node.exe" "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js" run build
```

สองคำสั่งนี้รันจาก `dashboard/frontend` และไม่เปลี่ยน dependencies ของ research engine

## Start

ดับเบิลคลิก `dashboard/start-dashboard.cmd` หรือรันจาก project root:

```powershell
uv run --project dashboard/backend --locked --no-sync uvicorn dashboard_api.app:app --host 127.0.0.1 --port 8765 --no-access-log
```

เปิด **http://127.0.0.1:8765**

หาก port ถูกใช้อยู่ อย่าฆ่า process อื่นโดยเดา PID ตรวจว่าเป็น dashboard เดิมหรือเปลี่ยนการตั้งค่าผ่านการตรวจสอบก่อน อย่าเปิด `--host 0.0.0.0` หรือ expose dashboard ไปอินเทอร์เน็ต

## Stop

ในหน้าต่าง terminal ที่รัน server ให้กด **Ctrl+C** แล้วรอให้ Uvicorn รายงาน shutdown การปิด server ไม่เกี่ยวกับ engine/registry และไม่คืนหรือเพิ่ม evaluation budget

หาก Hermes เป็นผู้เปิด background server ให้ขอ `หยุด dashboard Phase 2.5` เพื่อหยุด tracked server process โดยไม่กระทบโปรแกรมอื่น

## Tests

```powershell
uv run --project dashboard/backend --extra dev --locked pytest dashboard/backend/tests -q -W error
uv run --project dashboard/backend --extra dev --locked ruff check dashboard/backend
cd dashboard/frontend
npm.cmd test -- --run
npm.cmd run build
```

Tests ใช้ synthetic fixtures ที่ระบุชัดสำหรับกรณีเสียหาย และอ่าน actual Batch 001 สำหรับ integration ไม่เรียก research CLI หรือ strategy execution และไม่ใช้ budget 20 evaluations เพิ่ม

## วิธีอ่านกราฟโดยไม่เข้าใจผิด

1. เลือก strategy และ development/OOS fold แยกกัน ทุก OOS fold เริ่มบัญชีใหม่ 10,000 USDT ไม่ใช่พอร์ตต่อเนื่องสองปี
2. Candlestick timestamp คือ **เวลาเปิดแท่ง** ส่วน equity points คือ **เวลาปิดแท่ง** = เวลาเปิด + 1 ชั่วโมง
3. SMA ใช้ trailing closes ที่เกิดขึ้นแล้ว รวม warmup จากอดีต ไม่ใช่ centered average/backfill และเป็นเพียง display calculation ไม่ใช่ strategy rerun
4. Buy/Sell markers มาจากรายการ execution ที่บันทึกจริงใน simulation ไม่ใช่แค่สัญญาณ crossover
5. เหตุผล entry/exit เป็น **deterministic reconstruction** จาก reviewed SMA rule, saved signal timestamp และ raw closes ไม่ใช่ข้อความวิเคราะห์ที่ agent บันทึกในขณะเทรด
6. Spread อยู่ใน adjusted entry price ไม่หักเป็น cash fee อีกรอบ Commission แยก entry/actual exit ครั้งเดียว
7. Terminal open position ไม่มี sell/exit fee ที่ยังไม่เกิด แสดง mark-to-market และไม่รวมเป็น win/loss ของ closed trades
8. Buy-and-Hold 10% เทียบ initial capital/allocation เดียวกัน ส่วน B&H 100% เป็น contextual benchmark เท่านั้น ไม่ใช่ risk-matched comparator
9. Sharpe ของ Cash และ Win Rate ที่ไม่มี closed trades เป็น N/A ไม่ใช่ศูนย์
10. Stress มีเพียง development aggregate metrics ไม่มี saved full ledger/curve หรือ doubled-cost OOS จึงไม่เติมข้อมูลที่หายและไม่สร้าง fill เพิ่ม

## Provenance drilldown

รายละเอียด trade แสดง:

- immutable experiment artifact path + SHA256 และ original saved ledger fields
- Binance raw page path + SHA256 + **row index แบบเริ่มที่ 0**
- original 12-field REST kline row และ normalized OHLCV ของ signal/execution/terminal candle
- dataset provenance identity และ source endpoint เดิม (ไม่เรียก API ใหม่)

REST raw row: `[open_time_ms, open, high, low, close, volume, close_time_ms, quote_volume, trade_count, taker_buy_base, taker_buy_quote, ignore]` ตัวเลขราคาต้นฉบับอาจเป็น string ให้แยกจาก display rounding

ราคา entry จำลองเท่ากับ raw next-open × `(1 + 0.0005)` จึงไม่เท่าราคา Open ดิบพอดี ส่วนราคา exit คือ next-open ดิบ Commission ของ closed trade = quantity × `(entry_price + exit_price)` × `0.001` และ net P&L = quantity × `(exit_price − entry_price)` − commission

หาก evidence หาย/ไม่ตรง hash ให้หยุดอ่านผลและตรวจไฟล์ต้นฉบับ ห้าม rerun batch เพื่อสร้างสิ่งที่หายมาทดแทน

## Knowledge / research statuses

- `VERIFIED_ARTIFACT_METADATA`: ยืนยันว่าเป็น metadata ใน artifacts ที่ตรวจสอบผ่าน ไม่ใช่ข้อเท็จจริงสากลเรื่องการลงทุน
- `EVIDENCE_BACKED_CLAIM`: Knowledge Card ที่มีแหล่งรองรับ ยังไม่ถูกเลื่อนเป็น universal FACT
- `FINDING`: ผลเฉพาะ dataset/configuration/window ของ simulation
- `HYPOTHESIS`: ข้อเสนอที่ยังไม่ถูกทดลอง/อนุมัติ
- Critic verdict เดิมและ batch-level correction เก็บแยก ไม่แก้ประวัติให้ดูดีขึ้น ไม่มี winner selection หรือ strategy promotion

## Reference image

ไม่พบไฟล์ screenshot แนบในคำขอ Phase 2.5 นี้ จึงใช้ dark professional trading-terminal layout ตามคำอธิบาย ไม่อ้างว่าเป็นการจำลอง screenshot ที่ไม่ได้รับ
