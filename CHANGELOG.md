# 变更记录

版本号说明：1.0.0 期间多次修订均以 1.0.0 重新发包（下表按日期列出各次重发）。自 1.1.0 起，麒麟版、Windows Python 版与原生 Windows 版统一使用同一版本号。

## [1.2.1] — 2026-11-04　仅改版本号

- 本版只把版本号改为 1.2.1，已安装的 1.2.0 可以用增量 zip 升级。
- 搜索行为不变。

## [1.2.0] — 2026-11-03　增量升级

- 帮助菜单增加「增量升级…」。1.2.0 及以上可在界面中选择增量 zip 并确认，程序退出后重新打开，只替换 `app/qianxun.py`。
- 从 1.1.0 升到 1.2.0，以及更换 Python、Qt、启动器或原生 exe，仍须安装完整包。`/opt/qianxun`、deb 安装和单文件版释放目录不能用这个菜单写入。增量包没有签名。
- 维护者打包命令是 `python3 app/qianxun.py --pack-incremental 1.2.0 . _work/dist/qianxun-1.2.0-incremental.zip`。1.2.0 这份包与已安装版本相同，不改文件。`build/build_all.sh` 会在校验和之前打出这份空包。

## [1.1.0] — 2026-10-19　Windows 原生版

- 新增 C++17＋纯 Win32 原生版（`native/`），mingw-w64 静态编译，单个 exe 零运行库依赖，支持 Windows 7 SP1～11，x64 与 x86 各一。
- 功能、搜索语法、界面与 Python 版一致；新增 `--cli`／`--cli-watch` 测试接口。
- 差分测试：578 条查询与 Python 版逐条一致（Win7 模式 Wine，x64／x86 均 578／578）；百万条目查询 2～25 毫秒，内存约 120 MB。
- 版本号对齐（2026-10-23 入库时）：Python 版 `app/qianxun.py` 的 `VERSION` 由 1.0.0 改为 1.1.0，麒麟 deb／tar.gz／zip 与 Windows Python 版 zip／portable exe 的文件名随之改为 1.1.0（构建脚本改为从 `VERSION` 读取），Windows 启动器 VERSIONINFO 同步为 1.1.0.0；Python 版功能与 1.0.0 最后一次重发相同。
- 内置帮助的路径匹配示例改为 `path:项目`（两版程序同步）。

## [1.0.0] — 2026-10-19 重发　任务栏图标修复（麒麟）

- 修复固定到任务栏后无图标、菜单／桌面图标显示为问号：统一窗口身份（`RESOURCE_NAME=qianxun`、`prctl(PR_SET_NAME)`、QApplication argv0），`.desktop` 增加 `StartupWMClass=qianxun`，图标改用绝对路径。
- 修复桌面目录配置缺失时桌面快捷方式装到 `~/Desktop` 而非 `~/桌面`。
- 打包脚本不再清空整个输出目录（曾误删 Windows 发布物）。

## [1.0.0] — 2026-10-18 重发　Windows 10／11 版（Python）

- 同一份 `qianxun.py` 增加 Windows 分支：ReadDirectoryChangesW 实时监控、盘符插拔、`DirEntry.stat` 免费取大小时间、不进入重解析点、`%LOCALAPPDATA%`／`portable.txt`、系统集成（startfile、explorer /select、属性、回收站、CF_HDROP）、全局快捷键、开机自启、桌面快捷方式、AppUserModelID。
- C 启动器（文件夹版与自解压单文件版），运行库 Python 3.13＋PyQt5 5.15.11（Qt 5.15.2），`sitecustomize.py` 修复非 ANSI 路径下 Qt 插件加载失败。

## [1.0.0] — 2026-10-18 重发　绿色版解压修复（麒麟）

- 运行库与压缩包内去除全部符号链接（在 U 盘 FAT32／exFAT／NTFS 上解压会失败）；构建时发现符号链接即报错。
- 新增 zip 版与 `SHA256SUMS.txt`；从不可执行的介质启动时自动复制到 `~/.local/share/qianxun-portable` 运行。
- 新增 `check.sh` 环境自检；deb 的 `.desktop` 用 `sh` 启动，减少国防版对脚本执行的拦截。

## [1.0.0] — 2026-10-18 重发　QA 修复 20 项

- 严重：界面读索引未加锁导致 IndexError 退出；重建索引后旧结果行指向错误文件（误删／误改风险）；特定正则导致崩溃。
- 高：目录对调后子树错位；挂载／卸载与运行中插入的 U 盘不被感知；监控名额用尽后轮询永久停止。
- 中：持续写日志引起每 0.25 秒全量重搜（降为 10 秒）；非 UTF-8 文件名的改名、回收站、复制问题；回收站目录不存在时文件被挪到工作目录；注销（SIGTERM）不保存索引。
- 性能：100 万条目下路径匹配与全字匹配约 120 毫秒，按路径排序 1.2 秒。详见 `docs/QA_REPORT.md`。
- 实时刷新间隔：结果少于 20 万条时 0.25 秒。

## [1.0.0] — 2026-10-17　首发（麒麟）

- Python＋Qt 单文件主程序：内存索引、inotify 实时监控（名额不足时轮询）、Everything 语法、增量收窄、虚拟列表、托盘、单实例。
- 离线运行库：x86_64 用 PyQt5（Qt 5.15），飞腾 aarch64 无 PyQt5 轮子改用 PySide6 6.8（含 Qt5／Qt6 兼容层、手工交叉编译的 libxcb-cursor 与 fcitx5 输入法插件）。
- 发布 deb、tar.gz 绿色版与安装／卸载脚本；介绍视频（`promo/`）。
