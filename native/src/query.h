// 千寻 —— 搜索语法解析（与 qianxun.py 的 Query 逐条一致，平台无关）
// Compiles an Everything-style query into groups: AND between groups, OR inside a group, optional NOT per group.
#pragma once
#include <string>
#include <vector>
#include <memory>
#include <regex>
#include <cstdint>

namespace qx {

// Regex traits: Python-like Unicode \w \d \s classes and fast table-based case folding.
struct QxTraits : public std::regex_traits<wchar_t> {
    wchar_t translate_nocase(wchar_t c) const;
    bool isctype(wchar_t c, char_class_type f) const;
};
typedef std::basic_regex<wchar_t, QxTraits> QxRegex;
// Translate Python `re` syntax differences to ECMAScript (exposed for tests). Throws std::runtime_error.
std::wstring py_regex_to_ecma(const std::wstring& pat, bool* force_icase);

enum PredKind : uint8_t { P_ALL, P_FILE, P_FOLDER, P_EXT, P_SIZE, P_DM, P_SUB, P_WILD, P_REGEX, P_WHOLE };

// fnmatch-compatible glob (Python 3.13 fnmatch.translate semantics, full-string match)
struct GlobClass {
    bool neg = false;
    std::vector<std::pair<uint32_t, uint32_t>> ranges;
    bool match(wchar_t c) const {
        uint32_t u = (uint32_t)c;
        bool hit = false;
        for (auto& r : ranges) if (u >= r.first && u <= r.second) { hit = true; break; }
        return hit != neg;
    }
};
struct GlobTok {
    enum T : uint8_t { LIT, ANY, STAR, CLASS, NEVER } t;
    wchar_t c;
    int cls;
};
struct Glob {
    std::vector<GlobTok> toks;
    std::vector<GlobClass> classes;
    // fast paths for name-only matching: 0 none, 1 exact, 2 suffix (*lit), 3 prefix (lit*), 4 contains (*lit*)
    int fast = 0;
    std::wstring lit;
    void analyze();
    bool compile(const std::wstring& pat, std::wstring* err);   // false on (theoretical) error
    // match the virtual string a[0..na) + b[0..nb)
    bool match2(const wchar_t* a, size_t na, const wchar_t* b, size_t nb) const;
    bool match(const wchar_t* s, size_t n) const;
private:
    bool single(const GlobTok& t, wchar_t c) const {
        switch (t.t) {
            case GlobTok::LIT: return t.c == c;
            case GlobTok::ANY: return true;
            case GlobTok::CLASS: return classes[(size_t)t.cls].match(c);
            default: return false;
        }
    }
};

struct Pred {
    PredKind kind = P_ALL;
    std::wstring text;          // SUB/WILD/WHOLE: comparison text (lowercased unless case-sensitive)
    bool path = false;          // match against full path
    int cost = 1;
    int want_kind = -1;         // file:xxx / folder:xxx → 0 / 1
    std::vector<std::wstring> exts;
    long long lo = 0, hi = 0;   // size range
    double dlo = 0, dhi = 0;    // date range (epoch seconds)
    std::shared_ptr<Glob> glob;
    std::shared_ptr<QxRegex> rx;
};

struct Group {
    bool neg = false;
    std::vector<Pred> alts;
};

struct QueryOpts {
    bool case_ = false, whole = false, match_path = false, regex = false;
    bool operator==(const QueryOpts& o) const {
        return case_ == o.case_ && whole == o.whole && match_path == o.match_path && regex == o.regex;
    }
};

class Query {
public:
    Query() {}
    Query(const std::wstring& text, const QueryOpts& o, const std::wstring& extra = std::wstring());
    std::wstring text;
    QueryOpts opts;
    std::vector<Group> groups;
    std::vector<std::wstring> highlights;
    std::wstring error;          // non-empty = syntax error (no results)
    bool ok() const { return error.empty(); }
    bool is_plain() const;
    bool uses_stats() const;     // contains size:/dm:
private:
    void compile(const std::wstring& text, const std::wstring& extra);
    bool term(const std::wstring& t, Pred& out);          // false = None (dropped)
    Pred text_term(std::wstring t, bool force_path);
    Pred and_kind(const std::wstring& val, int kind);
    std::shared_ptr<QxRegex> make_regex(const std::wstring& pat);
};

// Exposed for unit tests
std::vector<std::wstring> split_tokens(const std::wstring& q);
std::vector<std::wstring> split_or(const std::wstring& tok);
bool size_range(const std::wstring& v, long long& lo, long long& hi, std::wstring& err);
bool date_range(const std::wstring& v, double& lo, double& hi, std::wstring& err);

extern const wchar_t* const FILTER_NAMES[9];
extern const wchar_t* const FILTER_EXPR[9];
const int FILTER_COUNT = 9;

} // namespace qx
