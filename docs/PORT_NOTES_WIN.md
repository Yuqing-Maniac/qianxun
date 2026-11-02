# 千寻 QianXun —— Windows 移植说明（port 代理，2026-10-18）

同一份源码 `app/qianxun.py`（2747 → 4157 行）同时运行于 Linux（麒麟／Python 3.6+／PyQt5 或 PySide6）与 Windows 10/11 x64（Python 3.13 + PyQt5 5.15.11／Qt 5.15.2）。平台开关为 `IS_WIN = os.name == 'nt'`、`SEP`。**Linux 行为不变**：QA 全套、t1、t4 的输出与移植前逐行一致（只有计时数字不同）。

## 一、改了什么（对应 WIN_SPEC 第 1–13 项）

| # | 内容 | 实现要点 |
|---|---|---|
| 1 | 路径 | `join_path` 改为按 `SEP` 拼接（Linux 结果与原来逐字相同）；`win_norm_path`（ntpath，'/'→'\\'、`c:`→`C:\`、盘符大写）、`split_path_sep`、`join_path_sep`、`long_path`（≥240 字符加 `\\?\`）；`dkey()`：Windows 小写、Linux 原样，`dir_ids` 的全部读写（新建、删除、加载、`refresh_path`、扫描去重、排除判断）都经 `dkey`。`dir_prefixes` 以 `SEP` 结尾。查询：Windows 下含 `\` 或 `/` 的词都是路径词，`/` 统一换成 `\`；`is_abs_term` 识别 `C:`／`\\`。Linux 仍只认 `/`。 |
| 2 | 根与排除 | `win_select_roots(cfg, 盘符表)`：`roots` 为空＝全部固定盘＋内存盘，`index_removable`／`index_network` 加入可移动盘／网络盘（标记为“动态根”）。`win_excludes`：用户排除＋各盘 `$Recycle.Bin`、`System Volume Information`＋`%SystemRoot%\WinSxS`，全部小写。`effective_roots`／`compute_excludes` 内部按平台分支，`/proc` 逻辑只在 Linux。盘符插拔：`EngineWin._check_mounts` 每 2 s 比较 `GetLogicalDrives` 位图，`_sync_roots` 增量加根（扫描＋监视）／撤根（`Index.remove_root`）；`WM_DEVICECHANGE`（到达／移除完成）另外立即触发 `drive_check`。 |
| 3 | 扫描 | `Index._list_dir_stats`：一次 `os.scandir` 用 `DirEntry.stat(follow_symlinks=False)` 直接取大小与时间（Windows 上不产生额外系统调用），子目录 mtime 也取自父目录列表，不再逐目录 `os.stat`；扫描后紧随的全量 stat 补全在 Windows 上省掉。名称代理类重解析点（联接点、目录符号链接、挂载点：`FILE_ATTRIBUTE_REPARSE_POINT` 且 reparse tag 第 29 位）只收录为条目、不递归；OneDrive 云文件占位符（非名称代理）照常进入。无权限目录静默跳过。`refresh_dir` 在 Windows 下顺带刷新已有条目的大小/时间。周期性补全改为“按目录重列”（每步 64 个目录）。 |
| 4 | 实时监控 | `DirWatcherWin`（ctypes）：每根一个 `CreateFileW(FILE_LIST_DIRECTORY, 共享读写删, BACKUP_SEMANTICS\|OVERLAPPED)`，`ReadDirectoryChangesW(子树, FILE_NAME\|DIR_NAME\|SIZE\|LAST_WRITE, 512 KB；网络盘 64 KB)`，`WaitForMultipleObjects` 带超时、`GetOverlappedResult` 非阻塞取结果；`parse_notify()` 为纯函数。`EngineWin._handle_events`：相对路径 → 父目录 dir id（不在索引中则向上找最近的已索引祖先，途经排除目录则丢弃）→ dirty；改名事件记入 `moved`（目录对调强制重建）；`MODIFIED` 作用于文件 → touched，作用于目录忽略；0 字节或 `ERROR_NOTIFY_ENUM_DIR` → 对该根补扫＋按目录补全；句柄失效 → 根已不存在则撤根，否则 2 s 后重挂并补扫空档。状态栏沿用原逻辑（每根一个监视即“实时监控已全覆盖”）。可移动盘：句柄登记 `RegisterDeviceNotificationW(DBT_DEVTYP_HANDLE)`，用户“安全弹出”时界面线程收到 `DBT_DEVICEQUERYREMOVE` 立即关闭句柄（否则会提示“设备正在使用”），10 s 内不重挂。“提升实时监控上限”菜单在 Windows 下换成“创建桌面快捷方式”。 |
| 5 | 数据目录 | `%LOCALAPPDATA%\QianXun\`（config.json、index.db、qianxun.log）；启动器目录（`QIANXUN_LAUNCHER` 所在目录或 `app\` 的上级）有 `portable.txt` 时改用其下 `data\`。单文件版的程序目录是 `rt-*`，便携模式只对文件夹版有意义。 |
| 6 | 单实例 | `server_name()`：Linux 仍为 `qianxun-<uid>`；Windows 为 `qianxun-<安全化用户名>-<crc32(域\用户)>`（运行库裁掉了 `_hashlib`，不用 hashlib）。第二实例连接前调用 `AllowSetForegroundWindow(ASFW_ANY)`，便于已运行实例把窗口提到前台。 |
| 7 | 系统集成 | 打开：`os.startfile`（无关联时调“打开方式”）；打开所在文件夹：`explorer.exe /select,"路径"`；终端：`wt -d` → `powershell -NoExit`（新控制台）→ `cmd`；属性：`ShellExecuteExW(properties, SEE_MASK_INVOKEIDLIST)`，失败回退自绘对话框（显示只读／隐藏／系统等属性，`pwd`／`grp` 只在 Linux 导入）；回收站：`QFile.moveToTrash` → `SHFileOperationW(FO_DELETE, ALLOWUNDO…)`；**非固定盘（U 盘、网络盘）拒绝“移到回收站”**，因为 Shell 在这类盘上会静默永久删除；复制文件：Qt URL 列表（Windows 上即 CF_HDROP），不再附加 gnome/mate 格式；重命名检查 Windows 非法字符与结尾空格／句点。 |
| 8 | 图标 | Windows 下 `QFileIconProvider().icon(QFileInfo(真实路径))`：普通扩展名按首个真实文件缓存，`.exe/.lnk/.ico/.url/.scr/.cpl/.msc` 按路径 LRU 2000；文件夹统一图标。 |
| 9 | 全局快捷键 | `RegisterHotKey(NULL, …, MOD_NOREPEAT)`，默认 Ctrl+Alt+F；`parse_hotkey()` 解析 Qt PortableText（纯函数）；`WinNativeFilter`（`QAbstractNativeEventFilter`）处理 `WM_HOTKEY` → `win.toggle()`；注册失败在状态栏提示；选项里可改键或关闭（`QKeySequenceEdit`）。 |
| 10 | 自启／快捷方式 | 选项“登录 Windows 时自动启动（后台托盘）”写 `HKCU\…\Run\QianXun = "<启动器>" --hidden`（winreg，无需管理员）；每次启动若自启项指向旧路径则自动更新。菜单“创建桌面快捷方式” → `QFile.link(启动器, 桌面\千寻.lnk)`（桌面路径取 `QStandardPaths`，兼容 OneDrive 重定向）。 |
| 11 | 任务栏 | 创建 QApplication 前 `SetCurrentProcessExplicitAppUserModelID("QianXun.FileSearch")`。 |
| 12 | 字体／DPI | 界面字体优先 Microsoft YaHei UI → Microsoft YaHei → 系统默认；`HighDpiScaleFactorRoundingPolicy.PassThrough`（125%／150% 不取整）。 |
| 13 | 文案 | 帮助（路径语法示例、全局快捷键说明）、关于、选项对话框按平台分支；新增 `win/README_WIN.txt`（build_win.sh 自动转 UTF-8 BOM＋CRLF 放入发布物）。 |

其它：pythonw 无 stdout/stderr → `--version`、缺 Qt 的报错都先判空；Windows 下安装 `sys.excepthook` 把未捕获异常写日志（否则 PyQt5 会在无提示的情况下 abort）；`commitDataRequest`（注销／关机）时保存窗口状态并同步落盘索引（Windows 不发 SIGTERM）；`disp()` 兼容 NTFS 文件名中的孤立代理项。

### 对 Linux 代码的触碰（均为零行为变化）
`Engine` 新增两个钩子 `_compute_excludes()`（原来直接调用 `compute_excludes(self.cfg, self.roots)` 的 4 处改为调它）与 `_after_load()`（空实现）；`_add_entry` 增加带默认值的 size/mtime 参数；`refresh_path` 查 `dir_ids` 经 `dkey`（Linux 恒等）。其余 Windows 逻辑全部在 `EngineWin` 子类与 `if IS_WIN` 分支中；`main()` 通过 `make_engine()` 选择引擎。

## 二、测试证据

### Linux（/home/claude/build/tests/run_regression.sh，移植前后各跑一遍）
QA：test_engine（18 场景）、test_search（含 3000 步属性测试，0 不一致）、test_pathref（0 不一致）、test_race／test_gui／test_churn（PyQt5 与 PySide6）、test_perf（30 万条目，计时与移植前一致：ext:pdf 46 ms、*.pdf 55–59 ms）、test_instance、test_install（重新打包后）；`/tmp/qx/t1.py`；t4 PyQt5／PySide6 均 `rc 0`、`rows 6931`。全部通过。（t4 PySide6 在 `rc 0` 之后解释器退出时段错误，返回码 139——移植前基线即如此，与本次改动无关。）

新增 Linux 上运行的 Windows 单元测试 `tests/win/`：
- `test_win_pure.py`（51 项）：FILE_NOTIFY_INFORMATION 解析（多条链、中文、孤立代理项、补充平面字符、截断、损坏偏移不死循环）、路径函数、盘符选根、内置排除、数据目录与 portable.txt、热键解析、启动器命令行、终端候选、`disp`、Linux `SERVER_NAME` 不变。
- `test_win_search.py`（24 项）：切到 Windows 语义后，`\` 与 `/` 路径词、盘符锚定通配、`!` 与 `|` 组合，逐条与暴力整路径比对一致；`dir_ids` 大小写不敏感；`remove_root` 不变式；Linux 下 `\` 不算分隔符。
- `test_engine_win.py`（33 项）：`EngineWin` 驱动真实文件＋假监视器（按 Windows 的事件形态喂入）：扫描即带大小/时间、新建（0.50 s 可见）、父目录未入索引的深层事件、改名、目录对调、删树、MODIFIED、排除子树、溢出补扫、句柄丢失重挂并补空档、安全弹出释放后暂不重挂、盘拔出撤根、新盘加根并监视、缓存头部不含动态根、重启从缓存加载（动态根缺席时删除、在场时补扫）、监视器不可用时的状态。

### Windows（Wine 9.0 + Xvfb，真实运行库与启动器；脚本与结果见 `tests/win/wine/`）
- **扫描**：C:\demo 40,015 个条目 1.57 s，**约 25,400 条/秒**（Wine 走宿主 ext4 且已缓存；真实 NTFS 冷启动会慢于此）。全部文件的大小/时间在扫描时即齐全，没有补 stat。
- **搜索**：`报告`、`ext:pdf`、`demo\报告00`、`demo/报告00/sub01`、`c:\demo\photos02\*.zip`、`PHOTOS`、`sub01\ !jpg` 等与暴力比对一致，每次 2–17 ms。
- **实时监控（ReadDirectoryChangesW）**：新建、改名、删除、建深层目录、目录改名、删树、改大小、只改大小写，8 项**引擎内可见延迟均为 0.50–0.51 s**；界面结果刷新 0.66 s；一次写 2000 个文件全部到位；排除子树内的事件被忽略。
- **缓存**：重启后从缓存就绪 **1.13 s**（含逐目录 mtime 核对），未整盘重扫，条目数一致，重启后实时监控继续生效（0.41 s）。经启动器冷启动到窗口可见约 2.4 s；单文件版首次（含释放运行环境）2.7 s。
- **单实例**：`QianXun.exe --toggle` 隐藏／再次唤出正常；再次双击不产生第二个进程；单文件版的 `--toggle` 也能唤到文件夹版实例（同一套接字名）。
- **系统集成**：打开所在文件夹（Wine explorer 打开并定位）、打开（startfile）、终端、属性、回收站（SHFileOperationW 成功）、重命名、复制文件（剪贴板 URL 正确）均不崩溃且结果正确；HKCU Run 写入／删除正确；桌面 .lnk 创建成功且目标正确；全局热键注册成功，Wine 窗口有焦点时按 Ctrl+Alt+F 窗口隐藏（WM_HOTKEY → 过滤器 → toggle 链路成立）。
- **盘符插拔**：用 dosdevices 符号链接模拟新盘 X:：2.1 s 内加根、扫描、挂上 DirWatcherWin，盘上新文件即时可见；移除后 1.5 s 撤根、句柄关闭、条目清空。
- **界面截图**（`tests/win/wine/results/*.png`，测试运行时生成，不入库）：中文字形正常（简体），.exe 按文件取到启动器自带的千寻图标，其它扩展名为系统文件图标，布局、状态栏、托盘图标正常。zip 版解压到 `C:\测试 目录\` 运行正常。

## 三、平台差异（用户可感知）
- 默认索引全部本地固定盘；U 盘默认索引（插入即加、拔出即撤），网络盘默认不索引。
- Windows 只需每盘一个监视句柄，没有 inotify 名额问题，也就没有“提升上限”菜单。
- 位于 U 盘或网络盘上的项目不能“移到回收站”（会提示到资源管理器处理），避免被 Shell 静默永久删除。
- 属性使用系统属性对话框；终端优先 Windows Terminal。

## 四、已知限制与 Wine 无法证明的部分
- **GetLogicalDrives 在 Wine 中按进程缓存**，新增的 dosdevices 盘符不会出现在位图里（盘符类型与 isdir 会实时变化）。生产代码按真实 Windows 的行为使用位图＋`WM_DEVICECHANGE`；Wine 下的插拔测试改用逐盘符探测注入。真实 Windows 上的 U 盘插拔、安全弹出时的 `DBT_DEVICEQUERYREMOVE` 句柄释放**未能实测**。
- **RegisterHotKey 全局性**：Wine/Xvfb 下只有 Wine 窗口有焦点时才收到 WM_HOTKEY；真实 Windows 的全局触发、与其它软件抢键的提示需实机确认。
- **ShellExecuteExW("properties")** 在 Wine 中返回失败，实际走的是回退对话框；真实 Windows 应弹系统属性页。`QFile.moveToTrash` 在 Wine 下未成功，走的是 SHFileOperationW。
- 真实 NTFS 性能（冷缓存扫描速度、目录 mtime 对 FindFirstFile 数据的同步延迟、大量变化时 512 KB 缓冲是否溢出）、SmartScreen／杀软、DPI 缩放、任务栏 AppUserModelID 分组、OneDrive 占位符目录，都需要在真实 Windows 10/11 上验证。
- 目录 mtime 取自父目录列表（省一次 stat）：若某些文件系统上它与目录自身 stat 不一致，首次重启会多刷新这些目录一次，之后自愈；不影响正确性。
- 每个根的初次扫描在引擎线程内进行：插入一块很大的新盘时，扫描期间其它盘的事件会排队等待（与 Linux 版挂载新盘时的行为一致）。
- 未实现 NTFS USN 日志（Everything 的做法需要管理员权限），因此首次扫描速度取决于目录枚举。

## 五、文件
- 源码：`/home/claude/build/app/qianxun.py`（所有发布物中 sha256 相同：bcdbe874…）
- 测试：`/home/claude/build/tests/win/test_win_pure.py`、`test_win_search.py`、`test_engine_win.py`；Wine 端到端脚本与结果 `tests/win/wine/`（脚本假定复制到 `C:\qxport\`、测试树在 `C:\demo`）；回归入口 `/home/claude/build/tests/run_regression.sh`
- 发布物：`dist/qianxun-1.0.0-windows-x64.zip`、`dist/QianXun-1.0.0-portable.exe`，以及重新打包的麒麟 tar.gz／zip／deb；`dist/SHA256SUMS.txt`
- Windows 说明书：`win/README_WIN.txt`（已打进 zip 的 `QianXun/README.txt`）
