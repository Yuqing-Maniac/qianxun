# 千寻 QianXun — Windows 原生版：实现说明

C++17 + 纯 Win32 API，mingw-w64 交叉编译，单文件 exe，零运行库依赖，Windows 7 SP1 – Windows 11，无需管理员权限。

## 产物

| 文件 | 大小 | 说明 |
|---|---|---|
| `out/QianXun-x64.exe` | 1,693,696 B | x86-64，静态链接 libstdc++/libgcc |
| `out/QianXun-x86.exe` | 1,878,016 B | i686（需 SSE2），`--large-address-aware` |

构建：`./build.sh`（或 `./build.sh x64` / `./build.sh x86`）。工具链：`x86_64-w64-mingw32-g++-win32` / `i686-w64-mingw32-g++-win32`（GCC 13，win32 线程模型；GCC 13 起该模型下 `std::thread`/`std::mutex` 可用，基于 SRWLOCK/CONDITION_VARIABLE，Vista+）。编译选项：`-O2 -static -static-libgcc -static-libstdc++ -municode -mwindows -DUNICODE -D_UNICODE -D_WIN32_WINNT=0x0601 -DWINVER=0x0601`，链接 `-s`、DEP/ASLR。

## 导入表核查（`x86_64-w64-mingw32-objdump -p`）

两个 exe 只导入：KERNEL32、USER32、GDI32、SHELL32、ole32、COMCTL32、ADVAPI32、UxTheme、msvcrt。
逐函数核对：最新的是 Vista/Win7 级 API（SRWLOCK、CONDITION_VARIABLE、CancelIoEx、FindFirstFileExW、SHCreateDataObject、K32GetProcessMemoryInfo〔Win7 起在 kernel32〕），**无 Win8+ 导入**，无 api-ms-win-*。Win10 才有的 `GetDpiForWindow`、`SystemParametersInfoForDpi`、`SetCurrentProcessExplicitAppUserModelID`、`AttachConsole` 等一律 `GetProcAddress` 动态获取。msvcrt 只用 XP 起就有的经典函数。

资源：多尺寸图标（复用 `win/launcher/qianxun.ico`）、VERSIONINFO（FileDescription=千寻 文件秒搜，ProductName=千寻，FileVersion=1.2.0.0）、清单（asInvoker、Common Controls v6、supportedOS Win7/8/8.1/10、`dpiAware=true/pm` + `dpiAwareness=PerMonitorV2,PerMonitor`、longPathAware）。

## 架构

```
src/
  textutil.{h,cpp}  小写折叠表（Win: LCMapStringW 不变区域）、Python 兼容 isspace/\w/\d、码点序比较、UTF-8、SSE2 子串搜索
  query.{h,cpp}     搜索语法解析（逐条对照 qianxun.py：split_tokens/split_or/Query/size_range/date_range/fnmatch.translate）
                    + Python re → ECMAScript 正则转换（QxTraits：Unicode \w\d\s、表驱动 icase）
  index.{h,cpp}     索引：32 字节 Entry（父目录号/名称偏移/长度/类型/标志/大小/FILETIME），分块 UTF-16 名称池（原文+小写两份同布局），
                    目录表（完整路径+子项），开放寻址的大小写不敏感路径表；名称预排序（rank）；二进制缓存（校验和、头部比对）
  search.{h,cpp}    fork-join 线程池；按块并行过滤；名称子串全扫描走“名称池 SIMD 扫描 + 偏移映射条目”快路径；
                    增量收窄（与 Python 相同的 is_plain/前缀条件）；排序（名称用预排序 rank 走表、路径用目录 rank、大小/时间）
  engine.{h,cpp}    多线程目录级工作队列扫描（FindFirstFileExW Basic+LARGE_FETCH，回退 FindFirstFileW；≥240 字符加 \\?\）；
                    ReadDirectoryChangesW（每根一个，512 KB/网络 64 KB，OVERLAPPED + WaitForMultipleObjects + 命令事件）；
                    300 ms 去抖差量重扫、修改事件只刷新大小/时间、溢出整根比对、句柄失效撤根、2 s 盘符位图比较增删根、
                    DBT_DEVICEQUERYREMOVE 释放句柄、30 min 保存/补全、退出保存（对照 Engine/EngineWin/DirWatcherWin）
  ui_main.cpp       主窗口：搜索框（提示文字、Ctrl+A/Ctrl+Backspace）、筛选下拉、LVS_OWNERDATA 虚拟列表（整行自绘：交替行、
                    主题选中背景、系统图标、名称列匹配片段加粗）、状态栏两栏、菜单+加速键、托盘、RegisterHotKey、
                    WM_COPYDATA 单实例、WM_DPICHANGED、后台搜索线程（新输入取消旧搜索）
  ui_dialogs.cpp    帮助（F1，两张表+说明）、关于、选项（索引范围/排除目录列表+添加删除、复选框、HOTKEY_CLASS 热键）、重命名输入框
  shell.cpp         打开/打不开时“打开方式”、定位（SHOpenFolderAndSelectItems）、终端（wt→powershell→cmd）、CF_HDROP+Preferred DropEffect、
                    回收站（SHFileOperationW）、属性、Shift+右键系统菜单（IContextMenu2/3）、拖出（SHCreateDataObject+SHDoDragDrop）、
                    桌面快捷方式（IShellLinkW）、开机自启（HKCU\…\Run）、图标缓存（按扩展名；exe/lnk/ico/url 等按路径 LRU 2000）
  config.cpp        config.ini（UTF-8 key=value）、热键串 ⇄ (MOD_*, VK)（与 Python parse_hotkey 同语法）
  plat_win.cpp      平台钩子、日志（qianxun.log，4 MB 轮转）、数据目录（portable.txt → exe 同目录 data\，否则 %LOCALAPPDATA%\QianXun）
  cli.cpp           规格第 9 节测试接口
  main.cpp          入口：--cli 分流、命名互斥体单实例、OleInitialize、消息循环
unittest/           Linux 下的差分测试（同一份 query/index/search 源码用 g++ 编译）
```

