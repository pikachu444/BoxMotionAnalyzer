"""Read-only observation adapter and fixed chronological event correspondence."""
from copy import deepcopy

import numpy as np
from scipy.spatial.transform import Rotation

from src.config.data_columns import PoseCols, VelocityCols
from src.utils.marker_profile_identity import envelope, digest, validate_envelope
from .contact_policy import validate_policy
from .contact_evaluation import metric,validate_evaluation
from .history_trajectory import WORLD_TRANSFORM


DETECTOR_CONTRACT = dict(world_frame='analysis-y-up', local_frame='box-body-origin', time='raw-seconds',
    units=dict(position='mm',velocity='mm/s',angular_velocity='rad/s',time='s'),
    event_kind='legacy_contact_set_run', eligibility='existing whole-record impact mask; runs >=2 samples',
    timing='first sample of stable contact-set run; t1-minus remains separate', semantics_version='pub08-legacy-adapter-v1')


def observed_events(processed, processor, source_identity, *, threshold_mm=1.):
    """Use exactly the existing postprocessor masks/run semantics, without truth."""
    base = dict(contract=deepcopy(DETECTOR_CONTRACT), source_identity=deepcopy(source_identity),
        source_sha256=digest(source_identity), events=[], t1_minus=metric(),
        settings=dict(threshold_mm=float(threshold_mm)), failure=None)
    try:
        if processed is None or processed.empty:
            return envelope('DetectorEvents',status='unavailable',reason='Empty observation processing.',**base)
        missing=[c for c in processor._required_columns() if c not in processed]
        if missing:
            return envelope('DetectorEvents',status='unavailable',reason='Incomplete pose/corner columns.',**base)
        times=processed.index.to_numpy(dtype=float)
        if not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('Invalid raw detector clock.')
        corners=processor._corner_positions(processed)
        rotations=processed[[PoseCols.ROT_X,PoseCols.ROT_Y,PoseCols.ROT_Z]].to_numpy(float)
        if not np.isfinite(corners).all() or not np.isfinite(rotations).all():
            return envelope('DetectorEvents',status='unavailable',reason='Existing whole-record contact requires complete pose.',**base)
        heights=corners[:,:,processor.vertical_axis_idx]
        analysis=processor._contact_analysis(min_heights=heights.min(axis=1),index=processed.index,contact_threshold_mm=threshold_mm)
        sets=processor._contact_sets(heights,threshold_mm,active_mask=analysis['active_mask'],relative_contact_band=analysis['relative_contact_band'])
        if analysis['t1_minus_pos'] is not None:base['t1_minus']=metric(float(times[analysis['t1_minus_pos']]),'valid')
        runs=[]; start=0
        for i in range(1,len(sets)+1):
            if i==len(sets) or sets[i]!=sets[start]:
                if sets[start] and i-start>=2:runs.append((start,i,sets[start]))
                start=i
        summary=processor._impact_sequence_summary(contact_sets=sets,index=processed.index)
        from src.config.data_columns import DropPostureSummaryCols
        if len(runs)!=summary[DropPostureSummaryCols.IMPACT_EVENT_COUNT]:raise ValueError('Legacy run adapter differs from production summary.')
        pose_cols=[PoseCols.POS_X,PoseCols.POS_Y,PoseCols.POS_Z]
        velocity_cols=[VelocityCols.T_VX,VelocityCols.T_VY,VelocityCols.T_VZ]
        angular_cols=[VelocityCols.R_VX,VelocityCols.R_VY,VelocityCols.R_VZ]
        for start,end,ids in runs:
            prior=max(0,start-1); row=processed.iloc[prior]
            state=dict(time_s=float(times[prior]),rotation=Rotation.from_rotvec(rotations[prior]).as_matrix().tolist())
            for key,cols in [('origin_mm',pose_cols),('origin_velocity_mm_s',velocity_cols),('angular_velocity_rad_s',angular_cols)]:
                value=row[cols].to_numpy(float) if all(c in row for c in cols) else None
                state[key]=value.tolist() if value is not None and np.isfinite(value).all() else None
            base['events'].append(dict(event_id=len(base['events']),kind='legacy_contact_set_run',status='valid',
                eligible=bool(analysis['impact_detected']),time_s=float(times[start]),bracket_s=[float(times[prior]),float(times[start])],
                corner_ids=list(ids),prior_state=state,run_records=[start,end],physical_kind='unverified'))
        if runs and analysis['impact_detected'] and analysis['t1_minus_pos'] is not None:
            first_start=runs[0][0];prior=max(0,first_start-1)
            if analysis['t1_minus_pos']!=prior:
                base['events'][0]['status']='ambiguous'
                base['events'][0]['reason']='Legacy first contact run and existing t1-minus refer to different events.'
        base['settings'].update(contact_state=analysis['contact_state'],method=analysis['contact_detection_method'],
            relative_band_mm=analysis['relative_contact_band'])
        return envelope('DetectorEvents',status='valid',reason=None,**base)
    except Exception as error:
        base['failure']=dict(exception_type=type(error).__name__,message=str(error))
        return envelope('DetectorEvents',status='failed',reason='Observation event adapter failed.',**base)


