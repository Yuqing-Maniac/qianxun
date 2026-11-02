// 千寻 —— 搜索执行实现
#include "search.h"
#include "textutil.h"
#include <algorithm>
#include <cstdio>
#include <cwchar>

namespace qx {

// ---------------------------------------------------------------- ThreadPool
ThreadPool::ThreadPool(int n) {
    for (int i = 1; i < n; i++) workers_.emplace_back([this, i] { loop(i); });
}

ThreadPool::~ThreadPool() {
    {
        std::lock_guard<std::mutex> g(m_);
        stop_ = true;
    }
    cv_.notify_all();
    for (auto& t : workers_) t.join();
}

void ThreadPool::loop(int id) {
    uint64_t seen = 0;
    while (true) {
        const std::function<void(size_t, int)>* fn;
        size_t n;
        {
            std::unique_lock<std::mutex> lk(m_);
            cv_.wait(lk, [&] { return stop_ || job_ != seen; });
            if (stop_) return;
            seen = job_;
            fn = fn_;
            n = nchunks_;
            active_++;
        }
        size_t did = 0;
        for (size_t c; (c = next_.fetch_add(1)) < n;) { (*fn)(c, id); did++; }
        {
            std::lock_guard<std::mutex> g(m_);
            finished_ += did;
            active_--;
        }
        done_cv_.notify_all();
    }
}

void ThreadPool::run(size_t nchunks, const std::function<void(size_t, int)>& fn) {
    if (nchunks == 0) return;
    std::lock_guard<std::mutex> rg(run_m_);
    if (workers_.empty() || nchunks == 1) {
        for (size_t c = 0; c < nchunks; c++) fn(c, 0);
        return;
    }
    {
        std::unique_lock<std::mutex> g(m_);
        // a worker that woke late for the previous job may still hold its (stale) fn/n: let it drain first
        done_cv_.wait(g, [&] { return active_ == 0; });
        fn_ = &fn;
        nchunks_ = nchunks;
        next_ = 0;
        finished_ = 0;
        job_++;
    }
    cv_.notify_all();
    size_t did = 0;
    for (size_t c; (c = next_.fetch_add(1)) < nchunks;) { fn(c, 0); did++; }
    std::unique_lock<std::mutex> lk(m_);
    finished_ += did;
    // wait until every chunk is done and no worker still holds a reference to fn
    done_cv_.wait(lk, [&] { return finished_ >= nchunks && active_ == 0; });
    fn_ = nullptr;
}

// ---------------------------------------------------------------- helpers
std::wstring human_size(int64_t n) {
    if (n < 0) return L"";
    if (n < 1024) return std::to_wstring(n) + L" B";
    double v = (double)n;
    const wchar_t* units[] = {L"KB", L"MB", L"GB", L"TB"};
    for (int k = 0; k < 4; k++) {
        v /= 1024.0;
        if (v < 1024 || k == 3) {
            wchar_t buf[64];
            swprintf(buf, 64, v >= 100 ? L"%.0f %ls" : L"%.1f %ls", v, units[k]);
            return buf;
        }
    }
    return L"";
}

static const size_t BLK = 1 << 16;   // == ChunkedVec block size of Index::entries

template <class F>
bool Searcher::select(Cand cand, std::vector<uint32_t>& out, F test) {
    out.clear();
    size_t total = cand ? cand->size() : idx_.size();
    size_t nchunks = (total + BLK - 1) / BLK;
    if (nchunks == 0) return true;
    std::vector<std::vector<uint32_t>> parts(nchunks);
    const Index& ix = idx_;
    pool_.run(nchunks, [&](size_t c, int w) {
        if (cancelled_.load(std::memory_order_relaxed)) return;
        if (w == 0 && cancel_ && (*cancel_) && (*cancel_)()) { cancelled_ = true; return; }
        std::vector<uint32_t>& o = parts[c];
        size_t a = c * BLK, b = std::min(total, a + BLK);
        if (!cand) {
            const Entry* blk = ix.entries.block(c);
            for (size_t i = a; i < b; i++) {
                const Entry& e = blk[i - a];
                if (e.kind != K_DEAD && test((uint32_t)i, e, w)) o.push_back((uint32_t)i);
            }
        } else {
            const uint32_t* cv = cand->data();
            for (size_t k = a; k < b; k++) {
                uint32_t i = cv[k];
                const Entry& e = ix.entries[i];
                if (e.kind != K_DEAD && test(i, e, w)) o.push_back(i);
            }
        }
    });
    if (cancelled_) return false;
    size_t n = 0;
    for (auto& p : parts) n += p.size();
    out.reserve(n);
    for (auto& p : parts) out.insert(out.end(), p.begin(), p.end());
    return true;
}

void Searcher::all_live(std::vector<uint32_t>& out) {
    select(nullptr, out, [](uint32_t, const Entry&, int) { return true; });
}

void Searcher::ensure_prefixes(bool lower) {
    Prefixes& P = lower ? pre_low_ : pre_orig_;
    uint64_t g = idx_.gen.load();
    if (P.gen != g) { P.pool.clear(); P.off.assign(1, 0); P.gen = g; }
    size_t nd = idx_.dirs.size();
    for (size_t d = P.count(); d < nd; d++) {
        const DirRec& r = idx_.dirs[d];
        if (!r.dead && !r.path.empty()) {
            for (wchar_t c : r.path) P.pool.push_back(lower ? lower_ch(c) : c);
            if (r.path.back() != L'\\') P.pool.push_back(L'\\');
        }
        P.off.push_back((uint32_t)P.pool.size());
    }
}

bool Searcher::whole_match(const wchar_t* s, size_t n, const std::wstring& t) const {
    // (?<!\w)t(?!\w) anywhere in s
    size_t tn = t.size();
    const wchar_t* p = s;
    size_t left = n;
    while (true) {
        const wchar_t* f = find_sub(p, left, t.data(), tn);
        if (!f) return false;
        size_t pos = (size_t)(f - s);
        bool okL = !word_before(s, pos);
        bool okR = !word_after(s, n, pos + tn);
        if (okL && okR) return true;
        p = f + 1;
        left = n - (pos + 1);
    }
}

// Full scan for a name substring: SIMD-search the contiguous name pool, map hits to entries
// (entries are appended in pool order, so name_off is monotonic in the entry id).
bool Searcher::pool_scan(const std::wstring& t, int want, bool lower, std::vector<uint32_t>& out) {
    out.clear();
    const Index& ix = idx_;
    const NamePool& pool = ix.pool;
    const size_t n = ix.size(), nch = pool.chunks(), tn = t.size();
    std::vector<std::vector<uint32_t>> parts(nch);
    pool_.run(nch, [&](size_t c, int w) {
        if (cancelled_.load(std::memory_order_relaxed)) return;
        if (w == 0 && cancel_ && (*cancel_) && (*cancel_)()) { cancelled_ = true; return; }
        const wchar_t* base = pool.chunk(c, lower);
        const size_t len = pool.fill(c);
        const uint64_t c0 = (uint64_t)c * NamePool::CH;
        // first entry whose name starts in this chunk
        size_t lo = 0, hi = n;
        while (lo < hi) {
            size_t mid = (lo + hi) / 2;
            if (ix.entries[mid].name_off < c0) lo = mid + 1; else hi = mid;
        }
        size_t e = lo, pos = 0;
        std::vector<uint32_t>& o = parts[c];
        while (pos < len && e < n) {
            const wchar_t* f = find_sub(base + pos, len - pos, t.data(), tn);
            if (!f) break;
            uint64_t h = c0 + (uint64_t)(f - base);
            while (e < n && (uint64_t)ix.entries[e].name_off + ix.entries[e].name_len <= h) e++;
            if (e >= n) break;
            const Entry& en = ix.entries[e];
            if (en.name_off <= h && h + tn <= (uint64_t)en.name_off + en.name_len) {
                if (en.kind != K_DEAD && (want < 0 || en.kind == (uint8_t)want)) o.push_back((uint32_t)e);
                pos = (size_t)(en.name_off + en.name_len - c0);
                e++;
            } else {
                pos = (size_t)(f - base) + 1;
            }
        }
    });
    if (cancelled_) return false;
    size_t tot = 0;
    for (auto& p : parts) tot += p.size();
    out.reserve(tot);
    for (auto& p : parts) out.insert(out.end(), p.begin(), p.end());
    return true;
}

// ---------------------------------------------------------------- filters
bool Searcher::filter(const Pred& p, Cand cand, std::vector<uint32_t>& out) {
    const Index& ix = idx_;
    const NamePool& pool = ix.pool;
    bool lower = !case_;
    switch (p.kind) {
        case P_ALL:
            if (cand) { out = *cand; return true; }
            all_live(out);
            return !cancelled_;
        case P_FILE:
            return select(cand, out, [](uint32_t, const Entry& e, int) { return e.kind == K_FILE; });
        case P_FOLDER:
            return select(cand, out, [](uint32_t, const Entry& e, int) { return e.kind == K_DIR; });
        case P_EXT: {
            const auto& exts = p.exts;
            return select(cand, out, [&](uint32_t, const Entry& e, int) {
                if (e.kind != K_FILE) return false;
                const wchar_t* n = pool.low(e.name_off);
                int j = (int)e.name_len - 1;
                while (j >= 0 && n[j] != L'.') j--;
                if (j < 0) return false;
                const wchar_t* x = n + j + 1;
                size_t xl = e.name_len - (size_t)j - 1;
                for (auto& s : exts)
                    if (s.size() == xl && (xl == 0 || (s[0] == x[0] && wmemcmp(s.data(), x, xl) == 0))) return true;
                return false;
            });
        }
        case P_SIZE: {
            long long lo = p.lo, hi = p.hi;
            return select(cand, out, [=](uint32_t, const Entry& e, int) {
                return e.kind == K_FILE && lo <= e.size && e.size <= hi;
            });
        }
        case P_DM: {
            double lo = p.dlo, hi = p.dhi;
            return select(cand, out, [=](uint32_t, const Entry& e, int) {
                double m = ft_to_epoch(e.mtime);
                return lo <= m && m < hi;
            });
        }
        default: break;
    }
    // ---- text predicates
    bool ok = true;
    const int want = p.want_kind;
    auto kind_ok = [want](const Entry& e) { return want < 0 || e.kind == (uint8_t)want; };
    auto nm = [&](const Entry& e) { return lower ? pool.low(e.name_off) : pool.orig(e.name_off); };
    if (!p.path) {
        const std::wstring& t = p.text;
        switch (p.kind) {
            case P_SUB:
                if (!cand) { ok = pool_scan(t, want, lower, out); break; }
                ok = select(cand, out, [&](uint32_t, const Entry& e, int) {
                    return kind_ok(e) && find_sub(nm(e), e.name_len, t.data(), t.size()) != nullptr;
                });
                break;
            case P_WILD: {
                const Glob& g = *p.glob;
                ok = select(cand, out, [&](uint32_t, const Entry& e, int) {
                    return kind_ok(e) && g.match(nm(e), e.name_len);
                });
                break;
            }
            case P_WHOLE:
                ok = select(cand, out, [&](uint32_t, const Entry& e, int) {
                    return kind_ok(e) && whole_match(nm(e), e.name_len, t);
                });
                break;
            case P_REGEX: {
                const QxRegex& rx = *p.rx;
                ok = select(cand, out, [&](uint32_t, const Entry& e, int) {
                    if (!kind_ok(e)) return false;
                    const wchar_t* s = nm(e);
                    try {
                        return std::regex_search(s, s + e.name_len, rx);
                    } catch (...) {
                        return false;
                    }
                });
                break;
            }
            default: break;
        }
        return ok;
    }
    // ---- path predicates: "dir\" + name
    ensure_prefixes(lower);
    const Prefixes& P = lower ? pre_low_ : pre_orig_;
    const std::wstring& t = p.text;
    if (p.kind == P_SUB) {
        // per-directory precomputation (dirs ≪ entries)
        size_t nd = P.count();
        std::vector<uint8_t> dhit(nd, 0);
        size_t k2 = t.rfind(L'\\');
        std::wstring head = k2 == std::wstring::npos ? std::wstring() : t.substr(0, k2 + 1);
        std::wstring tail = k2 == std::wstring::npos ? std::wstring() : t.substr(k2 + 1);
        size_t nch = (nd + 4095) / 4096;
        pool_.run(nch, [&](size_t c, int) {
            size_t a = c * 4096, b = std::min(nd, a + 4096);
            for (size_t d = a; d < b; d++) {
                const wchar_t* s = P.ptr((uint32_t)d);
                uint32_t n = P.len((uint32_t)d);
                if (!n) continue;
                if (find_sub(s, n, t.data(), t.size())) dhit[d] = 1;
                else if (k2 != std::wstring::npos && n >= head.size() &&
                         wmemcmp(s + n - head.size(), head.data(), head.size()) == 0)
                    dhit[d] = 2;
            }
        });
        if (k2 == std::wstring::npos) {
            return select(cand, out, [&](uint32_t, const Entry& e, int) {
                if (!kind_ok(e)) return false;
                return (e.parent < nd && dhit[e.parent] == 1) || find_sub(nm(e), e.name_len, t.data(), t.size());
            });
        }
        return select(cand, out, [&](uint32_t, const Entry& e, int) {
            if (!kind_ok(e) || e.parent >= nd) return false;
            uint8_t h = dhit[e.parent];
            if (h == 1) return true;
            return h == 2 && e.name_len >= tail.size() &&
                   (tail.empty() || wmemcmp(nm(e), tail.data(), tail.size()) == 0);
        });
    }
    if (p.kind == P_WILD) {
        const Glob& g = *p.glob;
        size_t nd = P.count();
        return select(cand, out, [&](uint32_t, const Entry& e, int) {
            if (!kind_ok(e) || e.parent >= nd) return false;
            return g.match2(P.ptr(e.parent), P.len(e.parent), nm(e), e.name_len);
        });
    }
    // WHOLE / REGEX on full path: concatenate into per-worker scratch buffer
    std::vector<std::wstring> scratch((size_t)pool_.size());
    size_t nd = P.count();
    if (p.kind == P_WHOLE) {
        return select(cand, out, [&](uint32_t, const Entry& e, int w) {
            if (!kind_ok(e) || e.parent >= nd) return false;
            std::wstring& b = scratch[(size_t)w];
            b.assign(P.ptr(e.parent), P.len(e.parent));
            b.append(nm(e), e.name_len);
            return whole_match(b.data(), b.size(), t);
        });
    }
    const QxRegex& rx = *p.rx;
    return select(cand, out, [&](uint32_t, const Entry& e, int w) {
        if (!kind_ok(e) || e.parent >= nd) return false;
        std::wstring& b = scratch[(size_t)w];
        b.assign(P.ptr(e.parent), P.len(e.parent));
        b.append(nm(e), e.name_len);
        try {
            return std::regex_search(b, rx);
        } catch (...) {
            return false;
        }
    });
}

// ---------------------------------------------------------------- run
bool Searcher::run(const Query& q, const std::wstring& extra_key, std::vector<uint32_t>& out, const CancelFn& cancel) {
    out.clear();
    cancel_ = &cancel;
    cancelled_ = false;
    if (!q.ok()) { prev_valid_ = false; return true; }
    uint64_t ver = idx_.version.load();
    bool use_prev = false;
    if (prev_valid_ && q.is_plain() && prev_opts_ == q.opts && prev_version_ == ver && prev_extra_ == extra_key &&
        !prev_text_.empty() && q.text.compare(0, prev_text_.size(), prev_text_) == 0) {
        Query pq(prev_text_, QueryOpts());
        use_prev = pq.is_plain();
    }
    std::vector<uint32_t> res, tmp;
    bool have = false;   // false = "all entries" (None)
    if (use_prev) { res = prev_rows_; have = true; }
    for (auto& g : q.groups) {
        if (g.alts.size() == 1 && !g.neg) {
            if (!filter(g.alts[0], have ? &res : nullptr, tmp)) { prev_valid_ = false; return false; }
            res.swap(tmp);
            have = true;
        } else if (!have) {
            // no candidates yet: run each alternative over the whole index (fast paths apply), then keep
            // live entries whose hit flag differs from the negation
            std::vector<uint8_t> hit(idx_.size(), 0);
            for (auto& a : g.alts) {
                if (!filter(a, nullptr, tmp)) { prev_valid_ = false; return false; }
                for (uint32_t i : tmp) hit[i] = 1;
            }
            const bool neg = g.neg;
            if (!select(nullptr, res, [&](uint32_t i, const Entry&, int) { return (hit[i] != 0) != neg; })) {
                prev_valid_ = false;
                return false;
            }
            have = true;
        } else {
            std::vector<uint32_t> base = res;
            std::vector<uint8_t> hit(idx_.size(), 0);
            for (auto& a : g.alts) {
                if (!filter(a, &base, tmp)) { prev_valid_ = false; return false; }
                for (uint32_t i : tmp) hit[i] = 1;
            }
            res.clear();
            for (uint32_t i : base) if ((hit[i] != 0) != g.neg) res.push_back(i);
            have = true;
        }
        if (res.empty()) break;
    }
    if (!have) { all_live(res); if (cancelled_) { prev_valid_ = false; return false; } }
    prev_valid_ = true;
    prev_text_ = q.text;
    prev_opts_ = q.opts;
    prev_version_ = ver;
    prev_extra_ = extra_key;
    prev_rows_ = res;
    out.swap(res);
    return true;
}

// ---------------------------------------------------------------- sorting
bool Searcher::sort_rows(std::vector<uint32_t>& rows, int col, bool desc, bool* unsorted, const CancelFn& cancel) {
    const Index& ix = idx_;
    if (unsorted) *unsorted = false;
    auto no = ix.name_order;
    bool have_order = no && no->gen == ix.gen.load();
    const NameOrder* NO = have_order ? no.get() : nullptr;
    auto name_less = [&](uint32_t a, uint32_t b) {
        if (NO && a < NO->n && b < NO->n) return NO->rank[a] < NO->rank[b];
        return ix.compare_name_path(a, b) < 0;
    };
    if (col == 0) {
        if (NO && rows.size() > 50000) {
            // walk the presorted order, then merge entries newer than the order
            std::vector<uint8_t> mask(ix.size(), 0);
            std::vector<uint32_t> extra;
            for (uint32_t i : rows) {
                if (i < NO->n) mask[i] = 1; else extra.push_back(i);
            }
            std::vector<uint32_t> out;
            out.reserve(rows.size());
            for (uint32_t i : NO->order) if (mask[i]) out.push_back(i);
            if (!extra.empty()) {
                std::sort(extra.begin(), extra.end(), [&](uint32_t a, uint32_t b) { return ix.compare_name_path(a, b) < 0; });
                std::vector<uint32_t> merged;
                merged.reserve(out.size() + extra.size());
                std::merge(out.begin(), out.end(), extra.begin(), extra.end(), std::back_inserter(merged),
                           [&](uint32_t a, uint32_t b) { return ix.compare_name_path(a, b) < 0; });
                out.swap(merged);
            }
            rows.swap(out);
        } else if (!NO && rows.size() > 400000) {
            if (unsorted) *unsorted = true;
        } else {
            std::sort(rows.begin(), rows.end(), name_less);
        }
    } else if (col == 1) {
        uint64_t dv = ix.dirs_version.load(), g = ix.gen.load();
        if (drank_ver_ != dv || drank_gen_ != g || drank_.size() != ix.dirs.size()) {
            ensure_prefixes(true);
            const Prefixes& P = pre_low_;
            size_t nd = P.count();
            std::vector<uint32_t> ord(nd);
            for (uint32_t d = 0; d < nd; d++) ord[d] = d;
            std::sort(ord.begin(), ord.end(), [&](uint32_t a, uint32_t b) {
                return cp_compare(P.ptr(a), P.len(a), P.ptr(b), P.len(b)) < 0;
            });
            drank_.assign(nd, 0);
            for (uint32_t r = 0; r < nd; r++) drank_[ord[r]] = r;
            drank_ver_ = dv;
            drank_gen_ = g;
        }
        if (cancel && cancel()) return false;
        std::sort(rows.begin(), rows.end(), [&](uint32_t a, uint32_t b) {
            uint32_t pa = ix.entries[a].parent, pb = ix.entries[b].parent;
            uint32_t ra = pa < drank_.size() ? drank_[pa] : NONE, rb = pb < drank_.size() ? drank_[pb] : NONE;
            if (ra != rb) return ra < rb;
            return name_less(a, b);
        });
    } else {
        bool sz = col == 2;
        std::sort(rows.begin(), rows.end(), [&](uint32_t a, uint32_t b) {
            const Entry& ea = ix.entries[a];
            const Entry& eb = ix.entries[b];
            int64_t va = sz ? ea.size : ea.mtime, vb = sz ? eb.size : eb.mtime;
            if (va != vb) return va < vb;
            return name_less(a, b);
        });
    }
    if (desc) std::reverse(rows.begin(), rows.end());
    return true;
}

} // namespace qx
