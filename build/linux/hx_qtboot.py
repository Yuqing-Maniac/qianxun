"""Relocation helper (loaded via hx_qtboot.pth).
Qt decodes its self-discovered plugin dir with the 8-bit locale codec, which breaks
when the runtime lives under a non-ASCII path (e.g. /home/用户/...) and LANG is C/POSIX.
In that case, set the Qt library path explicitly from Python (always UTF-8 correct)."""
import os, sys
def _fix():
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here.isascii():
            return
        d = os.path.join(here, 'PyQt5', 'Qt5', 'plugins')
        if not os.path.isdir(d):
            return
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.setLibraryPaths([d])
    except Exception:
        pass
_fix()
