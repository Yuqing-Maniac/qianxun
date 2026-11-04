#!/bin/sh
# install/uninstall in a HOME with spaces+Chinese, from a source dir with spaces+Chinese; verify nothing left.
set -u
TB=${QX_WORK:-$(cd "$(dirname "$0")/../.." && pwd)/_work}/dist/qianxun-1.2.0-kylin-x86_64.tar.gz
W=$(mktemp -d)
H="$W/home 用户"; S="$W/下载 目录"
mkdir -p "$H/桌面" "$S"
tar -C "$S" -xzf "$TB"
before=$(cd "$W" && find "home 用户" | sort)
HOME=$H; export HOME
unset XDG_CONFIG_HOME XDG_CACHE_HOME XDG_DATA_HOME
sh "$S/qianxun/install.sh" --autostart >/dev/null || { echo "FAIL install"; exit 1; }
for f in "$H/.local/share/qianxun/qianxun.sh" "$H/.local/bin/qianxun" "$H/.local/share/applications/qianxun.desktop" \
         "$H/.config/autostart/qianxun.desktop" "$H/桌面/qianxun.desktop"; do
  [ -e "$f" ] || echo "FAIL missing $f"
done
grep '^Exec=' "$H/.local/share/applications/qianxun.desktop"
grep '^Exec=' "$H/.config/autostart/qianxun.desktop"
command -v desktop-file-validate >/dev/null && desktop-file-validate "$H/.local/share/applications/qianxun.desktop"
# launcher via symlink, --version path (no Qt needed)
QIANXUN_MODE=bundled "$H/.local/bin/qianxun" --version || echo "FAIL launcher via symlink"
# re-install over existing (idempotent) and from the installed dir itself
sh "$S/qianxun/install.sh" >/dev/null || echo "FAIL reinstall"
sh "$H/.local/share/qianxun/install.sh" >/dev/null || echo "FAIL install from dest"
[ -x "$H/.local/share/qianxun/qianxun.sh" ] || echo "FAIL dest wiped by self-install"
# simulate runtime data
mkdir -p "$H/.config/qianxun" "$H/.cache/qianxun"; touch "$H/.config/qianxun/config.json" "$H/.cache/qianxun/index.db"
sh "$H/.local/share/qianxun/uninstall.sh" --purge >/dev/null || echo "FAIL uninstall"
after=$(cd "$W" && find "home 用户" -type f -o -type l | sort)
echo "--- leftover files/links after uninstall --purge:"; echo "$after" | grep -v '^$' || echo "(none)"
echo "--- leftover empty dirs:"; (cd "$W" && find "home 用户" -type d -empty | sort)
rm -rf "$W"
