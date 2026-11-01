// 千寻 —— 系统集成：打开、定位、终端、剪贴板（CF_HDROP）、回收站、属性、系统右键菜单、拖出、
// 桌面快捷方式、开机自启、图标、文件对话框。
#include "ui.h"
#include "textutil.h"
#include <shlobj.h>
#include <shellapi.h>
#include <shlwapi.h>
#include <shobjidl.h>
#include <unordered_map>
#include <list>

namespace qx {

int msg_box(HWND owner, const std::wstring& text, UINT flags, const std::wstring& title) {
    return MessageBoxW(owner, text.c_str(), title.c_str(), flags);
}

UINT drive_type_of(const std::wstring& p) {
    if (p.size() >= 3 && p[1] == L':' && p[2] == L'\\') {
        std::wstring r = p.substr(0, 3);
        return GetDriveTypeW(r.c_str());
    }
    if (p.compare(0, 2, L"\\\\") == 0) return DRIVE_REMOTE;
    return DRIVE_UNKNOWN;
}

void open_path(const std::wstring& p) {
    SHELLEXECUTEINFOW sei = {};
    sei.cbSize = sizeof sei;
    sei.fMask = SEE_MASK_NOASYNC | SEE_MASK_FLAG_NO_UI;
    sei.hwnd = g.hwnd;
    sei.lpFile = p.c_str();
    sei.nShow = SW_SHOWNORMAL;
    if (ShellExecuteExW(&sei)) return;
    DWORD e = GetLastError();
    log_line(L"open %ls: %lu", p.c_str(), e);
    if (e == ERROR_NO_ASSOCIATION || e == ERROR_CANCELLED || e == 1155) {
        std::wstring args = L"shell32.dll,OpenAs_RunDLL " + p;
        ShellExecuteW(g.hwnd, nullptr, L"rundll32.exe", args.c_str(), nullptr, SW_SHOWNORMAL);
        return;
    }
    msg_box(g.hwnd, L"无法打开：" + p + L"\n" + last_error_text(e), MB_ICONWARNING);
}

void show_in_folder(const std::wstring& p) {
    PIDLIST_ABSOLUTE pidl = ILCreateFromPathW(p.c_str());
    if (pidl) {
        HRESULT hr = SHOpenFolderAndSelectItems(pidl, 0, nullptr, 0);
        ILFree(pidl);
        if (SUCCEEDED(hr)) return;
    }
    wchar_t win[MAX_PATH] = L"C:\\Windows";
    GetWindowsDirectoryW(win, MAX_PATH);
    std::wstring exe = std::wstring(win) + L"\\explorer.exe";
    std::wstring args = L"/select,\"" + p + L"\"";
    if ((INT_PTR)ShellExecuteW(g.hwnd, nullptr, exe.c_str(), args.c_str(), nullptr, SW_SHOWNORMAL) <= 32) {
        std::wstring par, nm;
        if (split_path(p, par, nm)) open_path(par);
    }
}

static std::wstring find_exe(const wchar_t* name) {
    wchar_t buf[MAX_PATH * 2];
    DWORD n = SearchPathW(nullptr, name, nullptr, MAX_PATH * 2, buf, nullptr);
    if (n && n < MAX_PATH * 2) return buf;
    return L"";
}

static bool spawn(const std::wstring& cmdline, const std::wstring& cwd, DWORD flags) {
    STARTUPINFOW si = {};
    si.cb = sizeof si;
    PROCESS_INFORMATION pi = {};
    std::vector<wchar_t> cl(cmdline.begin(), cmdline.end());
    cl.push_back(0);
    if (!CreateProcessW(nullptr, cl.data(), nullptr, nullptr, FALSE, flags, nullptr, cwd.c_str(), &si, &pi)) return false;
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return true;
}

bool open_terminal(const std::wstring& d) {
    std::wstring wt = find_exe(L"wt.exe");
    if (!wt.empty() && d.find(L';') == std::wstring::npos) {   // wt treats ';' as a command separator
        std::wstring dd = d;
        if (dd.size() > 3 && dd.back() == L'\\') dd.pop_back();
        if (dd.size() == 3 && dd.back() == L'\\') dd += L'\\';   // "C:\" would escape the closing quote
        if (spawn(L"\"" + wt + L"\" -d \"" + dd + L"\"", d, 0)) return true;
    }
    std::wstring ps = find_exe(L"powershell.exe");
    if (!ps.empty() && spawn(L"\"" + ps + L"\" -NoExit", d, CREATE_NEW_CONSOLE)) return true;
    std::wstring cmd = find_exe(L"cmd.exe");
    if (cmd.empty()) cmd = L"cmd.exe";
    return spawn(L"\"" + cmd + L"\"", d, CREATE_NEW_CONSOLE);
}

static HGLOBAL make_hdrop(const std::vector<std::wstring>& paths) {
    size_t chars = 1;
    for (auto& p : paths) chars += p.size() + 1;
    HGLOBAL h = GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, sizeof(DROPFILES) + chars * sizeof(wchar_t));
    if (!h) return nullptr;
    DROPFILES* df = (DROPFILES*)GlobalLock(h);
    df->pFiles = sizeof(DROPFILES);
    df->fWide = TRUE;
    wchar_t* p = (wchar_t*)((char*)df + sizeof(DROPFILES));
    for (auto& s : paths) {
        memcpy(p, s.c_str(), (s.size() + 1) * sizeof(wchar_t));
        p += s.size() + 1;
    }
    *p = 0;
    GlobalUnlock(h);
    return h;
}

