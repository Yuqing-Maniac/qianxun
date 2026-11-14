// 千寻 —— 界面公共声明
#pragma once
#include "app.h"
#include "engine.h"
#include "search.h"
#include <commctrl.h>
#include <atomic>

namespace qx {

enum {
    WM_APP_RESULT = WM_APP + 1,
    WM_APP_TRAY = WM_APP + 2,
};
const ULONG_PTR COPYDATA_MAGIC = 0x51584E31;   // 'QXN1'
const wchar_t MAIN_CLASS[] = L"QianXun.Native.Main";

struct SearchReq {
    uint64_t seq = 0;
    std::wstring text;
    QueryOpts opts;
    int filter = 0, sort_col = 0;
    bool sort_desc = false, keep_view = false;
};
struct SearchRes {
    uint64_t seq = 0, gen = 0, version = 0, struct_version = 0;
    std::vector<uint32_t> rows;
    std::vector<std::wstring> highlights;
    std::wstring error;
    bool regex = false, unsorted = false, keep_view = false, stat_query = false;
    double ms = 0;
};

// Background search thread: latest request wins, older ones are cancelled.
class SearchService {
public:
    SearchService(Index& idx, ThreadPool& pool) : idx_(idx), pool_(pool) {}
    ~SearchService() { stop(); }
    void start(HWND target);
    void request(const SearchReq& r);
    void stop();
    uint64_t latest() const { return latest_.load(); }
private:
    void loop();
    Index& idx_;
    ThreadPool& pool_;
    HWND target_ = nullptr;
    std::thread th_;
    std::mutex m_;
    std::condition_variable cv_;
    bool has_ = false, stop_ = false;
    SearchReq req_;
    std::atomic<uint64_t> latest_{0};
};

struct App {
    HINSTANCE hinst = nullptr;
    HWND hwnd = nullptr, edit = nullptr, combo = nullptr, list = nullptr, status = nullptr;
    HACCEL accel = nullptr;
    HICON icon_big = nullptr, icon_small = nullptr;
    Config cfg;
    Index* idx = nullptr;
    Engine* engine = nullptr;
    ThreadPool* pool = nullptr;
    SearchService* search = nullptr;
    // fonts / dpi
    int dpi = 96;
    HFONT font = nullptr, font_bold = nullptr, font_big = nullptr;
    int row_h = 22;
    HIMAGELIST row_il = nullptr;     // blank image list that sets the row height
    HIMAGELIST sys_il = nullptr;     // system small icon list
    // results
    std::vector<uint32_t> rows;
    uint64_t rows_gen = 0, last_version = 0, last_struct = 0;
    std::vector<std::wstring> highlights;
    bool rows_unsorted = false, stat_query = false;
    double last_search = 0, search_ms = 0;
    std::wstring error;
    uint64_t seq = 0;
    bool search_pending = false;
    // window state
    bool quitting = false, tray_ok = false, hotkey_ok = false;
    UINT taskbar_created = 0;
    DWORD last_deactivate = 0;
    std::wstring state_text;
    bool msg_active = false;
    int sort_col = 0;
    bool sort_desc = false;
};
extern App g;

inline int S(int v) { return MulDiv(v, g.dpi, 96); }

// ui_main.cpp
bool create_main_window(bool show);
void do_search(bool keep_view = false);
void update_count();
void show_message(const std::wstring& s, UINT ms);
void toggle_window();
void show_raise();
void quit_app();
void save_state();
void register_hotkey();
std::vector<uint32_t> selected_entries();
std::vector<std::wstring> selected_paths();

// ui_dialogs.cpp
void show_help(HWND owner);
void show_about(HWND owner);
bool show_options(HWND owner, Config& cfg, bool& autostart);
bool input_box(HWND owner, const std::wstring& title, const std::wstring& label, std::wstring& value);
void apply_font_tree(HWND w, HFONT f);

// shell.cpp
void open_path(const std::wstring& p);
void show_in_folder(const std::wstring& p);
bool open_terminal(const std::wstring& dir);
bool copy_files_to_clipboard(HWND h, const std::vector<std::wstring>& paths);
bool copy_text_to_clipboard(HWND h, const std::wstring& s);
bool recycle_paths(HWND h, const std::vector<std::wstring>& paths, std::vector<std::wstring>& failed);
bool show_properties(HWND h, const std::wstring& p);
bool shell_context_menu(HWND h, const std::vector<std::wstring>& paths, POINT pt);
LRESULT shell_menu_msg(UINT msg, WPARAM wp, LPARAM lp, bool* handled);
void drag_paths(HWND h, const std::vector<std::wstring>& paths);
bool create_desktop_shortcut(std::wstring& lnk);
void ensure_desktop_shortcut();
std::wstring autostart_get();
bool autostart_set(bool on);
std::wstring autostart_command();
UINT drive_type_of(const std::wstring& p);
int sys_icon_index(const std::wstring& name, bool isdir, const std::wstring& full);
std::wstring pick_folder(HWND owner, const std::wstring& title);
std::wstring pick_save_file(HWND owner, const std::wstring& title, const std::wstring& def_name);
int msg_box(HWND owner, const std::wstring& text, UINT flags, const std::wstring& title = QX_APP_NAME);

} // namespace qx
