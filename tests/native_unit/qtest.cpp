// Differential unit test: build an Index from a listing, run queries, print sorted matched paths.
#include "../src/index.h"
#include "../src/query.h"
#include "../src/search.h"
#include "../src/textutil.h"
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <chrono>
using namespace qx;
static std::vector<std::string> split(const std::string& s, char c) {
    std::vector<std::string> r; std::string cur;
    for (char ch : s) { if (ch == c) { r.push_back(cur); cur.clear(); } else cur += ch; }
    r.push_back(cur); return r;
}
int main(int argc, char** argv) {
    text_init();
    if (argc < 3) { fprintf(stderr, "usage: qtest listing queries [threads]\n"); return 2; }
    int th = argc > 3 ? atoi(argv[3]) : 2;
    Index idx; ThreadPool pool(th);
    std::ifstream L(argv[1]); std::string line;
    {
        WriteGuard g(idx.lock);
        while (std::getline(L, line)) {
            auto f = split(line, '\t');
            if (f.size() < 4) continue;
            std::wstring p = from_utf8(f[3]);
            if (f[0] == "R") { idx.new_dir(p, NONE); continue; }
            if (f[0] == "X") {  // remove entry by path (dead entries)
                std::wstring par, nm; split_path(p, par, nm);
                uint32_t d = idx.find_dir(par);
                for (uint32_t c : idx.dirs[d].children) if (idx.entries[c].kind != K_DEAD && idx.name_str(c) == nm) { std::vector<uint32_t> rm; idx.remove_entry(c, rm); break; }
                continue;
            }
            std::wstring par, nm; split_path(p, par, nm);
            uint32_t d = idx.find_dir(par);
            if (d == NONE) { fprintf(stderr, "no parent for %s\n", f[3].c_str()); continue; }
            bool isd = f[0] == "D";
            int64_t mt = (int64_t)(atof(f[2].c_str()) * 1e7) + FT_EPOCH;
            uint32_t e = idx.add_entry(d, nm.data(), nm.size(), isd, isd ? -1 : atoll(f[1].c_str()), mt);
            if (isd) idx.new_dir(p, e);
        }
    }
    Searcher S(idx, pool);
    std::ifstream Q(argv[2]);
    int qn = 0;
    bool timing = getenv("QT_TIMING") != nullptr;
    if (getenv("QT_ORDER")) { auto no = idx.compute_order(); idx.name_order = no; }
    while (std::getline(Q, line)) {
        auto f = split(line, '\t');
        if (f.size() < 3) continue;
        QueryOpts o; o.case_ = f[0][0] == '1'; o.whole = f[0][1] == '1'; o.match_path = f[0][2] == '1'; o.regex = f[0][3] == '1';
        int filt = atoi(f[1].c_str());
        std::string qs = f[2];
        for (size_t k = 3; k < f.size(); k++) qs += "\t" + f[k];
        std::wstring extra = FILTER_EXPR[filt];
        auto t0 = std::chrono::steady_clock::now();
        Query q(from_utf8(qs), o, extra);
        std::vector<uint32_t> rows;
        ReadGuard g(idx.lock);
        S.case_ = o.case_;
        if (getenv("QT_FRESH")) S.reset();
        S.run(q, extra, rows, CancelFn());
        S.sort_rows(rows, 0, false, nullptr, CancelFn());
        double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        printf("Q%d %s count=%zu%s\n", qn++, q.ok() ? "ok" : "err", rows.size(), timing ? (" ms=" + std::to_string(ms)).c_str() : "");
        if (!timing) {
            std::vector<std::string> ps;
            for (uint32_t i : rows) ps.push_back(to_utf8(idx.fullpath(i)));
            std::sort(ps.begin(), ps.end());
            for (auto& s : ps) printf("  %s\n", s.c_str());
        }
    }
    return 0;
}
