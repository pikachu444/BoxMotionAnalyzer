"""Frozen limited synthetic fitting and separate holdout, never physical certification."""
from copy import deepcopy
from pathlib import Path
import re
from numbers import Real

import numpy as np
from scipy.spatial.transform import Rotation

from src.utils.marker_profile_identity import envelope, digest
from .initial_conditions import (sealed, check, finite, validate_profile, validate_seed,
    configured, engine_from_config, reseal, save, validate_compiled)
from .contact_policy import event_policy, validate_policy, policy_approval
from .contact_evaluation import (metric, evaluate_contacts, validate_recording,
    save_document, load_recording, load_evaluation, STATUSES, EVENT_KINDS)


ENDPOINT_UNITS = dict(dt12_s='s', rebound_height_mm='mm', final_origin_x_mm='mm', final_rotation_deg='deg')
FAMILIES = dict(normal_damping=('solref', 1), sliding=('friction', 0),
                torsional=('friction', 1), rolling=('friction', 2))
PROTOCOL_FIELDS = {'version', 'source_identity', 'cases', 'policy', 'policy_sha256', 'policy_approval',
    'alignment', 'objective', 'search', 'numerical_approval', 'label_uncertainty_approval',
    'range_approval', 'missing_rule', 'aggregation', 'baseline', 'reference_kind','convergence_plan','observed_evaluation'}


def freeze_protocol(cases, *, family='normal_damping', candidates=(.1, .2, .4),
        version='pub09-synthetic-protocol-v2', missing_penalty=1000000., tie_tolerance=1e-12):
    policy = event_policy()
    value = sealed('EvaluationProtocol', version=version,
        source_identity=dict(kind='public_synthetic_protocol', identity=digest(cases)), cases=cases,
        policy=policy, policy_sha256=digest(policy), policy_approval=policy_approval(policy),
        alignment='one-t1-offset;chronological-designated-t2;no-per-event-warp',
        objective='sum-required-fit-weighted-squared-residuals;no-holdout-access',
        search=dict(family=family, candidates=list(candidates), bounds=[min(candidates),max(candidates)],
            budget=len(candidates)*sum(c['split']=='fit' for c in cases), stopping='all-candidates-fixed-budget',
            tie_tolerance=tie_tolerance), numerical_approval='proposed', label_uncertainty_approval='proposed',
        range_approval='proposed', missing_rule=dict(penalty=missing_penalty, required_missing_blocks_pass=True),
        aggregation='required-denominator;partial-never-whole-pass', baseline='none', reference_kind='synthetic-self-consistency',
        convergence_plan=dict(case_ids=[c['case_id'] for c in cases if c['split']=='fit'],
            timesteps_s=[.002,.001,.0005],iterations=[10,100],approval='proposed'),
        observed_evaluation=dict(case_ids=[c['case_id'] for c in cases if c['split']=='holdout'],
            required_endpoints=['t1','t2'],modality='production-observed-Raw',acceptance='needs_review'))
    return validate_protocol(value)


