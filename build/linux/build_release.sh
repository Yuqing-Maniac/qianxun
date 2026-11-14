#!/bin/sh
set -e
ROOT=$(cd "$(dirname "$0")/../.." && pwd); WORK=${QX_WORK:-$ROOT/_work}
PKG=$ROOT/build/linux/package; ICONS=$ROOT/assets/icons; DESK=$ROOT/assets/desktop
V=$(sed -n "s/^VERSION = '\(.*\)'$/\1/p" "$ROOT/app/qianxun.py"); [ -n "$V" ] || { echo "VERSION not found in app/qianxun.py" >&2; exit 1; }
OUT=$WORK/dist; mkdir -p "$OUT"
for A in x86_64 aarch64; do [ -d "$WORK/runtime/$A" ] || { echo "missing $WORK/runtime/$A - run build/linux/build_runtime_linux.sh first" >&2; exit 1; }; done
 rm -rf "$OUT"/stage-x86_64 "$OUT"/stage-aarch64 "$OUT"/deb-x86_64 "$OUT"/deb-aarch64 "$OUT"/qianxun_*.deb "$OUT"/qianxun-$V-kylin-*
for ARCH in x86_64 aarch64; do
  case $ARCH in x86_64) DA=amd64;; aarch64) DA=arm64;; esac
  S=$OUT/stage-$ARCH/qianxun; mkdir -p "$S/app" "$S/runtime"
  cp "$PKG/qianxun.sh" "$PKG/install.sh" "$PKG/uninstall.sh" "$PKG/check.sh" "$PKG/README.txt" "$S/"
  cp "$ROOT/app/qianxun.py" "$ICONS/qianxun.svg" "$ICONS"/qianxun-*.png "$DESK"/qianxun*.desktop "$S/app/"
  cp -a "$WORK/runtime/$ARCH" "$S/runtime/"
  if [ -d "$WORK/syspyqt/$ARCH" ]; then mkdir -p "$S/syspyqt"; cp -a "$WORK/syspyqt/$ARCH" "$S/syspyqt/"; fi
  find "$S" -name __pycache__ -prune -exec rm -rf {} +
  chmod 755 "$S/qianxun.sh" "$S/install.sh" "$S/uninstall.sh" "$S/check.sh"
  cp "$PKG/qianxun-entry.sh" "$OUT/stage-$ARCH/qianxun.sh"
  chmod 755 "$OUT/stage-$ARCH/qianxun.sh"
  case $ARCH in
    x86_64) QTREL="qianxun/runtime/x86_64/lib/python3.13/site-packages/PyQt5/Qt5/plugins/platforms/libqxcb.so"; EXTRA="" ;;
    aarch64) QTREL="qianxun/runtime/aarch64/lib/python3.13/site-packages/PySide6/Qt/plugins/platforms/libqxcb.so"
             EXTRA="--need qianxun/runtime/aarch64/lib/python3.13/site-packages/PySide6/Qt/lib/libxcb-cursor.so.0" ;;
  esac
  python3 "$ROOT/build/portable_layout.py" tree "$OUT/stage-$ARCH" --folder qianxun --entry qianxun.sh \
    --need qianxun/app/qianxun.py --need qianxun/app/qianxun-256.png --need "qianxun/runtime/$ARCH/bin/python3.13" --need "$QTREL" $EXTRA
  [ -z "$(find "$S" -type l)" ] || { echo "symlinks found in $S" >&2; exit 1; }
  tar -C "$OUT/stage-$ARCH" --owner=0 --group=0 --format=gnu -czf "$OUT/qianxun-$V-kylin-$ARCH.tar.gz" qianxun qianxun.sh
  (cd "$OUT/stage-$ARCH" && zip -r -q -X -9 "$OUT/qianxun-$V-kylin-$ARCH.zip" qianxun qianxun.sh)
  python3 "$ROOT/build/portable_layout.py" archive "$OUT/qianxun-$V-kylin-$ARCH.tar.gz" --folder qianxun --entry qianxun.sh \
    --need qianxun/app/qianxun.py --need qianxun/app/qianxun-256.png --need "qianxun/runtime/$ARCH/bin/python3.13" --need "$QTREL" $EXTRA
  python3 "$ROOT/build/portable_layout.py" archive "$OUT/qianxun-$V-kylin-$ARCH.zip" --folder qianxun --entry qianxun.sh \
    --need qianxun/app/qianxun.py --need qianxun/app/qianxun-256.png --need "qianxun/runtime/$ARCH/bin/python3.13" --need "$QTREL" $EXTRA
  # deb
  D=$OUT/deb-$ARCH; mkdir -p "$D/DEBIAN" "$D/opt" "$D/usr/bin" "$D/usr/share/applications"
  cp -a "$S" "$D/opt/qianxun"; rm -f "$D/opt/qianxun/install.sh" "$D/opt/qianxun/uninstall.sh"
  ln -s /opt/qianxun/qianxun.sh "$D/usr/bin/qianxun"
  sed -e 's#@EXEC@#sh /opt/qianxun/qianxun.sh#' -e 's#@ICON@#/usr/share/icons/hicolor/256x256/apps/qianxun.png#' "$DESK/qianxun.desktop" > "$D/usr/share/applications/qianxun.desktop"
  for s in 16 32 48 64 128 256; do mkdir -p "$D/usr/share/icons/hicolor/${s}x${s}/apps"; cp "$ICONS/qianxun-$s.png" "$D/usr/share/icons/hicolor/${s}x${s}/apps/qianxun.png"; done
  mkdir -p "$D/usr/share/icons/hicolor/scalable/apps"; cp "$ICONS/qianxun.svg" "$D/usr/share/icons/hicolor/scalable/apps/"
  SZ=$(du -sk "$D" | cut -f1)
  cat > "$D/DEBIAN/control" <<CTL
Package: qianxun
Version: $V
Section: utils
Priority: optional
Architecture: $DA
Installed-Size: $SZ
Maintainer: QianXun <qianxun@localhost>
Description: QianXun - Everything-style instant file name search for Kylin
 Indexes all file names in memory with inotify live updates and
 Everything search syntax. Fully offline: bundles its own Python and Qt runtime.
CTL
  cat > "$D/DEBIAN/postinst" <<'PI'
#!/bin/sh
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
exit 0
PI
  cp "$D/DEBIAN/postinst" "$D/DEBIAN/postrm"; chmod 755 "$D/DEBIAN/postinst" "$D/DEBIAN/postrm"
  find "$D/opt" -type d -exec chmod 755 {} +
  dpkg-deb --root-owner-group -Zxz -b "$D" "$OUT/qianxun_${V}_$DA.deb" >/dev/null
done
(cd "$OUT" && sha256sum $(ls *.deb *.tar.gz *.zip *.exe 2>/dev/null) > SHA256SUMS.txt)
ls -la "$OUT"/*.deb "$OUT"/*.tar.gz "$OUT"/*.zip
