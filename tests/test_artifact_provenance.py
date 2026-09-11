"""Public synthetic serialization evidence, independent of flip detection."""
import json
import pandas as pd
import pytest

from src.simulation.marker_fixtures import write_case, virtual_profile_32
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.artifact_io import save_corrected_source_file, save_slice_file, read_slice_metadata, add_timeline_context_columns, save_proc_file
from src.utils.artifact_metadata import metadata_from_source_rows, read_identity, FIELDS, compatibility_reasons


def test_generated_safe_metadata_roundtrip_without_test_truth(tmp_path):
    root = write_case(tmp_path, 'healthy', profile=virtual_profile_32(), motion='face')
    # Production files must remain usable when all truth/event artifacts vanish.
    for name in ('truth_pose.csv', 'truth_markers.csv', 'observed.synthetic.json'):
        (root / name).unlink()
    source = root / 'observed.csv'
    before = source.read_bytes()
    header, raw = DataLoader().load_csv(str(source))
    metadata = header['artifact_metadata']
    assert metadata['SourceKind'] == 'mujoco_synthetic'
    assert metadata['IstaType'] == 'not_applicable'
    assert metadata['ScenarioKind'] == 'synthetic_face'
    assert set(metadata) == set(FIELDS)
    corrected = root / 'reviewed.csv'
    # Empty explicit legacy history suffices to test provenance transport; the
    # real v3 GUI path is checked separately with the collision test.
    save_corrected_source_file(filepath=str(corrected), header_info=header, raw_data=raw,
                               original_source_path=str(source), decisions=[])
    loaded_header, loaded_raw = DataLoader().load_csv(str(corrected))
    assert loaded_header['artifact_metadata'] == metadata
    sliced = root / 'scene.slice'
    save_slice_file(filepath=str(sliced), header_info=loaded_header, raw_data=loaded_raw,
                    source_path=str(corrected), full_start=0, full_end=.792,
                    user_start=.1, user_end=.7, pad_rows=0, box_dims=(300,180,90))
    slice_meta = read_slice_metadata(str(sliced))
    assert json.loads(slice_meta.artifact_metadata_json) == metadata
    assert DataLoader().load_csv(str(sliced))[0]['artifact_metadata'] == metadata
    flat = pd.DataFrame({'Frame': [100,104,108]}, index=pd.Index([.1,.2,.3],name='Time'))
    proc = root / 'scene.proc'
    save_proc_file(str(proc), add_timeline_context_columns(flat, {'artifact_metadata': slice_meta.artifact_metadata_json}))
    identity = read_identity(DataLoader().load_result_csv(str(proc)))
    # Merely wrapping raw data in a result container did not execute processing.
    assert any('processing record missing' in reason for reason in identity.exclusion_reasons())
    assert identity.values['ModelId'] == metadata['ModelId']
    assert source.read_bytes() == before


def test_whitelist_ignores_truth_and_never_infers_names():
    result = metadata_from_source_rows([['Artifact Metadata', json.dumps({'SourceKind':'real','truth_pose':[1,2,3],'events':['X']})]])
    assert 'truth_pose' not in result and 'events' not in result
    assert result['ModelId'] is None
    assert result['SchemaVersion'] is None
    legacy = metadata_from_source_rows([['File', 'VDTest_TypeG_model123.csv']])
    assert legacy['SourceKind'] == 'unknown_legacy'
    assert legacy['IstaType'] is None


def test_nonconstant_metadata_does_not_use_first_row(tmp_path):
    from comparison_fixtures import write_proc
    path = write_proc(tmp_path / 'varying.proc')
    df = pd.read_csv(path, header=[0,1,2])
    df[('Info','Artifact','ModelId')] = ['one','two','one']
    identity = read_identity(df)
    assert any('not constant' in reason for reason in identity.exclusion_reasons())


def test_duplicate_metadata_reports_only_the_actual_duplicate(tmp_path):
    from comparison_fixtures import write_proc
    path = write_proc(tmp_path / 'duplicate.proc')
    df = pd.read_csv(path, header=[0,1,2])
    df = pd.concat([df, df[[('Info','Artifact','ModelId')]]], axis=1)
    df.to_csv(path, index=False)
    identity = read_identity(DataLoader().load_result_csv(str(path)))
    assert identity.errors == ('ModelId: duplicate column',)
    assert identity.values['SourceKind'] == 'handcrafted_dummy'


def test_declared_dimension_mismatch_cannot_be_resaved(tmp_path):
    from test_marker_flip_artifact_io import _raw_bundle
    header, raw = _raw_bundle()
    header['artifact_metadata'] = {'BoxLengthMm': 200.}
    with pytest.raises(ValueError, match='dimensions conflict'):
        save_slice_file(filepath=str(tmp_path / 'bad.slice'), header_info=header, raw_data=raw,
                        source_path='unit.csv', full_start=0, full_end=5,
                        user_start=0, user_end=5, box_dims=(300.,120.,80.))
    assert not (tmp_path / 'bad.slice').exists()


def test_opaque_identity_strings_survive_serialized_loading(tmp_path):
    from comparison_fixtures import write_proc, identity
    a = write_proc(tmp_path / 'a.proc', metadata=identity(ModelId='001', ScenarioId='NA', MarkerLayoutHash='0' * 64))
    b = write_proc(tmp_path / 'b.proc', metadata=identity(ModelId='1', ScenarioId='NA', MarkerLayoutHash='0' * 64))
    first = read_identity(DataLoader().load_result_csv(str(a)))
    second = read_identity(DataLoader().load_result_csv(str(b)))
    assert first.values['ModelId'] == '001'
    assert first.values['ScenarioId'] == 'NA'
    assert first.values['MarkerLayoutHash'] == '0' * 64
    assert any('ModelId: mismatch' in reason for reason in compatibility_reasons(first, second))