static HGLOBAL make_text(const std::wstring& s) {
    HGLOBAL h = GlobalAlloc(GMEM_MOVEABLE, (s.size() + 1) * sizeof(wchar_t));
    if (!h) return nullptr;
    memcpy(GlobalLock(h), s.c_str(), (s.size() + 1) * sizeof(wchar_t));
    GlobalUnlock(h);
    return h;
}

static bool open_clip(HWND h) {
    for (int i = 0; i < 10; i++) {
        if (OpenClipboard(h)) return true;
        Sleep(20);
    }
    return false;
}

bool copy_files_to_clipboard(HWND hw, const std::vector<std::wstring>& paths) {
    if (paths.empty() || !open_clip(hw)) return false;
    EmptyClipboard();
    bool ok = false;
    if (HGLOBAL h = make_hdrop(paths)) ok = SetClipboardData(CF_HDROP, h) != nullptr;
    UINT cf = RegisterClipboardFormatW(CFSTR_PREFERREDDROPEFFECT);
    HGLOBAL he = GlobalAlloc(GMEM_MOVEABLE, sizeof(DWORD));
    if (he) {
        *(DWORD*)GlobalLock(he) = DROPEFFECT_COPY;
        GlobalUnlock(he);
        SetClipboardData(cf, he);
    }
    std::wstring text;
    for (size_t i = 0; i < paths.size(); i++) { if (i) text += L"\r\n"; text += paths[i]; }
    if (HGLOBAL ht = make_text(text)) SetClipboardData(CF_UNICODETEXT, ht);
    CloseClipboard();
    return ok;
}

bool copy_text_to_clipboard(HWND hw, const std::wstring& s) {
    if (!open_clip(hw)) return false;
    EmptyClipboard();
    bool ok = false;
    if (HGLOBAL h = make_text(s)) ok = SetClipboardData(CF_UNICODETEXT, h) != nullptr;
    CloseClipboard();
    return ok;
}

bool recycle_paths(HWND hw, const std::vector<std::wstring>& paths, std::vector<std::wstring>& failed) {
    for (auto& p : paths) {
        std::wstring from = p;
        from.push_back(0);
        from.push_back(0);
        SHFILEOPSTRUCTW op = {};
        op.hwnd = hw;
        op.wFunc = FO_DELETE;
        op.pFrom = from.c_str();
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI;
        int r = SHFileOperationW(&op);
        if (r != 0 || op.fAnyOperationsAborted || path_exists(p)) failed.push_back(p);
    }
    return failed.empty();
}

bool show_properties(HWND hw, const std::wstring& p) {
    SHELLEXECUTEINFOW sei = {};
    sei.cbSize = sizeof sei;
    sei.fMask = SEE_MASK_INVOKEIDLIST | SEE_MASK_FLAG_NO_UI;
    sei.hwnd = hw;
    sei.lpVerb = L"properties";
    sei.lpFile = p.c_str();
    sei.nShow = SW_SHOW;
    return ShellExecuteExW(&sei) != 0;
}

// ---------------------------------------------------------------- system context menu (Shift+right click)
static IContextMenu2* g_cm2 = nullptr;
static IContextMenu3* g_cm3 = nullptr;