def validate_detector(value):
    validate_envelope(value,'DetectorEvents')
    if value['contract']!=DETECTOR_CONTRACT or digest(value['source_identity'])!=value['source_sha256']:
        raise ValueError('Invalid detector source/frame/time/units.')
    if value['status'] not in ('valid','unavailable','failed'):raise ValueError('Invalid detector status.')
    previous=-np.inf
    for i,e in enumerate(value['events']):
        if e['kind']!='legacy_contact_set_run':raise ValueError('Unsupported detector event kind; no physical labels accepted.')
        if e['event_id']!=i or not np.isfinite(e['time_s']) or e['time_s']<=previous:
            raise ValueError('Wrong detector event order/clock.')
        if (e['status'] not in ('valid','ambiguous') or type(e['eligible']) is not bool
                or len(e['bracket_s'])!=2 or not np.isfinite(e['bracket_s']).all()
                or not e['bracket_s'][0]<=e['time_s']<=e['bracket_s'][1]):raise ValueError('Invalid detector event/bracket.')
        previous=e['time_s']


def _kinematics(truth, detector, shift):
    a,b=truth.get('prior_state'),detector.get('prior_state')
    if a is None or b is None:return dict(status='unavailable',reason='No pre-event state.')
    result=dict(truth_time_s=a['time_s'],detector_time_s=b['time_s'],acceptance='proposed; numerical diagnostic only')
    for key in ('origin_mm','origin_velocity_mm_s','angular_velocity_rad_s'):
        if a.get(key) is None or b.get(key) is None: result[key]=metric(reason='Missing observed state.');continue
        result[key]=metric((WORLD_TRANSFORM.T@np.array(b[key])-a[key]).tolist(),'valid')
    if a.get('rotation') is None or b.get('rotation') is None:result['rotation_error_deg']=metric()
    else:
        relative=np.array(a['rotation']).T@WORLD_TRANSFORM.T@np.array(b['rotation'])
        result['rotation_error_deg']=metric(float(np.degrees(Rotation.from_matrix(relative).magnitude())),'valid')
    result['raw_pre_sample_time_difference_s']=metric(b['time_s']-a['time_s'],'valid')
    result['aligned_pre_sample_time_error_s']=metric(b['time_s']+shift-a['time_s'],'valid')
    return result


def observation_pair(truth, raw_path):
    """Generator's explicit pairing; not an observation-analysis input."""
    import hashlib
    from pathlib import Path
    return envelope('ContactObservationPair',recording_sha256=truth['recording_sha256'],
        truth_source_sha256=digest(truth['source_identity']),raw_sha256=hashlib.sha256(Path(raw_path).read_bytes()).hexdigest(),
        policy_sha256=truth['policy_sha256'])


