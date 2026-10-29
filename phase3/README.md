# Phase 3 — Autonomous Research & Learning (preparation)

ระบบนี้เพิ่ม **การค้นคว้าและการออกแบบการทดลอง** ไม่ใช่ระบบส่งคำสั่งซื้อขายหรือรันกลยุทธ์อัตโนมัติ Phase 2.5 ตรวจซ้ำก่อนเริ่มแล้ว: backend 52 tests, frontend 14 tests, production build และ actual browser/first-trade inspection ผ่าน หลักฐานเดิม 56 ไฟล์ไม่เปลี่ยน, 88 audit events และ 20 engine evaluations เท่าเดิม

## ผลรอบแรก — หยุดรอการตรวจผลแล้ว

Actual cycle `adbc4a5d-5fdc-4212-9b4f-9f1a0845baa6` จบ workflow และตรวจ provenance ผ่าน แต่ critic ให้ **REVISE** ทำให้ทั้ง4 queue proposals เป็น **REJECTED** ยังไม่มีข้อเสนอพร้อมทดลองหรือรับรองกำไร สอง knowledge cards เป็น REJECTED_DRAFT ไม่ได้ยกระดับเป็น facts

รอบนี้ใช้3Hermes role calls; พบ11Crossrefmetadata candidates ที่ยังไม่อนุมัติและอ่าน2reviewed seed documents; บันทึก11lessons/9gaps โดยไม่รัน market backtest และไม่เปลี่ยน risk limits ดู `reports/cycle001-report-th.md` ก่อนดำเนินการต่อ **อย่ารันคำสั่ง run ซ้ำจากการจบรอบนี้โดยอัตโนมัติ**

## แยกจาก approved engine

- `lab3/`: deterministic Python controller, source validation, planning, versioned storage และ tool-free Hermes adapter
- `state/lab.sqlite`: Phase 3 event chain และ document revisions แยกจาก `storage/lab.sqlite` เดิม
- `reports/`: รายงานรอบค้นคว้าใหม่ ไม่เขียนทับผล Batch 001
- `CONTRACT.md`: shared interfaces, schemas, source/approval boundaries และขอบเขตแต่ละโมดูล
- `pyproject.toml` / `uv.lock` / `.venv`: environment แยก ไม่แก้ root engine dependencies
- Dashboard ใช้ read-only projection ไม่มีปุ่มอนุมัติ รัน แก้ไข หรือเปิด scheduler

## วงจรที่ผู้ใช้ไม่ต้องคิดหัวข้อเอง

1. **Hermes research planner** อ่าน gaps, cards และผล/คำวิจารณ์ Batch 001 แล้วตั้งคำถามและ search queries สำหรับ trend following, momentum, mean reversion และ volatility
2. **Deterministic source service** ค้น Crossref metadata แบบจำกัดจำนวน และเก็บ DOI/title/source provenance เป็น candidates; อ่านเอกสารเฉพาะ exact URLs ที่ผ่าน reviewed catalog แล้ว
3. **Hermes knowledge researcher** สรุปความรู้พร้อม exact quotes, ข้อไม่แน่ใจ, คำถามต่อไป และ declarative hypotheses ไม่สร้าง executable strategy code
4. **Deterministic planner** ตรวจ schema จัดอันดับแบบ heuristic และร่าง metrics, costs, benchmarks, chronological splits, freshness gates และ proposed budget ก่อนการทดลองใด ๆ
5. **Hermes independent critic** ใช้ fresh context ตรวจหลักฐานและการออกแบบ ไม่รับรองกำไร ต้องตอบ schema ที่ถูกต้องและไม่มี issues จึงผ่านเป็น proposal
6. บันทึก cards/hypotheses/critic/lessons/queue แบบ versioned; ผลที่ถูกปฏิเสธและ failures ไม่ถูกลบ แล้ว **หยุดหลังหนึ่ง foreground cycle**

Research planner, researcher และ critic เป็นบทบาทคนละ model call/บริบท ไม่ใช่หลักประกันความเป็นอิสระทางสถิติ และไม่ได้ปล่อยให้ LLM คุม execution หรือ risk limits

## สิ่งที่หมายถึงและไม่หมายถึง source approval

