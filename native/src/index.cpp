// 千寻 —— 索引数据结构实现（平台无关）
#include "index.h"
#include "textutil.h"
#include <algorithm>
#include <cstdio>
#include <cstring>

namespace qx {

// ---------------------------------------------------------------- paths
std::wstring join_path(const std::wstring& d, const wchar_t* name, size_t n) {
    std::wstring r;
    r.reserve(d.size() + n + 1);
    r = d;
    if (r.empty() || r.back() != L'\\') r += L'\\';
    r.append(name, n);
    return r;
}

std::wstring dir_prefix(const std::wstring& d) {
    if (!d.empty() && d.back() == L'\\') return d;
    return d + L'\\';
}

bool split_path(const std::wstring& p, std::wstring& parent, std::wstring& name) {
    size_t k = p.rfind(L'\\');
    if (k == std::wstring::npos) { parent.clear(); name = p; return false; }
    std::wstring head = p.substr(0, k);
    name = p.substr(k + 1);
    if (name.empty()) { parent.clear(); name = p; return false; }
    if (head.size() == 2 && head[1] == L':') head += L'\\';
    else if (head.size() >= 2 && head[0] == L'\\' && head[1] == L'\\' &&
             std::count(head.begin(), head.end(), L'\\') == 3)
        head += L'\\';
    parent = head;
    return true;
}

// ---------------------------------------------------------------- NamePool
uint32_t NamePool::add(const wchar_t* s, size_t n) {
    if (n > 0xFFFF) n = 0xFFFF;
    size_t chunk = used_ / CH, pos = used_ % CH;
    if (chunk < o_.size() && pos + n > CH) { chunk++; used_ = (uint32_t)(chunk * CH); }
    if (chunk >= o_.size()) {
        o_.emplace_back(new wchar_t[CH]);
        l_.emplace_back(new wchar_t[CH]);
        fill_.push_back(0);
    }
    uint32_t off = used_;
    wchar_t* po = o_[off / CH].get() + off % CH;
    wchar_t* pl = l_[off / CH].get() + off % CH;
    for (size_t i = 0; i < n; i++) { po[i] = s[i]; pl[i] = lower_ch(s[i]); }
    used_ += (uint32_t)n;
    fill_[off / CH] = used_ - (uint32_t)((off / CH) * CH);
    return off;
}

// ---------------------------------------------------------------- DirTable
uint32_t DirTable::hash_low(const wchar_t* s, size_t n) {
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < n; i++) { h ^= (uint32_t)s[i]; h *= 16777619u; }
    return h ? h : 1;
}

static bool eq_low(const std::wstring& path, const wchar_t* low, size_t n) {
    if (path.size() != n) return false;
    for (size_t i = 0; i < n; i++) if (lower_ch(path[i]) != low[i]) return false;
    return true;
}

uint32_t DirTable::find(const std::vector<DirRec>& dirs, const wchar_t* low, size_t n) const {
    if (slots_.empty()) return NONE;
    uint32_t h = hash_low(low, n);
    size_t mask = slots_.size() - 1;
    for (size_t k = h & mask;; k = (k + 1) & mask) {
        const Slot& s = slots_[k];
        if (s.did == NONE) return NONE;
        if (s.did != NONE - 1 && s.hash == h && eq_low(dirs[s.did].path, low, n)) return s.did;
    }
}

void DirTable::grow(const std::vector<DirRec>& dirs) {
    size_t ns = slots_.empty() ? 1024 : slots_.size();
    while (ns < (count_ + 1) * 2) ns *= 2;
    std::vector<Slot> old;
    old.swap(slots_);
    slots_.assign(ns, Slot{NONE, 0});
    tomb_ = 0;
    size_t mask = ns - 1;
    for (auto& s : old) {
        if (s.did == NONE || s.did == NONE - 1) continue;
        (void)dirs;
        size_t k = s.hash & mask;
        while (slots_[k].did != NONE) k = (k + 1) & mask;
        slots_[k] = s;
    }
}

