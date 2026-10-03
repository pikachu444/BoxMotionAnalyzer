"""Independent PUB04 UI topology over public analytic marker observations."""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.pipeline.scene_detection import DetectionResult, DetectionSettings, SceneCandidate
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile

VERTICAL = 'Vertical speed (mm/s)'
ROTATION = 'Relative rotation (deg)'


def public_raw(folder):
    folder = Path(folder) / 'observations'
    t = np.arange(601) * .02
    origins = np.column_stack((20 + 30*t, 1000 + 100*np.sin(.8*t), t*0))
    angle = np.deg2rad(15*np.sin(t))
    rotations = np.repeat(np.eye(3)[None], len(t), axis=0)
    rotations[:, 0, 0] = rotations[:, 1, 1] = np.cos(angle)
    rotations[:, 0, 1], rotations[:, 1, 0] = -np.sin(angle), np.sin(angle)
    write_observations(Path(folder), dict(schema_version=1, source_kind='handcrafted_dummy',
        coordinate_policy='world-y-up-box-local-fixed-center-v1', time_s=t,
        body_origin_mm=origins, rotation_matrix=rotations, frame=np.arange(len(t))),
        example_profile(), dict(schema_version=1, events=[]))
    source = Path(folder) / ('public_synthetic_scene_review_long_capture_filename_' * 3 + '.csv')
    (Path(folder) / 'observed.csv').rename(source)
    return source


def ui_session(source, count=24):
    """Explicit UI ranges are inputs, never claimed as detector answers."""
    t = np.arange(601) * .02
    origins = np.column_stack((20 + 30*t, 1000 + 100*np.sin(.8*t), t*0))
    rotations = np.repeat(np.eye(3)[None], len(t), axis=0)
    angle = np.deg2rad(15*np.sin(t))
    rotations[:, 0, 0] = rotations[:, 1, 1] = np.cos(angle)
    rotations[:, 0, 1], rotations[:, 1, 0] = -np.sin(angle), np.sin(angle)
    candidates = [SceneCandidate(f'scene_{i+1:03d}', .1+i*.5, .35+i*.5,
        'tip_or_rotation' if i % 2 else 'robot_handling',
        'tip_or_rotation' if i % 2 else 'robot_handling') for i in range(count)]
    signals = pd.DataFrame({VERTICAL: 80*np.cos(.8*t), ROTATION: 15*np.abs(np.sin(t))}, index=t)
    result = DetectionResult(candidates, signals, origins/1000, rotations, None,
        DetectionSettings(), None, np.ones(len(t), dtype=bool), np.zeros(len(t), dtype=int))
    return SceneReviewSession(result, hashlib.sha256(Path(source).read_bytes()).hexdigest())


def install_ui_fixture(widget, source, state='many'):
    widget.load_csv_path(str(source))
    for edit, value in zip((widget.le_box_l, widget.le_box_w, widget.le_box_h), (200., 120., 80.)):
        edit.setText(str(value))
    count = 0 if state == 'empty' else 1 if state in ('one', 'manual') else 24
    session = ui_session(source, count)
    widget.scene_session = widget.scene_panel.session = session
    widget._scene_dimensions = widget._read_box_dimensions()
    for i, row in enumerate(session.rows):
        session.set_decision(row['id'], 'include' if i < 2 else 'exclude')
    if state in ('edited', 'blocked'):
        session.set_range('scene_001', .14, .30)
        if state == 'blocked':
            for row in session.rows[1:4]:
                session.set_decision(row['id'], 'unreviewed')
    if state == 'manual':
        session.remove('scene_001')
        session.add_range(.14, .30)
    widget._populate_scene_signals(session.result, VERTICAL)
    widget.scene_panel.refresh(session.rows[0]['id'] if session.rows else None)
    if state == 'details':
        widget.scene_panel.type_combo.setCurrentText('G')
        widget.scene_panel.edition_combo.setCurrentText('2018-03')
        widget.scene_panel.details_section.setExpanded(True)
    widget._update_scene_gates()
    if state == 'loading':
        widget.scene_busy = True
        widget._update_scene_gates()
    elif state == 'error':
        widget._scene_detection_failed('Public fixture failure; retry detection')
