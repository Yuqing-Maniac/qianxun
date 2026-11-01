/*
 * 千寻 QianXun launcher.
 *   QianXun.exe           : runtime\pythonw.exe + app\qianxun.py next to the exe
 *   QianXun-portable.exe  : (-DPORTABLE) payload appended to the exe, extracted
 *                           once to %LOCALAPPDATA%\QianXun\rt-<hash12>\
 * Build: x86_64-w64-mingw32-gcc -municode -mwindows -O2 -s [-DPORTABLE] launcher.c res.o -lz
 * Source file is UTF-8; Chinese strings are written as \u escapes for safety.
 */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <commctrl.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#ifdef PORTABLE
#include <zlib.h>
#endif

#define MSG_TITLE L"千寻"                       /* 千寻 */

static void fail_box(const wchar_t *msg)
{
    MessageBoxW(NULL, msg, MSG_TITLE, MB_OK | MB_ICONERROR | MB_SETFOREGROUND);
}

/* Return pointer to the arguments after argv[0] in a raw command line
 * (CommandLineToArgvW rules for argv[0]: quoted => up to closing quote,
 * otherwise up to first space/tab; no backslash escaping in argv[0]). */
static const wchar_t *skip_argv0(const wchar_t *p)
{
    if (*p == L'"') {
        p++;
        while (*p && *p != L'"') p++;
        if (*p == L'"') p++;
    } else {
        while (*p && *p != L' ' && *p != L'\t') p++;
    }
    while (*p == L' ' || *p == L'\t') p++;
    return p;
}

