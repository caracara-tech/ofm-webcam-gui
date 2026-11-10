"""
Why this exists: a QLabel that shows a pixmap reports the pixmap's size as its
size hint, and the old code also pinned the label to the camera resolution with
setFixedSize(). Either way the *content* decided the window's minimum size, so
the window could not be shrunk, could not follow a maximize, and kept the
stream's size after the stream ended (error text, "Camera stopped").

VideoView inverts that: its size hints are constants, and the picture is scaled
to whatever room the layout gives it, keeping the aspect ratio (letterboxed).
Text messages and the snapshot flash are painted by the widget itself, so no
child widgets need their geometry kept in sync.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QSizePolicy, QWidget

# Smallest the preview may be squeezed to. Small on purpose: the window must fit
# a 1280x720 screen together with the controls column.
MIN_PREVIEW_SIZE = QSize(320, 240)
# What the window asks for before it has been resized (not a constraint).
PREFERRED_PREVIEW_SIZE = QSize(640, 480)

BACKGROUND = QColor("#111111")
MESSAGE_COLOR = QColor("#888888")
FLASH_COLOR = QColor("#ffffff")
MESSAGE_MARGIN_PX = 16


class VideoView(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Expanding in both directions, but the hints below are constant, so the
        # content can never push the layout around.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent)  # we paint every pixel: no background erase flicker

        self._image: Optional[QImage] = None
        self._buffer: Optional[object] = None  # keeps the numpy array behind _image alive
        self._message = ""
        self._flashing = False

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_flash)

    # ------------------------------------------------------------ size hints --
    def sizeHint(self) -> QSize:
        return PREFERRED_PREVIEW_SIZE

    def minimumSizeHint(self) -> QSize:
        return MIN_PREVIEW_SIZE

    # --------------------------------------------------------------- content --
    def show_frame(self, image: QImage, buffer: object = None) -> None:
        """Show a frame. `buffer` is whatever memory `image` was built on (a
        QImage made from a numpy array does not copy it), kept until replaced."""
        self._image = image
        self._buffer = buffer
        self._message = ""
        self.update()

    def show_message(self, text: str) -> None:
        """Drop the picture and show `text` (wrapped and clipped, never resizing)."""
        self._image = None
        self._buffer = None
        self._message = text
        self.update()

    def flash(self, duration_ms: int) -> None:
        """White flash over the picture (snapshot feedback)."""
        self._flashing = True
        self._flash_timer.start(duration_ms)
        self.update()

    def _end_flash(self) -> None:
        self._flashing = False
        self.update()

    # ----------------------------------------------------------------- paint --
    def image_rect(self) -> QRect:
        """Where the picture is drawn: the largest rectangle of the image's
        aspect ratio that fits the widget, centred."""
        if self._image is None or self._image.isNull():
            return self.rect()
        size = self._image.size().scaled(self.size(), Qt.KeepAspectRatio)
        target = QRect(0, 0, size.width(), size.height())
        target.moveCenter(self.rect().center())
        return target

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKGROUND)
        if self._image is not None and not self._image.isNull():
            target = self.image_rect()
            # Smooth only when shrinking: upscaling a live picture gains nothing
            # from it and costs time on every frame.
            painter.setRenderHint(QPainter.SmoothPixmapTransform, target.width() < self._image.width())
            painter.drawImage(target, self._image)
            if self._flashing:
                painter.fillRect(target, FLASH_COLOR)
        elif self._message:
            painter.setPen(MESSAGE_COLOR)
            m = MESSAGE_MARGIN_PX
            area = QRectF(self.rect().adjusted(m, m, -m, -m))
            painter.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, self._message)
        painter.end()
