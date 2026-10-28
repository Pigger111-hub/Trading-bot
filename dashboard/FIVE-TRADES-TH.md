# คู่มืออ่าน 5 simulated trades จริงจาก Batch 001

คำว่า **จริง** ในคู่มือนี้หมายถึงรายการที่มีอยู่จริงในไฟล์ผลการจำลองที่บันทึกไว้ ไม่ใช่รายการซื้อขายเงินจริง ไม่มีการเรียก Binance ใหม่หรือรัน backtest เพื่อจัดทำคู่มือนี้

## 1. เปิดหน้าที่ใช้ตรวจ

1. เปิด `http://127.0.0.1:8765` หลังเริ่ม server ตาม `dashboard/README.md`
2. เลือกแท็บ **ตลาด & รายการซื้อขาย**
3. เลือก **SMA 10/50** และ **นอกตัวอย่าง 1 / OOS 1**
4. ใน **TRADE INSPECTOR** กด **#1–#5** หรือคลิกรายการจากแถบขวา กราฟจะซูมไปยังช่วงเข้าและออก
5. อ่านราคา จำนวน BTC ค่าธรรมเนียมและ Net P&L แล้วขยาย **RAW TRACE** และ **Artifact provenance** ด้านล่าง

`closed-0001` ถึง `closed-0005` เป็น ID สำหรับการแสดงรายการตามลำดับใน dashboard ไม่ใช่ Binance order IDs ทั้งห้ารายการมีสถานะ `realized` คือปิดสถานะจำลองแล้ว

## 2. ผลที่ตรวจเทียบกับ saved ledger แล้ว

เวลาในตารางทั้งหมดเป็น **UTC** ไม่ใช่เวลาไทย ราคาเป็น USDT ต่อ 1 BTC ตัวเลขแสดงผลปัดเศษ แต่การตรวจใช้ค่าที่บันทึกเต็ม precision

| Trade | ซื้อ UTC | ขาย UTC | ราคาเข้า | ราคาออก | จำนวน BTC | Commission รวม USDT | Net P&L USDT |
|---|---|---|---:|---:|---:|---:|---:|
| #1 | 2025-10-08 23:00 | 2025-10-09 06:00 | 123262.420410 | 122100.920000 | 0.00810466 | 1.988586 | -11.402152 |
| #2 | 2025-10-12 19:00 | 2025-10-14 07:00 | 113935.869465 | 111987.390000 | 0.00875810 | 1.978658 | -19.043637 |
| #3 | 2025-10-18 21:00 | 2025-10-21 08:00 | 107072.009250 | 108086.380000 | 0.00930177 | 2.001354 | +7.434090 |
| #4 | 2025-10-21 18:00 | 2025-10-22 03:00 | 112029.396705 | 108198.850000 | 0.00889679 | 1.959324 | -36.038894 |
| #5 | 2025-10-23 11:00 | 2025-10-28 06:00 | 109493.919600 | 113605.320000 | 0.00906992 | 2.023492 | +35.266580 |

รายการทั้งหมดมาจาก:

`experiments/ec9ba548545ecd7bc16f0d7997018fdd60dbd344018b608b0d3bf11b16bf72b8.json`

ภายในไฟล์: `walk_forward.folds[0].result.trade_ledger[0]` ถึง `[4]`

SHA256 ของไฟล์ผล:

`3fcad33025a088d424482b212ae64eef74f4cf3d4654a0a34382d5ed364a6dda`

## 3. ตามแต่ละรายการกลับไปหา Binance raw rows

ไฟล์ raw ทั้งสองอยู่ใน `data/79f63ac8f5a247be94adc04f1fa29bb3/` แต่ละไฟล์เป็น JSON array; **row index เริ่มที่ 0** ไม่ใช่เลขบรรทัดใน text editor

| Trade | Raw page | Entry signal | Entry execution | Exit signal | Exit execution |
|---|---|---:|---:|---:|---:|
| #1 | `raw-00008.json` | 950 | 951 | 957 | 958 |
| #2 | `raw-00009.json` | 42 | 43 | 78 | 79 |
| #3 | `raw-00009.json` | 188 | 189 | 247 | 248 |
| #4 | `raw-00009.json` | 257 | 258 | 266 | 267 |
| #5 | `raw-00009.json` | 298 | 299 | 413 | 414 |

Hashes ของ raw pages:

- `raw-00008.json`: `fb43d9a5e4da2323d67e9b8cea5185434d622edb07b97dec134ffa25013f101c`
- `raw-00009.json`: `91f1043c48e7b8816d352c10796b49a3ac709bfb0fc3ee28dc603d8ef4343211`

ใน inspector ให้ขยาย entry_signal, entry_execution, exit_signal และ exit_execution ทีละรายการ จะเห็น path, SHA256, row index, OHLCV และ original 12-field kline row โดยไม่ต้องดาวน์โหลดข้อมูลใหม่

สำหรับ raw row: index `[0]` คือเวลาเปิดแท่งแบบ Unix milliseconds, `[1]` Open, `[2]` High, `[3]` Low, `[4]` Close, `[5]` Volume และ `[6]` เวลา close ดั้งเดิมของ Binance ตัวเลขราคาต้นฉบับเป็น string ส่วนใน dashboard แปลงเป็นตัวเลขเพื่อแสดงผล

ตัวอย่างอ่านแถวโดยไม่เขียนไฟล์หรือเรียก engine จาก project root:

```powershell
python -c "import json,pathlib; p=pathlib.Path('data/79f63ac8f5a247be94adc04f1fa29bb3/raw-00008.json'); print(json.loads(p.read_bytes())[951])"
```

ตรวจ hash แบบ read-only:

