// 千寻 —— 命令行测试接口（规格第 9 节，供差分测试）
//   QianXun.exe --cli --root <dir> [--root …] --query "<q>" [--case] [--whole] [--path] [--regex]
//               [--filter <n>] --out <file>
//     不建窗口；扫描给定根后执行一次查询；匹配项完整路径按“名称不区分大小写升序、同名按路径”排序，
//     逐行写入 --out（UTF-8，LF）；最后一行 "#count=<N> #ms=<查询毫秒>"；退出码 0。
//     查询有语法错误时，在最后一行之前多写一行 "#error=<说明>"（count=0）。
//   QianXun.exe --cli-watch … --duration <秒>
//     扫描后进入实时监控：先写 "#ready t=<epoch 秒> count=<N> entries=<条目数>"，此后每 100 ms 追加一行
//     "<epoch 秒，3 位小数> <当前结果数>"，结束写 "#end"。
//   附加（仅自测用）：--threads <n> 扫描线程数；--stats 额外写 "#stat …" 行；
//     --synthetic <N> 不扫描磁盘，在内存中生成 N 个合成条目（用于百万级查询延迟基准）；--repeat <k>；
//     --batch <file> 一次执行多条查询（每行 "选项4位\t筛选序号\t查询"，输出 "Q<n> ok|err count=<N>" 与匹配路径）。
#include "app.h"
#include "engine.h"
#include "search.h"
#include "textutil.h"
#include <psapi.h>
#include <cstdio>
#include <algorithm>

namespace qx {

static void err_out(const std::wstring& s) {
    HANDLE h = GetStdHandle(STD_ERROR_HANDLE);
    std::string u = to_utf8(s) + "\n";
    DWORD w;
    if (h && h != INVALID_HANDLE_VALUE) WriteFile(h, u.data(), (DWORD)u.size(), &w, nullptr);
    log_line(L"cli: %ls", s.c_str());
}

class OutFile {
public:
    explicit OutFile(const std::wstring& fn) {
        h_ = CreateFileW(fn.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    }
    ~OutFile() { flush(); if (ok()) CloseHandle(h_); }
    bool ok() const { return h_ != INVALID_HANDLE_VALUE; }
    void line(const std::string& s) { buf_ += s; buf_ += '\n'; if (buf_.size() > (1 << 20)) flush(); }
    void flush() {
        if (!ok() || buf_.empty()) return;
        DWORD w;
        WriteFile(h_, buf_.data(), (DWORD)buf_.size(), &w, nullptr);
        buf_.clear();
    }
private:
    HANDLE h_;
    std::string buf_;
};

static size_t proc_mem_mb() {
    PROCESS_MEMORY_COUNTERS pmc = {};
    pmc.cb = sizeof pmc;
    if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof pmc)) return pmc.PagefileUsage / (1024 * 1024);
    return 0;
}

