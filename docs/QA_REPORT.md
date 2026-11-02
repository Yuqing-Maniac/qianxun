# 千寻 QianXun 1.0.0 — QA 报告（2026-10-18）

范围：`app/qianxun.py`、`qianxun.sh`、`assets/install.sh` / `uninstall.sh`、`tools/build_release.sh`、离线包。
做法：每个问题先写最小复现，再改、再复测。改动都是局部修补，没有改架构。Python 3.6+ 兼容性已用 vermin 检查（最低要求 3.5），3.11 和 3.13 下 `py_compile` 均通过。
测试脚本在 `tests/qa/`。

## 一、问题与修复

| # | 严重度 | 问题 | 复现 | 修复 |
|---|---|---|---|---|
| 1 | **严重（崩溃）** | `model.data()` 不持 `index.lock` 读取平行数组。引擎线程追加条目或 `clear()` 时，各数组长度短暂不一致，会抛 `IndexError`。**PyQt5 在虚函数和槽中遇到未捕获异常会直接 abort 进程。**`selected_entries`、`mimeData`、`export_csv` 也有同样问题 | `test_race.py`：引擎线程循环 clear 加扫描，同时读 data，修复前 4 秒约 10 万次异常 | `data()` 改为持锁执行（`_data`）；选中、拖放、重命名、CSV 先在锁内取快照 |
| 2 | **严重（数据安全）** | 重建索引或加载缓存后数组整体换新，界面上旧结果行的条目号会指向**另一个文件**。这期间按 Delete、F2 或复制，操作的是别的文件 | 由 #1 的 race 测试和分析得出 | `Index.gen` 代数号：模型记录生成时的 gen，不一致时 `entry()` 返回 -1；`on_poll` 发现 gen 变化立即重搜 |
| 3 | **严重（崩溃）** | `regex:a{4294967296}` 或 `a{99999999999}`（开启正则时）抛 `OverflowError`，过深的括号嵌套抛 `RecursionError`，异常没有被捕获，GUI 被 abort | `test_search.py` 语法边界用例；`test_gui.py` 在两种绑定下都能复现崩溃 | `Query` 一并捕获上述异常，在状态栏显示“语法错误” |
| 4 | 高（数据错误） | 目录对调（A→T、B→A、T→B）在 0.3 秒去抖窗口内发生时，`refresh_dir` 只按名字和类型比对，名字没变就不重扫，**两棵子树内容互换后长期错位** | `test_engine.py::rename_dirs`（swap） | 记录 `IN_MOVED_FROM/TO` 加 `IN_ISDIR` 事件中的子目录名，刷新时强制重建这些目录 |
| 5 | 高 | 在已索引目录上 mount 本地盘（U 盘挂到 /media/...），或卸载它：目录 mtime 和 inotify 都不会触发，**盘上的文件永远搜不到**，卸载后条目残留 | `mount_ext_like`（ext4 loop 镜像） | 引擎每 2 秒比对 `/proc/self/mounts`，变化时重建受影响的挂载点目录（为根时整根重扫并重新监控） |
| 6 | 高 | 运行中插入的 `/run/media/<user>/<盘>`：`/run` 默认被排除，又只在启动时加入根，**热插拔的 U 盘不会被索引** | `run_media_hotplug` | 挂载变化时把新的 `/run/media` 本地盘作为根加入、扫描并监控 |
| 7 | 高 | inotify 名额用尽后，只要删除过一个受监控目录，`_unwatch` 就会把 `watch_full` 清零，**未监控目录的定时轮询从此停止** | `budget_poll_after_delete` | `_unwatch` 不再清 `watch_full`，空出的名额由每次轮询时的补挂逻辑接上 |
| 8 | 中（性能） | 被监控目录里有文件持续追加（日志每 100 ms 写一次）：每次 size/mtime 变化都把 version 加一，界面每 0.25～0.4 秒全量重搜并重置模型 | `test_churn.py`：10 秒 25 次重搜 | 新增 `struct_version`（只在增删条目时递增）。只有属性变化且查询不依赖 size/dm、也不按大小或时间排序时，只重绘不重搜，降为 10 秒 1 次 |
| 9 | 中 | 非 UTF-8 文件名重命名时，对话框预填的是 U+FFFD 文本，用户不改直接点确定，**文件会被改名为带 �的名字**，原始字节名丢失 | `test_gui.py` | 与 `disp(name)` 相同时视为未改动；同时拒绝 `.` 和 `..` |
| 10 | 中 | 非 UTF-8 文件名移到回收站时，`QFile.moveToTrash(disp(p))` 用的是有损转换后的路径，可能**误删另一个同名（U+FFFD）文件** | 代码审查 | 非 UTF-8 文件名跳过 QFile，走 `gio trash` 或 freedesktop 手工回收站（按原始字节处理） |
| 11 | 中 | 复制文件和拖放时的 URL 用 `fromLocalFile(disp(p))` 生成，非 UTF-8 文件名粘贴到文件管理器后找不到文件，“打开所在文件夹”同样定位不到 | `test_gui.py` URL 字节校验 | `file_url()`：按原始字节百分号编码（`%FF`） |
| 12 | 中 | Qt 5.15 的 `moveToTrash` 在 `~/.local/share/Trash` 不存在时，会把文件挪到**当前工作目录下的 `files/`**，而且不写 trashinfo（测试中实际发生过） | `test_gui.py` 在新建的 XDG_DATA_HOME 下复现 | 调用前先建好 `Trash/files` 和 `Trash/info` |
| 13 | 中 | 注销或关机时会话发 SIGTERM，Python 默认直接终止，索引缓存、窗口和排序状态都不保存，下次启动要整盘重扫或补扫 | `test_instance.sh` 和启动器实测 | SIGTERM 时走 `quit_app`（保存后正常退出），bundled 下实测 exit=0，index.db 和 config 均已写入 |
| 14 | 低 | `folder:"` 或 `file:""` 去掉引号后为空，会丢掉类型过滤，返回全部条目 | `test_semantics` | `_and_kind` 遇到空词时退化为纯 folder 或 file 过滤 |
| 15 | 低 | 手工改坏的 config（如 `"filter":"x"`、`"roots":"/"`）会在 `int()` 处或扫描时异常，程序起不来 | 手工用例 | `load_config` 只接受类型与默认值一致的项 |
| 16 | 低 | mtime 异常（年份越界）时 `time.localtime` 抛异常，在 data() 中会导致 abort | 探测脚本 | `fmt_time()` 统一兜底，异常时返回空串 |
| 17 | 低 | 缓存头部包含全部排除挂载点（docker overlay、/run/user/... 等），挂载变化就会让缓存失效、触发整盘重扫 | 代码审查 | 头部只记录“顶层”排除项 |
| 18 | 低 | 只改大小写的重命名在 FAT/exFAT 上被误判为“同名已存在”；手工回收站 rename 失败时残留孤立的 .trashinfo；日志写入非 UTF-8 路径时可能失败 | 代码审查 | `samestat` 判断；失败时删除 trashinfo；日志用 `errors='backslashreplace'` |
| 19 | 性能 | 100 万条目下，路径匹配（`path:`、含 `/`、Ctrl+U）每次输入 250～440 ms；全字匹配约 420 ms；按“路径”列排序 2.4 s | `test_perf.py` | 路径子串先按目录预计算再查表（`test_pathref.py` 与朴素整路径比对，0 不一致），降到约 120 ms；全字匹配先用子串预筛，降到约 115 ms；路径排序改为两趟稳定排序加目录名次表，降到 1.2 s（大结果集显示等待光标） |
| 20 | 低 | `install.sh` 的 Exec 只在路径含空格时加引号，含 `$`、`` ` ``、`"`、`\`、`%` 的路径会生成非法的 .desktop | 手工用例 | 按 Desktop Entry 规范转义 |

