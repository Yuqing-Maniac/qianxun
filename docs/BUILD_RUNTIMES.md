# Reproducible build of the bundled runtimes

Written 2026-10-22 to reproduce the hand-assembled runtimes of 2026-10-17/18; verified by diff against the originals.

```sh
build/fetch_all.sh                      # Linux (x86_64, aarch64, syspyqt) + Windows runtime, into ${QX_WORK:-<repo>/_work}
build/linux/build_runtime_linux.sh      # Linux only; optional args: x86_64 aarch64 syspyqt
build/windows/build_runtime.sh          # Windows only
```
Prerequisites (Ubuntu 24.04 x86_64): `sudo apt-get install -y curl ca-certificates tar gzip unzip binutils dpkg python3 coreutils findutils`;
Windows precompiled `.pyc` additionally need `wine64` (without wine the Windows runtime is built without `.pyc`, with a warning).
Network: registry.npmjs.org, files.pythonhosted.org, archive.ubuntu.com (http). GitHub is not needed. Every download is
sha256-pinned in the scripts, cached in `$WORK/dl`, and re-verified on each run (mismatch aborts). Scripts are idempotent
(target directories are removed and rebuilt). Total download about 268 MB (280 MB incl. debs), about 2 min on the sandbox link, plus about 8 s for the Linux build and
about 1 min for the Windows build (mostly wine prefix creation + compileall).

## Inputs
| File | Source | sha256 |
|---|---|---|
| cli-linux-x64-0.1.0-alpha.7.tgz (26.3 MB) | registry.npmjs.org/@rowstile/cli-linux-x64/-/ (pbs CPython 3.13.15) | c9c61263a7bdd2ee71d05f6b2fa98087c96b8dccfbc2f17529afca07666017de |
| cli-linux-arm64-0.1.0-alpha.7.tgz (20.7 MB) | registry.npmjs.org/@rowstile/cli-linux-arm64/-/ | 8fd0b497905395a8d3f26dc6d26fd113480aa7dcd49d67973ea5af80070c5191 |
| cli-win32-x64-0.1.0-alpha.7.tgz (11.6 MB) | registry.npmjs.org/@rowstile/cli-win32-x64/-/ | 971f68ca2fc4f75730b452ddebc125a8dcd40f8ab20bce78529c4791da42b094 |
| PyQt5-5.15.11-cp38-abi3-manylinux_2_17_x86_64.whl | PyPI | cd672a6738d1ae33ef7d9efa8e6cb0a1525ecf53ec86da80a9e1b6ec38c8d0f1 |
| pyqt5_qt5-5.15.18-py3-none-manylinux2014_x86_64.whl | PyPI | bf2457e6371969736b4f660a0c153258fa03dbc6a181348218e6f05421682af7 |
| pyqt5_sip-12.20.0-cp313-cp313-manylinux_2_5_x86_64.manylinux1_x86_64.whl | PyPI | ed838dcd21d8d01598b48c4c5c3a77b671f50ba8bbde1223fe25a1727d88bbec |
| fcitx-frontend-qt5_1.2.4-1build2_amd64.deb | archive.ubuntu.com focal universe | 1ccd8383fc2dc369cdba8f20f13c1f33717488eb52015814ca37104f80d0e1d1 |
| PySide6_Essentials-6.8.0.2-cp39-abi3-manylinux_2_31_aarch64.whl (92.3 MB) | PyPI | cf490145d18812a6cff48b0b0afb0bfaf7066744bfbd09eb071c3323f1d6d00d |
| shiboken6-6.8.0.2-cp39-abi3-manylinux_2_31_aarch64.whl | PyPI | 1aaa8b7f9138818322ef029b2c487d1c6e00dc3f53084e62e1d11bdea47e47c2 |
| python3-pyqt5_5.14.1+dfsg-3build1_amd64.deb | focal universe | 4efdb25d9e10879973350881531142da2540f76da09baa70d2d0f61e3d1177fc |
| python3-pyqt5.qtsvg_5.14.1+dfsg-3build1_amd64.deb | focal universe | b01265ffe348aec930fc5d3b6769fa2cee5a2d673003376db135701ee1b40788 |
| python3-sip_4.19.21+dfsg-1build1_amd64.deb | focal universe | 9314b3b008eea8e89ffbd73616b4482ee9b799a04b2881c54e7e0a51fb08ab9e |
| PyQt5-5.15.11-cp38-abi3-win_amd64.whl | PyPI | bdde598a3bb95022131a5c9ea62e0a96bd6fb28932cc1619fd7ba211531b7517 |
| PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl | PyPI | 750b78e4dba6bdf1607febedc08738e318ea09e9b10aea9ff0d73073f11f6962 |
| pyqt5_sip-12.20.0-cp313-cp313-win_amd64.whl | PyPI | 194ec42291089077c3290ad02c74a4b4922eb0f6608dd0bb133fbca60b985acd |

