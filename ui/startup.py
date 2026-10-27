"""Launch-time flow: pick an operating mode (and the interface language).

Nothing here touches hardware. Every mode opens its window right away and each
device reports for itself whether it was found (see ui/stage_module.py), so a
missing stage behaves the same on every OS instead of being decided by a
dialog before the window exists.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core.app_mode import AppMode
from core.i18n import _, available_languages, current_language
from .language import apply_language, save_language


class ModeDialog(QDialog):
    """One big button per mode offered at startup (Manual and Automated;
    simulation is command-line only), plus a language selector shown only when
    more than one language is installed. Closing the window cancels."""

    def __init__(self, default: AppMode = AppMode.AUTOMATED) -> None:
        super().__init__()
        self.setMinimumWidth(460)
        self.selected: Optional[AppMode] = None

        layout = QVBoxLayout(self)
        self.heading = QLabel()
        layout.addWidget(self.heading)

        self.buttons: dict[AppMode, QPushButton] = {}
        for mode in (AppMode.AUTOMATED, AppMode.MANUAL):
            btn = QPushButton()
            btn.setStyleSheet("text-align: left; padding: 10px;")
            btn.clicked.connect(lambda _checked=False, m=mode: self._choose(m))
            if mode is default:
                btn.setDefault(True)
            layout.addWidget(btn)
            self.buttons[mode] = btn

        self.language_label: Optional[QLabel] = None
        self.language_combo: Optional[QComboBox] = None
        languages = available_languages()
        if len(languages) > 1:
            row = QHBoxLayout()
            row.addStretch()
            self.language_label = QLabel()
            row.addWidget(self.language_label)
            self.language_combo = QComboBox()
            for language in languages:
                self.language_combo.addItem(language.name, language.code)
            self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(current_language())))
            self.language_combo.currentIndexChanged.connect(self._on_language_changed)
            row.addWidget(self.language_combo)
            layout.addLayout(row)

        self._retranslate()

    def _retranslate(self) -> None:
        """(Re)apply every text in the active language; also used when the language changes."""
        self.setWindowTitle(_("OFM Webcam Viewer \u2014 select mode"))
        self.heading.setText("<b>" + _("How is this device set up?") + "</b>")
        for mode, btn in self.buttons.items():
            btn.setText(f"{mode.label}\n{mode.description}")
        if self.language_label is not None:
            self.language_label.setText(_("Language:"))

    def _on_language_changed(self, index: int) -> None:
        code = self.language_combo.itemData(index)
        apply_language(code)
        save_language(code)  # remembered for the next launch
        self._retranslate()

    def _choose(self, mode: AppMode) -> None:
        self.selected = mode
        self.accept()

    @classmethod
    def ask(cls, default: AppMode = AppMode.AUTOMATED) -> Optional[AppMode]:
        dialog = cls(default)
        dialog.exec_()
        return dialog.selected


def choose_mode(requested: Optional[AppMode]) -> Optional[AppMode]:
    """The mode to start: `requested` (from the command line) if given, else
    whatever the user picks in the start dialog. None if they closed the dialog.
    Needs a QApplication when it has to show the dialog."""
    return requested if requested is not None else ModeDialog.ask()
