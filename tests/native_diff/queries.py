"""Differential-test query list for native QianXun (--cli).  Each: dict(id, cat, text, case, whole, path, regex, filter, soft)
soft=True: result depends on a spec-ambiguous / implementation-defined behaviour (reported as INFO, not FAIL)."""

QUERIES = []


def Q(cat, text, case=False, whole=False, path=False, regex=False, filt=0, soft=False, note=''):
    QUERIES.append(dict(id='q%03d' % (len(QUERIES) + 1), cat=cat, text=text, case=case, whole=whole, path=path,
                        regex=regex, filter=filt, soft=soft, note=note))


# ---- plain substrings --------------------------------------------------------------------------
for t in ['report', 'REPORT', '报告', 'img_0001', 'IMG', 'zzqxneedle', 'ZZQXNEEDLE', '独一无二', 'foo', 'readme', '.txt',
          'txt', '2024', '混合mix', 'a;b', "a'b", 'a#b', 'a~b', 'a%20b', '$dollar', '100%', '[brackets]', '{braces}',
          'a+b=c', '★', 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', '长长长长长', 'deepfile_unique_bottom', '深层文件',
          'level_14', 'bf.txt', 'size_1024', 'hidden', 'empty', 'IMG_9999', 'ｂｃ', '日本語', '한국어', 'v1.2.3',
          '..odd', 'a..b', '.gitignore', '.hidden', 'tar.gz', 'file.txt.bak', 'x.jpg']:
    Q('plain', t)
# unicode case folding
for t in ['ä', 'Ä', 'ÄPFEL', 'straße', 'STRASSE', 'ΑΒΓ', 'αβγ', 'ЖУК', 'жук', 'ＡＢＣ', 'ａｂｃ', 'ⅷ', 'Ⅷ', 'ÀÉÎÕÜ', 'àéîõü',
          'NAÏVE CAFÉ', 'emoji', '😀', '𠀀', '扩展b']:
    Q('unicode', t)
Q('unicode', 'İstanbul', soft=True, note='U+0130 lower() differs between Python and Windows')
Q('unicode', 'istanbul', soft=True, note='U+0130 lower() differs between Python and Windows')
Q('unicode', 'ß', soft=True, note='sharp s folding')

# ---- boolean ------------------------------------------------------------------------------------
for t in ['report invoice', 'report !invoice', 'report | invoice', 'report|invoice', '报告 | 发票 !2024', '!report', '!!report',
          'foo bar', 'foo !bar', 'alpha | beta | gamma', 'img_ !jpg', '(a|b)', 'a | b c', 'report !报告 !final',
          '!foo !bar !alpha', 'foo bar baz', 'foo | bar baz', 'IMG_0001 | IMG_0002 | IMG_0003', '!txt !jpg !png report',
          'zzqx needle', 'zzqxneedle | 独一无二', '报告 2024 docx', 'a|b|c|d']:
    Q('boolean', t)
for t in ['foo |', '| foo', 'foo||bar', '|', ' | ', '| |', '!', '!!', '! foo', 'foo !', '!|foo', 'foo|!bar']:
    Q('boolean-edge', t)

# ---- quotes -------------------------------------------------------------------------------------
for t in ['"foo bar"', '"foo_bar"', '"Dr. Who"', '"报告 2024"', '"a b  c"', '"foo bar" baz', '"file (1)"', '"foo bar"|"alpha beta"',
          '!"foo bar"', '"zzqx needle spaced"', '"独一无二的针 副本"', '"report" "final"', '"2024-01-15 notes"']:
    Q('quotes', t)
for t in ['"', '""', '"foo', 'foo"bar', '" "', '"foo bar', 'foo" "bar', '"|"', '!"']:
    Q('quotes-edge', t, soft=(t in ('" "', '"|"')))

# ---- wildcards ----------------------------------------------------------------------------------
for t in ['*.txt', '*.jpg', 'img_*.jpg', 'img_000?.jpg', 'report*', '*report*', '*.tar.gz', '报告*.docx', '*报告*', 'foo?ar',
          '?', '??', '*', 'a*b', 'IMG_00*', 'readme*', '*.*', '*txt', 'x*', '*.JPG', 'IMG_????.JPG', '*_final.*', '*[*',
          '!*.txt', '!img_*', '!*.txt !*.jpg', '*.txt | *.md', 'a?b*', '独一*针*']:
    Q('wild', t)