## 二、已验证无问题的项目
- 增量收窄缓存：随机组合输入、退格、切换选项、切换过滤器、键间修改索引，共 3000 步，增量结果与全新 Searcher 结果 **0 不一致**；每 300 步再与暴力逐谓词评估比对一次，也全部一致。
- 删除大目录（2 万条约 0.7 s）、目录与文件互换、符号链接环、坏链接、IN_Q_OVERFLOW（2 万文件超出 16384 队列后补扫一致）、缓存 kill -9 残留 `.tmp`、截断或乱码的缓存文件、头部不匹配、扫描中途重建、配置变更后重建。
- 两种绑定下逐列升降序排序结果正确；12 万以上结果的 name_order 归并路径（含后加条目和已删条目）正确；keep_view 恢复正确；无选中时的右键菜单和各项操作不报错；Esc 行为正确；CSV（中文路径）导出正确；无托盘时窗口不会消失。
- 单实例：第二个实例的 `--toggle`、`--hidden` 立即返回；kill -9 后残留的 socket 不影响重启。
- 安装与卸载：在含空格和中文的 HOME 与源目录下，用户安装、`--autostart`、重复安装、从安装目录自装、通过 symlink 启动、`--purge` 卸载都不留文件，只剩空的 XDG 标准目录；`--system` 安装后卸载，文件系统对比完全一致；deb 的 `dpkg -i` / `-r` 干净，`/usr/bin/qianxun` 指向 `/opt/qianxun/qianxun.sh`；`sh -n` 全部通过。

