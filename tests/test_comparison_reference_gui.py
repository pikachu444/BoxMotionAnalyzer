"""Real GUI display/state checks with declared public inputs, not accuracy tests."""
import hashlib
import json
from pathlib import Path
import uuid

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from test_posture_comparison import posture_frame, REVIEW, SUMMARY
from test_impact_comparison_gui import _load, _events
from test_posture_comparison_gui import _choose
from src.analysis.compare.main_window import CompareMainWindow
from src.analysis.compare.metric_guide import metric_entries


def test_reference_and_common_guide_in_all_actual_views(monkeypatch):
    out = Path('tmp/issue122') / ('qt_' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    app = QApplication.instance() or QApplication([])
    window = CompareMainWindow()
    window.resize(1510, 800)
    window.move(0, 0)
    window.show()
    _events(app)
    panel = window.table_panel
    report = dict(result='failed', oracle='Two declared independent Rz10/20 trials; second actual clock shifted +1.5s. Display/state only.',
                  interaction='QTest on real Qt/VTK; supplied file-dialog paths', screens=[], modes=[])
    def capture(name, widget=window):
        _events(app)
        assert widget.grab().save(str(out / name))
        report['screens'].append(name)
    def guide():
        QTest.mouseClick(panel.guide_button, Qt.LeftButton)
        _events(app)
        dialog = panel._metric_guide
        assert dialog is not None and dialog.isVisible()
        assert 'geometric centre' in dialog.reading.toPlainText()
        assert 'not an automatic ISTA failure' in ' '.join(dialog.reading.toPlainText().split())
        assert 'Lowest-corner uniqueness gap (mm)' in dialog.metrics.toPlainText()
        assert 'not confidence' in dialog.metrics.toPlainText()
        assert 'not a probability' in dialog.reading.toPlainText()
        return dialog
    def close_guide(dialog):
        QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.Close), Qt.LeftButton)
        _events(app)
        assert panel._metric_guide is None
    try:
        assert (window.width(), window.height(), window.devicePixelRatioF()) == (1510, 800, 1.25)
        report.update(logical_size=[1510,800], dpr=window.devicePixelRatioF())
        close_guide(guide())  # Available even before a result is open.
        paths = []
        for index, source in enumerate('ab'):
            frame = posture_frame(10*(index+1), source*64)
            if index:
                offset = 1.5
                frame[('Info','Time','Time')] += offset
                for field in ('T1MinusTimeSec','FirstImpactTimeSec'):
                    frame[(*SUMMARY, field)] += offset
                for field in ('SliceStartSec','SliceEndSec'):
                    frame[('Info','Timeline',field)] += offset
                review = json.loads(frame[REVIEW].iloc[0])
                for field in ('start','end','auto_start','auto_end'):
                    review['candidate'][field] += offset
                frame[REVIEW] = json.dumps(review)
            path = out / ('public_comparison_with_a_deliberately_long_filename_' + 'repeated_'*5 + f'trial_{source}.proc')
            frame.to_csv(path, index=False)
            paths.append(path)
        _load(window, paths, monkeypatch, app)
        window.control_panel.file_list.setCurrentRow(0)
        _choose(window.control_panel.cb_view, 1, app)
        # Seek within the common interval and retain that playback position.
        window.playback_panel.master_slider.setFocus()
        QTest.keyClick(window.playback_panel.master_slider, Qt.Key_Right)
        _events(app)
        elapsed = window.playback_panel.current_elapsed
        graph_choice = window.graph_panel.cb_plot_target.currentData()
        for mode in range(6):
            _choose(panel.view_combo, mode, app)
            for baseline_index in (0,1):
                _choose(window.control_panel.cb_baseline, baseline_index, app)
                assert window.control_panel.selected_file == paths[0].name
                assert panel.view_combo.currentIndex() == mode
                assert window.control_panel.cb_view.currentData() == 'aligned'
                assert window.graph_panel.cb_plot_target.currentData() == graph_choice
                assert window.playback_panel.current_elapsed == elapsed
                table = panel.table
                table.horizontalScrollBar().setValue(0)
                if mode in (0,2,4):
                    for index, path in enumerate(paths):
                        item = table.horizontalHeaderItem(index+1)
                        assert item.text().startswith('Baseline (') == (index == baseline_index)
                        assert str(path.resolve()) in item.toolTip()
                        filename = item.text().splitlines()[1 if index == baseline_index else 0]
                        assert filename.endswith(f'trial_{"ab"[index]}.proc') and '…' in filename
                    header = table.horizontalHeader()
                    right = header.sectionViewportPosition(baseline_index+1) + header.sectionSize(baseline_index+1)
                    assert right <= table.viewport().width()
                    assert table.fontMetrics().horizontalAdvance('Baseline') < header.sectionSize(baseline_index+1)
                elif mode == 3:
                    for index in range(2):
                        assert table.item(index, 0).text().startswith('Baseline (') == (index == baseline_index)
                    table.scrollToItem(table.item(baseline_index, 0))
                    assert table.visualItemRect(table.item(baseline_index, 0)).left() == 0
                else:
                    assert str(paths[baseline_index].resolve()) in table.horizontalHeaderItem(7).toolTip()
                    assert str(paths[baseline_index].resolve()) in panel.cohort_label.toolTip()
                    assert panel.cohort_label.width() > 80
                assert panel.guide_button.isVisible()
                assert panel.table.viewport().height() > 20
            capture(f'mode-{mode}.png')
            dialog = guide()
            if mode == 5:
                dialog.tabs.setCurrentIndex(0)
                capture('guide-reading.png', dialog)
                dialog.tabs.setCurrentIndex(1)
                dialog.metrics.scrollToAnchor('corner_gap')
                capture('guide-gap.png', dialog)
            close_guide(dialog)
            assert panel.view_combo.currentIndex() == mode
            assert window.control_panel.selected_file == paths[0].name
            report['modes'].append(mode)
        excluded = posture_frame(30, 'c'*64)
        excluded[('Info','Artifact','ModelId')] = 'different-box-model'
        excluded_path = out / 'excluded-other-model.proc'
        excluded.to_csv(excluded_path, index=False)
        _load(window, [excluded_path], monkeypatch, app)
        assert window.model.get_posture_comparison()['statistics']['beta']['n'] == 2
        assert 'ModelId' in window.model.get_posture_comparison()['files'][excluded_path.name]['reasons'][0]
        close_guide(guide())
        viewer = window.playback_panel.widgets[paths[0].name]
        viewer.plotter.render()
        pixels = viewer.plotter.screenshot(str(out / 'vtk.png'))
        assert pixels.std() > 1
        report['screens'].append('vtk.png')
        report['inputs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths+[excluded_path]}
        report['result'] = 'passed'
    finally:
        (out / 'execution.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        window.close()
        _events(app)


def test_guide_reuses_live_comparison_descriptors(monkeypatch):
    from src.analysis.compare.impact_metrics import METRICS
    from src.analysis.compare.posture_metrics import POSTURE_METRICS
    monkeypatch.setitem(METRICS['vertical_velocity'], 'tooltip', 'Changed upstream definition')
    entries = {key: (name, unit, description) for key, name, unit, description in metric_entries()}
    assert entries['vertical_velocity'][2] == 'Changed upstream definition'
    for key, descriptor in POSTURE_METRICS.items():
        assert entries[key] == (descriptor['label'], descriptor['unit'], descriptor['tooltip'])
    assert 'coexist with an earlier impact' in entries['summary:SustainedContactDetected'][2]
