// 千寻 —— Windows 端公共声明：日志、数据目录、配置、路径工具。
#pragma once
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <string>
#include <vector>
#include <cstdint>

#define QX_VERSION_W L"1.2.0"
#define QX_APP_NAME L"千寻"

namespace qx {

// ---- logging / data locations (plat_win.cpp)
void log_line(const wchar_t* fmt, ...);
const std::wstring& data_dir();     // %LOCALAPPDATA%\QianXun or <exe dir>\data (portable.txt)
const std::wstring& exe_path();
std::wstring exe_dir();
bool ensure_dir(const std::wstring& d);
std::wstring last_error_text(DWORD e);
std::wstring long_path(const std::wstring& p);   // \\?\ prefix for paths ≥ 240 chars
std::wstring win_norm_path(const std::wstring& p, bool make_abs);
bool is_dir(const std::wstring& p);
bool path_exists(const std::wstring& p);
int64_t now_ft();                    // current FILETIME
double now_sec();                    // monotonic seconds (QueryPerformanceCounter)
std::wstring fmt_time(int64_t ft, bool seconds);   // local "YYYY-MM-DD HH:MM[:SS]", '' if ≤ epoch
std::wstring fmt_w(const wchar_t* fmt, ...);
std::wstring lower_w(const std::wstring& s);

// ---- configuration (config.cpp)
struct Config {
    std::vector<std::wstring> roots;      // empty = all local fixed disks
    std::vector<std::wstring> excludes;
    bool index_network = false;
    bool index_removable = true;
    bool close_to_tray = true;
    bool case_ = false, whole = false, match_path = false, regex = false;
    int filter = 0;
    int sort_col = 0;
    bool sort_desc = false;
    std::wstring hotkey = L"Ctrl+Alt+F";  // empty = disabled
    int win_x = CW_USEDEFAULT, win_y = CW_USEDEFAULT, win_w = 0, win_h = 0;   // 96-dpi units for w/h
    bool win_max = false;
    int colw[4] = {330, 460, 90, 140};    // 96-dpi units
    int colorder[4] = {0, 1, 2, 3};
};
Config load_config();
bool save_config(const Config& c);

// ---- hotkey string ⇄ (MOD_*, VK) — same accepted syntax as qianxun.py parse_hotkey
bool parse_hotkey(const std::wstring& s, UINT& mods, UINT& vk);
std::wstring hotkey_to_string(UINT mods, UINT vk);

} // namespace qx
