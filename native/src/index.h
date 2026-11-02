// 千寻 —— 索引数据结构（平台无关）
// 条目＝父目录号＋名称偏移/长度＋类型＋大小＋修改时间（32 字节）；名称存放在分块的 UTF-16 字符串池中，
// 另有同布局的小写折叠池用于不区分大小写匹配。目录另有记录：完整路径、自身条目号（根为 NONE）、mtime、子项列表。
// 写入只在持写锁时进行（引擎/扫描线程），读取（搜索/界面）持读锁。
#pragma once
#include <string>
#include <vector>
#include <memory>
#include <atomic>
#include <cstdint>
#include <unordered_set>
#ifdef _WIN32
#include <windows.h>
#else
#include <shared_mutex>
#endif

namespace qx {

const uint32_t NONE = 0xFFFFFFFFu;
enum : uint8_t { K_FILE = 0, K_DIR = 1, K_DEAD = 2 };
enum : uint8_t { EF_NOREC = 1 };   // name-surrogate reparse point (junction/symlink): listed, not recursed

const int64_t FT_EPOCH = 116444736000000000LL;   // FILETIME of 1970-01-01
inline double ft_to_epoch(int64_t ft) { return (double)(ft - FT_EPOCH) / 1e7; }

struct Entry {
    uint32_t parent;     // dir id
    uint32_t name_off;   // offset in name pools
    uint32_t dir;        // dir id when kind==K_DIR and the dir is indexed, else NONE
    uint16_t name_len;
    uint8_t kind;
    uint8_t flags;
    int64_t size;        // -1 for directories
    int64_t mtime;       // FILETIME (100 ns since 1601, UTC)
};

// Reader/writer lock: SRWLOCK on Windows (Vista+), std::shared_mutex elsewhere.
class RWLock {
public:
#ifdef _WIN32
    RWLock() { InitializeSRWLock(&l_); }
    void lock() { AcquireSRWLockExclusive(&l_); }
    void unlock() { ReleaseSRWLockExclusive(&l_); }
    void lock_shared() { AcquireSRWLockShared(&l_); }
    void unlock_shared() { ReleaseSRWLockShared(&l_); }
private:
    SRWLOCK l_;
#else
    void lock() { m_.lock(); }
    void unlock() { m_.unlock(); }
    void lock_shared() { m_.lock_shared(); }
    void unlock_shared() { m_.unlock_shared(); }
private:
    std::shared_mutex m_;
#endif
};
struct ReadGuard { RWLock& l; explicit ReadGuard(RWLock& x) : l(x) { l.lock_shared(); } ~ReadGuard() { l.unlock_shared(); } };
struct WriteGuard { RWLock& l; explicit WriteGuard(RWLock& x) : l(x) { l.lock(); } ~WriteGuard() { l.unlock(); } };

// Append-only chunked array: elements never move, growth never copies.
template <typename T, int BITS>
class ChunkedVec {
public:
    static const size_t CH = (size_t)1 << BITS;
    size_t size() const { return n_; }
    T& operator[](size_t i) { return blocks_[i >> BITS][i & (CH - 1)]; }
    const T& operator[](size_t i) const { return blocks_[i >> BITS][i & (CH - 1)]; }
    void push_back(const T& v) {
        if ((n_ & (CH - 1)) == 0 && (n_ >> BITS) >= blocks_.size()) blocks_.emplace_back(new T[CH]);
        (*this)[n_] = v;
        n_++;
    }
    void clear() { blocks_.clear(); n_ = 0; }
    T* block(size_t b) { return blocks_[b].get(); }
    const T* block(size_t b) const { return blocks_[b].get(); }
    size_t mem() const { return blocks_.size() * CH * sizeof(T); }
private:
    std::vector<std::unique_ptr<T[]>> blocks_;
    size_t n_ = 0;
};

// Two parallel chunked UTF-16 pools (original + lowercase). A name never straddles chunks.
class NamePool {
public:
    static const uint32_t CH = 1u << 20;
    uint32_t add(const wchar_t* s, size_t n);
    const wchar_t* orig(uint32_t off) const { return o_[off / CH].get() + off % CH; }
    const wchar_t* low(uint32_t off) const { return l_[off / CH].get() + off % CH; }
    void clear() { o_.clear(); l_.clear(); fill_.clear(); used_ = 0; }
    size_t chunks() const { return o_.size(); }
    uint32_t fill(size_t c) const { return fill_[c]; }          // used chars in chunk c
    const wchar_t* chunk(size_t c, bool lower) const { return lower ? l_[c].get() : o_[c].get(); }
    size_t mem() const { return (o_.size() + l_.size()) * (size_t)CH * sizeof(wchar_t); }
private:
    std::vector<std::unique_ptr<wchar_t[]>> o_, l_;
    std::vector<uint32_t> fill_;
    uint32_t used_ = 0;
};

struct DirRec {
    std::wstring path;          // full path, e.g. C:\ or C:\Users\x (empty when dead)
    uint32_t entry = NONE;      // own entry id, NONE for roots
    int64_t mtime = 0;          // FILETIME of last listing
    bool dead = false;
    std::vector<uint32_t> children;
};

// Case-insensitive path → dir id (open addressing; keys are recomputed from DirRec::path).
class DirTable {
public:
    void clear() { slots_.clear(); count_ = 0; tomb_ = 0; }
    uint32_t find(const std::vector<DirRec>& dirs, const wchar_t* lowpath, size_t n) const;
    void insert(const std::vector<DirRec>& dirs, uint32_t did, const std::wstring& path);
    void erase(const std::vector<DirRec>& dirs, uint32_t did, const std::wstring& path);
    size_t mem() const { return slots_.size() * sizeof(Slot); }
private:
    struct Slot { uint32_t did; uint32_t hash; };   // did: NONE = empty, NONE-1 = tombstone
    std::vector<Slot> slots_;
    size_t count_ = 0, tomb_ = 0;
    static uint32_t hash_low(const wchar_t* s, size_t n);
    void grow(const std::vector<DirRec>& dirs);
};

struct NameOrder {
    std::vector<uint32_t> order;   // live entries sorted by name (then path)
    std::vector<uint32_t> rank;    // rank[entry] for entries < n, NONE if dead
    uint32_t n = 0;                // entry count covered
    uint64_t gen = 0;
};

struct CacheHeader {
    std::vector<std::wstring> roots, excludes;
    bool operator==(const CacheHeader& o) const { return roots == o.roots && excludes == o.excludes; }
};

class Index {
public:
    Index();
    RWLock lock;
    std::atomic<uint64_t> gen{1};             // bumps when the entry numbering is replaced (clear/load)
    std::atomic<uint64_t> version{1};         // any change (incl. size/time refresh)
    std::atomic<uint64_t> struct_version{1};  // entries added/removed
    std::atomic<uint64_t> dirs_version{1};
    std::atomic<int64_t> live{0};

