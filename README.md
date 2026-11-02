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
| 银河麒麟 V10／Ubuntu 20.04 系（x86_64） | 1.1.0 | Python 3.13＋PyQt5（Qt 5.15）自带运行库 | `qianxun_1.1.0_amd64.deb`、`qianxun-1.1.0-kylin-x86_64.tar.gz`／`.zip`（绿色版） |
| 银河麒麟 V10（飞腾 aarch64） | 1.1.0 | Python 3.13＋PySide6（Qt 6.8）自带运行库 | `qianxun_1.1.0_arm64.deb`、`qianxun-1.1.0-kylin-aarch64.tar.gz`／`.zip` |
| Windows 10／11（64 位） | 1.1.0 | Python 3.13＋PyQt5（Qt 5.15）＋C 启动器 | `qianxun-1.1.0-windows-x64.zip`、`QianXun-1.1.0-portable.exe` |
| **Windows 7 SP1～11（64／32 位）** | **1.1.0** | C++17＋纯 Win32 API，单文件零依赖 | `QianXun-x64.exe`、`QianXun-x86.exe`、`qianxun-1.1.0-windows-native.zip` |

Windows 推荐使用原生版（更快、更小、支持 Win7）；Python 版保留作为 Win10／11 的备选。

## 三、安装与使用

**麒麟／Linux**
- deb：`sudo dpkg -i qianxun_1.1.0_arm64.deb`（x86 机器用 amd64 包）。
- 绿色版：先把压缩包复制到本机硬盘（不要在 U 盘里解压），`tar -xzf qianxun-1.1.0-kylin-aarch64.tar.gz`，进入目录执行 `sh check.sh` 自检，再 `sh qianxun.sh` 运行；`./install.sh` 安装到当前用户（加 `--autostart` 开机自启），`sudo ./install.sh --system` 安装到系统（`/opt/qianxun`）；`./uninstall.sh` 卸载（`--purge` 同时删除配置与缓存）。
- 配置 `~/.config/qianxun/`，索引缓存 `~/.cache/qianxun/`。

**Windows**
- 原生版：64 位系统双击 `QianXun-x64.exe`，32 位系统双击 `QianXun-x86.exe`。
- Python 版：解压 zip 后双击 `QianXun\QianXun.exe`，或直接双击 `QianXun-1.1.0-portable.exe`（首次运行把运行环境释放到 `%LOCALAPPDATA%\QianXun\rt-*\`）。
- 数据位于 `%LOCALAPPDATA%\QianXun\`；exe 同目录放一个空文件 `portable.txt` 即改为便携模式（数据存同目录 `data\`）。
- 程序未做数字签名，从网上下载后首次运行如出现“Windows 已保护你的电脑”，点“更多信息 → 仍要运行”。

各发布包内另附中文 `README.txt`（版式与本节一致）。

## 四、从源码构建

见 `CLAUDE.md` 的“构建与测试”一节；一条命令构建全部发布包：`bash build/build_all.sh`（产物在 `_work/dist/`）。