LRESULT shell_menu_msg(UINT msg, WPARAM wp, LPARAM lp, bool* handled) {
    *handled = false;
    LRESULT r = 0;
    if (g_cm3) {
        if (SUCCEEDED(g_cm3->HandleMenuMsg2(msg, wp, lp, &r))) { *handled = true; return r; }
    } else if (g_cm2) {
        if (SUCCEEDED(g_cm2->HandleMenuMsg(msg, wp, lp))) { *handled = true; return 0; }
    }
    return 0;
}

bool shell_context_menu(HWND hw, const std::vector<std::wstring>& paths, POINT pt) {
    if (paths.empty()) return false;
    // all items must share the parent folder of the first one
    std::wstring par0, nm;
    split_path(paths[0], par0, nm);
    std::vector<PIDLIST_ABSOLUTE> abs;
    for (auto& p : paths) {
        std::wstring par;
        split_path(p, par, nm);
        if (to_lower(par) != to_lower(par0)) continue;
        PIDLIST_ABSOLUTE pidl = nullptr;
        if (SUCCEEDED(SHParseDisplayName(p.c_str(), nullptr, &pidl, 0, nullptr)) && pidl) abs.push_back(pidl);
        if (abs.size() >= 256) break;
    }
    bool ok = false;
    if (!abs.empty()) {
        IShellFolder* folder = nullptr;
        PCUITEMID_CHILD child = nullptr;
        if (SUCCEEDED(SHBindToParent(abs[0], IID_IShellFolder, (void**)&folder, &child))) {
            std::vector<PCUITEMID_CHILD> kids;
            for (auto a : abs) kids.push_back(ILFindLastID(a));
            IContextMenu* cm = nullptr;
            if (SUCCEEDED(folder->GetUIObjectOf(hw, (UINT)kids.size(), kids.data(), IID_IContextMenu, nullptr, (void**)&cm))) {
                HMENU m = CreatePopupMenu();
                if (SUCCEEDED(cm->QueryContextMenu(m, 0, 1, 0x7FFF, CMF_NORMAL | CMF_EXTENDEDVERBS))) {
                    cm->QueryInterface(IID_IContextMenu3, (void**)&g_cm3);
                    if (!g_cm3) cm->QueryInterface(IID_IContextMenu2, (void**)&g_cm2);
                    UINT cmd = (UINT)TrackPopupMenuEx(m, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, hw, nullptr);
                    if (g_cm3) { g_cm3->Release(); g_cm3 = nullptr; }
                    if (g_cm2) { g_cm2->Release(); g_cm2 = nullptr; }
                    if (cmd > 0) {
                        CMINVOKECOMMANDINFOEX ici = {};
                        ici.cbSize = sizeof ici;
                        ici.fMask = CMIC_MASK_UNICODE | CMIC_MASK_PTINVOKE;
                        if (GetKeyState(VK_CONTROL) < 0) ici.fMask |= CMIC_MASK_CONTROL_DOWN;
                        if (GetKeyState(VK_SHIFT) < 0) ici.fMask |= CMIC_MASK_SHIFT_DOWN;
                        ici.hwnd = hw;
                        ici.lpVerb = MAKEINTRESOURCEA(cmd - 1);
                        ici.lpVerbW = MAKEINTRESOURCEW(cmd - 1);
                        ici.nShow = SW_SHOWNORMAL;
                        ici.ptInvoke = pt;
                        cm->InvokeCommand((LPCMINVOKECOMMANDINFO)&ici);
                    }
                    ok = true;
                }
                DestroyMenu(m);
                cm->Release();
            }
            folder->Release();
        }
    }
    for (auto a : abs) ILFree(a);
    return ok;
}

// ---------------------------------------------------------------- drag out
void drag_paths(HWND hw, const std::vector<std::wstring>& paths) {
    if (paths.empty()) return;
    std::vector<PIDLIST_ABSOLUTE> abs;
    for (auto& p : paths) {
        PIDLIST_ABSOLUTE pidl = ILCreateFromPathW(p.c_str());
        if (pidl) abs.push_back(pidl);
        if (abs.size() >= 4096) break;
    }
    if (!abs.empty()) {
        IDataObject* dobj = nullptr;
        // pidls relative to the desktop (= absolute) work for items from different folders
        if (SUCCEEDED(SHCreateDataObject(nullptr, (UINT)abs.size(), (PCUITEMID_CHILD_ARRAY)abs.data(), nullptr,
                                         IID_IDataObject, (void**)&dobj)) && dobj) {
            // make sure CF_HDROP is present for non-shell drop targets
            FORMATETC fe = {CF_HDROP, nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL};
            if (dobj->QueryGetData(&fe) != S_OK) {
                STGMEDIUM sm = {};
                sm.tymed = TYMED_HGLOBAL;
                sm.hGlobal = make_hdrop(paths);
                if (sm.hGlobal && FAILED(dobj->SetData(&fe, &sm, TRUE))) GlobalFree(sm.hGlobal);
            }
            DWORD eff = 0;
            SHDoDragDrop(hw, dobj, nullptr, DROPEFFECT_COPY | DROPEFFECT_MOVE | DROPEFFECT_LINK, &eff);
            dobj->Release();
        }
    }
    for (auto a : abs) ILFree(a);
}

