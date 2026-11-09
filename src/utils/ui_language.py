"""Application language preference and presentation-only translation."""

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QSettings, QTranslator

from src.utils.ui_text_ko import KOREAN


_PREFERENCE = 'interface/language'
_LANGUAGES = ('en', 'ko')


def _settings():
    return QSettings('BoxMotionAnalyzer', 'BoxMotionAnalyzer')


def preferred_language():
    language = _settings().value(_PREFERENCE, 'en', type=str)
    return language if language in _LANGUAGES else 'en'


def save_language(language):
    if language not in _LANGUAGES:
        raise ValueError(f'Unsupported interface language: {language}')
    settings = _settings()
    settings.setValue(_PREFERENCE, language)
    settings.sync()
    return settings.status() == QSettings.Status.NoError


def configure_language(app):
    language = preferred_language()
    app.setProperty('interfaceLanguage', language)
    if language == 'ko':
        from matplotlib import rcParams

        rcParams['font.sans-serif'] = [
            'Malgun Gothic', 'Noto Sans CJK KR', 'NanumGothic',
            'Apple SD Gothic Neo', *rcParams['font.sans-serif'],
        ]
        rcParams['axes.unicode_minus'] = False
        translator = QTranslator(app)
        directory = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load('qtbase_ko', directory):
            app.installTranslator(translator)
            app.qt_language_translator = translator


def active_language():
    app = QCoreApplication.instance()
    return (app.property('interfaceLanguage') or 'en') if app is not None else 'en'


def tr(text):
    if not isinstance(text, str):
        return text
    if active_language() == 'ko':
        if text in KOREAN:
            return KOREAN[text]
        if text.endswith(')'):
            label, separator, unit = text.rpartition(' (')
            if separator and label in KOREAN:
                return f'{KOREAN[label]} ({unit}'
    return text
