// 千寻 —— 对话框：帮助（F1）、关于、选项、重命名输入框。纯 Win32，按 DPI 与系统消息字体布局。
#include "ui.h"
#include "textutil.h"
#include <windowsx.h>
#include <algorithm>
#include <functional>

namespace qx {

static BOOL CALLBACK set_font_cb(HWND c, LPARAM lp) {
    SendMessageW(c, WM_SETFONT, (WPARAM)lp, TRUE);
    return TRUE;
}

void apply_font_tree(HWND w, HFONT f) { EnumChildWindows(w, set_font_cb, (LPARAM)f); }

// ---------------------------------------------------------------- tiny modal dialog framework
struct Dlg {
    HWND hwnd = nullptr;
    bool done = false;
    int result = IDCANCEL;
    std::function<void(HWND)> on_create;
    std::function<bool(int id, int code, HWND ctl)> on_command;   // return true when handled
    std::function<bool()> on_ok;                                  // validate/collect, false keeps the dialog open
};

static LRESULT CALLBACK dlg_proc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    Dlg* d = (Dlg*)GetWindowLongPtrW(h, GWLP_USERDATA);
    switch (m) {
        case WM_NCCREATE: {
            CREATESTRUCTW* cs = (CREATESTRUCTW*)lp;
            SetWindowLongPtrW(h, GWLP_USERDATA, (LONG_PTR)cs->lpCreateParams);
            break;
        }
        case WM_CREATE:
            d->hwnd = h;
            if (d->on_create) d->on_create(h);
            return 0;
        case WM_COMMAND: {
            int id = LOWORD(wp), code = HIWORD(wp);
            if (d->on_command && d->on_command(id, code, (HWND)lp)) return 0;
            if (id == IDOK) {
                if (!d->on_ok || d->on_ok()) { d->result = IDOK; d->done = true; }
                return 0;
            }
            if (id == IDCANCEL) { d->result = IDCANCEL; d->done = true; return 0; }
            return 0;
        }
        case WM_CTLCOLORSTATIC:
        case WM_CTLCOLORBTN: {
            HDC dc = (HDC)wp;
            SetBkColor(dc, GetSysColor(COLOR_BTNFACE));
            return (LRESULT)GetSysColorBrush(COLOR_BTNFACE);
        }
        case WM_CLOSE:
            d->result = IDCANCEL;
            d->done = true;
            return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

static int run_modal(HWND owner, Dlg& d, const std::wstring& title, int cw, int ch) {
    static bool reg = false;
    if (!reg) {
        WNDCLASSEXW wc = {};
        wc.cbSize = sizeof wc;
        wc.lpfnWndProc = dlg_proc;
        wc.hInstance = g.hinst;
        wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
        wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
        wc.lpszClassName = L"QianXun.Dialog";
        wc.hIcon = g.icon_big;
        wc.hIconSm = g.icon_small;
        RegisterClassExW(&wc);
        reg = true;
    }
    DWORD style = WS_POPUP | WS_CAPTION | WS_SYSMENU, ex = WS_EX_DLGMODALFRAME | WS_EX_CONTROLPARENT;
    RECT r = {0, 0, cw, ch};
    AdjustWindowRectEx(&r, style, FALSE, ex);
    int w = r.right - r.left, hgt = r.bottom - r.top;
    RECT orc;
    if (owner && IsWindowVisible(owner) && !IsIconic(owner)) GetWindowRect(owner, &orc);
    else SystemParametersInfoW(SPI_GETWORKAREA, 0, &orc, 0);
    int x = orc.left + ((orc.right - orc.left) - w) / 2, y = orc.top + ((orc.bottom - orc.top) - hgt) / 2;
    RECT wa;
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &wa, 0);
    x = std::max((int)wa.left, std::min(x, (int)wa.right - w));
    y = std::max((int)wa.top, std::min(y, (int)wa.bottom - hgt));
    if (owner) EnableWindow(owner, FALSE);
    HWND h = CreateWindowExW(ex, L"QianXun.Dialog", title.c_str(), style, x, y, w, hgt, owner, nullptr, g.hinst, &d);
    if (!h) { if (owner) EnableWindow(owner, TRUE); return IDCANCEL; }
    apply_font_tree(h, g.font);
    ShowWindow(h, SW_SHOW);
    MSG msg;
    while (!d.done && GetMessageW(&msg, nullptr, 0, 0) > 0) {
        if (!IsDialogMessageW(h, &msg)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
    if (owner) EnableWindow(owner, TRUE);
    DestroyWindow(h);
    if (owner) SetActiveWindow(owner);
    return d.result;
}

static HWND mk(HWND parent, const wchar_t* cls, const std::wstring& text, DWORD style, int x, int y, int w, int h, int id,
               DWORD ex = 0) {
    return CreateWindowExW(ex, cls, text.c_str(), WS_CHILD | WS_VISIBLE | style, x, y, w, h, parent,
                           (HMENU)(INT_PTR)id, g.hinst, nullptr);
}

static int line_h() {
    HDC dc = GetDC(nullptr);
    HGDIOBJ o = SelectObject(dc, g.font);
    TEXTMETRICW tm;
    GetTextMetricsW(dc, &tm);
    SelectObject(dc, o);
    ReleaseDC(nullptr, dc);
    return tm.tmHeight;
}

static int text_w(const std::wstring& s, HFONT f = nullptr) {
    HDC dc = GetDC(nullptr);
    HGDIOBJ o = SelectObject(dc, f ? f : g.font);
    SIZE sz = {0, 0};
    GetTextExtentPoint32W(dc, s.c_str(), (int)s.size(), &sz);
    SelectObject(dc, o);
    ReleaseDC(nullptr, dc);
    return sz.cx;
}

// text height when wrapped to width w
static int wrap_h(const std::wstring& s, int w) {
    HDC dc = GetDC(nullptr);
    HGDIOBJ o = SelectObject(dc, g.font);
    RECT r = {0, 0, w, 0};
    DrawTextW(dc, s.c_str(), (int)s.size(), &r, DT_CALCRECT | DT_WORDBREAK | DT_NOPREFIX);
    SelectObject(dc, o);
    ReleaseDC(nullptr, dc);
    return r.bottom;
}

// ---------------------------------------------------------------- input box (rename)
bool input_box(HWND owner, const std::wstring& title, const std::wstring& label, std::wstring& value) {
    Dlg d;
    int lh = line_h(), m = S(12), bw = std::max(S(88), text_w(L"取消") + S(32)), bh = lh + S(12);
    int cw = S(440), eh = lh + S(10);
    int ch = m + lh + S(6) + eh + m + bh + m;
    HWND edit = nullptr;
    d.on_create = [&](HWND h) {
        mk(h, L"STATIC", label, SS_LEFT | SS_NOPREFIX, m, m, cw - 2 * m, lh, -1);
        edit = mk(h, L"EDIT", value, WS_TABSTOP | ES_AUTOHSCROLL, m, m + lh + S(6), cw - 2 * m, eh, 100, WS_EX_CLIENTEDGE);
        int y = m + lh + S(6) + eh + m;
        mk(h, L"BUTTON", L"确定", WS_TABSTOP | BS_DEFPUSHBUTTON, cw - m - 2 * bw - S(8), y, bw, bh, IDOK);
        mk(h, L"BUTTON", L"取消", WS_TABSTOP, cw - m - bw, y, bw, bh, IDCANCEL);
        apply_font_tree(h, g.font);
        SetFocus(edit);
        // select the base name (Explorer behaviour); whole text when there is no extension
        size_t dot = value.rfind(L'.');
        SendMessageW(edit, EM_SETSEL, 0, (dot != std::wstring::npos && dot > 0) ? (LPARAM)dot : -1);
    };
    d.on_ok = [&]() {
        int n = GetWindowTextLengthW(edit);
        std::wstring s((size_t)n + 1, 0);
        GetWindowTextW(edit, &s[0], n + 1);
        s.resize((size_t)n);
        value = s;
        return true;
    };
    return run_modal(owner, d, title, cw, ch) == IDOK;
}

// ---------------------------------------------------------------- about
void show_about(HWND owner) {
    std::wstring t = std::wstring(L"千寻 ") + QX_VERSION_W +
                     L"\nEverything 式文件名秒搜工具（Windows 原生版）。\n\n"
                     L"全盘索引常驻内存，ReadDirectoryChangesW 实时同步；支持 Everything 搜索语法。\n"
#ifdef _WIN64
                     L"运行环境：Win32 原生程序 · C++17 · x64";
#else
                     L"运行环境：Win32 原生程序 · C++17 · x86";
#endif
    MSGBOXPARAMSW mp = {};
    mp.cbSize = sizeof mp;
    mp.hwndOwner = owner;
    mp.hInstance = g.hinst;
    mp.lpszText = t.c_str();
    mp.lpszCaption = L"关于千寻";
    mp.dwStyle = MB_OK | MB_USERICON;
    mp.lpszIcon = MAKEINTRESOURCEW(1);
    MessageBoxIndirectW(&mp);
}

// ---------------------------------------------------------------- help (F1)
static HWND make_table(HWND parent, int x, int y, int w, const std::vector<std::wstring>& heads, const std::vector<int>& ratios,
                       const std::vector<std::vector<std::wstring>>& rows, int& out_h) {
    HWND lv = mk(parent, WC_LISTVIEWW, L"", WS_TABSTOP | LVS_REPORT | LVS_NOSORTHEADER | LVS_SINGLESEL | WS_BORDER, x, y, w, 100, -1);
    ListView_SetExtendedListViewStyle(lv, LVS_EX_GRIDLINES | LVS_EX_FULLROWSELECT | LVS_EX_DOUBLEBUFFER);
    SendMessageW(lv, WM_SETFONT, (WPARAM)g.font, TRUE);
    int tot = 0;
    for (int r : ratios) tot += r;
    int used = 0;
    for (size_t c = 0; c < heads.size(); c++) {
        LVCOLUMNW col = {};
        col.mask = LVCF_TEXT | LVCF_WIDTH;
        col.cx = c + 1 == heads.size() ? (w - GetSystemMetrics(SM_CXEDGE) * 2 - used - 2) : (w * ratios[c] / tot);
        used += col.cx;
        col.pszText = (LPWSTR)heads[c].c_str();
        ListView_InsertColumn(lv, (int)c, &col);
    }
    for (size_t r = 0; r < rows.size(); r++) {
        LVITEMW it = {};
        it.mask = LVIF_TEXT;
        it.iItem = (int)r;
        it.pszText = (LPWSTR)rows[r][0].c_str();
        ListView_InsertItem(lv, &it);
        for (size_t c = 1; c < rows[r].size(); c++) ListView_SetItemText(lv, (int)r, (int)c, (LPWSTR)rows[r][c].c_str());
    }
    // exact height: header + rows + borders (no scrollbars)
    RECT ir = {}, hr = {};
    ListView_GetItemRect(lv, 0, &ir, LVIR_BOUNDS);
    GetWindowRect(ListView_GetHeader(lv), &hr);
    int rh = ir.bottom - ir.top;
    if (rh <= 0) rh = line_h() + S(4);
    out_h = (hr.bottom - hr.top) + rh * (int)rows.size() + GetSystemMetrics(SM_CYEDGE) * 2 + S(2);
    SetWindowPos(lv, nullptr, 0, 0, w, out_h, SWP_NOMOVE | SWP_NOZORDER);
    for (int k = 0; k < 4 && ListView_GetCountPerPage(lv) < (int)rows.size(); k++) {   // grow until every row fits
        out_h += rh;
        SetWindowPos(lv, nullptr, 0, 0, w, out_h, SWP_NOMOVE | SWP_NOZORDER);
    }
    return lv;
}

void show_help(HWND owner) {
    static HFONT head = nullptr;
    LOGFONTW lf;
    GetObjectW(g.font, sizeof lf, &lf);
    lf.lfWeight = FW_BOLD;
    lf.lfHeight = (LONG)(lf.lfHeight * 1.2);
    if (head) DeleteObject(head);
    head = CreateFontIndirectW(&lf);
    std::vector<std::vector<std::wstring>> syn = {
        {L"空格", L"与（同时包含）", L"报告 2026"},
        {L"|", L"或", L"docx|wps"},
        {L"!", L"非（排除）", L"报告 !草稿"},
        {L"* ?", L"通配符（匹配整个文件名）", L"*.pdf　报告??.docx"},
        {L"\"…\"", L"含空格的短语", L"\"会议 纪要\""},
        {L"含 \\ 或 / 的词、path:", L"按完整路径匹配（/ 等同 \\）", L"Users\\文档 方案　d:/项目 报告　path:项目"},
        {L"ext:", L"扩展名（分号分隔）", L"ext:pdf;ofd"},
        {L"file: folder:", L"只要文件／只要文件夹", L"folder:项目"},
        {L"regex:", L"正则表达式", L"regex:^IMG_\\d{4}"},
        {L"size:", L"大小", L"size:>100mb　size:1mb..10mb　size:large"},
        {L"dm:", L"修改日期", L"dm:today　dm:yesterday　dm:thisweek　dm:last7days　dm:2026-10"},
    };
    std::vector<std::vector<std::wstring>> keys = {
        {L"Enter", L"打开", L"Ctrl+Enter", L"打开所在文件夹"},
        {L"Ctrl+C", L"复制文件（可直接粘贴到文件管理器）", L"Ctrl+Shift+C", L"复制完整路径"},
        {L"F2", L"重命名", L"Delete", L"移到回收站"},
        {L"Ctrl+I", L"区分大小写", L"Ctrl+B", L"全字匹配"},
        {L"Ctrl+U", L"匹配路径", L"Ctrl+R", L"正则表达式"},
        {L"Ctrl+F", L"回到搜索框", L"Esc", L"清空搜索／隐藏窗口"},
        {L"Alt+Enter", L"属性", L"Shift+右键", L"系统完整右键菜单"},
    };
    std::wstring alias = L"大小别名：empty、tiny(<10KB)、small、medium、large(1–16MB)、huge(16–128MB)、gigantic(>128MB)";
    std::wstring hk = L"全局唤出：默认 " + (g.cfg.hotkey.empty() ? std::wstring(L"Ctrl+Alt+F") : g.cfg.hotkey) +
                      L"（在“工具 → 选项”中可修改或关闭）；也可运行 QianXun.exe --toggle。";
    std::wstring mon = L"实时监控：每个磁盘一个 ReadDirectoryChangesW 监视，新建、改名、删除约 1 秒内反映到结果中。";
    Dlg d;
    int m = S(14), cw = S(760), lh = line_h(), bh = lh + S(12), bw = std::max(S(88), text_w(L"关闭") + S(40));
    int hh = line_h() * 6 / 5 + S(4);
    // measure: build in on_create, compute total height first with approximate row heights
    int row = std::max(lh + S(6), S(20));
    int t1 = row * ((int)syn.size() + 1) + S(8), t2 = row * ((int)keys.size() + 1) + S(8);
    int iw = cw - 2 * m;
    int ch = m + hh + S(6) + t1 + S(8) + wrap_h(alias, iw) + S(14) + hh + S(6) + t2 + S(10) + wrap_h(hk, iw) + S(6) +
             wrap_h(mon, iw) + S(14) + bh + m;
    d.on_create = [&](HWND h) {
        int y = m;
        HWND s1 = mk(h, L"STATIC", L"千寻 搜索语法（与 Everything 一致）", SS_LEFT | SS_NOPREFIX, m, y, iw, hh, -1);
        y += hh + S(6);
        int th;
        make_table(h, m, y, iw, {L"写法", L"含义", L"示例"}, {22, 30, 48}, syn, th);
        y += th + S(8);
        int ah = wrap_h(alias, iw);
        mk(h, L"STATIC", alias, SS_LEFT | SS_NOPREFIX, m, y, iw, ah, -1);
        y += ah + S(14);
        HWND s2 = mk(h, L"STATIC", L"快捷键", SS_LEFT | SS_NOPREFIX, m, y, iw, hh, -1);
        y += hh + S(6);
        make_table(h, m, y, iw, {L"按键", L"功能", L"按键", L"功能"}, {16, 34, 18, 32}, keys, th);
        y += th + S(10);
        int h1 = wrap_h(hk, iw);
        mk(h, L"STATIC", hk, SS_LEFT | SS_NOPREFIX, m, y, iw, h1, -1);
        y += h1 + S(6);
        int h2 = wrap_h(mon, iw);
        mk(h, L"STATIC", mon, SS_LEFT | SS_NOPREFIX, m, y, iw, h2, -1);
        y += h2 + S(14);
        HWND b = mk(h, L"BUTTON", L"关闭", WS_TABSTOP | BS_DEFPUSHBUTTON, cw - m - bw, y, bw, bh, IDOK);
        apply_font_tree(h, g.font);
        SendMessageW(s1, WM_SETFONT, (WPARAM)head, TRUE);
        SendMessageW(s2, WM_SETFONT, (WPARAM)head, TRUE);
        // resize the window to the real content height
        RECT r = {0, 0, cw, y + bh + m};
        AdjustWindowRectEx(&r, WS_POPUP | WS_CAPTION | WS_SYSMENU, FALSE, WS_EX_DLGMODALFRAME);
        SetWindowPos(h, nullptr, 0, 0, r.right - r.left, r.bottom - r.top, SWP_NOMOVE | SWP_NOZORDER);
        SetFocus(b);
    };
    run_modal(owner, d, L"搜索语法与快捷键", cw, ch);
}

// ---------------------------------------------------------------- options
bool show_options(HWND owner, Config& cfg, bool& autostart) {
    Dlg d;
    int lh = line_h(), m = S(12), bh = lh + S(12);
    int bw = std::max(S(88), text_w(L"添加…") + S(32));
    int cw = S(600);
    int list_h = lh * 5 + S(8);
    int gb_h = lh + S(8) + list_h + S(12);
    int cb_h = lh + S(8);
    EngineStatus st = g.engine->status();
    std::wstring info = L"实时监控：每个磁盘一个 ReadDirectoryChangesW 监视，已覆盖 " + fmt_thousands((long long)st.watched) +
                        L" / " + fmt_thousands((long long)st.dirs) + L" 个目录。";
    int info_h = wrap_h(info, cw - 2 * m);
    int ch = m + gb_h + S(8) + gb_h + S(10) + cb_h * 4 + S(4) + std::max(cb_h, lh + S(10)) + S(10) + info_h + S(12) + bh + m;
    HWND lb_roots = nullptr, lb_ex = nullptr, cb_rm, cb_net, cb_tray, cb_auto, cb_hk, hk;
    enum { ID_RADD = 200, ID_RDEL, ID_XADD, ID_XDEL, ID_HKCHK, ID_HK };
    auto fill = [](HWND lb, const std::vector<std::wstring>& v) {
        for (auto& s : v) SendMessageW(lb, LB_ADDSTRING, 0, (LPARAM)s.c_str());
    };
    auto fit_extent = [](HWND lb) {   // horizontal scrollbar only when an entry is wider than the box
        int n = (int)SendMessageW(lb, LB_GETCOUNT, 0, 0), wmax = 0;
        for (int i = 0; i < n; i++) {
            int l = (int)SendMessageW(lb, LB_GETTEXTLEN, i, 0);
            std::wstring s((size_t)l + 1, 0);
            SendMessageW(lb, LB_GETTEXT, i, (LPARAM)&s[0]);
            s.resize((size_t)l);
            wmax = std::max(wmax, text_w(s) + S(8));
        }
        SendMessageW(lb, LB_SETHORIZONTALEXTENT, (WPARAM)wmax, 0);
    };
    auto items = [](HWND lb) {
        std::vector<std::wstring> v;
        int n = (int)SendMessageW(lb, LB_GETCOUNT, 0, 0);
        for (int i = 0; i < n; i++) {
            int l = (int)SendMessageW(lb, LB_GETTEXTLEN, i, 0);
            std::wstring s((size_t)l + 1, 0);
            SendMessageW(lb, LB_GETTEXT, i, (LPARAM)&s[0]);
            s.resize((size_t)l);
            v.push_back(s);
        }
        return v;
    };
    d.on_create = [&](HWND h) {
        int y = m;
        auto group = [&](const std::wstring& title, HWND& lb, int idadd, int iddel) {
            mk(h, L"BUTTON", title, BS_GROUPBOX, m, y, cw - 2 * m, gb_h, -1);
            int ix = m + S(10), iy = y + lh + S(6);
            lb = mk(h, L"LISTBOX", L"", WS_TABSTOP | WS_VSCROLL | WS_HSCROLL | LBS_NOINTEGRALHEIGHT | LBS_EXTENDEDSEL | LBS_NOTIFY,
                    ix, iy, cw - 2 * m - S(20) - bw - S(10), list_h, -1, WS_EX_CLIENTEDGE);
            int bx = cw - m - S(10) - bw;
            mk(h, L"BUTTON", L"添加…", WS_TABSTOP, bx, iy, bw, bh, idadd);
            mk(h, L"BUTTON", L"删除", WS_TABSTOP, bx, iy + bh + S(6), bw, bh, iddel);
            y += gb_h + S(8);
        };
        group(L"索引范围（留空＝所有本地磁盘）", lb_roots, ID_RADD, ID_RDEL);
        fill(lb_roots, cfg.roots);
        group(L"排除目录（回收站、System Volume Information、WinSxS 已内置排除）", lb_ex, ID_XADD, ID_XDEL);
        fill(lb_ex, cfg.excludes);
        fit_extent(lb_roots);
        fit_extent(lb_ex);
        y += S(2);
        auto check = [&](const std::wstring& t, bool on) {
            HWND c = mk(h, L"BUTTON", t, WS_TABSTOP | BS_AUTOCHECKBOX, m, y, cw - 2 * m, cb_h, -1);
            Button_SetCheck(c, on ? BST_CHECKED : BST_UNCHECKED);
            y += cb_h;
            return c;
        };
        cb_rm = check(L"索引 U 盘、移动硬盘等可移动磁盘", cfg.index_removable);
        cb_net = check(L"索引网络文件系统（NFS／SMB 等，可能较慢）", cfg.index_network);
        cb_tray = check(L"关闭窗口时最小化到托盘（保持实时索引）", cfg.close_to_tray);
        cb_auto = check(L"登录 Windows 时自动启动（后台托盘）", autostart);
        y += S(4);
        std::wstring hkl = L"全局快捷键（唤出／隐藏）：";
        int hw = text_w(hkl) + S(30);
        cb_hk = mk(h, L"BUTTON", hkl, WS_TABSTOP | BS_AUTOCHECKBOX, m, y + S(1), hw, cb_h, ID_HKCHK);
        Button_SetCheck(cb_hk, cfg.hotkey.empty() ? BST_UNCHECKED : BST_CHECKED);
        hk = mk(h, HOTKEY_CLASSW, L"", WS_TABSTOP, m + hw + S(6), y, cw - 2 * m - hw - S(6), lh + S(10), ID_HK, WS_EX_CLIENTEDGE);
        UINT mods = MOD_CONTROL | MOD_ALT, vk = 'F';
        parse_hotkey(cfg.hotkey.empty() ? L"Ctrl+Alt+F" : cfg.hotkey, mods, vk);
        BYTE hf = (BYTE)(((mods & MOD_SHIFT) ? HOTKEYF_SHIFT : 0) | ((mods & MOD_CONTROL) ? HOTKEYF_CONTROL : 0) |
                         ((mods & MOD_ALT) ? HOTKEYF_ALT : 0));
        SendMessageW(hk, HKM_SETHOTKEY, MAKEWORD(vk, hf), 0);
        SendMessageW(hk, HKM_SETRULES, HKCOMB_NONE | HKCOMB_S, MAKELPARAM(HOTKEYF_CONTROL | HOTKEYF_ALT, 0));
        EnableWindow(hk, !cfg.hotkey.empty());
        y += std::max(cb_h, lh + S(10)) + S(10);
        mk(h, L"STATIC", info, SS_LEFT | SS_NOPREFIX, m, y, cw - 2 * m, info_h, -1);
        y += info_h + S(12);
        int obw = std::max(S(88), text_w(L"取消") + S(32));
        mk(h, L"BUTTON", L"确定", WS_TABSTOP | BS_DEFPUSHBUTTON, cw - m - 2 * obw - S(8), y, obw, bh, IDOK);
        mk(h, L"BUTTON", L"取消", WS_TABSTOP, cw - m - obw, y, obw, bh, IDCANCEL);
        apply_font_tree(h, g.font);
    };
    d.on_command = [&](int id, int code, HWND) -> bool {
        if (id == ID_RADD || id == ID_XADD) {
            std::wstring p = pick_folder(d.hwnd, L"选择目录");
            if (!p.empty()) {
                p = win_norm_path(p, true);
                HWND lb = id == ID_RADD ? lb_roots : lb_ex;
                if (SendMessageW(lb, LB_FINDSTRINGEXACT, (WPARAM)-1, (LPARAM)p.c_str()) == LB_ERR)
                    SendMessageW(lb, LB_ADDSTRING, 0, (LPARAM)p.c_str());
                fit_extent(lb);
            }
            return true;
        }
        if (id == ID_RDEL || id == ID_XDEL) {
            HWND lb = id == ID_RDEL ? lb_roots : lb_ex;
            int n = (int)SendMessageW(lb, LB_GETCOUNT, 0, 0);
            for (int i = n - 1; i >= 0; i--)
                if (SendMessageW(lb, LB_GETSEL, i, 0) > 0) SendMessageW(lb, LB_DELETESTRING, i, 0);
            return true;
        }
        if (id == ID_HKCHK && code == BN_CLICKED) {
            EnableWindow(hk, Button_GetCheck(cb_hk) == BST_CHECKED);
            return true;
        }
        return false;
    };
    d.on_ok = [&]() {
        cfg.roots = items(lb_roots);
        cfg.excludes = items(lb_ex);
        cfg.index_removable = Button_GetCheck(cb_rm) == BST_CHECKED;
        cfg.index_network = Button_GetCheck(cb_net) == BST_CHECKED;
        cfg.close_to_tray = Button_GetCheck(cb_tray) == BST_CHECKED;
        autostart = Button_GetCheck(cb_auto) == BST_CHECKED;
        if (Button_GetCheck(cb_hk) == BST_CHECKED) {
            WORD v = (WORD)SendMessageW(hk, HKM_GETHOTKEY, 0, 0);
            UINT vk = LOBYTE(v), hf = HIBYTE(v);
            UINT mods = ((hf & HOTKEYF_SHIFT) ? MOD_SHIFT : 0) | ((hf & HOTKEYF_CONTROL) ? MOD_CONTROL : 0) |
                        ((hf & HOTKEYF_ALT) ? MOD_ALT : 0);
            std::wstring s = vk ? hotkey_to_string(mods, vk) : L"";
            UINT pm, pv;
            if (s.empty() || !parse_hotkey(s, pm, pv)) {
                msg_box(d.hwnd, L"全局快捷键无效：须包含 Ctrl / Alt / Shift 修饰键（或使用 F1–F24）。", MB_ICONWARNING);
                return false;
            }
            cfg.hotkey = s;
        } else {
            cfg.hotkey.clear();
        }
        return true;
    };
    return run_modal(owner, d, L"选项", cw, ch) == IDOK;
}

} // namespace qx
