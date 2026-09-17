"""Serialized analytical observations exercise grouping, not real trial accuracy."""
import json
import shutil

import pandas as pd
import pytest

from impact_metric_fixtures import make_frame, write_proc, REVIEW, SUMMARY
from src.analysis.compare.data_model import ComparisonModel


def load_frame(model, path, frame):
    frame.to_csv(path, index=False)
    return model.load_file(str(path))


def repeats(tmp_path):
    model = ComparisonModel()
    names = [model.load_file(str(write_proc(tmp_path / f'trial_{i}.proc',
             velocity=(3., -float(i), 0.), source_sha256=str(i) * 64)))
             for i in (1, 2, 3)]
    return model, names


def test_distinct_observations_use_individual_heights_and_reopen_unchanged(tmp_path):
    model, names = repeats(tmp_path)
    before = {name: (tmp_path / name).read_bytes() for name in names}
    result = model.get_impact_comparison()
    assert all(not file['reasons'] for file in result['files'].values())
    assert result['statistics']['vertical_velocity'] == pytest.approx(
        dict(n=3, mean=-2., min=-3., max=-1., range=2.))
    heights = result['statistics']['equivalent_height']
    # Mean of v_i^2/(2g), not the height obtained from the mean velocity.
    expected = 1000. * (1. + 4. + 9.) / (3. * 2. * 9.80665)
    assert heights['mean'] == pytest.approx(expected)
    assert heights['mean'] != pytest.approx(1000. * 4. / (2. * 9.80665))
    reopened = ComparisonModel()
    for name in names:
        reopened.load_file(str(tmp_path / name))
    assert reopened.get_impact_comparison()['statistics'] == result['statistics']
    assert before == {name: (tmp_path / name).read_bytes() for name in names}


def test_missing_components_change_only_their_own_counts(tmp_path):
    model, _ = repeats(tmp_path)
    frame = make_frame(source_sha256='d' * 64).drop(columns=[('Position', 'CoM', 'P_TX')])
    name = load_frame(model, tmp_path / 'missing_x.proc', frame)
    stats = model.get_impact_comparison()['statistics']
    assert stats['vertical_velocity']['n'] == 4
    assert stats['horizontal_speed']['n'] == 3
    assert stats['angular_speed']['n'] == 4
    assert stats['equivalent_height']['n'] == 4
    assert model.impact_results[name].metrics['horizontal_speed'].reason
    # Final face is absent in the real pipeline too: never replace it by reference face.
    assert stats['final_face']['n'] == 0
    assert stats['final_face']['reference'] is None


def test_contact_counts_are_diagnostic_baseline_agreement(tmp_path):
    model, names = repeats(tmp_path)
    frame = make_frame(source_sha256='d' * 64)
    # Production _contact_label emits an unbraced ID for a single corner.
    frame[(*SUMMARY, 'FirstImpactContact')] = 'C3'
    changed = load_frame(model, tmp_path / 'different_contact.proc', frame)
    stats = model.get_impact_comparison()['statistics']['first_contact']
    assert stats == dict(n=4, counts={'{C1,C2}': 3, 'C3': 1}, reference='{C1,C2}', matching=3)
    model.set_baseline(changed)
    assert model.get_impact_comparison()['statistics']['first_contact']['matching'] == 1
    model.remove_file(changed)
    assert changed not in model.impact_results
    assert model.baseline_name == names[0]
    assert model.get_impact_comparison()['statistics']['first_contact']['n'] == 3


