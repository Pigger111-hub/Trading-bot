# รายงาน SMA Crossover — Batch 001

**BACKTEST / SIMULATED เท่านั้น — ไม่ใช่ verified real profit**

## 1. ขอบเขตและสถานะ

- รันครบ 4 configurations และ 20 engine evaluations; trial ล้มเหลว 0 รายการ ไม่มีการรันเพิ่มเติมหลัง batch นี้
- ใช้ reviewed code และ dependencies เดิม; ไม่แก้ strategy, runner, safety policy หรือ dependency versions
- ไม่มี Binance credentials, live trading, futures, leverage, generated executable strategy, paper loop หรือ scheduler
- อนุมัติจากข้อความผู้ใช้ใน Hermes desktop และบันทึกเป็น approval event ก่อนจอง run budget
- ข้อมูล BTCUSDT 1h จำนวน 17,520 แท่ง ช่วง [2024-10-01 00:00 UTC, 2026-10-01 00:00 UTC)
- เงินเริ่มต้นจำลอง 10,000 USDT ต่อบัญชีทดสอบ; จำกัด entry allocation 10% รวมต้นทุนเข้า ไม่ใช่ marked exposure cap ที่ rebalance ต่อเนื่อง

Batch spec: `f95c353c980937d548363e0b8bfeca737b7b98bc8d394b144ad6c2fba133263f`
Reviewed code: `68878a4bf03dd9912e4970ba126858ac7c1fbbc6f995700fb8a735b681cbbec8`
Dataset provenance identity: `2689f308c768490b6e6bb29f302f049ef06773b89c8426196de2a4c508014a10`
Strategy module SHA256: `3e1d162ddcc51e5eb1fd39262cd5b62f766eab202d91fcfba8d88067c98b8a5b`
Approval event: `15dc7c0cb0c3c1c46780e85338f695962e9acfddc1fe71192a260b2d759ee12e`

## 2. ผลสรุปที่ไม่ควรตีความเกินหลักฐาน

- ทุก configuration ให้ผลติดลบใน OOS สองช่วงแรก และเป็นบวกใน final holdout เพียงช่วงเดียว
- ทุก configuration ให้ final-holdout return ต่ำกว่า Buy-and-Hold ที่จัดสรรเริ่มต้นเท่ากัน 10% แต่มี drawdown ต่ำกว่าในช่วงนั้น
- SMA 10/100, 20/50 และ 20/100 มี drawdown ต่ำกว่า B&H 10% ครบทั้งสาม OOS folds ส่วน 10/50 ได้สองในสาม folds
- หลักฐานจึงรองรับเชิงพรรณนาว่าบางกติกาอาจลด drawdown โดยแลกกับการอยู่นอกตลาดและผลตอบแทนที่ลดลง ไม่ใช่หลักฐานยืนยัน alpha หรือกำไรในอนาคต
- SMA 20/100 ดูดีกว่าใน development แต่ผลดังกล่าวไม่ทำให้เป็นผู้ชนะหรือได้รับอนุมัติเลื่อนขั้น; ห้ามใช้ final holdout เลือก winner แล้วอ้างว่ายังเป็นข้อมูลไม่เคยเห็น

## 3. การแบ่งช่วงและความหมายของ Total Return

แต่ละ OOS fold เริ่มบัญชีใหม่ 10,000 USDT และเริ่ม flat หลัง warmup ด้วยอดีตเท่านั้น ไม่ carry position/PnL ข้าม fold จึงไม่ต่อผลให้กลายเป็นกำไรพอร์ตต่อเนื่องสองปี และไม่รายงาน pooled Sharpe ที่ทำให้เข้าใจผิด
Development เป็นข้อมูลครึ่งแรก ไม่ใช่ OOS; ไม่มี optimization หรือการ fit model ในขั้น walk-forward นี้ เป็น rolling evaluation ของกติกาคงที่

