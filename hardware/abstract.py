"""
Abstract base classes for hardware controllers.
"""

import abc
from typing import Tuple


class StageController(abc.ABC):
    """
    Abstract base class for stage controllers.
    Defines the interface for connecting, disconnecting, and moving the stage.
    """

    def __init__(self):
        # Calibration factors (nm per step)
        self.scale_nm_per_step_x = 100.0
        self.scale_nm_per_step_y = 100.0
        self.scale_nm_per_step_z = 100.0

        # Minimum delay between steps in microseconds
        self.min_step_delay_us = 0

        # Stop flag for aborting movements
        self._stop_requested = False

    def get_position_nm(self) -> Tuple[float, float, float]:
        """Returns the current position in nanometers (x, y, z)."""
        x_step, y_step, z_step = self.get_position()
        return (x_step * self.scale_nm_per_step_x,
                y_step * self.scale_nm_per_step_y,
                z_step * self.scale_nm_per_step_z)

    def get_position_um(self) -> Tuple[float, float, float]:
        """Returns the current position in micrometers (x, y, z)."""
        x_nm, y_nm, z_nm = self.get_position_nm()
        return (x_nm / 1000.0, y_nm / 1000.0, z_nm / 1000.0)

    def steps_to_nm(self, steps: int, axis: str) -> float:
        """Convert steps to nanometers for given axis."""
        if axis.lower() == 'x': return steps * self.scale_nm_per_step_x
        if axis.lower() == 'y': return steps * self.scale_nm_per_step_y
        if axis.lower() == 'z': return steps * self.scale_nm_per_step_z
        return 0

    def nm_to_steps(self, nm: float, axis: str) -> int:
        """Convert nanometers to steps for given axis."""
        scale = 1.0
        if axis.lower() == 'x': scale = self.scale_nm_per_step_x
        if axis.lower() == 'y': scale = self.scale_nm_per_step_y
        if axis.lower() == 'z': scale = self.scale_nm_per_step_z
        # Round to nearest integer step
        return int(round(nm / scale)) if scale != 0 else 0

    def um_to_steps(self, um: float, axis: str) -> int:
        """Convert micrometers to steps for given axis."""
        return self.nm_to_steps(um * 1000.0, axis)

    @abc.abstractmethod
    def connect(self):
        """Connect to the stage controller."""
        pass

    @abc.abstractmethod
    def disconnect(self):
        """Disconnect from the stage controller."""
        pass

    @abc.abstractmethod
    def is_connected(self) -> bool:
        """Check if the controller is connected."""
        pass

    @abc.abstractmethod
    def send_command(self, cmd: str):
        """Send a raw command to the controller."""
        pass

    @abc.abstractmethod
    def _move_steps_raw(self, command_char: str, steps: int, delay_per_step: float, callback=None):
        """
        Actual hardware implementation of moving steps.
        """
        pass

    @abc.abstractmethod
    def stop(self):
        """Stops any current movement immediately."""
        pass

    @abc.abstractmethod
    def set_step_delay(self, delay_us: int) -> bool:
        """
        Set the minimum time between steps in microseconds.
        Returns True if successful/supported, False otherwise.
        """
        pass

    @abc.abstractmethod
    def get_position(self) -> tuple:
        """Returns current (x, y, z) in steps."""
        pass

    @abc.abstractmethod
    def set_position(self, x=0, y=0, z=0, relative_move_to_target=False):
        """
        Sets the current logical position.
        If relative_move_to_target is True, it moves the stage solely by the difference
        between the current position and the target (x, y, z).
        If False (default), it just overwrites the internal position register (if supported).
        """
        pass


class SensorController(abc.ABC):
    """
    Abstract base class for sensor controllers (camera, power meter, etc.).
    Provides a common interface for measurement devices.
    """
    @abc.abstractmethod
    def connect(self):
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    @abc.abstractmethod
    def get_measurement(self):
        """Returns a measurement from the sensor. Type depends on sensor."""
        pass

    @abc.abstractmethod
    def get_averaged_measurement(self, n_avg=1, timeout_scale=1.0):
        """Returns an averaged measurement from multiple captures."""
        pass

    @abc.abstractmethod
    def get_device_info(self):
        """Returns device information (name, serial number, etc.)."""
        pass


class CameraController(SensorController):
    """
    Abstract base class for camera controllers.
    """
    @abc.abstractmethod
    def arm(self, buffer_count=2):
        pass

    @abc.abstractmethod
    def set_exposure(self, exposure_ms: float):
        pass

    @abc.abstractmethod
    def set_gain(self, gain_db: float):
        pass

    @abc.abstractmethod
    def start_acquisition(self):
        pass

    @abc.abstractmethod
    def stop_acquisition(self):
        pass

    @abc.abstractmethod
    def get_frame(self):
        """Returns a processed frame (2D numpy array) or None."""
        pass

    @abc.abstractmethod
    def get_averaged_frame(self, n_avg=1, timeout_scale=1.0):
        """Returns an averaged frame from multiple captures."""
        pass

    @abc.abstractmethod
    def set_roi(self, x, y, width, height):
        """Sets the hardware Region of Interest."""
        pass

    @abc.abstractmethod
    def reset_roi(self):
        """Resets ROI to full sensor."""
        pass

    @abc.abstractmethod
    def get_roi(self):
        """Returns (x, y, width, height)."""
        pass
