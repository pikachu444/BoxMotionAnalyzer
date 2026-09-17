"""Deterministic Qt lifecycle tests, separate from measured SciPy latency."""
from threading import Event
import time

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog

from marker_face_fixtures import raw_bundle, write_raw, DIMS
from test_event_local_marker_review import RecordingOptimizer
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision
from src.config.data_columns import FACE_PREFIX_TO_INFO


def pump_until(predicate, timeout=5):
    app = QApplication.instance()
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        app.processEvents()
        time.sleep(.002)
    assert predicate(), 'Qt lifecycle failed to complete'


@pytest.fixture
def widget(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    w = WidgetRawDataProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    source = tmp_path / 'independent.csv'
    h, raw, _ = raw_bundle(samples=24, boundary=12)
    write_raw(source, h, raw)
    w._apply_csv_preview(str(source), w._prepare_csv_preview(str(source)))
    for edit, value in zip((w.le_box_l, w.le_box_w, w.le_box_h), DIMS):
        edit.setText(str(value))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: None)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: None)
    yield w
    if w.review_worker is not None:
        w.cancel_marker_review()
        pump_until(lambda: w.review_worker is None)
    w.close()
    w.deleteLater()
    app.processEvents()


def existing_decision(w):
    decision = MarkerCorrectionDecision('saved-event', .12, True, 'X', correction_kind='face_assignment')
    w.marker_correction_decisions = [decision]
    w.marker_review_dirty = True
    w._update_marker_review_summary()
    return decision


def held_worker(w, at_call=1, fail=False):
    entered, release = Event(), Event()
    class HeldOptimizer(RecordingOptimizer):
        count = 0
        def process(self, frame, **kwargs):
            type(self).count += 1
            if type(self).count == at_call:
                entered.set()
                while not release.wait(.002):
                    if kwargs['cancelled']():
                        raise InterruptedError()
                if fail:
                    raise OSError('Injected computation failure')
            return super().process(frame, **kwargs)
    w.pose_optimizer_factory = HeldOptimizer
    w.confirm_review_dimensions.setChecked(True)
    w.open_marker_flip_review()
    pump_until(entered.is_set)
    return release


def test_explicit_dimensions_and_immediate_invalidation(widget):
    assert not widget.review_marker_flips_button.isEnabled()
    widget.confirm_review_dimensions.setChecked(True)
    assert widget.review_marker_flips_button.isEnabled()
    old = existing_decision(widget)
    widget.le_box_l.setText('201')
    assert widget._review_invalidated
    assert not widget.confirm_review_dimensions.isChecked()
    assert not widget.review_marker_flips_button.isEnabled()
    assert not widget.save_corrected_source_button.isEnabled()
    assert not widget.save_slice_button.isEnabled()
    assert widget.marker_correction_decisions == [old]
    widget.le_box_l.setText('200')
    assert widget._review_invalidated  # No automatic resurrection after reverting.


def test_numeric_dimension_formatting_preserves_confirmation(widget):
    widget.confirm_review_dimensions.setChecked(True)
    existing_decision(widget)
    widget.le_box_l.setText('200.000')
    assert widget.confirm_review_dimensions.isChecked()
    assert not widget._review_invalidated


def test_capture_replaced_during_preview_read_cannot_pair_old_rows_with_new_digest(widget, monkeypatch):
    old = existing_decision(widget)
    load = widget.data_loader.load_csv
    def changed_load(path):
        result = load(path)
        with open(path, 'a') as stream:
            stream.write('\n')
        return result
    monkeypatch.setattr(widget.data_loader, 'load_csv', changed_load)
    with pytest.raises(ValueError, match='changed while loading'):
        widget._prepare_csv_preview(widget.source_path)
    assert widget.marker_correction_decisions == [old]


@pytest.mark.parametrize('fit_call', [1, 2, 3, 4, 5, 6])
def test_cancel_during_each_fit_restores_previous_pending_save(widget, fit_call):
    old = existing_decision(widget)
    before = open(widget.source_path, 'rb').read()
    release = held_worker(widget, fit_call)
    try:
        assert widget.marker_review_busy
        widget.cancel_marker_review()
        pump_until(lambda: widget.review_worker is None)
        assert not widget.marker_review_busy
        assert widget.marker_correction_decisions == [old]
        assert widget.marker_review_dirty and widget.save_corrected_source_button.isEnabled()
        assert widget.review_marker_flips_button.isEnabled()
        assert not widget.save_slice_button.isEnabled()
        assert open(widget.source_path, 'rb').read() == before
        assert widget._review_cache is None
    finally:
        release.set()


