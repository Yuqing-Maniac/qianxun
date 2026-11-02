#!/bin/sh
# QianXun environment self-check. Run:  sh check.sh   (no root needed)
# Writes the report to check-report.txt next to this script.
SELF=$(readlink -f "$0" 2>/dev/null || echo "$0")
HERE=$(cd "$(dirname "$SELF")" && pwd)
OUT="$HERE/check-report.txt"
: > "$OUT" 2>/dev/null || OUT=/tmp/qianxun-check-report.txt
say() { echo "$1"; echo "$1" >> "$OUT"; }
ok=0; warn=0; bad=0
pass() { say "  [通过] $1"; ok=$((ok+1)); }
note() { say "  [注意] $1"; warn=$((warn+1)); }
fail() { say "  [不通过] $1"; bad=$((bad+1)); }

say "千寻运行环境自检  $(date '+%Y-%m-%d %H:%M')"
say "=============================================="

say "1. 系统与架构"
ARCH=$(uname -m)
case "$ARCH" in
    aarch64|arm64) A=aarch64; pass "CPU 架构 $ARCH（使用 arm64／aarch64 包）" ;;
    x86_64|amd64) A=x86_64; pass "CPU 架构 $ARCH（使用 amd64／x86_64 包）" ;;
    *) A=other; fail "CPU 架构 $ARCH 不在支持范围（x86_64／aarch64）" ;;
esac
say "  内核 $(uname -r)"
[ -r /etc/os-release ] && say "  系统 $(. /etc/os-release; echo "$PRETTY_NAME")"
say "  桌面会话 ${XDG_SESSION_TYPE:-未知}，DISPLAY=${DISPLAY:-无}"
[ "${XDG_SESSION_TYPE:-x11}" = wayland ] && note "当前为 Wayland 会话，程序按 X11 方式运行，一般可用"

say "2. 系统库版本"
GV=$(ldd --version 2>/dev/null | head -n 1 | grep -o '[0-9]\+\.[0-9]\+$')
if [ -n "$GV" ]; then
    MAJ=${GV%.*}; MIN=${GV#*.}
    if [ "$MAJ" -gt 2 ] || [ "$MIN" -ge 30 ]; then pass "glibc $GV（自带运行库要求 ≥ 2.30）"; else fail "glibc $GV，低于 2.30，自带运行库无法运行"; fi
else note "无法读取 glibc 版本"; fi
STDCXX=$(ldconfig -p 2>/dev/null | grep 'libstdc++.so.6[[:space:]]' | head -n 1 | sed 's/.*=> //')
if [ -n "$STDCXX" ] && grep -q GLIBCXX_3.4.28 "$STDCXX" 2>/dev/null; then pass "libstdc++ 含 GLIBCXX_3.4.28"
elif [ "$A" = x86_64 ]; then pass "x86_64 运行库只需 GLIBCXX_3.4.18，满足"
else fail "libstdc++ 缺 GLIBCXX_3.4.28（$STDCXX），arm64 自带运行库无法运行"; fi
MISSING=""
for L in libxcb.so.1 libxcb-icccm.so.4 libxcb-image.so.0 libxcb-keysyms.so.1 libxcb-render-util.so.0 \
         libxcb-xkb.so.1 libxkbcommon.so.0 libxkbcommon-x11.so.0 libfontconfig.so.1 libfreetype.so.6 \
         libdbus-1.so.3 libSM.so.6 libICE.so.6 libX11-xcb.so.1 libglib-2.0.so.0 libz.so.1; do
    ldconfig -p 2>/dev/null | grep -q "[[:space:]]$L[[:space:]]" || MISSING="$MISSING $L"
done
[ "$A" = aarch64 ] && for L in libzstd.so.1 libbrotlidec.so.1; do ldconfig -p 2>/dev/null | grep -q "[[:space:]]$L[[:space:]]" || MISSING="$MISSING $L"; done
if [ -z "$MISSING" ]; then pass "图形界面依赖的系统库齐全"; else fail "缺少系统库：$MISSING"; fi

say "3. 运行方式"
FST=$(df -T "$HERE" 2>/dev/null | awk 'NR==2 {print $2}')
case "$FST" in
    vfat|msdos|exfat|ntfs|ntfs3|fuseblk) note "当前目录位于 $FST 文件系统（多为 U 盘），不支持可执行权限：程序首次启动会自动复制到主目录运行；也可手动把整个文件夹复制到主目录" ;;
    *) [ -n "$FST" ] && say "  当前目录文件系统：$FST" ;;
