// 千寻 —— 索引引擎实现（Windows）
#include "engine.h"
#include "textutil.h"
#include <dbt.h>
#include <algorithm>
#include <condition_variable>
#include <unordered_map>

namespace qx {

std::wstring index_file() { return data_dir() + L"\\index.bin"; }

static int64_t ft64(const FILETIME& f) { return ((int64_t)f.dwHighDateTime << 32) | f.dwLowDateTime; }

// ================================================================ listing
ListResult list_dir(const std::wstring& path, std::vector<ListItem>& out, DWORD* perr) {
    out.clear();
    std::wstring pat = path;
    if (pat.empty() || pat.back() != L'\\') pat += L'\\';
    pat += L'*';
    pat = long_path(pat);
    WIN32_FIND_DATAW fd;
    static std::atomic<bool> basic_ok{true};
    HANDLE h = INVALID_HANDLE_VALUE;
    if (basic_ok) {
        h = FindFirstFileExW(pat.c_str(), FindExInfoBasic, &fd, FindExSearchNameMatch, nullptr,
                             FIND_FIRST_EX_LARGE_FETCH);
        if (h == INVALID_HANDLE_VALUE && GetLastError() == ERROR_INVALID_PARAMETER) basic_ok = false;   // pre-Win7
    }
    if (h == INVALID_HANDLE_VALUE && !basic_ok) h = FindFirstFileW(pat.c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) {
        DWORD e = GetLastError();
        if (perr) *perr = e;
        if (e == ERROR_FILE_NOT_FOUND || e == ERROR_NO_MORE_FILES) return LIST_OK;   // empty drive root
        if (e == ERROR_PATH_NOT_FOUND || e == ERROR_DIRECTORY || e == ERROR_INVALID_NAME) return LIST_GONE;
        return LIST_ERROR;
    }
    do {
        const wchar_t* n = fd.cFileName;
        if (n[0] == L'.' && (n[1] == 0 || (n[1] == L'.' && n[2] == 0))) continue;
        ListItem it;
        it.name = n;
        DWORD a = fd.dwFileAttributes;
        it.isdir = (a & FILE_ATTRIBUTE_DIRECTORY) != 0;
        it.flags = 0;
        if (a & FILE_ATTRIBUTE_REPARSE_POINT) {
            DWORD tag = fd.dwReserved0;
            if (!tag || (tag & 0x20000000)) it.flags |= EF_NOREC;   // name surrogate: junction, symlink, mount point
            if (tag == IO_REPARSE_TAG_SYMLINK) it.isdir = false;    // like Python DirEntry.is_dir(follow_symlinks=False)
        }
        it.size = it.isdir ? -1 : (int64_t)(((uint64_t)fd.nFileSizeHigh << 32) | fd.nFileSizeLow);
        it.mtime = ft64(fd.ftLastWriteTime);
        out.push_back(std::move(it));
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return LIST_OK;
}

bool dir_mtime(const std::wstring& path, int64_t& mt) {
    WIN32_FILE_ATTRIBUTE_DATA d;
    if (!GetFileAttributesExW(long_path(path).c_str(), GetFileExInfoStandard, &d)) return false;
    mt = ft64(d.ftLastWriteTime);
    return true;
}

// ================================================================ parallel scan
std::vector<uint32_t> scan_tree(Index& idx, const std::vector<uint32_t>& start, const ExcludeSet& ex,
                                const std::atomic<bool>* abort, int nthreads, const std::function<void()>& progress) {
    std::mutex m;
    std::condition_variable cv;
    std::deque<uint32_t> q(start.begin(), start.end());
    std::vector<uint32_t> new_dirs;
    int active = 0;
    std::atomic<size_t> count{0};
    double last_prog = now_sec();
    auto worker = [&](int wid) {
        std::vector<ListItem> items;
        std::vector<uint32_t> local;
        while (true) {
            uint32_t did;
            {
                std::unique_lock<std::mutex> lk(m);
                cv.wait(lk, [&] { return !q.empty() || active == 0 || (abort && abort->load()); });
                if (abort && abort->load()) return;
                if (q.empty()) { if (active == 0) return; else continue; }
                did = q.front();
                q.pop_front();
                active++;
            }
            std::wstring path;
            int64_t known_mt = 0;
            {
                ReadGuard g(idx.lock);
                if (did < idx.dirs.size() && !idx.dirs[did].dead) { path = idx.dirs[did].path; known_mt = idx.dirs[did].mtime; }
            }
            local.clear();
            if (!path.empty()) {
                int64_t mt = known_mt;
                if (mt <= 0) dir_mtime(path, mt);
                if (list_dir(path, items) == LIST_OK) {
                    WriteGuard g(idx.lock);
                    if (!idx.dirs[did].dead) {
                        idx.dirs[did].mtime = mt;
                        for (auto& it : items) {
                            uint32_t i = idx.add_entry(did, it.name.data(), it.name.size(), it.isdir, it.size, it.mtime, it.flags);
                            if (it.isdir && !(it.flags & EF_NOREC)) {
                                std::wstring full = join_path(idx.dirs[did].path, it.name);
                                std::wstring low = to_lower(full);
                                if (ex.count(low) || idx.table.find(idx.dirs, low.data(), low.size()) != NONE) continue;
                                uint32_t nd = idx.new_dir(full, i);
                                idx.dirs[nd].mtime = it.mtime > 0 ? it.mtime : 0;
                                local.push_back(nd);
                            }
                        }
                        idx.version++;
                    }
                }
            }
            count++;
            {
                std::lock_guard<std::mutex> lk(m);
                for (uint32_t d : local) { q.push_back(d); new_dirs.push_back(d); }
                active--;
                if (wid == 0 && progress && now_sec() - last_prog > 0.25) { last_prog = now_sec(); progress(); }
            }
            cv.notify_all();
        }
    };
    if (nthreads <= 1) {
        worker(0);
    } else {
        std::vector<std::thread> ts;
        for (int i = 1; i < nthreads; i++) ts.emplace_back(worker, i);
        worker(0);
        for (auto& t : ts) t.join();
    }
    return new_dirs;
}

// ================================================================ watcher
bool DirWatcher::issue(Rec& r) {
    ResetEvent(r.ev);
    BOOL ok = ReadDirectoryChangesW(r.h, r.buf.data(), (DWORD)r.buf.size(), TRUE,
                                    FILE_NOTIFY_CHANGE_FILE_NAME | FILE_NOTIFY_CHANGE_DIR_NAME |
                                        FILE_NOTIFY_CHANGE_SIZE | FILE_NOTIFY_CHANGE_LAST_WRITE,
                                    nullptr, &r.ov, nullptr);
    r.pending = ok != 0;
    return r.pending;
}

bool DirWatcher::add(uint32_t did, const std::wstring& path, bool dyn, bool network) {
    HANDLE h = CreateFileW(long_path(path).c_str(), FILE_LIST_DIRECTORY,
                           FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
                           FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OVERLAPPED, nullptr);
    if (h == INVALID_HANDLE_VALUE) {
        log_line(L"watch %ls: CreateFileW error %lu", path.c_str(), GetLastError());
        return false;
    }
    Rec* r = new Rec();
    r->h = h;
    r->ev = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    r->ov.hEvent = r->ev;
    r->path = path;
    r->dyn = dyn;
    r->buf.resize(network ? 64 * 1024 : 512 * 1024);
    if (!issue(*r)) {
        DWORD e = GetLastError();
        bool ok = false;
        if (e == ERROR_INVALID_PARAMETER && r->buf.size() > 64 * 1024) {   // network share: buffer ≤ 64 KB
            r->buf.resize(64 * 1024);
            ok = issue(*r);
        }
        if (!ok) {
            log_line(L"watch %ls: ReadDirectoryChangesW error %lu", path.c_str(), GetLastError());
            CloseHandle(h);
            CloseHandle(r->ev);
            delete r;
            return false;
        }
    }
    std::lock_guard<std::mutex> g(m_);
    auto it = w_.find(did);
    if (it != w_.end()) {   // should not happen; replace
        Rec* o = it->second;
        if (!o->released) { CancelIoEx(o->h, &o->ov); CloseHandle(o->h); }
        grave_.push_back(o);
    }
    w_[did] = r;
    return true;
}

void DirWatcher::reg(Rec& r, HWND hwnd) {
    if (!hwnd || r.dn || r.dead || r.released) return;
    DEV_BROADCAST_HANDLE f = {};
    f.dbch_size = sizeof f;
    f.dbch_devicetype = DBT_DEVTYP_HANDLE;
    f.dbch_handle = r.h;
    r.dn = RegisterDeviceNotificationW(hwnd, &f, DEVICE_NOTIFY_WINDOW_HANDLE);
}

void DirWatcher::register_all(HWND hwnd) {
    std::lock_guard<std::mutex> g(m_);
    for (auto& kv : w_) if (kv.second->dyn) reg(*kv.second, hwnd);
}

bool DirWatcher::release_handle(HANDLE h) {
    std::lock_guard<std::mutex> g(m_);
    for (auto& kv : w_) {
        Rec& r = *kv.second;
        if (r.h == h && !r.released) {
            r.released = true;
            CancelIoEx(h, &r.ov);
            if (r.dn) { UnregisterDeviceNotification(r.dn); r.dn = nullptr; }
            CloseHandle(h);
            SetEvent(r.ev);   // wake the engine so it notices
            return true;
        }
    }
    return false;
}

bool DirWatcher::has(uint32_t did) const {
    std::lock_guard<std::mutex> g(m_);
    auto it = w_.find(did);
    return it != w_.end() && !it->second->dead;
}

size_t DirWatcher::count() const {
    std::lock_guard<std::mutex> g(m_);
    return w_.size();
}

static void parse_notify(const char* data, DWORD n, uint32_t did, std::vector<WatchEvent>& out) {
    DWORD pos = 0;
    while (pos + 12 <= n) {
        const FILE_NOTIFY_INFORMATION* fi = (const FILE_NOTIFY_INFORMATION*)(data + pos);
        DWORD ln = fi->FileNameLength;
        if (pos + 12 + ln > n) break;
        out.push_back(WatchEvent{did, (int)fi->Action, std::wstring(fi->FileName, ln / sizeof(wchar_t))});
        if (fi->NextEntryOffset == 0 || fi->NextEntryOffset < 12) break;
        pos += fi->NextEntryOffset;
    }
}

void DirWatcher::wait(DWORD timeout, HANDLE extra, std::vector<WatchEvent>& out) {
    std::vector<std::pair<uint32_t, Rec*>> recs;
    {
        std::lock_guard<std::mutex> g(m_);
        for (auto& kv : w_) if (!kv.second->dead) recs.push_back(kv);
    }
    std::vector<HANDLE> hs;
    if (extra) hs.push_back(extra);
    for (auto& r : recs) { if (hs.size() >= MAXIMUM_WAIT_OBJECTS) break; hs.push_back(r.second->ev); }
    if (hs.empty()) { Sleep(timeout); return; }
    DWORD rc = WaitForMultipleObjects((DWORD)hs.size(), hs.data(), FALSE, timeout);
    if (rc == WAIT_FAILED) { Sleep(timeout); return; }
    if (rc == WAIT_TIMEOUT && recs.size() + (extra ? 1 : 0) <= MAXIMUM_WAIT_OBJECTS) return;
    for (auto& kv : recs) {
        uint32_t did = kv.first;
        Rec& r = *kv.second;
        std::lock_guard<std::mutex> g(m_);
        if (r.dead) continue;
        if (r.released) {
            r.dead = true;
            out.push_back(WatchEvent{did, WATCH_LOST, L"released"});
            continue;
        }
        DWORD n = 0;
        if (!GetOverlappedResult(r.h, &r.ov, &n, FALSE)) {
            DWORD e = GetLastError();
            if (e == ERROR_IO_INCOMPLETE) continue;
            r.pending = false;
            if (e == ERROR_NOTIFY_ENUM_DIR) {
                out.push_back(WatchEvent{did, WATCH_OVERFLOW, L""});
                if (issue(r)) continue;
            }
            r.dead = true;
            log_line(L"watch %ls lost: error %lu", r.path.c_str(), e);
            out.push_back(WatchEvent{did, WATCH_LOST, L""});
            continue;
        }
        r.pending = false;
        if (n == 0) out.push_back(WatchEvent{did, WATCH_OVERFLOW, L""});
        else parse_notify(r.buf.data(), n, did, out);
        if (!issue(r)) {
            r.dead = true;
            log_line(L"watch %ls lost on re-issue: error %lu", r.path.c_str(), GetLastError());
            out.push_back(WatchEvent{did, WATCH_LOST, L""});
        }
    }
}

void DirWatcher::remove(uint32_t did) {
    Rec* r;
    {
        std::lock_guard<std::mutex> g(m_);
        auto it = w_.find(did);
        if (it == w_.end()) return;
        r = it->second;
        w_.erase(it);
        if (r->dn) { UnregisterDeviceNotification(r->dn); r->dn = nullptr; }
        if (!r->released) {
            if (r->pending) CancelIoEx(r->h, &r->ov);
            CloseHandle(r->h);
            r->released = true;
        }
    }
    if (r->pending) {
        DWORD n;
        // wait for the cancelled I/O to finish before freeing the buffer/OVERLAPPED
        if (WaitForSingleObject(r->ev, 2000) != WAIT_OBJECT_0) { grave_.push_back(r); return; }
        (void)n;
    }
    CloseHandle(r->ev);
    delete r;
}

void DirWatcher::close() {
    std::vector<uint32_t> ids;
    {
        std::lock_guard<std::mutex> g(m_);
        for (auto& kv : w_) ids.push_back(kv.first);
    }
    for (uint32_t d : ids) remove(d);
}

// ================================================================ engine
enum { C_QUIT, C_REBUILD, C_REFRESH_PATH, C_REFRESH_ALL, C_SAVE, C_DEVNOTIFY, C_DRIVE_CHECK };

Engine::Engine(Index& idx, const Config& cfg, bool cli) : idx_(idx), cfg_(cfg), cli_(cli) {
    cmd_ev_ = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    scan_threads_ = std::max(2, std::min(8, (int)si.dwNumberOfProcessors * 2));
}

Engine::~Engine() {
    if (th_.joinable()) { post_quit(); th_.join(); }
    if (cmd_ev_) CloseHandle(cmd_ev_);
}

void Engine::start() { th_ = std::thread([this] { run(); }); }

void Engine::post(const Cmd& c) {
    if (c.op == C_REBUILD || c.op == C_QUIT) abort_ = true;
    {
        std::lock_guard<std::mutex> g(cm_);
        cmds_.push_back(c);
    }
    SetEvent(cmd_ev_);
}
void Engine::post_quit() { post(Cmd{C_QUIT, L"", Config()}); }
void Engine::post_rebuild(const Config& cfg) { post(Cmd{C_REBUILD, L"", cfg}); }
void Engine::post_refresh_path(const std::wstring& d) { post(Cmd{C_REFRESH_PATH, d, Config()}); }
void Engine::post_refresh_all() { post(Cmd{C_REFRESH_ALL, L"", Config()}); }
void Engine::post_save() { post(Cmd{C_SAVE, L"", Config()}); }
void Engine::post_devnotify() { post(Cmd{C_DEVNOTIFY, L"", Config()}); }
void Engine::post_drive_check() { post(Cmd{C_DRIVE_CHECK, L"", Config()}); }

bool Engine::join(DWORD ms) {
    if (!th_.joinable()) return true;
    HANDLE h = (HANDLE)th_.native_handle();
    if (WaitForSingleObject(h, ms) == WAIT_OBJECT_0) { th_.join(); return true; }
    return false;
}

EngineStatus Engine::status() const {
    std::lock_guard<std::mutex> g(sm_);
    return st_;
}

void Engine::set_status(const wchar_t* state, const std::wstring& msg) {
    std::lock_guard<std::mutex> g(sm_);
    st_.state = state;
    st_.msg = msg;
}

void Engine::set_msg(const std::wstring& msg) {
    std::lock_guard<std::mutex> g(sm_);
    st_.msg = msg;
}

std::vector<std::wstring> Engine::roots() const {
    std::lock_guard<std::mutex> g(sm_);
    return roots_;
}

// ---------------------------------------------------------------- roots / excludes
std::vector<std::pair<std::wstring, bool>> Engine::root_pairs() {
    std::vector<std::pair<std::wstring, bool>> out;
    std::set<std::wstring> seen;
    auto add = [&](const std::wstring& r, bool dyn) {
        std::wstring k = to_lower(r);
        if (seen.insert(k).second) out.push_back({r, dyn});
    };
    DWORD mask = cli_ ? 0 : GetLogicalDrives();
    std::vector<std::pair<std::wstring, UINT>> drives;
    net_.clear();
    for (int i = 0; i < 26; i++) {
        if (!(mask & (1u << i))) continue;
        std::wstring r = std::wstring(1, (wchar_t)(L'A' + i)) + L":\\";
        UINT t = GetDriveTypeW(r.c_str());
        drives.push_back({r, t});
        if (t == DRIVE_REMOTE) net_.insert(to_lower(r));
    }
    auto type_of = [&](const std::wstring& r) -> UINT {
        if (r.size() < 3) return 0;
        std::wstring k = to_lower(r.substr(0, 3));
        for (auto& d : drives) if (to_lower(d.first) == k) return d.second;
        return 0;
    };
    for (auto& r0 : cfg_.roots) {
        if (py_strip(r0).empty()) continue;
        std::wstring r = win_norm_path(r0, cli_);
        UINT t = type_of(r);
        add(r, t == DRIVE_REMOVABLE || t == DRIVE_REMOTE);
    }
    if (cli_) return out;
    if (cfg_.roots.empty())
        for (auto& d : drives) if (d.second == DRIVE_FIXED || d.second == DRIVE_RAMDISK) add(d.first, false);
    for (auto& d : drives) {
        if (d.second == DRIVE_REMOVABLE && cfg_.index_removable) add(d.first, true);
        else if (d.second == DRIVE_REMOTE && cfg_.index_network) add(d.first, true);
    }
    return out;
}

ExcludeSet make_excludes(const std::vector<std::wstring>& user, const std::vector<std::wstring>& roots) {
    ExcludeSet ex;
    for (auto& p : user)
        if (!py_strip(p).empty()) ex.insert(to_lower(win_norm_path(p, false)));
    wchar_t sr[MAX_PATH] = {0};
    DWORD n = GetEnvironmentVariableW(L"SystemRoot", sr, MAX_PATH);
    std::wstring sys = (n && n < MAX_PATH) ? std::wstring(sr) : std::wstring(L"C:\\Windows");
    while (!sys.empty() && sys.back() == L'\\') sys.pop_back();
    if (!sys.empty()) ex.insert(to_lower(sys + L"\\WinSxS"));
    std::set<std::wstring> drives;
    for (auto& r : roots)
        if (r.size() >= 2 && r[1] == L':' && iswalpha(r[0])) drives.insert(std::wstring(1, (wchar_t)towupper(r[0])) + L":");
    for (auto& d : drives) {
        ex.insert(to_lower(d + L"\\$Recycle.Bin"));
        ex.insert(to_lower(d + L"\\System Volume Information"));
    }
    for (auto& r : roots) ex.erase(to_lower(r));
    return ex;
}

ExcludeSet Engine::compute_excludes() const { return make_excludes(cfg_.excludes, roots_); }

CacheHeader Engine::header() const {
    CacheHeader h;
    std::vector<std::wstring> keys;
    for (auto& r : roots_) {
        if (dyn_.count(to_lower(r))) continue;
        h.roots.push_back(r);
        keys.push_back(dir_prefix(to_lower(r)));
    }
    std::vector<std::wstring> sorted(excluded_.begin(), excluded_.end());
    std::sort(sorted.begin(), sorted.end());
    std::vector<std::wstring> top;
    for (auto& e : sorted) {
        bool covered = false;
        for (auto& t : top) {
            std::wstring tp = t;
            while (!tp.empty() && tp.back() == L'\\') tp.pop_back();
            tp += L'\\';
            if (e.compare(0, tp.size(), tp) == 0) { covered = true; break; }
        }
        if (!covered) top.push_back(e);
    }
    for (auto& e : top) {
        std::wstring ep = e + L'\\';
        for (auto& k : keys) if (ep.compare(0, k.size(), k) == 0) { h.excludes.push_back(e); break; }
    }
    return h;
}

void Engine::setup_paths() {
    auto pairs = root_pairs();
    std::vector<std::wstring> rs;
    dyn_.clear();
    for (auto& p : pairs) {
        if (!is_dir(p.first)) continue;
        rs.push_back(p.first);
        if (p.second) dyn_.insert(to_lower(p.first));
    }
    {
        std::lock_guard<std::mutex> g(sm_);
        roots_ = rs;
    }
    excluded_ = compute_excludes();
    drive_mask_ = GetLogicalDrives();
}

bool Engine::under(const std::wstring& p, const std::vector<std::wstring>& prefs) const {
    std::wstring k = dir_prefix(to_lower(p));
    for (auto& x : prefs) if (k.compare(0, x.size(), x) == 0) return true;
    return false;
}

std::vector<std::wstring> Engine::unwatched_prefixes() const {
    std::vector<std::wstring> r;
    for (uint32_t d : idx_.root_dirs())
        if (!watched_.count(d)) r.push_back(dir_prefix(to_lower(idx_.dirs[d].path)));
    return r;
}

// ---------------------------------------------------------------- main
void Engine::run() {
    try {
        run2();
    } catch (const std::exception& e) {
        log_line(L"engine crashed: %hs", e.what());
        set_status(L"error", L"索引线程异常，详见 " + data_dir() + L"\\qianxun.log");
    } catch (...) {
        log_line(L"engine crashed (unknown exception)");
        set_status(L"error", L"索引线程异常，详见 " + data_dir() + L"\\qianxun.log");
    }
}

void Engine::run2() {
    setup_paths();
    bool loaded = false;
    if (!cli_) {
        set_status(L"loading", L"正在加载索引缓存…");
        double t0 = now_sec();
        if (path_exists(index_file())) {
            try {
                loaded = idx_.load(index_file(), header());
            } catch (const std::exception& e) {
                log_line(L"load cache failed: %hs", e.what());
                loaded = false;
            }
        }
        if (loaded) log_line(L"cache loaded: %lld entries in %.2f s", (long long)idx_.live.load(), now_sec() - t0);
    }
    cache_loaded_ = loaded;
    if (loaded) {
        sync_roots();
        saved_version_ = idx_.version.load();
        compute_order();
        set_status(L"updating", L"正在同步自上次以来的变化…");
        init_watches();
        catch_up(false);
    } else {
        full_scan();
    }
    if (!cli_) start_sweep(0);
    set_ready();
    loop();
}

void Engine::full_scan() {
    abort_ = false;
    close_watches();
    {
        WriteGuard g(idx_.lock);
        idx_.clear();
    }
    set_status(L"indexing", L"正在建立索引…");
    std::vector<uint32_t> starts;
    {
        WriteGuard g(idx_.lock);
        for (auto& r : roots_) {
            uint32_t d = idx_.new_dir(r, NONE);
            idx_.dirs[d].mtime = 0;   // fetched when listed
            starts.push_back(d);
        }
    }
    // Watch first: changes made while scanning are buffered by the system and replayed afterwards.
    init_watches();
    double t0 = now_sec();
    scan_tree(idx_, starts, excluded_, &abort_, scan_threads_, [this] {
        set_msg(L"正在建立索引：已收录 " + fmt_thousands(idx_.live.load()) + L" 个文件和目录…");
    });
    scan_seconds_ = now_sec() - t0;
    if (abort_) return;
    log_line(L"full scan: %lld entries, %zu dirs in %.2f s (%d threads)", (long long)idx_.live.load(),
             idx_.dirs.size(), scan_seconds_, scan_threads_);
    set_msg(L"正在排序…");
    compute_order();
    if (!cli_) save();
    skip_sweep_ = true;   // scanning already gave sizes/times
}

// ---------------------------------------------------------------- watches
void Engine::close_watches() {
    watcher_.close();
    watched_.clear();
    moved_.clear();
}

void Engine::init_watches() {
    close_watches();
    watcher_ok_ = true;
    watch(idx_.root_dirs());
    if (HWND h = hwnd_.load()) watcher_.register_all(h);
}

void Engine::watch(const std::vector<uint32_t>& dids) {
    double now = now_sec();
    for (uint32_t d : dids) {
        if (d >= idx_.dirs.size()) continue;
        const DirRec& r = idx_.dirs[d];
        if (r.dead || r.entry != NONE || watched_.count(d)) continue;
        std::wstring k = to_lower(r.path);
        auto h = hold_.find(k);
        if (h != hold_.end() && h->second > now) continue;
        bool ok = watcher_.add(d, r.path, dyn_.count(k) > 0, net_.count(k.substr(0, 3)) > 0);
        if (ok) {
            watched_.insert(d);
            if (dyn_.count(k)) if (HWND hw = hwnd_.load()) watcher_.register_all(hw);
        } else {
            hold_[k] = now + 30;
        }
    }
}

void Engine::unwatch(const std::vector<uint32_t>& dids) {
    for (uint32_t d : dids) {
        if (watched_.erase(d)) watcher_.remove(d);
    }
}

// ---------------------------------------------------------------- refresh
void Engine::refresh(uint32_t did) {
    std::set<std::wstring> force;
    auto it = moved_.find(did);
    if (it != moved_.end()) { force = it->second; moved_.erase(it); }
    std::vector<uint32_t> added, removed;
    refresh_dir(did, force, added, removed);
    if (!removed.empty()) unwatch(removed);
}

void Engine::refresh_dir(uint32_t did, const std::set<std::wstring>& force, std::vector<uint32_t>& added,
                         std::vector<uint32_t>& removed) {
    if (did >= idx_.dirs.size() || idx_.dirs[did].dead) return;
    std::wstring path = idx_.dirs[did].path;
    std::vector<ListItem> items;
    int64_t mt = 0;
    bool have_mt = dir_mtime(path, mt);
    ListResult lr = list_dir(path, items);
    if (lr == LIST_GONE || (lr == LIST_OK && !have_mt && !is_dir(path))) {
        WriteGuard g(idx_.lock);
        uint32_t e = idx_.dirs[did].entry;
        if (e != NONE) idx_.remove_entry(e, removed);
        else {
            std::vector<uint32_t> kids;
            kids.swap(idx_.dirs[did].children);
            for (uint32_t c : kids) idx_.remove_entry(c, removed);
        }
        idx_.version++;
        return;
    }
    if (lr != LIST_OK) return;
    {
        WriteGuard g(idx_.lock);
        if (idx_.dirs[did].dead) return;
        std::unordered_map<std::wstring, uint32_t> cur;
        for (uint32_t c : idx_.dirs[did].children)
            if (idx_.entries[c].kind != K_DEAD) cur[idx_.name_str(c)] = c;
        std::unordered_map<std::wstring, bool> disk;
        for (auto& it : items) disk[it.name] = it.isdir;
        for (auto& kv : cur) {
            auto d = disk.find(kv.first);
            bool isdir = idx_.entries[kv.second].kind == K_DIR;
            if (d == disk.end() || d->second != isdir || (isdir && force.count(kv.first)))
                idx_.remove_entry(kv.second, removed);
        }
        for (auto& it : items) {
            auto c = cur.find(it.name);
            if (c != cur.end() && idx_.entries[c->second].kind != K_DEAD) {
                Entry& e = idx_.entries[c->second];
                e.size = e.kind == K_DIR ? -1 : it.size;
                e.mtime = it.mtime;
                continue;
            }
            uint32_t i = idx_.add_entry(did, it.name.data(), it.name.size(), it.isdir, it.size, it.mtime, it.flags);
            if (it.isdir && !(it.flags & EF_NOREC)) {
                std::wstring full = join_path(path, it.name);
                std::wstring low = to_lower(full);
                if (!excluded_.count(low) && idx_.table.find(idx_.dirs, low.data(), low.size()) == NONE) {
                    uint32_t nd = idx_.new_dir(full, i);
                    idx_.dirs[nd].mtime = it.mtime > 0 ? it.mtime : 0;
                    added.push_back(nd);
                }
            }
        }
        auto& ch = idx_.dirs[did].children;
        ch.erase(std::remove_if(ch.begin(), ch.end(), [&](uint32_t c) { return idx_.entries[c].kind == K_DEAD; }),
                 ch.end());
        idx_.dirs[did].mtime = mt;
        idx_.version++;
    }
    if (!added.empty()) {
        auto more = scan_tree(idx_, added, excluded_, nullptr, added.size() > 4 ? 2 : 1);
        added.insert(added.end(), more.begin(), more.end());
    }
}

void Engine::catch_up(bool only_unwatched, const std::vector<uint32_t>* roots) {
    std::vector<std::wstring> prefs;
    bool use_prefs = false;
    if (roots) {
        use_prefs = true;
        for (uint32_t r : *roots)
            if (r < idx_.dirs.size() && !idx_.dirs[r].dead) prefs.push_back(dir_prefix(to_lower(idx_.dirs[r].path)));
    } else if (only_unwatched) {
        use_prefs = true;
        prefs = unwatched_prefixes();
    }
    if (use_prefs && prefs.empty()) return;
    size_t nd = idx_.dirs.size();
    for (size_t d = 0; d < nd && d < idx_.dirs.size(); d++) {
        if (stopping_ || abort_) return;
        if (idx_.dirs[d].dead) continue;
        if (use_prefs && !under(idx_.dirs[d].path, prefs)) continue;
        int64_t mt;
        if (!dir_mtime(idx_.dirs[d].path, mt)) { refresh((uint32_t)d); continue; }
        if (mt != idx_.dirs[d].mtime) refresh((uint32_t)d);
        if (d % 5000 == 4999) Sleep(1);
    }
}

uint32_t Engine::nearest_dir(const std::wstring& path) const {
    std::wstring p = path;
    while (!p.empty()) {
        std::wstring k = to_lower(p);
        if (excluded_.count(k)) return NONE;
        uint32_t d = idx_.table.find(idx_.dirs, k.data(), k.size());
        if (d != NONE) return d;
        std::wstring par, nm;
        if (!split_path(p, par, nm)) break;
        p = par;
    }
    return NONE;
}

void Engine::handle_events(std::vector<WatchEvent>& evs, std::set<uint32_t>& dirty,
                           std::map<uint32_t, std::set<std::wstring>>& touched) {
    std::set<uint32_t> over;
    std::vector<std::pair<uint32_t, std::wstring>> lost;
    for (auto& ev : evs) {
        if (ev.action == WATCH_OVERFLOW) { over.insert(ev.root); continue; }
        if (ev.action == WATCH_LOST) { lost.push_back({ev.root, ev.rel}); continue; }
        if (ev.root >= idx_.dirs.size() || idx_.dirs[ev.root].dead || ev.rel.empty()) continue;
        std::wstring full = join_path(idx_.dirs[ev.root].path, ev.rel);
        std::wstring parent, name;
        if (!split_path(full, parent, name)) continue;
        std::wstring pk = to_lower(parent);
        uint32_t pd = idx_.table.find(idx_.dirs, pk.data(), pk.size());
        if (pd == NONE) {
            pd = nearest_dir(parent);
            if (pd != NONE) dirty.insert(pd);
            continue;
        }
        if (ev.action == FILE_ACTION_MODIFIED) {
            if (idx_.find_dir(full) != NONE) continue;   // a directory's "modified" = content change, handled via children
            touched[pd].insert(name);
        } else {
            dirty.insert(pd);
            if (ev.action == FILE_ACTION_RENAMED_OLD_NAME || ev.action == FILE_ACTION_RENAMED_NEW_NAME)
                moved_[pd].insert(name);   // swapped dirs keep their names but not their content
        }
    }
    for (uint32_t rd : over) {
        if (rd < idx_.dirs.size() && !idx_.dirs[rd].dead) {
            set_msg(L"事件溢出，正在补扫…");
            log_line(L"watch overflow: %ls", idx_.dirs[rd].path.c_str());
            std::vector<uint32_t> one{rd};
            catch_up(false, &one);
            if (sweep_scope_ < 0) start_sweep(2, {dir_prefix(to_lower(idx_.dirs[rd].path))});
            set_msg(L"");
        }
    }
    double now = now_sec();
    for (auto& l : lost) {
        uint32_t rd = l.first;
        unwatch({rd});
        if (rd >= idx_.dirs.size() || idx_.dirs[rd].dead) continue;
        std::wstring k = to_lower(idx_.dirs[rd].path);
        if (l.second == L"released") { hold_[k] = now + 10.0; continue; }
        if (!is_dir(idx_.dirs[rd].path)) { remove_root(rd); continue; }
        hold_[k] = now + 2.0;
        std::vector<uint32_t> one{rd};
        catch_up(false, &one);
    }
}

void Engine::apply_touched(std::map<uint32_t, std::set<std::wstring>>& touched) {
    std::vector<std::pair<uint32_t, std::pair<int64_t, int64_t>>> upd;
    for (auto& kv : touched) {
        uint32_t d = kv.first;
        if (d >= idx_.dirs.size() || idx_.dirs[d].dead) continue;
        const std::wstring& p = idx_.dirs[d].path;
        for (uint32_t c : idx_.dirs[d].children) {
            const Entry& e = idx_.entries[c];
            if (e.kind == K_DEAD) continue;
            std::wstring nm = idx_.name_str(c);
            if (!kv.second.count(nm)) continue;
            WIN32_FILE_ATTRIBUTE_DATA a;
            if (GetFileAttributesExW(long_path(join_path(p, nm)).c_str(), GetFileExInfoStandard, &a)) {
                int64_t sz = e.kind == K_DIR ? -1 : (int64_t)(((uint64_t)a.nFileSizeHigh << 32) | a.nFileSizeLow);
                upd.push_back({c, {sz, ft64(a.ftLastWriteTime)}});
            }
        }
    }
    WriteGuard g(idx_.lock);
    for (auto& u : upd) {
        Entry& e = idx_.entries[u.first];
        if (e.kind == K_DEAD) continue;
        e.size = u.second.first;
        e.mtime = u.second.second;
    }
    idx_.version++;
}

// ---------------------------------------------------------------- drives
void Engine::remove_root(uint32_t rd) {
    if (rd >= idx_.dirs.size() || idx_.dirs[rd].dead) return;
    std::wstring p = idx_.dirs[rd].path;
    unwatch({rd});
    std::vector<uint32_t> removed;
    {
        WriteGuard g(idx_.lock);
        idx_.remove_root(rd, removed);
    }
    unwatch(removed);
    {
        std::lock_guard<std::mutex> g(sm_);
        std::wstring k = to_lower(p);
        roots_.erase(std::remove_if(roots_.begin(), roots_.end(), [&](const std::wstring& r) { return to_lower(r) == k; }),
                     roots_.end());
    }
    excluded_ = compute_excludes();
    log_line(L"root removed: %ls", p.c_str());
}

bool Engine::sync_roots() {
    if (cli_) return false;
    auto pairs = root_pairs();
    std::vector<std::wstring> want;
    std::set<std::wstring> wk;
    dyn_.clear();
    for (auto& p : pairs) {
        if (!is_dir(p.first)) continue;
        want.push_back(p.first);
        wk.insert(to_lower(p.first));
        if (p.second) dyn_.insert(to_lower(p.first));
    }
    bool changed = false;
    for (uint32_t d : idx_.root_dirs()) {
        if (!wk.count(to_lower(idx_.dirs[d].path))) { remove_root(d); changed = true; }
    }
    {
        std::lock_guard<std::mutex> g(sm_);
        roots_ = want;
    }
    excluded_ = compute_excludes();
    for (auto& r : want) {
        if (idx_.find_dir(r) != NONE) continue;
        log_line(L"root added: %ls", r.c_str());
        set_msg(L"正在索引新磁盘 " + r + L" …");
        uint32_t d;
        {
            WriteGuard g(idx_.lock);
            d = idx_.new_dir(r, NONE);
        }
        watch({d});
        scan_tree(idx_, {d}, excluded_, &abort_, scan_threads_);
        changed = true;
    }
    return changed;
}

bool Engine::check_drives() {
    bool changed = false;
    if (!cli_) {
        DWORD mask = GetLogicalDrives();
        if (mask != drive_mask_) {
            drive_mask_ = mask;
            changed = sync_roots();
        }
    }
    retry_watches();
    return changed;
}

void Engine::retry_watches() {
    double now = now_sec();
    std::vector<uint32_t> todo;
    for (uint32_t d : idx_.root_dirs()) {
        if (watched_.count(d)) continue;
        auto h = hold_.find(to_lower(idx_.dirs[d].path));
        if (h != hold_.end() && h->second > now) continue;
        todo.push_back(d);
    }
    if (todo.empty()) return;
    watch(todo);
    std::vector<uint32_t> back;
    for (uint32_t d : todo) if (watched_.count(d)) back.push_back(d);
    if (!back.empty()) catch_up(false, &back);
}

// ---------------------------------------------------------------- misc
void Engine::set_ready() {
    size_t nd = 0;
    for (auto& d : idx_.dirs) if (!d.dead) nd++;
    auto roots = idx_.root_dirs();
    size_t w = 0;
    if (!watched_.empty()) {
        bool all = true;
        for (uint32_t r : roots) if (!watched_.count(r)) all = false;
        if (all) w = nd;
        else {
            std::vector<std::wstring> prefs;
            for (uint32_t d : watched_) if (d < idx_.dirs.size() && !idx_.dirs[d].dead) prefs.push_back(dir_prefix(to_lower(idx_.dirs[d].path)));
            for (auto& d : idx_.dirs) if (!d.dead && under(d.path, prefs)) w++;
        }
    }
    std::lock_guard<std::mutex> g(sm_);
    st_.state = L"ready";
    st_.dirs = nd;
    st_.watched = w;
    st_.watcher_ok = watcher_ok_;
    st_.msg.clear();
}

void Engine::compute_order() {
    auto no = idx_.compute_order();   // engine is the only writer: reading without the lock is safe
    WriteGuard g(idx_.lock);
    if (no->gen == idx_.gen.load()) idx_.name_order = no;
    order_version_ = idx_.struct_version.load();
    last_order_ = now_sec();
}

void Engine::save() {
    if (cli_) return;
    uint64_t v = idx_.version.load();
    double t0 = now_sec();
    if (idx_.save(index_file(), header())) {
        saved_version_ = v;
        log_line(L"index saved (%lld entries, %.2f s)", (long long)idx_.live.load(), now_sec() - t0);
    } else {
        log_line(L"index save failed: %ls", last_error_text(GetLastError()).c_str());
    }
}

void Engine::start_sweep(int scope, const std::vector<std::wstring>& prefs) {
    if (scope == 0 && skip_sweep_) { skip_sweep_ = false; sweep_scope_ = -1; return; }
    sweep_scope_ = scope;
    sweep_prefs_ = prefs;
    sweep_pos_ = 0;
}

bool Engine::sweep_step(int budget) {
    if (sweep_scope_ < 0) return false;
    std::vector<std::wstring> allowed;
    bool use = false;
    if (sweep_scope_ == 1) { allowed = unwatched_prefixes(); use = true; }
    else if (sweep_scope_ == 2) { allowed = sweep_prefs_; use = true; }
    if (use && allowed.empty()) { sweep_scope_ = -1; return false; }
    int n = 0;
    while (sweep_pos_ < idx_.dirs.size()) {
        uint32_t d = sweep_pos_++;
        if (idx_.dirs[d].dead) continue;
        if (use && !under(idx_.dirs[d].path, allowed)) continue;
        refresh(d);
        if (++n >= budget) return true;
    }
    sweep_scope_ = -1;
    idx_.version++;
    return false;
}

bool Engine::command(const Cmd& c) {
    switch (c.op) {
        case C_QUIT: {
            stopping_ = true;
            abort_ = true;
            EngineStatus s = status();
            if ((s.state == L"ready" || s.state == L"updating") && idx_.version.load() != saved_version_) {
                set_msg(L"正在保存索引…");
                save();
            }
            close_watches();
            set_status(L"stopped", L"");
            return false;
        }
        case C_REBUILD:
            cfg_ = c.cfg;
            abort_ = false;
            setup_paths();
            full_scan();
            start_sweep(0);
            set_ready();
            break;
        case C_REFRESH_PATH: {
            uint32_t d = idx_.find_dir(c.arg);
            if (d != NONE) { refresh(d); set_ready(); }
            break;
        }
        case C_REFRESH_ALL:
            set_status(L"updating", L"正在刷新…");
            excluded_ = compute_excludes();
            catch_up(false);
            start_sweep(0);
            set_ready();
            break;
        case C_SAVE:
            save();
            break;
        case C_DEVNOTIFY:
            if (HWND h = hwnd_.load()) watcher_.register_all(h);
            break;
        case C_DRIVE_CHECK:
            drive_mask_ = 0;
            if (check_drives()) set_ready();
            break;
    }
    return true;
}

void Engine::loop() {
    std::set<uint32_t> dirty;
    std::map<uint32_t, std::set<std::wstring>> touched;
    double first_event = 0, now = now_sec();
    double last_poll = now, last_sweep = now, last_save = now, last_drives = now, last_change = 0;
    const double POLL = 180, SWEEP = 1800, SAVE = 1800, ORDER_DELAY = 20;
    std::vector<WatchEvent> evs;
    while (true) {
        while (true) {
            Cmd c;
            {
                std::lock_guard<std::mutex> g(cm_);
                if (cmds_.empty()) break;
                c = cmds_.front();
                cmds_.pop_front();
            }
            if (!command(c)) return;
        }
        DWORD timeout = (!dirty.empty() || !touched.empty()) ? 50 : (sweep_scope_ >= 0 ? 20 : 500);
        evs.clear();
        watcher_.wait(timeout, cmd_ev_, evs);
        if (!evs.empty()) {
            handle_events(evs, dirty, touched);
            if (first_event == 0 && (!dirty.empty() || !touched.empty())) first_event = now_sec();
        }
        now = now_sec();
        if ((!dirty.empty() || !touched.empty()) && now - first_event >= 0.3) {
            excluded_ = compute_excludes();
            for (uint32_t d : dirty) refresh(d);
            if (!touched.empty()) apply_touched(touched);
            dirty.clear();
            touched.clear();
            first_event = 0;
            last_change = now;
            set_ready();
        }
        if (now - last_drives >= 2) {
            last_drives = now;
            if (check_drives()) { last_change = now; set_ready(); }
        }
        if (sweep_scope_ >= 0) sweep_step(64);
        if (now - last_poll >= POLL) {
            last_poll = now;
            bool partial = false;
            for (uint32_t r : idx_.root_dirs()) if (!watched_.count(r)) partial = true;
            if (partial) { excluded_ = compute_excludes(); catch_up(true); set_ready(); }
        }
        if (now - last_sweep >= SWEEP && sweep_scope_ < 0) { last_sweep = now; start_sweep(1); }
        if (idx_.struct_version.load() != order_version_ && now - last_change > 2 && now - last_order_ >= ORDER_DELAY)
            compute_order();
        if (now - last_save >= SAVE) {
            last_save = now;
            if (idx_.version.load() != saved_version_) save();
        }
    }
}

} // namespace qx
