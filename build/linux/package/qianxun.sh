#!/bin/sh
# QianXun launcher - picks the best available Qt runtime, fully offline.
#   1. system python3 with PyQt5          (native input method / theme)
#   2. x86_64 + system python3.8 + bundled syspyqt (uses system Qt5 + fcitx)
#   3. bundled runtime (PyQt5/Qt5 on x86_64, PySide6/Qt6 on aarch64)
# Force a mode with QIANXUN_MODE=system|syspyqt|bundled
SELF=$(readlink -f "$0" 2>/dev/null || echo "$0")
HERE=$(cd "$(dirname "$SELF")" && pwd)
APP="$HERE/app/qianxun.py"
export PYTHONDONTWRITEBYTECODE=1

case "$(uname -m)" in
    x86_64|amd64) ARCH=x86_64 ;;
    aarch64|arm64) ARCH=aarch64 ;;
    *) ARCH=other ;;
esac

SYSPY=$(command -v python3 2>/dev/null)
MODE=${QIANXUN_MODE:-auto}

try_system() {
    [ -n "$SYSPY" ] || return 1
    "$SYSPY" -c "import PyQt5.QtWidgets, PyQt5.QtNetwork" >/dev/null 2>&1 || return 1
    exec "$SYSPY" "$APP" "$@"
}

try_syspyqt() {
    [ -n "$SYSPY" ] && [ -d "$HERE/syspyqt/$ARCH" ] || return 1
    PYTHONPATH="$HERE/syspyqt/$ARCH" "$SYSPY" -c "import PyQt5.QtWidgets, PyQt5.QtNetwork" >/dev/null 2>&1 || return 1
    PYTHONPATH="$HERE/syspyqt/$ARCH${PYTHONPATH:+:$PYTHONPATH}"
    export PYTHONPATH
    exec "$SYSPY" "$APP" "$@"
}

relocate() {
    # Extracted onto a USB drive (FAT/exFAT/NTFS) or a noexec mount: copy to $HOME and run from there.
    [ -n "${QIANXUN_RELOCATED:-}" ] && return 1
    DEST="${XDG_DATA_HOME:-$HOME/.local/share}/qianxun-portable"
    [ "$HERE" = "$DEST" ] && return 1
    if ! cmp -s "$HERE/app/qianxun.py" "$DEST/app/qianxun.py" 2>/dev/null || [ ! -f "$DEST/runtime/$ARCH/bin/python3.13" ]; then
        MSG="QianXun: copying to $DEST (cannot run from this drive) ..."
        echo "$MSG" >&2
        command -v notify-send >/dev/null 2>&1 && notify-send "QianXun" "$MSG" 2>/dev/null
        rm -rf "$DEST.tmp" && mkdir -p "$DEST.tmp" && cp -R "$HERE/." "$DEST.tmp/" || return 1
        rm -rf "$DEST" && mv "$DEST.tmp" "$DEST" || return 1
        chmod -R u+rwX "$DEST" 2>/dev/null
        chmod 755 "$DEST/qianxun.sh" "$DEST/runtime/$ARCH/bin/python3.13" 2>/dev/null
    fi
    QIANXUN_RELOCATED=1
    export QIANXUN_RELOCATED
    exec sh "$DEST/qianxun.sh" "$@"
}

try_bundled() {
    PY="$HERE/runtime/$ARCH/bin/python3.13"
    [ -f "$PY" ] || return 1
    if ! "$PY" -c "" >/dev/null 2>&1; then
        chmod 755 "$PY" 2>/dev/null
        "$PY" -c "" >/dev/null 2>&1 || relocate "$@"
    fi
    if [ "$ARCH" = aarch64 ]; then
        # Qt6 bundle: use fcitx plugin if bundled, else fall back to ibus protocol (fcitx5 serves it)
        PIC=$(find "$HERE/runtime/aarch64" -type d -name platforminputcontexts 2>/dev/null | head -n 1)
        case "${QT_IM_MODULE:-}" in
            fcitx*)
                if [ -n "$PIC" ] && ! ls "$PIC" 2>/dev/null | grep -q fcitx; then
                    QT_IM_MODULE=ibus
                    export QT_IM_MODULE
                fi ;;
        esac
    fi
    exec "$PY" "$APP" "$@"
}

fail() {
    MSG="QianXun cannot start: no usable Qt runtime for $(uname -m)."
    echo "$MSG" >&2
    if command -v zenity >/dev/null 2>&1; then zenity --error --text="$MSG" 2>/dev/null
    elif command -v notify-send >/dev/null 2>&1; then notify-send "QianXun" "$MSG"
    fi
    exit 1
}

case "$MODE" in
    system)  try_system "$@"; fail ;;
    syspyqt) try_syspyqt "$@"; fail ;;
    bundled) try_bundled "$@"; fail ;;
esac

try_system "$@"
[ "$ARCH" = x86_64 ] && try_syspyqt "$@"
try_bundled "$@"
fail
