# 千寻 QianXun —— 文件名秒搜

千寻是一款 Everything 式的文件名即时搜索工具：全盘文件名索引常驻内存，输入即出结果；新建、改名、删除约 1 秒内同步。全部离线运行，自带运行库，无需安装，无需管理员权限。

## 一、功能

- **秒搜**：百万级文件，常规查询数十毫秒（原生 Windows 版 2～25 毫秒）。
- **实时同步**：Linux 用 inotify（监控名额不足时自动降级为 3 分钟轮询），Windows 用 ReadDirectoryChangesW（每盘一个递归监视）。
- **索引缓存**：退出与每 30 分钟落盘，再次启动 1 秒内可用。
- **搜索语法（与 Everything 一致）**：空格＝与、`|`＝或、`!`＝非、`*`／`?` 通配、`"…"` 短语、含 `/`（Windows 另含 `\`）的词按路径匹配、`ext:`、`file:`、`folder:`、`path:`、`regex:`、`size:`、`dm:`；开关：区分大小写 Ctrl+I、全字匹配 Ctrl+B、匹配路径 Ctrl+U、正则 Ctrl+R。
- **结果操作**：打开、打开所在文件夹、复制文件／路径、重命名（F2）、移到回收站（Delete）、属性、拖拽、导出 CSV；按类型筛选；点击表头排序；匹配片段加粗。
- **系统集成**：托盘常驻、单实例（`--toggle`／`--hidden`）、全局快捷键（Windows 内置 Ctrl+Alt+F；麒麟在系统快捷键中绑定 `qianxun --toggle`）、开机自启、U 盘插拔自动增删索引。

## 二、支持平台与发布形态

| 平台 | 版本 | 技术路线 | 发布物 |
|---|---|---|---|
| 银河麒麟 V10（飞腾 aarch64） | 1.2.2 | Python 3.13＋PySide6（Qt 6.8）自带运行库 | `qianxun-1.2.2-kylin-aarch64.tar.gz` |
| Windows 10／11（64 位） | 1.2.2 | Python 3.13＋PyQt5（Qt 5.15）＋C 启动器 | `qianxun-1.2.2-windows-x64.zip` |

1.2.2 发布页只有上面两份便携包。麒麟 x86_64 与 Windows 7 的打包脚本还在 `build/linux/build_release.sh` 和 `build/windows/package_native.sh`，这次没有放上发布页。Windows 7 不能使用包内的 Python 3.13。

这次发布页上的 Windows 包是 Python 版，给 Windows 10／11 64 位用。原生版更快，也能在 Windows 7 上运行，打包脚本还在，这次没有放上发布页。

正式发布页是 [千寻 1.2.2](https://github.com/Yuqing-Maniac/qianxun/releases/tag/qianxun-v1.2.2)。该页提供上表两份便携包和 `SHA256SUMS.txt`。页上没有 deb，也没有自解压 exe。下载后在校验文件所在目录执行 `sha256sum -c SHA256SUMS.txt`。

## 三、安装与使用

**麒麟／Linux**
- 绿色版：先把压缩包复制到本机硬盘（不要在 U 盘里解压），`tar -xzf qianxun-1.2.2-kylin-aarch64.tar.gz`。解压后顶层是 `qianxun.sh` 和 `qianxun` 文件夹，双击或执行 `sh qianxun.sh`。第一次运行会在桌面建立快捷方式。文件夹里的 `sh check.sh` 可以自检。`qianxun/install.sh` 仍可安装到当前用户（加 `--autostart` 开机自启），`sudo ./install.sh --system` 安装到系统（`/opt/qianxun`）。`./uninstall.sh` 卸载（`--purge` 同时删除配置与缓存）。
- 配置 `~/.config/qianxun/`，索引缓存 `~/.cache/qianxun/`。

**Windows**
- 解压后顶层是 `QianXun.exe` 和 `QianXun` 文件夹。双击旁边的 `QianXun.exe`。不要只把 exe 拷走。第一次运行会在桌面建立快捷方式，图标来自这个 exe。
- Windows 10／11 用 `qianxun-1.2.2-windows-x64.zip`（Python 运行库在文件夹里）。Python 3.13 不能在 Windows 7 上运行。Windows 7 的原生打包脚本还在，这次发布页没有附带。
- 数据位于 `%LOCALAPPDATA%\QianXun\`；exe 同目录放一个空文件 `portable.txt` 即改为便携模式（数据存同目录 `data\`）。
- 程序未做数字签名，从网上下载后首次运行如出现“Windows 已保护你的电脑”，点“更多信息 → 仍要运行”。

各发布包内另附中文 `README.txt`（版式与本节一致）。

## 四、增量升级

从 1.1.0 升到 1.2.0，以及换到 1.2.2 的入口布局，都只能换完整包。这次发布页上的完整包是麒麟 aarch64 的 tar.gz 和 Windows 10／11 的 zip。更换 Python、Qt、启动器或原生 exe，也只能换完整包。

增量包的文件名是 `qianxun-<版本>-incremental.zip`。已经在用 1.2.0 或更新版本时，打开 **帮助 → 增量升级…**，选中这个 zip，再点确定。不需要命令行。

1.2.0 的增量包与已经装好的 1.2.0 相同，确认后不改文件。以后的增量包把起始版本写成 1.2.0，或写成这台机器上已经装好的更高版本。目标版本取打包时 `app/qianxun.py` 里的 `VERSION` 行。

维护者在仓库根目录执行下面这条命令。

```bash
python3 app/qianxun.py --pack-incremental 1.2.0 . _work/dist/qianxun-1.2.0-incremental.zip
```

增量升级有这些限制。

- 新的 `qianxun.py` 要等当前进程退出、新进程启动之后才运行。只关窗口会留在托盘，程序仍是旧的。
- `/opt/qianxun` 和 deb 安装目录这个菜单写不进去。
- 单文件版释放出来的目录会被拒绝。原生 exe 没有这个菜单。
- 这个 zip 不能更换 `python3.13` 或 Qt 库。复制到安装目录以外的菜单图标不会更新。
- 增量包没有签名。写入中途崩溃时，下次启动会把 `qianxun.py` 恢复成升级前的文件。
- 写进 `qianxun-portable` 的补丁，可能在下次从 U 盘启动且脚本内容不同时被盖掉。

## 五、从源码构建

见 `CLAUDE.md` 的“构建与测试”一节。本地全量打包用 `bash build/build_all.sh`。产物在 `_work/dist/`。PR 上的 `qianxun-ci` 只做语法检查、引擎测试、搜索测试，以及原生版编译和导入表核查。该检查不运行 `build/build_all.sh`。
