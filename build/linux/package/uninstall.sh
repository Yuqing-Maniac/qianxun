#!/bin/sh
# QianXun uninstaller (POSIX sh)
#
#   ./uninstall.sh [--purge]            remove a user-mode install
#   sudo ./uninstall.sh --system [--purge]   remove a system-mode install
#
# User config (~/.config/qianxun) and cache (~/.cache/qianxun) are kept
# unless --purge is given.

APP_ID=qianxun

MODE=user
PURGE=0

for arg in "$@"; do
    case "$arg" in
        --system) MODE=system ;;
        --purge) PURGE=1 ;;
        -h|--help)
            echo "Usage: $0 [--system] [--purge]"
            exit 0
            ;;
        *)
            echo "error: unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

die() {
    echo "error: $*" >&2
    exit 1
}

# Remove a file or symlink if present, reporting what was done.
remove_path() {
    if [ -e "$1" ] || [ -L "$1" ]; then
        rm -rf "$1" || die "cannot remove $1"
        echo "removed: $1"
    fi
}

# Print the desktop directory for the current user (same rule as install.sh).
find_desktop_dir() {
    _d=""
    if command -v xdg-user-dir >/dev/null 2>&1; then
        _d=$(xdg-user-dir DESKTOP 2>/dev/null)
        if [ "$_d" = "$1" ]; then
            _d=""
        fi
    fi
    if [ -z "$_d" ]; then
        _cn="$1/$(printf '\346\241\214\351\235\242')"
        if [ -d "$_cn" ]; then
            _d=$_cn
        else
            _d="$1/Desktop"
        fi
    fi
    printf '%s' "$_d"
}

refresh_caches() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$1" >/dev/null 2>&1 || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1 && [ -d "$2" ]; then
        gtk-update-icon-cache -q -t -f "$2" >/dev/null 2>&1 || true
    fi
}

purge_user_data() {
    _home=$1
    remove_path "$_home/.config/$APP_ID"
    remove_path "$_home/.cache/$APP_ID"
}

uninstall_user() {
    echo "mode: user"
    DEST_DIR=$HOME/.local/share/$APP_ID
    APPS_DIR=$HOME/.local/share/applications
    ICONS_DIR=$HOME/.local/share/icons/hicolor

    remove_path "$DEST_DIR"
    remove_path "$APPS_DIR/$APP_ID.desktop"
    for s in 16 32 48 64 128 256; do
        remove_path "$ICONS_DIR/${s}x${s}/apps/$APP_ID.png"
    done
    remove_path "$ICONS_DIR/scalable/apps/$APP_ID.svg"
    remove_path "$HOME/.local/bin/$APP_ID"
    remove_path "$HOME/.config/autostart/$APP_ID.desktop"

    for _d in "$(find_desktop_dir "$HOME")" "$HOME/Desktop" "$HOME/$(printf '\346\241\214\351\235\242')"; do
        remove_path "$_d/$APP_ID.desktop"
    done

    if [ "$PURGE" = 1 ]; then
        purge_user_data "$HOME"
    else
        echo "kept: $HOME/.config/$APP_ID and $HOME/.cache/$APP_ID (use --purge to remove)"
    fi

    refresh_caches "$APPS_DIR" "$ICONS_DIR"
    echo "done: user uninstall complete"
}

uninstall_system() {
    echo "mode: system"
    [ "$(id -u)" = 0 ] || die "--system requires root (use sudo)"

    remove_path "/opt/$APP_ID"
    remove_path "/usr/share/applications/$APP_ID.desktop"
    for s in 16 32 48 64 128 256; do
        remove_path "/usr/share/icons/hicolor/${s}x${s}/apps/$APP_ID.png"
    done
    remove_path "/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
    remove_path "/usr/local/bin/$APP_ID"
    remove_path "/etc/xdg/autostart/$APP_ID.desktop"

    if [ "$PURGE" = 1 ]; then
        purge_user_data "$HOME"
        if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
            _uhome=$(getent passwd "$SUDO_USER" 2>/dev/null | cut -d: -f6)
            if [ -n "$_uhome" ] && [ -d "$_uhome" ]; then
                purge_user_data "$_uhome"
            fi
        fi
    else
        echo "kept: per-user config and cache (use --purge to remove)"
    fi

    refresh_caches "/usr/share/applications" "/usr/share/icons/hicolor"
    echo "done: system uninstall complete"
}

case "$MODE" in
    system) uninstall_system ;;
    *) uninstall_user ;;
esac
