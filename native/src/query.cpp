// 千寻 —— 搜索语法解析实现。语义逐条对照 qianxun.py：split_tokens / split_or / Query._compile /
// Query._term / Query._text_term / size_range / date_range / fnmatch.translate（Python 3.13）。
#include "query.h"
#include "textutil.h"
#include <algorithm>
#include <cmath>
#include <climits>
#include <cstdlib>
#include <cwchar>
#include <stdexcept>

namespace qx {

const wchar_t* const FILTER_NAMES[9] = {L"所有", L"文件夹", L"文档", L"图片", L"音频", L"视频",
                                        L"压缩包", L"可执行/脚本", L"代码"};
const wchar_t* const FILTER_EXPR[9] = {
    L"",
    L"folder:",
    L"ext:doc;docx;wps;wpt;dot;rtf;odt;pdf;ofd;txt;md;xls;xlsx;et;csv;ods;ppt;pptx;dps;odp;vsd;vsdx;html;htm;xml;json;tex;epub;chm",
    L"ext:jpg;jpeg;png;gif;bmp;tif;tiff;webp;svg;ico;heic;raw;cr2;nef;arw;dng;psd;ai;eps",
    L"ext:mp3;wav;flac;aac;m4a;ogg;opus;wma;ape;amr;mid;midi",
    L"ext:mp4;mkv;avi;mov;wmv;flv;webm;m4v;mpg;mpeg;ts;m2ts;3gp;rmvb;rm;insv;lrv",
    L"ext:zip;rar;7z;tar;gz;tgz;bz2;xz;zst;lz4;iso;deb;rpm;cab;jar",
    L"ext:sh;py;run;appimage;bin;exe;msi;bat;cmd;desktop;so",
    L"ext:c;cc;cpp;cxx;h;hpp;py;java;js;ts;go;rs;cs;m;swift;kt;lua;sql;qml;ui;cmake;pro",
};

static const wchar_t SEP = L'\\';
static const long long BIG = 1LL << 62;

// ---------------------------------------------------------------- tokenizing
std::vector<std::wstring> split_tokens(const std::wstring& q) {
    std::vector<std::wstring> toks;
    std::wstring cur;
    bool inq = false;
    for (wchar_t ch : q) {
        if (ch == L'"') { inq = !inq; cur += ch; }
        else if (py_isspace(ch) && !inq) {
            if (!cur.empty()) { toks.push_back(cur); cur.clear(); }
        } else cur += ch;
    }
    if (!cur.empty()) toks.push_back(cur);
    return toks;
}

std::vector<std::wstring> split_or(const std::wstring& tok) {
    std::vector<std::wstring> parts;
    std::wstring cur;
    bool inq = false;
    for (wchar_t ch : tok) {
        if (ch == L'"') { inq = !inq; cur += ch; }
        else if (ch == L'|' && !inq) { parts.push_back(cur); cur.clear(); }
        else cur += ch;
    }
    parts.push_back(cur);
    std::vector<std::wstring> out;
    for (auto& p : parts) if (!p.empty()) out.push_back(p);
    return out;
}

static bool starts_with(const std::wstring& s, const wchar_t* p) {
    size_t n = 0;
    while (p[n]) n++;
    return s.size() >= n && s.compare(0, n, p) == 0;
}

// ---------------------------------------------------------------- size:
static long long sat_ll(double v) {
    if (v >= 9.2e18) return LLONG_MAX;
    if (v <= -9.2e18) return LLONG_MIN;
    return (long long)v;   // truncation, like int(float)
}

static bool parse_size(const std::wstring& s0, long long& out, std::wstring& err) {
    std::wstring s = to_lower(s0);
    size_t i = 0, n = s.size();
    while (i < n && py_isspace(s[i])) i++;
    std::string num;
    while (i < n && py_digit(s[i]) >= 0) { num += (char)('0' + py_digit(s[i])); i++; }
    if (num.empty()) { err = s0; return false; }
    if (i < n && s[i] == L'.' && i + 1 < n && py_digit(s[i + 1]) >= 0) {
        num += '.';
        i++;
        while (i < n && py_digit(s[i]) >= 0) { num += (char)('0' + py_digit(s[i])); i++; }
    }
    while (i < n && py_isspace(s[i])) i++;
    std::wstring unit;
    while (i < n && s[i] >= L'a' && s[i] <= L'z') unit += s[i++];
    while (i < n && py_isspace(s[i])) i++;
    if (i != n) { err = s0; return false; }
    double mul;
    if (unit.empty() || unit == L"b") mul = 1;
    else if (unit == L"k" || unit == L"kb") mul = 1024.0;
    else if (unit == L"m" || unit == L"mb") mul = 1048576.0;
    else if (unit == L"g" || unit == L"gb") mul = 1073741824.0;
    else if (unit == L"t" || unit == L"tb") mul = 1099511627776.0;
    else { err = s0; return false; }
    double v = strtod(num.c_str(), nullptr);
    if (std::isinf(v) || std::isinf(v * mul)) { err = L"cannot convert float infinity to integer"; return false; }
    out = sat_ll(v * mul);
    return true;
}

bool size_range(const std::wstring& v0, long long& lo, long long& hi, std::wstring& err) {
    std::wstring v = to_lower(py_strip(v0));
    struct W { const wchar_t* w; long long a, b; };
    static const W words[] = {
        {L"empty", 0, 0}, {L"tiny", 0, 10 * 1024}, {L"small", 10 * 1024, 100 * 1024},
        {L"medium", 100 * 1024, 1024 * 1024}, {L"large", 1024 * 1024, 16LL * 1024 * 1024},
        {L"huge", 16LL * 1024 * 1024, 128LL * 1024 * 1024}, {L"gigantic", 128LL * 1024 * 1024, BIG}};
    for (auto& w : words) if (v == w.w) { lo = w.a; hi = w.b; return true; }
    size_t dd = v.find(L"..");
    if (dd != std::wstring::npos) {
        std::wstring a = v.substr(0, dd), b = v.substr(dd + 2);
        lo = 0; hi = BIG;
        if (!a.empty() && !parse_size(a, lo, err)) return false;
        if (!b.empty() && !parse_size(b, hi, err)) return false;
        return true;
    }
    static const wchar_t* ops[] = {L">=", L"<=", L">", L"<", L"="};
    for (int k = 0; k < 5; k++) {
        if (starts_with(v, ops[k])) {
            long long x;
            if (!parse_size(v.substr(wcslen(ops[k])), x, err)) return false;
            switch (k) {
                case 0: lo = x; hi = BIG; break;
                case 1: lo = 0; hi = x; break;
                case 2: lo = (x == LLONG_MAX) ? x : x + 1; hi = BIG; break;
                case 3: lo = 0; hi = (x == LLONG_MIN) ? x : x - 1; break;
                default: lo = hi = x; break;
            }
            return true;
        }
    }
    long long x;
    if (!parse_size(v, x, err)) return false;
    lo = hi = x;
    return true;
}

// ---------------------------------------------------------------- dm:
// civil date helpers (proleptic Gregorian), days since 1970-01-01
static long long days_from_civil(long long y, unsigned m, unsigned d) {
    y -= m <= 2;
    const long long era = (y >= 0 ? y : y - 399) / 400;
    const unsigned yoe = (unsigned)(y - era * 400);
    const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + (long long)doe - 719468;
}
static void civil_from_days(long long z, int& y, int& m, int& d) {
    z += 719468;
    const long long era = (z >= 0 ? z : z - 146096) / 146097;
    const unsigned doe = (unsigned)(z - era * 146097);
    const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    long long yy = (long long)yoe + era * 400;
    const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    const unsigned mp = (5 * doy + 2) / 153;
    d = (int)(doy - (153 * mp + 2) / 5 + 1);
    m = (int)(mp < 10 ? mp + 3 : mp - 9);
    y = (int)(yy + (m <= 2));
}
static int days_in_month(int y, int m) {
    static const int dm[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (m == 2) return ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0) ? 29 : 28;
    return dm[m - 1];
}
static double day_start_days(long long days) {
    int y, m, d;
    civil_from_days(days, y, m, d);
    return plat_local_midnight(y, m, d);
}

bool date_range(const std::wstring& v0, double& lo, double& hi, std::wstring& err) {
    std::wstring v = to_lower(py_strip(v0));
    size_t dd = v.find(L"..");
    if (dd != std::wstring::npos) {
        std::wstring a = v.substr(0, dd), b = v.substr(dd + 2);
        double alo = 0, ahi = 0, blo = 0, bhi = 4e9;
        if (!a.empty() && !date_range(a, alo, ahi, err)) return false;
        if (!b.empty() && !date_range(b, blo, bhi, err)) return false;
        lo = alo; hi = bhi;
        return true;
    }
    int ty, tm, td, wd;
    plat_today(ty, tm, td, wd);
    long long today = days_from_civil(ty, (unsigned)tm, (unsigned)td);
    if (v == L"today") { lo = day_start_days(today); hi = day_start_days(today + 1); return true; }
    if (v == L"yesterday") { lo = day_start_days(today - 1); hi = day_start_days(today); return true; }
    if (v == L"thisweek") { lo = day_start_days(today - wd); hi = 4e9; return true; }
    if (v == L"thismonth") { lo = plat_local_midnight(ty, tm, 1); hi = 4e9; return true; }
    if (v == L"thisyear") { lo = plat_local_midnight(ty, 1, 1); hi = 4e9; return true; }
    // ^(?:last)?(\d+)(d|days?|w|weeks?|m|months?|y|years?)$
    {
        std::wstring s = starts_with(v, L"last") ? v.substr(4) : v;
        size_t i = 0;
        std::string num;
        while (i < s.size() && py_digit(s[i]) >= 0) { num += (char)('0' + py_digit(s[i])); i++; }
        if (!num.empty()) {
            std::wstring u = s.substr(i);
            int mult = 0;
            if (u == L"d" || u == L"day" || u == L"days") mult = 1;
            else if (u == L"w" || u == L"week" || u == L"weeks") mult = 7;
            else if (u == L"m" || u == L"month" || u == L"months") mult = 30;
            else if (u == L"y" || u == L"year" || u == L"years") mult = 365;
            if (mult) {
                double k = strtod(num.c_str(), nullptr);
                double sec = k * mult * 86400.0;
                if (std::isinf(sec)) { err = L"int too large to convert to float"; return false; }
                lo = plat_now() - sec;
                hi = 4e9;
                return true;
            }
        }
    }
    // ^(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?$
    {
        auto issep = [](wchar_t c) { return c == L'-' || c == L'/' || c == L'.'; };
        size_t i = 0, n = v.size();
        int y = 0, k = 0;
        while (i < n && k < 4 && py_digit(v[i]) >= 0) { y = y * 10 + py_digit(v[i]); i++; k++; }
        if (k == 4) {
            int parts[2] = {-1, -1};
            int np = 0;
            bool okp = true;
            while (i < n && np < 2) {
                if (!issep(v[i])) { okp = false; break; }
                i++;
                int x = 0, c = 0;
                while (i < n && c < 2 && py_digit(v[i]) >= 0) { x = x * 10 + py_digit(v[i]); i++; c++; }
                if (!c) { okp = false; break; }
                parts[np++] = x;
            }
            if (okp && i == n) {
                if (y < 1 || y > 9999) { err = L"year " + std::to_wstring(y) + L" is out of range"; return false; }
                if (np == 2) {
                    int mo = parts[0], d = parts[1];
                    if (mo < 1 || mo > 12) { err = L"month must be in 1..12"; return false; }
                    if (d < 1 || d > days_in_month(y, mo)) { err = L"day is out of range for month"; return false; }
                    if (y == 9999 && mo == 12 && d == 31) { err = L"date value out of range"; return false; }
                    long long dn = days_from_civil(y, (unsigned)mo, (unsigned)d);
                    lo = day_start_days(dn);
                    hi = day_start_days(dn + 1);
                    return true;
                }
                if (np == 1) {
                    int mo = parts[0];
                    if (mo < 1 || mo > 12) { err = L"month must be in 1..12"; return false; }
                    int y1 = y + (mo == 12), m1 = mo % 12 + 1;
                    if (y1 > 9999) { err = L"year 10000 is out of range"; return false; }
                    lo = plat_local_midnight(y, mo, 1);
                    hi = plat_local_midnight(y1, m1, 1);
                    return true;
                }
                if (y + 1 > 9999) { err = L"year 10000 is out of range"; return false; }
                lo = plat_local_midnight(y, 1, 1);
                hi = plat_local_midnight(y + 1, 1, 1);
                return true;
            }
        }
    }
    err = v;
    return false;
}

// ---------------------------------------------------------------- glob (fnmatch.translate)
// Parse a Python regex character-class body (as produced by fnmatch.translate) like sre does.
static bool parse_class_body(const std::wstring& body, GlobClass& cls) {
    size_t i = 0, n = body.size();
    if (i < n && body[i] == L'^') { cls.neg = true; i++; }
    auto item = [&](uint32_t& c) -> bool {
        if (i >= n) return false;
        if (body[i] == L'\\') {
            if (i + 1 >= n) return false;
            c = (uint32_t)body[i + 1];
            i += 2;
        } else {
            c = (uint32_t)body[i++];
        }
        return true;
    };
    while (i < n) {
        uint32_t a;
        if (!item(a)) return false;
        if (i < n && body[i] == L'-' && i + 1 < n) {
            i++;
            uint32_t b;
            if (!item(b)) return false;
            if (b < a) return false;    // "bad character range"
            cls.ranges.push_back({a, b});
        } else {
            cls.ranges.push_back({a, a});
        }
    }
    return true;
}

bool Glob::compile(const std::wstring& pat, std::wstring* err) {
    toks.clear();
    classes.clear();
    size_t i = 0, n = pat.size();
    while (i < n) {
        wchar_t c = pat[i++];
        if (c == L'*') {
            toks.push_back({GlobTok::STAR, 0, 0});
            while (i < n && pat[i] == L'*') i++;
        } else if (c == L'?') {
            toks.push_back({GlobTok::ANY, 0, 0});
        } else if (c == L'[') {
            size_t j = i;
            if (j < n && pat[j] == L'!') j++;
            if (j < n && pat[j] == L']') j++;
            while (j < n && pat[j] != L']') j++;
            if (j >= n) {
                toks.push_back({GlobTok::LIT, L'[', 0});
                continue;
            }
            std::wstring stuff = pat.substr(i, j - i);
            auto esc = [](const std::wstring& s, bool hyph) {
                std::wstring r;
                for (wchar_t ch : s) {
                    if (ch == L'\\') r += L"\\\\";
                    else if (hyph && ch == L'-') r += L"\\-";
                    else r += ch;
                }
                return r;
            };
            if (stuff.find(L'-') == std::wstring::npos) {
                stuff = esc(stuff, false);
            } else {
                std::vector<std::wstring> chunks;
                size_t ii = i;
                size_t k = (pat[ii] == L'!') ? ii + 2 : ii + 1;
                while (true) {
                    size_t f = std::wstring::npos;
                    for (size_t q = k; q < j; q++) if (pat[q] == L'-') { f = q; break; }
                    if (f == std::wstring::npos) break;
                    chunks.push_back(pat.substr(ii, f - ii));
                    ii = f + 1;
                    k = f + 3;
                }
                std::wstring chunk = pat.substr(ii, j - ii);
                if (!chunk.empty()) chunks.push_back(chunk);
                else if (!chunks.empty()) chunks.back() += L'-';
                for (size_t q = chunks.size() - 1; q >= 1 && q < chunks.size(); q--) {
                    if (!chunks[q - 1].empty() && !chunks[q].empty() &&
                        (uint32_t)chunks[q - 1].back() > (uint32_t)chunks[q][0]) {
                        chunks[q - 1] = chunks[q - 1].substr(0, chunks[q - 1].size() - 1) + chunks[q].substr(1);
                        chunks.erase(chunks.begin() + (long)q);
                    }
                }
                stuff.clear();
                for (size_t q = 0; q < chunks.size(); q++) {
                    if (q) stuff += L'-';
                    stuff += esc(chunks[q], true);
                }
            }
            i = j + 1;
            if (stuff.empty()) {
                toks.push_back({GlobTok::NEVER, 0, 0});
            } else if (stuff == L"!") {
                toks.push_back({GlobTok::ANY, 0, 0});
            } else {
                std::wstring s2;
                for (wchar_t ch : stuff) {   // escape set operations & ~ |
                    if (ch == L'&' || ch == L'~' || ch == L'|') s2 += L'\\';
                    s2 += ch;
                }
                if (s2[0] == L'!') s2 = L"^" + s2.substr(1);
                else if (s2[0] == L'^' || s2[0] == L'[') s2 = L"\\" + s2;
                GlobClass gc;
                if (!parse_class_body(s2, gc)) {
                    if (err) *err = L"bad character range";
                    return false;
                }
                classes.push_back(gc);
                toks.push_back({GlobTok::CLASS, 0, (int)classes.size() - 1});
            }
        } else {
            toks.push_back({GlobTok::LIT, c, 0});
        }
    }
    return true;
}

void Glob::analyze() {
    fast = 0;
    lit.clear();
    size_t m = toks.size();
    bool lead = m && toks[0].t == GlobTok::STAR, trail = m > 1 && toks[m - 1].t == GlobTok::STAR;
    size_t a = lead ? 1 : 0, b = trail ? m - 1 : m;
    if (a > b) return;
    for (size_t i = a; i < b; i++) {
        if (toks[i].t != GlobTok::LIT) return;
        lit += toks[i].c;
    }
    if (lit.empty()) return;
    fast = lead ? (trail ? 4 : 2) : (trail ? 3 : 1);
}

bool Glob::match(const wchar_t* s, size_t n) const {
    size_t ln = lit.size();
    switch (fast) {
        case 1: return n == ln && wmemcmp(s, lit.data(), ln) == 0;
        case 2: return n >= ln && wmemcmp(s + n - ln, lit.data(), ln) == 0;
        case 3: return n >= ln && wmemcmp(s, lit.data(), ln) == 0;
        case 4: return find_sub(s, n, lit.data(), ln) != nullptr;
        default: return match2(nullptr, 0, s, n);
    }
}

bool Glob::match2(const wchar_t* a, size_t na, const wchar_t* b, size_t nb) const {
    const size_t n = na + nb, m = toks.size();
    auto at = [&](size_t i) -> wchar_t { return i < na ? a[i] : b[i - na]; };
    size_t p = 0, s = 0, starP = (size_t)-1, starS = 0;
    while (s < n) {
        if (p < m && toks[p].t != GlobTok::STAR && single(toks[p], at(s))) { p++; s++; }
        else if (p < m && toks[p].t == GlobTok::STAR) { starP = p++; starS = s; }
        else if (starP != (size_t)-1) { p = starP + 1; s = ++starS; }
        else return false;
    }
    while (p < m && toks[p].t == GlobTok::STAR) p++;
    return p == m;
}

// ---------------------------------------------------------------- Query
Query::Query(const std::wstring& t, const QueryOpts& o, const std::wstring& extra) : text(t), opts(o) {
    try {
        compile(t, extra);
    } catch (const std::regex_error& e) {
        error = L"正则表达式错误（" + from_utf8(e.what()) + L"）";
        groups.clear();
    } catch (const std::exception& e) {
        error = from_utf8(e.what());
        groups.clear();
    }
    if (!error.empty()) groups.clear();
}

static bool is_abs_term(const std::wstring& t) {
    if (!t.empty() && t[0] == L'\\') return true;
    return t.size() >= 2 && t[1] == L':' && ((t[0] >= L'A' && t[0] <= L'Z') || (t[0] >= L'a' && t[0] <= L'z'));
}

// ---------------------------------------------------------------- regex
wchar_t QxTraits::translate_nocase(wchar_t c) const { return lower_ch(c); }

bool QxTraits::isctype(wchar_t c, char_class_type f) const {
    static const std::regex_traits<wchar_t> base;
    static const wchar_t W[] = L"w", D[] = L"d", S[] = L"s";
    static const char_class_type mw = base.lookup_classname(W, W + 1);
    static const char_class_type md = base.lookup_classname(D, D + 1);
    static const char_class_type ms = base.lookup_classname(S, S + 1);
    if ((f & mw) == mw && is_word_ch(c)) return true;
    if ((f & md) == md && py_digit(c) >= 0) return true;
    if ((f & ms) == ms && py_isspace(c)) return true;
    return base.isctype(c, f);
}

std::wstring py_regex_to_ecma(const std::wstring& p, bool* force_icase) {
    std::wstring o;
    size_t i = 0, n = p.size();
    // leading inline flags (?aiLmsux)
    while (i + 2 < n && p[i] == L'(' && p[i + 1] == L'?') {
        size_t j = i + 2;
        bool flags = true, icase = false;
        while (j < n && p[j] != L')') {
            if (wcschr(L"aiLmsux", p[j]) == nullptr) { flags = false; break; }
            if (p[j] == L'i') icase = true;
            j++;
        }
        if (!flags || j >= n || j == i + 2) break;
        if (icase && force_icase) *force_icase = true;
        i = j + 1;
    }
    auto digits = [&](size_t& j) { size_t s = j; while (j < n && p[j] >= L'0' && p[j] <= L'9') j++; return j > s; };
    bool incls = false;
    while (i < n) {
        wchar_t c = p[i];
        if (c == L'\\') {
            if (i + 1 >= n) throw std::runtime_error("bad escape (end of pattern)");
            wchar_t e = p[i + 1];
            if (!incls && e == L'A') o += L'^';
            else if (!incls && e == L'Z') o += L'$';
            else { o += c; o += e; }
            i += 2;
            continue;
        }
        if (incls) {
            if (c == L']') incls = false;
            o += c;
            i++;
            continue;
        }
        if (c == L'[') {
            o += c;
            i++;
            if (i < n && p[i] == L'^') { o += L'^'; i++; }
            if (i < n && p[i] == L']') { o += L"\\]"; i++; }   // Python: leading ']' is literal
            incls = true;
            continue;
        }
        if (c == L'(' && i + 2 < n && p[i + 1] == L'?' && p[i + 2] == L'P' && i + 3 < n && p[i + 3] == L'<') {
            size_t j = p.find(L'>', i + 4);
            if (j == std::wstring::npos) throw std::runtime_error("missing >, unterminated name");
            o += L'(';
            i = j + 1;
            continue;
        }
        if (c == L'{') {
            // valid Python quantifiers: {n} {n,} {n,m} {,m}; anything else is a literal '{'
            size_t j = i + 1;
            bool d1 = digits(j);
            bool valid = false;
            std::wstring q;
            if (j < n && p[j] == L'}' && d1) { valid = true; q = p.substr(i, j - i + 1); }
            else if (j < n && p[j] == L',') {
                size_t k = j + 1;
                bool d2 = digits(k);
                if (k < n && p[k] == L'}' && (d1 || d2)) {
                    valid = true;
                    q = d1 ? p.substr(i, k - i + 1) : L"{0" + p.substr(j, k - j + 1);
                    j = k;
                }
            }
            if (valid) { o += q; i = j + 1; }
            else { o += L"\\{"; i++; }
            continue;
        }
        if (c == L'}') { o += L"\\}"; i++; continue; }
        o += c;
        i++;
    }
    return o;
}

std::shared_ptr<QxRegex> Query::make_regex(const std::wstring& pat0) {
    // Limits against pathological patterns (libstdc++ regex is recursive).
    if (pat0.size() > 4096) throw std::runtime_error("正则表达式过长");
    bool force_icase = false;
    std::wstring pat = py_regex_to_ecma(pat0, &force_icase);
    int depth = 0, maxd = 0;
    bool backref = false;
    for (size_t i = 0; i < pat.size(); i++) {
        wchar_t c = pat[i];
        if (c == L'\\') {
            if (i + 1 < pat.size() && pat[i + 1] >= L'1' && pat[i + 1] <= L'9') backref = true;
            i++;
            continue;
        }
        if (c == L'(') { depth++; maxd = std::max(maxd, depth); }
        else if (c == L')') depth--;
    }
    if (maxd > 100) throw std::runtime_error("正则表达式嵌套过深");
    auto fl = std::regex_constants::ECMAScript;
    if (!opts.case_ || force_icase) {
        // names are matched in lowercase form (when not case-sensitive); fold literal chars too
        // (escapes such as \D \W \S keep their meaning)
        if (!opts.case_)
            for (size_t i = 0; i < pat.size(); i++) {
                if (pat[i] == L'\\') { i++; continue; }
                pat[i] = lower_ch(pat[i]);
            }
        fl |= std::regex_constants::icase;
    }
    if (!backref) fl |= std::regex_constants::__polynomial;
    return std::make_shared<QxRegex>(pat, fl);
}

void Query::compile(const std::wstring& t0, const std::wstring& extra) {
    if (!extra.empty()) {
        for (auto& t : split_tokens(extra)) {
            Pred p;
            if (term(t, p)) { Group g; g.alts.push_back(p); groups.push_back(g); }
        }
    }
    std::wstring t = py_strip(t0);
    if (t.empty()) return;
    if (opts.regex) {
        Pred p;
        p.kind = P_REGEX;
        p.rx = make_regex(t);
        p.path = opts.match_path;
        p.cost = 5;
        Group g;
        g.alts.push_back(p);
        groups.push_back(g);
        return;
    }
    std::vector<std::wstring> toks;
    for (auto& tok : split_tokens(t)) {
        if (!toks.empty() && ((!tok.empty() && tok[0] == L'|') || (!toks.back().empty() && toks.back().back() == L'|')))
            toks.back() += tok;
        else
            toks.push_back(tok);
    }
    for (auto tok : toks) {
        bool neg = false;
        while (tok.size() > 1 && tok[0] == L'!') { neg = !neg; tok = tok.substr(1); }
        Group g;
        g.neg = neg;
        for (auto& a : split_or(tok)) {
            Pred p;
            if (term(a, p)) g.alts.push_back(p);
        }
        if (!g.alts.empty()) groups.push_back(g);
    }
    std::stable_sort(groups.begin(), groups.end(), [](const Group& x, const Group& y) {
        int cx = 0, cy = 0;
        for (auto& p : x.alts) cx = std::max(cx, p.cost);
        for (auto& p : y.alts) cy = std::max(cy, p.cost);
        if (x.neg != y.neg) return !x.neg;
        return cx < cy;
    });
}

bool Query::term(const std::wstring& t, Pred& out) {
    // ^([a-z]+):(.*)$ on the lowercased token
    std::wstring low = to_lower(t);
    size_t k = 0;
    while (k < low.size() && low[k] >= L'a' && low[k] <= L'z') k++;
    if (k > 0 && k < low.size() && low[k] == L':') {
        std::wstring key = low.substr(0, k);
        static const wchar_t* keys[] = {L"ext", L"file", L"folder", L"dir", L"regex", L"size", L"dm", L"path",
                                        L"case", L"nocase", L"wholeword", L"ww"};
        bool known = false;
        for (auto kk : keys) if (key == kk) known = true;
        if (known) {
            std::wstring val = t.substr(k + 1);
            if (val.size() >= 2 && val.front() == L'"' && val.back() == L'"') val = val.substr(1, val.size() - 2);
            if (key == L"ext") {
                Pred p;
                p.kind = P_EXT;
                p.cost = 2;
                size_t s = 0;
                while (true) {
                    size_t e = val.find(L';', s);
                    std::wstring piece = val.substr(s, e == std::wstring::npos ? std::wstring::npos : e - s);
                    std::wstring st = py_strip(piece);
                    if (!st.empty()) {
                        std::wstring x = to_lower(st);
                        size_t a = 0;
                        while (a < x.size() && x[a] == L'.') a++;
                        x = x.substr(a);
                        if (std::find(p.exts.begin(), p.exts.end(), x) == p.exts.end()) p.exts.push_back(x);
                    }
                    if (e == std::wstring::npos) break;
                    s = e + 1;
                }
                if (p.exts.empty()) return false;
                out = p;
                return true;
            }
            if (key == L"file") {
                if (val.empty()) { out = Pred(); out.kind = P_FILE; out.cost = 2; return true; }
                out = and_kind(val, 0);
                return true;
            }
            if (key == L"folder" || key == L"dir") {
                if (val.empty()) { out = Pred(); out.kind = P_FOLDER; out.cost = 2; return true; }
                out = and_kind(val, 1);
                return true;
            }
            if (key == L"regex") {
                Pred p;
                p.kind = P_REGEX;
                p.rx = make_regex(val);
                p.path = opts.match_path;
                p.cost = 5;
                out = p;
                return true;
            }
            if (key == L"size") {
                Pred p;
                p.kind = P_SIZE;
                p.cost = 8;
                std::wstring err;
                if (!size_range(val, p.lo, p.hi, err)) throw std::runtime_error(to_utf8(L"大小格式无效：" + err));
                out = p;
                return true;
            }
            if (key == L"dm") {
                Pred p;
                p.kind = P_DM;
                p.cost = 8;
                std::wstring err;
                if (!date_range(val, p.dlo, p.dhi, err)) throw std::runtime_error(to_utf8(L"日期格式无效：" + err));
                out = p;
                return true;
            }
            if (key == L"path") { out = text_term(val, true); return true; }
            out = text_term(val, false);   // case: nocase: wholeword: ww: — modifiers accepted, value used as text
            return true;
        }
    }
    out = text_term(t, false);
    return true;
}

Pred Query::and_kind(const std::wstring& val, int kind) {
    Pred p = text_term(val, false);
    if (p.kind == P_ALL) {
        Pred q;
        q.kind = kind == 1 ? P_FOLDER : P_FILE;
        q.cost = 2;
        return q;
    }
    p.want_kind = kind;
    return p;
}

Pred Query::text_term(std::wstring t, bool force_path) {
    if (t.size() >= 2 && t.front() == L'"' && t.back() == L'"') t = t.substr(1, t.size() - 2);
    else t.erase(std::remove(t.begin(), t.end(), L'"'), t.end());
    Pred p;
    if (t.empty()) { p.kind = P_ALL; p.cost = 0; return p; }
    std::replace(t.begin(), t.end(), L'/', L'\\');
    bool path = force_path || opts.match_path || t.find(SEP) != std::wstring::npos;
    std::wstring cmp = opts.case_ ? t : to_lower(t);
    p.path = path;
    if (t.find(L'*') != std::wstring::npos || t.find(L'?') != std::wstring::npos) {
        auto g = std::make_shared<Glob>();
        std::wstring err;
        if (!g->compile(cmp, &err)) throw std::runtime_error(to_utf8(err));
        if (path && t[0] != L'*' && !is_abs_term(t))
            g->toks.insert(g->toks.begin(), GlobTok{GlobTok::STAR, 0, 0});   // 路径通配允许前缀
        g->analyze();
        std::wstring piece;
        for (wchar_t c : cmp) {
            if (c == L'*' || c == L'?') { if (!piece.empty()) highlights.push_back(piece); piece.clear(); }
            else piece += c;
        }
        if (!piece.empty()) highlights.push_back(piece);
        p.kind = P_WILD;
        p.text = cmp;
        p.glob = g;
        p.cost = 4;
        return p;
    }
    if (opts.whole) {
        highlights.push_back(cmp);
        p.kind = P_WHOLE;
        p.text = cmp;
        p.cost = 5;
        return p;
    }
    size_t ls = cmp.rfind(SEP);
    std::wstring last = ls == std::wstring::npos ? cmp : cmp.substr(ls + 1);
    highlights.push_back(last.empty() ? cmp : last);
    p.kind = P_SUB;
    p.text = cmp;
    p.cost = path ? 3 : 1;
    return p;
}

bool Query::is_plain() const {
    if (opts.regex || opts.whole) return false;
    if (py_strip(text).empty()) return false;
    for (wchar_t c : text)
        if (c == L'|' || c == L'!' || c == L'"' || c == L':' || c == L'*' || c == L'?' || c == L'/' ||
            c == L'<' || c == L'>' || c == L'\\')
            return false;
    return true;
}

bool Query::uses_stats() const {
    for (auto& g : groups)
        for (auto& p : g.alts)
            if (p.kind == P_SIZE || p.kind == P_DM) return true;
    return false;
}

} // namespace qx