def validate_protocol(value):
    check(value, 'EvaluationProtocol', PROTOCOL_FIELDS)
    if (not isinstance(value['version'],str) or not value['version'].strip()
            or value['source_identity']!={'kind':'public_synthetic_protocol','identity':digest(value['cases'])}
            or validate_policy(value['policy'])!=value['policy_sha256']
            or value['policy_approval']!=policy_approval(value['policy'])
            or value['alignment']!='one-t1-offset;chronological-designated-t2;no-per-event-warp'
            or value['objective']!='sum-required-fit-weighted-squared-residuals;no-holdout-access'
            or value['numerical_approval']!='proposed' or value['label_uncertainty_approval']!='proposed'
            or value['range_approval']!='proposed' or value['baseline']!='none'
            or value['reference_kind']!='synthetic-self-consistency'
            or value['aggregation']!='required-denominator;partial-never-whole-pass'):
        raise ValueError('Unsupported protocol semantics or unapproved promotion.')
    cases = value['cases']
    if not isinstance(cases,list) or not cases:raise ValueError('Required cases cannot be empty.')
    case_ids=set();ref_ids=set();groups={};motions={}
    from .mode_profiles import require_executable
    for c in cases:
        if (not isinstance(c,dict) or set(c)!={'case_id','motion_group','split','configuration','window_s',
                'eligible_endpoints','required_endpoints','reference_identity','endpoint_rules'}
                or c['split'] not in ('fit','holdout') or not isinstance(c['case_id'],str) or not c['case_id']
                or not isinstance(c['motion_group'],str) or not c['motion_group']):
            raise ValueError('Unsupported required case fields/split.')
        require_executable(c['configuration'])
        if c['configuration']['mode']!='single_drop' or 'initial_condition' not in c['configuration']:
            raise ValueError('Calibration case needs an explicit single-drop seed.')
        seed=validate_seed(c['configuration']['initial_condition'])
        if c['case_id'] in case_ids:raise ValueError('Duplicate required case.')
        case_ids.add(c['case_id'])
        if c['reference_identity'] is not None:
            r=c['reference_identity']
            if (not isinstance(r,dict) or set(r)!={'reference_id','content_hash'} or not r['reference_id']
                    or not isinstance(r['reference_id'],str) or r['reference_id'] in ref_ids):
                raise ValueError('Invalid/duplicate reference identity.')
            _hash(r['content_hash'])
            ref_ids.add(r['reference_id'])
        group=c['motion_group'];motion=(seed['source']['kind'],seed['source']['motion_id'])
        if group in groups and groups[group]!=c['split']:raise ValueError('Same motion_group in fit and holdout.')
        if motion in motions and motions[motion]!=group:raise ValueError('Variants of the same source motion must share a motion_group.')
        groups[group]=c['split'];motions[motion]=group
        window=finite(c['window_s'],(2,),'evaluation window')
        if window[0]!=0 or not window[1]>0 or window[1]>c['configuration']['duration_s']:
            raise ValueError('Supported diagnostic windows begin at seed and end within duration.')
        eligible=c['eligible_endpoints'];required=c['required_endpoints'];rules=c['endpoint_rules']
        if (not isinstance(eligible,list) or not eligible or len(set(eligible))!=len(eligible)
                or any(k not in ENDPOINT_UNITS for k in eligible) or not isinstance(required,list) or not required
                or len(set(required))!=len(required) or not set(required)<=set(eligible) or set(rules)!=set(eligible)):
            raise ValueError('Required/eligible endpoint set is invalid.')
        for endpoint,rule in rules.items():
            if (not isinstance(rule,dict) or set(rule)!={'units','scale','weight','tolerance','label_uncertainty','modality'}
                    or rule['units']!=ENDPOINT_UNITS[endpoint] or rule['modality']!='actual-contact-recording'):
                raise ValueError('Unsupported endpoint rules/units/modality.')
            for key in ('scale','weight','tolerance','label_uncertainty'):
                x=finite(rule[key],(),key)
                if x<0 or key in ('scale','weight') and x<=0:raise ValueError('Invalid objective scale/weight/tolerance.')
    if set(groups.values())!={'fit','holdout'}:raise ValueError('Both independent fit and holdout motions are required.')
    plan=value['convergence_plan']
    if plan!=dict(case_ids=[c['case_id'] for c in cases if c['split']=='fit'],timesteps_s=[.002,.001,.0005],iterations=[10,100],approval='proposed'):
        raise ValueError('Unsupported frozen convergence plan; create a new implementation/protocol version.')
    if value['observed_evaluation']!=dict(case_ids=[c['case_id'] for c in cases if c['split']=='holdout'],
            required_endpoints=['t1','t2'],modality='production-observed-Raw',acceptance='needs_review'):
        raise ValueError('Unsupported frozen observed endpoint population.')
    s=value['search']
    if (not isinstance(s,dict) or set(s)!={'family','candidates','bounds','budget','stopping','tie_tolerance'}
            or s['family'] not in FAMILIES or s['stopping']!='all-candidates-fixed-budget'
            or not isinstance(s['candidates'],list) or not s['candidates'] or len(s['candidates'])>30
            or len(set(s['candidates']))!=len(s['candidates'])
            or s['bounds']!=[min(s['candidates']),max(s['candidates'])]
            or type(s['budget']) is not int or s['budget']!=len(s['candidates'])*sum(c['split']=='fit' for c in cases)):
        raise ValueError('Invalid fixed single-family search/budget.')
    for x in s['candidates']:
        if finite(x,(),'candidate')<0 or s['family']=='normal_damping' and x<=0:raise ValueError('Invalid candidate.')
    if finite(s['tie_tolerance'],(),'tie tolerance')<0:raise ValueError('Invalid ambiguity rule.')
    m=value['missing_rule']
    if not isinstance(m,dict) or set(m)!={'penalty','required_missing_blocks_pass'} or m['required_missing_blocks_pass'] is not True or finite(m['penalty'],(),'missing penalty')<=0:
        raise ValueError('Required missing endpoints cannot be zero/pass.')
    return value


def approach_identity(config, profile):
    """Contact fitting cannot compensate for altered seed, mass, COM or inertia."""
    return digest(dict(seed=config['initial_condition'],size_mm=config['size_mm'],
        mass_kg=profile['mass_kg'],com_offset_mm=profile['com_offset_mm'],inertia=profile['inertia']))


