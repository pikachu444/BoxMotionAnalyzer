"""Production contact controls state their actual MuJoCo parameter meaning."""
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtTest import QTest
from src.simulation.ui.main_window import SimulationUI


def test_contact_damping_controls_in_production_window():
    app = QApplication.instance() or QApplication([])
    window = SimulationUI()
    window.show()
    QTest.qWait(200)
    try:
        assert any(label.text() == 'Contact damping control:' for label in window.findChildren(QLabel))
        assert 'not a coefficient of restitution' in window.elasticity_input.toolTip()
        assert window.elasticity_input.value() == .15
        assert 'not required for all tumbling' in window.com_y.toolTip()
        path = Path('tmp/issue74_gui/simulation_contact.png')
        path.parent.mkdir(parents=True,exist_ok=True)
        assert window.grab().save(str(path))
    finally:
        window.close()
        app.processEvents()
