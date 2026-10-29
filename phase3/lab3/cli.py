"""Local human CLI. Approval is design/metadata review, never execution authority."""
import argparse
import json
from pathlib import Path
import sys
from .store import Store
from .sources import approve_source, verify_source
from .planning import transition_proposal
from .research import run_cycle


def parser():
    result = argparse.ArgumentParser(description='Phase3: one foreground research cycle; no execution or scheduler')
    result.add_argument('--root', required=True, type=Path)
    subs = result.add_subparsers(dest='command', required=True)
    for command in ('run', 'status'):
        subs.add_parser(command)
    recover = subs.add_parser('recover', help='Mark an abandoned active cycle INTERRUPTED, never replay calls')
    recover.add_argument('--reason', required=True)
    for command in ('verify-source', 'approve-source', 'approve-proposal', 'reject-proposal'):
        p = subs.add_parser(command, help='Human local review only; same-OS-user authority is not authentication')
        p.add_argument('id')
        p.add_argument('--reviewer', required=True)
        p.add_argument('--reason', required=True)
        if command == 'verify-source':
            p.add_argument('--url', required=True, help='Exact HTTPS document URL; explicit human retrieval only')
            p.add_argument('--redirect-url', action='append', default=[], help='Explicit exact HTTPS redirect target (max3)')
        elif command == 'approve-source':
            p.add_argument('--scope', choices=('metadata-only', 'full-document'), default='metadata-only')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'status':
            result = Store.read_snapshot(args.root)
        elif args.command == 'run':
            result = run_cycle(args.root)
        elif args.command == 'recover':
            if not args.reason.strip():
                raise ValueError('nonblank recovery reason required')
            snap = Store.read_snapshot(args.root)
            active = [c for c in snap['cycles'] if c.get('status') == 'RUNNING']
            if len(active) != 1:
                raise ValueError('exactly one abandoned active cycle required')
            store = Store(args.root)
            result = store.finish_cycle(active[0]['id'], 'INTERRUPTED',
                                        {'human_recovery_reason': args.reason, 'automatic_replay': False})
        else:
            if not args.reviewer.strip() or not args.reason.strip():
                raise ValueError('human reviewer and nonblank rationale required')
            store = Store(args.root)
            if args.command == 'verify-source':
                result = verify_source(store, args.id, url=args.url, redirect_urls=args.redirect_url,
                                       actor='human', reviewer=args.reviewer, reason=args.reason)
            elif args.command == 'approve-source':
                result = approve_source(store, args.id, actor='human', reviewer=args.reviewer, reason=args.reason,
                                        scope=args.scope)
            else:
                target = 'APPROVED' if args.command == 'approve-proposal' else 'REJECTED'
                transition_proposal(store, args.id, target, actor='human',
                                    reason=args.reviewer + ': ' + args.reason)
                result = next(q for q in store.snapshot()['queue'] if q['id'] == args.id)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({'error_type': type(exc).__name__, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