// ---------------------------------------------------------------- shortcut / autostart
bool create_desktop_shortcut(std::wstring& lnk) {
    wchar_t desk[MAX_PATH];
    if (SHGetFolderPathW(nullptr, CSIDL_DESKTOPDIRECTORY, nullptr, 0, desk) != S_OK) return false;
    lnk = std::wstring(desk) + L"\\千寻.lnk";
    IShellLinkW* sl = nullptr;
    if (FAILED(CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER, IID_IShellLinkW, (void**)&sl))) return false;
    sl->SetPath(exe_path().c_str());
    sl->SetWorkingDirectory(exe_dir().c_str());
    sl->SetIconLocation(exe_path().c_str(), 0);
    sl->SetDescription(L"千寻 文件秒搜");
    IPersistFile* pf = nullptr;
    bool ok = false;
    if (SUCCEEDED(sl->QueryInterface(IID_IPersistFile, (void**)&pf))) {
        DeleteFileW(lnk.c_str());
        ok = SUCCEEDED(pf->Save(lnk.c_str(), TRUE));
        pf->Release();
    }
    sl->Release();
    return ok;
}

static const wchar_t RUN_KEY[] = L"Software\\Microsoft\\Windows\\CurrentVersion\\Run";

std::wstring autostart_command() { return L"\"" + exe_path() + L"\" --hidden"; }

std::wstring autostart_get() {
    HKEY k;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, RUN_KEY, 0, KEY_QUERY_VALUE, &k) != ERROR_SUCCESS) return L"";
    wchar_t buf[2048];
    DWORD type = 0, sz = sizeof buf - sizeof(wchar_t);
    std::wstring r;
    if (RegQueryValueExW(k, L"QianXun", nullptr, &type, (BYTE*)buf, &sz) == ERROR_SUCCESS && (type == REG_SZ || type == REG_EXPAND_SZ)) {
        buf[sz / sizeof(wchar_t)] = 0;
        r = buf;
    }
    RegCloseKey(k);
    return r;
}

bool autostart_set(bool on) {
    HKEY k;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, RUN_KEY, 0, nullptr, 0, KEY_SET_VALUE, nullptr, &k, nullptr) != ERROR_SUCCESS)
        return false;
    LONG r;
    if (on) {
        std::wstring v = autostart_command();
        r = RegSetValueExW(k, L"QianXun", 0, REG_SZ, (const BYTE*)v.c_str(), (DWORD)((v.size() + 1) * sizeof(wchar_t)));
    } else {
        r = RegDeleteValueW(k, L"QianXun");
        if (r == ERROR_FILE_NOT_FOUND) r = ERROR_SUCCESS;
    }
    RegCloseKey(k);
    return r == ERROR_SUCCESS;
}

