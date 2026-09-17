"""Public serialized counterexamples with literal statistics and analytic motion."""
from itertools import permutations
import json

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from impact_metric_fixtures import make_frame, REVIEW, SUMMARY, update_processing
from test_contact_comparison import contact_frame
from src.analysis.compare.data_model import ComparisonModel


def models(tmp_path, frames):
    paths = []
    for i, frame in enumerate(frames):
        path = tmp_path / f'variant_{i}.proc'
        frame.to_csv(path, index=False)
        paths.append(path)
    for order in permutations(paths):
        model = ComparisonModel()
        for path in order:
            model.load_file(str(path))
        for path in paths:
            model.set_baseline(path.name)
            yield model


def invariant_stats(result):
    return {key: {k: v for k, v in stat.items() if k not in ('reference', 'matching')}
            for key, stat in result['statistics'].items()}


@pytest.mark.parametrize('case,n,mean,minimum,maximum,span', [
    ('missing_y', 1, -4., -4., -4., 0.), ('equal', 1, -4., -4., -4., 0.),
    ('conflict', 0, None, None, None, None), ('distinct', 2, -3., -4., -2., 2.),
    ('all_invalid', 0, None, None, None, None),
])
def test_serial_impact_pair_all_orders_and_baselines(tmp_path, case, n, mean, minimum, maximum, span):
    a, b = make_frame(), make_frame()
    if case in ('missing_y', 'all_invalid'):
        a.loc[2, ('Position', 'CoM', 'P_TY')] = np.nan
    if case == 'all_invalid':
        b.loc[2, ('Position', 'CoM', 'P_TY')] = np.nan
    if case in ('conflict', 'distinct'):
        b = make_frame(velocity=(3., -2., 0.), source_sha256='b' * 64 if case == 'distinct' else 'a' * 64)
    prior = None
    for model in models(tmp_path, [a, b]):
        result = model.get_impact_comparison()
        stat = result['statistics']['vertical_velocity']
        assert stat['n'] == n
        for key, expected in dict(mean=mean, min=minimum, max=maximum, range=span).items():
            assert stat[key] is None if expected is None else stat[key] == pytest.approx(expected, rel=0, abs=1e-9)
        assert result['statistics']['horizontal_speed']['n'] == (2 if case == 'distinct' else 1)
        assert result['statistics']['first_contact']['n'] == (2 if case == 'distinct' else 1)
        current = invariant_stats(result)
        if prior is not None:
            assert current == prior
        prior = current
        if case == 'conflict':
            assert all(item['metric_resolution']['vertical_velocity']['status'] == 'conflict'
                       for item in result['files'].values())


@pytest.mark.parametrize('case,expected', [
    ('invalid_valid', (1, 1, 0, 0, 0)), ('equal', (1, 1, 0, 0, 0)),
    ('conflict', (0, 0, 0, 0, 1)), ('distinct', (2, 1, 1, 0, 0)),
    ('all_invalid', (0, 0, 0, 1, 0)),
])
def test_contact_pair_all_orders_and_baselines(tmp_path, case, expected):
    a, b = contact_frame(), contact_frame()
    if case in ('invalid_valid', 'all_invalid'):
        a.loc[10, ('Position', 'CoM', 'P_RX')] = np.nan
    if case == 'all_invalid':
        b.loc[10, ('Position', 'CoM', 'P_RX')] = np.nan
    if case in ('conflict', 'distinct'):
        b = contact_frame(observed='{C1,C5}', rotation=Rotation.from_euler('z', 30, degrees=True),
                          source='b' * 64 if case == 'distinct' else 'a' * 64)
    for model in models(tmp_path, [a, b]):
        stats = model.get_contact_comparison()['statistics']
        assert tuple(stats[k] for k in ('n', 'Match', 'Different', 'Unclear', 'conflicts')) == expected
        assert stats['excluded'] == 2 - stats['n'] - stats['Unclear']


def test_category_counts_and_references_are_separate(tmp_path):
    frames = [make_frame(source_sha256=c * 64) for c in 'abc']
    frames[2][(*SUMMARY, 'FirstImpactContact')] = 'C3'
    for model in models(tmp_path, frames):
        stat = model.get_impact_comparison()['statistics']['first_contact']
        assert stat['n'] == 3 and stat['counts'] == {'{C1,C2}': 2, 'C3': 1}
        assert stat['matching'] == (1 if model.baseline_name == 'variant_2.proc' else 2)


