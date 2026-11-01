#!/bin/sh
# QianXun installer (POSIX sh)
#
# User mode (default, no root needed):
#   ./install.sh [--autostart]
#   -> ~/.local/share/qianxun, ~/.local/share/applications, ~/.local/share/icons,
#      ~/.local/bin/qianxun, optional ~/.config/autostart, desktop shortcut.
#
# System mode (run as root):
#   sudo ./install.sh --system [--autostart]
#   -> /opt/qianxun, /usr/share/applications, /usr/share/icons/hicolor,
#      /usr/local/bin/qianxun, optional /etc/xdg/autostart.

APP_ID=qianxun
SIZES="16 32 48 64 128 256"

MODE=user
WANT_AUTOSTART=0

for arg in "$@"; do
    case "$arg" in
        --system) MODE=system ;;
        --autostart) WANT_AUTOSTART=1 ;;
        -h|--help)
            echo "Usage: $0 [--system] [--autostart]"
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

# Resolve the directory this script lives in (following no symlinks of its own name).
SCRIPT_PATH=$0
case "$SCRIPT_PATH" in
    */*) ;;
    *) SCRIPT_PATH=$(command -v "$SCRIPT_PATH" 2>/dev/null || echo "$SCRIPT_PATH") ;;
esac
SRC_DIR=$(cd "$(dirname "$SCRIPT_PATH")" && pwd -P) || die "cannot resolve script directory"

# Escape a string for use as the replacement part of sed s|||.
sed_escape() {
    printf '%s' "$1" | sed -e 's/[\\|&]/\\&/g'
}

# render_template <template> <dest> <exec> <icon>
render_template() {
    _e=$(sed_escape "$3")
    _i=$(sed_escape "$4")
    sed -e "s|@EXEC@|$_e|g" -e "s|@ICON@|$_i|g" "$1" > "$2" || die "failed to write $2"
}

# Quote an Exec path per the Desktop Entry spec when it contains spaces or reserved characters:
# inside double quotes escape " ` $ \ (then double every backslash again for the string level) and % -> %%.
exec_path() {
    case "$1" in
        *[!A-Za-z0-9/._+-]*)
            _q=$(printf '%s' "$1" | sed -e 's/[\\"`$]/\\&/g' -e 's/\\/\\\\/g' -e 's/%/%%/g')
            printf '"%s"' "$_q" ;;
        *) printf '%s' "$1" ;;
    esac
}

# Print the desktop directory for the current user (empty if none can be found).
find_desktop_dir() {
    _d=""
    if command -v xdg-user-dir >/dev/null 2>&1; then
        _d=$(xdg-user-dir DESKTOP 2>/dev/null)
        if [ "$_d" = "$HOME" ] || [ ! -d "$_d" ]; then
            _d=""
        fi
    fi
    if [ -z "$_d" ]; then
        # Localized Desktop folder name (UTF-8 octal escapes keep this file ASCII).
        _cn="$HOME/$(printf '\346\241\214\351\235\242')"
        if [ -d "$_cn" ]; then
            _d=$_cn
        else
            _d="$HOME/Desktop"
        fi
    fi
    printf '%s' "$_d"
}

refresh_caches() {
    _apps=$1
    _icons=$2
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$_apps" >/dev/null 2>&1 || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1 && [ -d "$_icons" ]; then
        gtk-update-icon-cache -q -t -f "$_icons" >/dev/null 2>&1 || true
    fi
}

install_user() {
    DEST_DIR=$HOME/.local/share/$APP_ID
    APPS_DIR=$HOME/.local/share/applications
    ICONS_DIR=$HOME/.local/share/icons/hicolor
    BIN_DIR=$HOME/.local/bin

    echo "mode: user"
    echo "source: $SRC_DIR"
    echo "target: $DEST_DIR"

    if [ "$(cd "$SRC_DIR" && pwd -P)" = "$(cd "$DEST_DIR" 2>/dev/null && pwd -P)" ]; then
        echo "copy: skipped (already in place)"
    else
        rm -rf "$DEST_DIR" || die "cannot remove old copy at $DEST_DIR"
        mkdir -p "$DEST_DIR" || die "cannot create $DEST_DIR"
        cp -R "$SRC_DIR"/. "$DEST_DIR"/ || die "copy failed"
        echo "copy: done"
    fi

    [ -f "$DEST_DIR/qianxun.sh" ] || die "launcher qianxun.sh not found in $DEST_DIR"
    chmod +x "$DEST_DIR/qianxun.sh" || die "cannot chmod launcher"
    EXEC_PATH=$DEST_DIR/qianxun.sh

    # Icons
    for s in $SIZES; do
        _src=$DEST_DIR/app/$APP_ID-$s.png
        [ -f "$_src" ] || die "missing icon $_src"
        _dir=$ICONS_DIR/${s}x${s}/apps
        mkdir -p "$_dir" || die "cannot create $_dir"
        cp "$_src" "$_dir/$APP_ID.png" || die "cannot install icon $s"
    done
    [ -f "$DEST_DIR/app/$APP_ID.svg" ] || die "missing app/$APP_ID.svg"
    mkdir -p "$ICONS_DIR/scalable/apps" || die "cannot create scalable icon dir"
    cp "$DEST_DIR/app/$APP_ID.svg" "$ICONS_DIR/scalable/apps/$APP_ID.svg" || die "cannot install svg icon"
    echo "icons: installed"

    # Application menu entry
    [ -f "$DEST_DIR/app/$APP_ID.desktop" ] || die "missing app/$APP_ID.desktop"
    mkdir -p "$APPS_DIR" || die "cannot create $APPS_DIR"
    render_template "$DEST_DIR/app/$APP_ID.desktop" "$APPS_DIR/$APP_ID.desktop" \
        "$(exec_path "$EXEC_PATH")" "$ICONS_DIR/256x256/apps/$APP_ID.png"
    echo "menu entry: $APPS_DIR/$APP_ID.desktop"

    # Command-line symlink
    mkdir -p "$BIN_DIR" || die "cannot create $BIN_DIR"
    ln -sfn "$EXEC_PATH" "$BIN_DIR/$APP_ID" || die "cannot create symlink"
    echo "symlink: $BIN_DIR/$APP_ID"

    # Autostart
    if [ "$WANT_AUTOSTART" = 1 ]; then
        _as=$HOME/.config/autostart
        mkdir -p "$_as" || die "cannot create $_as"
        [ -f "$DEST_DIR/app/$APP_ID-autostart.desktop" ] || die "missing app/$APP_ID-autostart.desktop"
        render_template "$DEST_DIR/app/$APP_ID-autostart.desktop" "$_as/$APP_ID.desktop" \
            "$(exec_path "$EXEC_PATH")" "$ICONS_DIR/256x256/apps/$APP_ID.png"
        echo "autostart: $_as/$APP_ID.desktop"
    fi

    # Desktop shortcut
    _desk=$(find_desktop_dir)
    mkdir -p "$_desk" || die "cannot create desktop directory $_desk"
    _short=$_desk/$APP_ID.desktop
    render_template "$DEST_DIR/app/$APP_ID.desktop" "$_short" \
        "$(exec_path "$EXEC_PATH")" "$ICONS_DIR/256x256/apps/$APP_ID.png"
    chmod +x "$_short" || true
    if command -v gio >/dev/null 2>&1; then
        gio set "$_short" metadata::trusted true >/dev/null 2>&1 || true
    fi
    echo "desktop shortcut: $_short"

    refresh_caches "$APPS_DIR" "$HOME/.local/share/icons/hicolor"
    echo "done: user install complete"
    echo "run: $BIN_DIR/$APP_ID  (or $EXEC_PATH)"
}

install_system() {
    DEST_DIR=/opt/$APP_ID
    APPS_DIR=/usr/share/applications
    ICONS_DIR=/usr/share/icons/hicolor
    BIN_LINK=/usr/local/bin/$APP_ID

    echo "mode: system"
    echo "source: $SRC_DIR"
    echo "target: $DEST_DIR"

    if [ "$(cd "$SRC_DIR" && pwd -P)" = "$(cd "$DEST_DIR" 2>/dev/null && pwd -P)" ]; then
        echo "copy: skipped (already in place)"
    else
        rm -rf "$DEST_DIR" || die "cannot remove old copy at $DEST_DIR"
        mkdir -p "$DEST_DIR" || die "cannot create $DEST_DIR"
        cp -R "$SRC_DIR"/. "$DEST_DIR"/ || die "copy failed"
        echo "copy: done"
    fi

    [ -f "$DEST_DIR/qianxun.sh" ] || die "launcher qianxun.sh not found in $DEST_DIR"
    chmod 755 "$DEST_DIR/qianxun.sh" || die "cannot chmod launcher"
    EXEC_PATH=$DEST_DIR/qianxun.sh

    for s in $SIZES; do
        _src=$DEST_DIR/app/$APP_ID-$s.png
        [ -f "$_src" ] || die "missing icon $_src"
        _dir=$ICONS_DIR/${s}x${s}/apps
        mkdir -p "$_dir" || die "cannot create $_dir"
        cp "$_src" "$_dir/$APP_ID.png" || die "cannot install icon $s"
    done
    [ -f "$DEST_DIR/app/$APP_ID.svg" ] || die "missing app/$APP_ID.svg"
    mkdir -p "$ICONS_DIR/scalable/apps" || die "cannot create scalable icon dir"
    cp "$DEST_DIR/app/$APP_ID.svg" "$ICONS_DIR/scalable/apps/$APP_ID.svg" || die "cannot install svg icon"
    echo "icons: installed"

    [ -f "$DEST_DIR/app/$APP_ID.desktop" ] || die "missing app/$APP_ID.desktop"
    mkdir -p "$APPS_DIR" || die "cannot create $APPS_DIR"
    render_template "$DEST_DIR/app/$APP_ID.desktop" "$APPS_DIR/$APP_ID.desktop" \
        "$(exec_path "$EXEC_PATH")" "$ICONS_DIR/256x256/apps/$APP_ID.png"
    chmod 644 "$APPS_DIR/$APP_ID.desktop" || true
    echo "menu entry: $APPS_DIR/$APP_ID.desktop"

    mkdir -p /usr/local/bin || die "cannot create /usr/local/bin"
    ln -sfn "$EXEC_PATH" "$BIN_LINK" || die "cannot create symlink"
    echo "symlink: $BIN_LINK"

    if [ "$WANT_AUTOSTART" = 1 ]; then
        _as=/etc/xdg/autostart
        mkdir -p "$_as" || die "cannot create $_as"
        [ -f "$DEST_DIR/app/$APP_ID-autostart.desktop" ] || die "missing app/$APP_ID-autostart.desktop"
        render_template "$DEST_DIR/app/$APP_ID-autostart.desktop" "$_as/$APP_ID.desktop" \
            "$(exec_path "$EXEC_PATH")" "$ICONS_DIR/256x256/apps/$APP_ID.png"
        chmod 644 "$_as/$APP_ID.desktop" || true
        echo "autostart: $_as/$APP_ID.desktop"
    fi

    refresh_caches "$APPS_DIR" "$ICONS_DIR"
    echo "done: system install complete"
    echo "run: $BIN_LINK  (or $EXEC_PATH)"
}

case "$MODE" in
    system)
        [ "$(id -u)" = 0 ] || die "--system requires root (use sudo)"
        install_system
        ;;
    *)
        install_user
        ;;
esac
