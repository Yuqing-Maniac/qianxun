# 千寻 BGM 与音效

原创合成（Python/numpy：polyBLEP 锯齿、加法合成、卷积混响、侧链、压限），无采样，可免版税使用。D 大调 / B 小调，100 BPM，44.1 kHz 立体声。

## 文件
- bgm.wav  时长 81.765 s（与 timeline.json 一致），积分响度 -16.0 LUFS，真峰值 -2.2 dBTP，无削波，直流约 0，首尾归零。
- bgm_spectrogram.png  频谱图与 RMS 曲线
- sfx/  whoosh(0.6s) pop click key success(2.1s) riser(1.5s) hit(4.5s) tick，峰值约 -3 至 -10 dBFS
- make_bgm.py / make_sfx.py / master.py  可复现脚本

## 时间点（秒）
- 揭幕冲击（hit，低频重击＋钟声和弦）：11.184（title 起点 10.484 + 0.7），起势 riser 自 8.58 起
- 场景切换（各自前约 1.6 s 为反向镲/嗖声扫频，结束于场景起点）：
  search 15.389（节奏进入）、how 23.502、syntax 36.095、filter 49.74、ops 55.603、offline 64.868（加厚＋副琶音）、outro 74.16（终止和弦＋钟声，长混响）
- 淡出至静音：约 78.0–81.76

## 说明
300 Hz–3 kHz 已做衰减让位旁白；hook 段无旋律，仅有低频脉动垫音与滴答声。SFX 在编辑器中建议比 BGM 高约 6 dB 使用。
