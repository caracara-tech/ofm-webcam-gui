import abc
import numpy as np
import time

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

        # Backlash Compensation
        self.backlash_enabled = False
        self.backlash_dist_nm_x = 0.0
        self.backlash_dist_nm_y = 0.0
        self.backlash_dist_nm_z = 0.0
        # Safe direction: +1 or -1.
        # If moving in safe direction, no overshoot.
        # If moving against safe direction, overshoot and return.
        self.safe_dir_x = 1
        self.safe_dir_y = 1
        self.safe_dir_z = 1 # Usually Up is safe against gravity if leadscrew, or Down if we want to push against gravity?
                            # Request says: "for z, we go down and do steps up... for any down motion with backlash compensation we overshoot by set distance and come back up"
                            # This implies UP is the stored/safe direction (we end moving UP).
                            # So safe_dir_z = 1 (assuming 1 is UP/W).

    def get_position_nm(self):
        """Returns the current position in nanometers (x, y, z)."""
        x_step, y_step, z_step = self.get_position()
        return (x_step * self.scale_nm_per_step_x,
                y_step * self.scale_nm_per_step_y,
                z_step * self.scale_nm_per_step_z)

    def get_position_um(self):
        """Returns the current position in micrometers (x, y, z)."""
        x_nm, y_nm, z_nm = self.get_position_nm()
        return (x_nm / 1000.0, y_nm / 1000.0, z_nm / 1000.0)

    def steps_to_nm(self, steps, axis):
        if axis.lower() == 'x': return steps * self.scale_nm_per_step_x
        if axis.lower() == 'y': return steps * self.scale_nm_per_step_y
        if axis.lower() == 'z': return steps * self.scale_nm_per_step_z
        return 0

    def nm_to_steps(self, nm, axis):
        scale = 1.0
        if axis.lower() == 'x': scale = self.scale_nm_per_step_x
        if axis.lower() == 'y': scale = self.scale_nm_per_step_y
        if axis.lower() == 'z': scale = self.scale_nm_per_step_z
        # Round to nearest integer step
        return int(round(nm / scale)) if scale != 0 else 0

    def um_to_steps(self, um, axis):
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

    def move_steps(self, command_char: str, steps: int, delay_per_step: float, callback=None):
        """
        Move the stage by sending 'command_char' 'steps' times.
        Handles backlash compensation if enabled.
        """
        cmd = command_char.upper()
        if steps <= 0: return

        # Determine axis and direction
        axis = None
        direction_sign = 0

        if cmd == 'L': axis = 'x'; direction_sign = -1
        elif cmd == 'R': axis = 'x'; direction_sign = 1
        elif cmd == 'U': axis = 'y'; direction_sign = 1 # Assuming Up is +Y (check impl)
        elif cmd == 'D': axis = 'y'; direction_sign = -1
        elif cmd == 'W': axis = 'z'; direction_sign = 1
        elif cmd == 'S': axis = 'z'; direction_sign = -1

        if not self.backlash_enabled or not axis:
            # Direct move - enforce minimum delay
            enforced_delay = max(delay_per_step, self.min_step_delay_us / 1e6)  # Convert us to seconds
            self._move_steps_raw(cmd, steps, enforced_delay, callback)
            return

        # Check Safe Direction
        # Rules:
        # If moving in Safe Direction -> Direct Move
        # If moving against Safe Direction -> Move (Steps + Overshoot) then Move back (Overshoot) in Safe Direction.
        # WAIT.
        # User request: "for z, we go down and do steps up, for any down motion with backlash compensation we overshoot by set distance and come back up"
        # This implies: Target is DOWN. We go DOWN (Target + Overshoot), then UP (Overshoot).
        # This means we END moving UP.
        # So UP is the safe direction ("approach positions from the same side").
        # If we are ALREADY moving UP (Safe), we just move UP.

        safe_sign = 0
        backlash_nm = 0
        if axis == 'x':
            safe_sign = self.safe_dir_x
            backlash_nm = self.backlash_dist_nm_x
        elif axis == 'y':
            safe_sign = self.safe_dir_y
            backlash_nm = self.backlash_dist_nm_y
        elif axis == 'z':
            safe_sign = self.safe_dir_z
            backlash_nm = self.backlash_dist_nm_z

        backlash_steps = self.nm_to_steps(backlash_nm, axis)

        if backlash_steps > 0 and direction_sign != safe_sign:
            # Unsafe move: Overshoot
            overshoot = backlash_steps
            total_out = steps + overshoot

            # 1. Move Out (Target + Overshoot)
            enforced_delay = max(delay_per_step, self.min_step_delay_us / 1e6)  # Convert us to seconds
            self._move_steps_raw(cmd, total_out, enforced_delay, callback)

            # 2. Check stop before return move
            if self._stop_requested:
                # Movement was aborted, don't do return move to prevent position corruption
                return

            # 2. Move Back (Overshoot) in Safe Direction
            # Find safe char
            safe_char = ''
            if axis == 'x': safe_char = 'R' if safe_sign > 0 else 'L'
            elif axis == 'y': safe_char = 'U' if safe_sign > 0 else 'D'
            elif axis == 'z': safe_char = 'W' if safe_sign > 0 else 'S'

            # Little pause?
            time.sleep(0.05)
            self._move_steps_raw(safe_char, overshoot, enforced_delay, None)

        else:
            # Safe move or no backlash - enforce minimum delay
            enforced_delay = max(delay_per_step, self.min_step_delay_us / 1e6)  # Convert us to seconds
            self._move_steps_raw(cmd, steps, enforced_delay, callback)

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