def test_finished_but_queued_completion_is_discarded_after_cancel(widget):
    old = existing_decision(widget)
    release = held_worker(widget)
    worker = widget.review_worker
    release.set()
    assert worker.wait(5000)  # Finish worker without delivering queued GUI completion.
    assert worker.result is not None
    widget.cancel_marker_review()
    pump_until(lambda: widget.review_worker is None)
    assert widget.marker_correction_decisions == [old]
    assert not widget._review_invalidated
    assert widget._review_cache is None


@pytest.mark.parametrize('change', ['dimensions', 'file', 'revision'])
def test_stale_completion_never_opens_approval_dialog(widget, change):
    old = existing_decision(widget)
    opened = []
    widget.marker_flip_dialog_factory = lambda *a, **k: opened.append(True)
    release = held_worker(widget)
    if change == 'dimensions':
        widget.le_box_w.setText('121')
    elif change == 'file':
        with open(widget.source_path, 'a') as stream:
            stream.write('\n')
    else:
        widget._source_revision += 1
        widget._review_invalidated = True  # Source replacement invalidates its old evidence at the mutation.
    release.set()
    pump_until(lambda: widget.review_worker is None)
    assert not opened
    assert widget.marker_correction_decisions == [old]
    assert not widget.save_corrected_source_button.isEnabled()


def test_failure_discards_new_result_and_restores_controls(widget):
    old = existing_decision(widget)
    release = held_worker(widget, fail=True)
    release.set()
    pump_until(lambda: widget.review_worker is None)
    assert widget.marker_correction_decisions == [old]
    assert not widget._review_invalidated
    assert widget.save_corrected_source_button.isEnabled()
    assert widget.review_marker_flips_button.isEnabled()
    assert widget.last_review_statistics is None


def test_close_cancels_and_waits_for_thread_cleanup(widget):
    widget.show()
    old = existing_decision(widget)
    release = held_worker(widget)
    assert widget.close() is False
    pump_until(lambda: widget.review_worker is None and not widget.isVisible())
    assert widget.marker_correction_decisions == [old]
    release.set()


def test_source_changed_inside_dialog_cannot_apply_decision(widget):
    old = existing_decision(widget)
    class StaleDialog:
        def setWindowTitle(self, title):
            pass
        def exec(self):
            widget.le_box_h.setText('81')
            return QDialog.DialogCode.Accepted
        def get_decisions(self):
            pytest.fail('Stale decisions must not be read')
    widget.marker_flip_dialog_factory = lambda *a, **k: StaleDialog()
    release = held_worker(widget)
    release.set()
    pump_until(lambda: widget.review_worker is None)
    assert widget.marker_correction_decisions == [old]
    assert widget._review_invalidated


@pytest.mark.parametrize('accepted', [False, True])
def test_empty_completed_review_requires_explicit_decision_replacement(widget, accepted, monkeypatch):
    from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QFileDialog
    old = existing_decision(widget)
    widget._review_invalidated = True
    widget._pending_review_context = widget._face_context()
    widget._pending_review_identity = widget._review_identity()
    def choose():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, MarkerFlipReviewDialog)
        assert dialog.candidates == []
        dialog.accept() if accepted else dialog.reject()
    QTimer.singleShot(50, choose)
    widget._finish_marker_review([])
    pump_until(lambda: widget.review_worker is None)
    assert widget._review_invalidated is (not accepted)
    assert widget.marker_correction_decisions == ([] if accepted else [old])
    if accepted:
        from pathlib import Path
        from src.analysis.pipeline.artifact_io import read_corrected_source_metadata
        target = Path(widget.source_path).with_name('empty.corrected.csv')
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(target), ''))
        widget.save_corrected_source()
        assert read_corrected_source_metadata(str(target)).schema_version == '3'
        assert widget.save_slice_button.isEnabled()


def test_done_source_verification_is_cancellable_without_replacing_approvals(widget, monkeypatch):
    from src.analysis.ui.widget_raw_data_processing import MarkerReviewWorker
    old = existing_decision(widget)
    widget._pending_review_context = widget._face_context()
    widget._pending_review_identity = widget._review_identity()
    class AcceptEmpty:
        def setWindowTitle(self, title):
            pass
        def exec(self):
            return QDialog.DialogCode.Accepted
        def get_decisions(self):
            return []
    widget.marker_flip_dialog_factory = lambda *a, **k: AcceptEmpty()
    entered = Event()
    def verify(worker):
        entered.set()
        while not worker.isInterruptionRequested():
            time.sleep(.002)
        raise InterruptedError()
    monkeypatch.setattr(MarkerReviewWorker, 'verify_source', verify)
    widget._finish_marker_review([])
    pump_until(entered.is_set)
    assert widget.marker_review_busy
    assert widget.marker_correction_decisions == [old]
    widget.cancel_marker_review()
    pump_until(lambda: widget.review_worker is None)
    assert widget.marker_correction_decisions == [old]
