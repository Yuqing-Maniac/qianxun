# CLAUDE.md —— 千寻 QianXun 维护指南（给接手的 Claude）

## 1. 一句话
Everything 式文件名秒搜。两套实现、三类发布物：
- `app/qianxun.py`：Python＋Qt 单文件主程序（约 4,100 行），**麒麟／Linux 与 Windows 10/11 共用**（`IS_WIN` 分支）。
- `native/`：C++17＋纯 Win32 原生版（Windows 7～11，单 exe 零依赖），行为以 `qianxun.py` 为准，用差分测试保证一致。

## 2. 目录
```
app/qianxun.py            主程序（Index / Inotify / DirWatcherWin / Engine / EngineWin / Query / Searcher / MainWindow）
assets/icons, desktop/    图标（svg、16–256 png、ico）与 .desktop 模板（@EXEC@ @ICON@ 由安装脚本替换）
build/linux/              build_release.sh（deb＋tar.gz＋zip）、build_runtime_linux.sh、裁剪脚本 trim_*、hx_qtboot*.py（.pth 钩子）
build/linux/package/      进发布包根目录的文件：qianxun.sh（启动器）install.sh uninstall.sh check.sh README.txt
build/linux/prebuilt/     手工交叉编译的 aarch64 二进制：libxcb-cursor.so.0、libfcitx5platforminputcontextplugin.so（+许可证）
build/linux/fcitx_aarch64/ 上述 fcitx 插件的原始构建脚本（依赖 /tmp/w 下的 qtbase v6.8.0 与 fcitx5-qt 0285a5d 源码）
build/windows/            build_runtime.sh、build_win.sh（zip＋portable exe）、package_native.sh、launcher/（C 启动器）、env.sh、setup_prefix.sh
build/build_all.sh        一键构建全部发布物；build/fetch_all.sh 下载并重建全部运行库
native/                   src/（15 个 cpp/h）、res/（rc、manifest、ico）、build.sh、pkg/README.txt
tests/                    run_regression.sh（Linux 全套）、qa/、smoke/、win/（Windows 纯逻辑与 Wine 测试）、native_unit/、native_diff/（差分）
docs/                     QA_REPORT、RUNTIME_LINUX、RUNTIME_WIN、BUILD_RUNTIMES、PORT_NOTES_WIN、WIN_SPEC、NATIVE_SPEC、NATIVE_NOTES、NATIVE_DIFF_REPORT、FCITX_AARCH64
promo/                    介绍视频工程（Remotion＋录屏脚本＋配乐合成），脚本保留原始绝对路径，见 promo/README.md
_work/                    （gitignore）运行库、Wine 前缀、发布包等大文件，可用 QX_WORK 改位置
```

## 3. 交付约定（用户的长期要求，必须遵守）
- **离线、免安装、无需管理员权限**；运行库全部内嵌；目标机器常为不联网的银河麒麟 V10（含国防版，kysec 可能拦截未签名程序）。
- **压缩包内文件名一律 ASCII**（用户机器上 UTF-8 与 GBK 文件名都出过乱码）；外层文件名可中文。zip 用 Python zipfile 写，构建脚本会 `.encode('ascii')` 校验。
- 包内**不得有符号链接**（U 盘 FAT/exFAT/NTFS 上解压会失败），`build_release.sh` 发现即报错。
- 交付时附 `SHA256SUMS.txt`。中文说明文档用全角标点。正式 Release 页的资产是免安装包和 `SHA256SUMS.txt`。`qianxun-v1.2.1` 的校验文件不含 deb。本地 `build/linux/build_release.sh` 仍会生成 deb。`.github/workflows/qianxun-release.yml` 的上传命令仍包含 `*.deb`。deb 不是正式资产。
- PR 自动检查以 `.github/workflows/qianxun-ci.yml` 为准。它做 `python -m py_compile app/qianxun.py`、`tests/qa/test_engine.py`、`tests/qa/test_search.py`，以及 `bash native/build.sh` 和 `tests/native_diff/check_imports.sh`。该检查不运行 `build/build_all.sh`。
- 发版打包时，各包内 `qianxun.py` 必须一致（核对 sha256）。