- Exact URLs ของ reviewed catalog เดิมเป็น seed sources โดยตรวจ original evidence ก่อนใช้งาน
- Crossref เป็นช่องทางค้น **bibliographic metadata** ไม่ใช่ peer-review authority, scientific credibility score หรือหลักฐานว่าอ่าน full paper แล้ว
- Candidate ที่ metadata ตรวจผ่านยัง **รอมนุษย์อนุมัติ** ไม่ถูกเพิ่มเป็น trusted source หรืออ้างเป็น empirical alpha evidence อัตโนมัติ
- การอนุมัติ source ต้องระบุ source identity, reviewer และเหตุผล เก็บประวัติไว้ การยืนยัน metadata อย่างเดียวไม่ยืนยันข้อสรุปทางวิทยาศาสตร์
- เพิ่มเส้นทาง usable catalog จริงแบบแยก gate: มนุษย์สั่งดึง exact document URL เพื่อ verification → เก็บ `QUARANTINED_DOCUMENT_TEXT` ที่ยัง approved=false → ตรวจ DOI/title association และ raw/text hashes → มนุษย์อนุมัติ `--scope full-document` → รอบถัดไปเลือก frozen snapshot นั้นได้ การ refresh ต้อง quarantine/อนุมัติใหม่ ไม่ย้าย metadata approval ให้กลายเป็น document approval เอง
- Cards ผูก source version, item hash, raw SHA256 และ text SHA256 พร้อม quote เพื่อย้อนกลับฉบับที่ใช้อ้างจริง แม้เอกสารมี revision ใหม่
- ไม่มีการอนุมัติ source ใหม่โดย agents ในรอบสาธิตนี้
- API/framework documentation รองรับกติกาหรือวิธีตรวจสอบ ไม่ใช่หลักฐานว่ากลยุทธ์จะชนะตลาด ความน่าเชื่อถือของสมมติฐานที่มีเพียงเอกสารทั่วไปต้องสะท้อนข้อจำกัดนี้

## การจัดอันดับและ experiment queue

คะแนน evidence quality, novelty, information gain และ complexity เป็น ordinal scores 1–5 ที่ต้องอธิบาย ไม่ใช่ความน่าจะเป็นกำไรหรือค่าทางสถิติที่วัดได้

```text
priority = 3 × evidence_quality + 2 × novelty
           + 3 × information_gain − 2 × complexity
```

Novelty เทียบกับประวัติของ lab ไม่ใช่คำอ้างว่าคิดค้นกลยุทธ์ใหม่ในโลก Information gain เป็น planning heuristic ไม่ใช่ mutual information ที่คำนวณจากการทดลอง

Queue แยก PROPOSED, APPROVED, RUNNING, COMPLETED และ REJECTED ออกจากผล backtest จริงของ Batch 001 ชัดเจน ใน Phase 3 นี้อนุญาตเพียงการทบทวน design และการปฏิเสธ: แม้เป็น APPROVED ก็เป็น **DESIGN_ONLY** ไม่ให้สิทธิ์รันจริง การเปลี่ยนเป็น RUNNING/COMPLETED ถูกปิดไว้

แผนต้องกำหนด entry/exit, falsification, metrics, Cash/BH10 comparators, BH100 context, costs และ sensitivity, minimum sample adequacy, data splits และ proposed evaluation budget แต่ **proposed budget ไม่ใช่ approved budget** ไม่มี engine evaluations ใหม่ถูกใช้ใน workflow นี้

## Holdout protection

ข้อมูล Batch 001 ที่เปิดดูแล้วทั้งช่วงเป็น exposed data ไม่ใช่เพียง final fold เปลี่ยน UUID หรือ file format ไม่ทำให้กลับมาเป็น untouched holdout ได้ ตรวจ interval overlap แบบ half-open ตามเวลาจริง รวมกับบันทึก exposures ไม่พึ่ง dataset ID อย่างเดียว

ช่วงที่เสนอใหม่แต่ยังไม่ได้รวบรวม/ตรวจข้อมูลต้องระบุ **UNAVAILABLE_UNVERIFIED** การไม่ทับ exposure ไม่ได้พิสูจน์ว่าข้อมูลมีอยู่ คุณภาพดี หรือพร้อมใช้ ทดสอบบน future data ไม่ได้ก่อนเวลาและก่อนอนุมัติแยก

## Bounds / recovery

