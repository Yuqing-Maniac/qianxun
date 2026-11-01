# 介绍视频工程（2026-10-17，约 82 秒）

本目录只存源文件；录屏 mp4、配音 mp3、配乐 wav、渲染成片均不入库（见 `.gitignore`），可按下述步骤重新生成。
**脚本中的路径保留了原工作区的绝对布局**，迁移后请先替换：

| 原路径 | 对应本仓库 |
|---|---|
| `/home/claude/video/q` | `promo/` |
| `/home/claude/video/q/rm` | `promo/remotion/` |
| `/home/claude/build/app/qianxun.py` | `app/qianxun.py` |
| `/tmp/chromium` | 任一 Chromium（原取自 npm `@sparticuz/chromium`） |

## 流程
1. 文案与时间轴：`script.json`（17 句）→ `tts.py` 调 MiniMax 国际版 `t2a_v2`（speech-02-hd，音色 `presenter_male`，Key 只从环境变量 `MM_KEY` 读取，不落盘）生成 `audio/pNN.mp3` → 按时长生成 `timeline.json`（场景与句子绝对时刻）。
2. 录屏：`rec/make_fs.py` 生成约 104 万条目的演示文件系统；`rec/harness.py` 在 Xvfb（2400×1440，QT_SCALE_FACTOR=1.5）中进程内驱动真实千寻，ffmpeg x11grab 录 R1–R5，输出光标轨迹与事件 `Rk.json`（已入库）。
3. 配乐：`music/make_bgm.py`、`make_sfx.py`、`master.py`（numpy 合成，原创无版权，−16 LUFS），`check.py` 做频谱与削波检查。
4. 动画与合成：`remotion/`（Remotion 4.0.536，React 18）。`node scripts/sync.mjs` 同步素材后渲染：`npx remotion render src/index.ts Main out.mp4 --codec=h264 --crf=18 --audio-bitrate=192k --concurrency=2`，再用 ffmpeg 两遍 loudnorm（−16 LUFS，线性）。字幕：得意黑 Smiley Sans 55 号单行（用户长期规则）。
5. 交付版本 v2 修正：终端命令不在文件名中间折行、筛选镜头整表显示、顶部语法图例上移、删除与字幕重复的托盘文字。
