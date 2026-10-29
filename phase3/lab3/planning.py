"""Declarative deterministic research design; never imports or runs an engine."""
from datetime import datetime, timedelta, timezone
import math
import re
import hashlib
import json
import sqlite3
from pathlib import Path
from contextlib import closing
from .store import Store, IntegrityError, canonical, digest

FAMILIES = ('trend_following', 'momentum', 'mean_reversion', 'volatility')
SCORES = ('evidence_quality', 'novelty', 'information_gain', 'complexity')


def validate_hypothesis(item, source_ids):
    fields = {'id','family','title_th','hypothesis_th','entry_logic','exit_logic','falsification','parameters','source_ids','scores'}
    if not isinstance(item, dict) or set(item) != fields:
        raise ValueError('Exact hypothesis schema required')
    for field in fields - {'parameters','source_ids','scores'}:
        if not isinstance(item[field], str) or not item[field].strip() or len(item[field]) > 10000:
            raise ValueError('Nonblank bounded declarative text required')
    if item['family'] not in FAMILIES:
        raise ValueError('Unsupported family')
    ids = item['source_ids']
    if not isinstance(ids, list) or not ids or any(not isinstance(i,str) or i not in source_ids for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Nonempty unique known source_ids required')
    scores = item['scores']
    if not isinstance(scores, dict) or set(scores) != set(SCORES) or any(type(v) is not int or not 1 <= v <= 5 for v in scores.values()):
        raise ValueError('Exact integer scores 1..5 required')
    parameters = item['parameters']
    if not isinstance(parameters, dict) or len(parameters) > 32:
        raise ValueError('Bounded declarative parameter dictionary required')
    for key, value in parameters.items():
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', key):
            raise ValueError('Declarative parameter name required')
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1000000:
            raise ValueError('Finite bounded numeric parameter required')
    canonical(item)
    return item


def _utc(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)', value):
        raise ValueError('Strict aware UTC ISO timestamp required')
    return datetime.fromisoformat(value.replace('Z','+00:00'))


def assert_fresh_window(start, end, exposures):
    a, b = _utc(start), _utc(end)
    if b <= a:
        raise ValueError('Window end must exceed start')
    for exposure in exposures:
        x, y = _utc(exposure['start']), _utc(exposure['end'])
        if y <= x:
            raise ValueError('Invalid exposure window')
        if a < y and x < b:
            raise ValueError('Window overlaps previously exposed data, regardless of hash or UUID')
    return True


# Pinned once from the original 56-entry manifest using store.digest, not its
# checkout-dependent JSON whitespace or line endings. Never learn this at load.
BASELINE_CANONICAL_SHA256 = '5be7be8acf2c7bc348b2ac2c722614ffca6a97312f759407ea55023388c65e5c'


def _original_baseline_manifest(root):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise IntegrityError('Duplicate baseline manifest key: ' + key)
            result[key] = value
        return result

    baseline = json.loads((root / 'dashboard/qa/baseline-evidence.json').read_bytes(),
                          object_pairs_hook=unique_object)
    if not isinstance(baseline, dict) or len(baseline) != 56:
        raise IntegrityError('Expected original 56 protected files')
    for name, expected in baseline.items():
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', name)
                or any(part in ('.', '..') for part in name.split('/'))):
            raise IntegrityError('Strict root-relative baseline path required')
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise IntegrityError('Lowercase SHA256 baseline hash required')
    if digest(baseline) != BASELINE_CANONICAL_SHA256:
        raise IntegrityError('Baseline trust anchor changed')
    return baseline


def verify_original_baseline(root):
    """Read-only verification of the pinned manifest and all protected bytes."""
    root = Path(root).resolve()
    try:
        baseline = _original_baseline_manifest(root)
        for name, expected in baseline.items():
            path = (root / name).resolve()
            if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise IntegrityError('Protected baseline changed: ' + name)
        return dict(verified=True, file_count=len(baseline), manifest_sha256=digest(baseline))
    except (OSError, TypeError, ValueError) as exc:
        raise IntegrityError(str(exc)) from exc


