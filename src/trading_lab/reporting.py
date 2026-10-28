"""Read-only projections of real audit records; never fabricate returns or source citations."""
from datetime import datetime, timezone
import html
from pathlib import Path


def _text(value):
    return html.escape(str(value)).replace('::', '∶∶')


def render_report(root, registry):
    total = registry.verify()
    cards = [event['payload'] for event in registry.events('knowledge_card')]
    experiments = [event['payload'] for event in registry.events('experiment_completed')]
    if experiments:
        from .runner import verify_result_artifact
        for experiment in experiments:
            verify_result_artifact(root, experiment)
    datasets = [event['payload'] for event in registry.events('dataset_ingested')]
    addressed = {event['payload']['gap_id'] for event in registry.events('knowledge_addressed')}
    gaps = [event['payload'] for event in registry.events('knowledge_gap')
            if event['payload']['gap_id'] not in addressed]
    lines = ['# Trading Research Lab — รายงานจากข้อมูลจริงของระบบ', '',
             '**BACKTEST / PAPER = SIMULATED เท่านั้น ไม่ใช่ verified real profit**', '',
             f'- Audit events ที่ตรวจ hash chain ผ่าน: {total}',
             f'- Knowledge cards: {len(cards)}', f'- Dataset snapshots: {len(datasets)}',
             f'- Completed experiments: {len(experiments)}', f'- Open knowledge gaps: {len(gaps)}',
             '- Live trading: ไม่มี module / ไม่รับ credentials',
             '- Scheduler และ continuous paper trading: ปิด', '', '## สิ่งที่เรียนรู้', '']
    if not cards:
        lines.append('ยังไม่มี knowledge card ที่ผ่าน evidence checks และ independent model review')
    for item in cards:
        card = item['card']
        lines += [f"### {_text(card['topic'])} — version {item['version']}", '',
                  f"ชนิด: `{card['kind']}` — ไม่ใช่ FACT ที่ยืนยันทั่วไป", '',
                  '> ' + _text(card['explanation_th']).replace('\n', '\n> '), '',
                  '**สิ่งที่ยังไม่แน่ใจ**']
        lines += ['- ' + _text(value) for value in card['uncertainties_th']]
        lines += ['', '**แหล่งข้อมูลที่ดึงจริง**']
        for source in item['sources']:
            lines.append(f"- {_text(source['url'])} — retrieved {_text(source['retrieved_at'])}; "
                         f"snapshot `{source['source_id']}`")
        lines += ['', f"Card ID: `{item['card_id']}`", '']
    lines += ['## คำถามวิจัยรอบถัดไป', '']
    lines += ['- ' + _text(gap['topic']) for gap in gaps]
    lines += ['', '## Experiments — SIMULATED', '']
    if not experiments:
        lines += ['ยังไม่มีการรัน strategy experiment บนข้อมูลตลาดที่ได้รับอนุมัติ',
                  'Synthetic unit tests เป็นการทดสอบ software ไม่ใช่หลักฐานกำไรของกลยุทธ์']
    for experiment in experiments:
        lines += [f"### Run `{experiment['run_id']}`", '',
                  f"Parameters: `{experiment['parameters']}`", f"Metrics: `{experiment['metrics']}`", '',
                  f"Verdict: `{experiment['verdict']['verdict']}` — ไม่อนุมัติ paper อัตโนมัติ", '']
    lessons = registry.events('experiment_lesson')
    if lessons:
        lines += ['## บทเรียนจากการทดลอง', '']
        for lesson in lessons:
            critique = lesson['payload']['critique']
            lines += ['- ' + _text(value) for value in critique.get('lessons_th', [])]
    lines += ['', '## ขอบเขตและข้อจำกัด', '',
              '- Research จำกัดแหล่ง primary sources ใน reviewed catalog; ยังไม่ใช่ unrestricted web discovery',
              '- Quote presence + independent model review ตรวจ provenance/support ไม่ได้พิสูจน์ universal truth',
              '- Strategy code ใหม่และ batch ใหม่ต้อง review/approve ก่อนรัน',
              '- Process isolation สำหรับ trusted built-in เท่านั้น ไม่ใช่ OS sandbox สำหรับโค้ดไม่ไว้วางใจ',
              '- SQLite triggers/hash chain ตรวจการเปลี่ยนแปลงได้ แต่ไม่ป้องกันผู้มีสิทธิ์ user เดียวกันแก้ฐานข้อมูล',
              '- Transaction cost เป็นสมมติฐาน scenario ไม่ใช่อัตราค่าธรรมเนียมบัญชี Binance ที่ตรวจยืนยัน', '']
    target = Path(root) / 'reports' / ('lab-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.md')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
    return target
