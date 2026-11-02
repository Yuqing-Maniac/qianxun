# Offline runtimes for hongxun.py (Galaxy Kylin V10, glibc >= 2.31)

Built 2026-10-17 in /home/claude/build. Both runtimes are relocatable: no PYTHONHOME, LD_LIBRARY_PATH,
QT_PLUGIN_PATH or QT_QPA_PLATFORM_PLUGIN_PATH needed (Qt libs found through RUNPATH `$ORIGIN`, plugins through the
Qt-in-wheel layout). Python is a static python-build-standalone interpreter (all stdlib C modules built in), so
`bin/python3` has no libpython dependency.

## Launcher (POSIX sh)
```sh
#!/bin/sh
HERE=$(cd "$(dirname "$0")" && pwd)
case "$(uname -m)" in x86_64) A=x86_64;; aarch64|arm64) A=aarch64;; *) echo "unsupported arch" >&2; exit 1;; esac
export PYTHONDONTWRITEBYTECODE=1          # optional, keeps install dir clean/read-only
exec "$HERE/runtime/$A/bin/python3" "$HERE/app/hongxun.py" "$@"
```
Optional: `QT_IM_MODULE=fcitx` (x86_64 only, plugin bundled) or `ibus`; Kylin normally exports it already.
`hx_qtboot.pth` (in site-packages) fixes the plugin path when the install dir has non-ASCII characters and the
locale is C/POSIX (Qt otherwise cannot find its plugins). It is automatic; do not run python with `-S`.

## x86_64 (runtime/x86_64)
- CPython 3.13.15 (pbs, glibc 2.17 baseline), PyQt5 5.15.11 (cp38-abi3 wheel, manylinux_2_17), PyQt5-Qt5 wheel 5.15.18
  (manylinux2014; QLibraryInfo reports Qt 5.15.14), PyQt5-sip 12.20.0 (cp313).
- Modules kept: QtCore, QtGui, QtWidgets, QtNetwork, QtDBus, QtSvg (+ `PyQt5.sip`, `uic`).
- Plugins: platforms xcb/offscreen/minimal; xcbglintegrations glx+egl; platforminputcontexts compose, ibus,
  **fcitx** (libfcitxplatforminputcontextplugin.so taken from Ubuntu focal fcitx-frontend-qt5 1.2.4, built for Qt 5.12;
  loads fine in 5.15, not tested against a live fcitx daemon); imageformats gif/ico/jpeg/svg (png/bmp built in);
  iconengines svg; platformthemes xdgdesktopportal (no gtk3 theme in the wheel); bearer generic. Translations: qtbase_zh_CN.qm only.
- Max required symbol versions: **GLIBC_2.17**, GLIBCXX_3.4.18, CXXABI_1.3.7 (33 ELF files).
- Size: 121 MB on disk (Python stdlib 13 MB, Qt payload 78 MB of which ICU data 24 MB), 44 MB as .tgz.

## aarch64 (runtime/aarch64)  -- PySide6 FALLBACK, NOT PyQt5
- PyPI has **no** aarch64 Linux wheel of PyQt5 or PyQt5-Qt5 (only x86_64 manylinux/mac/win), ports.ubuntu.com is
  unreachable, no PySide2 aarch64 either. Fallback = Qt 6: **PySide6 6.8.0.2 + shiboken6 6.8.0.2**
  (PySide6_Essentials cp39-abi3 manylinux_2_31_aarch64, Qt 6.8.0, ICU 73) on CPython 3.13.15 aarch64.
  The wheel metadata says Python <3.13, but shiboken 6.8.0.2 imports and QtCore/Gui/Widgets/Network/DBus/Svg load on
  3.13 (6.5.3 segfaults on 3.13). Alternative if problems: PyQt6 6.7.1 + PyQt6-Qt6 6.7.3 (manylinux_2_28), which
  keeps `pyqtSignal` but has strict enums.
- Modules kept: QtCore, QtGui, QtWidgets, QtNetwork, QtDBus, QtSvg, QtSvgWidgets.
- Plugins: platforms xcb/offscreen/minimal; xcbglintegrations glx+egl; platforminputcontexts compose, ibus
  (**no fcitx**); imageformats gif/ico/jpeg/svg; iconengines svg; platformthemes gtk3 + xdgdesktopportal; tls
  (certonly, openssl). No Qt translations shipped (the Qt6 wheel keeps them in a separate dir; trimmed).
- Extra: `libxcb-cursor.so.0` (Qt >= 6.5 hard requirement, not in Kylin) was cross-built from Ubuntu's
  xcb-util-cursor 0.1.4 source (MIT) and placed in PySide6/Qt/lib (links nothing but libxcb*/libc by NEEDED).
- Max required symbol versions: **GLIBC_2.30** (libpthread `pthread_cond_clockwait`, libQt6Core), **GLIBCXX_3.4.28**
  (needs libstdc++ of gcc >= 10; Ubuntu 20.04 has it, a Kylin box with gcc 7/8 runtime would not), CXXABI_1.3.11.
  40 ELF files, all AArch64.