def test_invalid_event_never_revived_by_another_variant(tmp_path):
    invalid = make_frame()
    invalid[(*SUMMARY, 'ImpactDetected')] = False
    for model in models(tmp_path, [invalid, make_frame()]):
        result = model.get_impact_comparison()
        for key in ('first_contact', 'contact_confidence'):
            assert result['statistics'][key]['n'] == 1
            entry = result['files']['variant_0.proc']['metric_resolution'][key]
            assert entry['status'] == 'invalid' and entry['reason']
        reference = result['statistics']['first_contact']['reference']
        assert reference is None if model.baseline_name == 'variant_0.proc' else reference == '{C1,C2}'


@pytest.mark.parametrize('field,value', [('SourceKind', 'real'), ('ModelId', 'other'),
    ('BoxLengthMm', 201.), ('MarkerLayoutHash', 'c' * 64), ('ScenarioId', 'G02'),
    ('CoordinatePolicy', 'other'), ('UnitsPolicy', 'other'), ('processing', None)])
def test_incompatible_variants_cannot_conflict_with_population(tmp_path, field, value):
    a, b = make_frame(), make_frame(velocity=(3., -2., 0.))
    if field == 'processing':
        update_processing(b, lambda s: s['single_pass']['marker_smoothing'].update(enabled=True))
    else:
        b[('Info', 'Artifact', field)] = value
    for model in models(tmp_path, [a, b]):
        model.set_baseline('variant_0.proc')
        result = model.get_impact_comparison()
        assert result['statistics']['vertical_velocity']['n'] == 1
        assert result['statistics']['vertical_velocity']['mean'] == pytest.approx(-4., abs=1e-9)
        assert result['files']['variant_1.proc']['reasons']


def test_incompatible_intent_cannot_poison_contact(tmp_path):
    other = contact_frame(target=('TOP',))
    other[('Info', 'Artifact', 'SourceKind')] = 'real'
    for model in models(tmp_path, [contact_frame(), other]):
        model.set_baseline('variant_0.proc')
        stats = model.get_contact_comparison()['statistics']
        assert stats['n'] == 1 and stats['Match'] == 1 and stats['conflicts'] == 0


def test_corrected_copy_reopen_and_replacement_preserve_identity(tmp_path):
    original = make_frame()
    corrected = make_frame(source_sha256='c' * 64)
    corrected[('Info', 'MarkerCorrection', 'OriginalSourceSha256')] = 'a' * 64
    for model in models(tmp_path, [original, original.copy(), corrected]):
        result = model.get_impact_comparison()
        assert len(result['observations']) == 1
        assert result['statistics']['vertical_velocity']['n'] == 1
        metrics = next(iter(result['observations'].values()))
        assert len(metrics['vertical_velocity']['sources']) == 3
        assert all(v['sha256'] and v['path'] for v in metrics['vertical_velocity']['variants'])
    path = tmp_path / 'replacement.proc'
    make_frame(velocity=(3., -2., 0.)).to_csv(path, index=False)
    model.load_file(str(path), replace_name='variant_2.proc')
    assert model.get_impact_comparison()['statistics']['vertical_velocity']['n'] == 0
    model.remove_file('variant_2.proc')
    assert model.get_impact_comparison()['statistics']['vertical_velocity']['n'] == 1


def test_distinct_review_intervals_are_not_filename_or_scenario_duplicates(tmp_path):
    a, b = make_frame(), make_frame()
    b = b.iloc[1:].copy()
    b[('Info', 'Timeline', 'SliceStartSec')] = .008
    review = json.loads(b[REVIEW].iloc[0])
    review['candidate'].update(start=.008, auto_start=.008)
    b[REVIEW] = json.dumps(review)
    for model in models(tmp_path, [a, b]):
        assert len(model.get_impact_comparison()['observations']) == 2
        assert model.get_impact_comparison()['statistics']['vertical_velocity']['n'] == 2


def test_categorical_conflict_excludes_only_that_metric(tmp_path):
    a, b = make_frame(), make_frame()
    b[(*SUMMARY, 'FirstImpactContact')] = 'C3'
    for model in models(tmp_path, [a, b]):
        stats = model.get_impact_comparison()['statistics']
        assert stats['first_contact']['n'] == 0 and stats['first_contact']['counts'] == {}
        assert stats['vertical_velocity']['n'] == 1
        assert stats['contact_confidence']['n'] == 1


def test_different_contact_features_with_same_outcome_still_conflict(tmp_path):
    a = contact_frame(target=('TOP',))
    b = contact_frame(target=('TOP',), observed='{C1,C5}', rotation=Rotation.from_euler('z', 30, degrees=True))
    for model in models(tmp_path, [a, b]):
        assert all(result.outcome == 'Different' for result in model.contact_results.values())
        stats = model.get_contact_comparison()['statistics']
        assert stats['n'] == 0 and stats['conflicts'] == 1


