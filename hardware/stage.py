"""
Concrete implementations of stage controllers.
"""

import abc
import time
import serial
from typing import Tuple
from .abstract import StageController


class ArduinoStageController(StageController):
    """
    Concrete implementation of StageController for the Arduino-based setup.
    """

    def __init__(self, port='COM12', baudrate=9600, timeout=1):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None
        self._connected = False
        self.x = 0
        self.y = 0
        self.z = 0

        # Initialize Base (Default Calibration)
        # User defaults: 244nm in y, 610nm in x, 305.5nm in z
        self.scale_nm_per_step_x = 610.0
        self.scale_nm_per_step_y = 244.0
        self.scale_nm_per_step_z = 305.5

    def get_position(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)

    def set_position(self, x=0, y=0, z=0, relative_move_to_target=False):
        if relative_move_to_target:
             dx_steps = int(x) - self.x
             dy_steps = int(y) - self.y
             dz_steps = int(z) - self.z

             if dx_steps != 0: self.move_steps('R' if dx_steps>0 else 'L', abs(dx_steps), 0)
             if dy_steps != 0: self.move_steps('U' if dy_steps>0 else 'D', abs(dy_steps), 0)
             if dz_steps != 0: self.move_steps('W' if dz_steps>0 else 'S', abs(dz_steps), 0)
        else:
             self.x = int(x)
             self.y = int(y)
             self.z = int(z)

    def connect(self):
        try:
            self.connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(2)  # Wait for Arduino reset
            self._connected = True
            print(f"Stage connected on {self.port}")
        except Exception as e:
            print(f"Could not connect to Stage at {self.port}: {e}")
            self._connected = False
            self.connection = None

    def disconnect(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
        self._connected = False
        self.connection = None

    def is_connected(self) -> bool:
        return self._connected and self.connection and self.connection.is_open

    def send_command(self, cmd: str):
        if self.is_connected():
            try:
                self.connection.write(cmd.encode())
                self.connection.flush()
            except Exception as e:
                print(f"Error sending command '{cmd}': {e}")
        else:
            print("Stage not connected (send_command)")

    def _move_steps_raw(self, command_char: str, steps: int, delay_per_step: float, callback=None):
        """
        Moves the stage by sending `command_char` repeatedly.
        """
        if not self.is_connected():
            print("Stage not connected (move_steps)")
            return

        steps = int(max(0, steps))
        cmd = command_char.upper() # Ensure uppercase as per original code
        self._stop_requested = False

        # Determine direction for position tracking
        dx, dy, dz = 0, 0, 0
        if cmd == 'L': dx = -1
        elif cmd == 'R': dx = 1
        elif cmd == 'U': dy = 1
        elif cmd == 'D': dy = -1
        elif cmd == 'W': dz = 1
        elif cmd == 'S': dz = -1

        # Track actual steps executed
        actual_steps = 0
        for _ in range(steps):
            if self._stop_requested:
                print("Stage movement aborted.")
                break

            try:
                self.connection.write(cmd.encode())
                self.connection.flush()
                time.sleep(delay_per_step)
                actual_steps += 1
                if callback:
                    callback()
            except Exception as e:
                print(f"Error during move_steps: {e}")
                break

        # Update position based on actual steps executed
        self.x += dx * actual_steps
        self.y += dy * actual_steps
        self.z += dz * actual_steps

    def set_step_delay(self, delay_us: int) -> bool:
        """
        Sets the step delay. Not supported on Arduino implementation.
        """
        print("Speed control (step delay) not supported on Arduino controller.")
        return False

    def stop(self):
        self._stop_requested = True
        return True


# Try import Sangaboard
try:
    from sangaboard import Sangaboard
except ImportError:
    Sangaboard = None
    print("Sangaboard module not found. SangaboardStageController will not be available.")


class SangaboardStageController(StageController):
    """
    Implementation of StageController for Sangaboard.
    """
    def __init__(self, port, timeout=2):
        super().__init__()
        self.port = port
        self.timeout = timeout
        self.sb = None
        self._connected = False
        self.x = 0
        self.y = 0
        self.z = 0

        # User defaults: Sangaboard step size 12.2nm
        self.scale_nm_per_step_x = 12.2
        self.scale_nm_per_step_y = 12.2
        self.scale_nm_per_step_z = 12.2

        # Enforce Sangaboard speed limit
        self.min_step_delay_us = 1000

    def get_position(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)

    def set_position(self, x=0, y=0, z=0, relative_move_to_target=False):
        if relative_move_to_target:
             dx_steps = int(x) - self.x
             dy_steps = int(y) - self.y
             dz_steps = int(z) - self.z

             if dx_steps != 0: self.move_steps('R' if dx_steps>0 else 'L', abs(dx_steps), 0)
             if dy_steps != 0: self.move_steps('U' if dy_steps>0 else 'D', abs(dy_steps), 0)
             if dz_steps != 0: self.move_steps('W' if dz_steps>0 else 'S', abs(dz_steps), 0)
        else:
             self.x = int(x)
             self.y = int(y)
             self.z = int(z)

    def connect(self):
        if Sangaboard is None:
            print("Sangaboard library not available.")
            return
        try:
            # Sangaboard init opens the port
            self.sb = Sangaboard(port=self.port, timeout=self.timeout)
            self._connected = True
            print(f"Sangaboard connected on {self.port}")
        except Exception as e:
            print(f"Could not connect to Sangaboard at {self.port}: {e}")
            self._connected = False
            self.sb = None

    def disconnect(self):
        if self.sb:
            try:
                self.sb.close()
            except Exception:
                pass
        self._connected = False
        self.sb = None

    def is_connected(self) -> bool:
        return self._connected and self.sb is not None

    def send_command(self, cmd: str):
        # Maps raw chars to moves if possible, or ignores/logs.
        if len(cmd) == 1 and cmd.upper() in "LRUDSW":
            self.move_steps(cmd.upper(), 1, 0)
        else:
            print(f"SangaboardStageController: Unknown/unsupported command '{cmd}'")

    def _move_steps_raw(self, command_char: str, steps: int, delay_per_step: float, callback=None):
        if not self.is_connected():
            print("Sangaboard not connected")
            return

        cmd = command_char.upper()
        self._stop_requested = False
        dx, dy, dz = 0, 0, 0

        if cmd == 'L': dx = -1
        elif cmd == 'R': dx = 1
        elif cmd == 'U': dy = 1
        elif cmd == 'D': dy = -1
        elif cmd == 'W': dz = 1
        elif cmd == 'S': dz = -1
        else:
            print(f"Unknown move command: {cmd}")
            return

        total_dx = dx * steps
        total_dy = dy * steps
        total_dz = dz * steps

        if total_dx == 0 and total_dy == 0 and total_dz == 0:
            return

        print(f"[Sangaboard] Move requesting: {[total_dx, total_dy, total_dz]} (Total)")

        chunk_size = 1000
        steps_remaining = steps

        try:
            while steps_remaining > 0:
                 if self._stop_requested:
                     print("[Sangaboard] Move aborted by user.")
                     break

                 current_chunk = min(steps_remaining, chunk_size)
                 c_dx = dx * current_chunk
                 c_dy = dy * current_chunk
                 c_dz = dz * current_chunk

                 # print(f"[Sangaboard] Moving chunk: {[c_dx, c_dy, c_dz]}")
                 t0 = time.time()
                 self.sb.move_rel([c_dx, c_dy, c_dz])
                 # dt = time.time() - t0

                 self.x += c_dx
                 self.y += c_dy
                 self.z += c_dz

                 steps_remaining -= current_chunk

            print(f"[Sangaboard] Move Sequence Complete.")
            if callback:
                callback()

        except Exception as e:
            print(f"Error during Sangaboard move: {e}")

    def set_step_delay(self, delay_us: int) -> bool:
        if not self.is_connected():
            print("Sangaboard not connected")
            return False

        try:
            # Enforce limit silently
            if delay_us < self.min_step_delay_us:
                delay_us = self.min_step_delay_us

            print(f"[Sangaboard] Setting step_delay to {delay_us} us")
            self.sb.step_time = int(delay_us)
            return True
        except Exception as e:
            print(f"Error setting step delay on Sangaboard: {e}")
            return False

    def stop(self):
        """Stop Sangaboard movement immediately."""
        self._stop_requested = True
        if self.is_connected() and self.sb:
            try:
                # Use Sangaboard's stop method if available
                if hasattr(self.sb, 'stop'):
                    self.sb.stop()
                else:
                    # Fallback: send immediate stop command
                    self.sb.move_rel([0, 0, 0])
                print("Sangaboard movement stopped.")
                return True
            except Exception as e:
                print(f"Error stopping Sangaboard: {e}")
                return False
        return True


class MockStageController(StageController):
    """
    Mock implementation of StageController for simulation/testing.
    Simulates all hardware operations without requiring physical devices.
    """

    def __init__(self, simulation_speed_multiplier=10.0):
        """
        Initialize mock stage controller.
        
        Args:
            simulation_speed_multiplier: Speed up simulation by this factor
                                       (e.g., 10.0 = 10x faster than real hardware)
        """
        super().__init__()
        self._connected = True  # Always connected
        self.x = 0
        self.y = 0
        self.z = 0
        
        # Simulation settings
        self.simulation_speed_multiplier = simulation_speed_multiplier
        
        # Use same calibration as Sangaboard for realistic simulation
        self.scale_nm_per_step_x = 12.2
        self.scale_nm_per_step_y = 12.2
        self.scale_nm_per_step_z = 12.2
        
        print("[MockStageController] Initialized (simulation mode)")

    def get_position(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)

    def set_position(self, x=0, y=0, z=0, relative_move_to_target=False):
        if relative_move_to_target:
             dx_steps = int(x) - self.x
             dy_steps = int(y) - self.y
             dz_steps = int(z) - self.z

             if dx_steps != 0: self.move_steps('R' if dx_steps>0 else 'L', abs(dx_steps), 0)
             if dy_steps != 0: self.move_steps('U' if dy_steps>0 else 'D', abs(dy_steps), 0)
             if dz_steps != 0: self.move_steps('W' if dz_steps>0 else 'S', abs(dz_steps), 0)
        else:
             self.x = int(x)
             self.y = int(y)
             self.z = int(z)
             print(f"[MockStageController] Position set to ({self.x}, {self.y}, {self.z})")

    def connect(self):
        """Simulate connection - always succeeds."""
        self._connected = True
        print("[MockStageController] Connected (simulation)")
        return True

    def disconnect(self):
        """Simulate disconnection."""
        self._connected = False
        print("[MockStageController] Disconnected (simulation)")

    def is_connected(self) -> bool:
        return self._connected

    def send_command(self, cmd: str):
        """Simulate sending a command."""
        if len(cmd) == 1 and cmd.upper() in "LRUDSW":
            self.move_steps(cmd.upper(), 1, 0)
        else:
            print(f"[MockStageController] Unknown command '{cmd}'")

    def _move_steps_raw(self, command_char: str, steps: int, delay_per_step: float, callback=None):
        """
        Simulate moving steps with realistic timing.
        """
        cmd = command_char.upper()
        self._stop_requested = False
        dx, dy, dz = 0, 0, 0

        if cmd == 'L': dx = -1
        elif cmd == 'R': dx = 1
        elif cmd == 'U': dy = 1
        elif cmd == 'D': dy = -1
        elif cmd == 'W': dz = 1
        elif cmd == 'S': dz = -1
        else:
            print(f"[MockStageController] Unknown move command: {cmd}")
            return

        # Simulate movement with accelerated timing
        steps = int(max(0, steps))
        actual_steps = 0
        
        # Speed up simulation by dividing delay
        sim_delay = delay_per_step / self.simulation_speed_multiplier if delay_per_step > 0 else 0.001
        
        for _ in range(steps):
            if self._stop_requested:
                print("[MockStageController] Movement aborted.")
                break
            
            time.sleep(sim_delay)
            actual_steps += 1
            if callback:
                callback()

        # Update position
        self.x += dx * actual_steps
        self.y += dy * actual_steps
        self.z += dz * actual_steps
        
        pos_um = (self.x * self.scale_nm_per_step_x / 1000.0,
                  self.y * self.scale_nm_per_step_y / 1000.0,
                  self.z * self.scale_nm_per_step_z / 1000.0)
        print(f"[MockStageController] Moved {cmd} {actual_steps} steps -> Position: ({pos_um[0]:.2f}, {pos_um[1]:.2f}, {pos_um[2]:.2f}) µm")

    def set_step_delay(self, delay_us: int) -> bool:
        """Simulate setting step delay."""
        print(f"[MockStageController] Step delay set to {delay_us} us (simulation)")
        return True

    def stop(self):
        """Simulate stopping movement."""
        self._stop_requested = True
        print("[MockStageController] Movement stopped (simulation)")
        return True
