# QianXun recordings (2400x1440, 30fps, scale 1.5; clip t=0 == action t0)
Regenerate: python3 make_fs.py; python3 harness.py prebuild; python3 harness.py R1 R2 R3 R4 R5 (lock file RECORDING.lock while recording).
Index: 1,040,333 entries, 30,791 dirs, status bar "实时监控已全覆盖".
R1 9.0s (scene search): click search 0.62, type 总体/方案 1.62/1.80, results visible 1.9 (33 rows, 0.1ms incremental / ~42-64ms full), hover rows, select row1 7.78.
R2 5.77s (t0 = p07 start-0.4): touch 1.00 (visible 1.86), mv 2.40 (3.27), rm 3.80 (4.68). Harness nudge do_search(keep_view) 0.25s after index.version change (events type=refresh); real UI lag ~0.9s.
R3 14.2s: queries visible at 3.49 报告 2024, 5.46 jpg|png, 6.10 报告 !草稿, 8.21 *.pdf, 10.00 ext:docx;wps, 10.77 size:>100mb (40), 11.87 dm:today (35).
R4 6.4s: click filter 1.10, select 图片 2.55, header 大小 3.50 (asc), 4.40 (desc). Start query "2024".
R5 6.08s: right-click 2.55->0.55, menu 0.75, hover 打开 1.0 / 打开所在文件夹 1.55 / 复制 2.96 / 重命名 3.60, Esc 4.2, F2 4.45, dialog 4.75, Esc 5.65.
JSON rects include menu/dialog/hover_* where relevant.
