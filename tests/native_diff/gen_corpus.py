#!/usr/bin/env python3
"""Deterministic test corpus for native QianXun differential tests.

usage: gen_corpus.py [--dest DIR] [--retouch]
  default dest: $WINEPREFIX/drive_c/corpus  (Windows view: C:\\corpus)
  --retouch   only re-apply the 'relative' mtimes (today / yesterday / N days ago) -- run before each test day.
~60k files, ~4k dirs. Everything is derived from a fixed seed; only the relative-date files depend on 'today'.
Also writes work/corpus_manifest.json (symlinks, hidden files, relative-date files)."""
import datetime
import json
import os
import random
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'work')
SEED = 20261019


def noon(d):
    return int(time.mktime(datetime.datetime(d.year, d.month, d.day, 12, 0, 0).timetuple()))


def ts(y, mo, d, h=12, mi=0, s=0):
    return int(time.mktime(datetime.datetime(y, mo, d, h, mi, s).timetuple()))


class Gen(object):
    def __init__(self, root):
        self.root = root
        self.rnd = random.Random(SEED)
        self.files = 0
        self.dirs = 0
        self.taken = {}      # dir -> set(lower names)
        self.rel = []        # (relpath, days_ago)
        self.hidden = []
        self.symlinks = []
        self.dirmt = {}      # abs dir -> mtime
        self.today = datetime.date.today()

    def rand_ts(self):
        a, b = ts(2019, 1, 1, 0), ts(2026, 10, 18, 0)
        return self.rnd.randint(a, b)

    def mkdir(self, rel, mt=None):
        p = os.path.join(self.root, rel)
        if not os.path.isdir(p):
            os.makedirs(p)
            self.dirs += 1
        self.dirmt[p] = mt if mt is not None else self.rand_ts()
        return p

    def mkfile(self, rel, size=0, mt=None, days_ago=None, attr=None):
        p = os.path.join(self.root, rel)
        d, n = os.path.split(p)
        if not os.path.isdir(d):
            os.makedirs(d)
        t = self.taken.setdefault(d, set())
        if n.lower() in t:
            return None
        t.add(n.lower())
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        if size:
            os.ftruncate(fd, size)
        os.close(fd)
        self.files += 1
        if days_ago is not None:
            mt = noon(self.today - datetime.timedelta(days=days_ago))
            self.rel.append((rel, days_ago))
        if mt is None:
            mt = self.rand_ts()
        os.utime(p, (mt, mt))
        if attr:
            os.setxattr(p, 'user.DOSATTRIB', ('0x%x' % attr).encode())
            self.hidden.append((rel, attr))
        return p

    # ------------------------------------------------------------------
    def special(self):
        R = self.mkfile
        names = [
            '报告 2024.docx', '报告2024.docx', '年度报告.pdf', 'Report 2024.DOCX', 'report_final.docx', 'REPORT.TXT',
            'readme', 'README.md', 'IMG_0001.JPG', 'img_0002.jpg', 'IMG_0003.jpeg', 'IMG_0004.PNG', 'photo.tar.gz',
            'archive.tar.gz', 'backup.2024.01.zip', 'a.b.c.d.txt', '.gitignore', '.hidden.txt', 'no_extension',
            'UPPER.TXT', 'lower.txt', 'MiXeD.TxT', 'file (1).txt', 'file (2).txt', 'a b  c.txt', '名称-带-连字符.txt',
            '名称_带_下划线.txt', '混合Mix中文English.txt', '日本語ファイル.txt', '한국어.txt', 'Ärger.txt', 'äpfel.txt',
            'ÄPFEL2.txt', 'Straße.txt', 'STRASSE.txt', 'İstanbul.txt', 'ÀÉÎÕÜ.txt', 'naïve café.txt', 'emoji😀.txt',
            '𠀀扩展B区.txt', '全角ＡＢＣ１２３.txt', 'Ⅷ罗马.txt', 'ΑΒΓ.txt', 'ЖУК.txt', 'жук_lower.txt', '[brackets].txt',
            '{braces}.txt', '(parens).txt', 'a+b=c.txt', 'a&b.txt', 'a;b.txt', 'a,b.txt', "a'b.txt", 'a`b.txt',
            'a~b.txt', 'a#b.txt', 'a%20b.txt', 'a@b.txt', 'a!b.txt', 'a^b.txt', '$dollar.txt', '100%.txt', 'star★.txt',
            'x.JPG', 'y.Jpg', 'z.jpg', 'file.txt.bak', 'file.bak.txt', '.txt', '..odd.txt', 'a..b.txt', 'Makefile',
            'foo bar baz.txt', 'foo_bar_baz.txt', 'foobar.txt', 'FooBar.TXT', 'bar foo.txt', 'foo.txt', 'bar.txt',
            'alpha beta.txt', 'alpha.txt', 'beta.txt', 'gamma.log', 'delta.LOG', 'main.cpp', 'main.h', 'util.c',
            'test.py', 'setup.exe', 'run.bat', 'lib.dll', 'movie.mp4', 'song.mp3', 'clip.MKV', 'zip.zip', 'doc.pdf',
            'Dr. Who.txt', 'v1.2.3.txt', '2024-01-15 notes.md', '2024_report_Q3.xlsx', 'budget 2025.xlsx',
            'x' * 250 + '.txt', 'L' * 255, '长' * 80 + '.txt',
        ]
        for n in names:
            R(os.path.join('special', 'names', n), self.rnd.choice([0, 0, 1, 100, 5000, 70000, 2000000]))
        for dn in ['folder.docx', 'dir.with.dots', '新建文件夹', 'New folder', 'My Documents', 'Program Files',
                   'Program Files (x86)', 'node_modules', '.git', 'UPPER_DIR', 'lower_dir', 'MixedDir', 'a b c',
                   'photos', 'Photos 2024', '文档', '项目A', '项目B', 'src', 'docs', 'build', '2024', '2025',
                   'empty_dir_a', 'empty_dir_b', 'Report Archive', 'foo bar dir', 'foobar_dir', 'dir (1)', '含空格 的 目录', 'ß-dir', 'Ünïcode-dir']:
            self.mkdir(os.path.join('special', 'dirs', dn))
        # files inside a few of them (path queries)
        for dn, fn in [('src', 'main.cpp'), ('src', 'main.h'), ('docs', 'report.docx'), ('docs', 'readme.md'),
                       ('项目A', '方案.docx'), ('项目A', '报告.docx'), ('项目B', '方案.docx'), ('Program Files', 'app.exe'),
                       ('Program Files (x86)', 'app86.exe'), ('Photos 2024', 'IMG_9999.JPG'), ('node_modules', 'x.js'),
                       ('folder.docx', 'inside.txt'), ('2024', '2024-report.pdf'), ('新建文件夹', '新建文本文档.txt'),
                       ('New folder', 'New Text Document.txt'), ('src', 'sub.dir.name.txt')]:
            R(os.path.join('special', 'dirs', dn, fn), 123)
        # sizes (sparse via truncate)
        K, M, G = 1024, 1024 ** 2, 1024 ** 3
        for sz in [0, 1, 2, 1023, 1024, 1025, 1536, 10239, 10240, 10241, 102399, 102400, 102401, 1048575, 1048576,
                   1048577, 1572864, 16 * M - 1, 16 * M, 16 * M + 1, 128 * M - 1, 128 * M, 128 * M + 1, 500 * M, G,
                   G + 1, 3 * G, 5 * K, 50 * K, 300 * K, 5 * M, 50 * M, 2000, 3000000]:
            R(os.path.join('special', 'sizes', 'size_%d.bin' % sz), sz)
        self.mkdir(os.path.join('special', 'sizes', 'dir_size_test'))   # dirs never match size:
        # dates
        fixed = [(2019, 1, 1, 0, 0, 0), (2019, 12, 31, 23, 59, 59), (2020, 2, 29, 12, 0, 0), (2021, 6, 15, 12, 0, 0),
                 (2022, 11, 11, 12, 0, 0), (2023, 12, 31, 23, 59, 59), (2024, 1, 1, 0, 0, 0), (2024, 1, 31, 12, 0, 0),
                 (2024, 2, 1, 0, 0, 0), (2024, 12, 31, 23, 59, 59), (2025, 1, 1, 0, 0, 0), (2025, 3, 8, 12, 0, 0),
                 (2025, 10, 19, 12, 0, 0), (2026, 1, 1, 0, 0, 0), (2026, 6, 30, 12, 0, 0), (2026, 2, 28, 12, 0, 0)]
        for y, mo, d, h, mi, s in fixed:
            R(os.path.join('special', 'dates', 'fixed_%04d%02d%02d_%02d%02d%02d.txt' % (y, mo, d, h, mi, s)),
              10, ts(y, mo, d, h, mi, s))
        for dago in [0, 1, 2, 3, 5, 10, 20, 45, 100, 200, 500, 1000]:
            R(os.path.join('special', 'dates', 'rel_%dd_ago.txt' % dago), 10, days_ago=dago)
        t0 = self.today
        R(os.path.join('special', 'dates', 'rel_first_of_month.txt'), 10, noon(t0.replace(day=1)))
        R(os.path.join('special', 'dates', 'rel_jan1.txt'), 10, noon(t0.replace(month=1, day=1)))
        R(os.path.join('special', 'dates', 'rel_prev_month_end.txt'), 10, noon(t0.replace(day=1) - datetime.timedelta(days=1)))
        R(os.path.join('special', 'dates', 'rel_prev_year_end.txt'), 10, ts(t0.year - 1, 12, 31, 23, 59, 30))
        # attributes
        R(os.path.join('special', 'attrs', 'hidden_file.txt'), 5, attr=0x2)
        R(os.path.join('special', 'attrs', 'system_file.sys'), 5, attr=0x4)
        R(os.path.join('special', 'attrs', 'hidden_system.dat'), 5, attr=0x6)
        R(os.path.join('special', 'attrs', 'readonly.txt'), 5, attr=0x1)
        self.mkdir(os.path.join('special', 'attrs', 'hidden_dir'))
        os.setxattr(os.path.join(self.root, 'special', 'attrs', 'hidden_dir'), 'user.DOSATTRIB', b'0x2')
        R(os.path.join('special', 'attrs', 'hidden_dir', 'inside_hidden.txt'), 5)
        R(os.path.join('special', 'attrs', 'empty_file.txt'), 0)
        # deep nesting (> 260 chars)
        p = os.path.join('special', 'deep')
        for i in range(1, 15):
            p = os.path.join(p, 'level_%02d_' % i + 'd' * 14)
            self.mkdir(p)
            R(os.path.join(p, 'deepfile_%02d.txt' % i), i)
        R(os.path.join(p, 'deepfile_unique_bottom.txt'), 77)
        R(os.path.join(p, '深层文件.txt'), 78)
        # boundary-length full paths: C:\corpus\special\bound\<pad>\f.txt  -> total len N
        for N in (258, 259, 260, 261, 262):
            base = 'C:\\corpus\\special\\bound\\'
            f = 'bf.txt'
            padlen = N - len(base) - 1 - len(f)
            self.mkdir(os.path.join('special', 'bound', 'p' * padlen))
            R(os.path.join('special', 'bound', 'p' * padlen, f), N)
        # long file name inside a deep dir (both long)
        R(os.path.join(p, 'x' * 200 + '_deep_long.txt'), 5)
        # symlinks (loop / ancestor / file / broken) -- Windows semantics ambiguous, oracle excludes them
        lp = self.mkdir(os.path.join('special', 'loop'))
        for name, target in [('up', '..'), ('root', self.root), ('self', '.'), ('file_link.txt', '../names/readme'),
                             ('broken_link', 'no/such/target')]:
            lk = os.path.join(lp, name)
            if os.path.lexists(lk):
                os.remove(lk)
            os.symlink(target, lk)
            self.symlinks.append(os.path.join('special', 'loop', name))
        R(os.path.join('special', 'loop', 'real_inside_loop.txt'), 3)
        # unique needles for plain tests
        R(os.path.join('special', 'needles', 'zzqxneedle.txt'), 1)
        R(os.path.join('special', 'needles', 'ZZQXNEEDLE_upper.txt'), 1)
        R(os.path.join('special', 'needles', 'zzqx needle spaced.txt'), 1)
        R(os.path.join('special', 'needles', '独一无二的针.txt'), 1)
        R(os.path.join('special', 'needles', '独一无二的针 副本.txt'), 1)
        self.mkdir(os.path.join('special', 'needles', 'zzqxneedle_dir'))
        R(os.path.join('special', 'needles', 'zzqxneedle_dir', 'child.txt'), 1)

    # ------------------------------------------------------------------
    def bulk(self, nfiles=59500, ndirs=3850):
        rnd = self.rnd
        en = ['report', 'invoice', 'photo', 'IMG', 'DSC', 'notes', 'backup', 'data', 'final', 'draft', 'test', 'config',
              'readme', 'main', 'util', 'index', 'Setup', 'Release', 'Debug', 'log', 'temp', 'cache', 'image', 'video',
              'music', 'document', 'summary', 'project', 'build', 'module', 'plan', 'review', 'Budget', 'Meeting']
        cn = ['报告', '发票', '照片', '方案', '总结', '会议纪要', '需求', '设计', '测试', '手册', '合同', '预算', '计划',
              '说明', '资料', '图纸', '论文', '简历', '笔记', '备份']
        exts = ['txt', 'docx', 'pdf', 'jpg', 'JPG', 'png', 'xlsx', 'pptx', 'mp3', 'mp4', 'zip', 'py', 'cpp', 'h', 'js',
                'md', 'log', 'dat', 'bin', 'exe', 'dll', 'json', 'xml', 'html', 'csv', 'doc', 'rar', '7z', 'tar.gz',
                'mkv', 'flac', 'wav', 'bat', 'sh', 'c', 'go', 'rs', 'sql', 'TXT', 'Docx', '', 'bak', 'tmp', 'ini']
        dvoc = ['src', 'docs', 'build', 'test', 'tests', 'lib', 'bin', 'data', 'images', 'assets', 'old', 'new', 'tmp',
                'release', 'debug', 'x64', 'x86', 'backup', 'archive', 'share', 'common', 'core', 'app', 'web', 'api',
                '项目', '资料', '文档', '图片', '备份', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026',
                'Project', 'Photos', 'Work', 'Misc', 'Users', 'Public']
        dirs = [self.mkdir('bulk')]
        rels = ['bulk']
        # build dir tree
        while self.dirs < ndirs:
            par = rnd.choice(rels)
            if par.count(os.sep) >= 8:
                continue
            nm = rnd.choice(dvoc) + ('' if rnd.random() < 0.4 else rnd.choice(['_', ' ', '-', '.']) + str(rnd.randint(0, 99)))
            rel = os.path.join(par, nm)
            full = os.path.join(self.root, rel)
            t = self.taken.setdefault(os.path.join(self.root, par), set())
            if nm.lower() in t or os.path.exists(full):
                continue
            t.add(nm.lower())
            self.mkdir(rel)
            rels.append(rel)
        start = self.files
        while self.files - start < nfiles:
            par = rnd.choice(rels)
            r = rnd.random()
            if r < 0.30:
                n = '%s_%d' % (rnd.choice(en), rnd.randint(0, 9999))
            elif r < 0.45:
                n = '%s%s' % (rnd.choice(cn), rnd.choice(['', ' ', '_', '-']) + str(rnd.randint(2019, 2026)))
            elif r < 0.55:
                n = 'IMG_%04d' % rnd.randint(0, 9999)
            elif r < 0.65:
                n = '%s %s' % (rnd.choice(en), rnd.choice(cn))
            elif r < 0.75:
                n = '%s.%s' % (rnd.choice(en).lower(), rnd.choice(['v1', 'v2', 'old', 'new', 'final', '2024']))
            elif r < 0.85:
                n = '%s_%s_%d' % (rnd.choice(en), rnd.choice(en).upper(), rnd.randint(0, 999))
            else:
                n = '%s%d' % (rnd.choice(cn + en), rnd.randint(0, 99999))
            e = rnd.choice(exts)
            n = n + ('.' + e if e else '')
            rel = os.path.join(par, n)
            u = rnd.random()
            sz = 0 if u < 0.3 else int(10 ** rnd.uniform(0, 7.3))
            if rnd.random() < 0.002:
                self.mkfile(rel, sz, days_ago=rnd.choice([0, 1, 3, 12, 40, 150, 400]))
            else:
                self.mkfile(rel, sz)

    def finish(self):
        # directory mtimes last (bottom-up, creating files changes them)
        for p in sorted(self.dirmt, key=lambda s: -s.count(os.sep)):
            if os.path.isdir(p):
                os.utime(p, (self.dirmt[p], self.dirmt[p]))
        # intermediate dirs created via makedirs without mkdir(): give them deterministic times too
        for dp, dn, fn in os.walk(self.root):
            if dp not in self.dirmt:
                t = ts(2022, 5, 5, 10, 0, 0) + (hash_str(dp) % 86400)
                self.dirmt[dp] = t
        for p in sorted(self.dirmt, key=lambda s: -s.count(os.sep)):
            if os.path.isdir(p):
                os.utime(p, (self.dirmt[p], self.dirmt[p]))
        # root itself
        os.utime(self.root, (ts(2026, 1, 1, 0), ts(2026, 1, 1, 0)))