| Scope | Configuration | เริ่มประเมิน UTC | สิ้นสุดแบบ exclusive UTC |
|---|---|---|---|
| development | 10/50 | 2024-10-03T02:00:00+00:00 | 2025-10-01T00:00:00+00:00 |
| oos_1 | 10/50 | 2025-10-01T00:00:00+00:00 | 2026-01-30T16:00:00+00:00 |
| oos_2 | 10/50 | 2026-01-30T16:00:00+00:00 | 2026-06-01T08:00:00+00:00 |
| oos_3 | 10/50 | 2026-06-01T08:00:00+00:00 | 2026-10-01T00:00:00+00:00 |
| development | 10/100 | 2024-10-05T04:00:00+00:00 | 2025-10-01T00:00:00+00:00 |
| oos_1 | 10/100 | 2025-10-01T00:00:00+00:00 | 2026-01-30T16:00:00+00:00 |
| oos_2 | 10/100 | 2026-01-30T16:00:00+00:00 | 2026-06-01T08:00:00+00:00 |
| oos_3 | 10/100 | 2026-06-01T08:00:00+00:00 | 2026-10-01T00:00:00+00:00 |
| development | 20/50 | 2024-10-03T02:00:00+00:00 | 2025-10-01T00:00:00+00:00 |
| oos_1 | 20/50 | 2025-10-01T00:00:00+00:00 | 2026-01-30T16:00:00+00:00 |
| oos_2 | 20/50 | 2026-01-30T16:00:00+00:00 | 2026-06-01T08:00:00+00:00 |
| oos_3 | 20/50 | 2026-06-01T08:00:00+00:00 | 2026-10-01T00:00:00+00:00 |
| development | 20/100 | 2024-10-05T04:00:00+00:00 | 2025-10-01T00:00:00+00:00 |
| oos_1 | 20/100 | 2025-10-01T00:00:00+00:00 | 2026-01-30T16:00:00+00:00 |
| oos_2 | 20/100 | 2026-01-30T16:00:00+00:00 | 2026-06-01T08:00:00+00:00 |
| oos_3 | 20/100 | 2026-06-01T08:00:00+00:00 | 2026-10-01T00:00:00+00:00 |

Development ของ slow=50 กับ slow=100 เริ่มต่างกันเพราะ warmup 50/100 ชั่วโมง จึงต้องใช้ baseline ของ configuration และช่วงเดียวกัน ไม่ถือว่าทั้งสี่แถวมี start date เหมือนกัน

## 4. นิยาม metrics

- Total Return = terminal marked equity / initial cash − 1 ภายใน window นั้น รวม unrealized marks ที่ยังเปิดอยู่
- Annualized Return = (terminal equity / 10,000)^(8,760 / จำนวนชั่วโมงประเมิน) − 1 ใช้ปี 365 วัน; เป็นการสเกลตามสูตร ไม่ใช่ forecast โดยเฉพาะ OOS ประมาณสี่เดือน
- Sharpe = ค่าเฉลี่ย simple hourly equity returns / sample standard deviation (ddof=1) × sqrt(8,760), risk-free=0 คำนวณใหม่จาก saved equity curve ไม่ใช่ยกค่า built-in ที่นิยามต่างกัน
- Cash มี zero variance จึง Sharpe = N/A ไม่ใช่ 0; ไม่สมมติดอกเบี้ยเงินสด
- Maximum Drawdown แสดงเป็นค่าติดลบจาก running equity peak รวม initial cash; ค่าใกล้ศูนย์แปลว่าขาดทุนจาก peak น้อยกว่า วัดเฉพาะ hourly close ไม่ใช่ intrabar
- Win Rate = closed round trips ที่ net PnL > 0 / closed round trips ทั้งหมด หลัง commission; open terminal marks ไม่ถูกนับเป็น win/loss
- B&H มีหนึ่ง entry และยังถืออยู่ตอนจบ จึง closed trades = 0, open = 1, Win Rate = N/A; ไม่ควรตีความ N/A ว่าแพ้หรือชนะ
- B&H 10% ใช้เงินจัดสรรเริ่มต้นเท่ากันและเหลือ cash 90%; B&H 100% เป็นบริบทตลาด ไม่ใช่ comparator ที่ risk matched กับ SMA 10%
- Baseline curves คำนวณเชิงบัญชีจาก size/cash/entry time ที่บันทึกไว้และราคาปิดเดิม ตรวจ Total Return/MDD ตรง saved metrics ภายใน tolerance 1e-8 percentage points ไม่ได้รันกลยุทธ์เพิ่ม

## 5. ตารางผลครบทุก configuration และ baseline

Return, Annualized, MDD และ Win Rate เป็น %; Trades คือ closed round trips; Open คือสถานะที่ยังไม่ขายปลายงวด

### 5.1 Development — ไม่ใช่ OOS

| Config | Portfolio | Total Return % | Annualized % | MDD % | Sharpe | Win Rate % | Trades | Open |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 10/50 | SMA | 0.2306 | 0.2319 | -4.6894 | 0.0856 | 31.62 | 117 | 1 |
| 10/50 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 10/50 | Buy-and-Hold 10% initial | 8.6120 | 8.6635 | -5.0787 | 1.2834 | N/A | 0 | 1 |
| 10/50 | Buy-and-Hold 100% context | 86.1203 | 86.7852 | -30.9361 | 1.5967 | N/A | 0 | 1 |
| 10/100 | SMA | -0.9357 | -0.9465 | -5.7245 | -0.2586 | 25.00 | 84 | 1 |
| 10/100 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 10/100 | Buy-and-Hold 10% initial | 8.3822 | 8.4830 | -5.0262 | 1.2691 | N/A | 0 | 1 |
| 10/100 | Buy-and-Hold 100% context | 83.8225 | 85.1193 | -30.9361 | 1.5768 | N/A | 0 | 1 |
| 20/50 | SMA | -2.1460 | -2.1582 | -6.1027 | -0.6313 | 32.69 | 104 | 1 |
| 20/50 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 20/50 | Buy-and-Hold 10% initial | 8.6120 | 8.6635 | -5.0787 | 1.2834 | N/A | 0 | 1 |
| 20/50 | Buy-and-Hold 100% context | 86.1203 | 86.7852 | -30.9361 | 1.5967 | N/A | 0 | 1 |
| 20/100 | SMA | 3.1483 | 3.1852 | -3.6018 | 0.9058 | 32.76 | 58 | 1 |
| 20/100 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 20/100 | Buy-and-Hold 10% initial | 8.3822 | 8.4830 | -5.0262 | 1.2691 | N/A | 0 | 1 |
| 20/100 | Buy-and-Hold 100% context | 83.8225 | 85.1193 | -30.9361 | 1.5768 | N/A | 0 | 1 |

