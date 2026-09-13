"""Step 1 orchestration for observed-motion detection and reviewed slices."""
from copy import deepcopy
import json
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.analysis.pipeline.scene_detection import detect_scenes, Registration, DetectionSettings
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.scene_trial_record import load_trial_record
from src.analysis.pipeline.scene_workspace import (save_workspace, read_workspace,
    workspace_source_path, restore_session)
from src.analysis.pipeline.artifact_io import (_sha256_file, save_slice_file,
    build_slice_default_name, DEFAULT_SLICE_PADDING_ROWS)
from src.utils.artifact_metadata import normalize_metadata


class SceneDetectionWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, header, raw, parsed, registration, parent, *, settings=None):
        super().__init__(parent)
        self.header, self.raw, self.parsed = deepcopy(header), raw.copy(deep=True), parsed.copy(deep=True)
        self.registration = deepcopy(registration)
        self.settings = settings

    def run(self):
        try:
            result = detect_scenes(self.header, self.raw, self.parsed, registration=self.registration,
                                   settings=self.settings,
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
        self._workspace_open_context = None

    def _connect_scene_signals(self):
        panel = self.scene_panel
        panel.detect_button.clicked.connect(self.detect_scene_candidates)
        panel.open_review_button.clicked.connect(self.open_scene_review)
        panel.save_review_button.clicked.connect(self.save_scene_review)
        panel.geometry_button.clicked.connect(self.load_scene_geometry)
        panel.load_trial_record_action.triggered.connect(self.load_scene_trial_record)
        panel.clear_trial_record_action.triggered.connect(self.clear_scene_trial_record)
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
        self.scene_panel.open_review_button.setEnabled(not busy and not self.marker_review_dirty)
        self.scene_panel.save_review_button.setEnabled(ready and self.scene_session is not None)
        self.scene_panel.trial_record_button.setEnabled(ready and self.scene_session is not None)
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
        contact_ready = ready and self.scene_panel.can_set_intended_contact()
        self.scene_panel.intended_combo.setEnabled(contact_ready)
        self.scene_panel.set_intended_button.setEnabled(contact_ready)
        self.save_slice_button.setEnabled(ready and (self.scene_session is None
            or (reviewed and selected is not None and selected['decision'] == 'include')))
        self.save_process_button.setEnabled(ready and (self.scene_session is None
            or (reviewed and any(row['decision'] == 'include' for row in self.scene_session.rows))))
        self.save_status_label.setText('Save correction first' if self.marker_review_dirty else
                                       'Review running' if marker_busy else '')
        self.save_status_label.setVisible(bool(self.save_status_label.text()))
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
            if self._workspace_open_context is not None:
                self._workspace_open_context['cancelled'] = True
            self.scene_worker.requestInterruption()
            return
        if self.scene_worker is not None and self.scene_worker.isRunning():
            return
        try:
            self._validate_scene_source()
            self.scene_busy = True
            self._update_scene_gates()
            header = self.header_info
            metadata = self.correction_source_metadata
            if metadata is not None and metadata.schema_version == '3':
                # Saving a corrected source activates in-memory arrays without
                # reloading the CSV. Use the same validated primitive transport.
                from src.analysis.pipeline.scene_face_corrections import face_correction_header
                header = face_correction_header(header, metadata.context_json, metadata.decisions)
            self.scene_worker = SceneDetectionWorker(header, self.raw_data, self.parsed_data,
                self.scene_registration, self,
                settings=self.scene_session.result.settings if self.scene_session else None)
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
                self.scene_session = SceneReviewSession(result, self.active_source_sha256,
                    original_source_sha256=self.original_source_sha256)
            else:
                self.scene_session.refresh(result)
            panel = self.scene_panel
            panel.session = self.scene_session
            self.scene_session.set_context(panel.type_combo.currentText(), panel.edition_combo.currentData())
            self._populate_scene_signals(result)
            active = next((r['id'] for r in self.scene_session.rows if r['motion'] != 'stationary'), None)
            panel.refresh(panel.selected_id() or active)
            self.append_log(f'[INFO] Detected {len(result.candidates)} observed intervals. Type and item remain unconfirmed.')
        except Exception as exc:
            self._scene_detection_failed(str(exc))
        self._update_scene_gates()

    def _populate_scene_signals(self, result, selected=None):
        self.combo_plot_axis.blockSignals(True)
        try:
            while self.combo_plot_axis.count() > 3:
                self.combo_plot_axis.removeItem(3)
            for name in result.signals:
                self.combo_plot_axis.addItem(name, name)
            index = self.combo_plot_axis.findData(selected) if selected is not None else -1
            if index < 0:
                index = self.combo_plot_axis.findData('Relative rotation (deg)')
            self.combo_plot_axis.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.combo_plot_axis.blockSignals(False)
        self.update_plot()

    def save_scene_review(self):
        if self.scene_busy or self.scene_session is None:
            return
        try:
            self._validate_scene_source()
            default = str(Path(self.source_path).with_suffix('.scene-review.json'))
            path, _ = QFileDialog.getSaveFileName(self, 'Save scene review', default,
                                                  'Scene review (*.scene-review.json)')
            if not path:
                return
            save_workspace(path, self.scene_session, self.source_path, self._read_box_dimensions(),
                           registration=self.scene_registration,
                           selected_id=self.scene_panel.selected_id(),
                           targets=self.current_selected_targets,
                           signal=self.combo_plot_axis.currentData())
            self.scene_panel.save_review_button.setToolTip(str(Path(path).resolve()))
            self.append_log(f'[INFO] Scene review saved: {path}')
        except Exception as exc:
            self.append_log(f'[ERROR] Save review: {exc}')

    def open_scene_review(self):
        if self.scene_busy or self.marker_review_dirty:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Open scene review', '',
                                              'Scene review (*.scene-review.json)')
        if not path:
            return
        try:
            data = read_workspace(path)
            source = workspace_source_path(path, data)
            if not source.is_file():
                located, _ = QFileDialog.getOpenFileName(self, 'Locate capture', str(Path(path).parent),
                                                         'Capture (*.csv)')
                if not located:
                    return
                source = Path(located)
            if _sha256_file(source) != data['source']['sha256']:
                raise ValueError('Capture contents differ from the saved review.')
            preview = self._prepare_csv_preview(str(source))
            if preview['source_sha256'] != data['source']['sha256']:
                raise ValueError('Capture changed while loading the review.')
            registration = Registration(**data['registration']) if data['registration'] else None
            settings = DetectionSettings(**data['settings'])
            self._workspace_open_context = dict(path=path, source=str(source), data=data,
                                                preview=preview, cancelled=False)
            self.scene_busy = True
            self._update_scene_gates()
            self.scene_worker = SceneDetectionWorker(preview['header_info'], preview['raw_data'],
                preview['parsed_data'], registration, self, settings=settings)
            self.scene_worker.completed.connect(self._finish_workspace_open)
            self.scene_worker.failed.connect(self._scene_detection_failed)
            self.scene_worker.cancelled.connect(self._scene_detection_cancelled)
            self.scene_worker.finished.connect(self._update_scene_gates)
            self.scene_worker.start()
        except Exception as exc:
            self._workspace_open_context = None
            self.scene_busy = False
            self.append_log(f'[ERROR] Open review: {exc}')
            self._update_scene_gates()

    def _finish_workspace_open(self, result):
        context = self._workspace_open_context
        if context is None:
            return
        if context['cancelled']:
            self._scene_detection_cancelled()
            return
        try:
            data, source, preview = context['data'], context['source'], context['preview']
            source_hash = _sha256_file(source)
            session, changed = restore_session(data, result, source_hash,
                original_source_sha256=preview['marker_state'][4])
            # All reads and evidence checks finish before replacing active work.
            self._apply_csv_preview(source, preview, emit=False)
            self.scene_session, self.scene_registration = session, result.registration
            panel = self.scene_panel
            panel.session = session
            for edit, value in zip((self.le_box_l, self.le_box_w, self.le_box_h), data['box_dims_mm']):
                edit.setText(str(value))
            for combo in (panel.type_combo, panel.edition_combo):
                combo.blockSignals(True)
            try:
                panel.type_combo.setCurrentText(session.ista_type)
                if panel.edition_combo.findData(session.applied_edition) < 0:
                    panel.edition_combo.addItem(session.applied_edition, session.applied_edition)
                panel.edition_combo.setCurrentIndex(panel.edition_combo.findData(session.applied_edition))
            finally:
                for combo in (panel.type_combo, panel.edition_combo):
                    combo.blockSignals(False)
            if self.scene_registration:
                panel.geometry_button.setText('Geometry loaded')
                panel.geometry_button.setToolTip('Registered geometry from ' + context['path'])
            available = self.data_loader.get_plottable_targets(self.parsed_data)
            self.current_selected_targets = [name for name in data['view'].get('targets', []) if name in available]
            self.selected_data_label.setText('Selected: ' + ', '.join(self.current_selected_targets))
            self._populate_scene_signals(result, data['view']['signal'])
            panel.refresh(data['view']['selected_id'])
            self.file_loaded.emit(self.header_info, self.raw_data, self.parsed_data)
            self.append_log(f"[INFO] Scene review opened: {context['path']}")
            if changed:
                self.append_log(f'[INFO] Recheck changed evidence: {", ".join(sorted(changed))}')
        except Exception as exc:
            self.append_log(f'[ERROR] Open review: {exc}')
        finally:
            self._workspace_open_context = None
            self.scene_busy = False
            self._update_scene_gates()

    def _scene_detection_failed(self, message):
        operation = 'Open review' if self._workspace_open_context else 'Scene detection'
        self._workspace_open_context = None
        self.scene_busy = False
        self.append_log(f'[ERROR] {operation}: {message}')
        self._update_scene_gates()

    def _scene_detection_cancelled(self):
        self._workspace_open_context = None
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

    def load_scene_trial_record(self):
        if self.scene_busy or self.scene_session is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Test record', '', 'Test record (*.json)')
        if not path:
            return
        try:
            self._validate_scene_source()
            record = load_trial_record(path)
            self.scene_session.set_trial_record(record)
            panel = self.scene_panel
            for combo in (panel.type_combo, panel.edition_combo):
                combo.blockSignals(True)
            try:
                panel.type_combo.setCurrentText(self.scene_session.ista_type)
                edition = self.scene_session.applied_edition
                if panel.edition_combo.findData(edition) < 0:
                    panel.edition_combo.addItem(edition, edition)
                panel.edition_combo.setCurrentIndex(panel.edition_combo.findData(edition))
            finally:
                for combo in (panel.type_combo, panel.edition_combo):
                    combo.blockSignals(False)
            panel.trial_record_button.setToolTip(record['record_id'])
            panel.refresh()
            self.append_log(f"[INFO] Test record loaded: {record['record_id']}")
        except Exception as exc:
            self.append_log(f'[ERROR] Test record: {exc}')

    def clear_scene_trial_record(self):
        if not self.scene_busy and self.scene_session is not None:
            self.scene_session.set_trial_record(None)
            self.scene_panel.trial_record_button.setToolTip('')
            self.scene_panel.refresh()

    def _invalidate_scene_evidence(self, reason):
        if self.scene_session:
            for row in self.scene_session.rows:
                self.scene_session._remember_trial_review(row, reason)
                if row['decision'] != 'unreviewed':
                    row.setdefault('previous_review', {'decision': row['decision'],
                        'identity': deepcopy(row['identity']), 'reasons': [reason]})
                    if row.get('intended_contact') is not None:
                        row['previous_review']['intended_contact'] = deepcopy(row['intended_contact'])
                elif 'previous_review' in row and reason not in row['previous_review']['reasons']:
                    row['previous_review']['reasons'].append(reason)
                row['evidence_status'], row['decision'] = reason, 'unreviewed'
                row['motion_geometry'] = {'version': 1, 'status': reason}
                row['support_cycle'] = {'version': 1, 'status': reason}
                row.pop('intended_contact', None)
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
            self.plot_manager.set_selector_active(False)
            self.update_plot()
            return
        self._selecting_scene = True
        try:
            self.slice_group.setChecked(True)
            self.le_slice_start.setText(repr(row['start']))
            self.le_slice_end.setText(repr(row['end']))
            self.le_scene_name.setText(row['id'])
            self.plot_manager.set_selector_active(True)
            self.plot_manager.set_region(row['start'], row['end'])
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
        if (not self.scene_session or not self.scene_session.all_reviewed
                or not any(row['decision'] == 'include' for row in self.scene_session.rows)):
            return []
        parent = QFileDialog.getExistingDirectory(self, 'Save included scenes', str(Path(self.source_path).parent))
        if not parent:
            return []
        written = []
        selected = self.scene_panel.selected_row()
        selected_id = selected['id'] if selected else None
        try:
            if self.marker_review_dirty or self.marker_review_busy or self.scene_busy:
                raise ValueError('Finish and save marker review before saving scenes.')
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
            from src.utils.qt_sections import set_path_label
            set_path_label(self.slice_path_label, str(output))
            self.append_log(f'[INFO] Saved {len(written)} included scenes to {output}')
            return [str(path.resolve()) for path in written]
        except Exception as exc:
            self.append_log(f'[ERROR] Saved {len(written)} scenes before failure: {exc}')
            QMessageBox.warning(self, 'Scene save failed', str(exc))
            return []
        finally:
            self.scene_panel.refresh(selected_id)