static int exists_file(const wchar_t *p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

/* Launch <base>\runtime\pythonw.exe -X utf8 "<base>\app\qianxun.py" <args> */
static int launch(const wchar_t *base, const wchar_t *self_path)
{
    wchar_t py[MAX_PATH * 2], app[MAX_PATH * 2];
    _snwprintf(py, MAX_PATH * 2, L"%ls\\runtime\\pythonw.exe", base);
    _snwprintf(app, MAX_PATH * 2, L"%ls\\app\\qianxun.py", base);
    py[MAX_PATH * 2 - 1] = app[MAX_PATH * 2 - 1] = 0;

    if (!exists_file(py) || !exists_file(app)) {
        wchar_t m[MAX_PATH * 4 + 256];
        _snwprintf(m, sizeof m / sizeof m[0],
            L"找不到运行环境或程序文件。\n\n"
            L"缺少：%ls\n\n"
            L"请重新解压完整的“千寻”文件夹，"
            L"不要单独复制 QianXun.exe。",
            exists_file(py) ? app : py);
        m[sizeof m / sizeof m[0] - 1] = 0;
        fail_box(m);
        return 2;
    }

    SetEnvironmentVariableW(L"QIANXUN_LAUNCHER", self_path);
    SetEnvironmentVariableW(L"PYTHONNOUSERSITE", L"1");
    SetEnvironmentVariableW(L"PYTHONHOME", NULL);
    SetEnvironmentVariableW(L"PYTHONPATH", NULL);

    const wchar_t *args = skip_argv0(GetCommandLineW());
    size_t n = wcslen(py) + wcslen(app) + wcslen(args) + 64;
    wchar_t *cmd = (wchar_t *)malloc(n * sizeof(wchar_t));
    if (!cmd) return 3;
    _snwprintf(cmd, n, L"\"%ls\" -X utf8 \"%ls\"%ls%ls", py, app, *args ? L" " : L"", args);
    cmd[n - 1] = 0;

    STARTUPINFOW si; PROCESS_INFORMATION pi;
    memset(&si, 0, sizeof si); si.cb = sizeof si;
    memset(&pi, 0, sizeof pi);
    /* inherit caller's cwd so relative path arguments keep their meaning */
    BOOL ok = CreateProcessW(py, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi);
    if (!ok) {
        DWORD e = GetLastError();
        wchar_t m[MAX_PATH * 2 + 128];
        _snwprintf(m, sizeof m / sizeof m[0],
            L"无法启动千寻（错误码 %lu）。\n\n%ls", (unsigned long)e, py);
        m[sizeof m / sizeof m[0] - 1] = 0;
        fail_box(m);
        free(cmd);
        return 4;
    }
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    free(cmd);
    return 0;
}

#ifndef PORTABLE
/* ------------------------------------------------------------------ folder version */
int WINAPI wWinMain(HINSTANCE hi, HINSTANCE hp, LPWSTR cl, int sw)
{
    (void)hi; (void)hp; (void)cl; (void)sw;
    wchar_t self[MAX_PATH * 2];
    DWORD len = GetModuleFileNameW(NULL, self, MAX_PATH * 2);
    if (len == 0 || len >= MAX_PATH * 2) { fail_box(L"无法定位程序自身路径。"); return 1; }
    wchar_t base[MAX_PATH * 2];
    wcscpy(base, self);
    wchar_t *sl = wcsrchr(base, L'\\');
    if (sl) *sl = 0;
    return launch(base, self);
}

#else
/* ------------------------------------------------------------------ portable version
 * File layout:  [PE exe][payload: concatenated zlib streams][index][trailer]
 * Trailer (72 bytes, little endian):
 *   char  magic[8]  = "QXPAYLD1"
 *   u64   index_off   (absolute file offset)
 *   u64   index_size
 *   u32   count
 *   u32   reserved
 *   u8    hash[32]    sha256(payload streams + index)  (computed by pack_portable.py)
 *   char  magic2[8] = "1DLYAPXQ"
 * Index entry: u16 pathlen, path (UTF-8, '/' separated), u64 size, u64 csize, u64 offset (absolute), u32 crc32
 */
#pragma pack(push, 1)
typedef struct {
    char magic[8]; unsigned long long idx_off, idx_size; unsigned int count, reserved;
    unsigned char hash[32]; char magic2[8];
} Trailer;
#pragma pack(pop)

typedef struct { char *path; unsigned long long size, csize, off; unsigned int crc; } Entry;

static volatile LONG64 g_done_bytes;
static LONG64 g_total_bytes;
static volatile LONG g_finished, g_ok;
static wchar_t g_tmpdir[MAX_PATH * 2];
static HANDLE g_file = INVALID_HANDLE_VALUE;
static Entry *g_ent; static unsigned int g_cnt;
static wchar_t g_err[512];

static int read_at(HANDLE h, unsigned long long off, void *buf, DWORD n)
{
    LARGE_INTEGER li; li.QuadPart = (LONGLONG)off;
    if (!SetFilePointerEx(h, li, NULL, FILE_BEGIN)) return 0;
    DWORD got = 0;
    return ReadFile(h, buf, n, &got, NULL) && got == n;
}

static int mkdirs(wchar_t *p)   /* create all parent dirs of file path p (in place edit, restored) */
{
    for (wchar_t *q = p + 3; *q; q++) {
        if (*q == L'\\') {
            *q = 0;
            CreateDirectoryW(p, NULL);
            *q = L'\\';
        }
    }
    return 1;
}

static void rmtree(const wchar_t *dir)
{
    wchar_t pat[MAX_PATH * 2];
    _snwprintf(pat, MAX_PATH * 2, L"%ls\\*", dir); pat[MAX_PATH * 2 - 1] = 0;
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pat, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..")) continue;
            wchar_t sub[MAX_PATH * 2];
            _snwprintf(sub, MAX_PATH * 2, L"%ls\\%ls", dir, fd.cFileName); sub[MAX_PATH * 2 - 1] = 0;
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) rmtree(sub);
            else { SetFileAttributesW(sub, FILE_ATTRIBUTE_NORMAL); DeleteFileW(sub); }
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    RemoveDirectoryW(dir);
}