### 5.2 OOS fold 1

| Config | Portfolio | Total Return % | Annualized % | MDD % | Sharpe | Win Rate % | Trades | Open |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 10/50 | SMA | -3.7723 | -10.8953 | -4.3931 | -4.3762 | 21.43 | 42 | 0 |
| 10/50 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 10/50 | Buy-and-Hold 10% initial | -2.7556 | -8.0411 | -3.7939 | -2.1892 | N/A | 0 | 1 |
| 10/50 | Buy-and-Hold 100% context | -27.5559 | -61.9803 | -34.7956 | -1.9822 | N/A | 0 | 1 |
| 10/100 | SMA | -2.5580 | -7.4793 | -3.1758 | -3.0604 | 13.64 | 22 | 0 |
| 10/100 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 10/100 | Buy-and-Hold 10% initial | -2.7556 | -8.0411 | -3.7939 | -2.1892 | N/A | 0 | 1 |
| 10/100 | Buy-and-Hold 100% context | -27.5559 | -61.9803 | -34.7956 | -1.9822 | N/A | 0 | 1 |
| 20/50 | SMA | -1.8159 | -5.3495 | -2.3243 | -2.1645 | 25.00 | 28 | 0 |
| 20/50 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 20/50 | Buy-and-Hold 10% initial | -2.7556 | -8.0411 | -3.7939 | -2.1892 | N/A | 0 | 1 |
| 20/50 | Buy-and-Hold 100% context | -27.5559 | -61.9803 | -34.7956 | -1.9822 | N/A | 0 | 1 |
| 20/100 | SMA | -2.0603 | -6.0543 | -2.2693 | -2.4267 | 15.00 | 20 | 0 |
| 20/100 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 20/100 | Buy-and-Hold 10% initial | -2.7556 | -8.0411 | -3.7939 | -2.1892 | N/A | 0 | 1 |
| 20/100 | Buy-and-Hold 100% context | -27.5559 | -61.9803 | -34.7956 | -1.9822 | N/A | 0 | 1 |

### 5.3 OOS fold 2

| Config | Portfolio | Total Return % | Annualized % | MDD % | Sharpe | Win Rate % | Trades | Open |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 10/50 | SMA | -1.6287 | -4.8071 | -1.6899 | -1.5640 | 29.73 | 37 | 0 |
| 10/50 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 10/50 | Buy-and-Hold 10% initial | -1.2556 | -3.7197 | -2.5636 | -0.9113 | N/A | 0 | 1 |
| 10/50 | Buy-and-Hold 100% context | -12.5559 | -33.1361 | -25.3622 | -0.6220 | N/A | 0 | 1 |
| 10/100 | SMA | -1.2713 | -3.7657 | -1.7943 | -1.2494 | 17.24 | 29 | 0 |
| 10/100 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 10/100 | Buy-and-Hold 10% initial | -1.2556 | -3.7197 | -2.5636 | -0.9113 | N/A | 0 | 1 |
| 10/100 | Buy-and-Hold 100% context | -12.5559 | -33.1361 | -25.3622 | -0.6220 | N/A | 0 | 1 |
| 20/50 | SMA | -0.6093 | -1.8168 | -1.3951 | -0.5684 | 37.93 | 29 | 0 |
| 20/50 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 20/50 | Buy-and-Hold 10% initial | -1.2556 | -3.7197 | -2.5636 | -0.9113 | N/A | 0 | 1 |
| 20/50 | Buy-and-Hold 100% context | -12.5559 | -33.1361 | -25.3622 | -0.6220 | N/A | 0 | 1 |
| 20/100 | SMA | -1.9313 | -5.6827 | -2.0241 | -1.8729 | 27.78 | 18 | 1 |
| 20/100 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 20/100 | Buy-and-Hold 10% initial | -1.2556 | -3.7197 | -2.5636 | -0.9113 | N/A | 0 | 1 |
| 20/100 | Buy-and-Hold 100% context | -12.5559 | -33.1361 | -25.3622 | -0.6220 | N/A | 0 | 1 |

### 5.4 OOS fold 3 — final holdout ที่ถูกเปิดเผยแล้ว