Q('wild', '*.TXT', case=True)
Q('wild', 'IMG_*', case=True)
Q('wild', 'img_*', case=True)
for t in ['special\\names\\*.txt', 'C:\\corpus\\special\\names\\*.txt', 'c:\\corpus\\special\\*\\*.txt', 'special/names/*.docx',
          '*\\names\\报告*', 'names\\img_*', '*\\src\\*.cpp', '\\dirs\\*\\*.exe', 'C:\\*.exe', 'bulk\\*\\*.mp3',
          'special\\sizes\\size_1*', 'C:\\corpus\\special\\dates\\fixed_2024*', 'dates\\rel_?d_ago.txt', 'x:\\*']:
    Q('wild-path', t)

# ---- path terms ---------------------------------------------------------------------------------
for t in ['special\\names', 'special/names', 'SPECIAL\\NAMES', '\\special\\', 'names\\报告', 'c:\\corpus\\special\\attrs',
          'C:/corpus/special/attrs/', 'corpus\\special\\dirs\\src', 'dirs\\src\\main', 'src\\', '\\main.cpp', 'bulk\\2024',
          '"program files\\"', '"program files (x86)\\app"', 'special\\deep\\level_01', 'deep\\level_14', 'bound\\ppp',
          'loop\\', 'loop\\real_inside', 'C:\\corpus', 'c:\\', 'C:\\corpus\\', '\\', '/', 'x:\\nothing', 'special\\names\\readme',
          '项目A\\报告', '新建文件夹\\新建', 'special\\dirs\\folder.docx\\', 'sizes\\size_1024 !1025', 'dirs\\src\\ | dirs\\docs\\',
          '!special\\ report', 'ppppppppppppppppp\\bf', 'level_14_dddddddddddddd\\deepfile']:
    Q('path', t)
for t in ['path:deepfile_unique', 'path:special names', 'path:报告', 'path:"special\\names"', 'path:corpus', 'path:CORPUS',
          'path:C:\\corpus\\special\\sizes', 'path:\\sizes\\size_1024', 'path:项目A', 'path:src main', 'path:', 'path:"" report',
          'path:special\\dates | path:special\\attrs', 'path:*.docx', 'path:special\\*\\readme']:
    Q('path:', t)

# ---- ext / file / folder -------------------------------------------------------------------------
for t in ['ext:txt', 'ext:TXT', 'ext:jpg;jpeg', 'ext:.jpg', 'ext:gz', 'ext:tar.gz', 'ext:docx report', 'ext:txt;md !readme',
          'ext:', 'ext:;', 'ext:exe|ext:dll', 'ext:bat;sh;c', 'ext:txt 报告', 'ext:"txt;md"', 'ext:dat', 'ext:log;LOG',
          'ext:mp3;flac;wav', 'ext:docx;xlsx;pptx 2024', 'ext:py|ext:cpp', 'ext:zip !backup', '!ext:txt report', 'ext:ini',
          'ext:jpg img', 'ext:sys', 'ext:b', 'ext:html;htm;xml;json']:
    Q('ext', t)
for t in ['file:', 'folder:', 'dir:', 'file:report', 'folder:src', 'folder:photos', 'dir:新建', 'file:*.txt', 'folder:*2024*',
          'folder:"program files"', 'file:"foo bar"', 'folder:docx', 'folder: docx', 'file:报告 | folder:项目', 'folder:""',
          'file:""', 'FOLDER:src', 'File:Report', '!folder: report', '!file: src', 'folder:special\\dirs', 'file:special\\names\\readme',
          'folder:. ', 'file:readme !md', 'dir:2024', 'folder:empty']:
    Q('file-folder', t)

# ---- regex --------------------------------------------------------------------------------------
for t in ['regex:^report', 'regex:\\d{4}$', 'regex:^IMG_\\d+\\.jpg$', 'regex:报告|发票', 'regex:^[a-z]+_\\d+\\.txt$',
          'regex:\\.(jpg|png)$', 'regex:^.{40,}$', 'regex:foo(?=bar)', 'regex:^(?!report).*\\.docx$', 'regex:[\\u4e00-\\u9fff]+2024',
          'regex:', 'regex:.', 'regex:^$', 'regex:a|b', 'regex:report regex:final']:
    Q('regex:', t)
for t in ['regex:"\\.(jpg|png)$"', 'regex:"^(report|invoice)_\\d+"', 'regex:"a b"', 'regex:^img regex:jpg$']:
    Q('regex:', t, note='quoted regex keeps | ; unquoted | splits into OR terms (reference behaviour)')
for t in ['regex:[', 'regex:(', 'regex:*abc', 'regex:a{4294967296}', 'regex:(?P<x>a)', 'regex:\\', 'regex:a{2,1}', 'regex:+']:
    Q('regex-error', t, note='syntax errors differ between Python re and ECMAScript for some; both must not crash',
      soft=t in ('regex:(?P<x>a)', 'regex:a{4294967296}'))
