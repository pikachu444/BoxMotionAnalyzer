import sys
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize
from shiboken6 import isValid

from src.config import config_visualization as config
from src.visualization.main_window import MainWindow
from src.analysis.app.main_window import MainApp
from src.analysis.compare.main_window import CompareMainWindow
from src.simulation.ui.main_window import SimulationUI
from src.utils.app_identity import configure_qt_application, get_window_icon
from src.utils.ui_language import preferred_language, save_language, tr


class LanguageOptions(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr('Options'))
        layout = QVBoxLayout(self)
        fields = QFormLayout()
        self.language = QComboBox()
        self.language.addItem('English', 'en')
        self.language.addItem('한국어', 'ko')
        self.language.setCurrentIndex(self.language.findData(preferred_language()))
        fields.addRow(tr('Language'), self.language)
        layout.addLayout(fields)

        restart_notice = QLabel(tr('Language changes take effect the next time you start BoxMotionAnalyzer.'))
        restart_notice.setWordWrap(True)
        layout.addWidget(restart_notice)
        buttons = QDialogButtonBox()
        apply_button = buttons.addButton(tr('Apply'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr('Cancel'), QDialogButtonBox.ButtonRole.RejectRole)
        apply_button.setDefault(True)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(360, self.sizeHint().height())

    def _apply(self):
        if save_language(self.language.currentData()):
            self.accept()
            return
        QMessageBox.warning(self, tr('Options'), tr('The language preference could not be saved.'))


class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr(config.LAUNCHER_TITLE))
        self.setWindowIcon(get_window_icon())
        self.resize(840, 420)

        self.data_processing_window = None
        self.simulation_window = None
        self.comparison_window = None

        # --- Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(22)
        main_layout.addStretch(1)

        # --- Left Panel (Image) ---
        image_label = QLabel()
        image_label.setFixedSize(384, 256)
        pixmap = QPixmap(config.LAUNCHER_ICON_PATH)
        if pixmap.isNull():
            # In case the image is not found, show a text placeholder
            image_label.setText(tr("Image not found"))
            image_label.setAlignment(Qt.AlignCenter)
        else:
            image_label.setPixmap(pixmap.scaled(
                QSize(384, 256), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(image_label, 0, Qt.AlignVCenter)

        # --- Right Panel (Buttons) ---
        right_panel = QWidget()
        right_panel.setFixedWidth(340)
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(14)
        right_panel_layout.addStretch(1)

        sim_layout = QVBoxLayout()
        sim_layout.setContentsMargins(0, 0, 0, 0)
        sim_layout.setSpacing(2)

        self.btn_simulation = QPushButton(tr("Simulation"))
        self.btn_simulation.clicked.connect(self.open_simulation)
        self.btn_simulation.setFixedSize(320, 50)
        sim_layout.addWidget(self.btn_simulation, 0, Qt.AlignHCenter)

        self.simulation_warning_label = QLabel(tr("Experimental"))
        self.simulation_warning_label.setToolTip(
            tr("Synthetic free-fall data, not independently calibrated. "
               "Type H support motion and the Type G hazard block are not modeled.")
        )
        self.simulation_warning_label.setWordWrap(True)
        self.simulation_warning_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.simulation_warning_label.setFixedWidth(320)
        self.simulation_warning_label.setStyleSheet("color: #805d00;")
        sim_layout.addWidget(self.simulation_warning_label, 0, Qt.AlignHCenter)

        right_panel_layout.addLayout(sim_layout)
        right_panel_layout.addSpacing(8)

        self.btn_data_processing = QPushButton(tr(config.LAUNCHER_BTN_PROCESS_TEXT))
        self.btn_data_processing.clicked.connect(self.open_data_processing)
        self.btn_data_processing.setFixedSize(320, 50)
        right_panel_layout.addWidget(self.btn_data_processing, 0, Qt.AlignHCenter)

        self.btn_visualization = QPushButton(tr(config.LAUNCHER_BTN_VISUALIZE_TEXT))
        self.btn_visualization.clicked.connect(self.open_visualization)
        self.btn_visualization.setFixedSize(320, 50)
        right_panel_layout.addWidget(self.btn_visualization, 0, Qt.AlignHCenter)

        self.btn_visualization.setToolTip(tr("Open an independent 3D window."))

        right_panel_layout.addSpacing(8)

        self.btn_compare = QPushButton(tr(config.LAUNCHER_BTN_COMPARE_TEXT))
        self.btn_compare.clicked.connect(self.open_comparison)
        self.btn_compare.setFixedSize(320, 50)
        right_panel_layout.addWidget(self.btn_compare, 0, Qt.AlignHCenter)

        self.btn_options = QPushButton(tr('Options'))
        self.btn_options.clicked.connect(self.open_options)
        right_panel_layout.addWidget(self.btn_options, 0, Qt.AlignRight)

        right_panel_layout.addStretch(1)

        main_layout.addWidget(right_panel, 0, Qt.AlignVCenter)
        main_layout.addStretch(1)

    def open_options(self):
        LanguageOptions(self).exec()

    def open_visualization(self):
        """Opens the main 3D visualization window."""
        MainWindow.create_and_show()

    def open_data_processing(self):
        """Opens the data processing window (MainApp)."""
        window = self._open_work_window('data_processing_window', MainApp)
        window.comparison_opener = self.open_comparison

    def open_simulation(self):
        """Opens the simulation window."""
        self._open_work_window('simulation_window', SimulationUI)

    def open_comparison(self, paths=None):
        """Opens the experiment comparison window."""
        window = self._open_work_window('comparison_window', CompareMainWindow)
        if paths:
            window.load_result_files(paths, deduplicate=True)

    def _open_work_window(self, attribute, factory):
        window = getattr(self, attribute)
        # A successfully closed comparison window has already released its VTK
        # resources, even before Qt delivers deferred deletion. Only reuse an
        # open window; minimizing leaves isVisible() true.
        if window is None or not isValid(window) or not window.isVisible():
            window = factory()
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            setattr(self, attribute, window)
            window.destroyed.connect(
                lambda _object=None, name=attribute, closed=window: self._forget_work_window(name, closed)
            )
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _forget_work_window(self, attribute, closed):
        # A new window may already have replaced a closed one while Qt was
        # waiting to delete the old object.
        if getattr(self, attribute) is closed:
            setattr(self, attribute, None)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    configure_qt_application(app)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())
