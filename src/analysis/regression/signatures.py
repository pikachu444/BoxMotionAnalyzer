"""Small signatures and full, record-exact trajectory residual summaries."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

from src.utils.header_converter import parse_column_name
from .contracts import envelope, metric, validate_envelope, digest


def array(df, columns):
    return df[[parse_column_name(c) for c in columns]].to_numpy(float)


def scalar(df, name):
    column = parse_column_name(name)
    if column not in df or df[column].nunique(dropna=False) != 1:
        raise ValueError(f'Missing/nonconstant signature field {name}.')
    return df[column].iloc[0]


def finite_metric(value, *, absent='unavailable', reason='Missing analysis value'):
    if isinstance(value, str):
        return metric(value) if value else metric(status=absent, reason=reason)
    return metric(float(value)) if value is not None and np.isfinite(value) else metric(status=absent, reason=reason)


def runs(mask, times):
    mask = np.asarray(mask, bool)
    limits = np.r_[0, np.flatnonzero(mask[1:] != mask[:-1]) + 1, len(mask)]
    return [dict(start_record=int(a), end_record_exclusive=int(b),
                 first_time_s=float(times[a]), last_time_s=float(times[b - 1]))
            for a, b in zip(limits[:-1], limits[1:]) if b > a and mask[a]]


def pose_trajectory(df, geometry):
    times = df.index.to_numpy(float)
    indices = array(df, ['Source_OriginalRecordIndex'])[:, 0]
    center = array(df, [f'P_T{a}' for a in 'XYZ'])
    rotvec = array(df, [f'P_R{a}' for a in 'XYZ'])
    corners = array(df, [f'C{i}_{a}' for i in range(1, 9) for a in 'XYZ']).reshape(-1, 8, 3)
    valid = np.isfinite(center).all(axis=1) & np.isfinite(rotvec).all(axis=1) & np.isfinite(corners).all(axis=(1, 2))
    rotations = np.full((len(df), 3, 3), np.nan)
    rotations[valid] = Rotation.from_rotvec(rotvec[valid]).as_matrix()
    return dict(original_record_index=indices, raw_time_s=times, geocenter_position_mm=center,
                rotation_matrix=rotations, corners_mm=corners,
                floor_height_mm=corners[:, :, 1] - geometry['floor_y_mm'], valid_mask=valid)


def residual_guard(actual, reference, tolerance):
    """Every row and every mask is required; no intersection or interpolation."""
    failures = []
    keys = ('original_record_index', 'raw_time_s', 'geocenter_position_mm',
            'rotation_matrix', 'corners_mm', 'floor_height_mm', 'valid_mask')
    ref = {k: np.asarray(reference[k], dtype=bool if k == 'valid_mask' else float) for k in keys}
    n = len(ref['raw_time_s'])
    shapes = dict(original_record_index=(n,), raw_time_s=(n,), geocenter_position_mm=(n, 3),
                  rotation_matrix=(n, 3, 3), corners_mm=(n, 8, 3), floor_height_mm=(n, 8), valid_mask=(n,))
    for k in keys:
        if ref[k].shape != shapes[k] or np.asarray(actual[k]).shape != shapes[k]:
            failures.append(k + ': shape/required sample mismatch')
    if failures:
        return dict(status='fail', failures=failures, reference_sha256=digest(reference), checked_samples=0, residuals={})
    for k in ('original_record_index', 'raw_time_s', 'valid_mask'):
        if not np.array_equal(actual[k], ref[k]):
            failures.append(k + ': exact correspondence mismatch')
    valid = ref['valid_mask']
    # Every finite field must agree with the approved mask; NaN -> zero fails.
    for k in ('geocenter_position_mm', 'rotation_matrix', 'corners_mm', 'floor_height_mm'):
        for name, data in (('actual', np.asarray(actual[k])), ('reference', ref[k])):
            finite = np.isfinite(data.reshape(n, -1)).all(axis=1)
            all_missing = np.isnan(data.reshape(n, -1)).all(axis=1)
            if not np.array_equal(finite, valid) or not np.all(all_missing[~valid]):
                failures.append(f'{k}: {name} finite/unavailable mask mismatch')
    # Reference SO(3) is a schema contract, not repaired by scipy projection.
    if valid.any():
        for name, data in (('actual', actual['rotation_matrix']), ('reference', ref['rotation_matrix'])):
            r = np.asarray(data)[valid]
            if not np.isfinite(r).all() or not np.allclose(r @ r.transpose(0, 2, 1), np.eye(3), atol=1e-9, rtol=0) or not np.allclose(np.linalg.det(r), 1., atol=1e-9, rtol=0):
                failures.append(f'{name}: invalid SO3 matrix')
    residuals = {}
    if not failures:
        difference = np.asarray(actual['geocenter_position_mm'])[valid] - ref['geocenter_position_mm'][valid]
        relative = ref['rotation_matrix'][valid].transpose(0, 2, 1) @ np.asarray(actual['rotation_matrix'])[valid]
        errors = dict(center_mm=np.linalg.norm(difference, axis=1),
            rotation_deg=np.degrees(Rotation.from_matrix(relative).magnitude()) if valid.any() else np.array([]),
            corner_mm=np.linalg.norm(np.asarray(actual['corners_mm'])[valid] - ref['corners_mm'][valid], axis=-1),
            height_mm=np.abs(np.asarray(actual['floor_height_mm'])[valid] - ref['floor_height_mm'][valid]))
        scales = dict(center_mm=np.linalg.norm(ref['geocenter_position_mm'][valid], axis=1),
                      rotation_deg=np.zeros(int(valid.sum())),
                      corner_mm=np.linalg.norm(ref['corners_mm'][valid], axis=-1),
                      height_mm=np.abs(ref['floor_height_mm'][valid]))
        for key, values in errors.items():
            spec = tolerance['bounds'][key]
            limit = spec['absolute'] + spec['relative'] * scales[key]
            bad = values > limit
            bad_rows = bad if bad.ndim == 1 else bad.any(axis=1)
            first = int(np.flatnonzero(bad_rows)[0]) if bad_rows.any() else None
            residuals[key] = dict(maximum=float(values.max()) if values.size else None,
                violations=int(bad.sum()), first_violation_raw_time_s=float(ref['raw_time_s'][valid][first]) if first is not None else None,
                tolerance=spec, per_corner_maximum=values.max(axis=0).tolist() if values.ndim == 2 and values.size else None)
            if bad.any():
                failures.append(key + ': tolerance exceeded')
    return dict(status='fail' if failures else 'pass', failures=failures,
                reference_sha256=digest(reference), checked_samples=int(valid.sum()),
                approved_unavailable_samples=int((~valid).sum()), residuals=residuals)


def compare_metrics(expected, actual, tolerance):
    comparisons = {}
    for key, before in expected.items():
        after = actual.get(key)
        passed = after is not None and before['status'] == after['status']
        delta, spec = None, None
        if passed and before['status'] == 'valid':
            a, b = after['value'], before['value']
            if isinstance(b, (int, float)) and not isinstance(b, bool):
                delta = float(a) - float(b) if isinstance(a, (int, float)) else None
                spec = tolerance['bounds'][before['tolerance']]
                passed = delta is not None and np.isfinite(delta) and abs(delta) <= spec['absolute'] + spec['relative'] * abs(b)
            else:
                passed = a == b
        elif passed:
            passed = after['value'] is None and before['value'] is None
        comparisons[key] = dict(expected=before, actual=after, difference=delta, tolerance=spec,
                                status='pass' if passed else 'fail')
    return comparisons


def scenario_guard(artifact, reference, tolerance):
    """Check exported sample heights and local velocities from independent pose.

    The finite-difference stencil is explicit test geometry, not copied saved
    Velocity columns. Equal-height corner ties permit either existing group.
    """
    times = np.asarray(reference['raw_time_s'], float)
    match = np.flatnonzero(times == artifact['scenario_sample_time_s'])
    if len(match) != 1:
        return dict(status='fail', reason='Scenario sample has no exact reference time.')
    i = int(match[0])
    if i == 0 or i == len(times) - 1 or not np.asarray(reference['valid_mask'])[i-1:i+2].all():
        return dict(status='fail', reason='Scenario requires independent neighboring valid poses.')
    r = np.asarray(reference['rotation_matrix'], float)
    center = np.asarray(reference['geocenter_position_mm'], float)
    world_velocity = (center[i+1] - center[i-1]) / (times[i+1] - times[i-1])
    angular_world = Rotation.from_matrix(r[i+1] @ r[i-1].T).as_rotvec() / (times[i+1] - times[i-1])
    expected = {}
    for prefix, vector, bound, scale in (('TRA_VEL_',r[i].T @ world_velocity,'velocity_m_s',1000.),
                                        ('ANG_VEL_',r[i].T @ angular_world,'angular_rad_s',1.)):
        for axis, value in zip('XYZ',vector):
            expected[prefix+axis] = dict(**metric(float(value / scale)), tolerance=bound)
    actual = {k:metric(float(v / (1000. if k.startswith('TRA') else 1.))) for k,v in artifact['scenario_velocities'].items()}
    heights = np.asarray(reference['floor_height_mm'], float)[i]
    ids = [int(corner[1:])-1 for corner,_ in artifact['scenario_offsets']]
    shape_ok = len(ids) == len(set(ids)) == 3 and (all(k<4 for k in ids) or all(k>=4 for k in ids))
    if shape_ok:
        group = list(range(0,4)) if all(k<4 for k in ids) else list(range(4,8))
        roundoff = 1e-9
        permitted_group = min(heights[group]) <= min(heights) + roundoff
        omitted = list(set(group)-set(ids))
        lowest_three = max(heights[ids]) <= min(heights[omitted]) + roundoff
        ordered = np.all(np.diff(heights[ids]) >= -roundoff)
        shape_ok = bool(permitted_group and lowest_three and ordered)
    for j,(corner,value) in enumerate(artifact['scenario_offsets']):
        expected['height_'+corner] = dict(**metric(float(heights[ids[j]])), tolerance='height_mm')
        actual['height_'+corner] = metric(float(value))
    checks = compare_metrics(expected,actual,tolerance)
    return dict(status='pass' if shape_ok and all(c['status']=='pass' for c in checks.values()) else 'fail',
                sample_raw_time_s=float(times[i]), corner_group_valid=shape_ok, comparisons=checks)


def scene_signature(df, fixture, decision, impact, artifact, residual):
    g = fixture['geometry']
    traj = pose_trajectory(df, g)
    valid, times = traj['valid_mask'], traj['raw_time_s']
    summary = lambda key: scalar(df, 'DropPostureSummary_' + key)
    unavailable_contact = summary('ContactState') == 'Unavailable'
    detected = str(summary('T1Detected')).lower() in ('true', '1', '1.0')
    t1 = finite_metric(summary('T1MinusTimeSec'), absent='unavailable' if unavailable_contact else 'not_detected') if detected else metric(status='unavailable' if unavailable_contact else 'not_detected', reason=str(summary('ContactState')))
    count = int(summary('ImpactEventCount'))
    t2 = metric(status='unavailable' if unavailable_contact or count > 1 else 'not_detected',
                reason='Legacy contact-set sequence does not serialize subsequent event times' if count > 1 else str(summary('ContactState')))
    metrics = dict(t1=t1, t2=t2, contact_state=finite_metric(summary('ContactState')),
                   impact_sequence=finite_metric(summary('ImpactSequence'), absent='not_detected'),
                   reference_face=finite_metric(summary('ReferenceFace')),
                   observed_first_contact=finite_metric(summary('FirstImpactContact'), reason='No recorded geometric contact'))
    for name in ('BetaAtT1MinusDeg', 'ThetaLongAtT1MinusDeg', 'ThetaShortAtT1MinusDeg', 'DeltaHAtT1Minus_mm',
                 'MaxBetaDeg', 'MaxAbsThetaLongDeg', 'MaxAbsThetaShortDeg', 'MaxDeltaH_mm', 'ContactConfidence'):
        metrics[name] = finite_metric(summary(name), reason='Whole-record first-event diagnostic unavailable')
    for key, value in impact.metrics.items():
        metrics[key] = metric(status='unavailable', reason=value.reason) if value.reason else finite_metric(value.value)
    corners = traj['corners_mm']
    heights = traj['floor_height_mm']
    rotations = traj['rotation_matrix']
    adjacent = valid[:-1] & valid[1:]
    position_jumps = np.linalg.norm(np.diff(traj['geocenter_position_mm'], axis=0)[adjacent], axis=1)
    relative = rotations[:-1][adjacent].transpose(0, 2, 1) @ rotations[1:][adjacent]
    angles = np.degrees(Rotation.from_matrix(relative).magnitude()) if adjacent.any() else np.array([])
    valid_indices = np.flatnonzero(valid)
    final_rotation = metric(status='unavailable', reason='No valid pose')
    max_rotation = final_rotation
    if len(valid_indices):
        r = rotations[valid_indices[0]].T @ rotations[valid]
        values = np.degrees(Rotation.from_matrix(r).magnitude())
        final_rotation, max_rotation = metric(float(values[-1])), metric(float(values.max()))
    metrics.update(final_rotation_deg=final_rotation, maximum_rotation_deg=max_rotation)
    samples = []
    reference_time = t1['value'] if t1['status'] == 'valid' else None
    targets = ([reference_time + dt for dt in (-.04, 0, .04)] if reference_time is not None else [])
    targets += [float(times[0]), float(times[len(times) // 2]), float(times[-1])]
    for target in targets:
        i = int(np.argmin(np.abs(times - target)))
        def values(v):
            return np.asarray(v).tolist() if valid[i] else None
        center = traj['geocenter_position_mm'][i]
        body = center - rotations[i] @ np.asarray(g['origin_to_geocenter_mm']) if valid[i] else np.full(3, np.nan)
        com = body + rotations[i] @ np.asarray(g['origin_to_com_mm']) if valid[i] else np.full(3, np.nan)
        samples.append(envelope('PoseSample', original_record_index=int(traj['original_record_index'][i]),
            raw_time_s=float(times[i]), relative_time_s=float(times[i] - reference_time) if reference_time is not None else None,
            reference_event='t1_minus' if reference_time is not None else 'unavailable', target_time_s=target,
            sample_time_error_s=float(times[i] - target), geocenter_position_mm=values(center),
            body_origin_mm=values(body), com_position_mm=values(com), rotation_matrix=values(rotations[i]),
            corners_mm=values(corners[i]), floor_height_mm=values(heights[i]), valid_mask=bool(valid[i]),
            world_frame=g['world_frame'], local_frame=g['local_frame'], rotation_convention=g['rotation_convention'],
            origin_to_geocenter_mm=g['origin_to_geocenter_mm'], origin_to_com_mm=g['origin_to_com_mm']))
    sources = df[('Info', 'Pose', 'Source')].fillna('Unavailable').astype(str)
    return envelope('SceneSignature', review_id=decision['review_id'], source_sha256=fixture['raw_sha256'],
        original_interval=decision['anchor'], stored_interval=artifact['saved_original_record_indices'],
        slice_mode=decision['slice_mode'], padding_rows=decision['padding_rows'], events=dict(
            t1=dict(**t1, kind='precontact_geometric_sample', clock='raw'), t2=dict(**t2, kind='legacy_contact_set_transition', clock='raw'),
            ordered=True, interval_s=metric(status='unavailable', reason='No evaluable t2'),
            policy='existing-whole-record-contact-v1', matching='fixed first event; no t2 realignment'),
        metrics=metrics, intended_contact=dict(value=decision.get('intended_contact'), status='unavailable' if not decision.get('intended_contact') else 'valid', evidence=decision['evidence']),
        observed_contact=metrics['observed_first_contact'], target_posture_error=metric(status='unavailable', reason='No independently approved target posture'),
        cmin_margin_mm=metric(float(np.min(np.sort(heights[valid], axis=1)[:, 1] - np.sort(heights[valid], axis=1)[:, 0]))) if valid.any() else metric(status='unavailable', reason='No valid corners'),
        rebound=dict(status='unavailable', value=None, reason='No independently approved rebound event in this protocol'),
        final_face_observation=metrics['final_face'], guards=dict(
            maximum_center_jump_mm=float(position_jumps.max()) if position_jumps.size else None,
            maximum_rotation_jump_deg=float(angles.max()) if angles.size else None,
            corner_min_mm=np.min(corners[valid], axis=0).tolist() if valid.any() else None,
            corner_max_mm=np.max(corners[valid], axis=0).tolist() if valid.any() else None,
            unavailable_intervals=runs(~valid, times), valid_ratio=float(valid.mean()),
            pose_sources=sources.value_counts().to_dict(),
            fallback_ratio=float(sources.str.contains('Fallback').mean()), residual=residual),
        warnings=['Synthetic software evidence; measured accuracy/calibration pending #104'],
        artifacts=artifact, representative_samples=samples)