// synthetic index: realistic-ish names and a moderate tree (for latency benchmarks)
static void build_synthetic(Index& idx, size_t n) {
    static const wchar_t* syl[] = {L"an", L"bo", L"chen", L"da", L"er", L"fu", L"ge", L"hui", L"ji", L"ka", L"lu", L"mo",
                                   L"ni", L"ou", L"pi", L"qu", L"ru", L"si", L"tu", L"wa", L"xi", L"ya", L"zh", L"报告",
                                   L"项目", L"照片", L"数据", L"文档", L"会议", L"Test", L"Data", L"IMG_", L"backup",
                                   L"final", L"v2", L"Program", L"Files", L"Windows", L"System32"};
    static const wchar_t* ext[] = {L"txt", L"docx", L"pdf", L"jpg", L"png", L"exe", L"dll", L"py", L"c", L"h",
                                   L"mp4", L"zip", L"log", L"xml", L"json", L"cpp"};
    uint64_t s = 88172645463325252ULL;
    auto rnd = [&]() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; };
    WriteGuard g(idx.lock);
    uint32_t root = idx.new_dir(L"C:\\", NONE);
    std::vector<uint32_t> dirs{root};
    std::vector<int> depth{0};
    wchar_t nb[256];
    for (size_t i = 0; i < n; i++) {
        size_t k = (size_t)(rnd() % dirs.size());
        if (dirs.size() > 64 && rnd() % 3) k = dirs.size() - 1 - (size_t)(rnd() % 64);
        uint32_t par = dirs[k];
        std::wstring nm;
        int parts = 1 + (int)(rnd() % 3);
        for (int p = 0; p < parts; p++) nm += syl[rnd() % (sizeof syl / sizeof *syl)];
        nm += std::to_wstring(rnd() % 1000);
        bool isdir = rnd() % 10 == 0 && depth[k] < 8;
        if (isdir) {
            swprintf(nb, 256, L"%ls_%zu", nm.c_str(), i);
            uint32_t e = idx.add_entry(par, nb, wcslen(nb), true, -1, FT_EPOCH + (int64_t)(rnd() % 1700000000) * 10000000);
            uint32_t d = idx.new_dir(join_path(idx.dirs[par].path, nb), e);
            dirs.push_back(d);
            depth.push_back(depth[k] + 1);
        } else {
            nm += L".";
            nm += ext[rnd() % (sizeof ext / sizeof *ext)];
            idx.add_entry(par, nm.data(), nm.size(), false, (int64_t)(rnd() % 100000000),
                          FT_EPOCH + (int64_t)(1600000000 + rnd() % 160000000) * 10000000);
        }
    }
    idx.version++;
}

static std::string fmt_ms(double ms) {
    char b[64];
    snprintf(b, sizeof b, "%.3f", ms);
    return b;
}