void DirTable::insert(const std::vector<DirRec>& dirs, uint32_t did, const std::wstring& path) {
    if ((count_ + tomb_ + 1) * 10 >= slots_.size() * 7) grow(dirs);
    std::wstring low = to_lower(path);
    uint32_t h = hash_low(low.data(), low.size());
    size_t mask = slots_.size() - 1;
    size_t k = h & mask;
    while (slots_[k].did != NONE && slots_[k].did != NONE - 1) k = (k + 1) & mask;
    if (slots_[k].did == NONE - 1) tomb_--;
    slots_[k] = Slot{did, h};
    count_++;
}

void DirTable::erase(const std::vector<DirRec>& dirs, uint32_t did, const std::wstring& path) {
    if (slots_.empty()) return;
    std::wstring low = to_lower(path);
    uint32_t h = hash_low(low.data(), low.size());
    size_t mask = slots_.size() - 1;
    for (size_t k = h & mask;; k = (k + 1) & mask) {
        Slot& s = slots_[k];
        if (s.did == NONE) return;
        if (s.did == did) { s.did = NONE - 1; tomb_++; count_--; return; }
    }
    (void)dirs;
}

// ---------------------------------------------------------------- Index
Index::Index() { clear(); }

void Index::clear() {
    entries.clear();
    pool.clear();
    dirs.clear();
    table.clear();
    name_order.reset();
    live = 0;
    gen++;
    version++;
    struct_version++;
    dirs_version++;
}

uint32_t Index::new_dir(const std::wstring& path, uint32_t entry) {
    uint32_t did = (uint32_t)dirs.size();
    dirs.emplace_back();
    DirRec& d = dirs.back();
    d.path = path;
    d.entry = entry;
    table.insert(dirs, did, path);
    if (entry != NONE) entries[entry].dir = did;
    dirs_version++;
    return did;
}

uint32_t Index::add_entry(uint32_t did, const wchar_t* nm, size_t n, bool isdir, int64_t size, int64_t mtime,
                          uint8_t flags) {
    Entry e;
    e.parent = did;
    e.name_off = pool.add(nm, n);
    e.name_len = (uint16_t)(n > 0xFFFF ? 0xFFFF : n);
    e.dir = NONE;
    e.kind = isdir ? K_DIR : K_FILE;
    e.flags = flags;
    e.size = isdir ? -1 : size;
    e.mtime = mtime;
    uint32_t i = (uint32_t)entries.size();
    entries.push_back(e);
    dirs[did].children.push_back(i);
    live++;
    struct_version++;
    return i;
}

void Index::remove_entry(uint32_t i0, std::vector<uint32_t>& removed_dirs) {
    std::vector<uint32_t> stack{i0};
    while (!stack.empty()) {
        uint32_t e = stack.back();
        stack.pop_back();
        Entry& en = entries[e];
        if (en.kind == K_DEAD) continue;
        if (en.kind == K_DIR && en.dir != NONE) {
            uint32_t did = en.dir;
            DirRec& d = dirs[did];
            for (uint32_t c : d.children)
                if (entries[c].kind != K_DEAD) stack.push_back(c);
            d.children.clear();
            d.children.shrink_to_fit();
            if (!d.dead) {
                table.erase(dirs, did, d.path);
                d.dead = true;
                d.path.clear();
                d.path.shrink_to_fit();
                dirs_version++;
                removed_dirs.push_back(did);
            }
            en.dir = NONE;
        }
        en.kind = K_DEAD;
        live--;
        struct_version++;
    }
}

void Index::remove_root(uint32_t did, std::vector<uint32_t>& removed) {
    DirRec& d = dirs[did];
    if (d.dead) return;
    std::vector<uint32_t> kids;
    kids.swap(d.children);
    for (uint32_t c : kids) remove_entry(c, removed);
    DirRec& d2 = dirs[did];
    table.erase(dirs, did, d2.path);
    d2.dead = true;
    d2.path.clear();
    removed.push_back(did);
    dirs_version++;
    version++;
    struct_version++;
}

uint32_t Index::find_dir(const std::wstring& path) const {
    std::wstring low = to_lower(path);
    return table.find(dirs, low.data(), low.size());
}

std::wstring Index::fullpath(uint32_t i) const {
    const Entry& e = entries[i];
    const DirRec& d = dirs[e.parent];
    if (d.dead) return std::wstring();
    return join_path(d.path, name(i), e.name_len);
}

std::vector<uint32_t> Index::root_dirs() const {
    std::vector<uint32_t> r;
    for (uint32_t d = 0; d < dirs.size(); d++)
        if (!dirs[d].dead && dirs[d].entry == NONE) r.push_back(d);
    return r;
}