def hash_str(s):
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return h


def retouch(root):
    man = json.load(open(os.path.join(WORK, 'corpus_manifest.json')))
    today = datetime.date.today()
    n = 0
    for rel, dago in man['rel']:
        p = os.path.join(root, rel)
        t = noon(today - datetime.timedelta(days=dago))
        if os.path.exists(p):
            os.utime(p, (t, t))
            n += 1
    t0 = today
    for rel, t in [('rel_first_of_month.txt', noon(t0.replace(day=1))), ('rel_jan1.txt', noon(t0.replace(month=1, day=1))),
                   ('rel_prev_month_end.txt', noon(t0.replace(day=1) - datetime.timedelta(days=1))),
                   ('rel_prev_year_end.txt', ts(t0.year - 1, 12, 31, 23, 59, 30))]:
        p = os.path.join(root, 'special', 'dates', rel)
        if os.path.exists(p):
            os.utime(p, (t, t))
    return n


def main():
    dest = None
    args = sys.argv[1:]
    if '--dest' in args:
        dest = args[args.index('--dest') + 1]
    if not dest:
        dest = os.path.join(os.environ.get('WINEPREFIX', os.path.join(HERE, 'prefix64')), 'drive_c', 'corpus')
    if '--retouch' in args:
        print('retouched', retouch(dest))
        return
    if os.path.lexists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    g = Gen(dest)
    g.special()
    g.bulk()
    g.finish()
    os.makedirs(WORK, exist_ok=True)
    json.dump({'rel': g.rel, 'hidden': g.hidden, 'symlinks': g.symlinks, 'seed': SEED},
              open(os.path.join(WORK, 'corpus_manifest.json'), 'w'), ensure_ascii=False, indent=0)
    print('corpus %s: %d files, %d dirs' % (dest, g.files, g.dirs))


if __name__ == '__main__':
    main()