- หนึ่ง foreground cycle ต่อคำสั่ง ไม่มีกำหนดเวลาอัตโนมัติ
- สูงสุดสาม tool-free model calls ต่อ cycle; reserve ก่อนเรียก และ failed calls ใช้ budget ด้วย
- สูงสุดสี่ discovery queries, สาม results/query และสิบสอง HTTP requests จริงต่อ cycle; จำกัดเวลา ขนาด response และ redirect
- Hermes role subprocess มี wall-clock timeout และ output bounds; ไม่ใช้ shell เพื่อรัน model-generated text
- ไม่เล่นซ้ำ model call หลัง crash อัตโนมัติ; cycle ค้างต้องถูกตรวจและ recover อย่างชัดเจน โดยเก็บประวัติและ budget เดิม
- SQLite/event hashes ช่วยตรวจการเปลี่ยนแปลงและ audit ไม่ใช่ OS sandbox หรือ cryptographic human authentication คนที่มีสิทธิ์ Windows user เดียวกันยังแก้โค้ด/ไฟล์ได้

## Windows commands

จาก project root:

```powershell
uv sync --project phase3 --python 3.12 --extra dev --locked
uv run --project phase3 --locked python -m lab3.cli --root . status
```

เมื่ออยู่ในขอบเขตที่มนุษย์อนุญาตให้ค้นคว้าหนึ่งรอบ:

```powershell
uv run --project phase3 --locked python -m lab3.cli --root . run
```

คำสั่งนี้ไม่ใช่การเปิด continuous service และไม่รัน market backtest ห้ามใช้ cron/loop เพื่อเรียกซ้ำก่อนอนุมัติ frequency และ budget

```powershell
uv run --project phase3 --extra dev --locked pytest phase3/tests -q -W error
uv run --project phase3 --extra dev --locked ruff check phase3/lab3 phase3/tests
uv run --project dashboard/backend --locked --no-sync python dashboard/verify_readonly.py
```

ใช้ `python -m lab3.cli --help` เพื่อดู manual source/proposal review และ recovery commands ที่ติดตั้งจริง ไม่มี execute/backtest/scheduler command

ตัวอย่าง syntax สำหรับมนุษย์ตรวจ source (ตัวพิมพ์ใหญ่ด้านล่างเป็น placeholders ไม่ใช่คำสั่งที่รันแล้ว):

```powershell
uv run --project phase3 --locked python -m lab3.cli --root . verify-source SOURCE_ID --url EXACT_HTTPS_URL --reviewer REVIEWER --reason REVIEW_REASON
uv run --project phase3 --locked python -m lab3.cli --root . approve-source SOURCE_ID --scope full-document --reviewer REVIEWER --reason REVIEW_REASON
```

ถ้ามี redirect ต้องระบุ exact target ด้วย `--redirect-url` อย่างชัดเจน ไม่อนุญาต redirect ไปที่อื่น ใช้เฉพาะ HTML/text ที่ extractor รองรับ; PDF/หน้า bot challenge/เอกสารไม่สัมพันธ์กับ DOI หรือ title ถูกปฏิเสธ ความสัมพันธ์ DOI/title เป็น heuristic และยังต้องให้คนตรวจ

Baseline manifest ใช้ canonical-content trust anchor เพื่อรองรับ LF/CRLF บนคนละเครื่อง แต่ยังตรวจ byte hash ของ original evidence ทั้ง 56 ไฟล์เหมือนเดิม ไม่แก้ original artifacts เพื่อให้ผ่าน

**ข้อเสนอต้นทุน Phase3 ไม่แก้ Batch001:** แผนใหม่ระบุ commission ต่อ notional ทั้งขาเข้า/ออก และแบ่ง spread ครึ่งหนึ่งแต่ละขา ส่วน Batch001 เดิมจำลอง spread รวมที่ entry; ทั้งสองเป็น scenario assumptions ไม่ใช่ต้นทุนบัญชีจริง และต้อง review implementation/อนุมัติแยกก่อนทดลองใหม่

## การยอมรับผล

การผ่าน critic หมายถึง **สมควรอยู่ในคิวเพื่อให้มนุษย์ตรวจ design** ไม่ใช่ผลทดลองสำเร็จ ความจริงสากล หรือกำไรที่ยืนยันแล้ว ผลสาธิตต้องอ้าง actual persisted cycle report, model responses และ event chain ไม่ใช้ synthetic tests แทนสิ่งที่ค้นพบจริง

ระบบต้องหยุดหลังรอบค้นคว้าที่ตรวจผ่านครั้งแรก และคง trading execution, credentials, futures, leverage และ scheduler เป็นปิดทั้งหมด