size_t Index::live_dirs() const {
    size_t n = 0;
    for (auto& d : dirs) if (!d.dead) n++;
    return n;
}

size_t Index::mem_estimate() const {
    size_t m = entries.mem() + pool.mem() + table.mem() + dirs.capacity() * sizeof(DirRec);
    for (auto& d : dirs) m += d.path.capacity() * sizeof(wchar_t) + d.children.capacity() * 4;
    auto no = name_order;
    if (no) m += no->order.capacity() * 4 + no->rank.capacity() * 4;
    return m;
}

// lowercase compare of two virtual strings a1+a2 vs b1+b2
static int cmp2_low(const std::wstring& a1, const wchar_t* a2, size_t na2, const std::wstring& b1, const wchar_t* b2,
                    size_t nb2, bool lower) {
    size_t na = a1.size() + na2, nb = b1.size() + nb2;
    size_t n = na < nb ? na : nb;
    for (size_t i = 0; i < n; i++) {
        wchar_t x = i < a1.size() ? a1[i] : a2[i - a1.size()];
        wchar_t y = i < b1.size() ? b1[i] : b2[i - b1.size()];
        if (lower) { x = lower_ch(x); y = lower_ch(y); }
        if (x != y) return cp_key(x) < cp_key(y) ? -1 : 1;
    }
    return na < nb ? -1 : (na > nb ? 1 : 0);
}

int Index::compare_name_path(uint32_t a, uint32_t b) const {
    if (a == b) return 0;
    const Entry& ea = entries[a];
    const Entry& eb = entries[b];
    int c = cp_compare(pool.low(ea.name_off), ea.name_len, pool.low(eb.name_off), eb.name_len);
    if (c) return c;
    const std::wstring da = dir_prefix(dirs[ea.parent].path), db = dir_prefix(dirs[eb.parent].path);
    c = cmp2_low(da, pool.orig(ea.name_off), ea.name_len, db, pool.orig(eb.name_off), eb.name_len, true);
    if (c) return c;
    c = cmp2_low(da, pool.orig(ea.name_off), ea.name_len, db, pool.orig(eb.name_off), eb.name_len, false);
    if (c) return c;
    return a < b ? -1 : 1;
}

std::shared_ptr<NameOrder> Index::compute_order() const {
    auto no = std::make_shared<NameOrder>();
    uint32_t n = (uint32_t)entries.size();
    no->n = n;
    no->gen = gen.load();
    no->order.reserve((size_t)live.load() + 16);
    for (uint32_t i = 0; i < n; i++)
        if (entries[i].kind != K_DEAD) no->order.push_back(i);
    // Fast path: compare names first; only ties need the (rare) path comparison.
    std::sort(no->order.begin(), no->order.end(), [this](uint32_t a, uint32_t b) {
        const Entry& ea = entries[a];
        const Entry& eb = entries[b];
        int c = cp_compare(pool.low(ea.name_off), ea.name_len, pool.low(eb.name_off), eb.name_len);
        if (c) return c < 0;
        return compare_name_path(a, b) < 0;
    });
    no->rank.assign(n, NONE);
    for (uint32_t r = 0; r < no->order.size(); r++) no->rank[no->order[r]] = r;
    return no;
}

// ---------------------------------------------------------------- cache I/O
static const char MAGIC[8] = {'Q', 'X', 'I', 'D', 'X', '1', 0, 0};
static const uint32_t FORMAT = 2;

static FILE* open_file(const std::wstring& fn, const char* mode) {
#ifdef _WIN32
    std::wstring m(mode, mode + strlen(mode));
    return _wfopen(fn.c_str(), m.c_str());
#else
    return fopen(to_utf8(fn).c_str(), mode);
#endif
}

