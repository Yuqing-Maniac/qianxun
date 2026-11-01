// 千寻 —— Windows 平台钩子与通用工具
#include "app.h"
#include "textutil.h"
#include <shlobj.h>
#include <cstdio>
#include <cstdarg>
#include <mutex>

namespace qx {

// ---------------------------------------------------------------- textutil hooks
void plat_init_tables(wchar_t* lower, uint8_t* word) {
    std::vector<wchar_t> src(65536), dst(65536);
    for (uint32_t c = 0; c < 65536; c++) src[c] = (c == 0 || (c >= 0xD800 && c < 0xE000)) ? L'a' : (wchar_t)c;
    if (LCMapStringW(0x007F /*LOCALE_INVARIANT*/, LCMAP_LOWERCASE, src.data(), 65536, dst.data(), 65536) == 65536) {
        for (uint32_t c = 1; c < 65536; c++)
            if (c < 0xD800 || c >= 0xE000) lower[c] = dst[c];
    } else {
        for (uint32_t c = 1; c < 65536; c++) {
            wchar_t ch = (wchar_t)c;
            if (c < 0xD800 || c >= 0xE000) { CharLowerBuffW(&ch, 1); lower[c] = ch; }
        }
    }
    std::vector<WORD> types(65536);
    if (GetStringTypeW(CT_CTYPE1, src.data(), 65536, types.data())) {
        for (uint32_t c = 1; c < 65536; c++)
            if (c < 0xD800 || c >= 0xE000) word[c] = (types[c] & (C1_ALPHA | C1_DIGIT)) ? 1 : 0;
    }
}

double plat_now() {
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    int64_t v = ((int64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    return (double)(v - 116444736000000000LL) / 1e7;
}

void plat_today(int& y, int& m, int& d, int& wd) {
    SYSTEMTIME st;
    GetLocalTime(&st);
    y = st.wYear; m = st.wMonth; d = st.wDay;
    wd = (st.wDayOfWeek + 6) % 7;
}

double plat_local_midnight(int y, int m, int d) {
    SYSTEMTIME lt = {}, ut = {};
    lt.wYear = (WORD)y; lt.wMonth = (WORD)m; lt.wDay = (WORD)d;
    FILETIME ft;
    if (y >= 1601 && TzSpecificLocalTimeToSystemTime(nullptr, &lt, &ut) && SystemTimeToFileTime(&ut, &ft)) {
        int64_t v = ((int64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
        return (double)(v - 116444736000000000LL) / 1e7;
    }
    // fallback (years before 1601): civil days × 86400 + current bias
    long long yy = y; unsigned mm = (unsigned)m, dd = (unsigned)d;
    yy -= mm <= 2;
    long long era = (yy >= 0 ? yy : yy - 399) / 400;
    unsigned yoe = (unsigned)(yy - era * 400);
    unsigned doy = (153 * (mm + (mm > 2 ? -3 : 9)) + 2) / 5 + dd - 1;
    unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    long long days = era * 146097 + (long long)doe - 719468;
    TIME_ZONE_INFORMATION tz;
    GetTimeZoneInformation(&tz);
    return (double)days * 86400.0 + tz.Bias * 60.0;
}

// ---------------------------------------------------------------- misc
std::wstring fmt_w(const wchar_t* fmt, ...) {
    wchar_t buf[2048];
    va_list ap;
    va_start(ap, fmt);
    int n = _vsnwprintf(buf, 2047, fmt, ap);
    va_end(ap);
    if (n < 0) n = 2047;
    buf[n] = 0;
    return buf;
}

std::wstring lower_w(const std::wstring& s) { return to_lower(s); }

const std::wstring& exe_path() {
    static std::wstring p;
    if (p.empty()) {
        std::vector<wchar_t> b(32768);
        DWORD n = GetModuleFileNameW(nullptr, b.data(), (DWORD)b.size());
        p.assign(b.data(), n);
    }
    return p;
}

std::wstring exe_dir() {
    const std::wstring& p = exe_path();
    size_t k = p.rfind(L'\\');
    return k == std::wstring::npos ? p : p.substr(0, k);
}

bool is_dir(const std::wstring& p) {
    DWORD a = GetFileAttributesW(long_path(p).c_str());
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

bool path_exists(const std::wstring& p) {
    return GetFileAttributesW(long_path(p).c_str()) != INVALID_FILE_ATTRIBUTES;
}

bool ensure_dir(const std::wstring& d) {
    if (is_dir(d)) return true;
    int r = SHCreateDirectoryExW(nullptr, d.c_str(), nullptr);
    return r == ERROR_SUCCESS || r == ERROR_ALREADY_EXISTS || r == ERROR_FILE_EXISTS;
}

const std::wstring& data_dir() {
    static std::wstring d;
    if (!d.empty()) return d;
    std::wstring ed = exe_dir();
    if (path_exists(ed + L"\\portable.txt")) {
        d = ed + L"\\data";
    } else {
        wchar_t buf[MAX_PATH * 2] = {0};
        DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", buf, MAX_PATH * 2);
        std::wstring base;
        if (n && n < MAX_PATH * 2) base = buf;
        else if (SHGetFolderPathW(nullptr, CSIDL_LOCAL_APPDATA | CSIDL_FLAG_CREATE, nullptr, 0, buf) == S_OK) base = buf;
        else if (GetTempPathW(MAX_PATH, buf)) base = buf;
        while (!base.empty() && base.back() == L'\\') base.pop_back();
        d = base + L"\\QianXun";
    }
    ensure_dir(d);
    return d;
}

static std::mutex g_log_m;
void log_line(const wchar_t* fmt, ...) {
    wchar_t buf[4096];
    va_list ap;
    va_start(ap, fmt);
    int n = _vsnwprintf(buf, 4095, fmt, ap);
    va_end(ap);
    if (n < 0) n = 4095;
    buf[n] = 0;
    SYSTEMTIME st;
    GetLocalTime(&st);
    wchar_t ts[64];
    _snwprintf(ts, 63, L"%04d-%02d-%02d %02d:%02d:%02d ", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    ts[63] = 0;
    std::string line = to_utf8(std::wstring(ts) + buf) + "\r\n";
    std::lock_guard<std::mutex> g(g_log_m);
    std::wstring fn = data_dir() + L"\\qianxun.log";
    HANDLE h = CreateFileW(fn.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    LARGE_INTEGER sz;
    if (GetFileSizeEx(h, &sz) && sz.QuadPart > 4 * 1024 * 1024) {   // rotate at 4 MB
        CloseHandle(h);
        std::wstring old = fn + L".old";
        MoveFileExW(fn.c_str(), old.c_str(), MOVEFILE_REPLACE_EXISTING);
        h = CreateFileW(fn.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, nullptr);
        if (h == INVALID_HANDLE_VALUE) return;
    }
    DWORD w;
    WriteFile(h, line.data(), (DWORD)line.size(), &w, nullptr);
    CloseHandle(h);
}

std::wstring last_error_text(DWORD e) {
    wchar_t* msg = nullptr;
    FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, nullptr, e,
                   0, (LPWSTR)&msg, 0, nullptr);
    std::wstring s = msg ? msg : fmt_w(L"错误 %lu", e);
    if (msg) LocalFree(msg);
    while (!s.empty() && (s.back() == L'\n' || s.back() == L'\r' || s.back() == L' ' || s.back() == L'.' ||
                          s.back() == L'。'))
        s.pop_back();
    return s;
}

std::wstring long_path(const std::wstring& p) {
    if (p.size() >= 240 && p.compare(0, 4, L"\\\\?\\") != 0) {
        if (p.compare(0, 2, L"\\\\") == 0) return L"\\\\?\\UNC\\" + p.substr(2);
        return L"\\\\?\\" + p;
    }
    return p;
}

// Python win_norm_path: '/'→'\'; 'c:'→'C:\'; normpath; optional abspath; upper-case drive letter.
std::wstring win_norm_path(const std::wstring& p0, bool make_abs) {
    std::wstring p = py_strip(p0);
    for (auto& c : p) if (c == L'/') c = L'\\';
    if (p.size() == 2 && p[1] == L':') p += L'\\';
    if (p.empty()) return p;
    // normpath
    std::wstring prefix, rest;
    if (p.size() >= 2 && p[0] == L'\\' && p[1] == L'\\') {   // UNC: keep \\server\share
        size_t a = p.find(L'\\', 2);
        size_t b = a == std::wstring::npos ? std::wstring::npos : p.find(L'\\', a + 1);
        prefix = b == std::wstring::npos ? p : p.substr(0, b);
        rest = b == std::wstring::npos ? L"" : p.substr(b);
        prefix += L'\\';
    } else if (p.size() >= 2 && p[1] == L':') {
        prefix = p.substr(0, 2);
        rest = p.substr(2);
        if (!rest.empty() && rest[0] == L'\\') prefix += L'\\';
    } else if (p[0] == L'\\') {
        prefix = L"\\";
        rest = p;
    } else {
        rest = p;
    }
    std::vector<std::wstring> parts;
    size_t s = 0;
    while (s <= rest.size()) {
        size_t e = rest.find(L'\\', s);
        std::wstring comp = rest.substr(s, e == std::wstring::npos ? std::wstring::npos : e - s);
        if (comp.empty() || comp == L".") {
        } else if (comp == L"..") {
            if (!parts.empty() && parts.back() != L"..") parts.pop_back();
            else if (prefix.empty() || prefix.back() != L'\\') parts.push_back(comp);
        } else parts.push_back(comp);
        if (e == std::wstring::npos) break;
        s = e + 1;
    }
    std::wstring r = prefix;
    for (size_t i = 0; i < parts.size(); i++) {
        if (i) r += L'\\';
        r += parts[i];
    }
    if (r.empty()) r = L".";
    bool absolute = (r.size() >= 3 && r[1] == L':' && r[2] == L'\\') || (r.size() >= 2 && r[0] == L'\\' && r[1] == L'\\');
    if (make_abs && !absolute) {
        std::vector<wchar_t> b(32768);
        DWORD n = GetFullPathNameW(r.c_str(), (DWORD)b.size(), b.data(), nullptr);
        if (n && n < b.size()) r.assign(b.data(), n);
        if (r.size() > 3 && r.back() == L'\\') r.pop_back();
    }
    if (r.size() >= 2 && r[1] == L':' && r[0] >= L'a' && r[0] <= L'z') r[0] = (wchar_t)(r[0] - 32);
    return r;
}

int64_t now_ft() {
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    return ((int64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
}

double now_sec() {
    static LARGE_INTEGER f = {};
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    LARGE_INTEGER c;
    QueryPerformanceCounter(&c);
    return (double)c.QuadPart / (double)f.QuadPart;
}

std::wstring fmt_time(int64_t ft, bool seconds) {
    if (ft <= 116444736000000000LL) return L"";
    FILETIME u;
    u.dwLowDateTime = (DWORD)ft;
    u.dwHighDateTime = (DWORD)(ft >> 32);
    SYSTEMTIME ust, st;
    if (!FileTimeToSystemTime(&u, &ust) || !SystemTimeToTzSpecificLocalTime(nullptr, &ust, &st)) return L"";
    if (seconds) return fmt_w(L"%04d-%02d-%02d %02d:%02d:%02d", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    return fmt_w(L"%04d-%02d-%02d %02d:%02d", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute);
}

} // namespace qx
