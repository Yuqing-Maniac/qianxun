// 千寻 —— 索引引擎（Windows）：多线程扫描、ReadDirectoryChangesW 实时监控、盘符插拔、缓存。
// 对照 qianxun.py 的 Engine / EngineWin / DirWatcherWin。
#pragma once
#include "app.h"
#include "index.h"
#include <thread>
#include <mutex>
#include <deque>
#include <set>
#include <map>
#include <unordered_set>
#include <functional>

namespace qx {

struct EngineStatus {
    std::wstring state = L"starting";   // starting loading indexing updating ready error stopped
    std::wstring msg = L"正在启动…";
    size_t watched = 0, dirs = 0;
    bool watcher_ok = true;
};

struct ListItem {
    std::wstring name;
    bool isdir;
    uint8_t flags;
    int64_t size, mtime;
};
enum ListResult { LIST_OK, LIST_GONE, LIST_ERROR };
ListResult list_dir(const std::wstring& path, std::vector<ListItem>& out, DWORD* err = nullptr);
bool dir_mtime(const std::wstring& path, int64_t& mt);

typedef std::unordered_set<std::wstring> ExcludeSet;   // lowercase full paths
// user excludes + <sysroot>\WinSxS + X:\$Recycle.Bin / X:\System Volume Information per root drive (qianxun.py win_excludes)
ExcludeSet make_excludes(const std::vector<std::wstring>& user, const std::vector<std::wstring>& roots);

// Multi-threaded breadth-first scan of the given (already created) dir ids. Returns new dir ids.
std::vector<uint32_t> scan_tree(Index& idx, const std::vector<uint32_t>& start, const ExcludeSet& ex,
                                const std::atomic<bool>* abort, int nthreads,
                                const std::function<void()>& progress = std::function<void()>());

// ---------------------------------------------------------------- watcher
const int WATCH_OVERFLOW = -1, WATCH_LOST = -2;
struct WatchEvent { uint32_t root; int action; std::wstring rel; };

class DirWatcher {
public:
    ~DirWatcher() { close(); }
    bool add(uint32_t did, const std::wstring& path, bool dyn, bool network);
    void remove(uint32_t did);
    void close();
    // Wait up to timeout_ms on all watch events + extra (e.g. a command event). Returns events.
    void wait(DWORD timeout_ms, HANDLE extra, std::vector<WatchEvent>& out);
    bool release_handle(HANDLE h);         // any thread (device query-remove)
    void register_all(HWND hwnd);          // device notifications for removable roots
    bool has(uint32_t did) const;
    size_t count() const;
private:
    struct Rec {
        HANDLE h = INVALID_HANDLE_VALUE, ev = nullptr;
        OVERLAPPED ov{};
        std::vector<char> buf;   // DWORD-aligned via vector<char> of malloc'd memory
        std::wstring path;
        bool pending = false, dead = false, released = false, dyn = false;
        HDEVNOTIFY dn = nullptr;
    };
    bool issue(Rec& r);
    void reg(Rec& r, HWND hwnd);
    mutable std::mutex m_;
    std::map<uint32_t, Rec*> w_;
    std::vector<Rec*> grave_;
};

// ---------------------------------------------------------------- engine
class Engine {
public:
    Engine(Index& idx, const Config& cfg, bool cli = false);
    ~Engine();
    void start();
    void post_quit();
    void post_rebuild(const Config& cfg);
    void post_refresh_path(const std::wstring& dir);
    void post_refresh_all();
    void post_save();
    void post_devnotify();
    void post_drive_check();
    bool join(DWORD ms);
    EngineStatus status() const;
    void set_hwnd(HWND h) { hwnd_ = h; }
    bool release_handle(HANDLE h) { return watcher_.release_handle(h); }
    uint64_t saved_version() const { return saved_version_; }
    std::vector<std::wstring> roots() const;
    bool cache_loaded() const { return cache_loaded_; }
    double scan_seconds() const { return scan_seconds_; }

private:
    struct Cmd { int op; std::wstring arg; Config cfg; };
    void post(const Cmd& c);
    void run();
    void run2();
    bool command(const Cmd& c);
    void loop();
    void setup_paths();
    std::vector<std::pair<std::wstring, bool>> root_pairs();
    ExcludeSet compute_excludes() const;
    CacheHeader header() const;
    void full_scan();
    void init_watches();
    void close_watches();
    void watch(const std::vector<uint32_t>& dids);
    void unwatch(const std::vector<uint32_t>& dids);
    void refresh(uint32_t did);
    void refresh_dir(uint32_t did, const std::set<std::wstring>& force, std::vector<uint32_t>& added,
                     std::vector<uint32_t>& removed);
    void catch_up(bool only_unwatched, const std::vector<uint32_t>* roots = nullptr);
    bool under(const std::wstring& p, const std::vector<std::wstring>& prefs) const;
    std::vector<std::wstring> unwatched_prefixes() const;
    uint32_t nearest_dir(const std::wstring& path) const;
    void handle_events(std::vector<WatchEvent>& evs, std::set<uint32_t>& dirty,
                       std::map<uint32_t, std::set<std::wstring>>& touched);
    void apply_touched(std::map<uint32_t, std::set<std::wstring>>& touched);
    bool sync_roots();
    bool check_drives();
    void retry_watches();
    void remove_root(uint32_t rd);
    void set_ready();
    void compute_order();
    void save();
    void start_sweep(int scope, const std::vector<std::wstring>& prefs = {});
    bool sweep_step(int budget);
    void set_status(const wchar_t* state, const std::wstring& msg);
    void set_msg(const std::wstring& msg);

    Index& idx_;
    Config cfg_;
    bool cli_;
    std::thread th_;
    mutable std::mutex sm_;
    EngineStatus st_;
    std::mutex cm_;
    std::deque<Cmd> cmds_;
    HANDLE cmd_ev_ = nullptr;
    std::atomic<bool> abort_{false};
    bool stopping_ = false;
    std::atomic<HWND> hwnd_{nullptr};
    std::vector<std::wstring> roots_;
    std::set<std::wstring> dyn_, net_;   // lowercase root keys
    ExcludeSet excluded_;
    DirWatcher watcher_;
    bool watcher_ok_ = true;
    std::set<uint32_t> watched_;           // root dids with an active watch
    std::map<std::wstring, double> hold_;  // root key → no re-watch before
    std::map<uint32_t, std::set<std::wstring>> moved_;
    DWORD drive_mask_ = 0;
    std::atomic<uint64_t> saved_version_{0};
    uint64_t order_version_ = 0;
    double last_order_ = 0;
    bool skip_sweep_ = false;
    int sweep_scope_ = -1;                 // -1 none, 0 all, 1 unwatched, 2 prefixes
    std::vector<std::wstring> sweep_prefs_;
    uint32_t sweep_pos_ = 0;
    bool cache_loaded_ = false;
    double scan_seconds_ = 0;
    int scan_threads_ = 4;
};

std::wstring index_file();

} // namespace qx