namespace {
inline uint64_t mix(uint64_t h, const unsigned char* c, size_t n) {
    for (size_t i = 0; i < n; i++) h = (h ^ c[i]) * 1099511628211ULL;
    return h;
}
struct Writer {
    FILE* f;
    std::vector<char> buf;
    bool ok = true;
    uint64_t sum = 1469598103934665603ULL;
    explicit Writer(FILE* fp) : f(fp) { buf.reserve(1 << 20); }
    void raw(const void* p, size_t n) {
        const unsigned char* c = (const unsigned char*)p;
        sum = mix(sum, c, n);
        buf.insert(buf.end(), c, c + n);
        if (buf.size() >= (1 << 20)) flush();
    }
    void flush() {
        if (!buf.empty() && fwrite(buf.data(), 1, buf.size(), f) != buf.size()) ok = false;
        buf.clear();
    }
    void u8(uint8_t v) { raw(&v, 1); }
    void u16(uint16_t v) { raw(&v, 2); }
    void u32(uint32_t v) { raw(&v, 4); }
    void i64(int64_t v) { raw(&v, 8); }
    void str(const wchar_t* s, size_t n) {
        u32((uint32_t)n);
        for (size_t i = 0; i < n; i++) u16((uint16_t)s[i]);
    }
    void str(const std::wstring& s) { str(s.data(), s.size()); }
};
struct Reader {
    FILE* f;
    std::vector<char> buf;
    size_t pos = 0, len = 0;
    bool ok = true;
    uint64_t sum = 1469598103934665603ULL;
    explicit Reader(FILE* fp) : f(fp), buf(1 << 20) {}
    bool fill() {
        if (pos < len) return true;
        len = fread(buf.data(), 1, buf.size(), f);
        pos = 0;
        return len > 0;
    }
    void raw(void* p, size_t n) {
        unsigned char* c = (unsigned char*)p;
        size_t got = 0;
        while (got < n) {
            if (!fill()) { ok = false; memset(c + got, 0, n - got); return; }
            size_t k = std::min(n - got, len - pos);
            memcpy(c + got, buf.data() + pos, k);
            pos += k;
            got += k;
        }
        sum = mix(sum, c, n);
    }
    uint8_t u8() { uint8_t v = 0; raw(&v, 1); return v; }
    uint16_t u16() { uint16_t v = 0; raw(&v, 2); return v; }
    uint32_t u32() { uint32_t v = 0; raw(&v, 4); return v; }
    int64_t i64() { int64_t v = 0; raw(&v, 8); return v; }
    bool str(std::wstring& s, uint32_t maxlen = 70000) {
        uint32_t n = u32();
        if (!ok || n > maxlen) { ok = false; return false; }
        s.resize(n);
        for (uint32_t i = 0; i < n; i++) s[i] = (wchar_t)u16();
        return ok;
    }
};
} // namespace

