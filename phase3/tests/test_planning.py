"""Deterministic planning tests; hypotheses are synthetic, never performance evidence."""
import copy
import importlib
import pytest


def api():
    return importlib.import_module('lab3.planning')


def hypothesis():
    return dict(id='synthetic-h1', family='momentum', title_th='ทดสอบ', hypothesis_th='สมมติฐาน',
                entry_logic='close above prior 24-bar high', exit_logic='close below prior 12-bar low',
                falsification='Fails matched cash after costs', parameters={'lookback':24}, source_ids=['s1'],
                scores=dict(evidence_quality=3, novelty=2, information_gain=4, complexity=2))


@pytest.mark.parametrize('plan,critic',[
    ({'id':'p','status':'RUNNING'}, {'verdict':'ACCEPT_AS_PROPOSAL','issues':[]}),
    ({'id':'p','status':'DESIGN_ONLY','gates':{'execution_enabled':True}}, {'verdict':'ACCEPT_AS_PROPOSAL','issues':[]}),
    ({'id':'p','status':'DESIGN_ONLY'}, {'verdict':'ACCEPT_AS_PROPOSAL','issues':[],'critical':True}),
])
def test_synthetic_approval_rejects_unsafe_design_or_critical_critic(tmp_path,plan,critic):
    from lab3.store import Store
    store = Store(tmp_path)
    store.put('queue',dict(id='synthetic-unsafe',status='PROPOSED',plan=plan,critic=critic))
    with pytest.raises(ValueError):
        api().transition_proposal(store,'synthetic-unsafe','APPROVED','human','reviewed')
    assert store.snapshot()['queue'][0]['status'] == 'PROPOSED'


def test_synthetic_human_design_only_approval_is_version_bound(tmp_path):
    from lab3.store import Store, digest
    p = api()
    store = Store(tmp_path)
    item = store.put('queue',dict(id='synthetic-q',status='PROPOSED',plan={'id':'synthetic-plan','status':'DESIGN_ONLY'},
                                  critic={'verdict':'ACCEPT_AS_PROPOSAL','issues':[]}))
    for actor,reason,target in [('model','why','APPROVED'),('human','','APPROVED'),('human','why','RUNNING'),('human','why','COMPLETED')]:
        with pytest.raises(ValueError):
            p.transition_proposal(store,item['id'],target,actor,reason)
    approved = p.transition_proposal(store,item['id'],'APPROVED','human','reviewed synthetic design')
    assert approved['status'] == 'APPROVED'
    assert approved['approval']['scope'] == 'DESIGN_ONLY'
    assert approved['approval']['proposal_hash'] == digest(item)
    assert approved['approval']['proposal_version'] == item['version']
    assert approved['approval']['plan_hash'] == digest(item['plan'])
    assert approved['execution_enabled'] is False
    assert approved['human_approved'] is True and approved['approval_scope'] == 'DESIGN_ONLY'
    rejected = p.transition_proposal(store,item['id'],'REJECTED','human','withdraw design')
    assert rejected['status'] == 'REJECTED'
    with pytest.raises(ValueError):
        p.transition_proposal(store,item['id'],'APPROVED','human','retry')
    for verdict,issues in [('REJECT',[]),('REVISE',[]),('ACCEPT_AS_PROPOSAL',['critical unsupported evidence'])]:
        store.put('queue',dict(id='synthetic-'+verdict+str(len(issues)),status='PROPOSED',plan={'id':'p'},critic=dict(verdict=verdict,issues=issues)))
        with pytest.raises(ValueError):
            p.transition_proposal(store,'synthetic-'+verdict+str(len(issues)),'APPROVED','human','reviewed')


def test_original_based_synthetic_hypothesis_plan_is_design_only():
    from pathlib import Path
    p = api()
    root = Path(__file__).resolve().parents[2]
    plan = p.make_plan(hypothesis(), root)
    assert plan == p.make_plan(hypothesis(), root)
    assert plan['data_status'] == 'UNAVAILABLE_UNVERIFIED'
    assert plan['engine_evaluations_consumed'] == 0
    assert not any(plan['gates'].values())
    assert plan['market'] == dict(symbol='BTCUSDT',market='spot',interval='1h',direction='long_only',leverage=1)
    assert plan['capital'] == dict(initial_cash=10000,position_fraction=0.1)
    assert plan['budget'] == dict(max_configs=2,max_evaluations=10,approved=False)
    assert plan['minimum_closed_trades'] == 30
    assert plan['insufficient_status'] == 'INSUFFICIENT'
    assert {x['name'] for x in plan['benchmarks']} == {'Cash','BH10','BH100'}
    assert set(plan['windows']) == {'development','validation','holdout'}
    for window in plan['windows'].values():
        assert p.assert_fresh_window(window['start'],window['end'],p.exposed_windows(root))
    assert set(plan['cost_sensitivity']['scopes']) == set(plan['windows'])
    assert plan['costs']['commission'] == .001 and plan['costs']['spread'] == .0005
    assert plan['cost_sensitivity']['commission'] == .002
    assert plan['cost_sensitivity']['spread'] == .001
    assert plan['holdout_tuning_allowed'] is False
    matched = [x for x in plan['benchmarks'] if x['name'] in ('Cash','BH10')]
    assert all(x['initial_cash'] == 10000 and x['position_fraction'] == .1 for x in matched)
    assert plan['budget_accounting']['maximum_planned_evaluations'] <= 10
    assert plan['budget_accounting']['validation_holdout_config_count'] == 1


