import sys

from PySide6.QtGui import QIcon

from src.config import config_visualization as config


def set_windows_app_user_model_id():
    """Hint the Windows shell to use the configured app identity."""
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            config.APP_USER_MODEL_ID
        )
    except Exception:
        pass


def get_taskbar_icon() -> QIcon:
    return QIcon(config.APP_ICON_PATH)


def get_window_icon() -> QIcon:
    return QIcon(config.WINDOW_ICON_PATH)


def configure_qt_application(app):
    set_windows_app_user_model_id()
    app.setWindowIcon(get_taskbar_icon())
