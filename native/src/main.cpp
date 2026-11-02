// 千寻 QianXun —— Windows 原生版入口：命令行测试接口 / 单实例 / 消息循环
#include "ui.h"
#include "textutil.h"
#include <shellapi.h>
#include <shlobj.h>
#include <ole2.h>

namespace qx { int cli_main(int argc, wchar_t** argv); }
using namespace qx;

static LONG WINAPI crash_filter(EXCEPTION_POINTERS* ep) {
    log_line(L"unhandled exception 0x%08lx at %p", ep->ExceptionRecord->ExceptionCode, ep->ExceptionRecord->ExceptionAddress);
    return EXCEPTION_CONTINUE_SEARCH;
}

static void console_print(const std::wstring& s) {
    typedef BOOL(WINAPI * AttachConsole_t)(DWORD);
    AttachConsole_t ac = (AttachConsole_t)GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "AttachConsole");
    HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
    if ((!h || h == INVALID_HANDLE_VALUE) && ac && ac((DWORD)-1)) h = GetStdHandle(STD_OUTPUT_HANDLE);
    if (!h || h == INVALID_HANDLE_VALUE) return;
    std::string u = to_utf8(s) + "\n";
    DWORD w;
    WriteFile(h, u.data(), (DWORD)u.size(), &w, nullptr);
}

// Hand the request to the running instance (WM_COPYDATA). Returns true when delivered.
static bool notify_running(const char* msg) {
    for (int i = 0; i < 50; i++) {   // the first instance may still be starting: retry up to ~5 s
        HWND h = FindWindowW(MAIN_CLASS, nullptr);
        if (h) {
            AllowSetForegroundWindow(ASFW_ANY);
            COPYDATASTRUCT cds;
            cds.dwData = COPYDATA_MAGIC;
            cds.cbData = (DWORD)strlen(msg);
            cds.lpData = (void*)msg;
            DWORD_PTR r = 0;
            if (SendMessageTimeoutW(h, WM_COPYDATA, 0, (LPARAM)&cds, SMTO_ABORTIFHUNG, 3000, &r)) return true;
        }
        Sleep(100);
    }
    return false;
}

int WINAPI wWinMain(HINSTANCE hinst, HINSTANCE, PWSTR, int) {
    text_init();
    int argc = 0;
    wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    bool cli = false, toggle = false, hidden = false;
    for (int i = 1; i < argc; i++) {
        std::wstring a = argv[i];
        if (a == L"--cli" || a == L"--cli-watch") cli = true;
        else if (a == L"--toggle") toggle = true;
        else if (a == L"--hidden") hidden = true;
        else if (a == L"--version") { console_print(std::wstring(L"qianxun ") + QX_VERSION_W); return 0; }
    }
    if (cli) {
        int r = cli_main(argc, argv);
        LocalFree(argv);
        return r;
    }
    LocalFree(argv);
    SetUnhandledExceptionFilter(crash_filter);
    // pre-Win10 fallback when the manifest is ignored
    typedef BOOL(WINAPI * SetDPIAware_t)();
    if (auto f = (SetDPIAware_t)GetProcAddress(GetModuleHandleW(L"user32.dll"), "SetProcessDPIAware")) {
        if (!GetProcAddress(GetModuleHandleW(L"user32.dll"), "GetDpiForWindow")) f();
    }
    typedef HRESULT(WINAPI * SetAppId_t)(PCWSTR);
    if (auto f = (SetAppId_t)GetProcAddress(GetModuleHandleW(L"shell32.dll"), "SetCurrentProcessExplicitAppUserModelID"))
        f(L"QianXun.FileSearch");

    const char* msg = toggle ? "toggle" : (hidden ? "hidden" : "show");
    HANDLE mutex = CreateMutexW(nullptr, FALSE, L"Local\\QianXun.Native.SingleInstance");
    if (mutex && GetLastError() == ERROR_ALREADY_EXISTS) {
        notify_running(msg);
        CloseHandle(mutex);
        return 0;
    }

    OleInitialize(nullptr);
    INITCOMMONCONTROLSEX icc = {sizeof icc, ICC_LISTVIEW_CLASSES | ICC_BAR_CLASSES | ICC_STANDARD_CLASSES |
                                                ICC_HOTKEY_CLASS | ICC_WIN95_CLASSES};
    InitCommonControlsEx(&icc);
    g.hinst = hinst;
    g.icon_big = (HICON)LoadImageW(hinst, MAKEINTRESOURCEW(1), IMAGE_ICON, GetSystemMetrics(SM_CXICON),
                                   GetSystemMetrics(SM_CYICON), LR_DEFAULTCOLOR);
    g.icon_small = (HICON)LoadImageW(hinst, MAKEINTRESOURCEW(1), IMAGE_ICON, GetSystemMetrics(SM_CXSMICON),
                                     GetSystemMetrics(SM_CYSMICON), LR_DEFAULTCOLOR);
    g.cfg = load_config();
    log_line(L"QianXun %ls native started (%ls)", QX_VERSION_W, sizeof(void*) == 8 ? L"x64" : L"x86");

    SYSTEM_INFO si;
    GetSystemInfo(&si);
    Index idx;
    ThreadPool pool(std::max(1, std::min(8, (int)si.dwNumberOfProcessors)));
    Engine engine(idx, g.cfg);
    SearchService search(idx, pool);
    g.idx = &idx;
    g.pool = &pool;
    g.engine = &engine;
    g.search = &search;
    engine.start();
    if (!create_main_window(!hidden)) {
        log_line(L"create window failed: %lu", GetLastError());
        engine.post_quit();
        engine.join(15000);
        return 1;
    }
    search.start(g.hwnd);
    engine.set_hwnd(g.hwnd);
    engine.post_devnotify();
    // keep the autostart entry pointing at this exe if the folder was moved
    std::wstring cur = autostart_get();
    if (!cur.empty() && cur != autostart_command()) autostart_set(true);

    MSG m;
    while (GetMessageW(&m, nullptr, 0, 0) > 0) {
        if (g.accel && g.hwnd && (m.hwnd == g.hwnd || IsChild(g.hwnd, m.hwnd)) && TranslateAcceleratorW(g.hwnd, g.accel, &m))
            continue;
        TranslateMessage(&m);
        DispatchMessageW(&m);
    }
    search.stop();
    if (!g.quitting) { engine.post_quit(); }
    engine.join(15000);
    OleUninitialize();
    if (mutex) CloseHandle(mutex);
    log_line(L"QianXun exited");
    // the engine thread may still be saving after the timeout: don't run destructors that would race it
    ExitProcess(0);
}