def exposed_windows(root):
    root = Path(root).resolve()
    try:
        verify_original_baseline(root)
        baseline = _original_baseline_manifest(root)
        windows = []
        for name in baseline:
            if name.startswith('data/') and name.endswith('/manifest.json'):
                manifest = json.loads((root / name).read_bytes())
                start = datetime.fromtimestamp(manifest['start_ms']/1000, timezone.utc).isoformat()
                end = datetime.fromtimestamp(manifest['end_ms']/1000, timezone.utc).isoformat()
                assert_fresh_window(start, end, [])
                windows.append(dict(start=start, end=end, origin='original_dataset', dataset_id=manifest['dataset_id']))
        original = root / 'storage/lab.sqlite'
        with closing(sqlite3.connect(original.as_uri() + '?mode=ro', uri=True)) as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            records = [(kind,json.loads(payload)) for kind,payload in db.execute('SELECT kind,payload FROM events ORDER BY id')]
        # The original exposure windows end at the last included hourly candle;
        # convert those inclusive original endpoints to half-open candle windows.
        for kind,payload in records:
            if kind == 'holdout_exposed':
                for key,origin in (('data_window','original_data_exposure'),('holdout_window','original_holdout')):
                    start,end = payload[key]
                    end = (_utc(end) + timedelta(hours=1)).isoformat()
                    assert_fresh_window(start,end,[])
                    windows.append(dict(start=start,end=end,origin=origin))
        phase_path = root / 'phase3/state/lab.sqlite'
        if phase_path.exists():
            with closing(sqlite3.connect(phase_path.as_uri() + '?mode=ro',uri=True)) as db:
                db.execute('PRAGMA query_only=ON')
                db.execute('BEGIN')
                events = Store._events(db)
                Store._project(events)
            for event in events:
                if event['kind'] in ('exposure', 'window_exposed', 'data_exposed', 'holdout_exposed', 'data_window_exposed'):
                    payload = event['payload']
                    found = False
                    for key in ('data_window','holdout_window','window'):
                        if key in payload:
                            start,end = payload[key]
                            assert_fresh_window(start,end,[])
                            windows.append(dict(start=start,end=end,origin='phase3',event_hash=event['hash']))
                            found = True
                    if 'start' in payload and 'end' in payload:
                        start,end = payload['start'],payload['end']
                        assert_fresh_window(start,end,[])
                        windows.append(dict(start=start,end=end,origin='phase3',event_hash=event['hash']))
                        found = True
                    if not found:
                        raise IntegrityError('Exposure event missing window')
        if not windows:
            raise IntegrityError('Original dataset exposure missing')
        return windows
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        raise IntegrityError(str(exc)) from exc


def make_plan(hypothesis, root):
    raw = {k:v for k,v in hypothesis.items() if k not in ('version','previous_version_hash','score','score_interpretation')}
    validate_hypothesis(raw, raw.get('source_ids', []))
    exposures = exposed_windows(root)
    cursor = max(_utc(w['end']) for w in exposures)
    # Fixed durations and anchoring, not a search for profitable dates. The
    # proposed timestamps make no assertion about data availability.
    windows = {}
    for scope,days in (('development',180),('validation',90),('holdout',90)):
        end = cursor + timedelta(days=days)
        window = dict(start=cursor.isoformat(),end=end.isoformat())
        assert_fresh_window(window['start'],window['end'],exposures + list(windows.values()))
        windows[scope] = window
        cursor = end
    return dict(
        id='plan-' + digest(hypothesis), hypothesis_id=hypothesis['id'], hypothesis_hash=digest(hypothesis),
        hypothesis_version=hypothesis.get('version'), status='DESIGN_ONLY',
        market=dict(symbol='BTCUSDT',market='spot',interval='1h',direction='long_only',leverage=1),
        capital=dict(initial_cash=10000,position_fraction=0.1),
        metrics=['return','annualized_return','maximum_drawdown','Sharpe','win_rate','closed_trade_count'],
        benchmarks=[dict(name='Cash',initial_cash=10000,position_fraction=0.1,invested_fraction=0.0,context_only=False),
                    dict(name='BH10',initial_cash=10000,position_fraction=0.1,context_only=False),
                    dict(name='BH100',initial_cash=10000,position_fraction=1.0,context_only=True)],
        costs=dict(commission=0.001,spread=0.0005,kind='scenario_not_verified_exchange_costs',
                   application='commission per traded notional each side; half spread each side'),
        cost_sensitivity=dict(commission=0.002,spread=0.001,scopes=list(windows)),
        windows=windows, split_method='Fixed chronological 180/90/90 UTC days after known exposure end',
        method=dict(signal_timing='Closed bar only; trade next bar open, no same-bar future data',
                    warmup='1000 closed hourly bars within each split excluded from scoring; insufficient bars fail closed',
                    parameters='Freeze declarative rules and at most two configurations before validation; no executable code',
                    selection='Development only; validation reports frozen configurations; holdout once after human review'),
        holdout_tuning_allowed=False, minimum_closed_trades=30,insufficient_status='INSUFFICIENT',
        data_status='UNAVAILABLE_UNVERIFIED',
        freshness_note='Absence of known exposure is not data availability, quality validation, or a future-data claim',
        gates=dict(execution_enabled=False,scheduler_enabled=False,credentials_enabled=False,
                   data_verified=False,human_execution_approved=False,engine_supported=False),
        engine_evaluations_consumed=0,
        budget_accounting=dict(development_configs=2,validation_holdout_config_count=1,
                               maximum_planned_evaluations=8,
                               calculation='2 development configs x 2 costs + 1 frozen config x 2 later splits x 2 costs',
                               benchmarks='Computed alongside each planned evaluation; never additional strategy searches'),
        budget=dict(max_configs=2,max_evaluations=10,approved=False))


