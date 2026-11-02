# 千寻 QianXun — Windows 版规格（共享给子代理）

目标：Windows 10／11 x64，**普通用户、无管理员权限、免安装**，双击即用；与 Linux 版同一份源码 `/home/claude/build/app/qianxun.py`（必须保持 Linux 行为与全部现有测试不变）。

## 运行时（runtime 代理负责）
- Python：npm 包 `@rowstile/cli-win32-x64@0.1.0-alpha.7`（python-build-standalone 3.13.15 Windows 版，含 pythonw.exe、_ctypes、vcruntime140*.dll）。下载：`cd /tmp/pp && npm pack @rowstile/cli-win32-x64@0.1.0-alpha.7`（已下载到 /tmp/pp/）。
- Qt：`pip download --no-deps --only-binary=:all: --platform win_amd64 --python-version 3.13 --implementation cp PyQt5==5.15.11 PyQt5-Qt5==5.15.2 PyQt5-sip`（PyQt5 为 abi3 cp38，sip 需 cp313 轮子）。解压进 runtime 的 Lib/site-packages。
- 裁剪：只留 QtCore/QtGui/QtWidgets/QtNetwork/QtSvg（及其 DLL）、插件 platforms/qwindows.dll、styles/qwindowsvistastyle.dll、imageformats（ico/svg/jpeg/gif）、iconengines/qsvgicon.dll、translations 仅 qtbase_zh_CN.qm；删 opengl32sw.dll、d3dcompiler、Qt5Quick/Qml/WebEngine/Multimedia/3D/Bluetooth 等、Python 的 test/idlelib/tkinter/ensurepip/lib2to3/__pycache__/_test*.pyd。保留 MSVC 运行库 DLL（msvcp140*.dll、vcruntime140*.dll、concrt140.dll）。
- 目录布局（最终发布物，全部 ASCII 文件名）：
  ```
  QianXun\
    QianXun.exe          ← 启动器（GUI 子系统、带图标与版本信息）
    app\qianxun.py
    runtime\pythonw.exe, python.exe, python313.dll, DLLs\, Lib\ (含 site-packages\PyQt5)
    README.txt           ← 中文说明，UTF-8 带 BOM，CRLF
  ```