// ---------------------------------------------------------------- icons
int sys_icon_index(const std::wstring& name, bool isdir, const std::wstring& full) {
    static int folder = -2, file = -2;
    static std::unordered_map<std::wstring, int> by_ext;
    static std::list<std::pair<std::wstring, int>> lru;
    static std::unordered_map<std::wstring, std::list<std::pair<std::wstring, int>>::iterator> by_path;
    SHFILEINFOW sfi;
    if (isdir) {
        if (folder == -2) {
            folder = -1;
            if (SHGetFileInfoW(L"folder", FILE_ATTRIBUTE_DIRECTORY, &sfi, sizeof sfi,
                               SHGFI_SYSICONINDEX | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES))
                folder = sfi.iIcon;
        }
        return folder;
    }
    size_t j = name.rfind(L'.');
    std::wstring ext = (j != std::wstring::npos && j > 0) ? to_lower(name.substr(j + 1)) : L"";
    static const wchar_t* path_exts[] = {L"exe", L"lnk", L"ico", L"url", L"scr", L"cpl", L"msc"};
    bool per_path = false;
    for (auto e : path_exts) if (ext == e) per_path = true;
    if (per_path && !full.empty() && drive_type_of(full) != DRIVE_REMOTE) {
        auto it = by_path.find(full);
        if (it != by_path.end()) {
            lru.splice(lru.begin(), lru, it->second);
            return it->second->second;
        }
        int idx = -1;
        if (SHGetFileInfoW(long_path(full).c_str(), 0, &sfi, sizeof sfi, SHGFI_SYSICONINDEX | SHGFI_SMALLICON)) idx = sfi.iIcon;
        if (idx < 0 && SHGetFileInfoW((L"x." + ext).c_str(), FILE_ATTRIBUTE_NORMAL, &sfi, sizeof sfi,
                                      SHGFI_SYSICONINDEX | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES))
            idx = sfi.iIcon;
        lru.push_front({full, idx});
        by_path[full] = lru.begin();
        if (lru.size() > 2000) { by_path.erase(lru.back().first); lru.pop_back(); }
        return idx;
    }
    if (ext.empty()) {
        if (file == -2) {
            file = -1;
            if (SHGetFileInfoW(L"file", FILE_ATTRIBUTE_NORMAL, &sfi, sizeof sfi,
                               SHGFI_SYSICONINDEX | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES))
                file = sfi.iIcon;
        }
        return file;
    }
    auto it = by_ext.find(ext);
    if (it != by_ext.end()) return it->second;
    int idx = -1;
    if (SHGetFileInfoW((L"x." + ext).c_str(), FILE_ATTRIBUTE_NORMAL, &sfi, sizeof sfi,
                       SHGFI_SYSICONINDEX | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES))
        idx = sfi.iIcon;
    by_ext[ext] = idx;
    return idx;
}

// ---------------------------------------------------------------- file dialogs (IFileDialog, Vista+; folder fallback SHBrowseForFolder)
std::wstring pick_folder(HWND owner, const std::wstring& title) {
    std::wstring res;
    IFileOpenDialog* d = nullptr;
    if (SUCCEEDED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER, IID_IFileOpenDialog, (void**)&d))) {
        DWORD opt = 0;
        d->GetOptions(&opt);
        d->SetOptions(opt | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);
        d->SetTitle(title.c_str());
        if (SUCCEEDED(d->Show(owner))) {
            IShellItem* it = nullptr;
            if (SUCCEEDED(d->GetResult(&it))) {
                PWSTR p = nullptr;
                if (SUCCEEDED(it->GetDisplayName(SIGDN_FILESYSPATH, &p))) { res = p; CoTaskMemFree(p); }
                it->Release();
            }
        }
        d->Release();
        return res;
    }
    BROWSEINFOW bi = {};
    bi.hwndOwner = owner;
    bi.lpszTitle = title.c_str();
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
    PIDLIST_ABSOLUTE pidl = SHBrowseForFolderW(&bi);
    if (pidl) {
        wchar_t buf[MAX_PATH];
        if (SHGetPathFromIDListW(pidl, buf)) res = buf;
        CoTaskMemFree(pidl);
    }
    return res;
}

std::wstring pick_save_file(HWND owner, const std::wstring& title, const std::wstring& def_name) {
    std::wstring res;
    IFileSaveDialog* d = nullptr;
    if (FAILED(CoCreateInstance(CLSID_FileSaveDialog, nullptr, CLSCTX_INPROC_SERVER, IID_IFileSaveDialog, (void**)&d)))
        return res;
    COMDLG_FILTERSPEC spec[] = {{L"CSV 文件 (*.csv)", L"*.csv"}};
    d->SetFileTypes(1, spec);
    d->SetDefaultExtension(L"csv");
    d->SetFileName(def_name.c_str());
    d->SetTitle(title.c_str());
    if (SUCCEEDED(d->Show(owner))) {
        IShellItem* it = nullptr;
        if (SUCCEEDED(d->GetResult(&it))) {
            PWSTR p = nullptr;
            if (SUCCEEDED(it->GetDisplayName(SIGDN_FILESYSPATH, &p))) { res = p; CoTaskMemFree(p); }
            it->Release();
        }
    }
    d->Release();
    return res;
}

} // namespace qx