| Config | Portfolio | Total Return % | Annualized % | MDD % | Sharpe | Win Rate % | Trades | Open |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 10/50 | SMA | 1.1005 | 3.3379 | -1.4754 | 1.1700 | 31.71 | 41 | 1 |
| 10/50 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 10/50 | Buy-and-Hold 10% initial | 1.4534 | 4.4239 | -2.0164 | 1.1511 | N/A | 0 | 1 |
| 10/50 | Buy-and-Hold 100% context | 14.5340 | 50.2461 | -20.1636 | 1.2065 | N/A | 0 | 1 |
| 10/100 | SMA | 1.3956 | 4.2454 | -1.3960 | 1.4265 | 30.00 | 20 | 1 |
| 10/100 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 10/100 | Buy-and-Hold 10% initial | 1.4534 | 4.4239 | -2.0164 | 1.1511 | N/A | 0 | 1 |
| 10/100 | Buy-and-Hold 100% context | 14.5340 | 50.2461 | -20.1636 | 1.2065 | N/A | 0 | 1 |
| 20/50 | SMA | 0.6463 | 1.9516 | -1.5912 | 0.6756 | 33.33 | 33 | 1 |
| 20/50 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 20/50 | Buy-and-Hold 10% initial | 1.4534 | 4.4239 | -2.0164 | 1.1511 | N/A | 0 | 1 |
| 20/50 | Buy-and-Hold 100% context | 14.5340 | 50.2461 | -20.1636 | 1.2065 | N/A | 0 | 1 |
| 20/100 | SMA | 0.3247 | 0.9772 | -1.8678 | 0.3439 | 23.53 | 17 | 0 |
| 20/100 | Cash | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0 | 0 |
| 20/100 | Buy-and-Hold 10% initial | 1.4534 | 4.4239 | -2.0164 | 1.1511 | N/A | 0 | 1 |
| 20/100 | Buy-and-Hold 100% context | 14.5340 | 50.2461 | -20.1636 | 1.2065 | N/A | 0 | 1 |

## 6. ผลต้นทุนเพิ่มเป็นสองเท่า — Development เท่านั้น

- Base: commission 0.1% ต่อ entry/actual exit และ spread 0.05% ที่ long entry
- Stress: commission 0.2% ต่อ entry/actual exit และ spread 0.10% ที่ long entry
- Spread อยู่ใน entry execution price ไม่หักเป็น cash fee ซ้ำ; commission คิดจาก notional ของแต่ละ leg ครั้งเดียว

| Config | Base Return % | Double-cost Return % | Double-cost Annualized % | ผลต่าง pp | Base MDD % | Double-cost MDD % | Closed Trades (base/stress) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10/50 | 0.2306 | -2.6697 | -2.6848 | -2.9003 | -4.6894 | -7.0516 | 117/117 |
| 10/100 | -0.9357 | -3.0039 | -3.0380 | -2.0682 | -5.7245 | -7.4851 | 84/84 |
| 20/50 | -2.1460 | -4.6634 | -4.6895 | -2.5174 | -6.1027 | -8.1538 | 104/104 |
| 20/100 | 3.1483 | 1.6434 | 1.6625 | -1.5049 | -3.6018 | -4.0728 | 58/58 |

**ข้อจำกัดของ stress artifact:** reviewed worker เก็บเฉพาะ Return, MDD, Trades และ Exposure ของ stress ไม่เก็บ stress equity curve/full ledger จึงรายงาน stress Sharpe และ Win Rate เป็น N/A และยังไม่มี doubled-cost OOS ใน batch นี้ ไม่สร้างตัวเลขแทนและไม่ rerun เพราะใช้ครบเพดาน 20 evaluations แล้ว

## 7. Independent Critic Verdict ต่อ trial — เก็บประวัติเดิม

| Config | Verdict จาก independent model critic ใน Experiment Loop |
|---|---|
| 10/50 | REJECTED |
| 10/100 | INCONCLUSIVE |
| 20/50 | REJECTED |
| 20/100 | INCONCLUSIVE |

Critic เดิมได้รับ summary metrics ไม่ใช่ source/ledger/equity/provenance ทั้งหมด จึงมีคำวิจารณ์ว่า “ยังไม่เห็นหลักฐาน” บางข้อ ซึ่งไม่ใช่ข้อพิสูจน์ว่า artifacts เหล่านั้นไม่มีอยู่จริง ประวัติ critic ไม่ถูกแก้ทับ; batch-level review ที่ตรวจ full artifacts จะอธิบาย scope และแก้ความเข้าใจนี้แยกต่างหาก

## 8. สิ่งที่ Agent เรียนรู้และสมมติฐานต่อไป — ข้อเสนอเท่านั้น

