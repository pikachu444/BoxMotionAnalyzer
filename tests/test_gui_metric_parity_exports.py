"""Literal P04 export bytes and failure preservation, independent of writer output."""
import csv
import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analysis.pipeline import scenario_export
from src.analysis.pipeline.scenario_export import (
    atomic_write_scenario, automatic_offsets, scenario_bytes, scenario_text,
)


OFFSETS = [('C1', 0.), ('C2', 1.25), ('C3', 2.5)]
VELOCITIES = dict(ANG_VEL_X=1., ANG_VEL_Y=-2., ANG_VEL_Z=3.,
                  TRA_VEL_X=4., TRA_VEL_Y=-5., TRA_VEL_Z=6.)
POINT_GOLDEN = b',Velocity,Velocity\n,CoM,CoM\n,V_TX_ANA,V_TY_ANA\n0.1,1.25,-2.5\n'
CAE_GOLDEN = """1,Left
2,Right
3,Bottom
4,Top
5,Rear
6,Front
cat,Corner_Drop_2nd,drop_name,Trial_A,variable_1,LeftBottomRear,value_1,0.000000,variable_2,RightBottomRear,value_2,1.250000,variable_3,RightTopRear,value_3,2.500000,variable_4,OFFSET,value_4,0.0,variable_5,ANG_VEL_X,value_5,1.000000,variable_6,ANG_VEL_Y,value_6,-2.000000,variable_7,ANG_VEL_Z,value_7,3.000000,variable_8,TRA_VEL_X,value_8,4.000000,variable_9,TRA_VEL_Y,value_9,-5.000000,variable_10,TRA_VEL_Z,value_10,6.000000,variable_11,POSI_FROM_CENT_X,value_11,0.0,variable_12,POSI_FROM_CENT_Y,value_12,0.0,variable_13,POSI_FROM_CENT_Z,value_13,0.0,variable_14,ROT_ANG_VEL_X,value_14,0.0,variable_15,ROT_ANG_VEL_Y,value_15,0.0,variable_16,ROT_ANG_VEL_Z,value_16,0.0,run_time,1.0,tmin,0.001"""
REST_GOLDEN = """1,Left
2,Right
3,Bottom
4,Top
5,Rear
6,Front
cat,Corner_Drop_2nd,drop_name,Trial_A,variable_1,LeftBottomRear,value_1,0.000000,variable_2,RightBottomRear,value_2,1.250000,variable_3,RightTopRear,value_3,2.500000,variable_4,OFFSET,value_4,0.0,variable_5,ANG_VEL_X,value_5,0.000000,variable_6,ANG_VEL_Y,value_6,0.000000,variable_7,ANG_VEL_Z,value_7,0.000000,variable_8,TRA_VEL_X,value_8,0.000000,variable_9,TRA_VEL_Y,value_9,0.000000,variable_10,TRA_VEL_Z,value_10,0.000000,variable_11,POSI_FROM_CENT_X,value_11,0.0,variable_12,POSI_FROM_CENT_Y,value_12,0.0,variable_13,POSI_FROM_CENT_Z,value_13,0.0,variable_14,ROT_ANG_VEL_X,value_14,0.0,variable_15,ROT_ANG_VEL_Y,value_15,0.0,variable_16,ROT_ANG_VEL_Z,value_16,0.0,run_time,1.0,tmin,0.001"""


def point_frame():
    return pd.DataFrame([[1.25, -2.5]], index=[.1], columns=pd.MultiIndex.from_tuples([
        ('Velocity', 'CoM', 'V_TX_ANA'), ('Velocity', 'CoM', 'V_TY_ANA')]))


def test_point_literal_utf8_lf_golden_retains_index_and_three_headers():
    stream = io.StringIO(newline='')
    point_frame().to_csv(stream, index=True, lineterminator='\n')
    assert stream.getvalue().encode('utf-8') == POINT_GOLDEN


def test_point_filesystem_bytes_have_declared_platform_newline(tmp_path):
    path = tmp_path / 'point.csv'
    point_frame().to_csv(path, index=True)
    expected = POINT_GOLDEN.replace(b'\n', os.linesep.encode('ascii'))
    assert path.read_bytes() == expected


