"""Serialized .proc contract tests, not evidence of measured physical accuracy."""
import numpy as np
import pandas as pd
import pytest

from comparison_fixtures import write_proc, identity
from src.analysis.compare.data_model import ComparisonModel
from src.utils.artifact_metadata import FIELDS
from src.utils.result_time import TIME_COLUMN, LEGACY_TIME_COLUMN, T1_COLUMN, T1_DETECTED_COLUMN


def test_compatible_baseline_differences_and_time_alignment(tmp_path):
    model = ComparisonModel()
    first = model.load_file(str(write_proc(tmp_path / 'first.proc')))
    second = model.load_file(str(write_proc(tmp_path / 'second.proc', times=(4., 4.005, 4.01, 4.02), t1=4.01, offset=5)))
    assert model.exclusion_reasons(second) == []
    assert model.get_summary_differences()[second]['diffs']['BetaAtT1MinusDeg'] == pytest.approx(5)
    curves = model.get_timeseries_data('Analysis', 'DropPosture', 'ThetaLongDeg')
    np.testing.assert_allclose(curves[first].index, [-.01, 0, .01])
    np.testing.assert_allclose(curves[second].index, [-.01, -.005, 0, .01])
    # Original frames 100/104/108 are row IDs 0/1/2 only for rendering.
    handler = model.visualization_handlers[first]
    assert handler.n_frames == 3
    assert not handler.get_frame_data(1).empty
    assert model.playback_row(second, 0) == 2
    model.set_baseline(second)
    assert model.get_summary_differences()[first]['diffs']['BetaAtT1MinusDeg'] == pytest.approx(-5)
    model.remove_file(second)
    assert model.baseline_name == first


@pytest.mark.parametrize('field', [f for f in FIELDS if f != 'GeneratorVersion'])
def test_each_required_field_mismatch_or_missing_excludes(tmp_path, field):
    model = ComparisonModel()
    model.load_file(str(write_proc(tmp_path / 'baseline.proc')))
    path = write_proc(tmp_path / 'missing.proc')
    df = pd.read_csv(path, header=[0,1,2]).drop(columns=[('Info', 'Artifact', field)])
    df.to_csv(path, index=False)
    name = model.load_file(str(path))
    assert any(field in reason for reason in model.exclusion_reasons(name))
    assert model.get_summary_differences()[name]['diffs']['BetaAtT1MinusDeg'] is None


@pytest.mark.parametrize('field', [f for f in FIELDS if f != 'GeneratorVersion'])
def test_single_changed_identity_key_excludes(tmp_path, field):
    model = ComparisonModel()
    model.load_file(str(write_proc(tmp_path / 'baseline.proc')))
    path = write_proc(tmp_path / 'changed.proc')
    df = pd.read_csv(path, header=[0,1,2])
    col = ('Info','Artifact',field)
    df[col] = float(df[col].iloc[0]) + 1 if field.startswith('Box') else 'different-contract'
    df.to_csv(path, index=False)
    name = model.load_file(str(path))
    assert any(field in reason for reason in model.exclusion_reasons(name))


@pytest.mark.parametrize('source', ['real', 'public_external', 'mujoco_synthetic', 'unknown_legacy'])
def test_source_populations_separate_unit_declarations_only(tmp_path, source):
    model = ComparisonModel()
    model.load_file(str(write_proc(tmp_path / 'baseline.proc')))
    name = model.load_file(str(write_proc(tmp_path / 'other.proc', metadata=identity(SourceKind=source))))
    assert any('SourceKind' in reason for reason in model.exclusion_reasons(name))
    overlay = model.get_timeseries_data('Analysis', 'DropPosture', 'ThetaLongDeg')
    assert (name in overlay) == (source != 'unknown_legacy')


@pytest.mark.parametrize('times', [(1,1,1.1), (1, .9, 1.1), (1, float('nan'),1.1), (1,float('inf'),1.1)])
def test_invalid_time_retains_individual_rows_without_alignment(tmp_path, times):
    model = ComparisonModel()
    name = model.load_file(str(write_proc(tmp_path / 'invalid.proc', times=times)))
    assert not model.timelines[name].aligned
    assert model.playback_row(name, 0) is None
    assert not model.get_timeseries_data('Analysis', 'DropPosture', 'ThetaLongDeg')
    assert len(model.get_timeseries_data('Analysis', 'DropPosture', 'ThetaLongDeg', individual=name)[name]) == 3


@pytest.mark.parametrize('change', ['missing_time', 'legacy_only', 'conflict', 'missing_t1', 'false_t1', 't1_outside', 'varying_t1'])
def test_no_alignment_fallback(tmp_path, change):
    path = write_proc(tmp_path / 'invalid.proc')
    df = pd.read_csv(path, header=[0,1,2])
    if change in ('missing_time','legacy_only'):
        if change == 'legacy_only':
            df[LEGACY_TIME_COLUMN] = df[TIME_COLUMN]
        df = df.drop(columns=[TIME_COLUMN])
    elif change == 'conflict':
        df[LEGACY_TIME_COLUMN] = df[TIME_COLUMN] + 1
    elif change == 'missing_t1':
        df = df.drop(columns=[T1_COLUMN])
    elif change == 'false_t1':
        df[T1_DETECTED_COLUMN] = False
    elif change == 't1_outside':
        df[T1_COLUMN] = 200
    else:
        df[T1_COLUMN] = [1,1.01,1.02]
    df.to_csv(path,index=False)
    model = ComparisonModel()
    name = model.load_file(str(path))
    assert not model.timelines[name].aligned
    assert model.playback_row(name,0) is None


