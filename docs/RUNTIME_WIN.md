# 千寻 Windows 运行时与启动器（runtime 代理交付）

## 产物
| 文件 | 大小 | 说明 |
|---|---|---|
| dist/qianxun-1.0.0-windows-x64.zip | 24.4 MB | 顶层 QianXun/，全部 ASCII 条目名（Python zipfile） |
| dist/QianXun-1.0.0-portable.exe | 24.5 MB | 单文件版：启动器 + zlib 负载 |
| win/runtime/ | 64 MB（解压后） | Python 3.13.15 + PyQt5 5.15.11 / Qt 5.15.2，已裁剪，stdlib 预编译 unchecked-hash .pyc |
| win/obj/QianXun.exe | 0.13 MB | 文件夹版启动器（静态链接，GUI 子系统） |

## 命令
- 重建运行时：`win/build_runtime.sh`（需 /tmp/pp 下 npm 包与 whl，缺失会自动下载；用 Wine 预编译 .pyc）
- 重建发布物：`win/build_win.sh`（取当前 app/qianxun.py；生成 icon、启动器、dist/stage-win/QianXun、zip、portable、更新 SHA256SUMS.txt）
- 打包器：`win/pack_portable.py 启动器exe 运行时目录 app目录 输出exe`
- README：存在 `win/README_WIN.txt` 即使用（自动转 UTF-8 BOM + CRLF），否则生成占位。

## 启动器行为
- QianXun.exe：GetModuleFileNameW 定位自身；检查 runtime\pythonw.exe 与 app\qianxun.py（缺失 -> 中文 MessageBox，不挂起）；
  设置 QIANXUN_LAUNCHER=自身全路径（另设 PYTHONNOUSERSITE=1，清 PYTHONHOME/PYTHONPATH）；
  CreateProcessW `"pythonw.exe" -X utf8 "app\qianxun.py" <原参数逐字转发>`，继承调用者 cwd，不等待，立即退出。
- 清单：asInvoker、PerMonitorV2、Win10 supportedOS、Common Controls v6、longPathAware。资源：多尺寸 ICO（16-256，256 为 PNG）、VERSIONINFO。
- portable：负载格式见 launcher.c 头注释（72 字节尾部：魔数、索引偏移/大小、条目数、sha256、尾魔数；条目：路径、size、csize、offset、crc32）。
  目标 `%LOCALAPPDATA%\QianXun\rt-<sha256 前 12 位>\`；存在 `.complete` 则跳过；否则解压到同级 `tmp-*`，
  最后写 `.complete`，MoveFileExW 改名发布；目标已被他人先建则丢弃临时目录；超 0.5 s 弹“千寻正在首次准备运行环境…”窗口。
  每个文件解压时校验 size 与 crc32；拒绝含 `..` 的路径。旧哈希目录不自动清理（可能仍在运行）。
  QIANXUN_LAUNCHER 为 portable exe 自身路径。注意：portable 下 app 所在目录是 rt-*，`portable.txt` 机制不适用，数据走 %LOCALAPPDATA%\QianXun\。

## 重要发现（给移植代理）
- Qt 5 在安装路径含“当前系统 ANSI 代码页外字符”时（如英文 Windows 上的中文目录；Wine 下 ACP=1252 可复现）会把插件路径变成 `??`，
  报 “no Qt platform plugin could be initialized”。运行时已内置 `Lib/site-packages/sitecustomize.py`：导入 PyQt5.QtCore 时自动
  `QCoreApplication.setLibraryPaths([PyQt5/Qt5/plugins])`，app 无需处理（app 内再做一次同样调用也无害）。
- 裁剪掉了 _ssl/_hashlib/OpenSSL（hashlib 回退内置实现），也无 tkinter/curses/idlelib/test。需要 ssl 的功能不可用。
- stdout/stderr 在 pythonw 下为 None：app 打印前需判空或重定向日志。

## 测试结果（Wine 9.0 + Xvfb，Python 3.13.15 / Qt 5.15.2 / PyQt5 5.15.11）
- python.exe 导入 ctypes/sqlite3/winreg/PyQt5 全模块 OK；GUI 冒烟（QApplication+QWidget+QLineEdit 显示、QLocalServer.listen=True、QTimer 退出）OK，中文显示正常。
- 文件夹启动器：路径 `Z:\tmp\pp\t\测试 目录\千寻 QianXun\`（空格+中文）OK；参数 `a b` / `中文参数` / `--toggle` / `x"y` / `C:\p q\` 逐字到达 sys.argv；QIANXUN_LAUNCHER 正确。
- runtime 缺失：弹中文错误框，进程等待点击，不死循环、不崩溃。
- portable：首次运行约 3.0 s 到应用启动（解压 56 MB/1086 文件约 2.3 s，弹进度窗口）；第二次 0.27 s；
  4 个实例同时冷启动：全部成功、仅 1 个 rt-* 目录、无 tmp-* 残留、解压树 sha256 与源 runtime 完全一致。
- zip 条目 1088 个，全部 ASCII。

## Wine 测试环境
```
source /home/claude/build/win/env.sh      # WINEPREFIX=/home/claude/build/win/wineprefix WINEDEBUG=-all WINEARCH=win64
xvfb-run -a -s "-screen 0 1280x800x24" wine <exe> ...    # 或 win/wine_run.sh wine <exe> ...
```
字体：Noto Sans CJK 已复制到 prefix 的 windows\Fonts，FontSubstitutes（YaHei UI/YaHei/SimSun/MS Shell Dlg(2)/Segoe UI/Tahoma 等）与 FontLink 已写入（fonts.reg）。
截图：在 xvfb-run 的 bash 里 `import -window root x.png`。LOCALAPPDATA=C:\users\root\AppData\Local（即 wineprefix/drive_c/users/root/AppData/Local）。
注意：不要 `pkill wine`（会杀自己的 shell）；用 `wineserver -k`。`python.exe` 输出重定向到文件需 `| cat`，否则句柄无效。

## 注意事项与 Wine 无法证明的部分
- 仅 Windows 10 及以上 64 位（Python 3.13 要求）。
- 未签名 exe：SmartScreen 可能提示“未知发布者”；部分杀软对“自解压/附加负载”的 exe 启发式报毒，建议发布 zip 为主、portable 为辅，必要时提供 SHA256。
- Wine 不能证明：真实 DPI 缩放表现、真实 Windows Defender/SmartScreen 行为、任务栏图标/AppUserModelID、系统 Explorer 集成、ACP=936 下的实际行为（已通过 ACP=1252 的更严苛情形验证）、MOTW（网络下载标记）对 zip 内文件的影响（用户需“解除锁定”后再解压，或直接解压即可）。
- 运行时目录含 .pyc（unchecked-hash）：修改运行时 .py 后需删除对应 .pyc。