(Ubuntu `.deb` pool URLs: `http://archive.ubuntu.com/ubuntu/pool/universe/{f/fcitx-qt5,p/pyqt5,s/sip4}/<file>`; PyPI URLs are the exact
`files.pythonhosted.org/packages/...` paths inside the scripts.) Two further focal debs in the old cache (libfcitx-qt5-1, Packages indexes) were not needed.

## Steps
**runtime/x86_64**: unpack npm package; keep `python/bin/python3.13` + `python/lib/python3.13` only; `trim_python.sh`
(stdlib baggage, `*.a`, `__pycache__`); unzip the three wheels into `lib/python3.13/site-packages`; `trim_qt5.py` (modules QtCore/Gui/Widgets/
Network/DBus/Svg, plugin whitelist, Qt libs by NEEDED closure, only `qtbase_zh_CN` translation); remove `PyQt5/uic/widget-plugins` and empty
dirs (`pyqt5_sip.libs`); copy `libfcitxplatforminputcontextplugin.so` (mode 755) from the focal deb into `platforminputcontexts`;
install `hx_qtboot.py` + `hx_qtboot.pth` (`import hx_qtboot`); no `__pycache__`.
**runtime/aarch64**: same base from the arm64 package; unzip PySide6_Essentials + shiboken6; `trim_pyside6.py`; delete `shiboken6/Shiboken.pyi`;
copy prebuilt `libxcb-cursor.so.0` -> `PySide6/Qt/lib/` and `libfcitx5platforminputcontextplugin.so` -> `platforminputcontexts/`;
write `licenses/xcb-util-cursor.COPYING` (MIT text embedded in the script); `hx_qtboot6.py` as `hx_qtboot.py` + `.pth`.
**syspyqt/x86_64**: `dpkg-deb -x` of the three focal debs; keep `PyQt5/__init__.py`, `Qt{Core,Gui,Widgets,Network,DBus,Svg}.cpython-38-x86_64-linux-gnu.so`,
`sip.cpython-38-x86_64-linux-gnu.so`.
**win/runtime**: original `build_runtime.sh` logic unchanged (trim stdlib/DLLs/Qt, `sitecustomize.py`, `wine python.exe -m compileall --invalidation-mode unchecked-hash`);
only paths (`$WORK/dl`, `$WORK/win/tmp`, `$WORK/win/wineprefix`) and downloads (curl + sha256 instead of `npm pack`/`pip download`) changed.

## Verification (2026-10-22, fresh `QX_WORK` with empty download cache, real downloads, all sha256 matched)
Compared with `/home/claude/build/{runtime/x86_64,runtime/aarch64,syspyqt/x86_64,win/runtime}`: file list, type and mode (`find -printf '%p %m %y'`) and sha256 of every file.
| Tree | Files | Result |
|---|---|---|
| runtime/x86_64 | 591 | file list, modes and sha256 identical (all ELF, .so, .pth, .py); neither tree has `__pycache__` |
| runtime/aarch64 | 572 | identical, except the original contains 64 stray `__pycache__/*.pyc` created by the qemu test runs (not shipped; `build_release.sh` strips them) |
| syspyqt/x86_64 | 8 | identical |
| win/runtime | 1085 | identical, incl. all 497 unchecked-hash `.pyc` (wine 9.0 compileall is deterministic) and `sitecustomize.py` |
Smoke tests on the rebuilt trees: `QT_QPA_PLATFORM=offscreen runtime/x86_64/bin/python3.13 tests/smoke_runtime.py` -> Qt 5.15.14, PyQt 5.15.11, offscreen,
QLocalServer/Socket ok, DBus+Svg ok, exit 0. Windows: `wine python.exe -I -c "import ctypes, sqlite3, PyQt5.Qt{Core,Gui,Widgets,Network,Svg}"` -> Python 3.13.15, Qt 5.15.2. aarch64 and syspyqt cannot be executed on this host (as before).

## Known non-reproducible parts
- `build/linux/prebuilt/aarch64/libxcb-cursor.so.0` (sha256 401a28b3...3773) and `libfcitx5platforminputcontextplugin.so` (sha256 c39dca92...6e2e) are
  hand-compiled aarch64 binaries copied verbatim from the repo. Their build scripts (`build/linux/fcitx_aarch64/{build,comp}.sh`, notes in `docs/FCITX_AARCH64.md`)
  use `/tmp/w` paths and need the qtbase `v6.8.0` tag and fcitx5-qt commit `0285a5d` (both from GitHub, blocked in the sandbox) plus the aarch64 cross
  toolchain (g++-10) and the xcb-util-cursor 0.1.4 source from Ubuntu. They are therefore not rebuilt by `fetch_all.sh`; a rebuild would not be byte-identical anyway (toolchain/timestamps).
- Files taken from the repo (`hx_qtboot*.py`, `sitecustomize.py`, trim scripts) are the same sources the originals used.