def test_identical_time_columns_are_not_duplicate_samples(tmp_path):
    path = write_proc(tmp_path / 'duplicate_columns.proc')
    df = pd.read_csv(path, header=[0,1,2])
    df = pd.concat([df, df[[TIME_COLUMN]]], axis=1)
    df.to_csv(path,index=False)
    model = ComparisonModel()
    name = model.load_file(str(path))
    assert model.timelines[name].aligned


def test_irregular_gap_has_no_clamp_or_bridge(tmp_path):
    model = ComparisonModel()
    name = model.load_file(str(write_proc(tmp_path / 'gap.proc', times=(1,1.008,1.031,2.,2.01), t1=1.008)))
    assert model.playback_row(name, .005) == 1
    assert model.playback_row(name, .5) is None
    assert model.playback_row(name, -10) is None
    assert model.playback_row(name, 10) is None
    series = model.get_timeseries_data('Analysis','DropPosture','ThetaLongDeg')[name]
    assert series.isna().sum() == 1
    assert len(series) == 6


@pytest.mark.parametrize('origin', [0.,1.,100.,1000.])
def test_exact_gap_limit_roundoff_and_true_excess(tmp_path, origin):
    from src.utils.result_time import exceeds_gap_limit, segmented_series
    model = ComparisonModel()
    times = origin + np.arange(11)/10
    name = model.load_file(str(write_proc(tmp_path / 'tenths.proc', times=times, t1=origin)))
    series = model.get_timeseries_data('Analysis','DropPosture','ThetaLongDeg')[name]
    assert series.isna().sum() == 0
    assert segmented_series(np.ones(11), times, .1, origin=origin).isna().sum() == 0
    assert model.playback_row(name, .05) == 0
    assert not exceeds_gap_limit(1.,1.1,.1)
    assert exceeds_gap_limit(1.,1.1 + 1e-10,.1)
    assert exceeds_gap_limit(origin, origin + .100001, .1)
    # A large absolute epoch must not enlarge the physical allowance.
    assert exceeds_gap_limit(1e12,1e12+.1001,.1)


@pytest.mark.parametrize('source', ['unknown_legacy','invalid-source'])
def test_source_only_missing_or_invalid_has_no_common_clock(tmp_path, source):
    model = ComparisonModel()
    name = model.load_file(str(write_proc(tmp_path / 'unknown.proc', metadata=identity(SourceKind=source))))
    assert model.timelines[name].times is not None
    assert not model.timelines[name].aligned
    assert model.elapsed_bounds() is None
    assert model.playback_row(name,0) is None
    assert not model.get_timeseries_data('Analysis','DropPosture','ThetaLongDeg')
    assert name in model.get_timeseries_data('Analysis','DropPosture','ThetaLongDeg',individual=name)


def test_empty_malformed_loading_is_atomic(tmp_path):
    model = ComparisonModel()
    path = tmp_path / 'empty.proc'
    path.write_text('')
    with pytest.raises(ValueError):
        model.load_file(str(path))
    assert model.datasets == {}
    assert model.baseline_name is None


def test_corner_and_text_summary_use_actual_baseline_categories(tmp_path):
    model = ComparisonModel()
    corner = ('Analysis', 'DropPostureSummary', 'CminAtT1MinusIndex')
    face = ('Analysis', 'DropPostureSummary', 'RefFaceAtT1Minus')
    paths = [write_proc(tmp_path / 'baseline.proc'), write_proc(tmp_path / 'other.proc')]
    for path, corner_id, face_name in zip(paths, [5, 6], ['BOTTOM', 'FRONT']):
        df = pd.read_csv(path, header=[0, 1, 2])
        df[corner] = corner_id
        df[face] = face_name
        df.to_csv(path, index=False)
        model.load_file(str(path))
    values = model.get_summary_differences()
    assert values['other.proc']['summary'][corner[2]] == 6
    assert values['other.proc']['diffs'][corner[2]] == 'C5'
    assert values['other.proc']['diffs'][face[2]] == 'BOTTOM'
    model.set_baseline('other.proc')
    values = model.get_summary_differences()
    assert values['baseline.proc']['diffs'][corner[2]] == 'C6'
    assert values['baseline.proc']['diffs'][face[2]] == 'FRONT'
    model.datasets['baseline.proc'][corner] = '6'
    assert model.get_summary_differences()['baseline.proc']['diffs'][corner[2]] == 'Match'
    # An invalid identifier cannot become a fractional physical difference.
    for invalid in (1.5, 0., 9., float('nan')):
        model.datasets['baseline.proc'][corner] = invalid
        values = model.get_summary_differences()['baseline.proc']
        assert values['diffs'][corner[2]] is None
        if np.isfinite(invalid):
            assert values['summary'][corner[2]] == invalid