def test_point_unicode_comma_quote_roundtrip_preserves_field_and_column_identity(tmp_path):
    frame = point_frame()
    field = '쉼표, "인용"'
    frame[('Info', 'Label', 'Text')] = field
    path = tmp_path / 'point-special.csv'
    frame.to_csv(path, index=True)
    parsed = pd.read_csv(path, header=[0, 1, 2], index_col=0, encoding='utf-8')
    assert parsed.columns.tolist() == frame.columns.tolist()
    assert parsed.index.tolist() == [.1]
    assert parsed.iloc[0][('Info', 'Label', 'Text')] == field
    with path.open(encoding='utf-8', newline='') as stream:
        assert list(csv.reader(stream))[-1][-1] == field


def test_cae_literal_measured_and_declared_rest_goldens_have_no_final_newline():
    measured = scenario_text(OFFSETS, VELOCITIES, 'Trial_A', '1.0', '0.001')
    rest = scenario_text(OFFSETS, {key: 0. for key in VELOCITIES}, 'Trial_A', '1.0', '0.001')
    assert measured.encode('utf-8') == CAE_GOLDEN.encode('ascii')
    assert rest.encode('utf-8') == REST_GOLDEN.encode('ascii')
    assert not measured.endswith('\n') and not rest.endswith('\n')


@pytest.mark.parametrize('heights,expected', [
    ([3., 1., 4., 2., 8., 6., 9., 7.], [('C2', 1.), ('C4', 2.), ('C1', 3.)]),
    ([8., 6., 9., 7., 3., 1., 4., 2.], [('C6', 1.), ('C8', 2.), ('C5', 3.)]),
    ([0.] * 8, [('C1', 0.), ('C2', 0.), ('C3', 0.)]),
])
def test_automatic_offset_group_and_stable_tie_order(heights, expected):
    row = pd.Series({('Analysis', f'C{i}', 'RelativeHeight'): height for i, height in enumerate(heights, 1)})
    assert automatic_offsets(row) == expected


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf, None])
def test_automatic_offsets_require_all_original_heights(bad):
    row = {('Analysis', f'C{i}', 'RelativeHeight'): float(i) for i in range(1, 9)}
    row[('Analysis', 'C8', 'RelativeHeight')] = bad
    with pytest.raises(ValueError, match='C8'):
        automatic_offsets(row)


@pytest.mark.parametrize('offsets', [
    [('C1', 0.), ('C1', 1.), ('C3', 2.)], [('C0', 0.), ('C2', 1.), ('C3', 2.)],
    [('C1', 0.), ('C2', 1.)], [('C1', 0.), ('C2', np.nan), ('C3', 2.)],
    [('C1', 0.), ('C2', np.inf), ('C3', 2.)],
])
def test_serializer_rejects_invalid_offset_corners_or_heights(offsets):
    with pytest.raises(ValueError):
        scenario_text(offsets, VELOCITIES, 'Trial_A', '1.0', '0.001')


@pytest.mark.parametrize('name', list(VELOCITIES))
@pytest.mark.parametrize('fault', ['missing', 'nan', 'inf'])
def test_serializer_requires_each_of_six_finite_measured_velocities(name, fault):
    velocities = dict(VELOCITIES)
    if fault == 'missing':
        velocities.pop(name)
    else:
        velocities[name] = np.nan if fault == 'nan' else np.inf
    with pytest.raises(ValueError, match=name):
        scenario_text(OFFSETS, velocities, 'Trial_A', '1.0', '0.001')


@pytest.mark.parametrize('runtime,timestep', [('0', '.001'), ('-1', '.001'), ('NaN', '.001'),
    ('inf', '.001'), ('1', '0'), ('1', '-.001'), ('1', 'NaN'), ('1', 'inf')])
def test_serializer_rejects_nonfinite_nonpositive_runtime_or_timestep(runtime, timestep):
    with pytest.raises(ValueError):
        scenario_text(OFFSETS, VELOCITIES, 'Trial_A', runtime, timestep)