- Size: 119 MB on disk (Qt+bindings 86 MB, ICU data 31 MB), 45 MB as .tgz.
- **App code needs a compat shim**: `from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork`;
  `pyqtSignal = Signal`, `pyqtSlot = Slot`, `pyqtProperty = Property`; `QAction`/`QShortcut` moved to QtGui;
  `QDesktopWidget` removed (use `QGuiApplication.screens()`); `app.exec_()` still works; unscoped enums
  (`Qt.AlignCenter`) work via PySide6 forgiveness mode. High-DPI is always on in Qt6.
- NEEDED libs that are neither bundled nor in the usual Ubuntu-20.04 desktop set: none exotic. Relies on system
  libzstd.so.1, libbrotlidec.so.1 (freetype dep), libresolv.so.2, libSM/libICE (Qt6XcbQpa), libxkbcommon(-x11),
  libxcb-{icccm,image,keysyms,render-util,xkb,xinerama...}, libGL/libEGL, libfontconfig, libfreetype, libdbus-1,
  libz. libgtk-3/libgdk/libpango/libgio/libgobject only for the optional libqgtk3.so theme plugin.

## Verification done
- x86_64: offscreen and xcb (xvfb) QApplication + QWidget + QLocalServer/QLocalSocket + QTimer quit, exit 0; also
  from a copied directory with spaces and Chinese characters under `env -i HOME=.. PATH=/usr/bin:/bin DISPLAY=..`
  (C locale), and with `QT_IM_MODULE=fcitx|ibus`. Test script: tests/smoke5.py.
- aarch64: executed under qemu-user (qemu-aarch64-static + Ubuntu noble libc/libstdc++ aarch64 cross libs) with
  generated stub .so files for the missing system libs (no arm64 rootfs available). Verified: interpreter + stdlib
  (ssl, sqlite3, ctypes, zlib), import of all 7 PySide6 modules + shiboken6, QCoreApplication/QLocalServer/QLocalSocket
  round trip, QImage pixel ops, QPluginLoader.load() of libqxcb, libqoffscreen, glx integration, ibus, svg, tls
  plugins, from a Chinese path. NOT verified: a real window, fonts, X11, input methods (needs real hardware).
  Use `QT_NO_GLIB=1` only in this emulated test, never needed on a real system.

## x86_64 "system-Qt mode" (syspyqt/x86_64)
- From Ubuntu focal debs: python3-pyqt5 5.14.1+dfsg-3build1 (QtCore, QtGui, QtWidgets, QtNetwork, QtDBus + __init__),
  python3-pyqt5.qtsvg 5.14.1 (QtSvg), python3-sip 4.19.21 (provides top-level `sip`; focal has no `python3-pyqt5.sip`
  package -- PyQt5 5.14 imports `sip`, not `PyQt5.sip`). Files: PyQt5/{__init__.py, Qt{Core,Gui,Widgets,Network,DBus,Svg}
  .cpython-38-x86_64-linux-gnu.so}, sip.cpython-38-x86_64-linux-gnu.so. 14 MB, max GLIBC_2.14.
- Usage: `PYTHONPATH=$HERE/syspyqt/x86_64 /usr/bin/python3 app/hongxun.py` -- ONLY with system **python3.8** (cp38 ABI-tagged
  names; Python 3.7 or 3.9+ cannot import them) plus system libqt5{core5a,gui5,widgets5,network5,dbus5,svg5} >= 5.12
  (Kylin desktop ships these, and its fcitx platform plugin). Untested here (no Python 3.8 in sandbox).
- arm64: not possible (archive.ubuntu.com has no arm64 index; ports/mirrors blocked). On Kylin aarch64 prefer
  the system `python3-pyqt5` (if `python3 -c "import PyQt5.QtWidgets"` works) when fcitx input is required, and use the
  bundled PySide6 runtime only as fallback.

## Caveats
- GitHub downloads are blocked in the sandbox, so python-build-standalone came from the npm packages
  `@rowstile/cli-linux-{x64,arm64}` 0.1.0-alpha.7 ("python-build-standalone 3.13.15, trimmed"), hence Python 3.13 (not 3.10/3.11).
  It lacks tkinter/ensurepip/pip (not needed). Re-test the app on 3.13 (removed modules: cgi, imp, asyncore, telnetlib...).
- x86_64: the Qt xcb plugin needs system libxcb-{icccm,image,keysyms,render-util,xinerama,xkb,...}, libxkbcommon-x11,
  libfontconfig, libfreetype, libGL, libX11, libglib, libdbus-1, libgssapi_krb5 (standard on any Ubuntu 20.04 /
  Kylin V10 desktop; none are bundled).
- aarch64 Chinese input: Qt6 has no fcitx4 plugin; ibus works if the ibus daemon runs. This is the main functional risk.
- Qt 6 / PySide6 needs GLIBCXX_3.4.28; check `strings /usr/lib/aarch64-linux-gnu/libstdc++.so.6 | grep GLIBCXX_3.4.28`.
- Tools: tools/trim_*.py (trimming), tools/maxglibc.py `<dir> [x]` (max GLIBC/GLIBCXX + non-bundled NEEDED).
