// 千寻 —— 配置读写（config.ini，UTF-8，key=value；列表以 | 分隔，| 不会出现在 Windows 路径中）
#include "app.h"
#include "textutil.h"
#include <cstdio>
#include <cwchar>
#include <cwctype>

namespace qx {

static std::wstring conf_file() { return data_dir() + L"\\config.ini"; }

static std::vector<std::wstring> split_list(const std::wstring& v) {
    std::vector<std::wstring> r;
    size_t s = 0;
    while (s <= v.size()) {
        size_t e = v.find(L'|', s);
        std::wstring x = py_strip(v.substr(s, e == std::wstring::npos ? std::wstring::npos : e - s));
        if (!x.empty()) r.push_back(x);
        if (e == std::wstring::npos) break;
        s = e + 1;
    }
    return r;
}

static std::wstring join_list(const std::vector<std::wstring>& v) {
    std::wstring r;
    for (size_t i = 0; i < v.size(); i++) { if (i) r += L'|'; r += v[i]; }
    return r;
}

Config load_config() {
    Config c;
    HANDLE h = CreateFileW(conf_file().c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return c;
    std::string data;
    char buf[65536];
    DWORD n;
    while (ReadFile(h, buf, sizeof buf, &n, nullptr) && n) data.append(buf, n);
    CloseHandle(h);
    if (data.size() >= 3 && (unsigned char)data[0] == 0xEF) data = data.substr(3);
    std::wstring text = from_utf8(data);
    size_t s = 0;
    while (s < text.size()) {
        size_t e = text.find(L'\n', s);
        std::wstring line = text.substr(s, e == std::wstring::npos ? std::wstring::npos : e - s);
        s = e == std::wstring::npos ? text.size() : e + 1;
        if (!line.empty() && line.back() == L'\r') line.pop_back();
        size_t eq = line.find(L'=');
        if (eq == std::wstring::npos || line[0] == L'#' || line[0] == L';') continue;
        std::wstring k = py_strip(line.substr(0, eq)), v = line.substr(eq + 1);
        auto b = [&](bool& x) { x = py_strip(v) == L"1" || lower_w(py_strip(v)) == L"true"; };
        auto i = [&](int& x) { x = (int)wcstol(v.c_str(), nullptr, 10); };
        if (k == L"roots") c.roots = split_list(v);
        else if (k == L"excludes") c.excludes = split_list(v);
        else if (k == L"index_network") b(c.index_network);
        else if (k == L"index_removable") b(c.index_removable);
        else if (k == L"close_to_tray") b(c.close_to_tray);
        else if (k == L"case") b(c.case_);
        else if (k == L"whole_word") b(c.whole);
        else if (k == L"match_path") b(c.match_path);
        else if (k == L"regex") b(c.regex);
        else if (k == L"filter") i(c.filter);
        else if (k == L"sort_col") i(c.sort_col);
        else if (k == L"sort_desc") b(c.sort_desc);
        else if (k == L"hotkey") c.hotkey = py_strip(v);
        else if (k == L"win_x") i(c.win_x);
        else if (k == L"win_y") i(c.win_y);
        else if (k == L"win_w") i(c.win_w);
        else if (k == L"win_h") i(c.win_h);
        else if (k == L"win_max") b(c.win_max);
        else if (k == L"columns") swscanf(v.c_str(), L"%d,%d,%d,%d", &c.colw[0], &c.colw[1], &c.colw[2], &c.colw[3]);
        else if (k == L"column_order")
            swscanf(v.c_str(), L"%d,%d,%d,%d", &c.colorder[0], &c.colorder[1], &c.colorder[2], &c.colorder[3]);
    }
    if (c.filter < 0 || c.filter > 8) c.filter = 0;
    c.sort_col = ((c.sort_col % 4) + 4) % 4;
    for (int k = 0; k < 4; k++) if (c.colw[k] < 20 || c.colw[k] > 4000) c.colw[k] = Config().colw[k];
    bool seen[4] = {false, false, false, false}, okord = true;
    for (int k = 0; k < 4; k++) {
        if (c.colorder[k] < 0 || c.colorder[k] > 3 || seen[c.colorder[k]]) okord = false;
        else seen[c.colorder[k]] = true;
    }
    if (!okord) for (int k = 0; k < 4; k++) c.colorder[k] = k;
    return c;
}

bool save_config(const Config& c) {
    std::wstring t;
    auto B = [](bool x) { return x ? L"1" : L"0"; };
    t += L"# 千寻 QianXun 配置（UTF-8）\r\n";
    t += L"roots=" + join_list(c.roots) + L"\r\n";
    t += L"excludes=" + join_list(c.excludes) + L"\r\n";
    t += fmt_w(L"index_network=%ls\r\nindex_removable=%ls\r\nclose_to_tray=%ls\r\n", B(c.index_network),
               B(c.index_removable), B(c.close_to_tray));
    t += fmt_w(L"case=%ls\r\nwhole_word=%ls\r\nmatch_path=%ls\r\nregex=%ls\r\n", B(c.case_), B(c.whole), B(c.match_path),
               B(c.regex));
    t += fmt_w(L"filter=%d\r\nsort_col=%d\r\nsort_desc=%ls\r\n", c.filter, c.sort_col, B(c.sort_desc));
    t += L"hotkey=" + c.hotkey + L"\r\n";
    t += fmt_w(L"win_x=%d\r\nwin_y=%d\r\nwin_w=%d\r\nwin_h=%d\r\nwin_max=%ls\r\n", c.win_x, c.win_y, c.win_w, c.win_h,
               B(c.win_max));
    t += fmt_w(L"columns=%d,%d,%d,%d\r\n", c.colw[0], c.colw[1], c.colw[2], c.colw[3]);
    t += fmt_w(L"column_order=%d,%d,%d,%d\r\n", c.colorder[0], c.colorder[1], c.colorder[2], c.colorder[3]);
    std::string u = "\xEF\xBB\xBF" + to_utf8(t);
    std::wstring fn = conf_file(), tmp = fn + L".tmp";
    HANDLE h = CreateFileW(tmp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) { log_line(L"save_config: %ls", last_error_text(GetLastError()).c_str()); return false; }
    DWORD w;
    BOOL ok = WriteFile(h, u.data(), (DWORD)u.size(), &w, nullptr) && w == u.size();
    CloseHandle(h);
    if (!ok || !MoveFileExW(tmp.c_str(), fn.c_str(), MOVEFILE_REPLACE_EXISTING)) {
        log_line(L"save_config failed: %ls", last_error_text(GetLastError()).c_str());
        return false;
    }
    return true;
}

// ---------------------------------------------------------------- hotkeys (qianxun.py parse_hotkey)
struct KeyName { const wchar_t* n; UINT vk; };
static const KeyName KEYS[] = {
    {L"space", 0x20}, {L"tab", 0x09}, {L"esc", 0x1B}, {L"escape", 0x1B}, {L"ins", 0x2D}, {L"insert", 0x2D},
    {L"del", 0x2E}, {L"delete", 0x2E}, {L"home", 0x24}, {L"end", 0x23}, {L"pgup", 0x21}, {L"pageup", 0x21},
    {L"pgdown", 0x22}, {L"pagedown", 0x22}, {L"left", 0x25}, {L"up", 0x26}, {L"right", 0x27}, {L"down", 0x28},
    {L"backspace", 0x08}, {L"return", 0x0D}, {L"enter", 0x0D}, {L"pause", 0x13}, {L"print", 0x2C},
    {L"`", 0xC0}, {L"~", 0xC0}, {L"-", 0xBD}, {L"=", 0xBB}, {L"+", 0xBB}, {L"[", 0xDB}, {L"]", 0xDD}, {L";", 0xBA},
    {L"'", 0xDE}, {L",", 0xBC}, {L".", 0xBE}, {L"/", 0xBF}, {L"\\", 0xDC}};

bool parse_hotkey(const std::wstring& s0, UINT& mods, UINT& vk) {
    std::wstring s = py_strip(s0);
    if (s.empty()) return false;
    std::vector<std::wstring> parts;
    if (s.size() >= 2 && s.compare(s.size() - 2, 2, L"++") == 0) {
        std::wstring h = s.substr(0, s.size() - 2);
        size_t a = 0;
        while (true) {
            size_t e = h.find(L'+', a);
            parts.push_back(h.substr(a, e == std::wstring::npos ? std::wstring::npos : e - a));
            if (e == std::wstring::npos) break;
            a = e + 1;
        }
        parts.push_back(L"+");
    } else {
        size_t a = 0;
        while (true) {
            size_t e = s.find(L'+', a);
            parts.push_back(s.substr(a, e == std::wstring::npos ? std::wstring::npos : e - a));
            if (e == std::wstring::npos) break;
            a = e + 1;
        }
    }
    if (parts.empty() || py_strip(parts.back()).empty()) return false;
    mods = 0;
    for (size_t i = 0; i + 1 < parts.size(); i++) {
        std::wstring m = lower_w(py_strip(parts[i]));
        if (m == L"ctrl" || m == L"control") mods |= MOD_CONTROL;
        else if (m == L"alt") mods |= MOD_ALT;
        else if (m == L"shift") mods |= MOD_SHIFT;
        else if (m == L"meta" || m == L"win") mods |= MOD_WIN;
        else return false;
    }
    std::wstring k = py_strip(parts.back()), kl = lower_w(k);
    int fk = 0;
    if (kl.size() >= 2 && kl[0] == L'f') {
        bool dig = true;
        for (size_t i = 1; i < kl.size(); i++) if (!iswdigit(kl[i]) || kl[i] > L'9') dig = false;
        if (dig && kl.size() <= 3 && kl[1] != L'0') { fk = (int)wcstol(kl.c_str() + 1, nullptr, 10); if (fk > 24) fk = 0; }
    }
    if (k.size() == 1 && k[0] < 128 && iswalnum(k[0])) vk = (UINT)towupper(k[0]);
    else if (fk) vk = 0x6F + (UINT)fk;
    else {
        bool found = false;
        for (auto& kn : KEYS) if (kl == kn.n) { vk = kn.vk; found = true; break; }
        if (!found) return false;
    }
    if (!mods && !fk) return false;
    return true;
}

std::wstring hotkey_to_string(UINT mods, UINT vk) {
    std::wstring s;
    if (mods & MOD_CONTROL) s += L"Ctrl+";
    if (mods & MOD_ALT) s += L"Alt+";
    if (mods & MOD_SHIFT) s += L"Shift+";
    if (mods & MOD_WIN) s += L"Meta+";
    if ((vk >= L'A' && vk <= L'Z') || (vk >= L'0' && vk <= L'9')) s += (wchar_t)vk;
    else if (vk >= 0x70 && vk <= 0x87) s += fmt_w(L"F%u", vk - 0x6F);
    else {
        static const KeyName names[] = {{L"Space", 0x20}, {L"Tab", 0x09}, {L"Esc", 0x1B}, {L"Ins", 0x2D}, {L"Del", 0x2E},
                                        {L"Home", 0x24}, {L"End", 0x23}, {L"PgUp", 0x21}, {L"PgDown", 0x22},
                                        {L"Left", 0x25}, {L"Up", 0x26}, {L"Right", 0x27}, {L"Down", 0x28},
                                        {L"Backspace", 0x08}, {L"Return", 0x0D}, {L"Pause", 0x13}, {L"Print", 0x2C},
                                        {L"`", 0xC0}, {L"-", 0xBD}, {L"=", 0xBB}, {L"[", 0xDB}, {L"]", 0xDD},
                                        {L";", 0xBA}, {L"'", 0xDE}, {L",", 0xBC}, {L".", 0xBE}, {L"/", 0xBF},
                                        {L"\\", 0xDC}};
        bool f = false;
        for (auto& kn : names) if (kn.vk == vk) { s += kn.n; f = true; break; }
        if (!f) return L"";
    }
    return s;
}

} // namespace qx