def test_synthetic_copied_baseline_and_new_exposure_are_fail_closed(tmp_path):
    from pathlib import Path
    import json
    import shutil
    from lab3.store import Store, IntegrityError
    p = api()
    original = Path(__file__).resolve().parents[2]
    baseline_path = 'dashboard/qa/baseline-evidence.json'
    baseline = json.loads((original/baseline_path).read_text())
    for name in [baseline_path,*baseline]:
        target = tmp_path/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(original/name,target)
    # All corruption is applied to labelled synthetic scratch copies, never originals.
    store = Store(tmp_path)
    store.append('window_exposed',dict(start='2026-10-01T00:00:00Z',end='2027-01-01T00:00:00Z',id='new-uuid',hash='new-hash'))
    exposures = p.exposed_windows(tmp_path)
    assert any(w['origin'] == 'phase3' for w in exposures)
    with pytest.raises(ValueError):
        p.assert_fresh_window('2026-12-01T00:00:00Z','2027-02-01T00:00:00Z',exposures)
    assert p.make_plan(hypothesis(),tmp_path)['windows']['development']['start'] == '2027-01-01T00:00:00+00:00'
    manifest = next(name for name in baseline if name.startswith('data/') and name.endswith('/manifest.json'))
    (tmp_path/manifest).write_text('{"synthetic":"tampered"}')
    with pytest.raises(IntegrityError):
        p.exposed_windows(tmp_path)


def test_original_56_baseline_and_full_window_are_verified_read_only():
    from pathlib import Path
    import hashlib
    import json
    p = api()
    root = Path(__file__).resolve().parents[2]
    baseline = json.loads((root/'dashboard/qa/baseline-evidence.json').read_text())
    before = {name:(hashlib.sha256((root/name).read_bytes()).hexdigest(),(root/name).stat().st_mtime_ns) for name in baseline}
    assert len(before) == 56
    windows = p.exposed_windows(root)
    assert any(w['start'] == '2024-10-01T00:00:00+00:00' and w['end'] == '2026-10-01T00:00:00+00:00' for w in windows)
    assert any(w.get('origin') == 'original_holdout' for w in windows)
    after = {name:(hashlib.sha256((root/name).read_bytes()).hexdigest(),(root/name).stat().st_mtime_ns) for name in baseline}
    assert before == after
    assert {name:v[0] for name,v in after.items()} == baseline


def test_synthetic_half_open_freshness_ignores_identity():
    p = api()
    exposure = [dict(start='2026-01-01T00:00:00Z',end='2026-02-01T00:00:00Z',id='different',hash='different')]
    assert p.assert_fresh_window('2026-02-01T00:00:00Z','2026-03-01T00:00:00Z',exposure)
    for start,end in [('2026-01-10T00:00:00Z','2026-03-01T00:00:00Z'),
                      ('2026-02-01','2026-03-01'), ('2026-02-01T01:00:00+01:00','2026-03-01T00:00:00Z'),
                      ('2026-02-01T00:00:00Z','2026-02-01T00:00:00Z')]:
        with pytest.raises(ValueError):
            p.assert_fresh_window(start,end,exposure)


def test_synthetic_strict_schema_and_deterministic_heuristic():
    p = api()
    h = hypothesis()
    assert p.validate_hypothesis(h, {'s1'}) == h
    for key, value in [('family','arbitrary'), ('source_ids',[]), ('parameters',{'x':float('inf')}), ('title_th','')]:
        bad = dict(h, **{key:value})
        with pytest.raises(ValueError):
            p.validate_hypothesis(bad, {'s1'})
    bad = copy.deepcopy(h)
    bad['scores']['novelty'] = True
    with pytest.raises(ValueError):
        p.validate_hypothesis(bad, {'s1'})
    with pytest.raises(ValueError):
        p.validate_hypothesis(dict(h, code='import os'), {'s1'})
    ranked = p.rank_hypotheses([dict(h,id='z'), dict(h,id='a')])
    assert [x['id'] for x in ranked] == ['a','z']
    assert ranked[0]['score'] == 21
    assert 'heuristic' in ranked[0]['score_interpretation'].lower()
