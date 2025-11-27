"""Utility to keep top-level PyQt windows alive by holding references."""
from __future__ import annotations

from typing import List

from PyQt6.QtCore import QObject

_WINDOW_REFS: List[QObject] = []


def keep_window(window: QObject) -> None:
    """Keep a reference to a top-level window to prevent premature GC."""
    if window in _WINDOW_REFS:
        return

    _WINDOW_REFS.append(window)

    def _cleanup(_obj=None, win=window):
        try:
            _WINDOW_REFS.remove(win)
        except ValueError:
            pass

    # type: ignore[arg-type]  # destroyed signal provides QObject
    window.destroyed.connect(_cleanup)

