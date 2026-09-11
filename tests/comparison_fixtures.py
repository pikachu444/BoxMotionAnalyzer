"""Declared unit-contract files; fabricated metadata never proves real validation."""
import numpy as np
import pandas as pd
from src.config.data_columns import TimeCols, PoseCols, DropPostureCols, DropPostureSummaryCols
from src.analysis.pipeline.artifact_io import add_timeline_context_columns, save_proc_file
from src.utils.processing_settings import SETTINGS_ATTR


def identity(**overrides):
    result = dict(SchemaVersion='1', SourceKind='handcrafted_dummy', ModelId='contract-box',
                  BoxLengthMm=200., BoxWidthMm=120., BoxHeightMm=80.,
                  IstaType='not_applicable', ScenarioId='contract-drop', ScenarioKind='synthetic_test',
                  MarkerLayoutId='contract-layout', MarkerLayoutHash='a' * 64,
                  CoordinatePolicy='world-y-up-box-local-fixed-center-v1',
                  UnitsPolicy='bma-mm-s-rotvec-rad-summary-deg-v1', GeneratorVersion='contract-1')
    result.update(overrides)
    return result


def write_proc(path, times=(1., 1.01, 1.02), *, t1=1.01, metadata=None, offset=0., settings=None):
    times = np.asarray(times)
    df = pd.DataFrame({TimeCols.FRAME: 100 + 4 * np.arange(len(times)),
                       PoseCols.POS_X: times * 10, PoseCols.POS_Y: np.zeros(len(times)), PoseCols.POS_Z: np.zeros(len(times)),
                       DropPostureCols.THETA_LONG_DEG: times * 2,
                       DropPostureSummaryCols.BETA_AT_T1_MINUS_DEG: 12.3 + offset,
                       DropPostureSummaryCols.T1_MINUS_TIME_SEC: t1,
                       DropPostureSummaryCols.T1_DETECTED: True}, index=pd.Index(times, name='Time'))
    for i, signs in enumerate(((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)), 1):
        for axis, sign, half in zip('XYZ', signs, (100,60,40)):
            df[f'C{i}_{axis}'] = sign * half + (times * 10 if axis == 'X' else 0)
    # Explicit handcrafted contract settings, not a claim of pipeline execution
    # on measured data. Real pipeline provenance is tested in the collision flow.
    df.attrs[SETTINGS_ATTR] = settings if settings is not None else {'single_pass': {'kind': 'handcrafted-unit-contract'},
                               'result_resampling': {'enabled': False},
                               'postprocess': {'kind': 'handcrafted-unit-contract'}}
    df = add_timeline_context_columns(df, {'artifact_metadata': identity() if metadata is None else metadata})
    save_proc_file(str(path), df)
    return path
