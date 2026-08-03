"""Manual stage jog controls, step/speed settings, and live position display."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox,
)

from core.types import Direction, Position, StageMotionSettings

_DIRECTION_BUTTONS = [
    (Direction.UP, "U", 0, 1),
    (Direction.DOWN, "D", 1, 1),
    (Direction.LEFT, "L", 1, 0),
    (Direction.RIGHT, "R", 1, 2),
    (Direction.FORWARD, "W \u2191", 0, 3),
    (Direction.BACKWARD, "S \u2193", 1, 3),
]


class StagePanel(QGroupBox):
    """Emits `jog_requested(Direction)` on button press and
    `settings_changed(StageMotionSettings)` whenever the user edits a spinbox."""

    jog_requested = pyqtSignal(object)  # Direction
    settings_changed = pyqtSignal(object)  # StageMotionSettings

    def __init__(self, initial_settings: StageMotionSettings, parent=None):
        super().__init__("Stage Control", parent)
        self.settings = initial_settings
        layout = QGridLayout(self)

        for direction, label, row, col in _DIRECTION_BUTTONS:
            btn = QPushButton(label)
            btn.setMaximumWidth(60)
            btn.clicked.connect(lambda checked=False, d=direction: self.jog_requested.emit(d))
            layout.addWidget(btn, row, col)

        layout.addWidget(QLabel("XY Step (\u00b5m):"), 2, 0, 1, 2)
        self.xy_step_spin = QSpinBox()
        self.xy_step_spin.setRange(1, 1000)
        self.xy_step_spin.setValue(int(self.settings.xy_step_um))
        self.xy_step_spin.valueChanged.connect(self._emit_settings)
        layout.addWidget(self.xy_step_spin, 2, 2, 1, 2)

        layout.addWidget(QLabel("Z Step (\u00b5m):"), 3, 0, 1, 2)
        self.z_step_spin = QSpinBox()
        self.z_step_spin.setRange(1, 1000)
        self.z_step_spin.setValue(int(self.settings.z_step_um))
        self.z_step_spin.valueChanged.connect(self._emit_settings)
        layout.addWidget(self.z_step_spin, 3, 2, 1, 2)

        layout.addWidget(QLabel("Speed (\u00b5m/s):"), 4, 0, 1, 2)
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 1000)
        self.speed_spin.setValue(int(self.settings.speed_um_per_s))
        self.speed_spin.valueChanged.connect(self._emit_settings)
        layout.addWidget(self.speed_spin, 4, 2, 1, 2)

        layout.addWidget(QLabel("Position (\u00b5m):"), 5, 0, 1, 2)
        pos_layout = QHBoxLayout()
        self.pos_x_label = QLabel("X: 0.00")
        self.pos_y_label = QLabel("Y: 0.00")
        self.pos_z_label = QLabel("Z: 0.00")
        pos_layout.addWidget(self.pos_x_label)
        pos_layout.addWidget(self.pos_y_label)
        pos_layout.addWidget(self.pos_z_label)
        layout.addLayout(pos_layout, 6, 0, 1, 4)

        self.bed_check = QCheckBox("Auto-Level Z")
        self.bed_check.setChecked(self.settings.auto_level_z)
        self.bed_check.toggled.connect(self._emit_settings)
        layout.addWidget(self.bed_check, 7, 0, 1, 4)

    def _emit_settings(self, *_args) -> None:
        self.settings = StageMotionSettings(
            xy_step_um=float(self.xy_step_spin.value()),
            z_step_um=float(self.z_step_spin.value()),
            speed_um_per_s=float(self.speed_spin.value()),
            auto_level_z=self.bed_check.isChecked(),
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
