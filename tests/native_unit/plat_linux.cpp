// Linux implementation of the platform hooks (unit tests only).
#include "../src/textutil.h"
#include <cwctype>
#include <clocale>
#include <ctime>
#include <sys/time.h>
namespace qx {
void plat_init_tables(wchar_t* lower, uint8_t* word) {
    setlocale(LC_ALL, "C.UTF-8");
    for (uint32_t c = 0; c < 65536; c++) {
        if (c >= 0xD800 && c < 0xE000) continue;
        wint_t l = towlower((wint_t)c);
        lower[c] = (l < 65536) ? (wchar_t)l : (wchar_t)c;
        word[c] = (iswalnum((wint_t)c) || c == '_') ? 1 : 0;
    }
}
double plat_now() { struct timeval tv; gettimeofday(&tv, nullptr); return tv.tv_sec + tv.tv_usec / 1e6; }
void plat_today(int& y, int& m, int& d, int& wd) {
    time_t t = time(nullptr); struct tm tm; localtime_r(&t, &tm);
    y = tm.tm_year + 1900; m = tm.tm_mon + 1; d = tm.tm_mday; wd = (tm.tm_wday + 6) % 7;
}
double plat_local_midnight(int y, int m, int d) {
    struct tm tm = {}; tm.tm_year = y - 1900; tm.tm_mon = m - 1; tm.tm_mday = d; tm.tm_isdst = -1;
    return (double)mktime(&tm);
}
}
