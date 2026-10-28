"""Verify original research evidence remains unchanged. Read-only; no engine imports."""
import hashlib
import json
from pathlib import Path
import sqlite3


def verify_files(root, baseline):
    root = Path(root).resolve()
    changed = []
    for relative, expected in baseline.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('baseline path escapes project')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            changed.append(relative)
    return sorted(changed)


def main():
    root = Path(__file__).resolve().parent.parent
    baseline = json.loads((root / 'dashboard/qa/baseline-evidence.json').read_text('utf-8'))
    changed = verify_files(root, baseline)
    db = sqlite3.connect((root / 'storage/lab.sqlite').as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('PRAGMA query_only=ON')
        kinds = dict(db.execute('SELECT kind, COUNT(*) FROM events GROUP BY kind').fetchall())
        last = db.execute("SELECT payload FROM events WHERE kind='batch_execution_completed' "
                          'ORDER BY id DESC LIMIT 1').fetchone()
        batch = json.loads(last[0]) if last else {}
        expected = (kinds.get('run_reserved') == 4 and kinds.get('experiment_completed') == 4
                    and batch.get('engine_evaluations') == 20
                    and batch.get('status') == 'HALTED_AWAITING_HUMAN_RESULTS_REVIEW')
        result = {'protected_files': len(baseline), 'changed_files': changed,
                  'registry_events': sum(kinds.values()), 'reservations': kinds.get('run_reserved', 0),
                  'completed_experiments': kinds.get('experiment_completed', 0),
                  'engine_evaluations': batch.get('engine_evaluations'), 'batch_status': batch.get('status'),
                  'passed': not changed and expected}
    finally:
        db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
