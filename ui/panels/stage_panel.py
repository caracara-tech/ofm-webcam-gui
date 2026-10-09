"""Manual stage jog controls, step/speed settings, and live position display."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox,
)

from core.i18n import _, pgettext
from core.types import Direction, Position, StageMotionSettings

# (direction, grid row, grid column) of each jog button.
_DIRECTION_LAYOUT = [
    (Direction.UP, 0, 1),
    (Direction.DOWN, 1, 1),
    (Direction.LEFT, 1, 0),
    (Direction.RIGHT, 1, 2),
    (Direction.FORWARD, 0, 3),
    (Direction.BACKWARD, 1, 3),
]


def direction_letter(direction: Direction) -> str:
    """Short name of a direction, as used on the jog buttons and in status
    messages. Built on demand (not at import) so it follows the active language."""
    return {
        # i18n: Jog button: move the stage up (a short abbreviation, 1-2 letters)
        Direction.UP: pgettext("jog button: up", "U"),
        # i18n: Jog button: move the stage down (a short abbreviation, 1-2 letters)
        Direction.DOWN: pgettext("jog button: down", "D"),
        # i18n: Jog button: move the stage left (a short abbreviation, 1-2 letters)
        Direction.LEFT: pgettext("jog button: left", "L"),
        # i18n: Jog button: move the stage right (a short abbreviation, 1-2 letters)
        Direction.RIGHT: pgettext("jog button: right", "R"),
        Direction.FORWARD: "W",
        Direction.BACKWARD: "S",
    }[direction]


def direction_label(direction: Direction) -> str:
    """Text of a jog button. The Z buttons are a letter plus an arrow."""
    return {
        Direction.FORWARD: "W \u2191",
        Direction.BACKWARD: "S \u2193",
    }.get(direction) or direction_letter(direction)


class StagePanel(QGroupBox):
    """Emits `jog_requested(Direction)` on button press and
    `settings_changed(StageMotionSettings)` whenever the user edits a spinbox."""

    jog_requested = pyqtSignal(object)  # Direction
    settings_changed = pyqtSignal(object)  # StageMotionSettings
    autofocus_requested = pyqtSignal()

    def __init__(self, initial_settings: StageMotionSettings, parent=None):
        super().__init__(_("Stage Control"), parent)
        self.settings = initial_settings
        layout = QGridLayout(self)

        self._direction_buttons: list[QPushButton] = []
        for direction, row, col in _DIRECTION_LAYOUT:
            btn = QPushButton(direction_label(direction))
            btn.setMaximumWidth(60)
            btn.clicked.connect(lambda checked=False, d=direction: self.jog_requested.emit(d))
            layout.addWidget(btn, row, col)
            self._direction_buttons.append(btn)

        layout.addWidget(QLabel(_("XY Step (\u00b5m):")), 2, 0, 1, 2)
        self.xy_step_spin = QSpinBox()
        self.xy_step_spin.setRange(1, 1000)
        self.xy_step_spin.setValue(int(self.settings.xy_step_um))
        self.xy_step_spin.valueChanged.connect(self._emit_settings)
        layout.addWidget(self.xy_step_spin, 2, 2, 1, 2)

        layout.addWidget(QLabel(_("Z Step (\u00b5m):")), 3, 0, 1, 2)
        self.z_step_spin = QSpinBox()
        self.z_step_spin.setRange(1, 1000)
        self.z_step_spin.setValue(int(self.settings.z_step_um))
        self.z_step_spin.valueChanged.connect(self._emit_settings)
        layout.addWidget(self.z_step_spin, 3, 2, 1, 2)

        layout.addWidget(QLabel(_("Speed (\u00b5m/s):")), 4, 0, 1, 2)
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 1000)
        self.speed_spin.setValue(int(self.settings.speed_um_per_s))
        self.speed_spin.valueChanged.connect(self._emit_settings)
        layout.addWidget(self.speed_spin, 4, 2, 1, 2)

        layout.addWidget(QLabel(_("Position (\u00b5m):")), 5, 0, 1, 2)
        pos_layout = QHBoxLayout()
        self.pos_x_label = QLabel("X: 0.00")
        self.pos_y_label = QLabel("Y: 0.00")
        self.pos_z_label = QLabel("Z: 0.00")
        pos_layout.addWidget(self.pos_x_label)
        pos_layout.addWidget(self.pos_y_label)
        pos_layout.addWidget(self.pos_z_label)
        layout.addLayout(pos_layout, 6, 0, 1, 4)

        self.autofocus_btn = QPushButton(_("Run Auto-Focus (Z sweep)"))
        self.autofocus_btn.clicked.connect(self.autofocus_requested.emit)
        layout.addWidget(self.autofocus_btn, 7, 0, 1, 4)

        self.autofocus_after_jog_check = QCheckBox(_("Auto-focus after each XY move"))
        self.autofocus_after_jog_check.setToolTip(
            _("Automatically re-runs the Z-sweep autofocus after every X/Y jog.")
        )
        self.autofocus_after_jog_check.setChecked(self.settings.autofocus_after_xy_jog)
        self.autofocus_after_jog_check.toggled.connect(self._emit_settings)
        layout.addWidget(self.autofocus_after_jog_check, 8, 0, 1, 4)

    def _emit_settings(self, *_args) -> None:
        self.settings = StageMotionSettings(
            xy_step_um=float(self.xy_step_spin.value()),
            z_step_um=float(self.z_step_spin.value()),
            speed_um_per_s=float(self.speed_spin.value()),
            autofocus_after_xy_jog=self.autofocus_after_jog_check.isChecked(),
        )
        self.settings_changed.emit(self.settings)

    def update_position_display(self, position_um: Position) -> None:
        self.pos_x_label.setText(f"X: {position_um.x:.2f}")
        self.pos_y_label.setText(f"Y: {position_um.y:.2f}")
        self.pos_z_label.setText(f"Z: {position_um.z:.2f}")

    def set_enabled_all(self, enabled: bool) -> None:
        for i in range(self.layout().count()):
            item = self.layout().itemAt(i)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setEnabled(enabled)

    def set_jog_enabled(self, enabled: bool) -> None:
        """Enable/disable just the direction and autofocus buttons - used to
        block new movement requests while one is already in flight, without
        touching the step/speed spinboxes or position labels."""
        for btn in self._direction_buttons:
            btn.setEnabled(enabled)
        self.autofocus_btn.setEnabled(enabled)