线程：UI 线程（只在此更新界面）；引擎线程（唯一的常驻写者）；扫描期间 N 个扫描线程（写锁按目录持有）；搜索线程（读锁，内部用线程池）。读写用 SRWLOCK；条目号在缓存重载时会整体换代（`gen`），界面据此作废旧结果并重搜。

数据文件（与 Python 版同目录、不同文件名，可共存）：`config.ini`、`index.bin`、`qianxun.log`。

## 测试接口（规格 §9）

```
QianXun-x64.exe --cli --root <目录> [--root …] --query "<查询>" [--case] [--whole] [--path] [--regex] [--filter <0-8>] --out <文件>
```
- 不建窗口，不读写配置/缓存；扫描给定根（根本身不作为结果，与 Python 一致；内置排除同 Python win_excludes），执行一次查询。
- 输出 UTF-8、LF：每行一个完整路径，按“小写名称（码点序）→ 小写完整路径 → 原样完整路径”升序；最后一行 `#count=<N> #ms=<查询+排序毫秒，3 位小数>`。
- 查询有语法错误时：在最后一行前多一行 `#error=<说明>`，count=0。退出码 0；参数错误/根不存在/输出不可写 → 退出码 2（stderr 有中文说明）。
- `--cli-watch … --duration <秒>`：扫描后进入实时监控；先写 `#ready t=<epoch 秒> count=<N> entries=<条目数>`，然后每 100 ms 追加 `<epoch 秒，3 位小数> <结果数>`，结束写 `#end`。以 `#` 开头的行都是元数据。
- 自测附加参数：`--threads n`、`--stats`（`#stat …` 行：条目数、扫描耗时/速率、内存、查询分解）、`--synthetic N`（内存合成 N 条目，用于百万级基准）、`--repeat k`、`--batch <文件>`（每行 `选项4位\t筛选序号\t查询`，一次进程跑多条查询）。

**Wine 注意**：必须在 UTF-8 locale 下运行 Wine（`LC_ALL=C.UTF-8`，见 `win/env.sh`），否则 Wine 把 Linux 上的非 ASCII 文件名转换成乱码（这是 Wine 环境问题，曾误判为 x86 版缺陷）。无窗口的 CLI 跑完后要先 `wineserver -k` 再在 Xvfb 下起 GUI，否则 GUI 连到无显示的旧 wineserver 会 CreateWindow 失败（程序记日志后退出码 1）。

## 已验证（Wine 9.0 + Xvfb；本机 2 核）

**语义差分（与 qianxun.py 的 Query/Searcher 对照，WinMode）**
- 合成索引（6000 条，Windows 路径，含中文/全角/ß/é/方括号/通配/删除条目）× 4084 条查询（182 条刁钻查询 × 12 种开关组合 + 9 种筛选 + 1500 步随机输入序列，覆盖增量收窄）：**0 差异**（Linux g++ 构建，同源码）。
- 真实磁盘树（2466 条，含 emoji、全角、`'`、`;`、`#`、`!` 等）经 Wine 扫描 × 1408 条查询：x64 **0 差异**，x86（自建 32 位前缀）**0 差异**，且 x86/x64 全量输出逐字节相同。
- 期间发现并修复：Python `[]]` 等正则方言差异（加了 Python→ECMAScript 转换）、全字匹配下 UTF-16 代理对（emoji）被当作单词字符。

