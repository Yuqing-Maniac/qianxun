// 千寻 —— 主窗口：搜索框＋筛选下拉、虚拟 ListView（自绘高亮）、状态栏、菜单、快捷键、托盘、全局热键。
// 行为与中文文案对照 qianxun.py 的 MainWindow。
#include "ui.h"
#include "textutil.h"
#include <windowsx.h>
#include <shellapi.h>
#include <shlobj.h>
#include <uxtheme.h>
#include <vssym32.h>
#include <dbt.h>
#include <algorithm>

namespace qx {

App g;

enum {
    ID_EDIT = 100, ID_COMBO, ID_LIST, ID_STATUS,
    IDM_EXPORT = 1000, IDM_QUIT, IDM_CASE, IDM_WHOLE, IDM_PATH, IDM_REGEX, IDM_FOCUS, IDM_OPTIONS, IDM_REFRESH,
    IDM_REBUILD, IDM_SHORTCUT, IDM_LOGDIR, IDM_HELP, IDM_ABOUT,
    IDM_OPEN = 1100, IDM_OPENDIR, IDM_TERMINAL, IDM_COPY, IDM_COPYPATH, IDM_COPYNAME, IDM_COPYDIR, IDM_RENAME,
    IDM_TRASH, IDM_PROPS, IDM_SELALL,
    IDM_TRAY_SHOW = 1200, IDM_TRAY_QUIT,
};
enum { T_SEARCH = 1, T_POLL, T_MSG, T_SELCOUNT };
static const UINT HOTKEY_ID = 0xA51;

static HMENU g_menu = nullptr;
static HTHEME g_theme = nullptr;
static int g_pending_open = 0;      // 1 = open, 2 = open folder, after the in-flight search finishes
static HWND g_last_focus = nullptr;
static bool g_debounce = false;     // typed text waiting for the 70 ms debounce timer

// ================================================================ search service
void SearchService::start(HWND target) {
    target_ = target;
    th_ = std::thread([this] { loop(); });
}

void SearchService::request(const SearchReq& r) {
    {
        std::lock_guard<std::mutex> l(m_);
        req_ = r;
        has_ = true;
        latest_ = r.seq;
    }
    cv_.notify_one();
}

void SearchService::stop() {
    {
        std::lock_guard<std::mutex> l(m_);
        stop_ = true;
        latest_ = ~0ULL;
    }
    cv_.notify_one();
    if (th_.joinable()) th_.join();
}

void SearchService::loop() {
    Searcher S(idx_, pool_);
    while (true) {
        SearchReq r;
        {
            std::unique_lock<std::mutex> l(m_);
            cv_.wait(l, [&] { return has_ || stop_; });
            if (stop_) return;
            r = req_;
            has_ = false;
        }
        std::unique_ptr<SearchRes> res(new SearchRes());
        res->seq = r.seq;
        res->keep_view = r.keep_view;
        double t0 = now_sec();
        std::wstring extra = FILTER_EXPR[r.filter];
        Query q(r.text, r.opts, extra);
        CancelFn cancel = [this, &r] { return latest_.load() != r.seq; };
        bool ok;
        {
            ReadGuard gd(idx_.lock);
            res->gen = idx_.gen.load();
            res->version = idx_.version.load();
            res->struct_version = idx_.struct_version.load();
            S.case_ = r.opts.case_;
            ok = S.run(q, extra, res->rows, cancel);
            if (ok) ok = S.sort_rows(res->rows, r.sort_col, r.sort_desc, &res->unsorted, cancel);
        }
        if (!ok || latest_.load() != r.seq) continue;   // superseded
        res->highlights = q.highlights;
        res->error = q.error;
        res->regex = r.opts.regex;
        res->stat_query = r.sort_col >= 2 || q.uses_stats();
        res->ms = (now_sec() - t0) * 1000;
        if (PostMessageW(target_, WM_APP_RESULT, 0, (LPARAM)res.get())) res.release();
    }
}

// ================================================================ fonts / dpi
typedef UINT(WINAPI* GetDpiForWindow_t)(HWND);
typedef BOOL(WINAPI* SPIForDpi_t)(UINT, UINT, PVOID, UINT, UINT);

static int window_dpi(HWND h) {
    static GetDpiForWindow_t f = (GetDpiForWindow_t)GetProcAddress(GetModuleHandleW(L"user32.dll"), "GetDpiForWindow");
    if (f && h) {
        UINT d = f(h);
        if (d) return (int)d;
    }
    HDC dc = GetDC(nullptr);
    int d = GetDeviceCaps(dc, LOGPIXELSY);
    ReleaseDC(nullptr, dc);
    return d > 0 ? d : 96;
}

static int system_dpi() {
    HDC dc = GetDC(nullptr);
    int d = GetDeviceCaps(dc, LOGPIXELSY);
    ReleaseDC(nullptr, dc);
    return d > 0 ? d : 96;
}

static void make_fonts() {
    NONCLIENTMETRICSW ncm = {};
    ncm.cbSize = sizeof ncm;
    static SPIForDpi_t f = (SPIForDpi_t)GetProcAddress(GetModuleHandleW(L"user32.dll"), "SystemParametersInfoForDpi");
    LOGFONTW lf;
    if (f && f(SPI_GETNONCLIENTMETRICS, sizeof ncm, &ncm, 0, (UINT)g.dpi)) {
        lf = ncm.lfMessageFont;
    } else {
        SystemParametersInfoW(SPI_GETNONCLIENTMETRICS, sizeof ncm, &ncm, 0);
        lf = ncm.lfMessageFont;
        lf.lfHeight = MulDiv(lf.lfHeight, g.dpi, system_dpi());
    }
    // at least 9 pt (Python: max(9.0, app font size))
    int min_h = -MulDiv(9, g.dpi, 72);
    if (lf.lfHeight > min_h) lf.lfHeight = min_h;
    lf.lfQuality = CLEARTYPE_QUALITY;
    if (g.font) DeleteObject(g.font);
    if (g.font_bold) DeleteObject(g.font_bold);
    if (g.font_big) DeleteObject(g.font_big);
    g.font = CreateFontIndirectW(&lf);
    LOGFONTW b = lf;
    b.lfWeight = FW_BOLD;
    g.font_bold = CreateFontIndirectW(&b);
    LOGFONTW big = lf;
    big.lfHeight = (LONG)(lf.lfHeight * 1.15);
    g.font_big = CreateFontIndirectW(&big);
}

static int font_height(HFONT f) {
    HDC dc = GetDC(g.hwnd);
    HGDIOBJ o = SelectObject(dc, f);
    TEXTMETRICW tm;
    GetTextMetricsW(dc, &tm);
    SelectObject(dc, o);
    ReleaseDC(g.hwnd, dc);
    return tm.tmHeight;
}

static int text_width(HFONT f, const std::wstring& s) {
    HDC dc = GetDC(g.hwnd);
    HGDIOBJ o = SelectObject(dc, f);
    SIZE sz = {0, 0};
    GetTextExtentPoint32W(dc, s.c_str(), (int)s.size(), &sz);
    SelectObject(dc, o);
    ReleaseDC(g.hwnd, dc);
    return sz.cx;
}

static void apply_row_height() {
    g.row_h = std::max(S(22), font_height(g.font) + S(6));
    if (g.row_il) ImageList_Destroy(g.row_il);
    g.row_il = ImageList_Create(1, g.row_h, ILC_COLOR32, 1, 1);
    ListView_SetImageList(g.list, g.row_il, LVSIL_SMALL);
}

static void layout() {
    if (!g.hwnd) return;
    RECT rc;
    GetClientRect(g.hwnd, &rc);
    SendMessageW(g.status, WM_SIZE, 0, 0);
    RECT sr;
    GetWindowRect(g.status, &sr);
    int sh = sr.bottom - sr.top;
    int m = S(6);
    int eh = std::max(S(30), font_height(g.font_big) + S(12));
    int cw = std::max(S(120), text_width(g.font, L"可执行/脚本") + S(40));
    MoveWindow(g.edit, m, m, rc.right - 3 * m - cw, eh, TRUE);
    SendMessageW(g.combo, CB_SETITEMHEIGHT, (WPARAM)-1, eh - S(6));
    MoveWindow(g.combo, rc.right - m - cw, m, cw, S(300), TRUE);
    int top = m + eh + m;
    MoveWindow(g.list, m, top, rc.right - 2 * m, std::max(0, (int)rc.bottom - sh - top), TRUE);
    // status parts: left = count (stretch), right = state text
    int w2 = text_width(g.font, g.state_text) + S(36);
    int parts[2] = {std::max(S(100), (int)rc.right - w2), -1};
    SendMessageW(g.status, SB_SETPARTS, 2, (LPARAM)parts);
}

static void set_fonts() {
    SendMessageW(g.edit, WM_SETFONT, (WPARAM)g.font_big, TRUE);
    SendMessageW(g.combo, WM_SETFONT, (WPARAM)g.font, TRUE);
    SendMessageW(g.list, WM_SETFONT, (WPARAM)g.font, TRUE);
    SendMessageW(g.status, WM_SETFONT, (WPARAM)g.font, TRUE);
    SendMessageW(g.edit, EM_SETMARGINS, EC_LEFTMARGIN | EC_RIGHTMARGIN, MAKELPARAM(S(4), S(4)));
    apply_row_height();
}

// ================================================================ helpers
static void set_status_text(int part, const std::wstring& s) {
    SendMessageW(g.status, SB_SETTEXTW, (WPARAM)part, (LPARAM)s.c_str());
}

void show_message(const std::wstring& s, UINT ms) {
    g.msg_active = true;
    set_status_text(0, s);
    SetTimer(g.hwnd, T_MSG, ms, nullptr);
}

void update_count() {
    if (g.msg_active) return;
    if (!g.error.empty()) { set_status_text(0, L"语法错误：" + g.error); return; }
    size_t n = g.rows.size();
    std::wstring s = fmt_thousands((long long)n) + L" 个对象";
    UINT sel = n ? ListView_GetSelectedCount(g.list) : 0;
    if (sel > 1) s += L"　｜　已选中 " + fmt_thousands(sel) + L" 个";
    if (g.rows_unsorted) s += L"　｜　索引建立中，结果暂未排序";
    set_status_text(0, s);
}

static std::wstring edit_text() {
    int n = GetWindowTextLengthW(g.edit);
    std::wstring s((size_t)n + 1, L'\0');
    GetWindowTextW(g.edit, &s[0], n + 1);
    s.resize((size_t)n);
    return s;
}

void do_search(bool keep_view) {
    KillTimer(g.hwnd, T_SEARCH);
    g_debounce = false;
    SearchReq r;
    r.seq = ++g.seq;
    r.text = edit_text();
    r.opts.case_ = g.cfg.case_;
    r.opts.whole = g.cfg.whole;
    r.opts.match_path = g.cfg.match_path;
    r.opts.regex = g.cfg.regex;
    r.filter = (int)SendMessageW(g.combo, CB_GETCURSEL, 0, 0);
    if (r.filter < 0 || r.filter >= FILTER_COUNT) r.filter = 0;
    r.sort_col = g.sort_col;
    r.sort_desc = g.sort_desc;
    r.keep_view = keep_view;
    g.search_pending = true;
    g.search->request(r);
}

static uint32_t row_entry(int row) {
    if (row < 0 || (size_t)row >= g.rows.size() || g.rows_gen != g.idx->gen.load()) return NONE;
    return g.rows[(size_t)row];
}

std::vector<uint32_t> selected_entries() {
    std::vector<int> rows;
    int i = -1;
    while ((i = ListView_GetNextItem(g.list, i, LVNI_SELECTED)) >= 0) rows.push_back(i);
    if (rows.empty()) {
        int f = ListView_GetNextItem(g.list, -1, LVNI_FOCUSED);
        if (f >= 0) rows.push_back(f);
    }
    std::vector<uint32_t> out;
    ReadGuard gd(g.idx->lock);
    for (int r : rows) {
        uint32_t e = row_entry(r);
        if (e != NONE && e < g.idx->size() && g.idx->entries[e].kind != K_DEAD) out.push_back(e);
    }
    return out;
}

std::vector<std::wstring> selected_paths() {
    std::vector<uint32_t> es = selected_entries();
    std::vector<std::wstring> out;
    ReadGuard gd(g.idx->lock);
    for (uint32_t e : es) {
        if (e >= g.idx->size() || g.idx->entries[e].kind == K_DEAD) continue;
        std::wstring p = g.idx->fullpath(e);
        if (!p.empty()) out.push_back(p);
    }
    return out;
}

static void focus_search() {
    SetFocus(g.edit);
    SendMessageW(g.edit, EM_SETSEL, 0, -1);
}

static void focus_results() {
    SetFocus(g.list);
    if (!g.rows.empty() && ListView_GetNextItem(g.list, -1, LVNI_FOCUSED) < 0) {
        ListView_SetItemState(g.list, 0, LVIS_SELECTED | LVIS_FOCUSED, LVIS_SELECTED | LVIS_FOCUSED);
        ListView_EnsureVisible(g.list, 0, FALSE);
    }
}

// ================================================================ actions
static void act_open() {
    auto ps = selected_paths();
    if (ps.size() > 10 &&
        msg_box(g.hwnd, fmt_w(L"确定同时打开 %d 个项目吗？", (int)ps.size()), MB_YESNO | MB_ICONQUESTION) != IDYES)
        return;
    for (auto& p : ps) open_path(p);
}

static void act_open_folder() {
    auto ps = selected_paths();
    for (size_t i = 0; i < ps.size() && i < 10; i++) show_in_folder(ps[i]);
}

static void act_terminal() {
    auto ps = selected_paths();
    if (ps.empty()) return;
    std::wstring d = ps[0], nm;
    if (!is_dir(d)) { std::wstring par; split_path(ps[0], par, nm); d = par; }
    if (!open_terminal(d)) msg_box(g.hwnd, L"未能打开终端。", MB_ICONINFORMATION);
}

static void act_copy() {
    auto ps = selected_paths();
    if (ps.empty()) return;
    if (copy_files_to_clipboard(g.hwnd, ps)) show_message(fmt_w(L"已复制 %d 个项目，可在文件管理器中粘贴", (int)ps.size()), 3000);
}

static std::wstring join_lines(const std::vector<std::wstring>& v) {
    std::wstring s;
    for (size_t i = 0; i < v.size(); i++) { if (i) s += L"\r\n"; s += v[i]; }
    return s;
}

static void act_copy_path() {
    auto ps = selected_paths();
    if (ps.empty()) return;
    if (copy_text_to_clipboard(g.hwnd, join_lines(ps))) show_message(L"已复制路径", 2000);
}

static void act_copy_name(bool dir) {
    auto ps = selected_paths();
    if (ps.empty()) return;
    std::vector<std::wstring> v;
    for (auto& p : ps) {
        std::wstring par, nm;
        split_path(p, par, nm);
        v.push_back(dir ? par : nm);
    }
    copy_text_to_clipboard(g.hwnd, join_lines(v));
}

static void act_rename() {
    auto es = selected_entries();
    if (es.size() != 1) return;
    std::wstring old, name;
    {
        ReadGuard gd(g.idx->lock);
        old = g.idx->fullpath(es[0]);
        name = g.idx->name_str(es[0]);
    }
    if (old.empty()) return;
    std::wstring nw = name;
    if (!input_box(g.hwnd, L"重命名", L"新名称：", nw) || nw.empty() || nw == name) return;
    if (nw == L"." || nw == L"..") { msg_box(g.hwnd, L"名称无效。", MB_ICONWARNING); return; }
    for (wchar_t c : nw) {
        if (wcschr(L"\\/:*?\"<>|", c) || c < 0x20) {
            msg_box(g.hwnd, L"名称中不能包含下列字符：\\ / : * ? \" < > |", MB_ICONWARNING);
            return;
        }
    }
    if (nw.back() == L' ' || nw.back() == L'.') { msg_box(g.hwnd, L"名称不能以空格或句点结尾。", MB_ICONWARNING); return; }
    std::wstring par, nm;
    split_path(old, par, nm);
    std::wstring dst = join_path(par, nw);
    bool same = to_lower(dst) == to_lower(old);   // case-only rename on a case-insensitive FS
    if (!same && path_exists(dst)) { msg_box(g.hwnd, L"同名项目已存在。", MB_ICONWARNING); return; }
    if (!MoveFileW(long_path(old).c_str(), long_path(dst).c_str())) {
        msg_box(g.hwnd, L"重命名失败：" + last_error_text(GetLastError()), MB_ICONWARNING);
        return;
    }
    g.engine->post_refresh_path(par);
}

static void act_trash() {
    auto ps = selected_paths();
    if (ps.empty()) return;
    std::wstring par, nm;
    split_path(ps[0], par, nm);
    std::wstring msg = ps.size() == 1 ? L"确定将“" + nm + L"”移到回收站吗？" : fmt_w(L"确定将这 %d 个项目移到回收站吗？", (int)ps.size());
    std::vector<std::wstring> bad;
    for (auto& p : ps) if (drive_type_of(p) != DRIVE_FIXED) bad.push_back(p);
    if (!bad.empty()) {
        // removable / network drives have no recycle bin: the shell would delete permanently
        std::wstring t = L"以下项目位于可移动磁盘或网络位置，不支持回收站，请在资源管理器中处理：";
        for (size_t i = 0; i < bad.size() && i < 10; i++) t += L"\n" + bad[i];
        msg_box(g.hwnd, t, MB_ICONWARNING);
        return;
    }
    if (msg_box(g.hwnd, msg, MB_YESNO | MB_ICONQUESTION) != IDYES) return;
    std::vector<std::wstring> failed;
    recycle_paths(g.hwnd, ps, failed);
    for (auto& p : ps) {
        std::wstring pp, n2;
        split_path(p, pp, n2);
        g.engine->post_refresh_path(pp);
    }
    if (!failed.empty()) {
        std::wstring t = L"以下项目未能移到回收站：";
        for (size_t i = 0; i < failed.size() && i < 10; i++) t += L"\n" + failed[i];
        msg_box(g.hwnd, t, MB_ICONWARNING);
    }
}

static void act_props() {
    auto ps = selected_paths();
    if (ps.empty()) return;
    const std::wstring& p = ps[0];
    if (show_properties(g.hwnd, p)) return;
    WIN32_FILE_ATTRIBUTE_DATA a;
    if (!GetFileAttributesExW(long_path(p).c_str(), GetFileExInfoStandard, &a)) {
        msg_box(g.hwnd, last_error_text(GetLastError()), MB_ICONWARNING);
        return;
    }
    auto ft = [](const FILETIME& f) { return fmt_time(((int64_t)f.dwHighDateTime << 32) | f.dwLowDateTime, true); };
    int64_t sz = (int64_t)(((uint64_t)a.nFileSizeHigh << 32) | a.nFileSizeLow);
    std::wstring flags;
    struct { DWORD b; const wchar_t* n; } fl[] = {{0x1, L"只读"}, {0x2, L"隐藏"}, {0x4, L"系统"}, {0x20, L"存档"},
                                                {0x400, L"重解析点"}, {0x800, L"压缩"}, {0x4000, L"加密"}};
    for (auto& f : fl) if (a.dwFileAttributes & f.b) { if (!flags.empty()) flags += L"　"; flags += f.n; }
    if (flags.empty()) flags = L"无";
    std::wstring par, nm;
    split_path(p, par, nm);
    bool d = (a.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
    std::wstring t = L"名称：" + nm + L"\n位置：" + par + L"\n类型：" + (d ? L"文件夹" : L"文件") + L"\n大小：" +
                     human_size(sz) + L"（" + fmt_thousands(sz) + L" 字节）\n修改时间：" + ft(a.ftLastWriteTime) +
                     L"\n访问时间：" + ft(a.ftLastAccessTime) + L"\n创建时间：" + ft(a.ftCreationTime) + L"\n属性：" + flags;
    msg_box(g.hwnd, t, MB_ICONINFORMATION, L"属性");
}

static std::wstring csv_field(const std::wstring& s) {
    if (s.find_first_of(L",\"\r\n") == std::wstring::npos) return s;
    std::wstring r = L"\"";
    for (wchar_t c : s) { if (c == L'"') r += L"\"\""; else r += c; }
    return r + L"\"";
}

static void export_csv() {
    std::wstring fn = pick_save_file(g.hwnd, L"导出搜索结果", L"千寻搜索结果.csv");
    if (fn.empty()) return;
    HCURSOR old = SetCursor(LoadCursor(nullptr, IDC_WAIT));
    std::string out = "\xEF\xBB\xBF";
    size_t n = 0;
    {
        ReadGuard gd(g.idx->lock);
        out += to_utf8(std::wstring(L"名称,路径,大小（字节）,修改时间\r\n"));
        if (g.rows_gen == g.idx->gen.load()) {
            for (uint32_t e : g.rows) {
                if (e >= g.idx->size()) continue;
                const Entry& en = g.idx->entries[e];
                if (en.kind == K_DEAD) continue;
                std::wstring line = csv_field(g.idx->name_str(e)) + L"," + csv_field(g.idx->dirpath(e)) + L"," +
                                    (en.kind == K_DIR ? L"" : std::to_wstring(en.size)) + L"," + fmt_time(en.mtime, true) + L"\r\n";
                out += to_utf8(line);
                n++;
            }
        }
    }
    HANDLE h = CreateFileW(fn.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    DWORD w = 0;
    bool ok = h != INVALID_HANDLE_VALUE && WriteFile(h, out.data(), (DWORD)out.size(), &w, nullptr) && w == out.size();
    DWORD e = GetLastError();
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    SetCursor(old);
    if (!ok) { msg_box(g.hwnd, L"导出失败：" + last_error_text(e), MB_ICONWARNING); return; }
    show_message(L"已导出 " + fmt_thousands((long long)n) + L" 条到 " + fn, 5000);
}

static void context_menu(POINT pt) {
    if (selected_entries().empty()) return;
    if (pt.x == -1 && pt.y == -1) {   // keyboard: menu at the focused row
        int f = ListView_GetNextItem(g.list, -1, LVNI_FOCUSED);
        RECT r = {};
        if (f >= 0 && ListView_GetItemRect(g.list, f, &r, LVIR_LABEL)) { pt.x = r.left + S(20); pt.y = r.bottom; }
        ClientToScreen(g.list, &pt);
    }
    if (GetKeyState(VK_SHIFT) < 0) {   // Shift+右键：系统完整右键菜单
        if (shell_context_menu(g.hwnd, selected_paths(), pt)) return;
    }
    HMENU m = CreatePopupMenu();
    AppendMenuW(m, MF_STRING, IDM_OPEN, L"打开");
    AppendMenuW(m, MF_STRING, IDM_OPENDIR, L"打开所在文件夹");
    AppendMenuW(m, MF_STRING, IDM_TERMINAL, L"在终端中打开");
    AppendMenuW(m, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(m, MF_STRING, IDM_COPY, L"复制\tCtrl+C");
    AppendMenuW(m, MF_STRING, IDM_COPYPATH, L"复制完整路径\tCtrl+Shift+C");
    AppendMenuW(m, MF_STRING, IDM_COPYNAME, L"复制文件名");
    AppendMenuW(m, MF_STRING, IDM_COPYDIR, L"复制所在目录路径");
    AppendMenuW(m, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(m, MF_STRING, IDM_RENAME, L"重命名\tF2");
    AppendMenuW(m, MF_STRING, IDM_TRASH, L"移到回收站\tDelete");
    AppendMenuW(m, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(m, MF_STRING, IDM_PROPS, L"属性\tAlt+Enter");
    SetMenuDefaultItem(m, IDM_OPEN, FALSE);
    TrackPopupMenuEx(m, TPM_RIGHTBUTTON, pt.x, pt.y, g.hwnd, nullptr);
    DestroyMenu(m);
}

static void open_options() {
    Config c = g.cfg;
    bool autostart = !autostart_get().empty();
    bool was_auto = autostart;
    if (!show_options(g.hwnd, c, autostart)) return;
    bool changed = c.roots != g.cfg.roots || c.excludes != g.cfg.excludes || c.index_removable != g.cfg.index_removable ||
                   c.index_network != g.cfg.index_network;
    bool hk_changed = c.hotkey != g.cfg.hotkey;
    g.cfg = c;
    save_config(g.cfg);
    if (autostart != was_auto && !autostart_set(autostart))
        msg_box(g.hwnd, L"设置开机自启失败：" + last_error_text(GetLastError()), MB_ICONWARNING);
    if (hk_changed) register_hotkey();
    if (changed) g.engine->post_rebuild(g.cfg);
}

static void update_menu_checks() {
    CheckMenuItem(g_menu, IDM_CASE, g.cfg.case_ ? MF_CHECKED : MF_UNCHECKED);
    CheckMenuItem(g_menu, IDM_WHOLE, g.cfg.whole ? MF_CHECKED : MF_UNCHECKED);
    CheckMenuItem(g_menu, IDM_PATH, g.cfg.match_path ? MF_CHECKED : MF_UNCHECKED);
    CheckMenuItem(g_menu, IDM_REGEX, g.cfg.regex ? MF_CHECKED : MF_UNCHECKED);
}

static void set_opt(bool& flag) {
    flag = !flag;
    update_menu_checks();
    save_config(g.cfg);
    do_search();
}

// ================================================================ tray / hotkey / window state
static void tray_add() {
    NOTIFYICONDATAW nid = {};
    nid.cbSize = sizeof nid;
    nid.hWnd = g.hwnd;
    nid.uID = 1;
    nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid.uCallbackMessage = WM_APP_TRAY;
    nid.hIcon = g.icon_small;
    wcscpy(nid.szTip, L"千寻 - 文件秒搜");
    g.tray_ok = Shell_NotifyIconW(NIM_ADD, &nid) != 0;
    if (!g.tray_ok) {   // explorer may still be starting (autostart): retry once later via TaskbarCreated
        log_line(L"tray: Shell_NotifyIcon failed");
    }
}

static void tray_remove() {
    NOTIFYICONDATAW nid = {};
    nid.cbSize = sizeof nid;
    nid.hWnd = g.hwnd;
    nid.uID = 1;
    Shell_NotifyIconW(NIM_DELETE, &nid);
    g.tray_ok = false;
}

void register_hotkey() {
    if (g.hotkey_ok) { UnregisterHotKey(g.hwnd, HOTKEY_ID); g.hotkey_ok = false; }
    if (g.cfg.hotkey.empty()) return;
    UINT mods, vk;
    if (!parse_hotkey(g.cfg.hotkey, mods, vk)) {
        show_message(L"全局快捷键“" + g.cfg.hotkey + L"”无效，请在“工具 → 选项”中重新设置。", 10000);
        return;
    }
    g.hotkey_ok = RegisterHotKey(g.hwnd, HOTKEY_ID, mods | 0x4000 /*MOD_NOREPEAT, Win7+*/, vk) != 0;
    if (!g.hotkey_ok) {
        log_line(L"RegisterHotKey %ls failed: %lu", g.cfg.hotkey.c_str(), GetLastError());
        show_message(L"全局快捷键 " + g.cfg.hotkey + L" 注册失败（可能已被其它程序占用），可在“工具 → 选项”中更换。", 15000);
    }
}

void show_raise() {
    if (IsIconic(g.hwnd)) ShowWindow(g.hwnd, SW_RESTORE);
    ShowWindow(g.hwnd, SW_SHOW);
    // SetForegroundWindow may be refused; the AttachThreadInput trick makes it reliable for hotkey/tray use
    HWND fg = GetForegroundWindow();
    DWORD ft = fg ? GetWindowThreadProcessId(fg, nullptr) : 0, me = GetCurrentThreadId();
    if (ft && ft != me) AttachThreadInput(ft, me, TRUE);
    SetForegroundWindow(g.hwnd);
    BringWindowToTop(g.hwnd);
    if (ft && ft != me) AttachThreadInput(ft, me, FALSE);
    focus_search();
}

void toggle_window() {
    if (IsWindowVisible(g.hwnd) && !IsIconic(g.hwnd) && GetForegroundWindow() == g.hwnd) ShowWindow(g.hwnd, SW_HIDE);
    else show_raise();
}

static void esc_hide() {
    if (g.tray_ok && g.cfg.close_to_tray) ShowWindow(g.hwnd, SW_HIDE);
}

void save_state() {
    WINDOWPLACEMENT wp = {};
    wp.length = sizeof wp;
    if (GetWindowPlacement(g.hwnd, &wp)) {
        g.cfg.win_x = wp.rcNormalPosition.left;
        g.cfg.win_y = wp.rcNormalPosition.top;
        g.cfg.win_w = MulDiv(wp.rcNormalPosition.right - wp.rcNormalPosition.left, 96, g.dpi);
        g.cfg.win_h = MulDiv(wp.rcNormalPosition.bottom - wp.rcNormalPosition.top, 96, g.dpi);
        g.cfg.win_max = wp.showCmd == SW_SHOWMAXIMIZED || (IsZoomed(g.hwnd) != 0);
    }
    for (int c = 0; c < 4; c++) g.cfg.colw[c] = MulDiv(ListView_GetColumnWidth(g.list, c), 96, g.dpi);
    int order[4];
    if (ListView_GetColumnOrderArray(g.list, 4, order)) for (int c = 0; c < 4; c++) g.cfg.colorder[c] = order[c];
    g.cfg.sort_col = g.sort_col;
    g.cfg.sort_desc = g.sort_desc;
    int f = (int)SendMessageW(g.combo, CB_GETCURSEL, 0, 0);
    g.cfg.filter = f >= 0 ? f : 0;
    save_config(g.cfg);
}

void quit_app() {
    if (g.quitting) return;
    g.quitting = true;
    save_state();
    ShowWindow(g.hwnd, SW_HIDE);
    tray_remove();
    if (g.hotkey_ok) UnregisterHotKey(g.hwnd, HOTKEY_ID);
    g.engine->post_quit();
    g.engine->join(15000);
    DestroyWindow(g.hwnd);
}

static void update_sort_header() {
    HWND hdr = ListView_GetHeader(g.list);
    for (int c = 0; c < 4; c++) {
        HDITEMW hi = {};
        hi.mask = HDI_FORMAT;
        Header_GetItem(hdr, c, &hi);
        hi.fmt &= ~(HDF_SORTUP | HDF_SORTDOWN);
        if (c == g.sort_col) hi.fmt |= g.sort_desc ? HDF_SORTDOWN : HDF_SORTUP;
        Header_SetItem(hdr, c, &hi);
    }
}

// ================================================================ drawing
static COLORREF blend(COLORREF a, COLORREF b, int pct_b) {
    return RGB((GetRValue(a) * (100 - pct_b) + GetRValue(b) * pct_b) / 100,
               (GetGValue(a) * (100 - pct_b) + GetGValue(b) * pct_b) / 100,
               (GetBValue(a) * (100 - pct_b) + GetBValue(b) * pct_b) / 100);
}

static void draw_highlighted(HDC dc, const std::wstring& text, RECT rc) {
    // mark matched spans (case-insensitive like the Python delegate)
    std::wstring low = to_lower(text);
    std::vector<uint8_t> mark(text.size(), 0);
    for (auto& t : g.highlights) {
        if (t.empty()) continue;
        size_t s = 0;
        while (true) {
            size_t k = low.find(t, s);
            if (k == std::wstring::npos) break;
            for (size_t j = k; j < k + t.size() && j < mark.size(); j++) mark[j] = 1;
            s = k + 1;
        }
    }
    int x = rc.left;
    size_t j = 0, n = text.size();
    while (j < n && x < rc.right) {
        uint8_t b = mark[j];
        size_t e = j;
        while (e < n && mark[e] == b) e++;
        SelectObject(dc, b ? g.font_bold : g.font);
        SIZE sz;
        GetTextExtentPoint32W(dc, text.c_str() + j, (int)(e - j), &sz);
        RECT r = {x, rc.top, rc.right, rc.bottom};
        DrawTextW(dc, text.c_str() + j, (int)(e - j), &r, DT_SINGLELINE | DT_VCENTER | DT_NOPREFIX | DT_END_ELLIPSIS);
        x += sz.cx;
        j = e;
    }
    SelectObject(dc, g.font);
}

static LRESULT on_custom_draw(NMLVCUSTOMDRAW* cd) {
    switch (cd->nmcd.dwDrawStage) {
        case CDDS_PREPAINT:
            return CDRF_NOTIFYITEMDRAW;
        case CDDS_ITEMPREPAINT: {
            int row = (int)cd->nmcd.dwItemSpec;
            HDC dc = cd->nmcd.hdc;
            RECT rb;
            if (!ListView_GetItemRect(g.list, row, &rb, LVIR_BOUNDS)) return CDRF_DODEFAULT;
            RECT cl;
            GetClientRect(g.list, &cl);
            RECT full = rb;
            full.right = std::max(rb.right, cl.right);
            bool sel = (ListView_GetItemState(g.list, row, LVIS_SELECTED) & LVIS_SELECTED) != 0;
            bool foc = GetFocus() == g.list;
            COLORREF win = GetSysColor(COLOR_WINDOW), txt = GetSysColor(COLOR_WINDOWTEXT);
            COLORREF bg = (row & 1) ? blend(win, txt, 4) : win;
            HBRUSH br = CreateSolidBrush(bg);
            FillRect(dc, &full, br);
            DeleteObject(br);
            COLORREF fg = txt;
            if (sel) {
                if (g_theme) {
                    DrawThemeBackground(g_theme, dc, LVP_LISTITEM, foc ? LISS_SELECTED : LISS_SELECTEDNOTFOCUS, &rb, nullptr);
                } else {
                    HBRUSH sb = CreateSolidBrush(GetSysColor(foc ? COLOR_HIGHLIGHT : COLOR_BTNFACE));
                    FillRect(dc, &rb, sb);
                    DeleteObject(sb);
                    if (foc) fg = GetSysColor(COLOR_HIGHLIGHTTEXT);
                }
            }
            SetBkMode(dc, TRANSPARENT);
            SetTextColor(dc, fg);
            HGDIOBJ oldf = SelectObject(dc, g.font);
            // entry data (under the read lock)
            std::wstring name, dir, size, mt;
            bool isdir = false, dead = true;
            int icon = -1;
            {
                ReadGuard gd(g.idx->lock);
                uint32_t e = row_entry(row);
                if (e != NONE && e < g.idx->size()) {
                    const Entry& en = g.idx->entries[e];
                    if (en.kind == K_DEAD) {
                        name = L"（已删除）";
                    } else {
                        dead = false;
                        isdir = en.kind == K_DIR;
                        name = g.idx->name_str(e);
                        dir = g.idx->dirpath(e);
                        size = isdir ? L"" : human_size(en.size);
                        mt = fmt_time(en.mtime, false);
                    }
                }
            }
            if (!dead) icon = sys_icon_index(name, isdir, join_path(dir, name));
            // columns in display order
            int order[4] = {0, 1, 2, 3};
            ListView_GetColumnOrderArray(g.list, 4, order);
            int x = rb.left;
            int pad = S(6);
            for (int k = 0; k < 4; k++) {
                int c = order[k];
                int w = ListView_GetColumnWidth(g.list, c);
                RECT r = {x + pad, rb.top, x + w - pad, rb.bottom};
                x += w;
                if (r.right <= r.left || r.left > cl.right) continue;
                if (c == 0) {
                    if (icon >= 0 && g.sys_il) {
                        int iw = 16, ih = 16;
                        ImageList_GetIconSize(g.sys_il, &iw, &ih);
                        ImageList_Draw(g.sys_il, icon, dc, r.left, r.top + (r.bottom - r.top - ih) / 2, ILD_TRANSPARENT);
                        r.left += iw + S(5);
                    }
                    if (r.right > r.left) {
                        if (!g.highlights.empty() && !dead) draw_highlighted(dc, name, r);
                        else DrawTextW(dc, name.c_str(), (int)name.size(), &r, DT_SINGLELINE | DT_VCENTER | DT_NOPREFIX | DT_END_ELLIPSIS);
                    }
                } else {
                    const std::wstring& s = c == 1 ? dir : (c == 2 ? size : mt);
                    UINT fl = DT_SINGLELINE | DT_VCENTER | DT_NOPREFIX | DT_END_ELLIPSIS | (c == 2 ? DT_RIGHT : 0);
                    DrawTextW(dc, s.c_str(), (int)s.size(), &r, fl);
                }
            }
            if (foc && !g_theme && (ListView_GetItemState(g.list, row, LVIS_FOCUSED) & LVIS_FOCUSED)) DrawFocusRect(dc, &rb);
            SelectObject(dc, oldf);
            return CDRF_SKIPDEFAULT;
        }
    }
    return CDRF_DODEFAULT;
}

// ================================================================ subclasses
static void cycle_focus(HWND from, bool back) {
    HWND seq[3] = {g.edit, g.combo, g.list};
    int k = 0;
    for (int i = 0; i < 3; i++) if (seq[i] == from) k = i;
    k = (k + (back ? 2 : 1)) % 3;
    if (seq[k] == g.list) focus_results(); else SetFocus(seq[k]);
}

static void delete_prev_word() {
    DWORD s = 0, e = 0;
    SendMessageW(g.edit, EM_GETSEL, (WPARAM)&s, (LPARAM)&e);
    if (s != e) { SendMessageW(g.edit, EM_REPLACESEL, TRUE, (LPARAM)L""); return; }
    std::wstring t = edit_text();
    size_t p = s;
    while (p > 0 && py_isspace(t[p - 1])) p--;
    while (p > 0 && !py_isspace(t[p - 1])) p--;
    SendMessageW(g.edit, EM_SETSEL, p, s);
    SendMessageW(g.edit, EM_REPLACESEL, TRUE, (LPARAM)L"");
}

static LRESULT CALLBACK edit_proc(HWND h, UINT m, WPARAM wp, LPARAM lp, UINT_PTR, DWORD_PTR) {
    if (m == WM_KEYDOWN) {
        bool ctrl = GetKeyState(VK_CONTROL) < 0, shift = GetKeyState(VK_SHIFT) < 0;
        switch (wp) {
            case VK_DOWN:
            case VK_NEXT:
                focus_results();
                return 0;
            case VK_RETURN:
                g_pending_open = ctrl ? 2 : 1;
                if (g.search_pending || KillTimer(g.hwnd, T_SEARCH)) {
                    do_search();   // flush: open after the fresh results arrive
                } else {
                    focus_results();
                    int a = g_pending_open;
                    g_pending_open = 0;
                    if (a == 2) act_open_folder(); else act_open();
                }
                return 0;
            case VK_ESCAPE:
                if (GetWindowTextLengthW(h) > 0) SetWindowTextW(h, L"");
                else esc_hide();
                return 0;
            case VK_TAB:
                cycle_focus(h, shift);
                return 0;
            case 'A':
                if (ctrl) { SendMessageW(h, EM_SETSEL, 0, -1); return 0; }
                break;
            case VK_BACK:
                if (ctrl) { delete_prev_word(); return 0; }
                break;
        }
    } else if (m == WM_CHAR) {
        if (wp == L'\r' || wp == L'\n' || wp == 27 || wp == 1 || wp == 127 || wp == L'\t') return 0;   // no beeps
    }
    return DefSubclassProc(h, m, wp, lp);
}

static LRESULT CALLBACK list_proc(HWND h, UINT m, WPARAM wp, LPARAM lp, UINT_PTR, DWORD_PTR) {
    if (m == WM_KEYDOWN) {
        bool ctrl = GetKeyState(VK_CONTROL) < 0, shift = GetKeyState(VK_SHIFT) < 0;
        switch (wp) {
            case VK_RETURN:
                if (ctrl) act_open_folder(); else act_open();
                return 0;
            case VK_ESCAPE:
                focus_search();
                return 0;
            case VK_UP:
                if (!shift && ListView_GetNextItem(h, -1, LVNI_FOCUSED) <= 0) { focus_search(); return 0; }
                break;
            case VK_TAB:
                cycle_focus(h, shift);
                return 0;
            case 'C':
                if (ctrl && shift) { act_copy_path(); return 0; }
                if (ctrl) { act_copy(); return 0; }
                break;
            case 'A':
                if (ctrl) { ListView_SetItemState(h, -1, LVIS_SELECTED, LVIS_SELECTED); return 0; }
                break;
            case VK_F2:
                act_rename();
                return 0;
            case VK_DELETE:
                act_trash();
                return 0;
        }
    } else if (m == WM_SYSKEYDOWN && wp == VK_RETURN) {
        act_props();
        return 0;
    } else if (m == WM_CHAR) {
        if (wp == L'\r' || wp == 27 || wp == L'\t' || (wp < 32 && GetKeyState(VK_CONTROL) < 0)) return 0;
    } else if (m == WM_SYSCHAR && wp == L'\r') {
        return 0;
    }
    return DefSubclassProc(h, m, wp, lp);
}

static LRESULT CALLBACK combo_proc(HWND h, UINT m, WPARAM wp, LPARAM lp, UINT_PTR, DWORD_PTR) {
    if (m == WM_KEYDOWN && wp == VK_TAB) { cycle_focus(h, GetKeyState(VK_SHIFT) < 0); return 0; }
    if (m == WM_CHAR && wp == L'\t') return 0;
    return DefSubclassProc(h, m, wp, lp);
}

// ================================================================ status / poll
static void on_poll() {
    EngineStatus st = g.engine->status();
    std::wstring text;
    if (st.state == L"ready") {
        std::wstring mon;
        if (!st.watcher_ok) mon = L"实时监控不可用，每 3 分钟轮询";
        else if (st.dirs && st.watched < st.dirs)
            mon = L"实时监控 " + fmt_thousands((long long)st.watched) + L"/" + fmt_thousands((long long)st.dirs) + L" 目录，其余定时轮询";
        else mon = L"实时监控已全覆盖";
        text = L"索引就绪：" + fmt_thousands(g.idx->live.load()) + L" 个文件和目录　｜　" + mon;
        if (!st.msg.empty()) text = st.msg + L"　｜　" + text;
    } else {
        text = st.msg.empty() ? L"…" : st.msg;
    }
    if (text != g.state_text) {
        g.state_text = text;
        layout();
        set_status_text(1, text);
    }
    if (!IsWindowVisible(g.hwnd) || g.search_pending) return;
    uint64_t gen = g.idx->gen.load(), ver = g.idx->version.load(), sv = g.idx->struct_version.load();
    bool timer_active = g_debounce;   // a typed query is waiting for its debounce: don't preempt it
    if (gen != g.rows_gen) {
        if (!timer_active) do_search(false);
    } else if (ver != g.last_version && sv == g.last_struct && !g.stat_query) {
        g.last_version = ver;   // only sizes/times changed: same rows, repaint
        InvalidateRect(g.list, nullptr, FALSE);
    } else if (ver != g.last_version && !timer_active) {
        double gap = (st.state == L"indexing" || st.state == L"loading") ? 4.0 : (g.rows.size() < 200000 ? 0.25 : 1.5);
        if (now_sec() - g.last_search >= gap) do_search(true);
    }
}

static void on_result(SearchRes* res) {
    std::unique_ptr<SearchRes> hold(res);
    if (res->seq != g.seq) return;   // stale
    g.search_pending = false;
    uint32_t keep_entry = NONE;
    int keep_top = 0;
    if (res->keep_view) {
        int f = ListView_GetNextItem(g.list, -1, LVNI_FOCUSED);
        keep_entry = row_entry(f);
        keep_top = ListView_GetTopIndex(g.list);
    }
    g.rows.swap(res->rows);
    g.rows_gen = res->gen;
    g.last_version = res->version;
    g.last_struct = res->struct_version;
    g.highlights = res->regex ? std::vector<std::wstring>() : res->highlights;
    g.error = res->error;
    g.rows_unsorted = res->unsorted;
    g.stat_query = res->stat_query;
    g.last_search = now_sec();
    g.search_ms = res->ms;
    SendMessageW(g.list, WM_SETREDRAW, FALSE, 0);
    ListView_SetItemState(g.list, -1, 0, LVIS_SELECTED | LVIS_FOCUSED);
    ListView_SetItemCountEx(g.list, (int)g.rows.size(), LVSICF_NOINVALIDATEALL | LVSICF_NOSCROLL);
    if (res->keep_view) {
        int top = ListView_GetTopIndex(g.list);
        if (keep_top != top) ListView_Scroll(g.list, 0, (keep_top - top) * g.row_h);
        if (keep_entry != NONE && g.rows.size() < 200000) {
            auto it = std::find(g.rows.begin(), g.rows.end(), keep_entry);
            if (it != g.rows.end()) {
                int r = (int)(it - g.rows.begin());
                ListView_SetItemState(g.list, r, LVIS_SELECTED | LVIS_FOCUSED, LVIS_SELECTED | LVIS_FOCUSED);
            }
        }
    } else if (!g.rows.empty()) {
        ListView_EnsureVisible(g.list, 0, FALSE);
    }
    SendMessageW(g.list, WM_SETREDRAW, TRUE, 0);
    InvalidateRect(g.list, nullptr, TRUE);
    update_count();
    if (g_pending_open) {
        int a = g_pending_open;
        g_pending_open = 0;
        focus_results();
        if (a == 2) act_open_folder(); else act_open();
    }
}

// ================================================================ window procedure
static void build_menu() {
    g_menu = CreateMenu();
    HMENU f = CreatePopupMenu();
    AppendMenuW(f, MF_STRING, IDM_EXPORT, L"导出搜索结果为 CSV…\tCtrl+S");
    AppendMenuW(f, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(f, MF_STRING, IDM_QUIT, L"退出\tCtrl+Q");
    AppendMenuW(g_menu, MF_POPUP, (UINT_PTR)f, L"文件(&F)");
    HMENU s = CreatePopupMenu();
    AppendMenuW(s, MF_STRING, IDM_CASE, L"区分大小写\tCtrl+I");
    AppendMenuW(s, MF_STRING, IDM_WHOLE, L"全字匹配\tCtrl+B");
    AppendMenuW(s, MF_STRING, IDM_PATH, L"匹配路径\tCtrl+U");
    AppendMenuW(s, MF_STRING, IDM_REGEX, L"正则表达式\tCtrl+R");
    AppendMenuW(s, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(s, MF_STRING, IDM_FOCUS, L"回到搜索框\tCtrl+F");
    AppendMenuW(g_menu, MF_POPUP, (UINT_PTR)s, L"搜索(&S)");
    HMENU t = CreatePopupMenu();
    AppendMenuW(t, MF_STRING, IDM_OPTIONS, L"选项…\tCtrl+P");
    AppendMenuW(t, MF_STRING, IDM_REFRESH, L"立即刷新索引\tF5");
    AppendMenuW(t, MF_STRING, IDM_REBUILD, L"重建索引");
    AppendMenuW(t, MF_STRING, IDM_SHORTCUT, L"创建桌面快捷方式");
    AppendMenuW(t, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(t, MF_STRING, IDM_LOGDIR, L"打开日志目录");
    AppendMenuW(g_menu, MF_POPUP, (UINT_PTR)t, L"工具(&T)");
    HMENU h = CreatePopupMenu();
    AppendMenuW(h, MF_STRING, IDM_HELP, L"搜索语法与快捷键\tF1");
    AppendMenuW(h, MF_STRING, IDM_ABOUT, L"关于千寻");
    AppendMenuW(g_menu, MF_POPUP, (UINT_PTR)h, L"帮助(&H)");
    update_menu_checks();
    ACCEL acc[] = {
        {FCONTROL | FVIRTKEY, 'S', IDM_EXPORT}, {FCONTROL | FVIRTKEY, 'Q', IDM_QUIT},
        {FCONTROL | FVIRTKEY, 'I', IDM_CASE},   {FCONTROL | FVIRTKEY, 'B', IDM_WHOLE},
        {FCONTROL | FVIRTKEY, 'U', IDM_PATH},   {FCONTROL | FVIRTKEY, 'R', IDM_REGEX},
        {FCONTROL | FVIRTKEY, 'F', IDM_FOCUS},  {FCONTROL | FVIRTKEY, 'P', IDM_OPTIONS},
        {FVIRTKEY, VK_F5, IDM_REFRESH},         {FVIRTKEY, VK_F1, IDM_HELP},
    };
    g.accel = CreateAcceleratorTableW(acc, (int)(sizeof acc / sizeof acc[0]));
}

static void command(int id) {
    switch (id) {
        case IDM_EXPORT: export_csv(); break;
        case IDM_QUIT: case IDM_TRAY_QUIT: quit_app(); break;
        case IDM_CASE: set_opt(g.cfg.case_); break;
        case IDM_WHOLE: set_opt(g.cfg.whole); break;
        case IDM_PATH: set_opt(g.cfg.match_path); break;
        case IDM_REGEX: set_opt(g.cfg.regex); break;
        case IDM_FOCUS: focus_search(); break;
        case IDM_OPTIONS: open_options(); break;
        case IDM_REFRESH: g.engine->post_refresh_all(); break;
        case IDM_REBUILD:
            if (msg_box(g.hwnd, L"重建索引将重新扫描全部磁盘，确定吗？", MB_YESNO | MB_ICONQUESTION) == IDYES)
                g.engine->post_rebuild(g.cfg);
            break;
        case IDM_SHORTCUT: {
            std::wstring lnk;
            if (create_desktop_shortcut(lnk)) show_message(L"已在桌面创建快捷方式：" + lnk, 5000);
            else msg_box(g.hwnd, L"创建快捷方式失败：" + lnk, MB_ICONWARNING);
            break;
        }
        case IDM_LOGDIR: open_path(data_dir()); break;
        case IDM_HELP: show_help(g.hwnd); break;
        case IDM_ABOUT: show_about(g.hwnd); break;
        case IDM_OPEN: act_open(); break;
        case IDM_OPENDIR: act_open_folder(); break;
        case IDM_TERMINAL: act_terminal(); break;
        case IDM_COPY: act_copy(); break;
        case IDM_COPYPATH: act_copy_path(); break;
        case IDM_COPYNAME: act_copy_name(false); break;
        case IDM_COPYDIR: act_copy_name(true); break;
        case IDM_RENAME: act_rename(); break;
        case IDM_TRASH: act_trash(); break;
        case IDM_PROPS: act_props(); break;
        case IDM_TRAY_SHOW: show_raise(); break;
    }
}

static void on_dpi_changed(int dpi, const RECT* suggested) {
    int old = g.dpi;
    g.dpi = dpi;
    make_fonts();
    set_fonts();
    for (int c = 0; c < 4; c++) ListView_SetColumnWidth(g.list, c, MulDiv(ListView_GetColumnWidth(g.list, c), dpi, old));
    if (suggested)
        SetWindowPos(g.hwnd, nullptr, suggested->left, suggested->top, suggested->right - suggested->left,
                     suggested->bottom - suggested->top, SWP_NOZORDER | SWP_NOACTIVATE);
    layout();
}

static LRESULT CALLBACK main_proc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (m == WM_INITMENUPOPUP || m == WM_DRAWITEM || m == WM_MEASUREITEM || m == WM_MENUCHAR) {
        bool handled;
        LRESULT r = shell_menu_msg(m, wp, lp, &handled);
        if (handled) return r;
    }
    if (g.taskbar_created && m == g.taskbar_created) { tray_add(); return 0; }
    switch (m) {
        case WM_CREATE: {
            g.hwnd = h;
            g.dpi = window_dpi(h);
            make_fonts();
            g.edit = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL, 0, 0,
                                     10, 10, h, (HMENU)(INT_PTR)ID_EDIT, g.hinst, nullptr);
            SendMessageW(g.edit, EM_SETCUEBANNER, TRUE,
                         (LPARAM)L"输入文件名即搜　空格=与　|=或　!=非　*.pdf　ext:docx　size:>10mb　dm:today　（F1 查看语法）");
            SendMessageW(g.edit, EM_SETLIMITTEXT, 4096, 0);
            g.combo = CreateWindowExW(0, WC_COMBOBOXW, L"", WS_CHILD | WS_VISIBLE | WS_TABSTOP | CBS_DROPDOWNLIST | WS_VSCROLL,
                                      0, 0, 10, 200, h, (HMENU)(INT_PTR)ID_COMBO, g.hinst, nullptr);
            for (int i = 0; i < FILTER_COUNT; i++) SendMessageW(g.combo, CB_ADDSTRING, 0, (LPARAM)FILTER_NAMES[i]);
            SendMessageW(g.combo, CB_SETCURSEL, (WPARAM)std::min(std::max(0, g.cfg.filter), FILTER_COUNT - 1), 0);
            g.list = CreateWindowExW(0, WC_LISTVIEWW, L"",
                                     WS_CHILD | WS_VISIBLE | WS_TABSTOP | LVS_REPORT | LVS_OWNERDATA | LVS_SHOWSELALWAYS |
                                         LVS_SHAREIMAGELISTS,
                                     0, 0, 10, 10, h, (HMENU)(INT_PTR)ID_LIST, g.hinst, nullptr);
            ListView_SetExtendedListViewStyle(g.list, LVS_EX_FULLROWSELECT | LVS_EX_DOUBLEBUFFER | LVS_EX_HEADERDRAGDROP |
                                                          LVS_EX_INFOTIP);
            SetWindowTheme(g.list, L"Explorer", nullptr);
            g_theme = OpenThemeData(g.list, L"LISTVIEW");
            g.status = CreateWindowExW(0, STATUSCLASSNAMEW, L"", WS_CHILD | WS_VISIBLE | SBARS_SIZEGRIP, 0, 0, 0, 0, h,
                                       (HMENU)(INT_PTR)ID_STATUS, g.hinst, nullptr);
            const wchar_t* cols[4] = {L"名称", L"路径", L"大小", L"修改时间"};
            for (int c = 0; c < 4; c++) {
                LVCOLUMNW col = {};
                col.mask = LVCF_TEXT | LVCF_WIDTH | LVCF_FMT | LVCF_SUBITEM;
                col.fmt = c == 2 ? LVCFMT_RIGHT : LVCFMT_LEFT;
                col.cx = S(g.cfg.colw[c]);
                col.pszText = (LPWSTR)cols[c];
                col.iSubItem = c;
                ListView_InsertColumn(g.list, c, &col);
            }
            ListView_SetColumnOrderArray(g.list, 4, g.cfg.colorder);
            SHFILEINFOW sfi;
            g.sys_il = (HIMAGELIST)SHGetFileInfoW(L"C:\\", 0, &sfi, sizeof sfi, SHGFI_SYSICONINDEX | SHGFI_SMALLICON);
            set_fonts();
            SetWindowSubclass(g.edit, edit_proc, 1, 0);
            SetWindowSubclass(g.list, list_proc, 1, 0);
            SetWindowSubclass(g.combo, combo_proc, 1, 0);
            build_menu();
            SetMenu(h, g_menu);
            g.sort_col = g.cfg.sort_col;
            g.sort_desc = g.cfg.sort_desc;
            update_sort_header();
            layout();
            SetTimer(h, T_POLL, 200, nullptr);
            return 0;
        }
        case WM_SIZE:
            layout();
            return 0;
        case WM_GETMINMAXINFO: {
            MINMAXINFO* mm = (MINMAXINFO*)lp;
            mm->ptMinTrackSize.x = S(480);
            mm->ptMinTrackSize.y = S(240);
            return 0;
        }
        case 0x02E0: {   // WM_DPICHANGED
            on_dpi_changed(HIWORD(wp), (RECT*)lp);
            return 0;
        }
        case WM_THEMECHANGED:
            if (g_theme) CloseThemeData(g_theme);
            g_theme = OpenThemeData(g.list, L"LISTVIEW");
            break;
        case WM_SETTINGCHANGE:
            if (wp == SPI_SETNONCLIENTMETRICS) { make_fonts(); set_fonts(); layout(); }
            break;
        case WM_ACTIVATE:
            if (LOWORD(wp) == WA_INACTIVE) { g_last_focus = GetFocus(); g.last_deactivate = GetTickCount(); }
            else if (g_last_focus && IsWindow(g_last_focus)) SetFocus(g_last_focus);
            else SetFocus(g.edit);
            return 0;
        case WM_SETFOCUS:
            SetFocus(g_last_focus && IsWindow(g_last_focus) ? g_last_focus : g.edit);
            return 0;
        case WM_COMMAND: {
            int id = LOWORD(wp), code = HIWORD(wp);
            if (id == ID_EDIT && code == EN_CHANGE) { g_debounce = true; SetTimer(h, T_SEARCH, 70, nullptr); return 0; }
            if (id == ID_COMBO && code == CBN_SELCHANGE) { do_search(); return 0; }
            if ((HWND)lp == nullptr || code == 0 || code == 1) command(id);
            return 0;
        }
        case WM_NOTIFY: {
            NMHDR* nh = (NMHDR*)lp;
            if (nh->hwndFrom == g.list) {
                switch (nh->code) {
                    case NM_CUSTOMDRAW: return on_custom_draw((NMLVCUSTOMDRAW*)lp);
                    case LVN_GETDISPINFOW: {
                        NMLVDISPINFOW* di = (NMLVDISPINFOW*)lp;
                        if (di->item.mask & LVIF_TEXT && di->item.pszText && di->item.cchTextMax > 0) {
                            std::wstring s;
                            ReadGuard gd(g.idx->lock);
                            uint32_t e = row_entry(di->item.iItem);
                            if (e != NONE && e < g.idx->size()) {
                                const Entry& en = g.idx->entries[e];
                                if (en.kind == K_DEAD) s = di->item.iSubItem == 0 ? L"（已删除）" : L"";
                                else if (di->item.iSubItem == 0) s = g.idx->name_str(e);
                                else if (di->item.iSubItem == 1) s = g.idx->dirpath(e);
                                else if (di->item.iSubItem == 2) s = en.kind == K_DIR ? L"" : human_size(en.size);
                                else s = fmt_time(en.mtime, false);
                            }
                            lstrcpynW(di->item.pszText, s.c_str(), di->item.cchTextMax);
                        }
                        return 0;
                    }
                    case LVN_GETINFOTIPW: {
                        NMLVGETINFOTIPW* it = (NMLVGETINFOTIPW*)lp;
                        std::wstring s;
                        {
                            ReadGuard gd(g.idx->lock);
                            uint32_t e = row_entry(it->iItem);
                            if (e != NONE && e < g.idx->size() && g.idx->entries[e].kind != K_DEAD) s = g.idx->fullpath(e);
                        }
                        if (it->pszText && it->cchTextMax > 0) lstrcpynW(it->pszText, s.c_str(), it->cchTextMax);
                        return 0;
                    }
                    case LVN_ODFINDITEMW:
                        return -1;
                    case LVN_COLUMNCLICK: {
                        int c = ((NMLISTVIEW*)lp)->iSubItem;
                        if (c == g.sort_col) g.sort_desc = !g.sort_desc;
                        else { g.sort_col = c; g.sort_desc = false; }
                        update_sort_header();
                        do_search(false);
                        return 0;
                    }
                    case LVN_ITEMCHANGED:
                    case LVN_ODSTATECHANGED:
                        SetTimer(h, T_SELCOUNT, 40, nullptr);
                        return 0;
                    case NM_DBLCLK:
                        if (((NMITEMACTIVATE*)lp)->iItem >= 0) act_open();
                        return 0;
                    case LVN_BEGINDRAG:
                    case LVN_BEGINRDRAG:
                        drag_paths(h, selected_paths());
                        return 0;
                }
            }
            break;
        }
        case WM_CONTEXTMENU:
            if ((HWND)wp == g.list) {
                POINT pt = {GET_X_LPARAM(lp), GET_Y_LPARAM(lp)};
                if (pt.x != -1 || pt.y != -1) {
                    // right click on an unselected row selects it first (ListView already did on NM_RCLICK)
                    POINT cp = pt;
                    ScreenToClient(g.list, &cp);
                    LVHITTESTINFO ht = {};
                    ht.pt = cp;
                    if (ListView_HitTest(g.list, &ht) < 0) return 0;
                }
                context_menu(pt);
                return 0;
            }
            break;
        case WM_TIMER:
            if (wp == T_SEARCH) { KillTimer(h, T_SEARCH); do_search(); }
            else if (wp == T_POLL) on_poll();
            else if (wp == T_MSG) { KillTimer(h, T_MSG); g.msg_active = false; update_count(); }
            else if (wp == T_SELCOUNT) { KillTimer(h, T_SELCOUNT); update_count(); }
            return 0;
        case WM_APP_RESULT:
            on_result((SearchRes*)lp);
            return 0;
        case WM_APP_TRAY:
            switch (LOWORD(lp)) {
                case WM_LBUTTONUP: {
                    // clicking the tray activates the taskbar first: "was active" = deactivated just now
                    bool active = IsWindowVisible(h) && !IsIconic(h) &&
                                  (GetForegroundWindow() == h || GetTickCount() - g.last_deactivate < 400);
                    if (active) ShowWindow(h, SW_HIDE); else show_raise();
                    break;
                }
                case WM_RBUTTONUP:
                case WM_CONTEXTMENU: {
                    HMENU mm = CreatePopupMenu();
                    AppendMenuW(mm, MF_STRING, IDM_TRAY_SHOW, L"显示主窗口");
                    AppendMenuW(mm, MF_STRING, IDM_TRAY_QUIT, L"退出");
                    SetMenuDefaultItem(mm, IDM_TRAY_SHOW, FALSE);
                    POINT pt;
                    GetCursorPos(&pt);
                    SetForegroundWindow(h);
                    TrackPopupMenuEx(mm, TPM_RIGHTBUTTON, pt.x, pt.y, h, nullptr);
                    PostMessageW(h, WM_NULL, 0, 0);
                    DestroyMenu(mm);
                    break;
                }
            }
            return 0;
        case WM_HOTKEY:
            if (wp == HOTKEY_ID) toggle_window();
            return 0;
        case WM_COPYDATA: {
            COPYDATASTRUCT* cds = (COPYDATASTRUCT*)lp;
            if (cds->dwData != COPYDATA_MAGIC) return FALSE;
            std::string s((const char*)cds->lpData, cds->cbData);
            if (s == "toggle") toggle_window();
            else if (s == "hidden") {}
            else show_raise();
            return TRUE;
        }
        case WM_DEVICECHANGE: {
            if (wp == DBT_DEVICEQUERYREMOVE && lp) {
                DEV_BROADCAST_HDR* hdr = (DEV_BROADCAST_HDR*)lp;
                if (hdr->dbch_devicetype == DBT_DEVTYP_HANDLE) {
                    DEV_BROADCAST_HANDLE* bh = (DEV_BROADCAST_HANDLE*)lp;
                    if (g.engine->release_handle(bh->dbch_handle)) log_line(L"released watch handle for device removal");
                }
            }
            if (wp == DBT_DEVICEARRIVAL || wp == DBT_DEVICEQUERYREMOVEFAILED || wp == DBT_DEVICEREMOVECOMPLETE)
                g.engine->post_drive_check();
            return TRUE;
        }
        case WM_QUERYENDSESSION:
            return TRUE;
        case WM_ENDSESSION:
            if (wp) {
                // log off / shutdown: save window state and the index (bounded wait)
                save_state();
                g.engine->post_quit();
                g.engine->join(8000);
            }
            return 0;
        case WM_CLOSE:
            if (!g.quitting && g.tray_ok && g.cfg.close_to_tray) { ShowWindow(h, SW_HIDE); return 0; }
            quit_app();
            return 0;
        case WM_DESTROY:
            KillTimer(h, T_POLL);
            if (g_theme) { CloseThemeData(g_theme); g_theme = nullptr; }
            PostQuitMessage(0);
            return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

bool create_main_window(bool show) {
    WNDCLASSEXW wc = {};
    wc.cbSize = sizeof wc;
    wc.lpfnWndProc = main_proc;
    wc.hInstance = g.hinst;
    wc.hIcon = g.icon_big;
    wc.hIconSm = g.icon_small;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszClassName = MAIN_CLASS;
    if (!RegisterClassExW(&wc)) { log_line(L"RegisterClassExW failed: %lu", GetLastError()); return false; }
    g.taskbar_created = RegisterWindowMessageW(L"TaskbarCreated");
    int sd = system_dpi();
    int w = g.cfg.win_w > 0 ? g.cfg.win_w : 1100, hh = g.cfg.win_h > 0 ? g.cfg.win_h : 680;
    int x = g.cfg.win_x, y = g.cfg.win_y;
    if (x != CW_USEDEFAULT) {
        // keep the window reachable if the monitor layout changed
        RECT r = {x, y, x + MulDiv(w, sd, 96), y + MulDiv(hh, sd, 96)};
        if (!MonitorFromRect(&r, MONITOR_DEFAULTTONULL)) x = y = CW_USEDEFAULT;
    }
    HWND h = nullptr;
    for (int attempt = 0; attempt < 3 && !h; attempt++) {   // the shell/desktop may still be starting at logon
        if (attempt) Sleep(700);
        h = CreateWindowExW(WS_EX_APPWINDOW, MAIN_CLASS, L"千寻 - 文件秒搜", WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN, x, y,
                            MulDiv(w, sd, 96), MulDiv(hh, sd, 96), nullptr, nullptr, g.hinst, nullptr);
    }
    if (!h) { log_line(L"CreateWindowExW failed: %lu", GetLastError()); return false; }
    // per-monitor DPI may differ from the system DPI used for the initial size
    if (g.dpi != sd) {
        RECT r;
        GetWindowRect(h, &r);
        SetWindowPos(h, nullptr, 0, 0, MulDiv(w, g.dpi, 96), MulDiv(hh, g.dpi, 96), SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
    }
    tray_add();
    register_hotkey();
    if (show || !g.tray_ok) {
        ShowWindow(h, g.cfg.win_max ? SW_SHOWMAXIMIZED : SW_SHOWNORMAL);
        show_raise();
    }
    do_search();
    return true;
}

} // namespace qx