@pytest.mark.parametrize('name', ['bad,name', 'bad"name', 'bad\rname', 'bad\nname', 'bad\0name'])
def test_serializer_rejects_unescaped_scene_delimiters(name):
    with pytest.raises(ValueError, match='Scene name'):
        scenario_text(OFFSETS, VELOCITIES, name, '1.0', '0.001')


def test_serializer_keeps_delimiter_free_korean_and_runtime_input_spelling():
    result = scenario_text(OFFSETS, VELOCITIES, '낙하시험', '1.00', '1e-7')
    assert 'drop_name,낙하시험,' in result
    assert result.endswith(',run_time,1.00,tmin,1e-7')


def test_filesystem_encoding_and_newline_follow_legacy_runtime(tmp_path):
    path = tmp_path / 'scenario.csv'
    text = scenario_text(OFFSETS, VELOCITIES, 'Trial_A', '1.0', '0.001')
    payload = scenario_bytes(text)
    atomic_write_scenario(path, payload)
    expected = CAE_GOLDEN.replace('\n', os.linesep).encode(scenario_export.locale.getpreferredencoding(False))
    assert path.read_bytes() == expected
    assert list(tmp_path.glob('.scenario-*.tmp')) == []


@pytest.mark.parametrize('encoding', ['utf-8', 'cp949'])
def test_representable_korean_scene_names_roundtrip_before_write(monkeypatch, encoding):
    monkeypatch.setattr(scenario_export.locale, 'getpreferredencoding', lambda _setlocale=False: encoding)
    text = scenario_text(OFFSETS, VELOCITIES, '낙하시험', '1.0', '0.001')
    assert scenario_bytes(text).decode(encoding) == text.replace('\n', os.linesep)


def test_encoding_failure_preserves_existing_sentinel_before_atomic_writer(tmp_path, monkeypatch):
    destination = tmp_path / 'scenario.csv'
    sentinel = b'original\x00sentinel\xff'
    destination.write_bytes(sentinel)
    monkeypatch.setattr(scenario_export.locale, 'getpreferredencoding', lambda _setlocale=False: 'ascii')
    text = scenario_text(OFFSETS, VELOCITIES, '낙하시험', '1.0', '0.001')
    with pytest.raises(UnicodeEncodeError):
        payload = scenario_bytes(text)
        atomic_write_scenario(destination, payload)
    assert destination.read_bytes() == sentinel
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize('failure', ['short_write', 'write_raises', 'flush_raises', 'replace_raises'])
def test_atomic_write_failures_preserve_original_bytes_and_cleanup_exact_temp(tmp_path, monkeypatch, failure):
    destination = tmp_path / 'scenario.csv'
    sentinel = b'original\x00sentinel\xff'
    destination.write_bytes(sentinel)
    original_factory = scenario_export.tempfile.NamedTemporaryFile
    temporary_paths = []

    def failing_file(*args, **kwargs):
        assert Path(kwargs['dir']).resolve() == destination.parent.resolve()
        stream = original_factory(*args, **kwargs)
        temporary_paths.append(Path(stream.name))
        real_write = stream.write
        if failure == 'short_write':
            stream.write = lambda payload: real_write(payload[:3])
        elif failure == 'write_raises':
            def interrupted_write(payload):
                real_write(payload[:3])
                raise OSError('injected partial write failure')
            stream.write = interrupted_write
        elif failure == 'flush_raises':
            def interrupted_flush():
                raise OSError('injected flush failure')
            stream.flush = interrupted_flush
        return stream

    monkeypatch.setattr(scenario_export.tempfile, 'NamedTemporaryFile', failing_file)
    if failure == 'replace_raises':
        def fail_replace(source, target):
            assert Path(source).parent.resolve() == destination.parent.resolve()
            assert Path(target) == destination
            raise OSError('injected replace failure')
        monkeypatch.setattr(scenario_export.os, 'replace', fail_replace)
    with pytest.raises(OSError):
        atomic_write_scenario(destination, b'new complete scenario payload')
    assert destination.read_bytes() == sentinel
    assert temporary_paths and all(not path.exists() for path in temporary_paths)
    assert list(tmp_path.iterdir()) == [destination]
