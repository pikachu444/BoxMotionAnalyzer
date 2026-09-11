"""Step 1 orchestration for observed-motion detection and reviewed slices."""
from copy import deepcopy
import json
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.analysis.pipeline.scene_detection import detect_scenes, Registration
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.support_motion import EDGE_TRAVEL_SIGNAL, LIFT_SIGNAL
from src.analysis.pipeline.artifact_io import (_sha256_file, save_slice_file,
    build_slice_default_name, DEFAULT_SLICE_PADDING_ROWS)
from src.utils.artifact_metadata import normalize_metadata


class SceneDetectionWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, header, raw, parsed, registration, parent):
        super().__init__(parent)
        self.header, self.raw, self.parsed = deepcopy(header), raw.copy(deep=True), parsed.copy(deep=True)
        self.registration = deepcopy(registration)

    def run(self):
        try:
            result = detect_scenes(self.header, self.raw, self.parsed, registration=self.registration,
                                   cancelled=self.isInterruptionRequested)
            if self.isInterruptionRequested():
                self.cancelled.emit()
            else:
                self.completed.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class SceneReviewFlow:
    def _init_scene_state(self):
        self.scene_worker = None
        self.scene_busy = False
        self.scene_registration = None
        self.scene_session = None
        self._selecting_scene = False

    def _connect_scene_signals(self):
        panel = self.scene_panel
        panel.detect_button.clicked.connect(self.detect_scene_candidates)
        panel.geometry_button.clicked.connect(self.load_scene_geometry)
        panel.add_button.clicked.connect(self.add_scene_range)
        panel.save_all_button.clicked.connect(self.save_included_scenes)
        panel.row_selected.connect(self._select_scene)
        panel.changed.connect(self._update_scene_gates)
        panel.error.connect(lambda text: self.append_log(f'[ERROR] {text}'))
        for edit in (self.le_box_l, self.le_box_w, self.le_box_h):
            edit.editingFinished.connect(self._scene_dimensions_changed)
        self._update_scene_gates()

    def _reset_scenes(self):
        self.scene_session, self.scene_registration = None, None
        self.scene_panel.session = None
        declared = normalize_metadata((self.header_info or {}).get('artifact_metadata'))
        self.scene_panel.type_combo.setCurrentText(declared['IstaType'] if declared['IstaType'] in ('G', 'H') else 'Unknown')
        self.scene_panel.edition_combo.setCurrentIndex(0)
        self.scene_panel.geometry_button.setText('Geometry...')
        self.scene_panel.refresh()
        while self.combo_plot_axis.count() > 3:
            self.combo_plot_axis.removeItem(3)
        self._update_scene_gates()

    def _update_scene_gates(self):
        if not hasattr(self, 'scene_panel'):
            return
        marker_busy = self.marker_review_busy or (self.review_worker is not None and self.review_worker.isRunning())
        busy = self.scene_busy or marker_busy
        loaded = self.raw_data is not None and self.parsed_data is not None
        ready = loaded and not busy and not self.marker_review_dirty
        self.scene_panel.detect_button.setEnabled(ready or self.scene_busy)
        self.scene_panel.detect_button.setText('Cancel detection' if self.scene_busy else 'Detect scenes')
        self.scene_panel.geometry_button.setEnabled(ready)
        self.scene_panel.table.setEnabled(not busy)
        for widget in (self.scene_panel.type_combo, self.scene_panel.edition_combo,
                       self.scene_panel.add_button, self.scene_panel.remove_button,
                       self.scene_panel.include_button, self.scene_panel.exclude_button):
            widget.setEnabled(ready and self.scene_session is not None)
        reviewed = bool(self.scene_session and self.scene_session.all_reviewed)
        self.scene_panel.identify_button.setEnabled(ready and reviewed)
        self.scene_panel.save_all_button.setEnabled(ready and reviewed
            and any(r['decision'] == 'include' for r in self.scene_session.rows))
        selected = self.scene_panel.selected_row()
        self.scene_panel.confirm_button.setEnabled(ready and reviewed and bool(selected
            and selected['item_candidates'] and self.scene_session.applied_edition))
        self.save_slice_button.setEnabled(ready and (self.scene_session is None
            or (reviewed and selected is not None and selected['decision'] == 'include')))
        self.load_csv_button.setEnabled(not busy)
        self.review_marker_flips_button.setEnabled(loaded and not busy)
        self.box_dims_group.setEnabled(not busy)
        self.slice_group.setEnabled(not busy)
        self.save_corrected_source_button.setEnabled(loaded and not busy and self.marker_review_dirty)

    def _validate_scene_source(self):
        if not self.source_path or _sha256_file(self.source_path) != self.active_source_sha256:
            raise ValueError('Capture changed on disk. Reload it before detection or saving.')
        if self.marker_review_dirty:
            raise ValueError('Save the corrected source before detecting or saving scenes.')
        if self.scene_registration and tuple(self.scene_registration.profile['box_dims_mm']) != self._read_box_dimensions():
            raise ValueError('Box dimensions differ from the registered marker geometry.')

    def detect_scene_candidates(self):
        if self.scene_busy:
            self.scene_worker.requestInterruption()
            return
        if self.scene_worker is not None and self.scene_worker.isRunning():
            return
        try:
            self._validate_scene_source()
            self.scene_busy = True
            self._update_scene_gates()
            self.scene_worker = SceneDetectionWorker(self.header_info, self.raw_data, self.parsed_data,
                                                     self.scene_registration, self)
            self.scene_worker.completed.connect(self._finish_scene_detection)
            self.scene_worker.failed.connect(self._scene_detection_failed)
            self.scene_worker.cancelled.connect(self._scene_detection_cancelled)
            self.scene_worker.finished.connect(self._update_scene_gates)
            self.scene_worker.start()
        except Exception as exc:
            self._scene_detection_failed(str(exc))

    def _finish_scene_detection(self, result):
        self.scene_busy = False
        try:
            self._validate_scene_source()
            if self.scene_session is None:
                self.scene_session = SceneReviewSession(result, self.active_source_sha256)
            else:
                self.scene_session.refresh(result)
            panel = self.scene_panel
            panel.session = self.scene_session
            self.scene_session.set_context(panel.type_combo.currentText(), panel.edition_combo.currentData())
            while self.combo_plot_axis.count() > 3:
                self.combo_plot_axis.removeItem(3)
            for name in result.signals:
                self.combo_plot_axis.addItem(name, name)
            if result.registration and result.registration.floor_y_mm is not None:
                for name in (EDGE_TRAVEL_SIGNAL, LIFT_SIGNAL):
                    self.combo_plot_axis.addItem(name, name)
            self.combo_plot_axis.setCurrentIndex(3)
            active = next((r['id'] for r in self.scene_session.rows if r['motion'] != 'stationary'), None)
            panel.refresh(panel.selected_id() or active)
            self.append_log(f'[INFO] Detected {len(result.candidates)} observed intervals. Type and item remain unconfirmed.')
        except Exception as exc:
            self._scene_detection_failed(str(exc))
        self._update_scene_gates()

    def _scene_detection_failed(self, message):
        self.scene_busy = False
        self.append_log(f'[ERROR] Scene detection: {message}')
        self._update_scene_gates()

    def _scene_detection_cancelled(self):
        self.scene_busy = False
        self.append_log('[INFO] Detection cancelled; existing ranges were kept.')
        self._update_scene_gates()

    def load_scene_geometry(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Marker geometry', '', 'Geometry (*.json)')
        if not path:
            return
        try:
            registration = Registration.load(path)
            # Geometry is a deliberate input, not a marker-layout hash lookup.
            self.scene_registration = registration
            for edit, value in zip((self.le_box_l, self.le_box_w, self.le_box_h), registration.profile['box_dims_mm']):
                edit.setText(str(value))
            self.scene_panel.geometry_button.setText('Geometry loaded')
            self.scene_panel.geometry_button.setToolTip(str(Path(path).resolve()))
            self._invalidate_scene_evidence('geometry_changed')
            self.append_log(f'[INFO] Registered marker geometry loaded: {path}')
        except Exception as exc:
            self.append_log(f'[ERROR] Geometry: {exc}')

    def _invalidate_scene_evidence(self, reason):
        if self.scene_session:
            for row in self.scene_session.rows:
                row['evidence_status'], row['decision'] = reason, 'unreviewed'
                row['motion_geometry'] = {'version': 1, 'status': reason}
                self.scene_session._reset_identity(row)
            self.scene_panel.refresh()

    def _scene_dimensions_changed(self):
        if self.scene_registration:
            try:
                if self._read_box_dimensions() != tuple(self.scene_registration.profile['box_dims_mm']):
                    self._invalidate_scene_evidence('geometry_changed')
            except ValueError:
                self._invalidate_scene_evidence('geometry_changed')

    def _select_scene(self, row):
        if row is None:
            if self.combo_plot_axis.currentData() in (EDGE_TRAVEL_SIGNAL, LIFT_SIGNAL):
                self.update_plot()
            return
        self._selecting_scene = True
        try:
            self.slice_group.setChecked(True)
            self.le_slice_start.setText(repr(row['start']))
            self.le_slice_end.setText(repr(row['end']))
            self.le_scene_name.setText(row['id'])
            self.plot_manager.set_region(row['start'], row['end'])
            if self.combo_plot_axis.currentData() in (EDGE_TRAVEL_SIGNAL, LIFT_SIGNAL):
                self.update_plot()
            self.canvas.draw_idle()
        finally:
            self._selecting_scene = False

    def _scene_range_edited(self, start, end):
        if not self._selecting_scene and self.scene_session and self.scene_panel.selected_id():
            try:
                self.scene_session.set_range(self.scene_panel.selected_id(), start, end)
                self.scene_panel.refresh()
            except ValueError as exc:
                self.append_log(f'[ERROR] {exc}')
                self._select_scene(self.scene_panel.selected_row())

    def add_scene_range(self):
        if self.scene_session:
            try:
                row_id = self.scene_session.add_range(*self._get_slice_bounds())
                self.scene_panel.refresh(row_id)
            except ValueError as exc:
                self.append_log(f'[ERROR] {exc}')

    def _scene_slice_context(self):
        self._validate_scene_source()
        header = deepcopy(self.header_info)
        review_json = ''
        if self.scene_session:
            row = self.scene_panel.selected_row()
            if row is None:
                raise ValueError('Select an included scene.')
            if self._get_slice_bounds() != (row['start'], row['end']):
                raise ValueError('Scene selection and slice range differ. Review the edited range.')
            review_json = self.scene_session.payload(row['id'])
            artifact = normalize_metadata(header.get('artifact_metadata'))
            identity = row['identity']
            artifact.update(IstaType=None if identity['ista_type'] == 'Unknown' else identity['ista_type'],
                            ScenarioId=identity['scenario_id'] if identity['confirmed'] else None,
                            ScenarioKind=identity['scenario_kind'] if identity['confirmed'] else None)
            header['artifact_metadata'] = artifact
        return header, review_json

    def save_included_scenes(self):
        if not self.scene_session or not self.scene_session.all_reviewed:
            return
        parent = QFileDialog.getExistingDirectory(self, 'Save included scenes', str(Path(self.source_path).parent))
        if not parent:
            return
        written = []
        try:
            self._validate_scene_source()
            dims = self._read_box_dimensions()
            base = Path(parent) / (Path(self.source_path).stem + '_scenes')
            output = base
            suffix = 1
            while output.exists():
                suffix += 1
                output = base.with_name(base.name + f'_{suffix}')
            output.mkdir()
            for row in self.scene_session.rows:
                if row['decision'] != 'include':
                    continue
                self.scene_panel.refresh(row['id'])
                header, review_json = self._scene_slice_context()
                path = output / build_slice_default_name(self.source_path, scene_name=row['id'])
                save_slice_file(filepath=str(path), header_info=header, raw_data=self.raw_data, source_path=self.source_path,
                    box_dims=dims, full_start=float(self.parsed_data.index.min()), full_end=float(self.parsed_data.index.max()),
                    user_start=row['start'], user_end=row['end'], pad_rows=DEFAULT_SLICE_PADDING_ROWS,
                    scene_name=row['id'], marker_correction_metadata=self.correction_source_metadata,
                    scene_review_json=review_json)
                written.append(path)
                self.slice_saved.emit(str(path))
            self.slice_path_label.setText(str(output))
            self.append_log(f'[INFO] Saved {len(written)} included scenes to {output}')
        except Exception as exc:
            self.append_log(f'[ERROR] Saved {len(written)} scenes before failure: {exc}')
            QMessageBox.warning(self, 'Scene save failed', str(exc))
