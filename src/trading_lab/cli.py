"""Explicit foreground commands only. No scheduler, account API, live or paper command."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from .governance import code_hash, holdout_fingerprint, load_policy, make_spec, parameter_grid, policy_hash
from .registry import Registry, canonical


def _identifier(value):
    if not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('expected a full SHA256 identifier, not a path')
    return value


def validate_review(review, current_hash):
    """Validate explicit clean review evidence; this never grants human approval."""
    if not isinstance(review, dict):
        raise ValueError('independent review must be a JSON object')
    digest = review.get('code_hash')
    if (review.get('passed') is not True or not isinstance(digest, str)
            or not re.fullmatch('[a-f0-9]{64}', digest) or digest != current_hash):
        raise ValueError('passed independent review with matching full code SHA256 required')
    reviewer = review.get('reviewer')
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('independent review requires a nonempty reviewer string')
    for field in ('security_concerns', 'logic_errors'):
        if type(review.get(field)) is not list or review[field]:
            raise ValueError(f'independent review requires explicit empty {field} list')
    if 'review_id' in review:
        if not isinstance(review['review_id'], str) or not review['review_id'].strip():
            raise ValueError('review_id must be a nonempty string when supplied')


def _dataset_identifier(value):
    if not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('expected a 32-character dataset UUID, not a path')
    return value


def _timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return int(result.timestamp() * 1000)


def _spec(root, spec_id):
    return json.loads((root / 'governance/specs' / (_identifier(spec_id) + '.json')).read_text('utf-8'))


def _model(registry, args):
    from .models import HermesModel
    return HermesModel(registry, provider=args.provider, model=args.model)


def main(argv=None):
    parser = argparse.ArgumentParser(description='PAPER-ONLY bounded autonomous research lab')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    ingest = sub.add_parser('ingest')
    ingest.add_argument('--start', required=True, help='ISO date/time, UTC if no timezone')
    ingest.add_argument('--end', required=True)
    research = sub.add_parser('research')
    research.add_argument('--cycles', type=int, default=1)
    research.add_argument('--provider', default='openai-codex')
    research.add_argument('--model', default='gpt-6.1-sol')
    spec = sub.add_parser('spec')
    spec.add_argument('--dataset', required=True)
    spec.add_argument('--fast', default='10,20')
    spec.add_argument('--slow', default='50,100')
    spec.add_argument('--budget', type=int, default=4)
    spec.add_argument('--commission', type=float, default=0.001)
    spec.add_argument('--spread', type=float, default=0.0005)
    approval = sub.add_parser('approve')
    approval.add_argument('--spec', required=True)
    approval.add_argument('--review', type=Path, required=True)
    run = sub.add_parser('experiment')
    run.add_argument('--spec', required=True)
    run.add_argument('--provider', default='openai-codex')
    run.add_argument('--model', default='gpt-6.1-sol')
    revoke = sub.add_parser('revoke')
    revoke.add_argument('--spec', required=True)
    sub.add_parser('report')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        policy = load_policy(root)
        registry = Registry(root / 'storage/lab.sqlite')
        registry.verify()
        if args.command == 'status':
            result = {'mode': policy['mode'], 'live_orders': False, 'credentials_needed': False,
                      'continuous_paper_enabled': False, 'scheduler_enabled': False,
                      'events': registry.verify(), 'knowledge_cards': len(registry.events('knowledge_card')),
                      'approvals': len(registry.events('approval')),
                      'experiments': len(registry.events('experiment_completed')),
                      'policy_hash': policy_hash(policy),
                      'isolation': 'trusted built-in subprocess only; NOT hostile-code OS sandbox'}
        elif args.command == 'ingest':
            from .data import download_snapshot
            result = download_snapshot(root / 'data', start_ms=_timestamp(args.start), end_ms=_timestamp(args.end))
            registry.append('dataset_ingested', result)
        elif args.command == 'research':
            from .research import KnowledgeLoop
            result = KnowledgeLoop(root, registry, _model(registry, args), policy).run(args.cycles)
        elif args.command == 'spec':
            from .data import load_snapshot
            frame, manifest = load_snapshot(root / 'data', _dataset_identifier(args.dataset))
            parameters = parameter_grid([int(x) for x in args.fast.split(',')],
                                        [int(x) for x in args.slow.split(',')])
            result = make_spec(manifest['dataset_sha256'], code_hash(root), policy, parameters, args.budget,
                               args.commission, args.spread, args.dataset, holdout_fingerprint(frame),
                               [frame.index[-((len(frame) - len(frame) // 2) // 3)].isoformat(),
                                frame.index[-1].isoformat()],
                               data_window=[frame.index[0].isoformat(), frame.index[-1].isoformat()])
            path = root / 'governance/specs' / (result['spec_id'] + '.json')
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                with path.open('x', encoding='utf-8') as handle:
                    handle.write(canonical(result))
                registry.append('experiment_spec_proposed', result)
            result = {**result, 'status': 'PENDING_HUMAN_APPROVAL', 'executed': False}
        elif args.command == 'approve':
            if not sys.stdin.isatty():
                raise PermissionError('approval requires an interactive HUMAN terminal; agents must not approve')
            specification = _spec(root, args.spec)
            current_hash = code_hash(root)
            review = json.loads(args.review.read_text('utf-8'))
            validate_review(review, current_hash)
            if (specification['code_hash'] != current_hash
                    or specification['policy_hash'] != policy_hash(policy)):
                raise PermissionError('matching passed independent code review and unchanged policy required')
            print(canonical(specification))
            print('WARNING: trusted built-in PROCESS isolation only, not an OS sandbox. '
                  'No generated executable code is accepted. This approves BACKTEST only, not continuous paper.')
            challenge = f"APPROVE BACKTEST {args.spec}"
            if input(f'Type exactly: {challenge}\n') != challenge:
                raise PermissionError('approval cancelled')
            result = {'spec_id': args.spec, 'policy_hash': policy_hash(policy), 'code_hash': current_hash,
                      'review_id': review.get('review_id', str(args.review)),
                      'isolation': 'trusted_builtin_process', 'human': 'interactive owner confirmation'}
            registry.append('approval', result)
        elif args.command == 'experiment':
            from .runner import ExperimentLoop
            specification = _spec(root, args.spec)
            result = ExperimentLoop(root, registry, policy, _model(registry, args)).run(specification)
        elif args.command == 'revoke':
            result = {'spec_id': _identifier(args.spec), 'reason': 'owner stop request'}
            registry.append('revocation', result)
        else:
            from .reporting import render_report
            result = {'report': str(render_report(root, registry))}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if args.command in ('research', 'experiment') and result.get('failed') else 0
    except (ValueError, PermissionError, RuntimeError, OSError, KeyError) as error:
        print(json.dumps({'error': str(error), 'command': args.command, 'failed_closed': True},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
