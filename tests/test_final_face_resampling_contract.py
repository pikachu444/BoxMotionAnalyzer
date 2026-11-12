"""Issue #200 characterization; the tail-support policy is still undecided."""
import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from src.analysis.pipeline.contact_reducers import final_face
from src.analysis.pipeline.drop_posture_post_processor import DropPosturePostProcessor
from src.analysis.pipeline.resampler import UniformResampler
from src.config.config_app import FACE_DEFINITIONS
from src.config.data_columns import DropPostureSummaryCols, PoseCols


@pytest.mark.parametrize('times', [
    [0., .1, .2, .3, .4, .5],
    [0., .04, .13, .29, .41, .5],
])
def test_current_final_face_row_gate_can_be_satisfied_by_interpolation(times):
    # Literal independent 200 x 120 x 80 mm box resting on world Y=0.
    local = np.array([
        [-100., -60., -40.], [100., -60., -40.],
        [100., 60., -40.], [-100., 60., -40.],
        [-100., -60., 40.], [100., -60., 40.],
        [100., 60., 40.], [-100., 60., 40.],
    ])
    points = local + [0., 60., 0.]
    frame = pd.DataFrame({PoseCols.ROT_X: 0., PoseCols.ROT_Y: 0., PoseCols.ROT_Z: 0.}, index=times)
    for corner, point in enumerate(points, 1):
        for axis, value in zip('XYZ', point):
            frame[f'C{corner}_{axis}'] = value
    original = frame.copy(deep=True)
    expanded = UniformResampler(factor=3).process(frame)
    # Each of five intervals contributes three positions, plus the final endpoint.
    assert len(expanded) == (6 - 1) * 3 + 1 == 16
    np.testing.assert_allclose(expanded.index[::3], times, rtol=0., atol=0.)
    processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS, local_box_corners=local)
    for data, start, expected, source_count in ((frame, 3, '', 3), (expanded, 10, 'BOTTOM', 2)):
        assert int(.65 * len(data)) == start
        tail_times = data.index[start:]
        assert sum(tail_times[0] <= t <= tail_times[-1] for t in times) == source_count
        corners = np.broadcast_to(points, (len(data), 8, 3))
        reduced = final_face(data.index, Rotation.identity(len(data)), corners,
                             [200., 120., 80.], floor=0., threshold=1.)
        output = processor.process(data, contact_threshold_mm=1.)
        assert output[DropPostureSummaryCols.FINAL_FACE].eq(expected).all()
        if expected:
            assert len(tail_times) == 6
            assert reduced.value == 'BOTTOM'  # Identity's local -Y face is down.
        else:
            assert len(tail_times) == 3
            assert reduced.value is None
            assert reduced.reason == 'At least five usable tail samples are required'
    pd.testing.assert_frame_equal(frame, original)