def test_copies_and_corrected_variants_do_not_inflate_repeat_count(tmp_path):
    model, names = repeats(tmp_path)
    duplicate_path = tmp_path / 'copy.proc'
    shutil.copyfile(tmp_path / names[0], duplicate_path)
    duplicate = model.load_file(str(duplicate_path))
    frame = pd.read_csv(tmp_path / names[0], header=[0, 1, 2])
    payload = json.loads(frame[REVIEW].iloc[0])
    payload['source_sha256'] = 'f' * 64
    frame[REVIEW] = json.dumps(payload)
    frame[('Info', 'MarkerCorrection', 'OriginalSourceSha256')] = '1' * 64
    corrected = load_frame(model, tmp_path / 'corrected.proc', frame)
    result = model.get_impact_comparison()
    assert result['statistics']['vertical_velocity']['n'] == 3
    for name in (duplicate, corrected):
        assert any('already counted' in reason for reason in result['files'][name]['reasons']), result['files'][name]['reasons']
    model.set_baseline(duplicate)
    result = model.get_impact_comparison()
    assert result['files'][duplicate]['reasons'] == []
    assert result['files'][names[0]]['reasons']
    assert result['statistics']['vertical_velocity']['n'] == 3


@pytest.mark.parametrize('source_sha', ['0' * 64, '01' * 32, '1' * 64])
def test_numeric_original_capture_digest_survives_loading_exactly(tmp_path, source_sha):
    model = ComparisonModel()
    frame = make_frame(source_sha256='c' * 64)
    column = ('Info', 'MarkerCorrection', 'OriginalSourceSha256')
    frame[column] = source_sha
    name = load_frame(model, tmp_path / 'numeric_digest.proc', frame)
    assert model.datasets[name][column].iloc[0] == source_sha
    assert isinstance(model.datasets[name][column].iloc[0], str)
    assert model.impact_results[name].observation_key[0] == source_sha
    assert model.get_impact_comparison()['files'][name]['reasons'] == []


@pytest.mark.parametrize('source', ['mujoco_synthetic', 'handcrafted_dummy', 'public_external', 'unknown_legacy'])
def test_synthetic_and_other_sources_never_enter_declared_real_statistics(tmp_path, source):
    # These are schema declarations in fabricated files, never actual real evidence.
    model = ComparisonModel()
    frame = make_frame()
    frame[('Info', 'Artifact', 'SourceKind')] = 'real'
    load_frame(model, tmp_path / 'declared_real.proc', frame)
    candidate = make_frame(source_sha256='b' * 64, velocity=(0., -100., 0.))
    candidate[('Info', 'Artifact', 'SourceKind')] = source
    name = load_frame(model, tmp_path / 'other.proc', candidate)
    result = model.get_impact_comparison()
    assert any('SourceKind' in reason for reason in result['files'][name]['reasons'])
    assert result['source'] == 'real'
    assert result['statistics']['vertical_velocity']['n'] == 1
    assert result['statistics']['vertical_velocity']['mean'] == pytest.approx(-4.)


@pytest.mark.parametrize('field', ['MarkerLayoutHash', 'ModelId', 'ProcessingSemanticsVersion'])
def test_incompatible_layout_model_or_processing_excluded_from_every_statistic(tmp_path, field):
    model, _ = repeats(tmp_path)
    frame = make_frame(source_sha256='d' * 64)
    frame[('Info', 'Artifact', field)] = 'e' * 64
    name = load_frame(model, tmp_path / 'incompatible.proc', frame)
    result = model.get_impact_comparison()
    assert any(field in reason for reason in result['files'][name]['reasons'])
    assert result['statistics']['vertical_velocity']['n'] == 3
    assert result['statistics']['first_contact']['n'] == 3


def test_supported_diagnostics_survive_unsupported_pose_processing(tmp_path):
    model = ComparisonModel()
    for i in (1, 2, 3):
        load_frame(model, tmp_path / f'smoothed_{i}.proc',
                   make_frame(marker_smoothing=True, source_sha256=str(i) * 64))
    result = model.get_impact_comparison()
    assert result['statistics']['vertical_velocity']['n'] == 0
    assert result['statistics']['first_contact']['n'] == 3
    assert result['statistics']['contact_confidence']['n'] == 3


