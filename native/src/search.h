// 千寻 —— 搜索执行（平台无关）：多核并行过滤、增量收窄、排序。语义对照 qianxun.py 的 Searcher。
#pragma once
#include "index.h"
#include "query.h"
#include <functional>
#include <thread>
#include <mutex>
#include <condition_variable>

namespace qx {

// Minimal fork-join pool: run(n, fn) executes fn(chunk, worker) for every chunk on all workers + caller.
class ThreadPool {
public:
    explicit ThreadPool(int nthreads);
    ~ThreadPool();
    int size() const { return (int)workers_.size() + 1; }
    void run(size_t nchunks, const std::function<void(size_t, int)>& fn);
private:
    void loop(int id);
    std::vector<std::thread> workers_;
    std::mutex m_;
    std::condition_variable cv_, done_cv_;
    const std::function<void(size_t, int)>* fn_ = nullptr;
    size_t nchunks_ = 0;
    std::atomic<size_t> next_{0};
    size_t finished_ = 0;
    uint64_t job_ = 0;
    int active_ = 0;
    bool stop_ = false;
    std::mutex run_m_;   // one job at a time
};

typedef std::function<bool()> CancelFn;

class Searcher {
public:
    Searcher(const Index& idx, ThreadPool& pool) : idx_(idx), pool_(pool) {}
    bool case_ = false;
    // Caller holds idx.lock (shared). Returns false when cancelled. out = matching entry ids (unsorted).
    bool run(const Query& q, const std::wstring& extra_key, std::vector<uint32_t>& out, const CancelFn& cancel);
    // col: 0 name, 1 path, 2 size, 3 mtime. Caller holds idx.lock (shared). *unsorted set when skipped.
    bool sort_rows(std::vector<uint32_t>& rows, int col, bool desc, bool* unsorted, const CancelFn& cancel);
    void reset() { prev_valid_ = false; prev_rows_.clear(); }
private:
    typedef const std::vector<uint32_t>* Cand;
    bool filter(const Pred& p, Cand cand, std::vector<uint32_t>& out);
    void all_live(std::vector<uint32_t>& out);
    bool pool_scan(const std::wstring& t, int want, bool lower, std::vector<uint32_t>& out);
    template <class F> bool select(Cand cand, std::vector<uint32_t>& out, F test);
    void ensure_prefixes(bool lower);
    bool whole_match(const wchar_t* s, size_t n, const std::wstring& t) const;

    const Index& idx_;
    ThreadPool& pool_;
    const CancelFn* cancel_ = nullptr;
    std::atomic<bool> cancelled_{false};
    // incremental narrowing state
    bool prev_valid_ = false;
    std::wstring prev_text_, prev_extra_;
    QueryOpts prev_opts_;
    uint64_t prev_version_ = 0;
    std::vector<uint32_t> prev_rows_;
    // dir prefix caches ("c:\dir\" lowercase / original), append-only per index gen
    struct Prefixes {
        std::vector<wchar_t> pool;
        std::vector<uint32_t> off{0};
        uint64_t gen = 0;
        size_t count() const { return off.size() - 1; }
        const wchar_t* ptr(uint32_t d) const { return pool.data() + off[d]; }
        uint32_t len(uint32_t d) const { return off[d + 1] - off[d]; }
    } pre_low_, pre_orig_;
    // dir rank for path sorting
    std::vector<uint32_t> drank_;
    uint64_t drank_ver_ = 0, drank_gen_ = 0;
};

std::wstring human_size(int64_t n);

} // namespace qx