    ChunkedVec<Entry, 16> entries;
    NamePool pool;
    std::vector<DirRec> dirs;
    DirTable table;
    std::shared_ptr<const NameOrder> name_order;   // swapped under write lock

    // ---- writer API (hold write lock) ----
    void clear();
    uint32_t new_dir(const std::wstring& path, uint32_t entry);
    uint32_t add_entry(uint32_t did, const wchar_t* name, size_t n, bool isdir, int64_t size, int64_t mtime,
                       uint8_t flags = 0);
    void remove_entry(uint32_t i, std::vector<uint32_t>& removed_dirs);
    void remove_root(uint32_t did, std::vector<uint32_t>& removed_dirs);
    void bump() { version++; }

    // ---- reader API (hold read lock, or be the only writer) ----
    uint32_t find_dir(const std::wstring& path) const;   // case-insensitive, NONE if absent
    size_t size() const { return entries.size(); }
    const wchar_t* name(uint32_t i) const { return pool.orig(entries[i].name_off); }
    const wchar_t* lname(uint32_t i) const { return pool.low(entries[i].name_off); }
    std::wstring name_str(uint32_t i) const { return std::wstring(name(i), entries[i].name_len); }
    std::wstring fullpath(uint32_t i) const;
    const std::wstring& dirpath(uint32_t i) const { return dirs[entries[i].parent].path; }
    std::vector<uint32_t> root_dirs() const;
    size_t live_dirs() const;
    size_t mem_estimate() const;

    // Comparator used for name sorting everywhere: (lowercase name, lowercase full path, full path, id).
    int compare_name_path(uint32_t a, uint32_t b) const;
    std::shared_ptr<NameOrder> compute_order() const;   // hold read lock (or be the sole writer)

    // ---- cache I/O ----
    bool save(const std::wstring& file, const CacheHeader& h) const;   // hold read lock / sole writer
    bool load(const std::wstring& file, const CacheHeader& h);          // replaces content (takes write lock)
};

std::wstring join_path(const std::wstring& d, const wchar_t* name, size_t n);
inline std::wstring join_path(const std::wstring& d, const std::wstring& name) { return join_path(d, name.data(), name.size()); }
// (parent, name); parent empty when p is a root ("C:\", "\\server\share\")
bool split_path(const std::wstring& p, std::wstring& parent, std::wstring& name);
std::wstring dir_prefix(const std::wstring& d);   // ensure trailing backslash

} // namespace qx
