"""Applying and remembering the interface language (the Qt side of core/i18n).

core/i18n.py does the actual translating and has no Qt in it. This module
adds what only the GUI layer can do: remember the choice between runs
(QSettings: registry on Windows, ~/.config on Linux) and switch Qt's own
built-in texts ("OK", "Cancel", file-dialog buttons...) to the same language.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import QCoreApplication, QLibraryInfo, QLocale, QSettings, QTranslator

from core.i18n import SOURCE_LANGUAGE, set_language

logger = logging.getLogger(__name__)

_ORGANIZATION = "ofm-webcam-gui"
_APPLICATION = "ofm-webcam-gui"

_qt_translators: list[QTranslator] = []  # kept alive: Qt does not own them


def _settings() -> QSettings:
    return QSettings(_ORGANIZATION, _APPLICATION)


def saved_language() -> Optional[str]:
    value = _settings().value("language", "", type=str)
    return value or None


def save_language(code: str) -> None:
    settings = _settings()
    settings.setValue("language", code)
    settings.sync()


def system_locale() -> str:
    """The operating system's locale, e.g. 'es_CL'."""
    return QLocale.system().name()


def apply_language(code: Optional[str]) -> str:
    """Activate a language for both our own strings and Qt's built-in ones.

    Returns the language actually activated (English if `code` is unknown).
    """
    activated = set_language(code)

    app = QCoreApplication.instance()
    if app is not None:
        for translator in _qt_translators:
            app.removeTranslator(translator)
        _qt_translators.clear()

        base = activated.split("_")[0]
        if base != SOURCE_LANGUAGE:
            directory = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
            translator = QTranslator()
            if translator.load(f"qtbase_{activated}", directory) or translator.load(f"qtbase_{base}", directory):
                app.installTranslator(translator)
                _qt_translators.append(translator)
            else:
                logger.info("No Qt translation for %r; Qt's own dialogs stay in English.", activated)
    return activated