esac
SYSPY=$(command -v python3 2>/dev/null)
if [ -n "$SYSPY" ]; then
    say "  系统 Python：$($SYSPY --version 2>&1)"
    if "$SYSPY" -c "import PyQt5.QtWidgets, PyQt5.QtNetwork" >/dev/null 2>&1; then
        pass "系统已装 PyQt5，将优先用系统运行库（输入法与主题最佳，安全管控最少）"; SYSMODE=1
    else note "系统未装 PyQt5，将使用包内自带运行库"; SYSMODE=0; fi
else note "系统无 python3，将使用包内自带运行库"; SYSMODE=0; fi
PY="$HERE/runtime/$A/bin/python3.13"
if [ -x "$PY" ]; then
    case "$A" in aarch64) MOD="PySide6.QtWidgets" ;; *) MOD="PyQt5.QtWidgets" ;; esac
    ERR=$(QT_QPA_PLATFORM=offscreen "$PY" -c "import $MOD, sys; from ${MOD%.*} import QtWidgets as W; a=W.QApplication(sys.argv); print('ok')" 2>&1)
    RC=$?
    if [ $RC -eq 0 ]; then pass "自带运行库可正常加载（$MOD）"
    else
        case "$ERR" in
            *"ermission denied"*|*"not permitted"*|*"Killed"*|*kysec*) fail "自带运行库被安全机制拦截（返回 $RC）：请在“安全中心 → 应用控制与保护”中放行，或让管理员添加信任" ;;
            *) fail "自带运行库加载失败（返回 $RC）：$(echo "$ERR" | tail -n 2 | tr '\n' ' ')" ;;
        esac
    fi
else note "未找到自带运行库 $PY（若系统 PyQt5 可用则不影响）"; fi

say "4. 安全管控"
if command -v getstatus >/dev/null 2>&1; then
    say "  $(getstatus 2>/dev/null | tr '\n' ' ')"
    getstatus 2>/dev/null | grep -qi "enable\|strict\|开启" && note "麒麟安全机制（kysec）已开启：未签名程序可能被拦截，以第 3 项实测结果为准"
else say "  未发现 getstatus 命令（无法读取 kysec 状态，以第 3 项实测结果为准）"; fi

say "5. 实时监控与输入法"
LIM=$(cat /proc/sys/fs/inotify/max_user_watches 2>/dev/null)
DIRS=$(find /home -xdev -type d 2>/dev/null | head -n 300000 | wc -l)
say "  inotify 上限 ${LIM:-未知}，/home 下目录约 $DIRS 个"
if [ -n "$LIM" ] && [ "$LIM" -ge 65536 ]; then pass "实时监控名额充足"
else note "监控名额较少：主目录优先实时监控，其余每 3 分钟轮询；可在程序“工具”菜单一键提升"; fi
IM="${QT_IM_MODULE:-未设置}"
P=""
for p in fcitx5 fcitx ibus-daemon; do pgrep -x "$p" >/dev/null 2>&1 && P="$P $p"; done
say "  输入法框架：${P:-未检测到}，QT_IM_MODULE=$IM"
if [ -n "$P" ]; then pass "输入法框架运行中（包内含 fcitx4／fcitx5／ibus 插件）"; else note "未检测到输入法进程，中文输入以实际为准"; fi

say "6. 资源"
MEM=$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null)
say "  可用内存约 ${MEM:-?} MB；CPU $(nproc 2>/dev/null) 核"
[ -n "$MEM" ] && [ "$MEM" -ge 1024 ] && pass "内存充足（百万文件索引约占 250 MB）"

say "=============================================="
if [ $bad -eq 0 ]; then say "结论：可以运行（通过 $ok 项，注意 $warn 项）。"
else say "结论：有 $bad 项不通过，请把 check-report.txt 发给维护人员。"; fi
say "报告已保存：$OUT"