int cli_main(int argc, wchar_t** argv) {
    bool watch = false, stats = false;
    std::vector<std::wstring> roots;
    std::wstring query, out, batch;
    QueryOpts o;
    int filter = 0, threads = 0, repeat = 1;
    double duration = 10;
    size_t synthetic = 0;
    for (int i = 1; i < argc; i++) {
        std::wstring a = argv[i];
        auto next = [&](std::wstring& v) {
            if (i + 1 >= argc) { err_out(L"缺少参数值：" + a); return false; }
            v = argv[++i];
            return true;
        };
        std::wstring v;
        if (a == L"--cli") {}
        else if (a == L"--cli-watch") watch = true;
        else if (a == L"--root") { if (!next(v)) return 2; roots.push_back(v); }
        else if (a == L"--query") { if (!next(v)) return 2; query = v; }
        else if (a == L"--out") { if (!next(v)) return 2; out = v; }
        else if (a == L"--case") o.case_ = true;
        else if (a == L"--whole") o.whole = true;
        else if (a == L"--path") o.match_path = true;
        else if (a == L"--regex") o.regex = true;
        else if (a == L"--filter") { if (!next(v)) return 2; filter = _wtoi(v.c_str()); }
        else if (a == L"--duration") { if (!next(v)) return 2; duration = _wtof(v.c_str()); }
        else if (a == L"--threads") { if (!next(v)) return 2; threads = _wtoi(v.c_str()); }
        else if (a == L"--synthetic") { if (!next(v)) return 2; synthetic = (size_t)_wtoi64(v.c_str()); }
        else if (a == L"--repeat") { if (!next(v)) return 2; repeat = std::max(1, _wtoi(v.c_str())); }
        else if (a == L"--stats") stats = true;
        else if (a == L"--batch") { if (!next(v)) return 2; batch = v; }
        else { err_out(L"未知参数：" + a); return 2; }
    }
    if (out.empty()) { err_out(L"缺少 --out"); return 2; }
    if (filter < 0 || filter >= FILTER_COUNT) filter = 0;
    std::vector<std::wstring> nroots;
    for (auto& r : roots) {
        std::wstring n = win_norm_path(r, true);
        if (!is_dir(n)) { err_out(L"根目录不存在：" + r); return 2; }
        bool dup = false;
        for (auto& x : nroots) if (to_lower(x) == to_lower(n)) dup = true;
        if (!dup) nroots.push_back(n);
    }
    if (nroots.empty() && !synthetic) { err_out(L"缺少 --root"); return 2; }
    OutFile of(out);
    if (!of.ok()) { err_out(L"无法写入输出文件：" + out); return 2; }

    SYSTEM_INFO si;
    GetSystemInfo(&si);
    int ncpu = std::max(1, (int)si.dwNumberOfProcessors);
    Index idx;
    ThreadPool pool(std::min(ncpu, 16));
    std::wstring extra = FILTER_EXPR[filter];

    double last_search_ms = 0, last_sort_ms = 0;
    auto run_query = [&](std::vector<uint32_t>& rows, double& ms, Query& q, bool sort_full) {
        double t0 = now_sec();
        q = Query(query, o, extra);
        Searcher S(idx, pool);
        S.case_ = o.case_;
        ReadGuard g(idx.lock);
        S.run(q, extra, rows, CancelFn());
        double t1 = now_sec();
        if (sort_full) {
            auto no = idx.name_order;
            if (no && no->gen == idx.gen.load()) S.sort_rows(rows, 0, false, nullptr, CancelFn());   // same order, uses ranks
            else std::sort(rows.begin(), rows.end(), [&](uint32_t a, uint32_t b) { return idx.compare_name_path(a, b) < 0; });
        }
        double t2 = now_sec();
        ms = (t2 - t0) * 1000.0;
        last_search_ms = (t1 - t0) * 1000.0;
        last_sort_ms = (t2 - t1) * 1000.0;
    };

    if (!watch) {
        double ts = now_sec();
        if (synthetic) build_synthetic(idx, synthetic);
        else {
            std::vector<uint32_t> starts;
            {
                WriteGuard g(idx.lock);
                for (auto& r : nroots) starts.push_back(idx.new_dir(r, NONE));
            }
            int nt = threads > 0 ? threads : std::max(2, std::min(8, ncpu * 2));
            scan_tree(idx, starts, make_excludes({}, nroots), nullptr, nt);
        }
        double scan_s = now_sec() - ts;
        {   // presorted name order, like the GUI (built after the scan; not part of the query time)
            auto no = idx.compute_order();
            WriteGuard g(idx.lock);
            idx.name_order = no;
        }
        if (!batch.empty()) {
            HANDLE h = CreateFileW(batch.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
            if (h == INVALID_HANDLE_VALUE) { err_out(L"无法读取 " + batch); return 2; }
            std::string data;
            char buf[65536];
            DWORD n;
            while (ReadFile(h, buf, sizeof buf, &n, nullptr) && n) data.append(buf, n);
            CloseHandle(h);
            Searcher S(idx, pool);
            size_t pos = 0;
            int qn = 0;
            while (pos < data.size()) {
                size_t e = data.find('\n', pos);
                std::string line = data.substr(pos, e == std::string::npos ? std::string::npos : e - pos);
                pos = e == std::string::npos ? data.size() : e + 1;
                size_t t1 = line.find('\t'), t2 = t1 == std::string::npos ? t1 : line.find('\t', t1 + 1);
                if (t2 == std::string::npos || t1 < 4) continue;
                QueryOpts bo;
                bo.case_ = line[0] == '1'; bo.whole = line[1] == '1'; bo.match_path = line[2] == '1'; bo.regex = line[3] == '1';
                int bf = atoi(line.substr(t1 + 1, t2 - t1 - 1).c_str());
                if (bf < 0 || bf >= FILTER_COUNT) bf = 0;
                std::wstring bx = FILTER_EXPR[bf];
                Query bq(from_utf8(line.substr(t2 + 1)), bo, bx);
                std::vector<uint32_t> br;
                ReadGuard g(idx.lock);
                S.case_ = bo.case_;
                S.run(bq, bx, br, CancelFn());
                std::sort(br.begin(), br.end(), [&](uint32_t a, uint32_t b) { return idx.compare_name_path(a, b) < 0; });
                of.line("Q" + std::to_string(qn++) + (bq.ok() ? " ok" : " err") + " count=" + std::to_string(br.size()));
                for (uint32_t i : br) of.line("  " + to_utf8(idx.fullpath(i)));
            }
            return 0;
        }
        std::vector<uint32_t> rows;
        double ms = 0, best = 1e18, total = 0;
        Query q;
        for (int k = 0; k < repeat; k++) {
            run_query(rows, ms, q, true);
            best = std::min(best, ms);
            total += ms;
        }
        if (!synthetic) {
            ReadGuard g(idx.lock);
            for (uint32_t i : rows) of.line(to_utf8(idx.fullpath(i)));
        }
        if (stats) {
            of.line("#stat entries=" + std::to_string(idx.live.load()) + " dirs=" + std::to_string(idx.dirs.size()) +
                    " scan_s=" + fmt_ms(scan_s) + " rate=" + std::to_string((long long)(idx.live.load() / std::max(scan_s, 1e-6))) +
                    "/s index_mb=" + std::to_string(idx.mem_estimate() / (1024 * 1024)) + " proc_mb=" +
                    std::to_string(proc_mem_mb()) + " best_ms=" + fmt_ms(best) + " avg_ms=" + fmt_ms(total / repeat) + " last_search_ms=" + fmt_ms(last_search_ms) +
                    " last_sort_ms=" + fmt_ms(last_sort_ms) +
                    " threads=" + std::to_string(pool.size()));
        }
        if (stats && synthetic) {   // cache round trip timing
            wchar_t tp[MAX_PATH];
            GetTempPathW(MAX_PATH, tp);
            std::wstring fn = std::wstring(tp) + L"qx_bench_index.bin";
            CacheHeader h;
            h.roots.push_back(L"C:\\");
            double c0 = now_sec();
            bool sok = idx.save(fn, h);
            double c1 = now_sec();
            Index i2;
            bool lok = i2.load(fn, h);
            double c2 = now_sec();
            WIN32_FILE_ATTRIBUTE_DATA fa = {};
            GetFileAttributesExW(fn.c_str(), GetFileExInfoStandard, &fa);
            of.line(std::string("#stat cache_save_s=") + fmt_ms(c1 - c0) + (sok ? "" : "(FAILED)") + " cache_load_s=" + fmt_ms(c2 - c1) +
                    (lok ? "" : "(FAILED)") + " cache_mb=" + std::to_string(fa.nFileSizeLow / (1024 * 1024)) +
                    " loaded_entries=" + std::to_string(i2.live.load()) + " proc_mb_after=" + std::to_string(proc_mem_mb()));
            DeleteFileW(fn.c_str());
        }
        if (!q.ok()) of.line("#error=" + to_utf8(q.error));
        of.line("#count=" + std::to_string(rows.size()) + " #ms=" + fmt_ms(ms));
        return 0;
    }

    // ---- watch mode: real engine (scan + ReadDirectoryChangesW), poll the query every 100 ms
    Config cfg;
    cfg.roots = nroots;
    cfg.index_removable = false;
    cfg.index_network = false;
    Engine eng(idx, cfg, true);
    eng.start();
    while (eng.status().state != L"ready") {
        if (eng.status().state == L"error") { err_out(eng.status().msg); return 3; }
        Sleep(20);
    }
    std::vector<uint32_t> rows;
    double ms;
    Query q;
    run_query(rows, ms, q, false);
    of.line("#ready t=" + fmt_ms(plat_now()) + " count=" + std::to_string(rows.size()) + " entries=" +
            std::to_string(idx.live.load()));
    of.flush();
    double end = now_sec() + duration;
    double next = now_sec();
    while (now_sec() < end) {
        next += 0.1;
        run_query(rows, ms, q, false);
        of.line(fmt_ms(plat_now()) + " " + std::to_string(rows.size()));
        of.flush();
        double wait = next - now_sec();
        if (wait > 0) Sleep((DWORD)(wait * 1000));
        else next = now_sec();
    }
    of.line("#end");
    of.flush();
    eng.post_quit();
    eng.join(5000);
    return 0;
}

} // namespace qx
