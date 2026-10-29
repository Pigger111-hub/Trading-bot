# Phase 3 — รายงาน autonomous research cycle แรก

## ข้อสรุปสำคัญ

**วงจรระบบทำงานครบและตรวจ provenance ผ่าน แต่ข้อเสนอวิจัยยังไม่ผ่าน Critic**

- Cycle ID: `adbc4a5d-5fdc-4212-9b4f-9f1a0845baa6`
- สถานะ workflow: `COMPLETED` — หมายถึงจบการค้นคว้า/ออกแบบ ไม่ใช่ backtest สำเร็จ
- Critic verdict: **`REVISE`**
- ข้อเสนอทั้งสี่ในคิว: **`REJECTED`** ยังไม่มีข้อเสนอที่พร้อมอนุมัติให้ทดลอง
- หยุดหลังหนึ่งรอบ ไม่มีการรันซ้ำเพื่อบังคับให้ critic ผ่าน ไม่มี market backtest, scheduler, trading, source approval หรือ proposal approval

ผลที่ไม่ผ่านถูกเก็บครบ ไม่เปลี่ยน verdict ให้ดูดีขึ้น ความสามารถที่ยืนยันได้คือ workflow ค้นคว้า–เสนอ–วิจารณ์–เก็บคิวและบทเรียน ไม่ใช่ความสามารถทำกำไรหรือคุณภาพกลยุทธ์ที่พิสูจน์แล้ว

## 1. ก่อนเริ่มตรวจอะไรแล้ว

Phase 2.5 เดิมผ่านการตรวจซ้ำด้วย backend52 tests, frontend14 tests, TypeScript/Vite build และ browser จริง จากนั้นเพิ่ม Phase3 แบบแยก code/environment/state โดยไม่แก้ approved engine หรือ Batch001 artifacts

หลังแก้สอง blocker จาก independent review:

| การตรวจ | ผล |
|---|---|
| Phase3 core/workflow tests | 98 ผ่าน |
| Dashboard backend/API tests | 59 ผ่าน |
| Frontend tests | 33 ผ่าน |
| Production build / Ruff | ผ่าน |
| Independent re-review | ผ่าน, ไม่มี security/logic issues ที่ระบุค้าง |
| Original evidence | 56 protected files ไม่เปลี่ยน |
| Original registry / budget | 88 events / 20 engine evaluations เท่าเดิม |

Reviewed32-file code digest ก่อน actual cycle:

`18c4f2bd9433da642d7032a015ed5e7dd3faa15f40460a5aa615fe433fbda8f6`

Blockers แรกและคำตัดสินหลังแก้เก็บแยกใน `code-review-initial.json` และ `code-review.json` ไม่เขียนทับประวัติ

## 2. ระบบทำอะไรเองจริง

1. **Hermes research_planner** อ่าน scoped findings/critique ของ Batch001 และบริบท knowledge/gaps แล้วตั้งคำถามกับ queries สำหรับสี่ strategy families โดยไม่ให้ผู้ใช้คิดกลยุทธ์เอง
2. **Deterministic source service** ส่ง Crossref queries แบบ bounded และอ่านสองเอกสารที่อยู่ใน reviewed catalog เดิม
3. **Hermes knowledge_researcher** สร้างร่างความรู้และสี่สมมติฐานพร้อม entry/exit, parameters, falsification และคะแนน heuristic
4. **Deterministic planner** สร้าง proposed experiment specifications: metrics, comparators, chronological splits, costs, proposed budget และ execution gates ที่ยังปิด
5. **Hermes independent_critic** อ่านร่าง แหล่งข้อมูล และแผนจาก fresh context แล้วให้ REVISE พร้อมปัญหาแปดข้อ
6. ระบบเก็บ hypotheses, rejected queue entries, lessons, gaps, raw responses และ provenance จากนั้นหยุด

Actual cycle ใช้ **สาม Hermes role calls** ที่ reserve ก่อนเรียกครบสามรายการ และ completed ครบสามรายการ พร้อม usage/session IDs ใน event chain นี่เป็นงบของ controller cycle ไม่ใช่จำนวน model calls ทั้งหมดที่ใช้ในการพัฒนา/review ซอฟต์แวร์

## 3. สิ่งที่เก็บจากรอบจริง

| รายการ | จำนวน / สถานะ |
|---|---|
| HTTP retrievals ใน cycle | 6 |
| Crossref candidates หลัง deduplicate DOI | 11, รอ human approval ทั้งหมด |
| Reviewed seed documents ที่ดึงจริง | 2 |
| Source records รวม | 13 |
| Knowledge card drafts | 2, สถานะ REJECTED_DRAFT ไม่ได้เลื่อนเป็น FACT |
| Hypotheses | 4 |
| Queue entries | 4 REJECTED, ไม่มี human approval |
| Lessons / method proposals ที่บันทึก | 11 |
| Open knowledge gaps | 9 |
| Phase3 audit events | 76 |
| New engine evaluations | 0 |

Phase3 event-chain head หลังจบรอบ:

`8e98addfd7ca7f9981381123db34da0a262f349b654af9cb96a287a3ec9b4101`

