"""Opaque PUB10 source identity. Sampled visibility/fault truth never enters Raw."""
import json
import re
from numbers import Integral,Real

import numpy as np

from .marker_profile_identity import envelope, validate_envelope, digest

FIELD = 'ObservationMetadataJson'


def build(result):
    manifest=result['manifest']; profile=manifest['observation_evidence']['profile']
    value=envelope('ObservationSourceMetadata',source_kind=manifest['source_kind'],
        marker_profile_hash=manifest['layout_hash'],profile_id=profile['profile_id'],
        model=profile['model'],profile_hash=profile['content_hash'],adapter=profile['adapter'],
        settings_hash=digest(dict(profile_hash=profile['content_hash'],events=manifest['events'])),
        seed=manifest['seed'],calibration_status='uncalibrated',details='evaluation-only',
        clock=dict(samples=len(result['time_s']),first_s=float(result['time_s'][0]),last_s=float(result['time_s'][-1]),
            recorded_time_hash=digest(result['time_s'].tolist()),recorded_frame_hash=digest(result['frame'].tolist()),
            record_hashes=[digest([float(t),int(f)]) for t,f in zip(result['time_s'],result['frame'])]))
    value['content_hash']=digest(value)
    return value


def artifact_observation(artifact):
    text=artifact.get(FIELD)
    if text is None or text=='':
        if artifact.get('GeneratorVersion')=='marker-corruption-1.1':
            raise ValueError('PUB10 observation source declaration is required.')
        return None
    from src.simulation.observation_profile import MODEL,ADAPTERS
    from .marker_profile_identity import artifact_identity
    value=json.loads(text)
    validate_envelope(value,'ObservationSourceMetadata')
    if set(value)!={'schema_version','plan_spec','object_type','source_kind','marker_profile_hash','profile_id','model',
            'profile_hash','adapter','settings_hash','seed','calibration_status','details','clock','content_hash'}:
        raise ValueError('Unexpected observation source fields; fault truth is private.')
    if value['content_hash']!=digest({k:v for k,v in value.items() if k!='content_hash'}):
        raise ValueError('Stale observation source identity.')
    if (value['source_kind'] not in ('mujoco_synthetic','handcrafted_dummy') or value['source_kind']!=artifact.get('SourceKind')
            or value['model']!=MODEL or value['adapter'] not in ADAPTERS or value['calibration_status']!='uncalibrated'
            or value['details']!='evaluation-only' or not isinstance(value['profile_id'],str) or not value['profile_id'].strip()
            or type(value['seed']) is not int or value['seed']<0):
        raise ValueError('Unsupported observation source/model/adapter/seed/calibration.')
    for key in ('marker_profile_hash','profile_hash','settings_hash'):
        if not isinstance(value[key],str) or re.fullmatch('[0-9a-f]{64}',value[key]) is None:
            raise ValueError('Invalid observation '+key)
    identity=artifact_identity(artifact)
    if identity is None or identity['profile_hash']!=value['marker_profile_hash']:
        raise ValueError('Observation marker source identity mismatch.')
    clock=value['clock']
    if not isinstance(clock,dict) or set(clock)!={'samples','first_s','last_s','recorded_time_hash','recorded_frame_hash','record_hashes'}:
        raise ValueError('Invalid observation clock fields.')
    if type(clock['samples']) is not int or clock['samples']<2:
        raise ValueError('Invalid observation sample count.')
    for key in ('first_s','last_s'):
        if type(clock[key]) not in (int,float) or not np.isfinite(clock[key]):raise ValueError('Invalid observation clock.')
    if clock['last_s']<=clock['first_s']:raise ValueError('Observation clock must increase.')
    for key in ('recorded_time_hash','recorded_frame_hash'):
        if not isinstance(clock[key],str) or re.fullmatch('[0-9a-f]{64}',clock[key]) is None:
            raise ValueError('Invalid observation record identity.')
    records=clock['record_hashes']
    if (not isinstance(records,list) or len(records)!=clock['samples']
            or any(not isinstance(h,str) or re.fullmatch('[0-9a-f]{64}',h) is None for h in records)
            or len(set(records))!=len(records)):
        raise ValueError('Invalid observation original-record identities.')
    return value


def validate_records(artifact,times,frames=None,*,complete=False):
    value=artifact_observation(artifact)
    if value is None:return
    t=np.asarray(times,dtype=float);clock=value['clock']
    if (t.ndim!=1 or not len(t) or not np.isfinite(t).all() or np.any(np.diff(t)<=0)
            or t[0]<clock['first_s']-1e-12 or t[-1]>clock['last_s']+1e-12):
        raise ValueError('Observation timestamps conflict with source clock.')
    if frames is None:raise ValueError('Observation requires original frame records.')
    raw_frames=np.asarray(frames,dtype=object)
    if raw_frames.shape!=t.shape:
        raise ValueError('Invalid observation frame records.')
    f=[]
    for raw in raw_frames:
        if isinstance(raw,(bool,np.bool_)):raise ValueError('Boolean observation frame.')
        if isinstance(raw,str) and re.fullmatch('[0-9]+',raw):frame=int(raw)
        elif isinstance(raw,Integral):frame=int(raw)
        elif isinstance(raw,Real) and np.isfinite(raw) and raw==int(raw):frame=int(raw)
        else:raise ValueError('Invalid observation frame record.')
        if not 0<=frame<2**63:raise ValueError('Observation frame outside int64.')
        f.append(frame)
    actual=[digest([float(at),int(frame)]) for at,frame in zip(t,f)]
    record_index={h:i for i,h in enumerate(clock['record_hashes'])}
    indices=[record_index.get(h,-1) for h in actual]
    if any(i<0 for i in indices) or any(a>=b for a,b in zip(indices,indices[1:])):
        raise ValueError('Observation timestamp/frame original-record mismatch.')
    if complete or len(t)==clock['samples']:
        if (len(t)!=clock['samples'] or digest(t.tolist())!=clock['recorded_time_hash']
                or t[0]!=clock['first_s'] or t[-1]!=clock['last_s']):
            raise ValueError('Observation timestamp/record identity mismatch.')
        if digest(f)!=clock['recorded_frame_hash']:
            raise ValueError('Observation frame/record identity mismatch.')