- ต้นทุนซื้อขายมีผลต่อ SMA ที่เข้าออกถี่: 10/50 เปลี่ยนจาก development บวกเล็กน้อยเป็นลบเมื่อเพิ่มต้นทุน ส่วนทุก configuration มีผลลดลง
- ผล development ของ 20/100 ไม่ยืนยันผล OOS: ผลบวกใน development อยู่ร่วมกับ OOS สองช่วงติดลบได้
- การลด drawdown ต้องแยกจากการสร้างผลตอบแทนส่วนเกิน และไม่ควรอ้าง alpha จากการถือเงินสดมากขึ้น
- Critic ควรเห็น terminal accounting, ledger/curve และ audit manifest ก่อนสรุปว่าไม่พบหลักฐาน; การปรับวิธีให้ context เป็น skill/method proposal รอ review ไม่ถูก activate ในรอบนี้
- จำนวน trades ไม่เท่าจำนวน independent observations; hourly Sharpe ไม่ได้ปรับ serial correlation หรือ multiple comparisons

### สมมติฐานที่ระบบเสนอจริงหลังแต่ละ trial

1. **SMA 10/50** — การทดสอบพารามิเตอร์เดิม fast=10 และ slow=50 บนข้อมูลใหม่ที่ไม่เคยใช้เลือกกลยุทธ์ โดยคิดต้นทุนและสถานะปลายงวดให้เทียบกันได้ จะช่วยตรวจสอบว่าผลตอบแทนสุทธิส่วนต่างจาก buy-and-hold ที่จัดสรร 10% ยังคงติดลบหรือไม่ โดยยังไม่ตั้งสมมติฐานว่ากลยุทธ์มีความได้เปรียบ
   เหตุผล: กลยุทธ์แพ้เกณฑ์เทียบที่จัดสรร 10% ทั้งสามช่วง และผลช่วงพัฒนาเปลี่ยนจากบวกเป็นลบเมื่อเพิ่มต้นทุน จึงควรทดลองยืนยันพารามิเตอร์เดิมหนึ่งชุด แทนการเลือกค่าใหม่จากผลที่เปิดเผยแล้ว หลักฐานปัจจุบันไม่รองรับว่าค่า fast หรือ slow อื่นน่าจะดีกว่า

2. **SMA 10/100** — พารามิเตอร์เดิม fast=10 และ slow=100 อาจยังไม่ให้ผลตอบแทนส่วนเกินสุทธิเหนือเกณฑ์ถือสินทรัพย์ด้วยเงินจัดสรร 10% อย่างสม่ำเสมอ เมื่อทดสอบกับข้อมูลนอกตัวอย่างใหม่โดยคิดต้นทุนและสถานะปลายงวดให้เท่าเทียมกัน
   เหตุผล: เสนอการทดลองยืนยันพารามิเตอร์เดิมเพียงชุดเดียว แทนการเลือกค่าใหม่ที่ไม่มีหลักฐานรองรับ เพราะผลช่วงพัฒนาติดลบ และผลตอบแทนส่วนเกินในสามช่วงที่รายงานอยู่ที่ประมาณ +0.198, -0.016 และ -0.058 จุดเปอร์เซ็นต์ โดยยังมีข้อจำกัดด้านต้นทุนและความเท่าเทียมของเกณฑ์เปรียบเทียบ ข้อมูลนี้จึงรองรับการตรวจสอบความทนทานมากกว่าการอ้างว่าการปรับพารามิเตอร์จะช่วยเพิ่มผลตอบแทน

3. **SMA 20/50** — การทดสอบพารามิเตอร์เดิม fast=20 และ slow=50 บนข้อมูลใหม่ที่ไม่เคยใช้เลือกกลยุทธ์ ภายใต้ต้นทุนและกติกาประเมินที่เทียบเคียงกัน จะช่วยตรวจสอบสมมติฐานว่ากลยุทธ์ให้ผลตอบแทนสุทธิส่วนเพิ่มเหนือเงินสดและเกณฑ์ซื้อถือที่จัดสรรเงินเท่ากันได้หรือไม่ โดยยังไม่มีหลักฐานเพียงพอให้คาดว่าจะผ่าน
   เหตุผล: ควรตรึงพารามิเตอร์เดิมแทนการเสนอค่าที่ปรับใหม่ เพราะไม่มีหลักฐานรองรับทิศทางการปรับ และไม่ทราบประวัติการค้นหาพารามิเตอร์ ผล evaluation ทั้งสองช่วงติดลบ ส่วน final holdout ให้ผลตอบแทนต่ำกว่าเกณฑ์ซื้อถือที่จัดสรร 10% อีกทั้งผลพัฒนาไวต่อต้นทุน จึงควรทดลองยืนยันนอกตัวอย่างหนึ่งครั้งด้วยวิธีที่ตรวจสอบซ้ำได้ มากกว่าค้นหาค่าที่ดูดีจากข้อมูลที่เปิดเผยแล้ว

