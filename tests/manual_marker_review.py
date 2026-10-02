"""Launch public UI states for separate native Windows inspection (#136)."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from src.analysis.app.main_window import MainApp
from test_marker_review_layout import layout_fixture
from marker_face_fixtures import raw_bundle, write_raw, DIMS
from test_event_local_marker_review import RecordingOptimizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['one', 'many', 'details', 'unavailable', 'empty', 'loading', 'error', 'raw'], default='details')
    parser.add_argument('--size', default='820x600')
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    root = Path('tmp/issue136/native') / f'{args.case}-{time.time_ns()}'
    root.mkdir(parents=True)
    width, height = map(int, args.size.split('x'))
    if args.case in ('loading', 'error', 'raw'):
        window = MainApp()
        w = window.original_widget
        header, raw, _ = raw_bundle(samples=24, boundary=12)
        source = root / ('public_synthetic_observation_' * 5 + '.csv')
        write_raw(source, header, raw)
        w.load_csv_path(str(source))
        for edit, value in zip((w.le_box_l, w.le_box_w, w.le_box_h), DIMS):
            edit.setText(str(value))
        if args.case != 'raw':
            class UiOptimizer(RecordingOptimizer):
                count = 0
                def process(self, frame, **kwargs):
                    type(self).count += 1
                    if type(self).count == 1:
                        if args.case == 'error':
                            raise OSError('Public UI fixture: injected calculation failure; retry is available.')
                        while not kwargs['cancelled']():
                            time.sleep(.002)
                        raise InterruptedError()
                    return super().process(frame, **kwargs)
            w.pose_optimizer_factory = UiOptimizer
        w.marker_review_section.setExpanded(True)
        w.confirm_review_dimensions.setChecked(True)
        QTimer.singleShot(300, w.open_marker_flip_review)
    else:
        window, _ = layout_fixture(0 if args.case == 'empty' else 1 if args.case == 'one' else 24,
                                   unavailable=args.case == 'unavailable')
        window.details_section.setExpanded(args.case in ('details', 'unavailable', 'empty'))
    window.setWindowTitle(f'Marker review #136 — {args.case} — public fixture')
    window.resize(width, height)
    window.show()
    # These are widget renders, explicitly not native capture evidence.
    def widget_render():
        if window.isVisible():
            window.grab().save(str(root / 'widget-render.png'))
    timer = QTimer(window)
    timer.timeout.connect(widget_render)
    timer.start(2000)
    app.exec()


if __name__ == '__main__':
    main()