def compare_events(truth, detector, policy, *, approval='proposed', pairing=None):
    """No closest-event optimization, event-wise warp, or hidden extra events."""
    ph=validate_policy(policy); validate_evaluation(truth,policy);validate_detector(detector)
    if truth['policy_sha256']!=ph or truth['policy']!=policy:raise ValueError('Truth policy identity differs.')
    identity=truth['source_identity'];observation=detector['source_identity']
    if str(identity.get('kind','')).startswith('actual_') and pairing is None:
        raise ValueError('Actual contact comparison requires a producer-bound Raw identity pair.')
    if pairing is not None:
        validate_envelope(pairing,'ContactObservationPair')
        if (pairing['recording_sha256']!=truth['recording_sha256'] or pairing['truth_source_sha256']!=digest(identity)
                or pairing['raw_sha256']!=observation.get('raw_sha256') or pairing['policy_sha256']!=ph):
            raise ValueError('Stale or mismatched Raw/contact pairing.')
    if 'public_configuration_sha256' in identity and observation.get('public_configuration_sha256')!=identity['public_configuration_sha256']:
        raise ValueError('Observation configuration differs from actual contact source.')
    if 'geometry_mm' in identity and observation.get('geometry_mm')!=identity['geometry_mm']:
        raise ValueError('Observed geometry differs from contact source.')
    ts=truth['events']; ds=detector['events']
    if any(e['event_id']!=i for i,e in enumerate(ts)) or any(b['time_s']<=a['time_s'] for a,b in zip(ts,ts[1:])):
        raise ValueError('Wrong truth event order.')
    ta=[e for e in ts if e['eligible'] and e['in_window'] and e.get('release_group_id')==truth['release_group_id']]
    da=[e for e in ds if e['eligible'] and e['status']=='valid' and truth['window_s'][0]<=e['time_s']<truth['window_s'][1]]
    designated_observed=[e for e in ds if e['eligible'] and truth['window_s'][0]<=e['time_s']<truth['window_s'][1]]
    anchor_ambiguous=bool(designated_observed and designated_observed[0]['status']=='ambiguous')
    shift=None; matches=[]; ambiguous=[]; used_t=set(); used_d=set();reserved_t=set()
    if ta and da and not anchor_ambiguous and truth['t1']['status']=='valid' and detector['status']=='valid':
        shift=ta[0]['time_s']-da[0]['time_s']
        matches.append(dict(truth_id=ta[0]['event_id'],detector_id=da[0]['event_id'],aligned_error_s=0.,role='t1_anchor'))
        used_t.add(ta[0]['event_id']);used_d.add(da[0]['event_id'])
        last_d=da[0]['event_id']
        for t in ta[1:]:
            if t['event_id'] in reserved_t:continue
            options=[d for d in designated_observed if d['event_id']>last_d and d['event_id'] not in used_d
                and abs(d['time_s']+shift-t['time_s'])<=policy['matching_window_s']+1e-12]
            if not options:continue
            d=options[0]
            competing=[t2 for t2 in ta if t2['event_id'] not in (used_t|reserved_t)
                and any(abs(option['time_s']+shift-t2['time_s'])<=policy['matching_window_s']+1e-12 for option in options)]
            if d['status']=='ambiguous' or len(options)>1 or len(competing)>1:
                ambiguous.append(dict(truth_ids=[x['event_id'] for x in competing],detector_ids=[x['event_id'] for x in options],reason='Unresolved or multiple chronological counterparts within fixed window.'))
                # Reserve ambiguous interval so later events cannot steal a favorable match.
                reserved_t.update(x['event_id'] for x in competing)
                last_d=max(x['event_id'] for x in options);continue
            matches.append(dict(truth_id=t['event_id'],detector_id=d['event_id'],aligned_error_s=d['time_s']+shift-t['time_s'],role='ordered'))
            used_t.add(t['event_id']);used_d.add(d['event_id']);last_d=d['event_id']
    def endpoint(which):
        target=truth[which]
        if target['status']!='valid':return metric(status=target['status'],reason=target['reason'])
        if detector['status']!='valid':return metric(status=detector['status'],reason=detector['reason'])
        if anchor_ambiguous:return metric(status='ambiguous',reason='Declared first observation conflicts with existing t1-minus; later anchors are forbidden.')
        if which=='t2' and len(designated_observed)>=2 and designated_observed[1]['status']=='ambiguous':
            return metric(status='ambiguous',reason='The designated second observation is unresolved; later replacement is forbidden.')
        event=target['value']; match=next((m for m in matches if m['truth_id']==event['event_id']),None)
        if any(event['event_id'] in a['truth_ids'] for a in ambiguous):return metric(status='ambiguous',reason='Multiple ordered matches.')
        if match is None:return metric(status='not_detected',reason='Designated truth event has no eligible observed match.')
        d=ds[match['detector_id']]
        # t2 is pre-designated second observed run; never choose a later matching run instead.
        if which=='t2' and (len(designated_observed)<2 or d['event_id']!=designated_observed[1]['event_id']):
            return metric(status='ambiguous',reason='Truth t2 matches a later run than the designated analysis t2.')
        return metric(dict(truth_event_id=event['event_id'],detector_event_id=d['event_id'],
            aligned_time_error_s=match['aligned_error_s'],corner_agreement=event.get('corner_ids')==d.get('corner_ids'),
            kinematics=_kinematics(event,d,shift)),'valid')
    t1=endpoint('t1');t2=endpoint('t2')
    delta=metric(reason='Two designated matched events are required.')
    declared_delta=metric(reason='Two eligible truth and observed endpoints are required.')
    if truth['t1']['status']==truth['t2']['status']=='valid' and len(designated_observed)>=2:
        a1,a2=truth['t1']['value'],truth['t2']['value'];b1,b2=designated_observed[:2]
        declared_delta=metric(dict(truth_s=a2['time_s']-a1['time_s'],detector_s=b2['time_s']-b1['time_s'],
            error_s=(b2['time_s']-b1['time_s'])-(a2['time_s']-a1['time_s']),
            interpretation='declared endpoints; may be unmatched or ambiguous; not an accepted correspondence'),'valid')
    if t1['status']==t2['status']=='valid':
        a1,a2=truth['t1']['value'],truth['t2']['value'];b1,b2=[ds[x['value']['detector_event_id']] for x in (t1,t2)]
        delta=metric(dict(truth_s=a2['time_s']-a1['time_s'],detector_s=b2['time_s']-b1['time_s'],
            error_s=(b2['time_s']-b1['time_s'])-(a2['time_s']-a1['time_s'])),'valid')
    coverage='first_and_subsequent' if t1['status']==t2['status']=='valid' else 'first_only' if t1['status']=='valid' else 'no_first_match'
    return envelope('ContactComparison',policy_sha256=ph,truth_sha256=digest(truth),detector_sha256=digest(detector),
        observation_pair=deepcopy(pairing),
        source_identity=dict(truth=truth['source_identity'],detector=detector['source_identity']),
        t1_shift_s=metric(shift,'valid') if shift is not None else metric(reason='No unambiguous first-event anchor.'),
        t1=t1,t2=t2,delta_t12=delta,declared_delta_t12=declared_delta,matches=matches,coverage=coverage,
        unmatched_truth=[e for e in ts if e['eligible'] and e['event_id'] not in used_t],
        extra_detector=[e for e in ds if e['eligible'] and e['event_id'] not in used_d],
        ambiguous=dict(matching=ambiguous,truth=[e for e in ts if e['status']=='ambiguous'],detector=[e for e in ds if e['status']=='ambiguous']),
        policy_approval=approval,numerical_acceptance='needs_review',physical_acceptance='not_evaluated')


