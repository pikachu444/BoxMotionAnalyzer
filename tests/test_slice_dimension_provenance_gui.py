"""Actual slice GUI rejection preserves disk and editable input state."""
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from src.analysis.pipeline.artifact_io import save_slice_file, read_slice_metadata, update_slice_box_dimensions
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
from src.config.data_columns import FACE_PREFIX_TO_INFO
from test_marker_flip_artifact_io import _raw_bundle
import pytest


def test_existing_slice_dimension_patch_rejects_conflict_before_save(tmp_path):
    app = QApplication.instance() or QApplication([])
    header, raw = _raw_bundle()
    header['artifact_metadata'] = dict(BoxLengthMm=200.,BoxWidthMm=120.,BoxHeightMm=80.)
    path = tmp_path/'missing_box.slice'
    save_slice_file(filepath=str(path),header_info=header,raw_data=raw,source_path='unit.csv',
                    full_start=0,full_end=5,user_start=0,user_end=5,box_dims=None,pad_rows=0)
    original = path.read_bytes()
    with pytest.raises(ValueError,match='dimensions conflict'):
        update_slice_box_dimensions(str(path),(300.,120.,80.))
    assert path.read_bytes() == original
    widget = WidgetSliceProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    widget.resize(1200,800)
    widget.show()
    evidence=Path('tmp/issue83_gui')
    evidence.mkdir(parents=True,exist_ok=True)
    messages=[]
    watcher=QTimer()
    def close_warning():
        dialog=app.activeModalWidget()
        if isinstance(dialog,QMessageBox):
            messages.append(dialog.text())
            dialog.grab().save(str(evidence/'dimension_rejection.png'))
            dialog.accept()
    watcher.timeout.connect(close_warning)
    watcher.start(100)
    try:
        widget.load_slice_file(str(path))
        QTest.qWait(100)
        assert len(messages) == 1 and 'does not include complete box dimensions' in messages[0]
        messages.clear()
        assert widget.le_box_l.isEnabled()
        for field,value in zip((widget.le_box_l,widget.le_box_w,widget.le_box_h),('300','120','80')):
            field.setText(value)
        widget.save_box_dims_to_slice_checkbox.setChecked(True)
        QTest.mouseClick(widget.apply_box_dims_button,Qt.LeftButton)
        assert len(messages)==1 and 'dimensions conflict' in messages[0]
        assert path.read_bytes()==original
        assert widget.slice_metadata.box_l is None
        assert widget.le_box_l.text()=='300' and widget.le_box_l.isEnabled()
        assert widget.apply_box_dims_button.isEnabled() and not widget.run_button.isEnabled()
        widget.grab().save(str(evidence/'dimension_editable_after_failure.png'))
        widget.le_box_l.setText('200')
        QTest.mouseClick(widget.apply_box_dims_button,Qt.LeftButton)
        assert len(messages)==1
        assert read_slice_metadata(str(path)).box_l==200.
        assert not widget.le_box_l.isEnabled() and widget.run_button.isEnabled()
        widget.grab().save(str(evidence/'dimension_match_saved.png'))
    finally:
        watcher.stop()
        widget.close()