def transition_proposal(store, id, target, actor, reason):
    if actor != 'human' or not isinstance(reason,str) or not reason.strip():
        raise ValueError('Human actor and nonblank reason required')
    if target not in ('APPROVED','REJECTED'):
        raise ValueError('RUNNING/COMPLETED execution transitions disabled in Phase3')
    with store._write() as db:
        item = next((i for i in store._project(store._events(db))['queue'] if i['id'] == id), None)
        if item is None:
            raise ValueError('Unknown proposal')
        if (item.get('status'),target) not in (('PROPOSED','APPROVED'),('PROPOSED','REJECTED'),('APPROVED','REJECTED')):
            raise ValueError('Forbidden proposal transition')
        updated: dict = dict(item, status=target,execution_enabled=False,
                       human_approved=target == 'APPROVED',approval_scope='DESIGN_ONLY')
        if target == 'APPROVED':
            critic = item.get('critic')
            allowed_critic = {'verdict','issues','lessons_th','next_questions'}
            if not isinstance(critic,dict) or set(critic) - allowed_critic or critic.get('verdict') != 'ACCEPT_AS_PROPOSAL' or critic.get('issues') != []:
                raise ValueError('Critical, rejected, missing or revision-needed critic blocks approval')
            plan = item.get('plan')
            if not isinstance(plan,dict) or not plan or plan.get('status') != 'DESIGN_ONLY':
                raise ValueError('Immutable DESIGN_ONLY plan required')
            if not isinstance(plan.get('gates',{}),dict) or any(value is not False for value in plan.get('gates',{}).values()):
                raise ValueError('All plan execution gates must remain false')
            plan_hash = digest(plan)
            if 'plan_hash' in item and item['plan_hash'] != plan_hash:
                raise ValueError('Proposal plan hash mismatch')
            updated['approval'] = dict(actor=actor,reason=reason,scope='DESIGN_ONLY',
                                       proposal_hash=digest(item),proposal_version=item['version'],plan_hash=plan_hash)
        history = list(item.get('review_history',[]))
        history.append(dict(actor=actor,reason=reason,target=target,proposal_hash=digest(item)))
        updated['review_history'] = history
        return store._put(db,'queue',updated)


def rank_hypotheses(items):
    result = []
    for item in items:
        raw = {k:v for k,v in item.items() if k not in ('version','previous_version_hash')}
        validate_hypothesis(raw, raw.get('source_ids', []))
        s = item['scores']
        score = 3*s['evidence_quality'] + 2*s['novelty'] + 3*s['information_gain'] - 2*s['complexity']
        result.append(dict(item, score=score, score_interpretation='Heuristic research priority; not expected profits or calculated mutual information'))
    return sorted(result, key=lambda i: (-i['score'], i['id']))