```powershell
python -c "import hashlib,pathlib; p=pathlib.Path('data/79f63ac8f5a247be94adc04f1fa29bb3/raw-00008.json'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

## 4. ไล่ #1 ให้ครบหนึ่งรอบ

### ก่อนซื้อ: SMA crossover

SMA คือค่าเฉลี่ยราคาปิดย้อนหลังของจำนวนแท่งที่กำหนด สำหรับข้อมูล 1h นี้ SMA 10 ใช้ 10 แท่ง และ SMA 50 ใช้ 50 แท่ง

ที่ entry signal ซึ่งติดป้ายเวลาเปิดแท่ง **2025-10-08 22:00 UTC**:

- แท่งก่อนหน้า: SMA10 = 122986.874 ต่ำกว่า SMA50 = 123038.904
- แท่งสัญญาณ: SMA10 = 123043.804 สูงกว่า SMA50 = 122998.700

จึงอธิบายได้ว่าเส้นเร็วตัดขึ้นเหนือเส้นช้า โดยคำอธิบายนี้เป็น **deterministic reconstruction** จากกฎและข้อมูลที่เก็บไว้ ไม่ใช่ข้อความเหตุผลดั้งเดิมที่ AI เขียนขณะเกิดรายการ

แท่งที่ติดป้าย 22:00 ต้องปิดก่อนจึงทราบสัญญาณ การซื้อจำลองจึงอยู่ที่เปิดแท่งถัดไป **23:00 UTC** ไม่ได้ใช้ราคาปิดในอนาคตมาตัดสินใจล่วงหน้า

### ราคาซื้อและต้นทุน

`raw-00008.json[951][1]` ให้ Open = **123200.82**

กติกาของ Batch 001 สำหรับ long position นี้:

```text
entry_price = raw_entry_open × (1 + 0.0005)
            = 123262.420410 USDT/BTC

entry commission = quantity × entry_price × 0.001
exit commission  = quantity × exit_price × 0.001

net P&L = quantity × (exit_price − entry_price)
          − entry commission − exit commission
```

Spread 0.05% รวมอยู่ในราคาเข้าแล้ว **ห้ามหักเป็นค่าธรรมเนียมเงินสดซ้ำ** Commission 0.1% คิดแยกตอนเข้าและตอนขายจริงของ simulation

### ขายและสรุป

Exit signal ติดป้าย **2025-10-09 05:00 UTC** และขายที่เปิดแท่ง **06:00 UTC** ใน `raw-00008.json[958]` ซึ่ง Open = **122100.92**

ด้วยจำนวน **0.00810466 BTC** commission รวม **1.988586 USDT** และ net P&L **-11.402152 USDT** ตรงกับ saved ledger ไม่ใช่ผลจากการรันกลยุทธ์ใหม่

ใช้ขั้นตอนเดียวกันกับ #2–#5 และแถวในตารางด้านบน: ตรวจสัญญาณ, เปิดแท่งถัดไป, adjusted entry, exit, จำนวน, commission และ net P&L ให้ครบ

## 5. อ่าน Portfolio และ Research อย่างไร

- **Equity** คือมูลค่ารวมของพอร์ตจำลองที่แต่ละเวลา รวมการตีราคาสถานะที่ยังเปิด ไม่ใช่ยอดเงินสดอย่างเดียว เส้น SMA ใช้ equity ที่บันทึกจาก Batch 001
- เส้น **BH10/BH100** เป็นการสร้างย้อนหลังจาก baseline cash/quantity ที่บันทึกและ archived closes ไม่ใช่ complete benchmark curve ที่บันทึกดั้งเดิม และไม่ใช่การรัน backtest ใหม่
- **Drawdown** แสดงการลดลงจากยอดสูงสุดก่อนหน้า ไม่ใช่ผลตอบแทนรวม
- **Sharpe / RF 0** เป็น metric ที่ระบบคำนวณจาก hourly returns ภายใต้ risk-free rate 0 ไม่ใช่คำรับรองผลในอนาคต
- **Win rate** ใช้เฉพาะ closed trades; terminal open positions ไม่มีราคาขาย/exit fee ที่ยังไม่เกิด และไม่ถูกนับเป็นชนะหรือแพ้
- แต่ละ OOS fold เริ่มพอร์ต 10000 USDT แยกกัน ห้ามนำกราฟมาอ้างเป็นบัญชีต่อเนื่องสองปี
- BH10 เทียบ initial capital และ allocation เริ่มต้น ส่วน BH100 เป็นบริบทตลาด ไม่ใช่คู่เทียบความเสี่ยงเท่ากัน
- Knowledge Cards เป็น `EVIDENCE_BACKED_CLAIM`; findings จำกัดอยู่ในชุดข้อมูล/ช่วง/การตั้งค่าที่ทดลอง และ hypotheses ยังไม่ใช่ข้อเท็จจริงหรือการอนุมัติทดลองต่อ

## 6. ขอบเขตการตรวจและข้อจำกัด

ตรวจ actual API กับ saved ledger ครบห้ารายการ และตรวจ hash + indexed raw row ครบ **20 trace rows** รวมทั้งสูตร adjusted entry, exit, commission และ net P&L โดยไม่เรียก engine

ไม่มีการเติมข้อมูล stress ledger/curve ที่ไม่ถูกบันทึก ไม่มี complete broker lifecycle/warnings log ให้ตรวจ และไม่ตีความ deterministic signal explanations เป็น original AI narrative

หาก hash/provenance ไม่ผ่าน ให้หยุดอ่านผลและตรวจหลักฐาน ห้ามสร้างข้อมูลทดแทนหรือ rerun Batch 001 ทั้งนี้ระบบยังหยุดรอ human results review; ไม่มีการอนุมัติ next batch, scheduler, continuous paper trading หรือ real trading