static DWORD WINAPI extract_thread(LPVOID unused)
{
    (void)unused;
    static unsigned char inbuf[1 << 16], outbuf[1 << 17];
    for (unsigned int i = 0; i < g_cnt; i++) {
        Entry *e = &g_ent[i];
        int wl = MultiByteToWideChar(CP_UTF8, 0, e->path, -1, NULL, 0);
        wchar_t *rel = (wchar_t *)malloc((wl + 1) * sizeof(wchar_t));
        MultiByteToWideChar(CP_UTF8, 0, e->path, -1, rel, wl + 1);
        for (wchar_t *q = rel; *q; q++) if (*q == L'/') *q = L'\\';
        /* reject path traversal / absolute paths */
        if (wcsstr(rel, L"..") || rel[0] == L'\\' || (rel[0] && rel[1] == L':')) {
            _snwprintf(g_err, 512, L"payload path invalid"); free(rel); return 1;
        }
        wchar_t full[MAX_PATH * 3];
        _snwprintf(full, MAX_PATH * 3, L"%ls\\%ls", g_tmpdir, rel); full[MAX_PATH * 3 - 1] = 0;
        free(rel);
        mkdirs(full);
        HANDLE out = CreateFileW(full, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (out == INVALID_HANDLE_VALUE) {
            _snwprintf(g_err, 512, L"无法写入：%ls (%lu)", full, (unsigned long)GetLastError());
            return 1;
        }
        z_stream zs; memset(&zs, 0, sizeof zs);
        if (inflateInit(&zs) != Z_OK) { CloseHandle(out); return 1; }
        unsigned long long remain = e->csize, pos = e->off;
        uLong crc = crc32(0L, Z_NULL, 0);
        int zr = Z_OK, bad = 0;
        while (zr != Z_STREAM_END) {
            if (zs.avail_in == 0) {
                DWORD n = remain > sizeof inbuf ? (DWORD)sizeof inbuf : (DWORD)remain;
                if (n == 0) { bad = 1; break; }
                if (!read_at(g_file, pos, inbuf, n)) { bad = 1; break; }
                pos += n; remain -= n; zs.next_in = inbuf; zs.avail_in = n;
            }
            zs.next_out = outbuf; zs.avail_out = sizeof outbuf;
            zr = inflate(&zs, Z_NO_FLUSH);
            if (zr != Z_OK && zr != Z_STREAM_END) { bad = 1; break; }
            DWORD have = (DWORD)(sizeof outbuf - zs.avail_out), wr = 0;
            if (have) {
                crc = crc32(crc, outbuf, have);
                if (!WriteFile(out, outbuf, have, &wr, NULL) || wr != have) { bad = 1; break; }
                InterlockedExchangeAdd64((volatile LONG64 *)&g_done_bytes, have);
            }
        }
        inflateEnd(&zs);
        CloseHandle(out);
        if (bad || zs.total_out != e->size || (unsigned int)crc != e->crc) {
            _snwprintf(g_err, 512, L"数据校验失败（程序文件可能已损坏）：%hs", e->path);
            return 1;
        }
    }
    /* completion marker lives inside the temp dir => becomes visible atomically with the rename */
    wchar_t mk[MAX_PATH * 2 + 16];
    _snwprintf(mk, MAX_PATH * 2 + 16, L"%ls\\.complete", g_tmpdir);
    HANDLE m = CreateFileW(mk, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (m == INVALID_HANDLE_VALUE) { _snwprintf(g_err, 512, L"marker"); return 1; }
    DWORD w; WriteFile(m, "ok\r\n", 4, &w, NULL); CloseHandle(m);
    InterlockedExchange(&g_ok, 1);
    return 0;
}

static HWND g_wnd, g_bar;
static LRESULT CALLBACK wp(HWND h, UINT m, WPARAM w, LPARAM l)
{
    if (m == WM_TIMER) {
        if (g_total_bytes > 0 && g_bar)
            SendMessageW(g_bar, PBM_SETPOS, (WPARAM)(g_done_bytes * 1000 / g_total_bytes), 0);
        return 0;
    }
    if (m == WM_CLOSE) return 0;           /* not cancellable: avoid half-state confusion */
    return DefWindowProcW(h, m, w, l);
}

static void show_progress(HINSTANCE hi)
{
    INITCOMMONCONTROLSEX ic = { sizeof ic, ICC_PROGRESS_CLASS }; InitCommonControlsEx(&ic);
    WNDCLASSW wc; memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = wp; wc.hInstance = hi; wc.lpszClassName = L"QXPrep";
    wc.hCursor = LoadCursorW(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.hIcon = LoadIconW(hi, MAKEINTRESOURCEW(1));
    RegisterClassW(&wc);
    NONCLIENTMETRICSW ncm; memset(&ncm, 0, sizeof ncm); ncm.cbSize = sizeof ncm;
    SystemParametersInfoW(SPI_GETNONCLIENTMETRICS, sizeof ncm, &ncm, 0);
    HFONT font = CreateFontIndirectW(&ncm.lfMessageFont);
    UINT dpi = 96; { HDC dc = GetDC(NULL); dpi = GetDeviceCaps(dc, LOGPIXELSX); ReleaseDC(NULL, dc); }
    int W = MulDiv(380, dpi, 96), H = MulDiv(118, dpi, 96);
    int sx = GetSystemMetrics(SM_CXSCREEN), sy = GetSystemMetrics(SM_CYSCREEN);
    g_wnd = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW, L"QXPrep", MSG_TITLE,
        WS_POPUP | WS_CAPTION, (sx - W) / 2, (sy - H) / 2, W, H, NULL, NULL, hi, NULL);
    RECT rc; GetClientRect(g_wnd, &rc);
    int pad = MulDiv(16, dpi, 96);
    HWND st = CreateWindowExW(0, L"STATIC", L"千寻正在首次准备运行环境…",
        WS_CHILD | WS_VISIBLE, pad, pad, rc.right - 2 * pad, MulDiv(22, dpi, 96), g_wnd, NULL, hi, NULL);
    HWND st2 = CreateWindowExW(0, L"STATIC", L"仅首次运行需要，之后将直接启动。",
        WS_CHILD | WS_VISIBLE, pad, pad + MulDiv(24, dpi, 96), rc.right - 2 * pad, MulDiv(20, dpi, 96), g_wnd, NULL, hi, NULL);
    g_bar = CreateWindowExW(0, PROGRESS_CLASSW, NULL, WS_CHILD | WS_VISIBLE | PBS_SMOOTH,
        pad, pad + MulDiv(52, dpi, 96), rc.right - 2 * pad, MulDiv(16, dpi, 96), g_wnd, NULL, hi, NULL);
    SendMessageW(g_bar, PBM_SETRANGE32, 0, 1000);
    SendMessageW(st, WM_SETFONT, (WPARAM)font, TRUE);
    SendMessageW(st2, WM_SETFONT, (WPARAM)font, TRUE);
    ShowWindow(g_wnd, SW_SHOWNOACTIVATE);
    SetTimer(g_wnd, 1, 80, NULL);
}

static int hexval(const unsigned char *h, wchar_t *out12)
{
    static const wchar_t *hx = L"0123456789abcdef";
    for (int i = 0; i < 6; i++) { out12[2 * i] = hx[h[i] >> 4]; out12[2 * i + 1] = hx[h[i] & 15]; }
    out12[12] = 0; return 1;
}

int WINAPI wWinMain(HINSTANCE hi, HINSTANCE hp, LPWSTR cl, int sw)
{
    (void)hp; (void)cl; (void)sw;
    wchar_t self[MAX_PATH * 2];
    DWORD len = GetModuleFileNameW(NULL, self, MAX_PATH * 2);
    if (len == 0 || len >= MAX_PATH * 2) { fail_box(L"无法定位程序自身路径。"); return 1; }

    g_file = CreateFileW(self, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (g_file == INVALID_HANDLE_VALUE) { fail_box(L"无法读取程序自身。"); return 1; }
    LARGE_INTEGER fsz; GetFileSizeEx(g_file, &fsz);
    Trailer tr;
    if (fsz.QuadPart < (LONGLONG)sizeof tr || !read_at(g_file, (unsigned long long)fsz.QuadPart - sizeof tr, &tr, sizeof tr) ||
        memcmp(tr.magic, "QXPAYLD1", 8) || memcmp(tr.magic2, "1DLYAPXQ", 8)) {
        fail_box(L"单文件版内置的运行环境不完整，请重新下载。");
        return 1;
    }
    wchar_t h12[16]; hexval(tr.hash, h12);

    wchar_t root[MAX_PATH * 2], target[MAX_PATH * 2], marker[MAX_PATH * 2 + 16];
    DWORD el = GetEnvironmentVariableW(L"LOCALAPPDATA", root, MAX_PATH);
    if (el == 0 || el >= MAX_PATH) {
        wchar_t tmp[MAX_PATH];
        if (!GetTempPathW(MAX_PATH, tmp)) { fail_box(L"找不到 LOCALAPPDATA。"); return 1; }
        _snwprintf(root, MAX_PATH * 2, L"%ls", tmp);
        size_t l = wcslen(root); if (l && root[l - 1] == L'\\') root[l - 1] = 0;
    }
    /* %LOCALAPPDATA%\QianXun */
    wcscat(root, L"\\QianXun");
    CreateDirectoryW(root, NULL);
    _snwprintf(target, MAX_PATH * 2, L"%ls\\rt-%ls", root, h12);
    _snwprintf(marker, MAX_PATH * 2 + 16, L"%ls\\.complete", target);

    if (!exists_file(marker)) {
        /* read index */
        if (tr.idx_size > (1ULL << 28) || tr.idx_off + tr.idx_size > (unsigned long long)fsz.QuadPart) { fail_box(L"payload index invalid"); return 1; }
        unsigned char *idx = (unsigned char *)malloc((size_t)tr.idx_size);
        if (!idx || !read_at(g_file, tr.idx_off, idx, (DWORD)tr.idx_size)) { fail_box(L"payload index unreadable"); return 1; }
        g_cnt = tr.count; g_ent = (Entry *)calloc(g_cnt, sizeof(Entry));
        unsigned char *p = idx, *end = idx + tr.idx_size;
        for (unsigned int i = 0; i < g_cnt; i++) {
            if (p + 2 > end) { fail_box(L"payload index corrupt"); return 1; }
            unsigned short pl = *(unsigned short *)p; p += 2;
            if (p + pl + 28 > end) { fail_box(L"payload index corrupt"); return 1; }
            g_ent[i].path = (char *)malloc(pl + 1); memcpy(g_ent[i].path, p, pl); g_ent[i].path[pl] = 0; p += pl;
            memcpy(&g_ent[i].size, p, 8); memcpy(&g_ent[i].csize, p + 8, 8); memcpy(&g_ent[i].off, p + 16, 8);
            memcpy(&g_ent[i].crc, p + 24, 4); p += 28;
            g_total_bytes += (LONG64)g_ent[i].size;
        }
        _snwprintf(g_tmpdir, MAX_PATH * 2, L"%ls\\tmp-%ls-%lu-%lu", root, h12, GetCurrentProcessId(), GetTickCount());
        rmtree(g_tmpdir);
        if (!CreateDirectoryW(g_tmpdir, NULL)) { fail_box(L"无法创建临时目录。"); return 1; }

        HANDLE th = CreateThread(NULL, 0, extract_thread, NULL, 0, NULL);
        DWORD wr = WaitForSingleObject(th, 500);
        if (wr == WAIT_TIMEOUT) {
            show_progress(hi);
            for (;;) {
                DWORD r = MsgWaitForMultipleObjects(1, &th, FALSE, INFINITE, QS_ALLINPUT);
                if (r == WAIT_OBJECT_0) break;
                MSG msg;
                while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
            }
            DestroyWindow(g_wnd);
        }
        CloseHandle(th);

        if (!g_ok) {
            rmtree(g_tmpdir);
            wchar_t m[700];
            _snwprintf(m, 700, L"准备运行环境失败。\n\n%ls", g_err);
            fail_box(m);
            return 1;
        }
        /* atomic publish; handle races */
        if (!MoveFileExW(g_tmpdir, target, 0)) {
            if (exists_file(marker)) {
                rmtree(g_tmpdir);                       /* another instance won the race */
            } else {
                /* target exists but incomplete (stale): move it aside, retry once */
                wchar_t stale[MAX_PATH * 2];
                _snwprintf(stale, MAX_PATH * 2, L"%ls\\stale-%lu-%lu", root, GetCurrentProcessId(), GetTickCount());
                MoveFileExW(target, stale, 0);
                if (!MoveFileExW(g_tmpdir, target, 0) && !exists_file(marker)) {
                    wchar_t m[600];
                    _snwprintf(m, 600, L"无法完成运行环境准备（错误码 %lu）。", (unsigned long)GetLastError());
                    rmtree(g_tmpdir);
                    fail_box(m);
                    return 1;
                }
                rmtree(g_tmpdir);                       /* harmless if already renamed away */
                rmtree(stale);
            }
        }
    }
    CloseHandle(g_file);
    return launch(target, self);
}
#endif