Crossref candidates เป็น **metadata ที่พบจริง** ไม่ใช่การอ่าน full papers สิบเอ็ดฉบับ และไม่ได้รับรองคุณภาพงานวิจัย ความเกี่ยวข้องของผลค้นบางรายการยังต้องคัดกรอง การมี DOI ไม่ใช่หลักฐานว่า strategy มี alpha

ตัวอย่างชื่อที่พบและเก็บไว้รอ review:

- *Optimal Trend-Following With Transaction Costs* — DOI `10.2139/ssrn.4282126`
- *Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit* — DOI `10.2139/ssrn.2222196`
- *Fat tails, serial dependence, and implied volatility index connections* — DOI `10.1016/j.ejor.2021.09.038`

ชื่อ/DOI เหล่านี้อ้างจาก retrieved metadata เท่านั้น ไม่สรุปข้อค้นพบภายในบทความ

## 4. เสนออะไร และทำไม

**ตารางนี้เป็นร่างที่ถูกปฏิเสธ ไม่ใช่คำแนะนำลงทุนหรือแผนพร้อมรัน** คะแนนเป็น heuristic priority ไม่ใช่โอกาสกำไรหรือ mutual information ที่คำนวณจากข้อมูล

| ลำดับที่บันทึก | Family / ร่างสมมติฐาน | หลักการเข้า–ออกในร่าง | คะแนน | ข้อควรระวัง |
|---|---|---|---:|---|
| 1 | Momentum: แยกสัญญาณออกจากการรับความเสี่ยงตลาด | Long10% เมื่อผลตอบแทนย้อนหลัง24hเป็นบวก; ออกเมื่อไม่เป็นบวก ใช้เปิดแท่งถัดไป | 15 | baseline และ bootstrap/Holm inference ยังไม่ครบ |
| 2 | Mean reversion: ตรวจการกลับตัวหลังราคาต่ำผิดปกติ | ราคาต่ำกว่าค่าเฉลี่ย20แท่ง2sample standard deviations; ออกเมื่อกลับค่าเฉลี่ยหรือครบ12แท่ง | 15 | จำนวน confirmatory folds ไม่ตรงแผน และยังไม่มี empirical evidence |
| 3 | Volatility: แยกผล position sizing จากสัญญาณทิศทาง | ใช้168hour volatility และปรับน้ำหนักทุก24แท่ง | 15 | ร่างเสนอ max_weight0.2 เกินเพดานเดิม0.1; **ไม่อนุมัติและไม่เปลี่ยนเพดาน** |
| 4 | Trend following: ทดสอบ SMA20/100 ซ้ำอย่างมีฐานเทียบ | Long10% เมื่อSMA20ตัดขึ้นSMA100; ออกเมื่อตัดลง เปิดแท่งถัดไป | 13 | เป็น recorded retest ไม่ใช่ signal family ใหม่ และฐานเทียบ/foldsยังไม่ตรงแผน |

ทั้งสี่มี evidence_quality **1/5** จาก model ซึ่งต่ำกว่า ceiling2/5 ของ corpus นี้ เอกสาร mechanics และ metadata ไม่ใช่หลักฐานว่ากลยุทธ์เหล่านี้ชนะตลาด คะแนน15ที่เท่ากันเรียงด้วย deterministic ID tie-break ไม่ได้พิสูจน์ว่า momentum ดีกว่าสองรายการที่คะแนนเท่ากัน

## 5. Critic พบอะไร

1. **ฐานเทียบไม่ตรงกัน:** h1/h2/h4 ขอ investment-matched baseline ที่ calibrate จาก development แต่ planner มี Cash, fixed BH10 และ contextual BH100 ต้องนิยาม weight/formula/cost/freeze rule ให้ชัด Time in position ไม่เท่ากับ invested-capital/risk matching
2. **จำนวน folds ไม่ตรงกัน:** บางร่างต้องการสามช่วงใหม่ แต่ planner มี development และสองช่วงประเมินต่อมา ห้ามนับช่วงเลือกพารามิเตอร์เป็น independent confirmation
3. **การเลือก configurations ยังไม่ตรึง:** planner เปิดสอง development configurations แต่ยังไม่มี candidate ที่สอง/selection objective/tie-break และต้องนับ prior four configurations/20evaluations เป็น selection burden ด้วย
4. **Volatility sizing ไม่ตรง risk/engine plan:** ร่างขอ weightสูงสุด20% และ periodic resizing แต่ plan10% ไม่มี partial-reduction/fractional-unit/cash/rebalancing specification การเปลี่ยน risk limit ไม่ได้รับอนุญาต
5. **สถิติ momentum ยังไม่ครบ:** ต้องระบุ inference scope, independent-account boundaries, bootstrap interval/test, p-values สำหรับ Holm correction, block-length sensitivity และ insufficient outcome ก่อนอ้างนัยสำคัญ
6. **Warm-up และ sample adequacy ไม่ชัด:** within-split1000h ทำให้ scored horizons ต่างกัน ต้องจับคู่ benchmark entry, initialization, account reset, terminal/pending orders และกำหนด30closed tradesว่าต่อfold/cost/pool; จำนวน30ไม่ใช่ power justification
7. **ข้อมูลยังไม่พร้อมและ freshness ยังไม่พิสูจน์:** ณ29ตุลาคม2026 ช่วงที่เสนอจำนวนมากอยู่อนาคต และช่วงต้นตุลาคมผ่านไปแล้ว ต้องตรวจ provenance/exposure/coverage/missing bars/availability ไม่อ้างว่า fresh จากวันที่อย่างเดียว
8. **ต้นทุน/implementation ยังไม่เทียบตรง:** literal quotes รองรับ narrow mechanics cards แต่ไม่รองรับ alpha และ native documented spread ไม่เท่ากับ half-spread-per-side โดยอัตโนมัติ ต้อง pin engine/version และตรวจไม่มี double charging; ไม่มี actual slippage/impact/bid–ask evidence

