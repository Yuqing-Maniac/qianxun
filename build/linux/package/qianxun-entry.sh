#!/bin/sh
# Top-level entry for the Kylin / Linux portable archive.
# The archive root is this script plus the sibling qianxun/ folder.
# No root, no installer. The first launch writes a desktop shortcut.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP=$HERE/qianxun
ENTRY=$HERE/qianxun.sh
if [ ! -f "$APP/app/qianxun.py" ] || [ ! -f "$APP/qianxun.sh" ]; then
  printf '%s\n' '请把 qianxun.sh 和旁边的 qianxun 文件夹放在一起，不要只拷走脚本。' >&2
  exit 1
fi

desktop_field() {
  case "$1" in
    *[!A-Za-z0-9/._+-]*)
      printf '"%s"' "$(printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
      ;;
    *) printf '%s' "$1" ;;
  esac
}

write_shortcuts() {
  ICON=$APP/app/qianxun-256.png
  [ -f "$ICON" ] || return 0
  DESKTOP=$(xdg-user-dir DESKTOP 2>/dev/null || printf '%s\n' "$HOME/Desktop")
  if [ ! -d "$DESKTOP" ] && [ -d "$HOME/桌面" ]; then DESKTOP=$HOME/桌面; fi
  [ -n "$DESKTOP" ] || return 0
  CONF=${XDG_CONFIG_HOME:-$HOME/.config}/qianxun
  MARK=$CONF/entry-path
  mkdir -p "$DESKTOP" "$HOME/.local/share/applications" "$CONF" 2>/dev/null || return 0
  cur=$(cat "$MARK" 2>/dev/null || true)
  if [ "$cur" = "$ENTRY" ]; then
    return 0
  fi
  for png in "$APP"/app/qianxun-*.png; do
    [ -f "$png" ] || continue
    base=$(basename "$png")
    size=${base#qianxun-}
    size=${size%.png}
    case "$size" in
      *[!0-9]*) continue ;;
    esac
    mkdir -p "$HOME/.local/share/icons/hicolor/${size}x${size}/apps"
    cp -f "$png" "$HOME/.local/share/icons/hicolor/${size}x${size}/apps/qianxun.png"
  done
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
  fi
  exec_field=$(desktop_field "$ENTRY")
  icon_field=$(desktop_field "$ICON")
  path_field=$(desktop_field "$APP")
  for dest in "$HOME/.local/share/applications/qianxun.desktop" "$DESKTOP/千寻.desktop"; do
    cat > "$dest" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=千寻
GenericName=文件秒搜
Comment=千寻 文件秒搜
Exec=$exec_field
Path=$path_field
Icon=$icon_field
StartupWMClass=qianxun
Terminal=false
Categories=Utility;
EOF
    chmod 755 "$dest" 2>/dev/null || true
    if command -v gio >/dev/null 2>&1; then
      gio set "$dest" metadata::trusted true >/dev/null 2>&1 || true
    fi
  done
  printf '%s\n' "$ENTRY" > "$MARK"
}

write_shortcuts || true
exec sh "$APP/qianxun.sh" "$@"