## 4. 关键技术决定与踩过的坑
**运行库**
- 沙箱里 GitHub、python.org、NuGet、conda 均不可达，CPython 取自 npm 包 `@rowstile/cli-{linux-x64,linux-arm64,win32-x64}@0.1.0-alpha.7`（python-build-standalone 3.13.15），所以是 Python 3.13。能跑 Win7 的 Python 3.8 拿不到，这就是另写原生版的原因。
- aarch64 在 PyPI 上**没有 PyQt5／PyQt5-Qt5 轮子**，只能用 PySide6 6.8.0.2（Qt 6.8）。代码里有绑定兼容层（`QT_BINDING`、`qexec`/`qflag`/`qbytes`），环境变量 `QIANXUN_QT=PyQt5|PySide6` 可强制。
- Qt ≥ 6.5 需要 `libxcb-cursor0`，麒麟没有，所以手工交叉编译后内置。Qt6 没有 fcitx4 插件，所以手工编译了 fcitx5-qt 的 Qt6 插件（同时支持 fcitx4／fcitx5 的 DBus 协议）。它用 Qt 私有 API，**只能配 Qt 6.8.x**；换 PySide6 版本就必须重编。
- x86_64 的 fcitx Qt5 插件取自 Ubuntu focal 的 `fcitx-frontend-qt5`；`syspyqt/` 是 focal 的 python3-pyqt5，只配系统 python3.8，用来让 Kylin x86 走系统 Qt。
- 中文路径加 C locale 时 Qt 找不到插件：Linux 用 `hx_qtboot*.py` 写的 `.pth` 钩子修，Windows 用 `sitecustomize.py` 修（非 ANSI 路径）。
- Windows 运行库删掉了 `_ssl`/`_hashlib`，代码里不要无条件 import hashlib/ssl。pythonw 没有 stdout，print 前要判空。

**启动器 `build/linux/package/qianxun.sh`**
- 选择顺序：系统 python3＋PyQt5 → x86_64 系统 python3.8＋内置 syspyqt → 内置运行库；`QIANXUN_MODE=system|syspyqt|bundled` 可强制。
- 用 `readlink -f` 解析 `/usr/bin/qianxun` 软链（曾因此找不到运行库）。
- 从 noexec 或 FAT 介质启动时，自动复制到 `~/.local/share/qianxun-portable` 再运行。
- aarch64 上若没有 fcitx 插件，把 `QT_IM_MODULE` 从 fcitx 回退为 ibus。

**麒麟桌面集成**
- 窗口身份必须统一成 `qianxun`：`RESOURCE_NAME`、`prctl(PR_SET_NAME)`、QApplication argv0，加上 `.desktop` 的 `StartupWMClass=qianxun`。否则 WM_CLASS 是 `qianxun.py`、进程名是 `python3`，固定到任务栏后没有图标。
- `.desktop` 的 Icon 用 PNG 绝对路径，部分 UKUI 按主题名找用户目录图标会失败，显示问号。
- deb 的 Exec 用 `sh /opt/qianxun/qianxun.sh`，减少 kysec 拦截。
- 桌面目录优先 `xdg-user-dir DESKTOP`，结果不存在时回退到 `~/桌面`。

**引擎与搜索**
- 索引是平行数组加目录表，持锁读写，读侧不加锁就会出 IndexError（QA 严重项）。
- inotify 名额是上限减 4096；溢出或名额用尽时做目录 mtime 比对，并每 3 分钟轮询。
- GUI 刷新间隔：结果少于 20 万条时 0.25 秒；持续变化时节流到 10 秒。
- 增量收窄：新查询以旧查询为前缀时，只在旧结果里过滤。结果多于 12 万条时，按名称排序用预排序数组归并。
- `a | b`（两侧带空格）等同 `a|b`；正则编译失败或过于复杂时报“语法错误”，不能崩溃。
- 详见 `docs/QA_REPORT.md`（20 项修复，每项都有复现与回归测试）。

**Windows（Python 版，见 docs/PORT_NOTES_WIN.md）**
- 每盘一个 ReadDirectoryChangesW 递归监视；返回 0 字节表示缓冲溢出，要对该盘做全量比对。
- 不进入重解析点（Application Data 之类的循环联接）。
- U 盘和网络盘上拒绝“移到回收站”，因为 Windows 在这些盘上会永久删除。
- 安全弹出时要立即释放句柄。

**原生版（见 docs/NATIVE_SPEC.md、NATIVE_NOTES.md）**
- 只允许 Win7 能用的静态导入，Win8+ 的 API 一律 GetProcAddress。`tests/native_diff/check_imports.sh` 负责核查。
- 已知差异（已在测试中归类为预期）：不支持正则后行断言与 `(?P=name)`；大小写折叠只做 1:1；`?` 匹配一个 UTF-16 单元。
- Wine 的 ReadDirectoryChangesW 不报告“刚改名目录里新建的文件”，这是 Wine 的问题。真机上应该正常，但原生版可在 RENAMED_NEW 时重扫该目录，作为加固。

