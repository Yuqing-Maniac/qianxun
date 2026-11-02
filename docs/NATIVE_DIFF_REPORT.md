# QianXun native (--cli) test report, 2026-10-19

Exes: out/QianXun-x64.exe (1.69 MB, built 06:06), out/QianXun-x86.exe. Wine 9.0, Win7 mode, TZ=Asia/Shanghai.
Prefixes: test/prefix64 (win64), test/prefix32 (win32, wine32:i386 installed). Env: env64.sh / env32.sh.

## Differential suite (578 queries vs Python oracle in Windows mode, corpus 63,579 entries / 3,860 dirs)
| exe | PASS | FAIL | CRASH/TIMEOUT | wall | #ms median / p90 / max |
|---|---|---|---|---|---|
| x64 (Win7 prefix) | 578 | 0 | 0 | 389 s | 1.0 / 10.6 / 1209 ms |
| x86 (32-bit Win7 prefix) | 578 | 0 | 0 | 392 s | 1.1 / 10.6 / 966 ms |

All 25 categories pass (plain, unicode folding, boolean, quotes, wildcards, path terms, path:, ext, file/folder, regex incl. errors,
size and dm all forms, toggles, filters 0-8, edge cases, 120+ syntax-error cases). Including the "soft" items
(U+0130 folding, ss, Python-only regex syntax) the native result equals the oracle on this corpus. Syntax errors give empty results,
rc 0, `#error=` line. Sorting by name (case-insensitive) holds (5 queries sorted by upper-fold key, equivalent). No duplicates, no
BOM/CRLF, footer count == lines. Symlink loop (special\loop\up/root/self): nothing listed below a link; no recursion.
Long paths (>260, boundary 258-262, 14-level deep) all found. Details: report/native64/summary.md, report/native32/summary.md.

Imports (check_imports.sh): only advapi32, comctl32, gdi32, kernel32, msvcrt, ole32, shell32, user32, uxtheme; no Win8+ imports;
GetDpiForWindow present only as string (GetProcAddress).

## Live update (--cli-watch), report/live_x64.md, live_x86.md
Latency from Linux-side change to the count following: 376-402 ms (x64), ~355 ms (x86) for create, 50-file burst, rename in/out of match,
delete, CJK name, new dir with 20 files, dir moved out/in the root, subtree delete (consistent with the 300 ms debounce); size
refresh (truncate/append, query `size:>1kb`) 366-387 ms. Sampling every 100 ms (max gap 111 ms); exit 0, `#ready`/`#end` present.
**Problem (Wine, not native):** after a directory is renamed (d03 -> d03_renamed) new files created inside are never reported.
A 20-line standalone ReadDirectoryChangesW (recursive) program under Wine shows the same: events for the rename only, nothing for
files later created in the renamed directory (Wine's inotify emulation loses the watch). Real Windows delivers them; a
workaround in native (re-arm / rescan the renamed dir on FILE_ACTION_RENAMED_NEW_NAME) would also make it robust. Likely harmless on Windows.
Everything else (incl. the file after the 100-file create/delete storm) passed; the "NEVER" rows are the consequence of the one bug above (the count stays 1 behind).

## Performance, ~951k entries (950k files + 1,050 dirs), report/perf_x64.md, perf_x86.md
Scan + startup under Wine: ~4.1 s (x64), ~4.7 s (x86) (wall of a no-match run minus 0.15 s startup). Peak RSS 119-124 MB including Wine
(target < 150 MB: met). Query #ms (23 queries, all counts equal oracle): median 8 ms, p90 22 ms; substring/ext/size/dm/path/OR/filter
queries 2-25 ms (target < 30 ms met, including `a` = 312,682 hits at 17.5 ms and path match `data` 177,656 hits at 22 ms);
the exception: `regex:^img_\d+` 1.1 s (x64) / 2.0 s (x86) on 951k entries (std::wregex; Python is similar). x86 is not slower otherwise.

## Mismatch analysis
None remaining. Intentional gaps listed by the author (regex lookbehind, (?P=name), 1:1 lowercase folding, `?` = one UTF-16 unit) are
not exercised by the 578 queries except as soft items, which agreed with the oracle. Not covered: GUI, tray, hotkey, shell operations;
real NTFS reparse points/junctions (Wine reports symlinked dirs as DIRECTORY|REPARSE_POINT with tag 0, files symlinks as plain files).

## Harness notes
* run_diff.sh [exe] [--tag T] [-j N] [--cats a,b] [--ids ..]; relative-date files are re-touched and the oracle rebuilt daily; `lastNd`
  style queries are checked against a window of oracle results (run start/end) because "now" moves.
* Never capture Wine output through pipes in subprocess: lazily spawned wine helper processes inherit the pipe and cause apparent
  120 s hangs (this was a harness bug, fixed; no native hang exists; 100-run stress at j2 clean, stress_hang.py).
* Run `wineserver -k` between headless and GUI runs (done at the end). Wrapper /usr/local/bin/wine picks wine64 for win64 prefixes (needed after wine32 install).