4. **SMA 20/100** — การทดสอบซ้ำแบบลงทะเบียนแผนล่วงหน้าด้วย fast=20 และ slow=100 บนข้อมูลที่ยังไม่เคยใช้ตัดสินใจ จะช่วยตรวจสอบว่าพารามิเตอร์เดิมให้ผลตอบแทนสุทธิเหนือเงินสดและ buy-and-hold ที่จัดสรรเงิน 10% ได้หรือไม่ โดยยังไม่มีหลักฐานเพียงพอให้คาดว่าจะเหนือกว่า
   เหตุผล: เสนอการทดลองยืนยันพารามิเตอร์เดิมเพียงหนึ่งชุด แทนการปรับค่าจากผลทดสอบที่เปิดดูแล้ว เพราะผลนอกตัวอย่างสองช่วงติดลบ และ final holdout ให้ผลตอบแทนเพียง 0.3247% ขณะที่ต้นทุนยังไม่ผ่านการยืนยัน ไม่มีหลักฐานรองรับว่าพารามิเตอร์อื่นดีกว่า

ข้อเสนอที่มีเหตุผลสำหรับการ review ครั้งถัดไปคือยืนยันกติกาเดิมบนข้อมูลใหม่ที่ยังไม่เคยใช้ตัดสินใจ ทดสอบ cost stress ใน OOS และประเมิน uncertainty ด้วยวิธีที่คำนึงถึงการพึ่งพาตามเวลา แต่ยังไม่อนุมัติหรือเริ่มข้อเสนอใด

## 9. ข้อจำกัดและการตีความ

- ข้อมูลหนึ่ง exchange หนึ่งคู่เงิน หนึ่ง timeframe และกติกา 4 ชุด ไม่ครอบคลุมตลาดทุกสภาวะ ไม่มีหลักฐานกำไรจริง
- Commission/spread เป็น scenario assumptions ไม่ใช่อัตราบัญชีที่ยืนยัน; ไม่มี orderbook, market impact, latency หรือ partial fills
- Fractional unit 1e-8 BTC เป็นหน่วยของ simulation ไม่ได้พิสูจน์ว่าผ่าน historical Binance LOT_SIZE/MIN_NOTIONAL rules
- Terminal positions ทั้ง strategy และ B&H mark ที่ final close ไม่ขายปลอมและไม่คิด exit fee ที่ยังไม่เกิด ผลตอบแทนจึงไม่ใช่ liquidation return หากขายจริงอาจต่ำกว่านี้
- Equal initial allocation ไม่ใช่ equal time exposure หรือ continuously risk-matched portfolio; exposure_pct ใน engine คือเวลาที่มีสถานะ ไม่ใช่สัดส่วนเงินลงทุน
- OOS folds เป็นบัญชีอิสระ reset ไม่มีผลต่อเนื่องสองปี; stress จำกัด development และไม่มี retained stress Sharpe/Win Rate
- Annualized Return/Sharpe ของช่วงสั้นเป็นค่าพรรณนาภายใต้นิยามที่เปิดเผย ไม่ใช่ความมั่นใจทางสถิติ ไม่มี confidence interval/HAC adjustment/deflated Sharpe
- Final holdout และทุกช่วงใน dataset นี้ถูกเปิดเผยแล้ว ห้ามนำไปใช้เป็น fresh holdout ใน spec ใหม่; same-batch exception ไม่เปิดสิทธิ์ปรับ parameter ตามผลแล้วรันต่อ
- Process isolation เป็น trusted-code hygiene ไม่ใช่ OS sandbox; ไม่รองรับ generated executable code

## 10. Audit และ batch-level independent review

### 10.1 Independent cost/fractional execution audit — PASS ภายใน scope ที่บันทึกไว้

- ตรวจ 16 detailed results (development + 3 OOS ต่อ configuration), 707 buy signals, 699 close/realized trades และ 8 terminal positions
- Reconcile buy signal ทุกตัวกับ realized entry หรือ terminal position และ close signal ทุกตัวกับ realized exit: ไม่พบ missing, duplicate หรือ orphan fills ในหลักฐานที่เก็บไว้
- จำนวน BTC ที่เกิดจริงใน simulation อยู่ระหว่าง **0.00810466–0.01660301 BTC** และเป็นหน่วย **1e-8 BTC** จึงไม่ติดข้อจำกัด whole-BTC units ของ backtest แบบปกติ
- ตรวจ entry = next open × (1+spread), exit = raw next open, commission ครั้งเดียวต่อ entry/exit, net PnL และ terminal entry-fee-only marks ครบ
- ตรวจ 69,780 equity points; maximum accounting discrepancy ประมาณ **1.0914e-11 USDT** อยู่ใน tolerance 1e-7 USDT
- Trade counts และ exposure ของ doubled-cost development ตรง normal ทั้งสี่ trials แต่เป็นเพียง aggregate evidence ไม่ใช่ full stress ledger audit
- **ขอบเขตการยืนยันเรื่องคำสั่งยกเลิก:** ไม่พบสัญญาณที่ไม่มี fill จากหลักฐาน normal-cost ที่เก็บไว้ แต่ original broker warning/cancellation lifecycle logs ไม่ถูก persist จึงไม่อ้างว่าตรวจ log ที่ไม่มีอยู่ และไม่ขยายผล pass ไปยัง stress ledgers ที่ไม่ได้เก็บ

