# 千寻 QianXun — 介绍视频制作规格（共享给所有子代理）

产品：千寻（QianXun），银河麒麟（Kylin Linux）上的 Everything 式文件名秒搜工具。源码 /home/claude/build/app/qianxun.py（PyQt5/PySide6，单文件）。图标 /home/claude/build/app/qianxun.svg（蓝→青渐变圆角方块 + 白色放大镜，内有三条横线）。品牌色 #1E4FD8 → #13A3C2，深色底 #0B1530。

成片：1920×1080，30fps，H.264，总长 = timeline.json 的 total（约 82 秒）。中文解说为 MiniMax 配音，音频在 /home/claude/video/q/audio/pNN.mp3，时间轴在 /home/claude/video/q/timeline.json（sentences[].start/dur 为成片绝对秒；scenes[] 为场景起止）。

字幕（用户长期规则）：得意黑 Smiley Sans（已装：~/.fonts/SmileySans-Oblique.ttf；npm 包 /home/claude/video/node_modules/@fontpkg/smiley-sans/），字号 55px（1080p），每条只能一行、不得换行，居中底部，白字加柔和阴影/半透明底条。字幕文本 = sentences[].text，随句出现。画面中文一律简体字形（Noto Sans CJK SC／思源黑体简体），不得出现日文或繁体字形。

## 场景与镜头（时间为场景内相对秒，以 timeline.json 为准）

| 场景 | 句子 | 画面 |
|---|---|---|
| hook 0–10.5 | p01 p02 | 纯动画。p01：仿麒麟文件管理器窗口，路径面包屑一层层加深（/home/kylin/文档/项目/2024/…），光标反复点开文件夹、滚动、找不到，越来越焦躁（窗口层层叠出）。p02：左侧“Windows · Everything ✓（秒出结果）”，右侧“银河麒麟 · ？”问号闪烁、空状态；不要使用 Everything 的官方图标，只用文字。 |
| title 10.5–15.4 | p03 | 品牌片名：图标从光点生长展开（放大镜描边动画、三条横线依次划入），“千寻”大字（思源黑体 Heavy/Black，或得意黑）+ 副标“银河麒麟 · 文件秒搜”，粒子/光扫过，干净高级。 |
| search 15.4–23.5 | p04 p05 | 录屏 R1：在仿 UKUI 窗口框中展示真实软件；输入“总体方案”，结果即刻刷新。镜头推近搜索框→结果区。p05 时叠加数据卡：“已索引 1,0xx,xxx 个文件”“检索耗时 xx 毫秒”（数字取录屏日志里的真实值）。 |
| how 23.5–36.1 | p06 p07 p08 | p06：动画——磁盘目录树汇流成内存中的一条“名称索引带”，查询光束扫过瞬间命中。p07：分屏——左侧仿终端逐字敲命令（touch／mv／rm），右侧录屏 R2 结果同步出现/改名/消失，命中时绿色脉冲标注“+ 新建”“↻ 改名”“− 删除”。p08：动画——索引缓存写盘，重新启动进度条 0.7 秒满格，“二次启动 < 1 秒”。 |
| syntax 36.1–49.7 | p09 p10 p11 | 录屏 R3：依次输入多条查询，屏幕右侧/上方飘出语法胶囊标签与之同步：`空格 = 与`、`| = 或`、`! = 排除`、`*.pdf 通配符`、`ext:docx;wps`、`size:>100mb`、`dm:today`。镜头随输入在搜索框与结果之间推拉。 |
| filter 49.7–55.6 | p12 | 录屏 R4：点开右上角筛选下拉选“图片”，再点击表头“大小”排序（降序）。 |
| ops 55.6–64.9 | p13 p14 | 录屏 R5：右键菜单展开，光标依次滑过“打开／打开所在文件夹／复制／重命名”，F2 弹出重命名框。p14：动画——窗口缩入托盘图标，键帽 “Alt + Space” 按下，窗口从托盘弹回。 |
| offline 64.9–74.2 | p15 p16 | 动画：断网图标（Wi-Fi 划线）+“完全离线”；两张芯片卡片“x86_64”“飞腾 · arm64”并排点亮；下方两个包裹图标“deb 安装包”“绿色版 tar.gz”，打勾。 |
| outro 74.2–81.8 | p17 | 图标 + “千寻” + 金句“千寻之深，一寻即得”，副标“银河麒麟 · 文件秒搜 · 离线可用”，缓慢光效收尾，淡出。 |

## 录屏素材接口（录屏代理产出，动画代理消费）

目录 /home/claude/video/q/rec/。每段录屏：`Rk.mp4` + `Rk.json`。
- 录制方式：Xvfb 2400×1440，`QT_SCALE_FACTOR=1.5`，应用窗口铺满（逻辑 1600×960），ffmpeg x11grab 30fps，不画系统光标。
- `Rk.json` = `{ "fps":30, "width":2400, "height":1440, "scale":1.5, "duration":秒, "cursor":[{"t":秒,"x":px,"y":px,"down":bool}], "events":[{"t":秒,"type":"type|click|rightclick|key|fs|result|...","label":"…","value":…}], "rects":{ "search":[x,y,w,h], "results":[...], "statusbar":[...], "filter":[...], "header_size":[...], "menu":[...], ...}, "stats":{"indexed":整数,"search_ms":[{"t":秒,"q":"…","ms":数}]} }`，坐标为录屏像素（物理 px）。光标由动画端按 cursor 轨迹绘制（仿系统箭头，点击有涟漪）。
- 镜头（录屏内时间要与配音对齐：每段录屏开始时刻 = 所在场景开始时刻，长度不少于场景长度；动作时刻按句子起点安排）。

## CPU 约束
本机仅 2 核。录屏期间存在锁文件 /home/claude/video/q/rec/RECORDING.lock，此时其他代理不得进行 Remotion 全片渲染或其他重 CPU 任务（可写代码、可渲染单帧）。
