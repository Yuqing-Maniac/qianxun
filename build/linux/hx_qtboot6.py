"""Relocation helper for PySide6 (loaded via hx_qtboot.pth). See hx_qtboot.py."""
import os
def _fix():
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here.isascii():
            return
        d = os.path.join(here, 'PySide6', 'Qt', 'plugins')
        if not os.path.isdir(d):
            return
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.setLibraryPaths([d])
    except Exception:
        pass
_fix()
