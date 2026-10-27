"""About / License dialog: what this program is, its version, and its license."""

from __future__ import annotations

from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QDialog, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from core.app_info import APP_NAME, LICENSE_NAME, LICENSE_NOTICE, LICENSE_URL, load_license_text
from core.i18n import _
from core.version import __version__


class AboutDialog(QDialog):
    """Modal. The summary comes first; the full license text is below it,
    read from the LICENSE file at the moment the dialog opens."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("About / License"))
        self.resize(640, 520)
        layout = QVBoxLayout(self)

        title = QLabel(f"<h3>{APP_NAME}</h3>" + _("Version {version}").format(version=__version__))
        layout.addWidget(title)

        notice = QLabel(_(LICENSE_NOTICE))
        notice.setWordWrap(True)
        layout.addWidget(notice)

        link = QLabel(f'{LICENSE_NAME}: <a href="{LICENSE_URL}">{LICENSE_URL}</a>')
        link.setOpenExternalLinks(True)
        link.setWordWrap(True)
        layout.addWidget(link)

        self.license_view = QPlainTextEdit()
        self.license_view.setReadOnly(True)
        self.license_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.license_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        text = load_license_text()
        self.license_view.setPlainText(
            text if text is not None
            else _("The license text file was not found in this installation. The full text is at {url}").format(url=LICENSE_URL)
        )
        layout.addWidget(self.license_view, stretch=1)

        close = QPushButton(_("Close"))
        close.clicked.connect(self.accept)
        layout.addWidget(close)