## 三、已运行的测试（PyQt5 5.15 和 PySide6 6.8 各跑一遍，offscreen 加 Xvfb）
`test_engine.py`（18 个场景）、`test_search.py`（语法边界 × 16 种选项组合、语义、日期与大小解析、3000 步属性测试）、`test_pathref.py`、`test_race.py`、`test_gui.py`、`test_churn.py`、`test_perf.py`（100 万条目）、`test_instance.sh`、`test_install.sh`，以及 shellcheck。
最后用 `tools/build_release.sh` 重新打包，把 x86_64 tar.gz 解压到含中文和空格的目录：在 `env -i`、C 语言环境下用 bundled Python 3.13 加 PyQt5 5.15 启动，索引、搜索“报告”、实时新增文件都正常；`qianxun.sh` 在 QIANXUN_MODE=bundled 下的启动、`--toggle`、SIGTERM 保存也都正常。

## 四、100 万条目下的性能（2 核测试机）
逐字输入：首字约 60 ms，之后 0.2～25 ms。全新查询：`ext:pdf` 150 ms、`*.pdf` 180～270 ms、`size:` 和 `dm:` 130～185 ms、`a|b` 约 250 ms、路径类约 120～140 ms。排序：名称 0.16 s，大小或时间 0.4 s，路径 1.2 s（100 万全量）。9 万结果时各列排序都在 100 ms 以内。

## 五、未修复或保留的问题
- **通配符和 OR 的全新查询**在 100 万条目下约 180～270 ms，超过 150 ms 目标。瓶颈是逐条调用 Python 正则或集合，要再降需要换架构（如预建 trigram 索引），按约束不改。输入有 70 ms 去抖，且每次只在首字发生，体感可以接受。
- **路径列排序 100 万全量需要 1.2 s**（会显示等待光标），只在空查询并按路径排序时出现。
- **aarch64 包没能在本机实际运行**：qemu-user 下缺少 aarch64 系统库（libEGL 等）。PySide6 代码路径已在 x86_64 的 PySide6 6.8 上全量测试，aarch64 运行时仍需在飞腾机器上实测。
- 本机以 root 运行，**无权限目录的测试受限**（root 绕过 DAC）。代码路径是 `OSError` 时跳过，审查结论是安全的。
- 托盘、`close_to_tray` 隐藏和全局快捷键需要真实桌面，offscreen 下无托盘，只验证了无托盘时的分支。
- `qianxun.sh` 的 shellcheck 有一条 SC2010（`ls | grep`）提示，只匹配插件文件名，无实际风险，没有改。
