#!/bin/bash
# check_imports.sh <exe>: list imported DLLs, flag DLLs outside the spec list and APIs that do not exist on Win7 SP1.
EXE=${1:-$(cd "$(dirname "$0")/../.." && pwd)/native/out/QianXun-x64.exe}
case "$EXE" in *x86*) OD=i686-w64-mingw32-objdump;; *) OD=x86_64-w64-mingw32-objdump;; esac
ALLOWED='kernel32 user32 gdi32 shell32 ole32 comctl32 shlwapi advapi32 uxtheme msvcrt'
BAD='GetDpiForWindow|GetDpiForSystem|SetProcessDpiAwarenessContext|SetThreadDescription|GetThreadDescription|PathCch|GetSystemTimePreciseAsFileTime|CreateFile2|WaitOnAddress|WakeByAddress|PrefetchVirtualMemory|SetProcessDpiAwareness|GetDpiForMonitor|GetSystemMetricsForDpi|AdjustWindowRectExForDpi|EnableNonClientDpiScaling|SystemParametersInfoForDpi|GetAwarenessFromDpiAwarenessContext|SetThreadpoolTimerEx|CreateFileMapping2|LoadPackagedLibrary|SetDefaultDllDirectories|AddDllDirectory|api-ms-win|ext-ms-win|GetCurrentPackage|InitOnce'
echo "== DLL imports ($EXE)"
$OD -p "$EXE" | awk '/DLL Name:/{print $3}' | tr 'A-Z' 'a-z' | sort -u | while read d; do
  b=${d%.dll}; if echo " $ALLOWED " | grep -q " $b "; then echo "  ok      $d"; else echo "  OUTSIDE-SPEC-LIST  $d"; fi; done
echo "== suspicious (Win8+/delay-load-only) imports"
$OD -p "$EXE" | grep -E "$BAD" | sort -u | sed 's/^/  /' || true
$OD -p "$EXE" | grep -qE "$BAD" || echo "  none"
echo "== subsystem / version fields"
$OD -p "$EXE" | grep -E 'MajorSubsystemVersion|MinorSubsystemVersion|MajorOSystemVersion|Subsystem\s' | sed 's/^/  /'
echo "== GetProcAddress use (dynamic lookup expected for Win8+ APIs)"
strings -a "$EXE" | grep -E '^(GetDpiForWindow|SetProcessDpiAwarenessContext|SetThreadDescription|GetDpiForMonitor|SetProcessDpiAwareness)$' | sort -u | sed 's/^/  string present: /'