นี่เป็นผลตรวจ design จาก actual critic call ไม่ใช่ผลแพ้/ชนะในตลาด เพราะไม่ได้รัน market experiment

## 6. ระบบเรียนรู้อะไร

บทเรียนหลักที่บันทึกจาก researcher/critic คือแยกเอกสารกลไกออกจาก empirical alpha, ทำ hypothesis–baseline–fold–budget ให้ตรงกันก่อนทดสอบ, รู้ว่าSMA20/100เป็น retest และไม่ยืนยันความใหม่ระดับโลก, รวมทั้งไม่ตีความข้อมูลอนาคต/ข้อมูลไม่ตรวจแล้วว่าใช้งานได้

**จุดอ่อนที่วงจรนี้เปิดเผย:** generic deterministic planner ยังไม่รองรับรายละเอียดเฉพาะแต่ละ family ที่ researcher เสนออย่างสอดคล้องกัน Critic จึงเป็น gate ที่มีประโยชน์ แต่ไม่ควรถูกใช้แทน deterministic schema/risk/plan compatibility checks ในการพัฒนารอบต่อไป ข้อนี้เป็นข้อสังเกตจากการตรวจระบบ ไม่ใช่การแก้โค้ด/เริ่มcycleใหม่อัตโนมัติ

คำถามต่อไปที่ agent บันทึกไว้ เช่น baseline-weight formula/fold structure แบบใดจะเป็น authoritative, จะใช้หนึ่งconfigurationหรือ freezecandidateที่สองอย่างไร, bootstrapเชื่อมHolmอย่างไร, variable sizing/warm-up/terminal marksจะนิยามอย่างไร และอะไรยืนยันความพร้อม/non-exposureของข้อมูลแต่ละช่วง

## 7. Provenance ตรวจอย่างไร

- Canonical report จริง: `adbc4a5d-5fdc-4212-9b4f-9f1a0845baa6.json`
- Event chain/model responses/sources/card revisions/queue: `../state/lab.sqlite`
- `cycles[0].details` เท่ากับ canonical report ที่อ่านกลับจริง
- ตรวจ literal quotes **สองรายการ** กับ source revision, item hash และ text SHA256 แล้ว; raw SHA ใน quoteตรงกับ source revisionที่อ้าง
- Source revision1ของ seed แรกมี raw SHA256 `f82b43312a2cdd34add784421a72b06af1aef12cdd73f203611b232ba7348172`
- Source revision1ของ seed ที่สองมี raw SHA256 `0685c0db587552cd4c89d62dd3d70a330b363e1d15aef5d39dcecd09801db292`

เอกสารที่อ่านจริง:

1. backtesting.py API: `https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html` รองรับ claim เรื่อง commission เข้า/ออก ไม่รองรับผลตอบแทนของกลยุทธ์
2. Freqtrade backtesting: `https://www.freqtrade.io/en/stable/backtesting/` รองรับว่ามี detail-timeframe option ไม่รับรองว่าจะขจัด intrabar error หรือจำลองตลาดครบถ้วน

## 8. Dashboard และสิ่งที่ยังปิดอยู่

เปิด `http://127.0.0.1:8765` แล้วเลือก **วิจัยอัตโนมัติ · Phase3** จะเห็นรอบจริง, counters, persisted rankings, rejected queue, critic, lessons และ gaps โดยไม่สร้าง/รันข้อมูลใหม่ Browser actual-data checkผ่านบนdesktopและ390pxmobile; ไม่มี captured runtime errors หรือปุ่ม mutation/run/approve

`execution_enabled=false`, `scheduler_enabled=false`, `credentials_enabled=false` ทุก proposalยังไม่อนุมัติ ไม่มี futures/leverage/real trading/continuous paper execution ไม่มีข้อมูลตลาดใหม่และไม่เปลี่ยน source catalog เดิมหรือ risk policy

**หยุดแล้วหลังรอบแรก** ขั้นที่ควรพิจารณาต่อคือขออนุมัติรอบแก้ research/experiment design แบบ bounded เท่านั้น: จับคู่ hypothesisกับplan,คงเพดาน10%,ทำstatistical/benchmark specificationให้ครบ และเลือกเอกสารใหม่เข้ากระบวนการ human review ไม่ใช่อนุมัติ backtest ของข้อเสนอที่ถูกปฏิเสธทันที
