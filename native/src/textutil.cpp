// 千寻 —— 文本工具实现（平台无关部分）
#include "textutil.h"
#include <emmintrin.h>
#include <cstring>

namespace qx {

wchar_t g_lower[65536];
uint8_t g_word[65536];

void text_init() {
    static bool done = false;
    if (done) return;
    done = true;
    for (uint32_t i = 0; i < 65536; i++) { g_lower[i] = (wchar_t)i; g_word[i] = 0; }
    plat_init_tables(g_lower, g_word);
    // ASCII parts are fixed regardless of platform behaviour
    for (uint32_t c = 0; c < 128; c++) {
        g_lower[c] = (wchar_t)((c >= 'A' && c <= 'Z') ? c + 32 : c);
        g_word[c] = (uint8_t)(((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_') ? 1 : 0);
    }
    // surrogates: never folded; word-ness of a pair is decided on the decoded code point (is_word_cp)
    for (uint32_t c = 0xD800; c < 0xE000; c++) { g_lower[c] = (wchar_t)c; g_word[c] = 0; }
}

bool is_word_cp(uint32_t c) {
    if (c < 0x10000) return g_word[c] != 0;
    // supplementary planes: historic scripts, math alphanumerics, CJK extensions are letters (Python str.isalnum);
    // emoji / symbols / private use are not
    if (c < 0x1BD00) return true;
    if (c >= 0x1D400 && c < 0x1D800) return true;
    if (c >= 0x1E800 && c < 0x1E960) return true;
    if (c >= 0x20000 && c < 0x323B0) return true;
    return false;
}

bool word_before(const wchar_t* s, size_t pos) {
    if (pos == 0) return false;
    uint32_t c = (uint32_t)s[pos - 1];
    if (sizeof(wchar_t) == 2 && c >= 0xDC00 && c < 0xE000 && pos >= 2) {
        uint32_t h = (uint32_t)s[pos - 2];
        if (h >= 0xD800 && h < 0xDC00) return is_word_cp(0x10000 + ((h - 0xD800) << 10) + (c - 0xDC00));
    }
    return c < 0x10000 ? g_word[c] != 0 : is_word_cp(c);
}

bool word_after(const wchar_t* s, size_t n, size_t pos) {
    if (pos >= n) return false;
    uint32_t c = (uint32_t)s[pos];
    if (sizeof(wchar_t) == 2 && c >= 0xD800 && c < 0xDC00 && pos + 1 < n) {
        uint32_t l = (uint32_t)s[pos + 1];
        if (l >= 0xDC00 && l < 0xE000) return is_word_cp(0x10000 + ((c - 0xD800) << 10) + (l - 0xDC00));
    }
    return c < 0x10000 ? g_word[c] != 0 : is_word_cp(c);
}

int py_digit(wchar_t c) {
    uint32_t u = (uint32_t)c;
    if (u >= '0' && u <= '9') return (int)(u - '0');
    static const uint32_t zeros[] = {0xFF10, 0x0660, 0x06F0, 0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6,
                                     0x0C66, 0x0CE6, 0x0D66, 0x0E50, 0x0ED0, 0x0F20, 0x1040, 0x17E0, 0x1810};
    for (uint32_t z : zeros)
        if (u >= z && u <= z + 9) return (int)(u - z);
    return -1;
}

void to_lower_inplace(wchar_t* p, size_t n) {
    for (size_t i = 0; i < n; i++) p[i] = lower_ch(p[i]);
}

std::wstring to_lower(const std::wstring& s) {
    std::wstring r(s);
    to_lower_inplace(&r[0], r.size());
    return r;
}

std::wstring py_strip(const std::wstring& s) {
    size_t a = 0, b = s.size();
    while (a < b && py_isspace(s[a])) a++;
    while (b > a && py_isspace(s[b - 1])) b--;
    return s.substr(a, b - a);
}

std::string to_utf8(const wchar_t* s, size_t n) {
    std::string out;
    out.reserve(n + n / 2);
    for (size_t i = 0; i < n; i++) {
        uint32_t c = (uint32_t)s[i];
        if (sizeof(wchar_t) == 2 && c >= 0xD800 && c < 0xDC00 && i + 1 < n &&
            (uint32_t)s[i + 1] >= 0xDC00 && (uint32_t)s[i + 1] < 0xE000) {
            c = 0x10000 + ((c - 0xD800) << 10) + ((uint32_t)s[i + 1] - 0xDC00);
            i++;
        } else if (c >= 0xD800 && c < 0xE000) {
            c = 0xFFFD;   // lone surrogate (NTFS allows it) → replacement char, like Python 'replace'
        }
        if (c < 0x80) out += (char)c;
        else if (c < 0x800) { out += (char)(0xC0 | (c >> 6)); out += (char)(0x80 | (c & 0x3F)); }
        else if (c < 0x10000) {
            out += (char)(0xE0 | (c >> 12)); out += (char)(0x80 | ((c >> 6) & 0x3F)); out += (char)(0x80 | (c & 0x3F));
        } else {
            out += (char)(0xF0 | (c >> 18)); out += (char)(0x80 | ((c >> 12) & 0x3F));
            out += (char)(0x80 | ((c >> 6) & 0x3F)); out += (char)(0x80 | (c & 0x3F));
        }
    }
    return out;
}

std::wstring from_utf8(const std::string& s) {
    std::wstring out;
    out.reserve(s.size());
    size_t i = 0, n = s.size();
    while (i < n) {
        unsigned char b = (unsigned char)s[i];
        uint32_t c;
        int extra;
        if (b < 0x80) { c = b; extra = 0; }
        else if ((b & 0xE0) == 0xC0) { c = b & 0x1F; extra = 1; }
        else if ((b & 0xF0) == 0xE0) { c = b & 0x0F; extra = 2; }
        else if ((b & 0xF8) == 0xF0) { c = b & 0x07; extra = 3; }
        else { out += (wchar_t)0xFFFD; i++; continue; }
        bool ok = true;
        for (int k = 1; k <= extra; k++) {
            if (i + k >= n || (((unsigned char)s[i + k]) & 0xC0) != 0x80) { ok = false; break; }
            c = (c << 6) | (((unsigned char)s[i + k]) & 0x3F);
        }
        if (!ok) { out += (wchar_t)0xFFFD; i++; continue; }
        i += extra + 1;
        if (sizeof(wchar_t) == 2 && c >= 0x10000) {
            c -= 0x10000;
            out += (wchar_t)(0xD800 + (c >> 10));
            out += (wchar_t)(0xDC00 + (c & 0x3FF));
        } else {
            out += (wchar_t)c;
        }
    }
    return out;
}

const wchar_t* find_sub_simd(const wchar_t* h, size_t hn, const wchar_t* nd, size_t nn) {
    if (nn > hn) return nullptr;
    const size_t last = hn - nn;            // last valid start position
    const size_t L = 16 / sizeof(wchar_t);  // lanes per vector
    const wchar_t* p = h;
    size_t i = 0;
    if (nn == 1 || sizeof(wchar_t) != 2) {
        // generic: first char only
        if (sizeof(wchar_t) == 2) {
            const __m128i v0 = _mm_set1_epi16((short)nd[0]);
            for (; i + L <= last + 1; i += L) {
                __m128i x = _mm_loadu_si128((const __m128i*)(p + i));
                unsigned m = (unsigned)_mm_movemask_epi8(_mm_cmpeq_epi16(x, v0));
                while (m) {
                    unsigned b = (unsigned)__builtin_ctz(m) / 2;
                    if (memcmp(p + i + b, nd, nn * sizeof(wchar_t)) == 0) return p + i + b;
                    m &= ~(3u << (b * 2));
                }
            }
        } else {
            const __m128i v0 = _mm_set1_epi32((int)nd[0]);
            for (; i + L <= last + 1; i += L) {
                __m128i x = _mm_loadu_si128((const __m128i*)(p + i));
                unsigned m = (unsigned)_mm_movemask_epi8(_mm_cmpeq_epi32(x, v0));
                while (m) {
                    unsigned b = (unsigned)__builtin_ctz(m) / 4;
                    if (memcmp(p + i + b, nd, nn * sizeof(wchar_t)) == 0) return p + i + b;
                    m &= ~(15u << (b * 4));
                }
            }
        }
    } else {
        const __m128i v0 = _mm_set1_epi16((short)nd[0]);
        const __m128i v1 = _mm_set1_epi16((short)nd[1]);
        // need p[i+b+1] readable: i + L + 1 <= hn  ⇐  i + L <= last + 1 (since nn >= 2)
        for (; i + L <= last + 1; i += L) {
            __m128i x0 = _mm_loadu_si128((const __m128i*)(p + i));
            __m128i x1 = _mm_loadu_si128((const __m128i*)(p + i + 1));
            unsigned m = (unsigned)_mm_movemask_epi8(_mm_and_si128(_mm_cmpeq_epi16(x0, v0), _mm_cmpeq_epi16(x1, v1)));
            while (m) {
                unsigned b = (unsigned)__builtin_ctz(m) / 2;
                if (nn == 2 || memcmp(p + i + b + 2, nd + 2, (nn - 2) * sizeof(wchar_t)) == 0) return p + i + b;
                m &= ~(3u << (b * 2));
            }
        }
    }
    const wchar_t* r = find_sub_scalar(p + i, hn - i, nd, nn);
    return r;
}

std::wstring fmt_thousands(long long v) {
    bool neg = v < 0;
    unsigned long long u = neg ? (unsigned long long)(-(v + 1)) + 1 : (unsigned long long)v;
    std::wstring d;
    int k = 0;
    do {
        if (k && k % 3 == 0) d += L',';
        d += (wchar_t)(L'0' + (u % 10));
        u /= 10;
        k++;
    } while (u);
    if (neg) d += L'-';
    return std::wstring(d.rbegin(), d.rend());
}

} // namespace qx