Audit DATA: `reports/batch001-execution-audit.json`
Audit SHA256: `347173b5ff19b8de552225fd959a72698b3f5481167a0682fb28e16485404dfa`

### 10.2 Independent performance/metrics review

- ตรวจ metrics JSON/CSV ครบ 64 rows และ 16 evaluation windows โดยคำนวณ annualized return, hourly Sharpe, MDD และ Win Rate ซ้ำจากหลักฐานที่เก็บไว้: ผ่านทั้งหมด
- ผล batch-level critic: **DESCRIPTIVE_DRAWDOWN_EVIDENCE_ONLY_NO_PROMOTION**

ทั้ง 4 ชุดต้องรายงานครบ ไม่เลือกผู้ชนะจาก holdout ชุด 10/100, 20/50 และ 20/100 มี drawdown ต่ำกว่า BH10 ครบสามช่วง ส่วน 10/50 ต่ำกว่าเพียงสองช่วง หลักฐานสนับสนุนเชิงพรรณนาบางชุด ไม่ใช่ข้อพิสูจน์กำไรจริง alpha หรือนัยสำคัญทางสถิติ ไม่ปฏิเสธสมมติฐานลด drawdown เพียงเพราะผลตอบแทนต่ำกว่า

| Config | Batch-level verdict | OOS folds ที่ drawdown ต่ำกว่า BH10 |
|---|---|---:|
| 10/50 | MIXED_DRAWDOWN_EVIDENCE | 2/3 |
| 10/100 | DESCRIPTIVE_DRAWDOWN_SUPPORT_NOT_PROVEN | 3/3 |
| 20/50 | DESCRIPTIVE_DRAWDOWN_SUPPORT_NOT_PROVEN | 3/3 |
| 20/100 | DESCRIPTIVE_DRAWDOWN_SUPPORT_NOT_PROVEN | 3/3 |

**คำอธิบายต่อ configuration**

- **10/50**: ลด drawdown ได้ 2 ใน 3 ช่วงนอกตัวอย่าง แต่ช่วงแรก drawdown แย่กว่า BH10 จึงไม่สม่ำเสมอตามสมมติฐานเดิม ผลตอบแทนนอกตัวอย่างติดลบสองช่วงและเป็นบวกช่วงสุดท้าย การได้ผลตอบแทนต่ำกว่าเกณฑ์ไม่ใช่เหตุให้ปฏิเสธสมมติฐานลด drawdown โดยลำพัง ไม่มีการจัดอันดับหรือเลือกผู้ชนะจาก holdout
- **10/100**: ลด drawdown เทียบ BH10 ได้ทั้ง 3 ช่วงนอกตัวอย่าง เป็นหลักฐานเชิงพรรณนาที่สอดคล้องกับสมมติฐานเดิม แต่ยังไม่พิสูจน์นัยสำคัญหรือความทนทานในอนาคต ผลตอบแทนนอกตัวอย่างติดลบสองช่วงและเป็นบวกช่วงสุดท้าย การได้ผลตอบแทนต่ำกว่าเกณฑ์ไม่ใช่เหตุให้ปฏิเสธสมมติฐานลด drawdown โดยลำพัง ไม่มีการจัดอันดับหรือเลือกผู้ชนะจาก holdout
- **20/50**: ลด drawdown เทียบ BH10 ได้ทั้ง 3 ช่วงนอกตัวอย่าง เป็นหลักฐานเชิงพรรณนาที่สอดคล้องกับสมมติฐานเดิม แต่ยังไม่พิสูจน์นัยสำคัญหรือความทนทานในอนาคต ผลตอบแทนนอกตัวอย่างติดลบสองช่วงและเป็นบวกช่วงสุดท้าย การได้ผลตอบแทนต่ำกว่าเกณฑ์ไม่ใช่เหตุให้ปฏิเสธสมมติฐานลด drawdown โดยลำพัง ไม่มีการจัดอันดับหรือเลือกผู้ชนะจาก holdout
- **20/100**: ลด drawdown เทียบ BH10 ได้ทั้ง 3 ช่วงนอกตัวอย่าง เป็นหลักฐานเชิงพรรณนาที่สอดคล้องกับสมมติฐานเดิม แต่ยังไม่พิสูจน์นัยสำคัญหรือความทนทานในอนาคต ผลตอบแทนนอกตัวอย่างติดลบสองช่วงและเป็นบวกช่วงสุดท้าย การได้ผลตอบแทนต่ำกว่าเกณฑ์ไม่ใช่เหตุให้ปฏิเสธสมมติฐานลด drawdown โดยลำพัง ไม่มีการจัดอันดับหรือเลือกผู้ชนะจาก holdout