**测试环境**
- 装了 `wine32:i386` 以后，`wine` 默认走 32 位加载器，会把 win64 前缀弄坏。当时在 `/usr/local/bin/wine` 加了包装脚本：win64 前缀走 wine64。新机器上要么照做，要么直接用 `wine64` 跑 64 位前缀。
- 无头 CLI 跑完后要先 `wineserver -k`，再启动 GUI；Wine 下要 `LC_ALL=C.UTF-8`，否则中文名乱码。

**未在真机验证**
- 飞腾真机：用户确认 deb 能运行；任务栏图标修复以后还没有回报。
- Windows 两个版本只在 Wine 里测过。真机还要确认：U 盘插拔与安全弹出、拖拽、开机自启、全局快捷键、高 DPI、SmartScreen。

## 5. 构建与测试

**依赖（Ubuntu 24.04 x86_64）**
```
apt-get install -y python3-pip nodejs npm zip unzip dpkg-dev librsvg2-bin imagemagick xvfb xdotool x11-utils fonts-noto-cjk \
                   mingw-w64 g++-mingw-w64-x86-64-win32 g++-mingw-w64-i686-win32 libz-mingw-w64-dev wine64
pip install --break-system-packages PyQt5==5.15.11 "PySide6_Essentials==6.8.0.2" "shiboken6==6.8.0.2"   # 仅测试用
# 可选：32 位 Wine 测 x86 原生版：dpkg --add-architecture i386 && apt-get update && apt-get install -y wine32:i386（随后按上面的坑配置包装脚本）
```
需要能访问 pypi.org、registry.npmjs.org、archive.ubuntu.com。运行库的来源、版本、sha256 与校验结果见 `docs/BUILD_RUNTIMES.md`。

**构建**
```
bash build/fetch_all.sh                  # 下载并重建运行库 → _work/runtime/{x86_64,aarch64}、_work/syspyqt、_work/win/runtime
sh   build/linux/build_release.sh        # 麒麟 deb / tar.gz / zip → _work/dist
bash build/windows/build_win.sh          # Win10/11 zip + portable exe（需 mingw、rsvg-convert、convert）
bash build/windows/package_native.sh     # 原生 exe x64/x86 + zip（native/build.sh）
bash build/build_all.sh                  # 以上全部，并生成 _work/dist/SHA256SUMS.txt
```
2026-10-22 已在空的 QX_WORK 中实测 `build/build_all.sh`：约 4 分钟，从零产出全部 11 个发布物；运行库与原件逐文件一致（见 docs/BUILD_RUNTIMES.md），原生 exe 与已交付版本仅 PE 时间戳不同。

**增量升级**
- 从 1.1.0 升到 1.2.0，以及更换 Python、Qt、启动器或原生 exe，都只能安装完整包。发布页上的完整包是绿色版 tar.gz 和 zip、Windows 文件夹 zip、portable exe、原生版 zip。
- 增量包是 `qianxun-<版本>-incremental.zip`。1.2.0 及以上打开 **帮助 → 增量升级…**，选中 zip 并确认。不需要命令行。
- `build/build_all.sh` 在 `sha256sum` 之前，用 `VERSION` 行作为 from_version，把同版本空包打到 `_work/dist/`。单独打包：`python3 app/qianxun.py --pack-incremental 1.2.0 . _work/dist/qianxun-1.2.0-incremental.zip`。
- 1.2.0 这包与已安装版本相同，不改文件。之后的包把 from_version 设为 1.2.0，或设为一台机器上已安装的更高版本。to_version 取树里的 `VERSION` 行。
- 新文件要等进程退出并重新启动才运行。只关窗口会留在托盘，程序仍是旧的。`/opt/qianxun` 和 deb 安装此菜单不可写。单文件版的释放目录会被拒绝。原生 exe 没有该菜单。zip 不替换 `python3.13` 或 Qt 库。目录外的菜单图标不会更新。包没有签名。写入中崩溃时，下次启动恢复原来的 `qianxun.py`。写进 `qianxun-portable` 的补丁，可能在下次 U 盘启动且脚本内容不同时被盖掉。

唯二不能从零重建的是 `build/linux/prebuilt/aarch64/` 下两个手工交叉编译的二进制（需要 GitHub 上的 qtbase v6.8.0 与 fcitx5-qt 源码，构建脚本在 build/linux/fcitx_aarch64/，说明见 docs/FCITX_AARCH64.md）。