def test_registration_incompatible_intent_is_separate(tmp_path):
    from src.analysis.pipeline.scene_detection import Registration
    other = contact_frame(target=('TOP',))
    review = json.loads(other[REVIEW].iloc[0])
    review['detection']['registration']['com_offset_mm'] = [0., 0., 0.]
    fingerprint = Registration(**review['detection']['registration']).fingerprint
    review['detection']['registration_sha256'] = fingerprint
    review['candidate']['intended_contact']['registration_sha256'] = fingerprint
    other[REVIEW] = json.dumps(review)
    for model in models(tmp_path, [contact_frame(), other]):
        assert model.get_contact_comparison()['statistics']['n'] == 1
        assert model.get_contact_comparison()['statistics']['conflicts'] == 0


@pytest.mark.parametrize('component,dependent', [('P_TX', {'horizontal_speed'}),
    ('P_TY', {'vertical_velocity', 'equivalent_height'}), ('P_RZ', {'angular_speed'})])
def test_duplicate_component_missingness_retains_independent_metrics(tmp_path, component, dependent):
    invalid, valid = make_frame(), make_frame()
    invalid.loc[2, ('Position', 'CoM', component)] = np.nan
    for model in models(tmp_path, [invalid, valid]):
        result = model.get_impact_comparison()
        for key in ('vertical_velocity', 'horizontal_speed', 'angular_speed', 'equivalent_height',
                    'first_contact', 'contact_confidence'):
            assert result['statistics'][key]['n'] == 1
            status = result['files']['variant_0.proc']['metric_resolution'][key]['status']
            assert status == ('invalid' if key in dependent else 'equivalent')


def test_rotation_missingness_with_offset_blocks_only_dependent_height(tmp_path):
    invalid, valid = make_frame(com_offset=(1., 0., 0.)), make_frame(com_offset=(1., 0., 0.))
    invalid.loc[2, ('Position', 'CoM', 'P_RZ')] = np.nan
    for model in models(tmp_path, [invalid, valid]):
        result = model.get_impact_comparison()
        assert result['statistics']['equivalent_height']['n'] == 1
        assert result['files']['variant_0.proc']['metric_resolution']['equivalent_height']['status'] == 'invalid'
        assert result['files']['variant_0.proc']['metric_resolution']['vertical_velocity']['status'] == 'equivalent'


def test_emitted_corrected_slice_proc_lineage_reaches_comparison_identity(tmp_path):
    """Exercise real metadata transport; this does not claim a pose refit."""
    import hashlib
    from types import SimpleNamespace
    import pandas as pd
    from test_marker_flip_artifact_io import _raw_bundle, _decisions
    from src.analysis.pipeline.artifact_io import (save_corrected_source_file, save_slice_file,
        read_slice_metadata, add_timeline_context_columns, save_proc_file)
    from src.analysis.pipeline.marker_flip import apply_approved_marker_permutations
    from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
    header, raw = _raw_bundle()
    original = tmp_path / 'capture.csv'
    raw.to_csv(original, index=False)
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    corrected = tmp_path / 'capture.corrected.csv'
    corrected_raw = apply_approved_marker_permutations(raw, header, _decisions())
    metadata = save_corrected_source_file(filepath=str(corrected), header_info=header,
        raw_data=corrected_raw, original_source_path=str(original), decisions=_decisions())
    keys = []
    for name, source, data, correction in [('original', original, raw, None),
                                          ('corrected', corrected, corrected_raw, metadata)]:
        review = json.loads(make_frame(times=[0., 1., 2., 3., 4., 5.])[REVIEW].iloc[0])
        review['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        sliced = tmp_path / (name + '.slice')
        save_slice_file(filepath=str(sliced), header_info=header, raw_data=data, source_path=str(source),
            full_start=0., full_end=5., user_start=0., user_end=5., box_dims=(200.,120.,80.),
            pad_rows=0, marker_correction_metadata=correction, scene_review_json=json.dumps(review))
        reopened = read_slice_metadata(str(sliced))
        context = WidgetSliceProcessing._build_timeline_context(SimpleNamespace(slice_metadata=reopened))
        output = tmp_path / (name + '.proc')
        save_proc_file(str(output), add_timeline_context_columns(
            pd.DataFrame({'Frame': range(6)}, index=pd.Index(range(6), name='Time')), context))
        model = ComparisonModel()
        loaded = model.load_file(str(output))
        keys.append(model.impact_results[loaded].observation_key)
    assert keys == [(digest, 0., 5., 'G01'), (digest, 0., 5., 'G01')]
