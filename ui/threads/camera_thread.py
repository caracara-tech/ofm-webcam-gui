"""QThread that owns the cv2.VideoCapture and emits frames."""

from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal


class CameraThread(QThread):
    """Reads frames from a webcam in a background thread."""

    frame_ready = pyqtSignal(np.ndarray, float)
    error_occurred = pyqtSignal(str)

    def __init__(self, device_index: int, width: int, height: int, backend_flag: Optional[int], target_fps: int = 30):
        super().__init__()
        self.device_index = device_index
        self.width = width
        self.height = height
        self.backend_flag = backend_flag
        self.target_fps = target_fps
        self._running = False

    def run(self) -> None:
        self._running = True
        try:
            cap = self._open_capture()
            if cap is None or not cap.isOpened():
                self.error_occurred.emit(
                    f"Could not open camera at index {self.device_index}. "
                    f"Try a different device index or backend."
                )
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.target_fps)

            # Brief warm-up: some backends (esp. MSMF) need a moment before
            # the first frame is actually deliverable.
            warm_up_ok = False
            for _ in range(20):
                if not self._running:
                    cap.release()
                    return
                ret, _ = cap.read()
                if ret:
                    warm_up_ok = True
                    break
                time.sleep(0.1)

            if not warm_up_ok:
                self.error_occurred.emit(
                    f"Camera opened but never delivered a frame at index "
                    f"{self.device_index}. It may be in use by another app, "
                    f"or need a different backend."
                )
                cap.release()
                return

            last_time = time.time()
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    self.error_occurred.emit("Lost connection to camera (no frame).")
                    break
                now = time.time()
                dt = now - last_time
                last_time = now
                fps = 1.0 / dt if dt > 0 else 0.0
                self.frame_ready.emit(frame, fps)

            cap.release()
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        if self.backend_flag is None:
            return cv2.VideoCapture(self.device_index)
        cap = cv2.VideoCapture(self.device_index, self.backend_flag)
        if cap.isOpened():
            return cap
        cap.release()
        return cv2.VideoCapture(self.device_index)  # fallback to Auto

    def stop(self) -> None:
        self._running = False
        self.wait(2000)