**测试**
```
sh tests/run_regression.sh               # Linux 全套：engine/search/race/gui/churn/perf/instance/smoke，PyQt5 与 PySide6 各一遍；win 纯逻辑单测
python3 tests/smoke/t1.py                # 引擎＋实时同步冒烟；t4.py PyQt5|PySide6 为 GUI 冒烟；t9.py 测实时同步延迟
bash build/windows/setup_prefix.sh       # 建 Win10 Wine 前缀（Python 版 GUI 测试用），然后见 tests/win/wine/*.sh
bash tests/native_diff/setup_prefix.sh 64   # 建 Win7 模式前缀（32 位用参数 32）
python3 tests/native_diff/gen_corpus.py && python3 tests/native_diff/oracle.py   # 生成语料与 Python 期望结果
bash tests/native_diff/run_diff.sh       # 原生版 578 条差分；live_test.py 测实时同步；perf_test.py 测百万条目；check_imports.sh 查导入表
```
已知：PySide6 下 `t4.py` 在 `rc 0` 之后的解释器退出阶段会段错误（退出码 139），这是测试框架的问题，真实程序退出码为 0，索引会正常保存。

## 6. 工作方式
- 用户偏好：端到端自主执行、少打断；回复简洁，适合手机阅读；中文。
- 改了 `qianxun.py` 的搜索语义，要同步改 `native/src/query.cpp` 并跑差分测试；反过来也一样。
- 新增平台差异时，Linux 行为必须不变：先跑一遍 `tests/run_regression.sh` 作为基线，改完再跑一遍对比。

## 7. 版本号
发版前以下各处必须一致（当前 1.2.1），并在 `CHANGELOG.md` 新增条目：
- `app/qianxun.py` 的 `VERSION`：程序“关于”与 `--version` 显示；**`build/linux/build_release.sh`（变量 `V`）与 `build/windows/build_win.sh`（变量 `VER`）用 sed 从这一行读取**，决定 deb 的 `Version:` 与 deb／tar.gz／zip／portable exe 的文件名，取不到即报错退出。
- `native/src/app.h` 的 `QX_VERSION_W`：原生版“关于”与 `--version`。
- `native/res/qianxun.rc`（FILEVERSION／PRODUCTVERSION 及两处字符串）与 `native/res/manifest.xml`：原生 exe 的文件属性。
- `build/windows/launcher/launcher.rc` 与 `launcher/manifest.xml`：Windows Python 版启动器的文件属性。
- `build/windows/package_native.sh` 的 `VER`：原生版 zip 文件名（手写，未从源码读取）。
- 文档与测试中的文件名：`README.md` 平台表与安装说明、`native/pkg/README.txt`、`build/windows/README_WIN.txt`、`build/linux/package/README.txt`、`tests/qa/test_install.sh`、`tests/win/wine/l6.sh`／`l7.sh`。
- `docs/` 下 QA_REPORT、RUNTIME_WIN、WIN_SPEC、PORT_NOTES_WIN 中的 1.0.0 是当时的测试记录，不随版本改。
- 核查：`git grep -nE "1\.[0-9]+\.[0-9]+" -- qianxun ':!*.json' ':!*/licenses/*'`。

## 8. 评审清单（审查者逐条核对）
1. 改了 `app/qianxun.py` 的搜索语义（语法、匹配、排序、过滤），是否同步改了 `native/src/query.cpp`（或反向），并跑了 `tests/native_diff/run_diff.sh` 差分（578 条全一致，或新差异已归类为预期）。
2. 原生版没有新增 Win8+ 才有的静态导入：`tests/native_diff/check_imports.sh native/out/QianXun-x64.exe`（x86 同）输出无 `OUTSIDE-SPEC-LIST`，`suspicious` 为 `none`；新 API 一律 GetProcAddress。
3. 发布包内文件名全部 ASCII、无符号链接：Windows 两种 zip 由 `build_win.sh`／`package_native.sh` 的 `.encode('ascii')` 校验文件名；麒麟绿色版由 `build_release.sh` 的 `find -type l` 校验无符号链接（deb 中 `/usr/bin/qianxun` 链接除外）。麒麟包目前没有 ASCII 文件名校验，需人工确认。
4. 版本号按第 7 节各处同步，`CHANGELOG.md` 有对应条目。
5. 改动 Linux 行为的，改前改后各跑一遍 `sh tests/run_regression.sh` 并对比结果；只改 Windows 时 Linux 结果必须不变。
6. 不引入任何联网依赖（运行时不得访问网络、不得依赖在线服务或在线安装），新增运行库须内嵌并写进 `docs/BUILD_RUNTIMES.md`。