def test_malformed_optional_review_still_opens_for_individual_inspection(tmp_path):
    model = ComparisonModel()
    frame = make_frame()
    payload = json.loads(frame[REVIEW].iloc[0])
    payload['identity'] = None
    frame[REVIEW] = json.dumps(payload)
    name = load_frame(model, tmp_path / 'malformed_review.proc', frame)
    assert name in model.datasets
    assert model.get_summary_differences()[name]['summary']['ContactConfidence'] == .75
    assert model.get_timeseries_data('Position', 'CoM', 'P_TY', individual=name)
    result = model.get_impact_comparison()
    assert result['files'][name]['reasons']
    assert result['statistics']['vertical_velocity']['n'] == 0


def test_empty_after_last_removal(tmp_path):
    model, names = repeats(tmp_path)
    for name in names:
        model.remove_file(name)
    assert model.get_impact_comparison() == dict(files={}, statistics={}, source=None)
    assert not model.impact_results


@pytest.mark.parametrize('fault', ['no_impact', 'missing_time', 'nonfinite_time', 'off_timeline',
                                 'row_conflict', 'duplicate_column', 'resampled', 'tracking_jump'])
def test_stale_event_reopens_with_zero_diagnostic_counts_and_reasons(tmp_path, fault):
    frame = make_frame(result_resampling=fault == 'resampled')
    column = (*SUMMARY, 'FirstImpactTimeSec')
    if fault == 'no_impact':
        frame[(*SUMMARY, 'ImpactDetected')] = False
        frame[(*SUMMARY, 'ContactState')] = 'NoContact'
    elif fault == 'missing_time':
        frame = frame.drop(columns=[column])
    elif fault == 'nonfinite_time':
        frame[column] = float('inf')
    elif fault == 'off_timeline':
        frame[column] = .049
    elif fault == 'row_conflict':
        frame.loc[2, column] = .040
    elif fault == 'duplicate_column':
        frame = pd.concat([frame, frame[[column]]], axis=1)
    elif fault == 'tracking_jump':
        review = json.loads(frame[REVIEW].iloc[0])
        review['candidate'].update(motion='tracking_jump', evidence_class='tracking_jump')
        frame[REVIEW] = json.dumps(review)
    from src.analysis.compare.impact_metrics import calculate_impact_metrics
    direct = calculate_impact_metrics(frame)
    path = tmp_path / 'stale.proc'
    frame.to_csv(path, index=False)
    before = path.read_bytes()
    for _ in range(2):
        model = ComparisonModel()
        name = model.load_file(str(path))
        result = model.get_impact_comparison()
        for key in ('first_contact', 'contact_confidence'):
            assert result['statistics'][key]['n'] == 0
            assert result['files'][name]['result'].metrics[key] == direct.metrics[key]
            assert direct.metrics[key].value is None and direct.metrics[key].reason
        details = model.get_summary_differences()[name]
        assert details['summary']['FirstImpactContact'] == '{C1,C2}'
        assert details['summary']['ContactConfidence'] == .75
        assert details['diffs']['FirstImpactContact'] is None
        assert details['diffs']['ContactConfidence'] is None
        assert details['metric_reasons']['FirstImpactContact']
        assert path.read_bytes() == before


def test_invalid_baseline_diagnostic_cannot_produce_raw_summary_agreement(tmp_path):
    model = ComparisonModel()
    invalid = make_frame()
    invalid[(*SUMMARY, 'ImpactDetected')] = False
    load_frame(model, tmp_path / 'invalid.proc', invalid)
    valid = load_frame(model, tmp_path / 'valid.proc', make_frame(source_sha256='b' * 64))
    details = model.get_summary_differences()
    assert details[valid]['diffs']['FirstImpactContact'] is None
    assert details[valid]['diffs']['ContactConfidence'] is None
    stats = model.get_impact_comparison()['statistics']
    assert stats['first_contact'] == dict(n=1, counts={'{C1,C2}': 1}, reference=None, matching=None)
    assert stats['contact_confidence'] == dict(n=1, mean=.75, min=.75, max=.75, range=0.)