def extract_endpoints(recording, evaluation, eligible, window):
    validate_recording(recording)
    result={}
    rows=[r for r in recording['samples'] if window[0]<=r['time_s']<=window[1]+1e-12]
    complete=bool(rows) and recording['execution_status'] not in ('partial','cancelled','time_limit','failure') and rows[-1]['time_s']>=window[1]-1e-10
    for key in eligible:
        if not complete:result[key]=metric(None,'unavailable','Evaluation window was not completed.');continue
        if key in ('dt12_s','rebound_height_mm'):
            bad=next((evaluation[k] for k in ('t1','t2') if evaluation[k]['status']!='valid'),None)
            if bad is not None:result[key]=metric(None,bad['status'],bad['reason']);continue
            t1=evaluation['t1']['value']['time_s'];t2=evaluation['t2']['value']['time_s']
            if key=='dt12_s':result[key]=metric(t2-t1,'valid')
            else:
                if evaluation['t2']['value']['kind']!='rebound_recontact':
                    result[key]=metric(None,'unavailable','Designated t2 is a new-feature impact, not a rebound recontact.')
                    continue
                interval=[r for r in rows if t1<=r['time_s']<=t2]
                if not interval:result[key]=metric(None,'unavailable','No actual samples in event interval.')
                else:result[key]=metric(max(r['com_mm'][2] for r in interval)-interval[0]['com_mm'][2],'valid')
        elif key=='final_origin_x_mm':result[key]=metric(rows[-1]['origin_mm'][0],'valid')
        elif key=='final_rotation_deg':
            angle=Rotation.from_matrix(np.asarray(rows[-1]['rotation'])@np.asarray(rows[0]['rotation']).T).magnitude()
            result[key]=metric(float(np.rad2deg(angle)),'valid')
        result[key]['units']=ENDPOINT_UNITS[key]
        result[key]['sample_time_s']=rows[-1]['time_s'] if key.startswith('final_') else None
    for key,m in result.items():
        m['units']=ENDPOINT_UNITS[key]
        m['sample_time_s']=rows[-1]['time_s'] if m['status']=='valid' and key.startswith('final_') else None
    return result


def run_case(case, profile, policy, *, output=None):
    """Fresh actual engine -> contacts -> event evaluation -> optional persisted reopen."""
    validate_profile(profile)
    config=configured(case['configuration'],case['configuration']['initial_condition'],profile)
    from src.utils.simulation_metadata import public_configuration
    source=dict(kind='actual_pub09_engine',case_id=case['case_id'],motion_group=case['motion_group'],geometry_mm=config['size_mm'],
        public_configuration_sha256=digest(public_configuration(config)),
        configuration_sha256=digest(config),profile_sha256=profile['content_hash'],seed_sha256=config['initial_condition']['content_hash'])
    engine=engine_from_config(config);engine.enable_contact_recording(source)
    dt=profile['solver']['timestep_s'];end=case['window_s'][1]
    count=int(round(end/dt))
    if abs(count*dt-end)>1e-10:raise ValueError('Window endpoint must be on actual integration clock; no resampling.')
    history=engine.record_samples(count+1,1)
    recording=engine.contact_recorder.document();validate_recording(recording,source)
    evaluation=evaluate_contacts(recording,policy,window=case['window_s'])
    endpoints=extract_endpoints(recording,evaluation,case['eligible_endpoints'],case['window_s'])
    result=sealed('CalibrationCaseResult',case_id=case['case_id'],motion_group=case['motion_group'],
        source_identity=source,configuration_sha256=digest(config),profile_sha256=profile['content_hash'],
        approach_sha256=approach_identity(config,profile),recording_sha256=digest(recording),
        evaluation_sha256=digest(evaluation),endpoints=endpoints,actual_end_s=recording['samples'][-1]['time_s'],
        event_brackets={k:evaluation[k]['value']['bracket_s'] if evaluation[k]['status']=='valid' else None for k in ('t1','t2')},
        event_status={k:evaluation[k]['status'] for k in ('t1','t2')},
        designated_events={k:{name:evaluation[k]['value'][name] for name in ('time_s','kind','bracket_s')}
            if evaluation[k]['status']=='valid' else None for k in ('t1','t2')},
        event_sequence=[{name:e[name] for name in ('event_id','kind','status','eligible','time_s','bracket_s','in_window','release_group_id')}
            for e in evaluation['events']],
        event_topology=[e['kind'] for e in evaluation['events']],compiled_profile=validate_compiled(engine),
        completion='completed',fresh=True,reused=False,calibration_status='uncalibrated')
    validate_case_result(result,case,profile)
    if output is not None:
        root=Path(output);root.mkdir(parents=True,exist_ok=False)
        save(root/'configuration.json',config);save(root/'result.json',result)
        save_document(root/'contacts.json',recording);save_document(root/'evaluation.json',evaluation)
        retained=load_recording(root/'contacts.json',source);load_evaluation(root/'evaluation.json',policy,retained)
    return result,engine,history,evaluation,recording,config


REFERENCE_FIELDS={'reference_id','case_id','motion_group','source_identity','approach_sha256',
    'endpoints','reference_kind','provenance','window_s'}


def reference_from_result(case, result, reference_id):
    """No ground-truth parameter vector or hidden profile reaches the fitter."""
    value=sealed('CalibrationReference',reference_id=reference_id,case_id=case['case_id'],motion_group=case['motion_group'],
        source_identity=dict(result_sha256=result['content_hash'],recording_sha256=result['recording_sha256']),
        approach_sha256=result['approach_sha256'],endpoints=result['endpoints'],reference_kind='synthetic-self-consistency',
        provenance='same MuJoCo simulator; not independent measured calibration',window_s=case['window_s'])
    return validate_reference(value)