**แก้ความเข้าใจจาก critic input โดยไม่แก้ทับประวัติเดิม**

- คำกล่าวว่าไม่มีข้อมูลต้นทาง/ledger/equity/code/provenance เป็นข้อจำกัดของ input นักวิจารณ์ ไม่ใช่ข้อเท็จจริงของ repository: อ่าน raw pages, source, spec และ artifact ที่ตรวจด้วย Registry.verify/verify_result_artifact แล้ว
- รายละเอียดสถานะปลายงวดระบุชัดใน source/metadata และ artifact: finalize_trades=False, mark_to_final_close_no_forced_fill; BH และกลยุทธ์ไม่หัก exit fee สมมติเหมือนกัน จึงไม่ใช่ข้อบกพร่องด้านความเท่าเทียมที่ยังไม่ทราบ
- ประวัติ batch ปัจจุบันมี 4 configurations, 20 evaluations ตาม spec; ไม่ใช่ไม่ทราบจำนวนการลองใน batch แต่ยังรับรองประวัติที่ไม่ถูกบันทึกภายนอกไม่ได้
- นิยาม exposure_pct มีอยู่ใน source เป็นสัดส่วนแท่งที่ถือ long ที่ close ไม่ใช่เงินลงทุน 100%; รายงานตัวเลขใกล้ 100% ของ BH10 จึงไม่ผิดนิยาม
- Sharpe และ WinRate ของต้นทุนปกติคำนวณซ้ำได้จากหลักฐานที่บันทึก; ข้อจำกัด stress ledger/curve และ stress OOS เป็นการขาดจริง
- คำวิจารณ์ 20/100 ที่ระบุ trades สองช่วงแรก 18,20 สลับกับ artifact จริง ซึ่งเป็น 20,18,17 ตามลำดับ; ไม่แก้ต้นฉบับ
- คำตัดสิน REJECTED ที่อิงไม่ชนะผลตอบแทนไม่ใช่การทดสอบตรงสมมติฐานเดิมซึ่งเน้นลด drawdown; หลักฐานความเสี่ยงกับข้ออ้างกำไรต้องแยกกัน

Performance review DATA: `reports/batch001-independent-performance-review.json`
Performance review SHA256: `aaa1a5284514e2720d45d8855cbe84422f70ce8dc4560aac5a9e316e04e537e9`

## 11. ข้อเสนอที่ยังไม่เริ่มและสถานะหยุด

- หากได้รับอนุมัติแยกต่างหากในอนาคต ให้ตรึงเกณฑ์ขั้นต่ำของประโยชน์ drawdown และงบยอมเสียผลตอบแทนก่อนทดสอบข้อมูลใหม่ โดยคงรายงานทุกชุด ไม่เลือกชุดจาก holdout ที่เปิดแล้ว
- ทดสอบความทนทานของประโยชน์ drawdown ต่อค่าต้นทุนและความไม่แน่นอนแบบ block-aware ในทุกช่วงใหม่ โดยเก็บ stress ledger และ equity เต็มเพื่อคำนวณ Sharpe/WinRate ตรวจซ้ำได้ ขณะนี้เป็นเพียงข้อเสนอ inert

- ไม่สร้าง strategy executable ใหม่ ไม่แก้ code/dependency/policy ไม่เลื่อนสถานะกลยุทธ์ ไม่ activate skill changes
- บันทึก batch completion แล้ว และปิด approval เดิมด้วย revocation event หลังครบ 20 evaluations เพื่อหยุดรอผู้ใช้ตรวจผล
- สถานะ: **HALTED_AWAITING_HUMAN_RESULTS_REVIEW** — ไม่เริ่ม batch ถัดไป, paper trading, scheduler หรือ live trading

Batch completion event: `fe25df74a53954b4d9ab9deb922fbe441257cb75d3bfcf6c80caac9979e4d22b`
Approval closure event: `04f02a812b246a4cb1f1bc41f2afd83bc5928ee39e1a14415bbfb16a127e5e30`

## 12. ไฟล์หลักฐาน

- `reports/batch001-metrics.csv` — ตาราง metrics 64 rows ครบ development/OOS ทั้ง SMA, Cash, BH10 และ BH100
- `reports/batch001-metrics.json` — ค่าเต็ม สูตร ขอบเขตเวลา stress aggregates และ original critic/next proposals
- `reports/batch001-execution-audit.json` — ตรวจ costs, fractional quantities, signal-to-fill และ equity reconciliation
- `reports/batch001-independent-performance-review.json` — independent metrics verification และคำตัดสิน
- `reports/batch001-artifact-manifest.json` — SHA256 ของรายงานและ artifacts เชื่อมกับ spec/code/data/approval
- `experiments/<run_id>.json` ทั้งสี่ไฟล์ — immutable run evidence; identities อยู่ใน metrics JSON และ SQLite
- `storage/lab.sqlite` — append-only event history, approvals, reservations, lessons, proposals และ batch stop
