// 千寻 QianXun —— 文本工具（平台无关）：小写折叠表、Python 兼容的空白/单词字符判定、码点序比较、UTF-8 转换。
// Platform-neutral text helpers. Tables are filled once by plat_init_tables() (Windows: LCMapStringW /
// GetStringTypeW; Linux unit test: towlower / iswalnum).
#pragma once
#include <string>
#include <vector>
#include <cstdint>
#include <cstddef>
#include <cwchar>

namespace qx {

// ---- platform hooks (plat_win.cpp / plat_linux.cpp) ----
// lower[c] = simple 1:1 lowercase of BMP code unit c; word[c] = 1 if c is a Python-regex "\w" char.
void plat_init_tables(wchar_t* lower, uint8_t* word);
double plat_now();                                         // epoch seconds (UTC)
void plat_today(int& y, int& m, int& d, int& wday_mon0);   // local date; Monday = 0
double plat_local_midnight(int y, int m, int d);           // epoch seconds of local 00:00 of that date

void text_init();   // must be called once before anything else

extern wchar_t g_lower[65536];
extern uint8_t g_word[65536];

#if WCHAR_MAX > 0xFFFF
inline wchar_t lower_ch(wchar_t c) { return ((uint32_t)c < 65536u) ? g_lower[(uint32_t)c] : c; }
inline bool is_word_ch(wchar_t c) { return ((uint32_t)c < 65536u) ? g_word[(uint32_t)c] != 0 : true; }
#else
inline wchar_t lower_ch(wchar_t c) { return g_lower[(uint16_t)c]; }
inline bool is_word_ch(wchar_t c) { return g_word[(uint16_t)c] != 0; }
#endif
bool is_word_cp(uint32_t cp);                                  // Python "\w" on a code point
bool word_before(const wchar_t* s, size_t pos);                // is the char before s[pos] a word char
bool word_after(const wchar_t* s, size_t n, size_t pos);       // is s[pos] a word char (handles surrogate pairs)
// Python str.isspace()
inline bool py_isspace(wchar_t c) {
    uint32_t u = (uint32_t)c;
    if (u <= 0x20) return u == 0x20 || (u >= 0x09 && u <= 0x0D) || (u >= 0x1C && u <= 0x1F);
    if (u < 0x85) return false;
    return u == 0x85 || u == 0xA0 || u == 0x1680 || (u >= 0x2000 && u <= 0x200A) || u == 0x2028 ||
           u == 0x2029 || u == 0x202F || u == 0x205F || u == 0x3000;
}
// Python \d (ASCII + fullwidth + a few common Nd blocks) → digit value or -1
int py_digit(wchar_t c);

std::wstring to_lower(const std::wstring& s);
void to_lower_inplace(wchar_t* p, size_t n);
std::wstring py_strip(const std::wstring& s);

// Compare UTF-16 strings in Unicode code point order (Python str ordering).
inline uint32_t cp_key(wchar_t c) {
    uint32_t u = (uint32_t)c;
    if (sizeof(wchar_t) == 2) {
        if (u >= 0xD800 && u < 0xE000) return u + 0x2000;
        if (u >= 0xE000 && u <= 0xFFFF) return u - 0x800;
    }
    return u;
}
inline int cp_compare(const wchar_t* a, size_t na, const wchar_t* b, size_t nb) {
    size_t n = na < nb ? na : nb;
    for (size_t i = 0; i < n; i++) {
        if (a[i] != b[i]) {
            uint32_t x = cp_key(a[i]), y = cp_key(b[i]);
            return x < y ? -1 : 1;
        }
    }
    return na < nb ? -1 : (na > nb ? 1 : 0);
}

std::string to_utf8(const wchar_t* s, size_t n);
inline std::string to_utf8(const std::wstring& s) { return to_utf8(s.data(), s.size()); }
std::wstring from_utf8(const std::string& s);

// Fast substring search (needle non-empty). Returns pointer to first match or nullptr.
// SSE2: compare the first two needle chars 8 (UTF-16) / 4 (UTF-32) positions at a time.
inline const wchar_t* find_sub_scalar(const wchar_t* h, size_t hn, const wchar_t* nd, size_t nn) {
    if (nn > hn) return nullptr;
    const wchar_t c0 = nd[0];
    const wchar_t* end = h + (hn - nn);
    if (nn == 1) {
        for (const wchar_t* p = h; p <= end; ++p) if (*p == c0) return p;
        return nullptr;
    }
    const wchar_t c1 = nd[1];
    for (const wchar_t* p = h; p <= end; ++p) {
        if (*p == c0 && p[1] == c1) {
            size_t k = 2;
            while (k < nn && p[k] == nd[k]) k++;
            if (k == nn) return p;
        }
    }
    return nullptr;
}
const wchar_t* find_sub_simd(const wchar_t* h, size_t hn, const wchar_t* nd, size_t nn);
inline const wchar_t* find_sub(const wchar_t* h, size_t hn, const wchar_t* nd, size_t nn) {
    if (hn < 24) return find_sub_scalar(h, hn, nd, nn);
    return find_sub_simd(h, hn, nd, nn);
}

std::wstring fmt_thousands(long long v);   // 1,234,567

} // namespace qx