def validate_reference(value):
    check(value,'CalibrationReference',REFERENCE_FIELDS)
    if value['reference_kind']!='synthetic-self-consistency' or value['provenance']!='same MuJoCo simulator; not independent measured calibration':
        raise ValueError('Unsupported reference scope; measured calibration requires its own reviewed protocol.')
    for key in ('reference_id','case_id','motion_group'):
        if not isinstance(value[key],str) or not value[key].strip():raise ValueError('Invalid reference identity.')
    identity=value['source_identity']
    if not isinstance(identity,dict) or set(identity)!={'result_sha256','recording_sha256'}:
        raise ValueError('Invalid reference source fields.')
    for h in (*identity.values(),value['approach_sha256']):_hash(h)
    window=finite(value['window_s'],(2,),'reference window')
    if window[0]!=0 or window[1]<=0:raise ValueError('Invalid reference window.')
    _metrics(value['endpoints'],value['window_s'])
    return value


def _references(protocol, references, split, base):
    expected={c['case_id'] for c in protocol['cases'] if c['split']==split}
    if not isinstance(references,dict) or set(references)!=expected:raise ValueError(f'{split} input must contain exactly its cases; holdout leakage/partial input blocked.')
    for case in protocol['cases']:
        if case['split']!=split:continue
        ref=references[case['case_id']];identity=case['reference_identity']
        if ref is None:
            if identity is not None:raise ValueError('Frozen reference is missing/corrupt; cannot silently remove it.')
            continue
        validate_reference(ref)
        if (identity!={'reference_id':ref['reference_id'],'content_hash':ref['content_hash']}
                or ref['case_id']!=case['case_id'] or ref['motion_group']!=case['motion_group']
                or ref['window_s']!=case['window_s'] or set(ref['endpoints'])!=set(case['eligible_endpoints'])
                or ref['approach_sha256']!=approach_identity(case['configuration'],base)):
            raise ValueError('Stale reference or initial/COM/inertia mismatch; contact fitting is prohibited.')


def endpoint_report(case, result, reference, protocol):
    records=[]
    for key in case['required_endpoints']:
        actual=result['endpoints'][key];ref=reference['endpoints'][key] if reference else metric(None,'unavailable','Reference absent.')
        status=actual['status'] if actual['status']!='valid' else ref['status']
        rule=case['endpoint_rules'][key]
        delta=actual['value']-ref['value'] if status=='valid' else None
        within=abs(delta)<=rule['tolerance']+rule['label_uncertainty'] if delta is not None else None
        records.append(dict(case_id=case['case_id'],endpoint=key,required=True,units=rule['units'],
            actual=actual,reference=ref,status=status,difference=delta,scale=rule['scale'],weight=rule['weight'],
            tolerance=rule['tolerance'],label_uncertainty=rule['label_uncertainty'],within_proposed_tolerance=within,
            acceptance='needs_review' if status=='valid' else status))
    return records


def aggregate(records, required, *, complete):
    counts=dict(required=required,evaluable=sum(r['status']=='valid' for r in records),pass_count=0,
        ambiguous=sum(r['status']=='ambiguous' for r in records),unavailable=sum(r['status']=='unavailable' for r in records),
        failed=sum(r['status']=='failed' for r in records),not_detected=sum(r['status']=='not_detected' for r in records),
        out_of_window=sum(r['status']=='out_of_window' for r in records),reported=len(records),
        within_proposed_tolerance=sum(r['within_proposed_tolerance'] is True for r in records))
    counts['pass']=0
    return dict(**counts,denominators=dict(required=required,evaluable=counts['evaluable']),
        coverage='complete' if complete and len(records)==required else 'partial',
        numerical_status='needs_review',physical_status='pending',calibration_status='uncalibrated',
        all_required_evaluable=complete and counts['evaluable']==required,
        whole_protocol_pass=False)


def candidate_profile(base, family, value):
    validate_profile(base)
    if family not in FAMILIES:raise ValueError('Only one supported contact parameter family may vary.')
    if family=='rolling' and base['condim']!=6:raise ValueError('Rolling is inactive below condim 6; fitting is unidentifiable.')
    if family=='torsional' and base['condim']<4:raise ValueError('Torsion is inactive below condim 4.')
    field,index=FAMILIES[family];p=deepcopy(base);p[field][index]=value
    return validate_profile(reseal(p))


CASE_FIELDS={'case_id','motion_group','source_identity','configuration_sha256','profile_sha256',
    'approach_sha256','recording_sha256','evaluation_sha256','endpoints','actual_end_s','event_brackets',
    'event_status','designated_events','event_sequence','event_topology','compiled_profile','completion','fresh','reused','calibration_status'}
CONVERGENCE_FIELDS={'source_identity','window_s','physical_settings','runs','changes','endpoint_stability',
    'numerical_acceptance','physical_accuracy','monotonic_convergence'}
FIT_FIELDS={'protocol_sha256','protocol_version','base_profile','base_profile_sha256','fit_references',
    'fit_reference_sha256','selected_profile','selected_profile_sha256','candidates','tied_profile_sha256',
    'identifiability','scope','calibration_status','convergence_reports','convergence_sha256'}
