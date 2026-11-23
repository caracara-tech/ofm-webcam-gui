"""Preview-overlay controls: alignment grid and a scale bar. This panel
only collects user input and emits signals/exposes properties - the
grid/scale-bar geometry lives in core/overlays.py; MainWindow wires the
two together, the same "dumb panel, smart core" split used elsewhere.

Scale bar defaults to pixel units (fully automatic, no input required -
see core/overlays.py's module docstring for why that's the honest
default). A physical um/pixel override lives behind a collapsed
"Advanced" section, hidden until the user opts into it, for anyone who
has actually calibrated their setup and wants real-world units instead."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QLabel, QSpinBox, QToolButton, QWidget

from core.help_topics import HelpTopic
from core.i18n import _
from core.overlays import ScaleBarColor
from ui.widgets.help import HelpGroupBox, add_help, reserve_help_column, set_tip

_HELP_COLUMN = 2  # the controls use columns 0-1; this one is reserved for the "?" marks

DEFAULT_GRID_SPACING_PX = 40
DEFAULT_UM_PER_PIXEL = 1.0


class DisplayPanel(HelpGroupBox):
    grid_toggled = pyqtSignal(bool)
    grid_spacing_changed = pyqtSignal(int)
    scale_bar_toggled = pyqtSignal(bool)
    # Emits the new override value (float) when enabled/changed, or None
    # when the override is turned off (falling back to automatic pixels).
    um_per_pixel_override_changed = pyqtSignal(object)
    # The panel grew or shrank (Advanced expanded/collapsed): the window should re-fit.
    layout_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(_("Display"), parent)
        self.set_help(HelpTopic.DISPLAY_SECTION)
        layout = QGridLayout(self)
        reserve_help_column(layout, _HELP_COLUMN)
        row = 0

        self.grid_check = QCheckBox(_("Show grid"))
        set_tip(self.grid_check, HelpTopic.DISPLAY_GRID)
        self.grid_check.toggled.connect(self.grid_toggled.emit)
        layout.addWidget(self.grid_check, row, 0)

        self.grid_spacing_spin = QSpinBox()
        self.grid_spacing_spin.setRange(10, 500)
        self.grid_spacing_spin.setSuffix(" px")
        set_tip(self.grid_spacing_spin, HelpTopic.DISPLAY_GRID)
        self.grid_spacing_spin.setValue(DEFAULT_GRID_SPACING_PX)
        self.grid_spacing_spin.valueChanged.connect(self.grid_spacing_changed.emit)
        layout.addWidget(self.grid_spacing_spin, row, 1)
        row += 1

        self.scale_bar_check = QCheckBox(_("Show scale bar"))
        set_tip(self.scale_bar_check, HelpTopic.DISPLAY_SCALE_BAR)
        self.scale_bar_check.toggled.connect(self.scale_bar_toggled.emit)
        layout.addWidget(self.scale_bar_check, row, 0)

        # White or black bar: pick whichever reads better on the sample.
        self.scale_bar_color_combo = QComboBox()
        self.scale_bar_color_combo.addItem(_("White"), ScaleBarColor.WHITE.value)
        self.scale_bar_color_combo.addItem(_("Black"), ScaleBarColor.BLACK.value)
        set_tip(self.scale_bar_color_combo, HelpTopic.DISPLAY_SCALE_COLOR)
        self.scale_bar_color_combo.setEnabled(False)
        self.scale_bar_check.toggled.connect(self.scale_bar_color_combo.setEnabled)
        layout.addWidget(self.scale_bar_color_combo, row, 1)
        row += 1

        scale_hint = QLabel(
            _(
                "Automatic - reads in pixels (e.g. \"100 px\"), computed "
                "directly from the image. No calibration needed."
            )
        )
        scale_hint.setWordWrap(True)
        layout.addWidget(scale_hint, row, 0, 1, 2)
        row += 1

        # --- Advanced: physical-unit override, collapsed by default ----
        self.advanced_toggle_btn = QToolButton()
        self.advanced_toggle_btn.setText("\u25b8 " + _("Advanced"))
        self.advanced_toggle_btn.setCheckable(True)
        self.advanced_toggle_btn.setChecked(False)
        self.advanced_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        set_tip(self.advanced_toggle_btn, HelpTopic.DISPLAY_ADVANCED)
        self.advanced_toggle_btn.toggled.connect(self._on_advanced_toggled)
        layout.addWidget(self.advanced_toggle_btn, row, 0, 1, 2)
        row += 1

        self.advanced_frame = QWidget()
        adv_layout = QGridLayout(self.advanced_frame)
        adv_layout.setContentsMargins(12, 4, 0, 0)
        reserve_help_column(adv_layout, _HELP_COLUMN)

        self.override_check = QCheckBox(_("Override with physical calibration"))
        self.override_check.toggled.connect(self._on_override_toggled)
        adv_layout.addWidget(self.override_check, 0, 0, 1, 2)
        add_help(adv_layout, 0, HelpTopic.DISPLAY_CALIBRATION, column=_HELP_COLUMN, tips=(self.override_check,))

        adv_layout.addWidget(QLabel("um/pixel:"), 1, 0)
        self.um_per_pixel_spin = QDoubleSpinBox()
        self.um_per_pixel_spin.setRange(0.0001, 10000)
        self.um_per_pixel_spin.setDecimals(4)
        self.um_per_pixel_spin.setValue(DEFAULT_UM_PER_PIXEL)
        set_tip(self.um_per_pixel_spin, HelpTopic.DISPLAY_CALIBRATION)
        self.um_per_pixel_spin.setEnabled(False)
        self.um_per_pixel_spin.valueChanged.connect(self._emit_override)
        adv_layout.addWidget(self.um_per_pixel_spin, 1, 1)

        self.advanced_frame.setVisible(False)
        layout.addWidget(self.advanced_frame, row, 0, 1, _HELP_COLUMN + 1)  # reaches the help column, so its "?" lines up

    def _on_advanced_toggled(self, checked: bool) -> None:
        self.advanced_frame.setVisible(checked)
        self.advanced_toggle_btn.setText(("\u25be " if checked else "\u25b8 ") + _("Advanced"))
        self.layout_changed.emit()

    def _on_override_toggled(self, checked: bool) -> None:
        self.um_per_pixel_spin.setEnabled(checked)
        self._emit_override()

    def _emit_override(self) -> None:
        self.um_per_pixel_override_changed.emit(self.um_per_pixel_override)

    # ---- accessors used by MainWindow ----
    @property
    def show_grid(self) -> bool:
        return self.grid_check.isChecked()

    @property
    def grid_spacing_px(self) -> int:
        return self.grid_spacing_spin.value()

    @property
    def show_scale_bar(self) -> bool:
        return self.scale_bar_check.isChecked()

    @property
    def scale_bar_color(self) -> ScaleBarColor:
        return ScaleBarColor(self.scale_bar_color_combo.currentData())

    @property
    def um_per_pixel_override(self) -> Optional[float]:
        """The calibrated um/pixel value if the Advanced override is
        enabled, else None (meaning: use the automatic pixel-count bar)."""
        return self.um_per_pixel_spin.value() if self.override_check.isChecked() else None