**性能（Wine 下实测，2 线程）**
- 百万条目（`--synthetic 1000000`）：内存 117–122 MB（进程 PagefileUsage；索引自估 110 MB）。查询耗时（含排序）：`ab` 4.5 ms、`abc` 1.5 ms、`报告` 5.8 ms（5 万结果）、`*.pdf` 11 ms、`ext:pdf` 11.7 ms、`dm:2025` 8.3 ms、`size:>50mb` 15.9 ms（46 万结果）、`an|bo` 9.8 ms、`a` 14.2 ms（39 万结果）、空查询 14.5 ms（100 万结果）、`!an` 30 ms（95 万结果）；正则 `^an.*\d{3}\.txt$` ≈1.1 s（libstdc++ 正则慢，可被新输入取消）。
- 缓存：100 万条目保存 0.17 s、加载 0.57 s，文件 55 MB；5.2 万条目加载 0.02 s。
- 扫描（Wine 的 FindFirstFile 仿真，真机 NTFS 会快得多）：30 万条目 1 线程 64k/s、4 线程 103k/s、8 线程 117k/s；C:\ 5.2 万条目 0.49 s。
- 实时更新（`--cli-watch`，100 ms 采样）：新建、深层新建、改名、新建子树、删除子树、删除 → 结果变化延迟 357–371 ms（含 300 ms 去抖）；500 个文件风暴 193–352 ms 一次性反映。

**GUI（截图人工检查）**：C:\（5.2 万条目，含中文目录）下输入英文/中文查询、名称列加粗高亮、系统图标、交替行、状态栏“N 个对象｜已选中 M 个”与“索引就绪：…｜实时监控已全覆盖”；点击表头按大小升/降序；监控目录新建文件约 1 s 内出现在结果；右键菜单（中文、快捷键对齐）；Shift+右键系统菜单；F2 重命名（MoveFileW，索引随之更新）；Delete → 确认框 → 进回收站（Wine Trash）且结果消失；F1 帮助、Ctrl+P 选项（修复了分组框黑底、列表框多余横向滚动条、帮助表格高度）；Ctrl+S 弹出保存对话框；托盘图标；`--hidden` 启动不显示、`--toggle` 显示/隐藏（单实例，第二个进程立即退出）；Esc 清空/再按隐藏、Alt+F4 隐藏到托盘、Ctrl+Alt+F 热键切换；Ctrl+Q 退出时保存配置与索引，重启从缓存秒开；144 DPI 下窗口约 1650×980、字体与列宽按 150% 缩放；x86 版 GUI 在 32 位前缀运行正常。
- 鲁棒性：513 字符深路径（`\\?\`）、符号链接环（只收录不进入）、悬空链接、制表符/控制字符/emoji 文件名、错误查询（`size:abc`、`regex:(`、`dm:2026-13`）均正常；根不存在退出码 2。

## 与 Python 版的已知差异 / 局限

- 正则：std::regex（ECMAScript），已兼容 Python 的 `[]…]`、`{` 字面量、`{,n}`、`\A`/`\Z`、`(?P<name>…)`、开头的 `(?i)` 等内联标志、Unicode `\w\d\s`；**不支持后行断言 `(?<=…)`/`(?<!…)` 与 `(?P=name)`**（报“语法错误”）。libstdc++ 正则较慢（百万条目约 1 s，可取消）。
- 小写折叠用 LCMapStringW 1:1 映射；Python `str.lower()` 对少数字符（如 `İ` → `i̇`）会改变长度，这类极端字符的匹配可能不同。`?` 通配匹配一个 UTF-16 单元（emoji 等增补平面字符占两个）。
- “同名按路径”的次序：Python GUI 里同名项保持条目顺序，原生版按路径排序（CLI 规格要求）。
- 配置/缓存格式与 Python 版不同（config.ini / index.bin），不互相读取。
- Wine 无法证明的部分：真实 Windows 7 上的运行（导入表已核查）、Explorer 主题下的选中行外观（Wine 主题只画边框）、真实每显示器 DPI 切换（WM_DPICHANGED 代码路径未在 Wine 触发）、真机 NTFS 扫描速度、可移动盘安全弹出（DBT_DEVICEQUERYREMOVE）、开机自启与桌面快捷方式的实际效果、拖放到 Explorer、SmartScreen/杀软对未签名 exe 的反应。
- 选项里“索引网络文件系统（NFS／SMB 等）”沿用 Python 文案；右键菜单用 Python 的“在终端中打开”。

## 差分测试复现

```
cd unittest
g++ -std=c++17 -O2 -o qtest qtest.cpp plat_linux.cpp ../src/{textutil,query,index,search}.cpp -lpthread
python3 gen_and_ref.py <临时目录> && ./qtest <临时目录>/listing.tsv <临时目录>/queries.tsv > <临时目录>/cpp.txt && python3 cmp.py <临时目录>
python3 disk_diff.py <临时目录> ../out/QianXun-x64.exe                                   # 64 位前缀
QX_WINE=wine QX_PREFIX=<32 位前缀> python3 disk_diff.py <临时目录> ../out/QianXun-x86.exe   # 32 位前缀
```