- 启动器 QianXun.exe：mingw-w64 编译（`x86_64-w64-mingw32-gcc -municode -mwindows -O2 -s`），wWinMain；定位自身目录（GetModuleFileNameW，支持中文与空格路径）；`CreateProcessW` 启动 `runtime\pythonw.exe -X utf8 "app\qianxun.py" <原参数>`，不等待、立即退出；找不到运行库时 MessageBoxW 中文报错。图标：由 /home/claude/build/app/qianxun.svg 生成多尺寸 .ico（16/24/32/48/64/128/256），windres 编进资源；VERSIONINFO（FileDescription=千寻 文件秒搜，ProductName=千寻，CompanyName 留空，FileVersion=1.0.0.0），清单 manifest：asInvoker（绝不请求管理员）、dpiAware PerMonitorV2、supportedOS Win10。
- 单文件版 `QianXun-portable.exe`（可选加分）：同一启动器 + 末尾附加压缩负载（libz-mingw-w64-dev 静态 zlib；自定义简单归档格式：魔数+目录表+每文件 zlib 流，Python 端用 zlib 生成），首次运行解压到 `%LOCALAPPDATA%\QianXun\rt-<负载哈希前 12 位>\`（已存在且完整则跳过；写入临时目录后原子改名），再按上面方式启动。解压期间若超过 0.5 秒，显示一个简单的“千寻正在首次准备运行环境…”小窗口（纯 Win32）。
- 测试环境：apt 安装 wine64（以及 wine32 不需要）、Xvfb 已有。用 `WINEPREFIX=/home/claude/build/win/wineprefix`、`WINEDEBUG=-all`、`xvfb-run -a` 运行 `wine QianXun\runtime\python.exe -c "from PyQt5 import QtWidgets…"` 冒烟；再用启动器启动 app 截图。

## 代码移植（port 代理负责）——`qianxun.py` 增加 Windows 分支，`IS_WIN = os.name == 'nt'`
1. **路径**：分隔符抽象（`SEP = '\\' if IS_WIN else '/'`），`join_path`、`norm_path`、`dir_prefixes`（目录前缀以 SEP 结尾）、根目录形如 `C:\\`；Windows 下 `dir_ids` 键大小写不敏感（`dkey(p) = p.lower()` on Windows，原样 on Linux），所有 dir_ids 读写走 dkey。查询里含 `\\` 或 `/` 的词都按路径匹配，Windows 下把 `/` 统一换成 `\\`；Linux 行为不变。
2. **根目录与排除**：Windows 默认根 = 所有本地固定盘（GetLogicalDrives + GetDriveTypeW==DRIVE_FIXED），`index_removable` 时含可移动盘，`index_network` 时含映射网络盘；默认排除 `X:\\$Recycle.Bin`、`X:\\System Volume Information`、`C:\\Windows\\WinSxS`（各盘）；`read_mounts`/`compute_excludes` 的 /proc 逻辑仅 Linux。盘符插拔：引擎每 3 秒比较 GetLogicalDrives 位图，新盘符增量加根（扫描+监视），移除的盘符增量删根（复用/参照现有 Linux 挂载变化处理 `_check_mounts`）。
3. **扫描**：Windows 下 `os.scandir` 的 `DirEntry.stat()` 免费给出大小与修改时间 → 扫描时直接填 size/mtime（`_list_dir` 返回带统计的条目），size:/dm: 无需补全；**不进入重解析点**（`st_file_attributes & 0x400`，联接点/符号链接只作为条目收录，不递归），避免 “Application Data” 之类的循环联接。无权限目录静默跳过。
4. **实时监控**：新增 `DirWatcherWin`（ctypes）替代 Inotify：每个根一个句柄 `CreateFileW(root, FILE_LIST_DIRECTORY, share RW|DELETE, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OVERLAPPED)`，`ReadDirectoryChangesW(bWatchSubtree=TRUE, filter=FILE_NAME|DIR_NAME|SIZE|LAST_WRITE, 512KB 缓冲, OVERLAPPED+事件)`，引擎循环用 `WaitForMultipleObjects` 带超时取结果、`GetOverlappedResult`，解析 FILE_NOTIFY_INFORMATION（相对路径），映射到父目录 dir id（找不到就向上找最近已索引祖先）→ dirty；`FILE_ACTION_MODIFIED` 作用于文件 → touched（刷新大小/时间），作用于目录则忽略；返回 0 字节＝缓冲溢出 → 对该根做 catch-up；句柄失效（盘拔出）→ 撤根。状态栏：每个根一个监视即“实时监控已全覆盖”。Linux 下 inotify 逻辑完全不变。“提升实时监控上限”菜单在 Windows 下隐藏。
5. **配置／缓存目录**：Windows 用 `%LOCALAPPDATA%\\QianXun\\`（config.json、index.db、日志）；若程序目录下存在 `portable.txt`，则改存程序目录下 `data\\`（真正便携）。
6. **单实例**：`SERVER_NAME` 不能用 `os.getuid()`（Windows 没有）→ 用 `getpass.getuser()` 的安全化形式；`--toggle`/`--hidden` 保持。
7. **系统集成（Windows）**：打开 `os.startfile`；打开所在文件夹 `explorer /select,"路径"`；在终端打开：优先 `wt.exe -d 目录`，否则 `powershell.exe`（cwd=目录，CREATE_NEW_CONSOLE），再否则 cmd；属性：`ShellExecuteExW` 动词 `properties`（SEE_MASK_INVOKEIDLIST）弹系统属性框，失败回退现有自绘对话框（pwd/grp 只在 Linux 导入）；回收站：Qt 5.15 `QFile.moveToTrash` 优先，失败回退 `SHFileOperationW(FO_DELETE, FOF_ALLOWUNDO|FOF_NOCONFIRMATION|FOF_SILENT)`；复制文件到剪贴板：Qt 的 URL 列表在 Windows 上即 CF_HDROP，确认资源管理器可粘贴。
8. **图标**：Windows 下 `QIcon.fromTheme` 无效 → 用 `QFileIconProvider().icon(QFileInfo(真实路径))`：普通扩展名按扩展名缓存（取首次遇到的真实文件），`.exe/.lnk/.ico/.url` 按路径缓存（LRU 2000）；文件夹统一图标。
9. **全局快捷键**：Windows 下用 `RegisterHotKey`（默认 Ctrl+Alt+F，可在选项中改或关闭）+ `QAbstractNativeEventFilter` 处理 WM_HOTKEY → `win.toggle()`；注册失败（被占用）在状态栏提示一次。
10. **开机自启**：选项中“登录 Windows 时自动启动（后台托盘）”→ 写 `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\QianXun = "<启动器路径>" --hidden`（winreg，无需管理员）；“创建桌面快捷方式”菜单 → `QFile.link(启动器路径, 桌面\\千寻.lnk)`。启动器路径由环境变量 `QIANXUN_LAUNCHER`（启动器设置）提供，缺省用 sys.executable+脚本。
11. **任务栏**：启动早期调用 `SetCurrentProcessExplicitAppUserModelID("QianXun.FileSearch")`，使任务栏图标为千寻而非 Python。
12. **字体**：Windows 下界面字体优先 “Microsoft YaHei UI”，回退系统默认。
13. 帮助文本、README 中涉及 Linux 的说法（麒麟快捷键设置、inotify 等）按平台分支显示。

## 验收
- Linux：`/home/claude/build/tests/qa/` 全部测试、`python3 /tmp/qx/t1.py`、PyQt5 与 PySide6 GUI 冒烟全部通过，行为不变。
- Windows（Wine + Xvfb）：启动器拉起程序；索引一个 Wine 盘（如 `Z:\\` 映射的测试目录或 `C:\\` 下生成的 ~5 万文件树）；搜索语法；在被监视目录新建/改名/删除文件后 ≤1 秒内结果更新；重启后从缓存秒开；单实例 `--toggle`；截图人工检查中文字形、图标、布局。
- 发布物：`/home/claude/build/dist/qianxun-1.0.0-windows-x64.zip`（条目全 ASCII 名，顶层目录 QianXun\）＋可选 `QianXun-1.0.0-portable.exe`，SHA256SUMS 追加。