for t in ['regex:(?i)ÄRGER', 'regex:(?s)a.b', 'regex:(?x) rep ort', 'regex:\\Areport', 'regex:(?<n>a)\\k<n>']:
    Q('regex-pyonly', t, soft=True, note='Python-only regex syntax; ECMAScript wregex expected to differ')
for t in ['^report', '\\.(jpg|png)$', '报告\\d+', '^IMG_\\d+', 'a|b', '^$', '.', 'final$', '\\d{4}-\\d{2}-\\d{2}', '[0-9]{5}']:
    Q('regex-toggle', t, regex=True)
for t in ['[', '(unclosed', '*', '\\']:
    Q('regex-toggle-error', t, regex=True)
Q('regex-toggle', '^REPORT', regex=True, case=True)
Q('regex-toggle', '^report', regex=True, case=True)
Q('regex-toggle', '\\\\special\\\\names\\\\IMG', regex=True, path=True)
Q('regex-toggle', 'special.names.img', regex=True, path=True)
Q('regex-toggle', '^C:\\\\corpus\\\\special\\\\dirs\\\\src\\\\', regex=True, path=True)
Q('regex-toggle', 'regex:report', regex=True, soft=True, note='regex: prefix inside regex mode is literal')
Q('regex-toggle', '', regex=True, soft=True)

# ---- size ---------------------------------------------------------------------------------------
for t in ['size:0', 'size:empty', 'size:tiny', 'size:small', 'size:medium', 'size:large', 'size:huge', 'size:gigantic', 'size:>1mb',
          'size:>=1mb', 'size:<1kb', 'size:<=1kb', 'size:=1024', 'size:1024', 'size:1kb', 'size:1k', 'size:1.5mb', 'size:1mb..16mb',
          'size:..1kb', 'size:1gb..', 'size:>1gb', 'size:>=1gb', 'size:3gb', 'size:10kb..100kb', 'size:>100', 'size:large report',
          'size:>1mb ext:bin', 'size:1b', 'size:1tb', 'size:<=0', 'size:5 kb', 'size:>=128mb', 'size:>128mb', 'size:1.5kb',
          'size:EMPTY', 'size:>1MB', 'size:1MB', 'size:10240', 'size:<10240', 'size:..', 'size:0..0', 'size:1..2', 'size:>0 file:',
          'size:>=16mb size:<=128mb', 'size:2gb..4gb', 'size:"1mb"', 'size:>1kb | size:<10', 'size:tiny size:>1b', '!size:>1',
          'size:1.5', 'size:0.5kb', 'size:.5kb', 'size:1 mb']:
    Q('size', t)
for t in ['size:abc', 'size:>', 'size:1xb', 'size:-1', 'size:KB', 'size:', 'size:>>1', 'size:1..2..3', 'size:1,5mb', 'size:1e3']:
    Q('size-error', t)

# ---- dm -----------------------------------------------------------------------------------------
for t in ['dm:today', 'dm:yesterday', 'dm:thisweek', 'dm:thismonth', 'dm:thisyear', 'dm:last7d', 'dm:last2w', 'dm:last1m', 'dm:last1y',
          'dm:last3days', 'dm:7d', 'dm:3weeks', 'dm:2024', 'dm:2024-01', 'dm:2024-1-31', 'dm:2024/02/01', 'dm:2024.12.31',
          'dm:2024-01-01..2024-12-31', 'dm:2023..2024', 'dm:2024-01-01..', 'dm:..2020', 'dm:2019-12', 'dm:2020-02-29', 'dm:2023-12-31',
          'dm:2025-03', 'dm:2026', 'dm:2026-06', 'dm:yesterday..today', 'dm:today..', 'dm:2024-01..2024-03', 'dm:2021 report',
          'dm:2024 ext:docx', 'dm:today folder:', 'dm:2019', 'dm:2019-01-01', 'dm:2024-02-01', 'dm:2025-01-01', 'dm:2026-01-01',
          'dm:last10y', 'dm:last100d', 'dm:LAST7D', 'dm:Today', 'dm:2022..2023-06', 'dm:..', 'dm:2024-12-31', 'dm:2019-12-31',
          'dm:"2024"', '!dm:2024 report', 'dm:2020 | dm:2021', 'dm:fixed']:
    Q('dm', t, soft=(t in ('dm:fixed',)))
