"""Independent floor impacts and ordered comparisons; no simulation mutation."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from src.utils.marker_profile_identity import envelope, digest, validate_envelope
from .contact_recording import CONTACT_CONTRACT
from .contact_policy import validate_policy


STATUSES = {'valid', 'not_detected', 'unavailable', 'out_of_window', 'ambiguous', 'failed'}
EVENT_KINDS = {'first_floor_impact','new_feature_impact','rebound_recontact','support_transition','contact_chatter',
    'initial_support','unavailable_contact','ambiguous_contact','unresolved_impact_cluster','constrained_floor_contact','gripper_contact','visible_floor_impact'}


def metric(value=None, status='unavailable', reason=None):
    if status not in STATUSES or (status == 'valid' and value is None):
        raise ValueError('Invalid metric status/value.')
    return dict(value=value, status=status, reason=reason)


def _array(value, shape):
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError('Invalid finite contact array shape.')
    return a


def validate_recording(recording, source_identity=None):
    validate_envelope(recording, 'ContactRecording')
    if recording['contract'] != CONTACT_CONTRACT or recording['completion'] != 'recorded':
        raise ValueError('Unsupported contact time/frame/units/stage contract.')
    if recording['execution_status'] not in ('bounded_capture','completed','partial','cancelled','time_limit','failure'):
        raise ValueError('Unsupported physical recording completion status.')
    source = recording['source_identity']
    if not source or digest(source) != recording['source_sha256'] or (source_identity is not None and source != source_identity):
        raise ValueError('Stale contact source identity.')
    if len(recording['model_xml_sha256']) != 64 or recording['mujoco_version'] != '3.6.0':
        raise ValueError('Unsupported contact model/version.')
    dt = float(recording['timestep_s'])
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError('Invalid contact timestep.')
    size = _array(recording['box_half_extents_mm'], (3,))
    offset = _array(recording['origin_to_com_local_mm'], (3,))
    if 'initial_condition' in recording:
        from .initial_conditions import canonical_state
        state=canonical_state(recording['initial_condition'],offset)
        first=recording['samples'][0]
        if first['time_s']!=0:raise ValueError('Seed recording must begin at actual engine zero.')
        for key,field in (('origin_mm','origin_mm'),('rotation','rotation'),('origin_velocity_mm_s','origin_velocity_mm_s'),('angular_velocity_rad_s','angular_velocity_world')):
            if not np.allclose(first[key],state[field],atol=1e-9,rtol=0):raise ValueError('Recording differs from declared initial condition.')
    if 'contact_profile' in recording:
        from .initial_conditions import validate_compiled_values
        validate_compiled_values(recording['contact_profile'],recording['compiled_profile'],size*2)
    local_corners=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])*size
    if (size <= 0).any() or not recording['samples']:
        raise ValueError('Missing contact geometry/samples.')
    previous = None
    geom_identity={};body_identity={}
    for s in recording['samples']:
        t = float(s['time_s'])
        if not np.isfinite(t) or t < 0 or (previous is not None and abs(t-previous-dt) > 1e-9):
            raise ValueError('Contact recording must contain consecutive actual timesteps.')
        previous = t
        r = _array(s['rotation'], (3, 3))
        if not np.allclose(r.T@r, np.eye(3), atol=1e-10, rtol=0) or abs(np.linalg.det(r)-1) > 1e-10:
            raise ValueError('Invalid contact rotation.')
        for key in ('origin_mm', 'com_mm', 'origin_velocity_mm_s', 'angular_velocity_rad_s'):
            _array(s[key], (3,))
        corners=_array(s['corners_world_mm'], (8, 3)); velocities=_array(s['corners_velocity_mm_s'], (8, 3))
        arms=local_corners@r.T
        if (not np.allclose(corners,arms+s['origin_mm'],atol=1e-8,rtol=0)
                or not np.allclose(velocities,np.cross(s['angular_velocity_rad_s'],arms)+s['origin_velocity_mm_s'],atol=1e-8,rtol=0)
                or not np.allclose(s['com_mm'],r@offset+s['origin_mm'],atol=1e-8,rtol=0)):
            raise ValueError('Inconsistent actual corner/COM/point-velocity frame.')
        if type(s['box_attached']) is not bool:
            raise ValueError('Missing actual attachment state.')
        for c in s['contacts']:
            if 'contact_profile' in recording and c['role']=='floor':
                p=recording['contact_profile'];actual=c.get('effective_parameters',{})
                f=p['friction'];expected=dict(condim=p['condim'],friction=[f[0],f[0],f[1],f[2],f[2]],
                    solref=p['solref'],solimp=p['solimp'],inclusion_margin_mm=sum(p['margin_mm'].values()))
                if set(actual)!=set(expected) or any(not np.allclose(actual[k],v,rtol=0,atol=1e-12) for k,v in expected.items()):
                    raise ValueError('Actual combined contact differs from requested profile.')
            if c['role'] not in ('floor', 'gripper', 'other'):
                raise ValueError('Unknown contact role.')
            pair=set(c['geom_names'])
            expected_role='floor' if pair=={'box_geom','floor'} else 'gripper' if pair=={'box_geom','gripper_geom'} else 'other'
            if c['role']!=expected_role:
                raise ValueError('Contact role differs from actual geom identity.')
            if c['role']=='floor' and (set(c['body_names'])!={'world','box'} or not np.allclose(
                    np.array(c['frame_world_rows'])[0]*c['box_side_sign'],[0,0,1],atol=1e-10,rtol=0)):
                raise ValueError('Unsupported floor body/normal orientation.')
            if len(c['geom_ids']) != 2 or len(c['geom_names']) != 2 or len(c['body_ids']) != 2 or len(c['body_names']) != 2:
                raise ValueError('Missing geom/body identity.')
            for g,gn,b,bn in zip(c['geom_ids'],c['geom_names'],c['body_ids'],c['body_names']):
                if type(g) is not int or type(b) is not int or g<0 or b<0:raise ValueError('Invalid geom/body index.')
                expected_body={'floor':'world','box_geom':'box','gripper_geom':'gripper'}.get(gn)
                if expected_body is not None and bn!=expected_body:raise ValueError('Geom belongs to the wrong recorded body.')
                if (bn=='world')!=(b==0):raise ValueError('Invalid world-body identity.')
                if g in geom_identity and geom_identity[g]!=(gn,b):raise ValueError('Geom identity changes across timesteps.')
                if b in body_identity and body_identity[b]!=bn:raise ValueError('Body identity changes across timesteps.')
                geom_identity[g]=(gn,b);body_identity[b]=bn
            side = 1 if c['geom_names'][1] == 'box_geom' else -1 if c['geom_names'][0] == 'box_geom' else 0
            if c['box_side_sign'] != side:
                raise ValueError('Wrong contact wrench sign.')
            basis = _array(c['frame_world_rows'], (3, 3)); wrench = _array(c['wrench_contact_on_geom2'], (6,))
            if type(c.get('efc_address')) is not int or c['efc_address'] < -1 or (c['efc_address']==-1 and np.any(wrench!=0)):
                raise ValueError('Invalid or absent force-constraint evidence.')
            if not np.allclose(basis@basis.T, np.eye(3), atol=1e-10, rtol=0) or abs(np.linalg.det(basis)-1) > 1e-10:
                raise ValueError('Invalid contact frame.')
            mid = _array(c['world_midpoint_mm'], (3,)); world = _array(c['box_surface_world_mm'], (3,))
            local = _array(c['box_surface_local_mm'], (3,))
            for key in ('distance_mm', 'inclusion_margin_mm', 'closing_speed_mm_s', 'normal_force_n'):
                if not np.isfinite(c[key]): raise ValueError('Nonfinite contact evidence.')
            if (c['normal_force_n'] < 0 or c['normal_force_n'] != wrench[0]
                    or not np.allclose(world, mid + side*c['distance_mm']/2*basis[0], atol=1e-8, rtol=0)
                    or not np.allclose(world, r@local+s['origin_mm'], atol=1e-8, rtol=0)
                    or not np.allclose(c['force_world_on_box_n'], side*basis.T@wrench[:3], atol=1e-8, rtol=0)
                    or not np.allclose(c['torque_world_at_contact_on_box_nm'], side*basis.T@wrench[3:], atol=1e-8, rtol=0)):
                raise ValueError('Inconsistent contact point/frame/wrench.')
    return digest(recording)


def _feature(ids):
    if len(ids) == 1: return 'corner'
    signs=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])
    chosen=signs[np.array(ids)-1] if ids else np.empty((0,3))
    if len(ids) == 2 and np.count_nonzero(chosen[0]!=chosen[1])==1:return 'edge'
    if len(ids) == 4 and np.any(np.ptp(chosen,axis=0)==0):return 'face'
    return 'mixed'


def evaluate_contacts(recording, policy, *, window=None, source_identity=None, release_group_id=None):
    """Classify material-point load onsets, not aggregate force peaks or labels."""
    ph = validate_policy(policy); rh = validate_recording(recording, source_identity)
    samples = recording['samples']; dt = recording['timestep_s']
    times = np.array([s['time_s'] for s in samples])
    if window is None: window = (float(times[0]), float(times[-1]+dt))
    if len(window) != 2 or not np.isfinite(window).all() or window[1] <= window[0]:
        raise ValueError('Invalid half-open evaluation window.')
    half = np.array(recording['box_half_extents_mm'])
    local = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])*half
    armed = np.zeros(8, bool); clear_since = [None]*8; loaded = np.zeros(8, bool)
    airborne_since = None; airborne_armed = False; had_impact = False
    episode = None; episodes = []; events = []; last_impact = None
    release_group = 0; bad_loaded = False
    geometric = [None]*8
    for i, s in enumerate(samples):
        t = s['time_s']; corners = np.array(s['corners_world_mm']); heights = corners[:,2]
        if i and samples[i-1]['box_attached'] and not s['box_attached']:
            release_group += 1
        if s['box_attached']:
            had_impact = False; last_impact = None
        floor = [c for c in s['contacts'] if c['role'] == 'floor']
        forces = np.zeros(8); mappings = {}; bad = []
        for c in floor:
            distances = np.linalg.norm(local - c['box_surface_local_mm'], axis=1); j = int(np.argmin(distances))
            if distances[j] > policy['feature_tolerance_mm']:
                bad.append(c); continue
            forces[j] += c['normal_force_n']; mappings.setdefault(j, []).append(c)
        active = forces >= policy['force_on_n']; any_load = any(c['normal_force_n'] >= policy['force_on_n'] for c in floor)
        if floor and episode is None:
            episode = dict(episode_id=len(episodes), start_time_s=t, end_time_s=None, start_censored=i==0)
            episodes.append(episode)
        elif not floor and episode is not None:
            episode['end_time_s'] = t; episode = None
        if i:
            previous = samples[i-1]; prev_heights = np.array(previous['corners_world_mm'])[:,2]
            for j in range(8):
                if prev_heights[j] > 0 and heights[j] <= 0:
                    geometric[j] = [previous['time_s'], t]
        for j in range(8):
            if forces[j] <= policy['force_off_n'] and heights[j] >= policy['rearm_clearance_mm']:
                if clear_since[j] is None: clear_since[j] = t
                if t-clear_since[j] >= policy['rearm_dwell_s']-1e-12: armed[j] = True
            else: clear_since[j] = None
        if not any_load and np.min(heights) >= policy['rearm_clearance_mm']:
            if airborne_since is None: airborne_since = t
            if t-airborne_since >= policy['rearm_dwell_s']-1e-12: airborne_armed = True
        else: airborne_since = None
        onset = np.flatnonzero(active & ~loaded)
        bad_on = any(c['normal_force_n'] >= policy['force_on_n'] for c in bad)
        if len(onset) or (bad_on and not bad_loaded):
            previous = samples[max(0,i-1)]
            speeds = {int(j): float(-np.array(previous['corners_velocity_mm_s'])[j,2]) for j in onset}
            qualified = [int(j) for j in onset if armed[j] and speeds[int(j)] >= policy['approach_mm_s']]
            conflict = bad_on or any(armed[j] and speeds[int(j)] <= -policy['approach_mm_s'] for j in onset)
            if s['box_attached']: kind, status = 'constrained_floor_contact', 'unavailable'
            elif conflict: kind, status = 'ambiguous_contact', 'ambiguous'
            elif qualified:
                kind = 'first_floor_impact' if not had_impact else 'rebound_recontact' if airborne_armed else 'new_feature_impact'
                status = 'valid'
                if last_impact is not None and t-last_impact <= policy['merge_s']+1e-12:
                    kind, status = 'unresolved_impact_cluster', 'ambiguous'
                had_impact = True; last_impact = t
            else:
                insufficient=(not had_impact and t-times[0]<policy['rearm_dwell_s']
                    and any(speeds[int(j)]>=policy['approach_mm_s'] for j in onset))
                kind = 'initial_support' if i==0 else 'unavailable_contact' if insufficient else 'contact_chatter' if all(not armed[j] for j in onset) else 'support_transition'
                status = 'unavailable' if i==0 or insufficient else 'valid'
            ids = [int(j)+1 for j in np.flatnonzero(active)]
            if kind in ('first_floor_impact','rebound_recontact','new_feature_impact') and _feature(ids)=='mixed':
                kind,status='ambiguous_contact','ambiguous'
            impact = kind in ('first_floor_impact','rebound_recontact','new_feature_impact')
            event = dict(event_id=len(events),kind=kind,status=status,eligible=impact and status=='valid',
                time_s=t, bracket_s=[previous['time_s'],t], corner_ids=ids, new_corner_ids=[int(j)+1 for j in onset],
                release_group_id=release_group,
                feature=_feature(ids), episode_id=episodes[-1]['episode_id'] if episodes else None,
                prior_closing_mm_s=speeds, current_closing_mm_s=[c['closing_speed_mm_s'] for c in floor],
                normal_force_n=float(sum(c['normal_force_n'] for c in floor)),
                geometric_brackets_s=[geometric[j] for j in onset],
                prior_state=deepcopy({k:previous[k] for k in ('time_s','origin_mm','rotation','origin_velocity_mm_s','angular_velocity_rad_s')}),
                in_window=bool(window[0]<=t<window[1]))
            events.append(event)
            for j in onset: armed[j] = False
            airborne_armed = False
        loaded = (loaded & (forces > policy['force_off_n'])) | active
        bad_loaded = bad_on
        if any(c['role']=='gripper' and c['normal_force_n']>=policy['force_on_n'] for c in s['contacts']) and not floor:
            if not events or events[-1]['kind']!='gripper_contact':
                events.append(dict(event_id=len(events),kind='gripper_contact',status='valid',eligible=False,time_s=t,
                    bracket_s=[samples[max(i-1,0)]['time_s'],t],in_window=bool(window[0]<=t<window[1])))
    # Geometry can follow soft force onset; look ahead without moving event time.
    for event in events:
        if 'new_corner_ids' not in event: continue
        brackets=[]
        for j in event['new_corner_ids']:
            next_onset=next((e['bracket_s'][0] for e in events if e['time_s']>event['time_s'] and j in e.get('new_corner_ids',[])),times[-1]+dt)
            bracket=next(([samples[k-1]['time_s'],samples[k]['time_s']] for k in range(1,len(samples))
                if event['bracket_s'][0]<=samples[k]['time_s']<next_onset and np.array(samples[k-1]['corners_world_mm'])[j-1,2]>0
                and np.array(samples[k]['corners_world_mm'])[j-1,2]<=0),None)
            brackets.append(bracket)
        event['geometric_brackets_s']=brackets
        first=next((b for b in brackets if b is not None),None)
        event['force_minus_geometric_s']=metric(event['time_s']-first[1],'valid') if first else metric(reason='No geometric zero crossing in recorded interval.')
    if recording.get('initial_condition',{}).get('mode')=='precontact':
        for e in events:
            if e['release_group_id']==0 and e['kind']=='first_floor_impact':e['kind']='visible_floor_impact'
    selected_group=release_group_id if release_group_id is not None else next((e['release_group_id'] for e in events if e['eligible']),0)
    if type(selected_group) is not int or selected_group<0:raise ValueError('Invalid declared release group.')
    eligible=[e for e in events if e['eligible'] and e['release_group_id']==selected_group]
    ambiguous=[e for e in events if e['status']=='ambiguous' and e.get('release_group_id')==selected_group]
    def endpoint(which):
        if recording.get('initial_condition',{}).get('mode')=='precontact' and selected_group==0:
            return metric(None,'unavailable','Precontact seed has unknown release prehistory; first visible impact is not full-release t1/t2.')
        candidates=eligible if which==1 else [e for e in eligible[1:] if e['release_group_id']==eligible[0]['release_group_id']
            and (policy['designated_t2']=='next_floor_impact' or e['kind']=='rebound_recontact')]
        event=candidates[0] if candidates else None
        if ambiguous and (event is None or any(a['time_s']<=event['time_s'] for a in ambiguous)):
            return metric(status='ambiguous',reason='Unresolved prior floor onset; cannot choose a later favorable event.')
        if event and not event['in_window']:return metric(event,'out_of_window','Designated event is outside evaluation window.')
        if event is None and (window[1]>times[-1]+dt+1e-9 or recording.get('execution_status') in ('partial','cancelled','time_limit','failure')):
            return metric(status='unavailable',reason='Incomplete recording cannot establish absence of designated impact.')
        if event is None and which==1 and any(e['kind'] in ('initial_support','unavailable_contact') for e in events):
            return metric(status='unavailable',reason='Initial floor support has no recorded approach/onset prehistory.')
        return metric(event,'valid') if event else metric(status='not_detected',reason='No qualifying designated floor impact.')
    clusters=[]
    for e in events:
        if e['kind'] not in ('first_floor_impact','new_feature_impact','rebound_recontact','unresolved_impact_cluster'):continue
        if clusters and e['kind']=='unresolved_impact_cluster':
            c=clusters[-1];c['onset_event_ids'].append(e['event_id']);c['status']='ambiguous'
            c['onset_spread_s']=e['time_s']-c['time_s'];c['reason']='Independently armed onsets within merge resolution.'
        else:clusters.append(dict(cluster_id=len(clusters),time_s=e['time_s'],onset_event_ids=[e['event_id']],status=e['status'],onset_spread_s=0.,reason='Resolved onset.'))
    result = envelope('ContactEvaluation',policy=deepcopy(policy),policy_sha256=ph,recording_sha256=rh,
        source_identity=deepcopy(recording['source_identity']),window_s=list(window),release_group_id=selected_group,events=events,episodes=episodes,onset_clusters=clusters,
        t1=endpoint(1),t2=endpoint(2),physical_acceptance='not_evaluated')
    if 'initial_condition' in recording:
        seed=recording['initial_condition']
        result['seed_context']=dict(mode=seed['mode'],content_hash=seed['content_hash'],prehistory=seed['prehistory'])
    return result


def save_document(path, value):
    """New evidence paths only; never overwrite failed or previous results."""
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False); f.write('\n')


def load_recording(path, source_identity=None):
    value=json.loads(Path(path).read_text(encoding='utf-8'),parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    validate_recording(value,source_identity); return value


def validate_evaluation(value, policy):
    validate_envelope(value,'ContactEvaluation');ph=validate_policy(policy)
    if value['policy']!=policy or value['policy_sha256']!=ph or not value['source_identity'] or len(value['recording_sha256'])!=64:
        raise ValueError('Invalid evaluation policy/source identity.')
    window=value['window_s']
    if len(window)!=2 or not np.isfinite(window).all() or window[1]<=window[0]:raise ValueError('Invalid evaluation window.')
    group=value['release_group_id']
    if type(group) is not int or group<0:raise ValueError('Invalid evaluation release group.')
    previous=-np.inf
    for i,e in enumerate(value['events']):
        if e['event_id']!=i or e['kind'] not in EVENT_KINDS or e['status'] not in STATUSES or e['time_s']<=previous or not np.isfinite(e['time_s']):
            raise ValueError('Invalid truth event kind/status/order/clock.')
        previous=e['time_s']
        expected=e['kind'] in ('first_floor_impact','new_feature_impact','rebound_recontact','visible_floor_impact') and e['status']=='valid'
        if e['kind']=='visible_floor_impact' and value.get('seed_context',{}).get('mode')!='precontact':
            raise ValueError('Visible-only impact needs a precontact seed declaration.')
        if type(e['eligible']) is not bool or e['eligible']!=expected or type(e['in_window']) is not bool or e['in_window']!=(window[0]<=e['time_s']<window[1]):
            raise ValueError('Inconsistent truth eligibility/window.')
        b=e['bracket_s']
        if len(b)!=2 or not np.isfinite(b).all() or not b[0]<=e['time_s']<=b[1]:raise ValueError('Invalid truth bracket.')
    for key in ('t1','t2'):
        m=value[key]
        if m['status'] not in STATUSES or (m['status']=='valid' and m['value'] is None):raise ValueError('Invalid endpoint metric status.')
        if m['value'] is not None and (not isinstance(m['value'],dict) or m['value'] not in value['events']):raise ValueError('Endpoint does not reference a recorded event.')
        eligible=[e for e in value['events'] if e['eligible'] and e.get('release_group_id')==group]
        candidates=eligible if key=='t1' else [e for e in eligible[1:] if policy['designated_t2']=='next_floor_impact' or e['kind']=='rebound_recontact']
        designated=candidates[0] if candidates else None
        prior_ambiguous=any(e['status']=='ambiguous' and e.get('release_group_id')==group and (designated is None or e['time_s']<=designated['time_s']) for e in value['events'])
        precontact=value.get('seed_context',{}).get('mode')=='precontact' and group==0
        if precontact and (m['status']!='unavailable' or m['value'] is not None):
            raise ValueError('Precontact seed cannot establish full-release t1/t2.')
        if designated is not None and not precontact:
            expected_status='ambiguous' if prior_ambiguous else 'valid' if designated['in_window'] else 'out_of_window'
            if m['status']!=expected_status:raise ValueError('Endpoint status contradicts the designated event evidence.')
        if m['status'] in ('valid','out_of_window'):
            if m['value']!=designated or designated is None or (m['status']=='valid')!=designated['in_window']:
                raise ValueError('Endpoint differs from the frozen chronological designation.')
            if prior_ambiguous:
                raise ValueError('Endpoint skips an unresolved prior floor onset.')
        elif m['value'] is not None:raise ValueError('Missing/ambiguous endpoint cannot contain an accepted event.')
    return digest(value)


def load_evaluation(path, policy, recording):
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    validate_evaluation(value,policy)
    actual=evaluate_contacts(recording,policy,window=value['window_s'],release_group_id=value['release_group_id'])
    if digest(value)!=digest(actual):raise ValueError('Saved evaluation differs from its actual recording/policy.')
    return value


def evaluate_available(recording, policy, **kwargs):
    """Absent modality differs from a malformed source/calculation failure."""
    if recording is None:
        return envelope('ContactEvaluationFailure',status='unavailable',reason='Actual contact recording is absent.',value=None)
    try:return evaluate_contacts(recording,policy,**kwargs)
    except Exception as error:
        return envelope('ContactEvaluationFailure',status='failed',reason=str(error),value=None,exception_type=type(error).__name__)