HOLDOUT_FIELDS={'protocol_sha256','selected_profile_sha256','fit_result_sha256','holdout_reference_sha256',
    'results','endpoints','summary','candidate_selection','calibration_status'}


def _hash(value):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{64}',value) is None:
        raise ValueError('Invalid SHA256 identity.')


def _same(actual, expected):
    """Compare derived JSON while keeping booleans separate from numbers."""
    if isinstance(expected,dict):
        return isinstance(actual,dict) and set(actual)==set(expected) and all(_same(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and len(actual)==len(expected) and all(_same(a,b) for a,b in zip(actual,expected))
    if isinstance(expected,(bool,str)) or expected is None:
        return type(actual) is type(expected) and actual==expected
    if isinstance(expected,Real):
        return isinstance(actual,Real) and not isinstance(actual,(bool,np.bool_)) and actual==expected
    return type(actual) is type(expected) and actual==expected


def _metrics(endpoints, window, eligible=None):
    if (not isinstance(endpoints,dict) or not endpoints or not set(endpoints)<=set(ENDPOINT_UNITS)
            or eligible is not None and set(endpoints)!=set(eligible)):
        raise ValueError('Endpoint population differs.')
    for key,m in endpoints.items():
        if (not isinstance(m,dict) or set(m)!={'value','status','reason','units','sample_time_s'}
                or m['units']!=ENDPOINT_UNITS[key] or m['status'] not in STATUSES
                or m['reason'] is not None and not isinstance(m['reason'],str)):
            raise ValueError('Invalid nested endpoint fields/status/units.')
        if m['status']=='valid':
            finite(m['value'],(),'endpoint value')
            if key.startswith('final_'):
                t=finite(m['sample_time_s'],(),'endpoint sample time')
                if abs(t-window[1])>1e-10:raise ValueError('Endpoint sample is outside frozen window.')
            elif m['sample_time_s'] is not None:raise ValueError('Event endpoint has no single sample time.')
            if key in ('dt12_s','rebound_height_mm','final_rotation_deg') and m['value']<0:
                raise ValueError('Invalid nonnegative endpoint.')
        elif m['value'] is not None or not m['reason'] or m['sample_time_s'] is not None:
            raise ValueError('Missing endpoint remains null with reason.')


def validate_case_result(result, case, profile):
    """Reopened results bind every nested field to the requested physical input."""
    check(result,'CalibrationCaseResult',CASE_FIELDS);validate_profile(profile)
    config=configured(case['configuration'],case['configuration']['initial_condition'],profile)
    from src.utils.simulation_metadata import public_configuration
    from .initial_conditions import validate_compiled_values
    expected_source=dict(kind='actual_pub09_engine',case_id=case['case_id'],motion_group=case['motion_group'],
        geometry_mm=config['size_mm'],public_configuration_sha256=digest(public_configuration(config)),
        configuration_sha256=digest(config),profile_sha256=profile['content_hash'],seed_sha256=config['initial_condition']['content_hash'])
    if (result['case_id']!=case['case_id'] or result['motion_group']!=case['motion_group']
            or result['source_identity']!=expected_source or result['configuration_sha256']!=digest(config)
            or result['profile_sha256']!=profile['content_hash']
            or result['approach_sha256']!=approach_identity(config,profile)):
        raise ValueError('Case result source/profile/state identity differs.')
    for name in ('recording_sha256','evaluation_sha256'):_hash(result[name])
    if (result['completion']!='completed' or result['fresh'] is not True or result['reused'] is not False
            or result['calibration_status']!='uncalibrated'
            or abs(finite(result['actual_end_s'],(),'actual end')-case['window_s'][1])>1e-10):
        raise ValueError('Stale/partial case evidence.')
    validate_compiled_values(profile,result['compiled_profile'],config['size_mm'])
    _metrics(result['endpoints'],case['window_s'],case['eligible_endpoints'])
    for name in ('event_brackets','event_status','designated_events'):
        if not isinstance(result[name],dict) or set(result[name])!={'t1','t2'}:
            raise ValueError('Invalid event population.')
    if (not isinstance(result['event_topology'],list)
            or any(kind not in EVENT_KINDS for kind in result['event_topology'])):
        raise ValueError('Unsupported event topology.')
    sequence=result['event_sequence']
    if not isinstance(sequence,list) or [e.get('kind') for e in sequence if isinstance(e,dict)]!=result['event_topology']:
        raise ValueError('Event sequence differs from topology.')
    previous=-1.
    for i,event in enumerate(sequence):
        if (not isinstance(event,dict) or set(event)!={'event_id','kind','status','eligible','time_s','bracket_s','in_window','release_group_id'}
                or type(event['event_id']) is not int or event['event_id']!=i or event['kind'] not in EVENT_KINDS
                or event['status'] not in STATUSES or type(event['release_group_id']) is not int or event['release_group_id']<0
                or type(event['eligible']) is not bool or type(event['in_window']) is not bool):
            raise ValueError('Invalid nested event fields/status.')
        t=finite(event['time_s'],(),'event time');b=finite(event['bracket_s'],(2,),'event bracket')
        eligible=event['kind'] in {'first_floor_impact','new_feature_impact','rebound_recontact','visible_floor_impact'} and event['status']=='valid'
        if (t<=previous or not 0<=b[0]<=t==b[1]<=result['actual_end_s']
                or b[1]-b[0]>profile['solver']['timestep_s']+1e-10 or event['eligible']!=eligible
                or event['in_window']!=(case['window_s'][0]<=t<case['window_s'][1])):
            raise ValueError('Invalid native event chronology/window/eligibility.')
        previous=t
    eligible=[e for e in sequence if e['eligible'] and e['release_group_id']==0]
    for key in ('t1','t2'):
        status=result['event_status'][key];event=result['designated_events'][key];bracket=result['event_brackets'][key]
        if status not in STATUSES:raise ValueError('Invalid event status.')
        candidates=eligible if key=='t1' else eligible[1:]
        first=candidates[0] if candidates else None
        precontact=config['initial_condition']['mode']=='precontact'
        prior_ambiguous=any(e['status']=='ambiguous' and e['release_group_id']==0 and
            (first is None or e['time_s']<=first['time_s']) for e in sequence)
        if precontact and status!='unavailable':raise ValueError('Precontact cannot establish release ordinals.')
        if first is not None and not precontact:
            expected='ambiguous' if prior_ambiguous else 'valid' if first['in_window'] else 'out_of_window'
            if status!=expected:raise ValueError('Event status differs from chronological designation.')
        if status!='valid':
            if event is not None or bracket is not None:raise ValueError('Missing event cannot be coerced valid.')
            continue
        if not isinstance(event,dict) or set(event)!={'time_s','kind','bracket_s'}:
            raise ValueError('Invalid designated event fields.')
        if first is None or not _same(event,{k:first[k] for k in ('time_s','kind','bracket_s')}):
            raise ValueError('Favorable t2 replacement differs from chronological designation.')
        b=finite(bracket,(2,),'event bracket');t=finite(event['time_s'],(),'event time')
        kinds={'first_floor_impact'} if key=='t1' else {'new_feature_impact','rebound_recontact'}
        if (event['kind'] not in kinds or event['kind'] not in result['event_topology'] or not _same(event['bracket_s'],bracket)
                or not 0<=b[0]<=t==b[1]<case['window_s'][1]
                or b[1]-b[0]>profile['solver']['timestep_s']+1e-10):
            raise ValueError('Designated event differs from native bracket/window.')
    valid=all(result['event_status'][k]=='valid' for k in ('t1','t2'))
    if valid and result['designated_events']['t2']['time_s']<=result['designated_events']['t1']['time_s']:
        raise ValueError('Designated t2 must follow t1.')
    for key in ('dt12_s','rebound_height_mm'):
        m=result['endpoints'].get(key)
        if m is None or m['status']!='valid':continue
        if not valid:raise ValueError('Valid event endpoint requires both designated events.')
        if key=='dt12_s' and abs(m['value']-(result['designated_events']['t2']['time_s']-result['designated_events']['t1']['time_s']))>1e-12:
            raise ValueError('Favorable t2 replacement differs from designated event.')
        if key=='rebound_height_mm' and result['designated_events']['t2']['kind']!='rebound_recontact':
            raise ValueError('Rebound height requires designated rebound recontact.')
    return result


def _convergence_diagnostics(case, runs, timesteps, iterations):
    pairs=[]
    for dt in timesteps:
        group=[r for r in runs if r['compiled_profile']['solver']['timestep_s']==dt]
        pairs.extend(('iterations',a,b) for a,b in zip(group,group[1:]))
    for it in iterations:
        group=[r for r in runs if r['compiled_profile']['solver']['iterations']==it]
        pairs.extend(('timestep',a,b) for a,b in zip(group,group[1:]))
    changes=[dict(axis=axis,from_profile=a['profile_sha256'],to_profile=b['profile_sha256'],
        endpoint_differences={k:b['endpoints'][k]['value']-a['endpoints'][k]['value']
            if b['endpoints'][k]['status']==a['endpoints'][k]['status']=='valid' else None for k in case['eligible_endpoints']},
        topology_same=a['event_topology']==b['event_topology'],statuses_same=a['event_status']==b['event_status']) for axis,a,b in pairs]
    stability={k:dict(statuses=[r['endpoints'][k]['status'] for r in runs],values=[r['endpoints'][k]['value'] for r in runs]) for k in case['eligible_endpoints']}
    return changes,stability


def validate_convergence_report(report, case, profile, timesteps=(.002,.001,.0005), iterations=(10,100)):
    check(report,'ContactConvergenceReport',CONVERGENCE_FIELDS)
    if (report['source_identity']!=dict(case_sha256=digest(case),profile_sha256=profile['content_hash'])
            or report['window_s']!=case['window_s'] or report['physical_settings']!='unchanged;solver-iterations-and-timestep-only'
            or report['numerical_acceptance']!='needs_review' or report['physical_accuracy']!='pending'
            or report['monotonic_convergence']!='not-assumed' or not isinstance(report['runs'],list)
            or len(report['runs'])!=len(timesteps)*len(iterations)):
        raise ValueError('Stale/partial convergence evidence.')
    for result,(dt,it) in zip(report['runs'],[(dt,it) for dt in timesteps for it in iterations]):
        p=deepcopy(profile);p['solver'].update(timestep_s=dt,iterations=it);p=reseal(p)
        validate_case_result(result,case,p)
    changes,stability=_convergence_diagnostics(case,report['runs'],timesteps,iterations)
    if not _same(report['changes'],changes) or not _same(report['endpoint_stability'],stability):
        raise ValueError('Convergence diagnostics differ from actual runs.')
    return report


def _population(protocol, split, profile, results, references):
    cases=[c for c in protocol['cases'] if c['split']==split]
    if not isinstance(results,list) or len(results)!=len(cases):raise ValueError('Required case population differs.')
    records=[]
    for case,result in zip(cases,results):
        validate_case_result(result,case,profile)
        records.extend(endpoint_report(case,result,references[case['case_id']],protocol))
    return records,aggregate(records,sum(len(c['required_endpoints']) for c in cases),complete=True)


def validate_fit_result(result, protocol):
    validate_protocol(protocol);check(result,'ContactFitResult',FIT_FIELDS)
    validate_profile(result['selected_profile'])
    base=validate_profile(result['base_profile']);refs=result['fit_references'];reports=result['convergence_reports']
    _references(protocol,refs,'fit',base)
    if (result['protocol_sha256']!=protocol['content_hash'] or result['protocol_version']!=protocol['version']
            or result['base_profile_sha256']!=base['content_hash']
            or result['fit_reference_sha256']!={k:v['content_hash'] if v else None for k,v in refs.items()}
            or set(reports)!=set(protocol['convergence_plan']['case_ids'])
            or result['convergence_sha256']!={k:v['content_hash'] for k,v in reports.items()}
            or result['calibration_status']!='uncalibrated'
            or result['scope']!='synthetic-self-consistency;no-parameter-truth-input;no-holdout-access'):
        raise ValueError('Frozen fit protocol/base/reference/convergence identity differs.')
    for case in protocol['cases']:
        if case['split']=='fit':validate_convergence_report(reports[case['case_id']],case,base)
    candidates=result['candidates']
    if not isinstance(candidates,list) or len(candidates)!=len(protocol['search']['candidates']):
        raise ValueError('Frozen search population differs.')
    for candidate,value in zip(candidates,protocol['search']['candidates']):
        if not isinstance(candidate,dict) or set(candidate)!={'value','profile','score','missing','endpoints','results','summary'}:
            raise ValueError('Unsupported candidate fields.')
        validate_profile(candidate['profile'])
        profile=candidate_profile(base,protocol['search']['family'],value)
        if not _same(candidate['value'],value) or not _same(candidate['profile'],profile):raise ValueError('Candidate differs from single-family search.')
        records,summary=_population(protocol,'fit',profile,candidate['results'],refs)
        score=sum(r['weight']*(r['difference']/r['scale'])**2 if r['difference'] is not None else protocol['missing_rule']['penalty'] for r in records)
        if (not _same(candidate['endpoints'],records) or not _same(candidate['summary'],summary) or type(candidate['missing']) is not int
                or candidate['missing']!=sum(r['difference'] is None for r in records)
                or finite(candidate['score'],(),'fit score')!=score):
            raise ValueError('Fit score/rules/required endpoint population differs.')
    best=min(candidates,key=lambda r:(r['missing'],r['score']))
    tied=[r['profile']['content_hash'] for r in candidates if r['missing']==best['missing'] and abs(r['score']-best['score'])<=protocol['search']['tie_tolerance']]
    identifiability='unavailable-required-endpoint' if best['missing'] else 'ambiguous' if len(tied)>1 else 'unique-on-grid-only'
    if (not _same(result['selected_profile'],best['profile']) or result['selected_profile_sha256']!=best['profile']['content_hash']
            or result['tied_profile_sha256']!=tied or result['identifiability']!=identifiability):
        raise ValueError('Selected profile or ambiguity differs from fit-only objective.')
    return result


def validate_holdout_report(report, protocol, fit_result, references):
    validate_fit_result(fit_result,protocol);check(report,'ContactHoldoutReport',HOLDOUT_FIELDS)
    profile=fit_result['selected_profile'];_references(protocol,references,'holdout',profile)
    records,summary=_population(protocol,'holdout',profile,report['results'],references)
    if (report['protocol_sha256']!=protocol['content_hash'] or report['fit_result_sha256']!=fit_result['content_hash']
            or report['selected_profile_sha256']!=profile['content_hash']
            or report['holdout_reference_sha256']!={k:v['content_hash'] if v else None for k,v in references.items()}
            or not _same(report['endpoints'],records) or not _same(report['summary'],summary)
            or report['candidate_selection']!='already-frozen;holdout-not-used' or report['calibration_status']!='uncalibrated'):
        raise ValueError('Frozen holdout identity/required population differs.')
    return report


def fit(protocol, base_profile, fit_references, *, convergence_reports, output=None):
    """This entry point accepts FIT references only and never runs a holdout."""
    validate_protocol(protocol);validate_profile(base_profile)
    _references(protocol,fit_references,'fit',base_profile)
    if set(convergence_reports)!=set(protocol['convergence_plan']['case_ids']):
        raise ValueError('Fixed-physics convergence for every fit case is required before fitting.')
    for case in protocol['cases']:
        if case['split']=='fit':validate_convergence_report(convergence_reports[case['case_id']],case,base_profile)
    cases=[c for c in protocol['cases'] if c['split']=='fit'];runs=[]
    for index,value in enumerate(protocol['search']['candidates']):
        profile=candidate_profile(base_profile,protocol['search']['family'],value);records=[];results=[]
        for case in cases:
            destination=Path(output)/f'candidate-{index}'/case['case_id'] if output else None
            result,*_=run_case(case,profile,protocol['policy'],output=destination)
            results.append(result);records.extend(endpoint_report(case,result,fit_references[case['case_id']],protocol))
        missing=sum(r['difference'] is None for r in records)
        score=sum(r['weight']*(r['difference']/r['scale'])**2 if r['difference'] is not None else protocol['missing_rule']['penalty'] for r in records)
        runs.append(dict(value=value,profile=profile,score=score,missing=missing,endpoints=records,results=results,
            summary=aggregate(records,sum(len(c['required_endpoints']) for c in cases),complete=True)))
    best=min(runs,key=lambda r:(r['missing'],r['score']))
    tied=[r['profile']['content_hash'] for r in runs if r['missing']==best['missing'] and abs(r['score']-best['score'])<=protocol['search']['tie_tolerance']]
    result=sealed('ContactFitResult',protocol_sha256=protocol['content_hash'],protocol_version=protocol['version'],
        base_profile=base_profile,base_profile_sha256=base_profile['content_hash'],fit_references=fit_references,fit_reference_sha256={k:v['content_hash'] if v else None for k,v in fit_references.items()},
        selected_profile=best['profile'],selected_profile_sha256=best['profile']['content_hash'],candidates=runs,
        tied_profile_sha256=tied,identifiability='unavailable-required-endpoint' if best['missing'] else 'ambiguous' if len(tied)>1 else 'unique-on-grid-only',
        scope='synthetic-self-consistency;no-parameter-truth-input;no-holdout-access',calibration_status='uncalibrated')
    result['convergence_reports']=convergence_reports
    result['convergence_sha256']={k:v['content_hash'] for k,v in convergence_reports.items()}
    result=reseal(result)
    validate_fit_result(result,protocol)
    if output:save(Path(output)/'fit-result.json',result)
    return result


def evaluate_holdout(protocol, fit_result, holdout_references, *, output=None):
    validate_fit_result(fit_result,protocol)
    profile=validate_profile(fit_result['selected_profile']);_references(protocol,holdout_references,'holdout',profile)
    cases=[c for c in protocol['cases'] if c['split']=='holdout'];results=[];records=[]
    for case in cases:
        result,*_=run_case(case,profile,protocol['policy'],output=Path(output)/case['case_id'] if output else None)
        results.append(result);records.extend(endpoint_report(case,result,holdout_references[case['case_id']],protocol))
    report=sealed('ContactHoldoutReport',protocol_sha256=protocol['content_hash'],selected_profile_sha256=profile['content_hash'],
        fit_result_sha256=fit_result['content_hash'],holdout_reference_sha256={k:v['content_hash'] if v else None for k,v in holdout_references.items()},
        results=results,endpoints=records,summary=aggregate(records,sum(len(c['required_endpoints']) for c in cases),complete=True),
        candidate_selection='already-frozen;holdout-not-used',calibration_status='uncalibrated')
    validate_holdout_report(report,protocol,fit_result,holdout_references)
    if output:save(Path(output)/'holdout-report.json',report)
    return report


def convergence(case, profile, policy, *, timesteps=(.002,.001,.0005), iterations=(10,100), output=None):
    """Same physical input/window, native times/brackets; no forced resampling."""
    validate_profile(profile)
    if profile['solref'][0]<2*max(timesteps):raise ValueError('Convergence would change refsafe clamp; fixed-physics comparison blocked.')
    runs=[]
    for dt in timesteps:
        for it in iterations:
            p=deepcopy(profile);p['solver'].update(timestep_s=dt,iterations=it);p=validate_profile(reseal(p))
            result,*_=run_case(case,p,policy,output=Path(output)/f'dt-{dt}-iterations-{it}' if output else None)
            runs.append(result)
    changes,stability=_convergence_diagnostics(case,runs,timesteps,iterations)
    report=sealed('ContactConvergenceReport',source_identity=dict(case_sha256=digest(case),profile_sha256=profile['content_hash']),
        window_s=case['window_s'],physical_settings='unchanged;solver-iterations-and-timestep-only',runs=runs,changes=changes,
        endpoint_stability=stability,
        numerical_acceptance='needs_review',physical_accuracy='pending',monotonic_convergence='not-assumed')
    validate_convergence_report(report,case,profile,timesteps,iterations)
    if output:save(Path(output)/'convergence-report.json',report)
    return report