bool Index::save(const std::wstring& fn, const CacheHeader& h) const {
    std::wstring tmp = fn + L".tmp";
    FILE* f = open_file(tmp, "wb");
    if (!f) return false;
    Writer w(f);
    w.raw(MAGIC, 8);
    w.u32(FORMAT);
    w.u32((uint32_t)h.roots.size());
    for (auto& r : h.roots) w.str(r);
    w.u32((uint32_t)h.excludes.size());
    for (auto& e : h.excludes) w.str(e);
    // compact: live dirs and live entries renumbered
    uint32_t n = (uint32_t)entries.size();
    std::vector<uint32_t> emap(n, NONE), dmap(dirs.size(), NONE);
    uint32_t ne = 0, nd = 0;
    for (uint32_t d = 0; d < dirs.size(); d++) if (!dirs[d].dead) dmap[d] = nd++;
    for (uint32_t i = 0; i < n; i++) {
        const Entry& e = entries[i];
        if (e.kind != K_DEAD && dmap[e.parent] != NONE) emap[i] = ne++;
    }
    w.u32(nd);
    for (uint32_t d = 0; d < dirs.size(); d++) {
        if (dirs[d].dead) continue;
        uint32_t ent = dirs[d].entry == NONE ? NONE : emap[dirs[d].entry];
        w.u32(ent);
        w.i64(dirs[d].mtime);
        w.str(dirs[d].path);
    }
    w.u32(ne);
    for (uint32_t i = 0; i < n; i++) {
        if (emap[i] == NONE) continue;
        const Entry& e = entries[i];
        unsigned char rec[24];
        uint32_t par = dmap[e.parent];
        memcpy(rec, &par, 4);
        rec[4] = e.kind;
        rec[5] = e.flags;
        memcpy(rec + 6, &e.size, 8);
        memcpy(rec + 14, &e.mtime, 8);
        memcpy(rec + 22, &e.name_len, 2);
        w.raw(rec, 24);
        const wchar_t* s = name(i);
        if (sizeof(wchar_t) == 2) w.raw(s, (size_t)e.name_len * 2);
        else for (uint32_t k = 0; k < e.name_len; k++) w.u16((uint16_t)s[k]);
    }
    uint64_t sum = w.sum;
    w.raw(&sum, 8);
    w.flush();
    bool ok = w.ok && fflush(f) == 0;
    fclose(f);
    if (!ok) {
#ifdef _WIN32
        DeleteFileW(tmp.c_str());
#endif
        return false;
    }
#ifdef _WIN32
    return MoveFileExW(tmp.c_str(), fn.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
#else
    return rename(to_utf8(tmp).c_str(), to_utf8(fn).c_str()) == 0;
#endif
}

bool Index::load(const std::wstring& fn, const CacheHeader& want) {
    FILE* f = open_file(fn, "rb");
    if (!f) return false;
    Reader r(f);
    char mg[8];
    r.raw(mg, 8);
    bool ok = r.ok && memcmp(mg, MAGIC, 8) == 0 && r.u32() == FORMAT;
    CacheHeader h;
    if (ok) {
        uint32_t nr = r.u32();
        for (uint32_t k = 0; k < nr && r.ok && nr < 10000; k++) { std::wstring s; r.str(s); h.roots.push_back(s); }
        uint32_t nx = r.u32();
        for (uint32_t k = 0; k < nx && r.ok && nx < 100000; k++) { std::wstring s; r.str(s); h.excludes.push_back(s); }
        ok = r.ok && h == want;
    }
    if (!ok) { fclose(f); return false; }
    // build into a fresh index, then swap under the write lock
    std::unique_ptr<Index> tmp(new Index());
    uint32_t nd = r.u32();
    if (!r.ok || nd > 100000000) { fclose(f); return false; }
    std::vector<uint32_t> dent(nd);
    tmp->dirs.reserve(nd);
    for (uint32_t d = 0; d < nd && r.ok; d++) {
        dent[d] = r.u32();
        int64_t mt = r.i64();
        std::wstring p;
        if (!r.str(p)) break;
        tmp->dirs.emplace_back();
        tmp->dirs.back().path = p;
        tmp->dirs.back().mtime = mt;
        tmp->dirs.back().entry = NONE;
    }
    uint32_t ne = r.u32();
    if (!r.ok || ne > 400000000) { fclose(f); return false; }
    std::vector<wchar_t> nb(70000);
    for (uint32_t i = 0; i < ne && r.ok; i++) {
        unsigned char rec[24];
        r.raw(rec, 24);
        uint32_t par;
        int64_t size, mt;
        uint16_t len;
        memcpy(&par, rec, 4);
        uint8_t kind = rec[4], flags = rec[5];
        memcpy(&size, rec + 6, 8);
        memcpy(&mt, rec + 14, 8);
        memcpy(&len, rec + 22, 2);
        if (sizeof(wchar_t) == 2) r.raw(nb.data(), (size_t)len * 2);
        else for (uint32_t k = 0; k < len; k++) nb[k] = (wchar_t)r.u16();
        if (!r.ok || par >= nd || kind > K_DIR) { r.ok = false; break; }
        tmp->add_entry(par, nb.data(), len, kind == K_DIR, size, mt, flags);
    }
    uint64_t expect = r.sum;
    uint64_t got = 0;
    r.raw(&got, 8);
    fclose(f);
    if (!r.ok || got != expect) return false;
    for (uint32_t d = 0; d < nd; d++) {
        uint32_t e = dent[d];
        if (e != NONE) {
            if (e >= ne || tmp->entries[e].kind != K_DIR) return false;
            tmp->dirs[d].entry = e;
            tmp->entries[e].dir = d;
        }
        tmp->table.insert(tmp->dirs, d, tmp->dirs[d].path);
    }
    WriteGuard g(lock);
    std::swap(entries, tmp->entries);
    std::swap(pool, tmp->pool);
    std::swap(dirs, tmp->dirs);
    std::swap(table, tmp->table);
    name_order.reset();
    live = (int64_t)ne;
    gen++;
    version++;
    struct_version++;
    dirs_version++;
    return true;
}

} // namespace qx