def motion_diagnostics(recording, truth, detector, processed, *, comparison=None):
    """Compare trajectories using only the established event correspondence.

    Values are diagnostics, with no new detector labels or acceptance threshold.
    Minimum-corner clearance is not the rise of the COM or a measured bounce.
    """
    if comparison is None:
        return dict(status='unavailable',reason='An established event comparison is required.')
    validate_envelope(comparison,'ContactComparison')
    if comparison['truth_sha256']!=digest(truth) or comparison['detector_sha256']!=digest(detector):
        raise ValueError('Motion comparison source differs from the established event comparison.')
    if comparison['t1']['status']!='valid':
        return dict(status=comparison['t1']['status'],reason=comparison['t1']['reason'])
    if comparison['t1_shift_s']['status']!='valid':
        return dict(status='unavailable',reason='No established single t1 alignment.')
    first=truth['t1']['value'];start=first['time_s'];stop=truth['window_s'][1]
    later_attach=next((s['time_s'] for s in recording['samples'] if s['time_s']>start and s['box_attached']),None)
    if later_attach is not None:stop=min(stop,later_attach)
    samples=[s for s in recording['samples'] if start<=s['time_s']<stop]
    shift=comparison['t1_shift_s']['value']
    obs=processed.loc[(processed.index.to_numpy(float)+shift>=start)&(processed.index.to_numpy(float)+shift<stop)]
    if len(samples)<2 or len(obs)<2:return dict(status='unavailable',reason='Insufficient post-impact trajectory.')
    truth_height=np.array([min(np.array(s['corners_world_mm'])[:,2]) for s in samples])
    observed_height=obs[[f'C{i}_Y' for i in range(1,9)]].min(axis=1).to_numpy(float)
    tr=Rotation.from_matrix(np.array([s['rotation'] for s in samples]))
    dr=Rotation.from_rotvec(obs[[PoseCols.ROT_X,PoseCols.ROT_Y,PoseCols.ROT_Z]].to_numpy(float))
    # Relative angles are frame-invariant; each side uses its own first actual sample.
    angles_t=np.degrees((tr[0].inv()*tr).magnitude());angles_d=np.degrees((dr[0].inv()*dr).magnitude())
    velocity=np.gradient(observed_height,obs.index.to_numpy(float))
    observed_reversal=bool(np.any(velocity>50.) and np.any(velocity< -50.))
    return dict(status='valid',interval_truth_s=[start,stop],single_t1_shift_s=shift,
        truth=dict(rebound_recontact_count=sum(e['kind']=='rebound_recontact' and e.get('release_group_id')==truth['release_group_id'] and start<=e['time_s']<stop for e in truth['events']),
            maximum_min_corner_clearance_mm=float(truth_height.max()),maximum_rotation_deg=float(angles_t.max()),final_rotation_deg=float(angles_t[-1]),
            final_rotation=np.array(samples[-1]['rotation']).tolist()),
        detector=dict(height_reversal_candidate=observed_reversal,maximum_min_corner_clearance_mm=float(observed_height.max()),
            maximum_rotation_deg=float(angles_d.max()),final_rotation_deg=float(angles_d[-1]),final_rotation=dr[-1].as_matrix().tolist()),
        difference=dict(maximum_min_corner_clearance_mm=float(observed_height.max()-truth_height.max()),
            maximum_rotation_deg=float(angles_d.max()-angles_t.max()),final_rotation_deg=float(angles_d[-1]-angles_t[-1])),
        acceptance='needs_review; clearance/reversal diagnostics are not measured rebound accuracy')
