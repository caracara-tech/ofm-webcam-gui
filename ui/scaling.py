"""High-DPI configuration. Must run before the QApplication is created.

Without it, Qt 5 sizes text by each screen's DPI but sizes widgets in raw device
pixels, so the same window looks different on every monitor and a layout that
fits on one screen clips or overlaps on another (e.g. a 1080p panel next to a
scaled laptop display). With scaling on, all sizes are logical and Qt converts
per screen, including when the window is dragged between screens.
"""

from __future__ import annotations

from PyQt5.QtCore import QCoreApplication, Qt


def configure_high_dpi() -> None:
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # Qt >= 5.14: use the real scale factor (125 %, 150 %) instead of rounding
    # it to a whole number, which would make 125 % screens look 200 % sized.
    policy = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    setter = getattr(QCoreApplication, "setHighDpiScaleFactorRoundingPolicy", None)
    if policy is not None and setter is not None:
        setter(policy.PassThrough)