for t in ['dm:2024-02-30', 'dm:2024-13', 'dm:abc', 'dm:last', 'dm:lastyear', 'dm:2024-02-29', 'dm:', 'dm:2024-00', 'dm:12345', 'dm:2024-1-1-1']:
    Q('dm-error', t)

# ---- toggles --------------------------------------------------------------------------------------
for t, kw in [('Report', dict(case=True)), ('report', dict(case=True)), ('IMG', dict(case=True)), ('img', dict(case=True)),
              ('报告', dict(case=True)), ('Ä', dict(case=True)), ('ä', dict(case=True)), ('readme', dict(case=True)),
              ('README', dict(case=True)), ('.TXT', dict(case=True)), ('a b', dict(case=True)), ('Foo | foo', dict(case=True)),
              ('!REPORT report', dict(case=True)), ('"MiXeD.TxT"', dict(case=True)), ('mixed.txt', dict(case=True)),
              ('ext:TXT', dict(case=True)), ('ext:txt', dict(case=True)), ('size:1kb', dict(case=True)),
              ('report', dict(whole=True)), ('readme', dict(whole=True)), ('foo', dict(whole=True)), ('报告', dict(whole=True)),
              ('img', dict(whole=True)), ('txt', dict(whole=True)), ('2024', dict(whole=True)), ('size', dict(whole=True)),
              ('file', dict(whole=True)), ('README', dict(whole=True, case=True)), ('a', dict(whole=True)), ('final', dict(whole=True)),
              ('foo bar', dict(whole=True)), ('foo | bar', dict(whole=True)), ('!report data', dict(whole=True)), ('v1', dict(whole=True)),
              ('Ärger', dict(whole=True)), ('a*', dict(whole=True)), ('special\\names', dict(whole=True)), ('names', dict(whole=True, path=True)),
              ('special', dict(path=True)), ('corpus', dict(path=True)), ('报告', dict(path=True)), ('names 报告', dict(path=True)),
              ('项目A', dict(path=True)), ('src', dict(path=True)), ('src', dict(path=True, whole=True)), ('dirs', dict(path=True, whole=True)),
              ('Special', dict(path=True, case=True)), ('special', dict(path=True, case=True)), ('Names\\Img', dict(path=True)),
              ('c:', dict(path=True)), ('*.txt', dict(path=True)), ('*names*txt', dict(path=True)), ('src !main', dict(path=True)),
              ('level_14', dict(path=True)), ('ppp', dict(path=True)), ('Program Files', dict(path=True)), ('"program files"', dict(path=True)),
              ('x64 debug', dict(path=True)), ('bulk 2024 pdf', dict(path=True)), ('SPECIAL', dict(path=True, case=True, whole=True)),
              ('ext:docx 项目', dict(path=True)), ('folder:src', dict(path=True)), ('file:main', dict(path=True))]:
    Q('toggle', t, **kw)

# ---- filters 0-8 ----------------------------------------------------------------------------------
for f in range(0, 9):
    Q('filter', 'report', filt=f)
for f in range(1, 9):
    Q('filter', '', filt=f)
    Q('filter', '2024', filt=f)
Q('filter', 'a', filt=2)
Q('filter', 'IMG', filt=3, case=True)
Q('filter', '报告', filt=2)
Q('filter', 'src', filt=1)
Q('filter', 'src', filt=1, path=True)
Q('filter', 'main', filt=8)
Q('filter', '^.{30,}$', filt=2, regex=True)
Q('filter', 'size:>1mb', filt=5)
Q('filter', 'dm:2024', filt=4)
Q('filter', 'x | y', filt=7)
Q('filter', '!report', filt=6)

# ---- edge -----------------------------------------------------------------------------------------
Q('edge-empty', '', soft=True, note='empty query: Python returns everything; native behaviour unspecified')
Q('edge-empty', '   ', soft=True)
Q('edge-empty', '\t', soft=True)
for t in ['\\', '/', 'c:', 'C:\\', '\\\\', '\\*', '?*', '**', '*?*', 'a**b', '\\\\?\\C:\\corpus', '..', '.', '...', ' foo ',
          '  foo   bar  ', 'FOO', 'Foo Bar', '\u3000foo', 'foo\u3000bar', 'C:\\corpus\\special\\names\\readme', 'c:\\CORPUS\\SPECIAL\\NAMES\\README',
          'special\\\\names', 'special\\names\\\\readme', 'names\\', '\\names', '\\readme']:
    Q('edge', t, soft=(t.startswith('\\\\?\\') or '\u3000' in t))

assert len(QUERIES) >= 120
if __name__ == '__main__':
    from collections import Counter
    print(len(QUERIES), Counter(q['cat'] for q in QUERIES))
