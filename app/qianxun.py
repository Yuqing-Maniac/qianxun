#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
千寻 QianXun —— 银河麒麟上的 Everything 式文件名秒搜工具

  * 全盘文件名索引常驻内存，输入即出结果
  * inotify 实时监控 + 目录 mtime 轮询，增删改名秒级同步
  * Everything 搜索语法：空格=与  |=或  !=非  * ?=通配  ext: size: dm: regex: path: file: folder:
  * 索引缓存落盘，二次启动秒开
依赖：Python 3.6+、PyQt5（离线包已内嵌）
"""
import os
import sys
import re
import json
import time
import errno
import select
import struct
import pickle
import ctypes
import ctypes.util
import fnmatch
import threading
import queue
import shutil
import subprocess
import heapq
import csv
import datetime
import traceback
from array import array
from collections import deque

APP_NAME = '千寻'
APP_ID = 'qianxun'
VERSION = '1.1.0'

# 平台：同一份源码同时支持 Linux（银河麒麟等）与 Windows 10/11
IS_WIN = os.name == 'nt'
SEP = '\\' if IS_WIN else '/'

HOME = os.path.expanduser('~')


def win_data_dir(env=None, script=None, exists=os.path.exists):
    """Windows 数据目录：程序目录（启动器所在目录）下有 portable.txt 时用其 data\\（真正便携），
    否则 %LOCALAPPDATA%\\QianXun\\。纯函数（参数可注入），便于在 Linux 上测试。"""
    import ntpath
    env = os.environ if env is None else env
    script = os.path.abspath(__file__) if script is None else script
    cands = []
    la = env.get('QIANXUN_LAUNCHER')
    if la:
        cands.append(ntpath.dirname(la))
    app_dir = ntpath.dirname(script)
    cands.append(ntpath.dirname(app_dir))   # QianXun\app\qianxun.py → QianXun\
    cands.append(app_dir)
    for d in cands:
        if d and exists(ntpath.join(d, 'portable.txt')):
            return ntpath.join(d, 'data')
    base = env.get('LOCALAPPDATA') or ntpath.join(env.get('USERPROFILE') or HOME, 'AppData', 'Local')
    return ntpath.join(base, 'QianXun')


if IS_WIN:
    CONF_DIR = CACHE_DIR = win_data_dir()
else:
    CONF_DIR = os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.join(HOME, '.config'), APP_ID)
    CACHE_DIR = os.path.join(os.environ.get('XDG_CACHE_HOME') or os.path.join(HOME, '.cache'), APP_ID)
CONF_FILE = os.path.join(CONF_DIR, 'config.json')
INDEX_FILE = os.path.join(CACHE_DIR, 'index.db')
LOG_FILE = os.path.join(CACHE_DIR, 'qianxun.log')
LOG_HINT = LOG_FILE if IS_WIN else '~/.cache/qianxun/qianxun.log'
INDEX_FORMAT = 3

DEFAULT_CONFIG = {
    'roots': ['/'],
    'excludes': ['/proc', '/sys', '/dev', '/run', '/snap', '/var/lib/docker', '/var/lib/containerd'],
    'index_network': False,
    'index_removable': True,
    'close_to_tray': True,
    'case': False,
    'whole_word': False,
    'match_path': False,
    'regex': False,
    'filter': 0,
    'sort_col': 0,
    'sort_desc': False,
    'geometry': '',
    'header': '',
}
if IS_WIN:
    # roots 为空＝自动：所有本地固定盘（＋可移动盘／网络盘，按开关）；内置排除见 win_excludes()
    DEFAULT_CONFIG.update(roots=[], excludes=[], hotkey='Ctrl+Alt+F')

LOCAL_FS = {
    'ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'f2fs', 'jfs', 'reiserfs', 'zfs', 'nilfs2', 'bcachefs',
    'vfat', 'msdos', 'exfat', 'ntfs', 'ntfs3', 'fuseblk', 'hfsplus', 'udf', 'iso9660',
    'fuse.mergerfs', 'fuse.ntfs-3g', 'fuse.exfat',
}
NET_FS = {'nfs', 'nfs4', 'cifs', 'smb3', 'smbfs', 'fuse.sshfs', 'fuse.davfs', 'davfs', 'fuse.rclone'}
REMOVABLE_PREFIX = ('/media/', '/run/media/')


def log(msg):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8', errors='backslashreplace') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')
    except OSError:
        pass


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONF_FILE, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            # 只接受类型与默认值一致的项，手改坏的配置（如 "filter": "x"、"roots": "/"）不至于让程序起不来
            for k, v in data.items():
                d = DEFAULT_CONFIG.get(k)
                if k not in DEFAULT_CONFIG or type(v) is not type(d):
                    continue
                if isinstance(d, list) and not all(isinstance(x, str) for x in v):
                    continue
                cfg[k] = v
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        tmp = CONF_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CONF_FILE)
    except OSError as e:
        log('save_config: %s' % e)


def win_norm_path(p, abspath=None):
    """Windows 路径规范化（用 ntpath，Linux 上也可测试）：'/'→'\\'，'c:'→'C:\\'，盘符大写。"""
    import ntpath
    p = p.strip().replace('/', '\\')
    if p.startswith('~'):
        p = os.path.expanduser(p) if IS_WIN else p
    if re.match(r'^[A-Za-z]:$', p):
        p += '\\'
    p = ntpath.normpath(p)
    if not ntpath.isabs(p) or re.match(r'^[A-Za-z]:[^\\]', p):
        p = (abspath or os.path.abspath)(p)
    if re.match(r'^[a-z]:', p):
        p = p[0].upper() + p[1:]
    return p


def norm_path(p):
    if IS_WIN:
        return win_norm_path(p)
    p = os.path.normpath(os.path.expanduser(p.strip()))
    return p if p.startswith('/') else os.path.abspath(p)


def join_path(d, name):
    # Linux：'/' + name 或 d + '/' + name；Windows：'C:\\' + name 或 d + '\\' + name
    return d + name if d[-1:] == SEP else d + SEP + name


def join_path_sep(d, name, sep):
    """join_path 的显式分隔符版本（测试用）。"""
    return d + name if d[-1:] == sep else d + sep + name


def split_path_sep(p, sep):
    """(父目录, 名称)；根（'/'、'C:\\'）的父目录为 None。"""
    k = p.rfind(sep)
    if k < 0:
        return None, p
    head, name = p[:k], p[k + 1:]
    if not name:
        return None, p
    if sep == '/' and head == '':
        head = '/'
    elif sep == '\\' and re.match(r'^[A-Za-z]:$', head):
        head += '\\'
    elif sep == '\\' and head.startswith('\\\\') and head.count('\\') == 3:
        head += '\\'   # \\server\share\x → \\server\share\
    return head, name


def long_path(p, force_win=False):
    """Windows 超过 MAX_PATH 的路径加 \\\\?\\ 前缀（未开启系统长路径支持时也能列目录）。"""
    if (IS_WIN or force_win) and len(p) >= 240 and not p.startswith('\\\\?\\'):
        if p.startswith('\\\\'):
            return '\\\\?\\UNC\\' + p[2:]
        return '\\\\?\\' + p
    return p


def dkey(p):
    """dir_ids 的键：Windows 文件系统不区分大小写，用小写；Linux 原样。"""
    return p.lower() if IS_WIN else p


def disp(s):
    """把含非 UTF-8 字节（surrogateescape）的文件名转成可显示文本。"""
    try:
        s.encode('utf-8')
        return s
    except UnicodeEncodeError:
        try:
            return s.encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')
        except UnicodeEncodeError:
            # Windows（NTFS）文件名可含孤立的 UTF-16 代理项，不在 surrogateescape 范围内
            return s.encode('utf-8', 'replace').decode('utf-8')


def fmt_time(m, f):
    """mtime 转文本；损坏/极端时间戳（年份越界）返回空串而不是抛异常。"""
    if not m or m <= 0:
        return ''
    try:
        return time.strftime(f, time.localtime(m))
    except (ValueError, OverflowError, OSError):
        return ''


def read_mounts():
    res = []
    try:
        with open('/proc/self/mounts', encoding='utf-8', errors='surrogateescape') as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mnt = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), parts[1])
                res.append((mnt, parts[2]))
    except OSError:
        pass
    return res


# ---- Windows：盘符与内置排除 ----
DRIVE_REMOVABLE, DRIVE_FIXED, DRIVE_REMOTE, DRIVE_CDROM, DRIVE_RAMDISK = 2, 3, 4, 5, 6


def win_drive_mask():
    """GetLogicalDrives 位图（bit0=A:）；非 Windows 返回 0。"""
    if not IS_WIN:
        return 0
    try:
        return int(ctypes.windll.kernel32.GetLogicalDrives())
    except Exception:
        return 0


def win_drive_list(mask=None):
    """[(根 'C:\\', 类型)]，按盘符排序。"""
    if not IS_WIN:
        return []
    if mask is None:
        mask = win_drive_mask()
    out = []
    try:
        gdt = ctypes.windll.kernel32.GetDriveTypeW
        gdt.argtypes = [ctypes.c_wchar_p]
        gdt.restype = ctypes.c_uint
    except Exception:
        return out
    for i in range(26):
        if mask & (1 << i):
            r = chr(65 + i) + ':\\'
            try:
                out.append((r, int(gdt(r))))
            except Exception:
                pass
    return out


def win_select_roots(cfg, drives):
    """由配置与盘符列表求根：[(根, 是否动态)]。动态＝可移动盘／网络盘，可随时插拔，不计入缓存头部。
    cfg['roots'] 为空时自动取所有本地固定盘（含内存盘）；index_removable / index_network 时加入相应盘符。"""
    out, seen = [], set()

    def add(r, dyn):
        k = r.lower()
        if k not in seen:
            seen.add(k)
            out.append((r, dyn))
    types = dict((r.lower(), t) for r, t in drives)
    for r in cfg.get('roots') or []:
        if r.strip():
            r = win_norm_path(r, abspath=lambda x: x)
            t = types.get(r.lower()[:3])
            add(r, t in (DRIVE_REMOVABLE, DRIVE_REMOTE))
    if not cfg.get('roots'):
        for r, t in drives:
            if t in (DRIVE_FIXED, DRIVE_RAMDISK):
                add(r, False)
    for r, t in drives:
        if t == DRIVE_REMOVABLE and cfg.get('index_removable'):
            add(r, True)
        elif t == DRIVE_REMOTE and cfg.get('index_network'):
            add(r, True)
    return out


def win_excludes(cfg, roots, sysroot=None):
    """Windows 排除集合（dkey 小写）：用户排除 + 各根所在盘的 $Recycle.Bin、System Volume Information，
    以及系统目录的 WinSxS。"""
    ex = set()
    for p in cfg.get('excludes') or []:
        if p.strip():
            ex.add(win_norm_path(p, abspath=lambda x: x).lower())
    sysroot = sysroot if sysroot is not None else os.environ.get('SystemRoot', 'C:\\Windows')
    if sysroot:
        ex.add((sysroot.rstrip('\\') + '\\WinSxS').lower())
    drives = set()
    for r in roots:
        if re.match(r'^[A-Za-z]:', r):
            drives.add(r[:2].upper())
    for d in sorted(drives):
        ex.add((d + '\\$Recycle.Bin').lower())
        ex.add((d + '\\System Volume Information').lower())
    for r in roots:
        ex.discard(r.lower())
    return ex


def effective_roots(cfg):
    if IS_WIN:
        return [r for r, _dyn in win_select_roots(cfg, win_drive_list()) if os.path.isdir(r)]
    roots = []
    for r in cfg['roots']:
        r = norm_path(r)
        if r not in roots and os.path.isdir(r):
            roots.append(r)
    if cfg.get('index_removable'):
        # /run/media 默认被 /run 排除，单独作为根加入
        for mnt, fs in read_mounts():
            if mnt.startswith('/run/media/') and fs in LOCAL_FS and mnt not in roots:
                if not any(mnt == r or mnt.startswith(r.rstrip('/') + '/') for r in roots if r != '/'):
                    roots.append(mnt)
    return roots


def compute_excludes(cfg, roots):
    if IS_WIN:
        return win_excludes(cfg, roots)
    ex = set(norm_path(p) for p in cfg['excludes'] if p.strip())
    for mnt, fs in read_mounts():
        if mnt in roots:
            continue
        if fs in LOCAL_FS:
            if not cfg.get('index_removable') and mnt.startswith(REMOVABLE_PREFIX):
                ex.add(mnt)
            continue
        if fs in NET_FS and cfg.get('index_network'):
            continue
        ex.add(mnt)
    for r in roots:
        ex.discard(r)
    return ex


# ----------------------------------------------------------------------------
#  索引
# ----------------------------------------------------------------------------
KIND_FILE, KIND_DIR, KIND_DEAD = 0, 1, 2


class Index(object):
    """
    条目（文件/目录）以平行数组保存：names / lnames / parent / kind / size / mtime
    目录另有 dir id：dirs（完整路径）/ dir_entry（该目录自身的条目号，根为 -1）/ dir_mtime / dir_children
    写入只由引擎线程进行（持锁），界面线程读取时持锁。
    """

    win_stats = IS_WIN   # 扫描时直接取 DirEntry.stat() 的大小/时间（Windows 上免费），并识别重解析点

    def __init__(self):
        self.lock = threading.RLock()
        self.gen = 0          # clear()/load() 换掉整套数组时递增；界面据此丢弃旧的条目号
        self.version = 0
        self.struct_version = 0   # 仅增删条目时递增；大小/时间刷新只改 version
        self.dirs_version = 0
        self.clear()

    def clear(self):
        with self.lock:
            self.gen += 1
            self.dirs = []
            self.dir_ids = {}
            self.dir_entry = array('i')
            self.dir_mtime = array('d')
            self.dir_children = []
            self.names = []
            self.lnames = []
            self.parent = array('i')
            self.kind = bytearray()
            self.size = array('q')
            self.mtime = array('d')
            self.entry_dir = {}
            self.live = 0
            self.name_order = None      # (排好序的条目列表, 覆盖到的条目数)
            self._dp_cache = {}
            self.version += 1
            self.struct_version += 1
            self.dirs_version += 1

    # ---- 基本操作（调用方持锁） ----
    def _new_dir(self, path, entry):
        if self.dir_children is None:
            self.ensure_children()
        did = len(self.dirs)
        self.dirs.append(path)
        self.dir_ids[dkey(path)] = did
        self.dir_entry.append(entry)
        self.dir_mtime.append(0.0)
        self.dir_children.append([])
        if entry >= 0:
            self.entry_dir[entry] = did
        self.dirs_version += 1
        return did

    def _add_entry(self, did, name, isdir, size=-1, mtime=-1.0):
        if self.lnames is None:
            self.ensure_lnames()
        i = len(self.names)
        self.names.append(name)
        ln = name.lower()
        self.lnames.append(name if ln == name else ln)
        self.parent.append(did)
        self.kind.append(KIND_DIR if isdir else KIND_FILE)
        self.size.append(size)
        self.mtime.append(mtime)
        self.dir_children[did].append(i)
        self.live += 1
        self.struct_version += 1
        return i

    def _remove_entry(self, i, removed_dirs):
        if self.lnames is None:
            self.ensure_lnames()
        stack = [i]
        while stack:
            e = stack.pop()
            if self.kind[e] == KIND_DEAD:
                continue
            if self.kind[e] == KIND_DIR:
                did = self.entry_dir.pop(e, None)
                if did is not None:
                    for c in self.dir_children[did]:
                        if self.kind[c] != KIND_DEAD:
                            stack.append(c)
                    self.dir_children[did] = []
                    p = self.dirs[did]
                    if p is not None:
                        self.dir_ids.pop(dkey(p), None)
                    self.dirs[did] = None
                    self.dirs_version += 1
                    removed_dirs.append(did)
            self.kind[e] = KIND_DEAD
            self.names[e] = ''
            self.lnames[e] = ''
            self.live -= 1
            self.struct_version += 1

    def fullpath(self, i):
        d = self.dirs[self.parent[i]]
        if d is None:
            return None
        return join_path(d, self.names[i])

    def dirpath(self, i):
        return self.dirs[self.parent[i]]

    def dir_prefixes(self, lower):
        """每个 dir id 对应 '目录路径/'（Windows 为 '目录路径\\'），用于路径匹配；按目录版本缓存。"""
        key = (lower, self.dirs_version)
        c = self._dp_cache.get(key)
        if c is None:
            sep = SEP
            if lower:
                c = [('' if d is None else (d.lower() if d[-1:] == sep else d.lower() + sep)) for d in self.dirs]
            else:
                c = [('' if d is None else (d if d[-1:] == sep else d + sep)) for d in self.dirs]
            self._dp_cache = {key: c}
        return c

    # ---- 扫描 ----
    @staticmethod
    def _list_dir(path):
        st = os.stat(path)
        items = []
        with os.scandir(path) as it:
            for e in it:
                try:
                    isd = e.is_dir(follow_symlinks=False)
                except OSError:
                    isd = False
                items.append((e.name, isd))
        return st.st_mtime, items

    @staticmethod
    def _list_dir_stats(path, mt=None):
        """Windows 版列目录：DirEntry.stat(follow_symlinks=False) 由 FindNextFile 数据直接给出，不另行 stat。
        返回 (目录 mtime, [(名称, 是否目录)], [(大小, mtime, 不递归)])。
        不递归＝名称代理类重解析点（联接点、符号链接、挂载点）：只收录为条目，不进入，避免
        “Application Data”之类的循环联接；云文件占位（OneDrive）等非名称代理的照常进入。"""
        lp = long_path(path)
        if mt is None or mt <= 0:
            mt = os.stat(lp).st_mtime
        items, info = [], []
        with os.scandir(lp) as it:
            for e in it:
                try:
                    isd = e.is_dir(follow_symlinks=False)
                except OSError:
                    isd = False
                try:
                    st = e.stat(follow_symlinks=False)
                    attrs = getattr(st, 'st_file_attributes', 0)
                    ns = False
                    if attrs & 0x400:      # FILE_ATTRIBUTE_REPARSE_POINT
                        tag = getattr(st, 'st_reparse_tag', 0)
                        ns = (not tag) or bool(tag & 0x20000000) or e.is_symlink()
                    elif e.is_symlink():
                        ns = True
                    info.append((-1 if isd else st.st_size, st.st_mtime, ns))
                except OSError:
                    info.append((-1 if isd else 0, 0.0, e.is_symlink()))
                items.append((e.name, isd))
        return mt, items, info

    def scan_tree(self, start_dirs, excluded, abort=None, progress=None):
        """广度优先扫描，返回新建的 dir id 列表。"""
        q = deque(start_dirs)
        new_dirs = []
        count = 0
        while q:
            if abort is not None and abort.is_set():
                break
            did = q.popleft()
            path = self.dirs[did]
            if path is None:
                continue
            if self.win_stats:
                self._scan_one_stats(did, path, excluded, q, new_dirs)
                count += 1
                if progress is not None and count % 500 == 0:
                    progress()
                continue
            try:
                mt, items = self._list_dir(path)
            except OSError:
                continue
            with self.lock:
                if self.dirs[did] is None:
                    continue
                self.dir_mtime[did] = mt
                for name, isd in items:
                    i = self._add_entry(did, name, isd)
                    if isd:
                        full = join_path(path, name)
                        if full in excluded or full in self.dir_ids:
                            continue
                        nd = self._new_dir(full, i)
                        q.append(nd)
                        new_dirs.append(nd)
                self.version += 1
            count += 1
            if progress is not None and count % 500 == 0:
                progress()
        return new_dirs

    def _scan_one_stats(self, did, path, excluded, q, new_dirs):
        """scan_tree 的 Windows 分支：一次列目录同时得到大小/时间；子目录的 mtime 取自父目录列表。"""
        try:
            mt, items, info = self._list_dir_stats(path, self.dir_mtime[did])
        except OSError:
            return
        with self.lock:
            if self.dirs[did] is None:
                return
            self.dir_mtime[did] = mt
            for k, (name, isd) in enumerate(items):
                s, m, ns = info[k]
                i = self._add_entry(did, name, isd, s, m)
                if isd and not ns:
                    full = join_path(path, name)
                    kf = dkey(full)
                    if kf in excluded or kf in self.dir_ids:
                        continue
                    nd = self._new_dir(full, i)
                    self.dir_mtime[nd] = m if m > 0 else 0.0
                    q.append(nd)
                    new_dirs.append(nd)
            self.version += 1

    def remove_root(self, did):
        """整棵删除一个根（盘符拔出、根被删除）；返回被删除的 dir id 列表（含根自身）。"""
        self.ensure_children()
        removed = []
        with self.lock:
            p = self.dirs[did]
            if p is None:
                return removed
            for c in self.dir_children[did]:
                self._remove_entry(c, removed)
            self.dir_children[did] = []
            self.dir_ids.pop(dkey(p), None)
            self.dirs[did] = None
            removed.append(did)
            self.dirs_version += 1
            self.version += 1
            self.struct_version += 1
        return removed

    def refresh_dir(self, did, excluded, force=()):
        """重新列一个目录，与索引比对增删；返回 (新增目录, 删除目录)。
        force：须整体重建的子项名（被移入/移出或换了挂载的目录，同名不代表内容相同）。"""
        self.ensure_children()
        path = self.dirs[did]
        if path is None:
            return [], []
        removed = []
        info = None
        try:
            if self.win_stats:
                mt, items, info = self._list_dir_stats(path)
            else:
                mt, items = self._list_dir(path)
        except (FileNotFoundError, NotADirectoryError):
            with self.lock:
                e = self.dir_entry[did]
                if e >= 0:
                    self._remove_entry(e, removed)
                else:
                    for c in self.dir_children[did]:
                        self._remove_entry(c, removed)
                    self.dir_children[did] = []
                self.version += 1
            return [], removed
        except OSError:
            return [], []
        added = []
        with self.lock:
            if self.dirs[did] is None:
                return [], []
            cur = {}
            for c in self.dir_children[did]:
                if self.kind[c] != KIND_DEAD:
                    cur[self.names[c]] = c
            disk = dict(items)
            for name, c in cur.items():
                isd = disk.get(name)
                if isd is None or isd != (self.kind[c] == KIND_DIR) or (isd and name in force):
                    self._remove_entry(c, removed)
            if info is not None:
                self._refresh_stats(did, path, items, info, cur, excluded, added)
            else:
                for name, isd in items:
                    c = cur.get(name)
                    if c is not None and self.kind[c] != KIND_DEAD:
                        continue
                    i = self._add_entry(did, name, isd)
                    if isd:
                        full = join_path(path, name)
                        if full not in excluded and full not in self.dir_ids:
                            added.append(self._new_dir(full, i))
            k = self.kind
            self.dir_children[did] = [c for c in self.dir_children[did] if k[c] != KIND_DEAD]
            self.dir_mtime[did] = mt
            self.version += 1
        if added:
            added += self.scan_tree(added, excluded)
        return added, removed

    def _refresh_stats(self, did, path, items, info, cur, excluded, added):
        """refresh_dir 的 Windows 分支（调用方持锁）：新增条目带大小/时间；已有条目顺带刷新大小/时间。"""
        sz, mt, kind = self.size, self.mtime, self.kind
        for k, (name, isd) in enumerate(items):
            s, m, ns = info[k]
            c = cur.get(name)
            if c is not None and kind[c] != KIND_DEAD:
                sz[c] = s
                mt[c] = m
                continue
            i = self._add_entry(did, name, isd, s, m)
            if isd and not ns:
                full = join_path(path, name)
                kf = dkey(full)
                if kf not in excluded and kf not in self.dir_ids:
                    nd = self._new_dir(full, i)
                    self.dir_mtime[nd] = m if m > 0 else 0.0
                    added.append(nd)

    # ---- 持久化 ----
    def save(self, fn, header):
        n = len(self.names)
        nd = len(self.dirs)
        kind = self.kind
        live = [i for i in range(n) if kind[i] != KIND_DEAD]
        emap = array('i', [-1]) * n
        for new, i in enumerate(live):
            emap[i] = new
        dlive = [d for d in range(nd) if self.dirs[d] is not None]
        dmap = array('i', [-1]) * nd
        for new, d in enumerate(dlive):
            dmap[d] = new
        names = self.names
        par = self.parent
        out_names = [names[i] for i in live]
        out_parent = array('i', [dmap[par[i]] for i in live])
        out_kind = bytes(bytearray([kind[i] for i in live]))
        sz, mt = self.size, self.mtime
        out_size = array('q', [sz[i] for i in live])
        out_mtime = array('d', [mt[i] for i in live])
        de = self.dir_entry
        out_dirs = [self.dirs[d] for d in dlive]
        out_dentry = array('i', [(emap[de[d]] if de[d] >= 0 else -1) for d in dlive])
        out_dmtime = array('d', [self.dir_mtime[d] for d in dlive])
        h = dict(header)
        h.update({'fmt': INDEX_FORMAT, 'n': len(live), 'nd': len(dlive), 'time': time.time()})
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        tmp = fn + '.tmp'
        with open(tmp, 'wb') as f:
            P = pickle.HIGHEST_PROTOCOL if pickle.HIGHEST_PROTOCOL < 5 else 4
            pickle.dump(h, f, P)
            pickle.dump(out_dirs, f, P)
            for a in (out_dentry, out_dmtime):
                pickle.dump(a.tobytes(), f, P)
            CH = 200000
            for s in range(0, len(out_names), CH):
                pickle.dump(out_names[s:s + CH], f, P)
                time.sleep(0)
            for a in (out_parent, out_size, out_mtime):
                pickle.dump(a.tobytes(), f, P)
            pickle.dump(out_kind, f, P)
        os.replace(tmp, fn)

    def load(self, fn, header):
        with open(fn, 'rb') as f:
            h = pickle.load(f)
            if not isinstance(h, dict) or h.get('fmt') != INDEX_FORMAT:
                return False
            for k, v in header.items():
                if h.get(k) != v:
                    return False
            n, nd = h['n'], h['nd']
            dirs = pickle.load(f)
            dentry = array('i'); dentry.frombytes(pickle.load(f))
            dmtime = array('d'); dmtime.frombytes(pickle.load(f))
            names = []
            while len(names) < n:
                names.extend(pickle.load(f))
            parent = array('i'); parent.frombytes(pickle.load(f))
            size = array('q'); size.frombytes(pickle.load(f))
            mtime = array('d'); mtime.frombytes(pickle.load(f))
            kind = bytearray(pickle.load(f))
        if not (len(dirs) == nd == len(dentry) == len(dmtime) and
                len(names) == n == len(parent) == len(kind) == len(size) == len(mtime)):
            return False
        with self.lock:
            self.gen += 1
            self.dirs = dirs
            self.dir_ids = {dkey(p): d for d, p in enumerate(dirs)}
            self.dir_entry = dentry
            self.dir_mtime = dmtime
            self.dir_children = None
            self.names = names
            self.lnames = None
            self.parent = parent
            self.kind = kind
            self.size = size
            self.mtime = mtime
            self.entry_dir = {e: d for d, e in enumerate(dentry) if e >= 0}
            self.live = n
            self.name_order = None
            self._dp_cache = {}
            self.version += 1
            self.struct_version += 1
            self.dirs_version += 1
        return True

    def ensure_children(self):
        if self.dir_children is not None:
            return
        with self.lock:
            if self.dir_children is not None:
                return
            nd = len(self.dirs)
            parent = self.parent
            children = [[] for _ in range(nd)]
            for i, p in enumerate(parent):
                children[p].append(i)
            self.dir_children = children

    def ensure_lnames(self):
        if self.lnames is not None:
            return
        with self.lock:
            if self.lnames is not None:
                return
            names = self.names
            self.lnames = [ln if ln != s else s for s, ln in zip(names, map(str.lower, names))]


# ----------------------------------------------------------------------------
#  inotify（ctypes 直调 libc，无第三方依赖）
# ----------------------------------------------------------------------------
IN_MODIFY = 0x2
IN_ATTRIB = 0x4
IN_CLOSE_WRITE = 0x8
IN_MOVED_FROM = 0x40
IN_MOVED_TO = 0x80
IN_CREATE = 0x100
IN_DELETE = 0x200
IN_DELETE_SELF = 0x400
IN_MOVE_SELF = 0x800
IN_Q_OVERFLOW = 0x4000
IN_IGNORED = 0x8000
IN_ISDIR = 0x40000000
IN_ONLYDIR = 0x01000000
IN_DONT_FOLLOW = 0x02000000
IN_EXCL_UNLINK = 0x04000000
STRUCT_EVENTS = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO | IN_DELETE_SELF | IN_MOVE_SELF
CONTENT_EVENTS = IN_CLOSE_WRITE | IN_ATTRIB
WATCH_MASK = STRUCT_EVENTS | CONTENT_EVENTS | IN_ONLYDIR | IN_DONT_FOLLOW | IN_EXCL_UNLINK


def inotify_limit():
    try:
        with open('/proc/sys/fs/inotify/max_user_watches') as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 8192


class Inotify(object):
    def __init__(self):
        libc = ctypes.CDLL(ctypes.util.find_library('c') or 'libc.so.6', use_errno=True)
        self._add = libc.inotify_add_watch
        self._add.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self._add.restype = ctypes.c_int
        self._rm = libc.inotify_rm_watch
        self._rm.argtypes = [ctypes.c_int, ctypes.c_int]
        self._rm.restype = ctypes.c_int
        init1 = libc.inotify_init1
        init1.argtypes = [ctypes.c_int]
        init1.restype = ctypes.c_int
        self.fd = init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            e = ctypes.get_errno()
            raise OSError(e, os.strerror(e))

    def add(self, path, mask=WATCH_MASK):
        wd = self._add(self.fd, os.fsencode(path), mask)
        if wd < 0:
            return -ctypes.get_errno()
        return wd

    def rm(self, wd):
        self._rm(self.fd, wd)

    def read(self, timeout):
        try:
            r, _, _ = select.select([self.fd], [], [], timeout)
        except (OSError, ValueError):
            return []
        if not r:
            return []
        events = []
        for _ in range(8):
            try:
                data = os.read(self.fd, 1 << 18)
            except BlockingIOError:
                break
            except OSError:
                break
            pos, L = 0, len(data)
            while pos + 16 <= L:
                wd, mask, cookie, ln = struct.unpack_from('iIII', data, pos)
                name = data[pos + 16:pos + 16 + ln].split(b'\0', 1)[0]
                pos += 16 + ln
                events.append((wd, mask, os.fsdecode(name)))
            if L < (1 << 17):
                break
        return events

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


# ----------------------------------------------------------------------------
#  引擎线程：建索引、加载缓存、实时监控、轮询、属性补全、落盘
# ----------------------------------------------------------------------------
class Engine(threading.Thread):
    POLL_INTERVAL = 180        # 未被 inotify 覆盖的目录，轮询周期（秒）
    SWEEP_INTERVAL = 1800      # 全量刷新大小/时间
    SAVE_INTERVAL = 1800
    ORDER_DELAY = 20

    def __init__(self, index, cfg):
        threading.Thread.__init__(self, name='qianxun-engine')
        self.daemon = True
        self.index = index
        self.cfg = dict(cfg)
        self.cmds = queue.Queue()
        self.abort = threading.Event()
        self.stopping = False
        self.status = {'state': 'starting', 'watched': 0, 'dirs': 0, 'limit': inotify_limit(),
                       'msg': '正在启动…', 'inotify': True}
        self.ino = None
        self.dir_wd = {}
        self.wd_dir = {}
        self.watch_full = False
        self.roots = []
        self.excluded = set()
        self.saved_version = -1
        self.order_version = -1
        self.sweep_iter = None
        self.sweep_scope = None
        self.skip_sweep = False
        self.moved = {}        # dir id -> 被移入/移出的子目录名（须强制重建）
        self.mounts = None

    # ---- 对外 ----
    def post(self, *cmd):
        if cmd and cmd[0] in ('rebuild', 'quit'):
            self.abort.set()
        self.cmds.put(cmd)

    def _header(self):
        # 只记录“顶层”排除项：已被其它排除目录覆盖的挂载点（docker overlay、/run/user/... 等）
        # 随开关机/容器变化，不应让缓存失效、触发整盘重扫
        top = []
        for e in sorted(self.excluded):
            if not any(e.startswith(t.rstrip('/') + '/') for t in top):
                top.append(e)
        return {'roots': list(self.roots), 'excludes': top}

    # ---- 主循环 ----
    def run(self):
        try:
            self._run()
        except Exception:
            log('engine crashed:\n' + traceback.format_exc())
            self.status.update(state='error', msg='索引线程异常，详见 ' + LOG_HINT)

    def _setup_paths(self):
        self.roots = effective_roots(self.cfg)
        self.excluded = compute_excludes(self.cfg, self.roots)

    def _compute_excludes(self):
        return compute_excludes(self.cfg, self.roots)

    def _after_load(self):
        """缓存加载成功后的钩子（Windows：按当前盘符增删根）。"""
        pass

    def _use_cached_stats(self):
        self.skip_sweep = True

    def _cached_startup(self):
        # 名字已经在缓存里。先让界面可搜，再挂监控、比对目录时间和排序。
        self._use_cached_stats()
        self._set_ready()
        time.sleep(0)
        self._init_watches()
        self._catch_up(False)
        self._compute_order()

    def _run(self):
        self._setup_paths()
        self.mounts = set(read_mounts())
        loaded = False
        self.status.update(state='loading', msg='正在加载索引缓存…')
        if os.path.exists(INDEX_FILE):
            try:
                loaded = self.index.load(INDEX_FILE, self._header())
            except Exception:
                log('load cache failed:\n' + traceback.format_exc())
                loaded = False
        if loaded:
            self._after_load()
            self.saved_version = self.index.version
            self._cached_startup()
        else:
            self._full_scan()
        self._start_sweep(None)
        self._set_ready()
        self._loop()

    def _check_mounts(self):
        """挂载表变化（插拔 U 盘、mount 到已索引目录）时，重建受影响的挂载点目录。"""
        cur = set(read_mounts())
        old, self.mounts = self.mounts, cur
        if old is None or old == cur:
            return False
        idx = self.index
        changed = False
        # 运行中新插入的 /run/media 可移动盘：作为新根加入（/run 默认被排除，不会经父目录发现）
        new_roots = [r for r in effective_roots(self.cfg) if r not in self.roots and r not in idx.dir_ids] \
            if self.cfg.get('index_removable') else []
        self.roots.extend(new_roots)
        self.excluded = self._compute_excludes()
        for r in new_roots:
            with idx.lock:
                d = idx._new_dir(r, -1)
            added = idx.scan_tree([d], self.excluded)
            self._watch([d] + added)
            changed = True
        for mnt in sorted(set(m for m, _ in (old ^ cur)), key=len):
            if mnt in new_roots:
                continue
            d = idx.dir_ids.get(mnt)
            if d is None:
                pd = idx.dir_ids.get(os.path.dirname(mnt))
                if pd is not None:
                    self._refresh(pd)
                    changed = True
                continue
            e = idx.dir_entry[d]
            if e >= 0:
                pd = idx.parent[e]
                self.moved.setdefault(pd, set()).add(idx.names[e])
                self._refresh(pd)
            else:
                # 索引根本身换了挂载：清掉子项后重扫，并重新挂监控
                self._unwatch([d])
                idx.ensure_children()
                with idx.lock:
                    removed = []
                    for c in idx.dir_children[d]:
                        idx._remove_entry(c, removed)
                    idx.dir_children[d] = []
                    idx.dir_mtime[d] = -1.0
                    idx.version += 1
                self._unwatch(removed)
                self._refresh(d)
                self._watch([d])
            changed = True
        return changed

    def _set_ready(self):
        idx = self.index
        nd = sum(1 for d in idx.dirs if d is not None)
        self.status.update(state='ready', dirs=nd, watched=len(self.dir_wd), msg='')

    def _full_scan(self):
        idx = self.index
        self.abort.clear()
        self._close_watches()
        idx.clear()
        self.status.update(state='indexing', msg='正在建立索引…')
        with idx.lock:
            starts = [idx._new_dir(r, -1) for r in self.roots]

        def prog():
            self.status['msg'] = '正在建立索引：已收录 {:,} 个文件和目录…'.format(idx.live)
        idx.scan_tree(starts, self.excluded, self.abort, prog)
        if self.abort.is_set():
            return
        self.status['msg'] = '正在排序…'
        self._compute_order()
        self._init_watches()
        self._catch_up(False)
        self._save()

    # ---- inotify ----
    def _close_watches(self):
        if self.ino is not None:
            self.ino.close()
        self.ino = None
        self.dir_wd = {}
        self.wd_dir = {}
        self.watch_full = False
        self.moved = {}

    def _init_watches(self):
        self._close_watches()
        try:
            self.ino = Inotify()
        except Exception as e:
            log('inotify unavailable: %s' % e)
            self.status['inotify'] = False
            return
        idx = self.index
        home = HOME.rstrip('/') + '/'
        first, rest = [], []
        for d, p in enumerate(idx.dirs):
            if p is None:
                continue
            (first if (p + '/').startswith(home) else rest).append(d)
        self._watch(first)
        self._watch(rest)

    def _budget(self):
        lim = inotify_limit()
        self.status['limit'] = lim
        return max(0, lim - 4096) if lim > 16384 else int(lim * 0.6)

    def _watch(self, dids):
        if self.ino is None or self.watch_full:
            return
        budget = self._budget()
        idx = self.index
        for d in dids:
            if len(self.dir_wd) >= budget:
                self.watch_full = True
                break
            p = idx.dirs[d]
            if p is None or d in self.dir_wd:
                continue
            wd = self.ino.add(p)
            if wd < 0:
                if -wd == errno.ENOSPC:
                    self.watch_full = True
                    break
                continue
            old = self.wd_dir.get(wd)
            if old is not None and old != d:
                self.dir_wd.pop(old, None)
            self.dir_wd[d] = wd
            self.wd_dir[wd] = d
        self.status['watched'] = len(self.dir_wd)

    def _unwatch(self, dids):
        for d in dids:
            wd = self.dir_wd.pop(d, None)
            if wd is not None:
                if self.wd_dir.get(wd) == d:
                    self.wd_dir.pop(wd, None)
                    if self.ino is not None:
                        self.ino.rm(wd)
        # 不在这里清 watch_full：仍有未监控目录时必须继续轮询；空出的名额由轮询周期内的重新挂监控补上
        self.status['watched'] = len(self.dir_wd)

    def _refresh(self, did):
        added, removed = self.index.refresh_dir(did, self.excluded, self.moved.pop(did, ()))
        if removed:
            self._unwatch(removed)
        if added:
            self._watch(added)

    def _catch_up(self, only_unwatched):
        idx = self.index
        nd = len(idx.dirs)
        for d in range(nd):
            if self.stopping or self.abort.is_set():
                return
            if only_unwatched and d in self.dir_wd:
                continue
            p = idx.dirs[d]
            if p is None:
                continue
            try:
                mt = os.stat(p).st_mtime
            except OSError:
                self._refresh(d)
                continue
            if mt != idx.dir_mtime[d]:
                self._refresh(d)
            if d % 5000 == 4999:
                time.sleep(0.001)

    def _handle_events(self, events, dirty, touched):
        idx = self.index
        overflow = False
        for wd, mask, name in events:
            if mask & IN_Q_OVERFLOW:
                overflow = True
                continue
            d = self.wd_dir.get(wd)
            if d is None:
                continue
            if mask & IN_IGNORED:
                self.wd_dir.pop(wd, None)
                if self.dir_wd.get(d) == wd:
                    self.dir_wd.pop(d, None)
                continue
            if mask & (IN_DELETE_SELF | IN_MOVE_SELF):
                e = idx.dir_entry[d] if d < len(idx.dir_entry) else -1
                dirty.add(idx.parent[e] if e >= 0 else d)
            elif mask & STRUCT_EVENTS:
                dirty.add(d)
                if mask & (IN_MOVED_FROM | IN_MOVED_TO) and mask & IN_ISDIR and name:
                    # A→T、B→A、T→B 这类对调后名字仍在，但目录内容已换，须整棵重建
                    self.moved.setdefault(d, set()).add(name)
            elif mask & CONTENT_EVENTS and name:
                touched.setdefault(d, set()).add(name)
        return overflow

    def _apply_touched(self, touched):
        idx = self.index
        idx.ensure_children()
        for d, names in touched.items():
            p = idx.dirs[d] if d < len(idx.dirs) else None
            if p is None:
                continue
            kids = idx.dir_children[d]
            if len(names) * 4 < len(kids):
                lookup = {}
                for c in kids:
                    nm = idx.names[c]
                    if nm in names:
                        lookup[nm] = c
            else:
                lookup = {idx.names[c]: c for c in kids}
            for nm in names:
                c = lookup.get(nm)
                if c is None or idx.kind[c] == KIND_DEAD:
                    continue
                try:
                    st = os.lstat(join_path(p, nm))
                    with idx.lock:
                        idx.size[c] = -1 if idx.kind[c] == KIND_DIR else st.st_size
                        idx.mtime[c] = st.st_mtime
                except OSError:
                    pass
        with idx.lock:
            idx.version += 1

    # ---- 大小/时间补全 ----
    def _start_sweep(self, scope):
        if scope is None and self.skip_sweep:
            self.skip_sweep = False
            self.sweep_iter = None
            return
        self.sweep_scope = scope   # None=全部；'unwatched'=仅未监控目录下的
        self.sweep_iter = iter(range(len(self.index.names)))

    def _sweep_step(self, budget=20000):
        if self.sweep_iter is None:
            return False
        idx = self.index
        names, par, kind, dirs = idx.names, idx.parent, idx.kind, idx.dirs
        only_unw = self.sweep_scope == 'unwatched'
        dir_wd = self.dir_wd
        batch = []
        done = True
        for i in self.sweep_iter:
            if kind[i] == KIND_DEAD:
                continue
            d = par[i]
            if only_unw and d in dir_wd:
                continue
            p = dirs[d]
            if p is None:
                continue
            try:
                st = os.lstat(join_path(p, names[i]))
                batch.append((i, -1 if kind[i] == KIND_DIR else st.st_size, st.st_mtime))
            except OSError:
                batch.append((i, 0, 0.0))
            if len(batch) >= budget:
                done = False
                break
        if batch:
            with idx.lock:
                sz, mt = idx.size, idx.mtime
                for i, s, m in batch:
                    sz[i] = s
                    mt[i] = m
        if done:
            self.sweep_iter = None
            with idx.lock:
                idx.version += 1
        return not done

    # ---- 名称排序缓存（分块排序 + 归并，避免长时间占用 GIL 卡界面） ----
    def _compute_order(self):
        idx = self.index
        idx.ensure_lnames()
        n = len(idx.names)
        ln, kind = idx.lnames, idx.kind
        live = [i for i in range(n) if kind[i] != KIND_DEAD]
        key = ln.__getitem__
        chunks = []
        CH = 40000
        for s in range(0, len(live), CH):
            c = live[s:s + CH]
            c.sort(key=key)
            chunks.append(c)
            time.sleep(0)
        if len(chunks) > 1:
            order = list(heapq.merge(*chunks, key=key))
        else:
            order = chunks[0] if chunks else []
        idx.name_order = (order, n)
        self.order_version = idx.version

    def _save(self):
        try:
            v = self.index.version
            self.index.save(INDEX_FILE, self._header())
            self.saved_version = v
        except Exception:
            log('save failed:\n' + traceback.format_exc())

    def _loop(self):
        dirty, touched = set(), {}
        first_event = 0.0
        last_poll = last_sweep = last_save = last_mounts = time.time()
        last_change = 0.0
        while True:
            # 命令
            try:
                while True:
                    cmd = self.cmds.get_nowait()
                    if not self._command(cmd):
                        return
            except queue.Empty:
                pass
            timeout = 0.05 if self.sweep_iter is not None else 0.5
            if self.ino is not None:
                events = self.ino.read(timeout)
            else:
                time.sleep(timeout)
                events = []
            if events:
                if self._handle_events(events, dirty, touched):
                    self.status['msg'] = '事件溢出，正在补扫…'
                    self._catch_up(False)
                    self.status['msg'] = ''
                if not first_event:
                    first_event = time.time()
            now = time.time()
            if (dirty or touched) and now - first_event >= 0.3:
                self.excluded = self._compute_excludes()
                for d in list(dirty):
                    self._refresh(d)
                if touched:
                    self._apply_touched(touched)
                dirty, touched = set(), {}
                first_event = 0.0
                last_change = now
                self._set_ready()
            if now - last_mounts >= 2:
                last_mounts = now
                if self._check_mounts():
                    last_change = now
                    self._set_ready()
            if self.sweep_iter is not None:
                self._sweep_step()
            if now - last_poll >= self.POLL_INTERVAL:
                last_poll = now
                if self.watch_full or self.ino is None:
                    self.excluded = self._compute_excludes()
                    self._catch_up(True)
                    self._set_ready()
                if self.watch_full and len(self.dir_wd) < self._budget():
                    self.watch_full = False
                    self._watch([d for d, p in enumerate(self.index.dirs) if p is not None])
            if now - last_sweep >= self.SWEEP_INTERVAL and self.sweep_iter is None:
                last_sweep = now
                self._start_sweep('unwatched' if self.ino is not None else None)
            if (self.index.version != self.order_version and now - last_change > 2
                    and now - getattr(self, '_last_order', 0) >= self.ORDER_DELAY):
                self._last_order = now
                self._compute_order()
            if now - last_save >= self.SAVE_INTERVAL:
                last_save = now
                if self.index.version != self.saved_version:
                    self._save()

    def _command(self, cmd):
        name = cmd[0]
        if name == 'quit':
            self.stopping = True
            self.abort.set()
            if self.status.get('state') in ('ready', 'updating') and self.index.version != self.saved_version:
                self.status['msg'] = '正在保存索引…'
                self._save()
            self._close_watches()
            self.status['state'] = 'stopped'
            return False
        if name == 'rebuild':
            if len(cmd) > 1 and cmd[1]:
                self.cfg = dict(cmd[1])
            self.abort.clear()
            self._setup_paths()
            self.mounts = set(read_mounts())
            self._full_scan()
            self._start_sweep(None)
            self._set_ready()
        elif name == 'refresh_path':
            p = cmd[1]
            d = self.index.dir_ids.get(dkey(p))
            if d is not None:
                self._refresh(d)
                self._set_ready()
        elif name == 'refresh_all':
            self.status.update(state='updating', msg='正在刷新…')
            self.excluded = self._compute_excludes()
            self._catch_up(False)
            self._start_sweep(None)
            self._set_ready()
        elif name == 'rewatch':
            self.status.update(state='updating', msg='正在重新挂载实时监控…')
            self._init_watches()
            self._catch_up(False)
            self._set_ready()
        elif name == 'save':
            self._save()
        return True


# ----------------------------------------------------------------------------
#  Windows 实时监控：ReadDirectoryChangesW（ctypes，每个根一个句柄，监视整棵子树）
# ----------------------------------------------------------------------------
FILE_ACTION_ADDED, FILE_ACTION_REMOVED, FILE_ACTION_MODIFIED = 1, 2, 3
FILE_ACTION_RENAMED_OLD_NAME, FILE_ACTION_RENAMED_NEW_NAME = 4, 5
WATCH_OVERFLOW, WATCH_LOST = -1, -2


def parse_notify(data):
    """解析 ReadDirectoryChangesW 返回的 FILE_NOTIFY_INFORMATION 链表 → [(action, 相对路径)]。
    纯函数：NextEntryOffset(DWORD) Action(DWORD) FileNameLength(DWORD, 字节) FileName(UTF-16LE)。"""
    out = []
    pos, L = 0, len(data)
    while pos + 12 <= L:
        nxt, act, ln = struct.unpack_from('<III', data, pos)
        end = pos + 12 + ln
        if end > L:
            break
        out.append((act, data[pos + 12:end].decode('utf-16-le', 'surrogatepass')))
        if nxt == 0 or nxt < 12:
            break
        pos += nxt
    return out


class DirWatcherWin(object):
    """每个根一个目录句柄 + 重叠 I/O；read() 用 WaitForMultipleObjects 带超时等待，
    返回 [(根 dir id, action, 相对路径)]；action 为 WATCH_OVERFLOW（缓冲溢出，须补扫）
    或 WATCH_LOST（句柄失效：盘被拔出、根被删除，或为了安全弹出而主动释放，此时路径为 'released'）。
    只由引擎线程调用；release_handle() 可由界面线程调用（响应 WM_DEVICECHANGE 的 DBT_DEVICEQUERYREMOVE）。"""
    BUF_SIZE = 512 * 1024
    NET_BUF_SIZE = 64 * 1024      # 网络盘上 ReadDirectoryChangesW 缓冲不能超过 64 KB
    FILTER = 0x1 | 0x2 | 0x8 | 0x10   # FILE_NAME | DIR_NAME | SIZE | LAST_WRITE

    def __init__(self):
        import ctypes.wintypes as wt
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        u = ctypes.WinDLL('user32', use_last_error=True)
        H, D, B, P = wt.HANDLE, wt.DWORD, wt.BOOL, ctypes.c_void_p

        class OVERLAPPED(ctypes.Structure):
            _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                        ('Offset', D), ('OffsetHigh', D), ('hEvent', H)]

        class DEV_BROADCAST_HANDLE(ctypes.Structure):
            _fields_ = [('dbch_size', D), ('dbch_devicetype', D), ('dbch_reserved', D), ('dbch_handle', H),
                        ('dbch_hdevnotify', P), ('dbch_eventguid', ctypes.c_byte * 16),
                        ('dbch_nameoffset', ctypes.c_long), ('dbch_data', ctypes.c_byte * 4)]
        self.OVERLAPPED, self.DBH = OVERLAPPED, DEV_BROADCAST_HANDLE
        POV = ctypes.POINTER(OVERLAPPED)

        def fn(dll, name, res, *args):
            f = getattr(dll, name)
            f.restype = res
            f.argtypes = list(args)
            return f
        self.CreateFileW = fn(k, 'CreateFileW', H, wt.LPCWSTR, D, D, P, D, D, H)
        self.CreateEventW = fn(k, 'CreateEventW', H, P, B, B, wt.LPCWSTR)
        self.ReadDirectoryChangesW = fn(k, 'ReadDirectoryChangesW', B, H, P, D, B, D, ctypes.POINTER(D), POV, P)
        self.GetOverlappedResult = fn(k, 'GetOverlappedResult', B, H, POV, ctypes.POINTER(D), B)
        self.WaitForMultipleObjects = fn(k, 'WaitForMultipleObjects', D, D, ctypes.POINTER(H), B, D)
        self.WaitForSingleObject = fn(k, 'WaitForSingleObject', D, H, D)
        self.ResetEvent = fn(k, 'ResetEvent', B, H)
        self.CancelIoEx = fn(k, 'CancelIoEx', B, H, POV)
        self.CloseHandle = fn(k, 'CloseHandle', B, H)
        self.RegisterDeviceNotificationW = fn(u, 'RegisterDeviceNotificationW', P, H, P, D)
        self.UnregisterDeviceNotification = fn(u, 'UnregisterDeviceNotification', B, P)
        self.INVALID = ctypes.c_void_p(-1).value
        self.H = H
        self.w = {}            # did -> rec
        self.lock = threading.Lock()
        self.hwnd_getter = None
        self.grave = []        # 取消超时的缓冲区：内核可能仍在写入，不能释放

    def _err(self):
        return ctypes.get_last_error()

    def add(self, did, path, dyn=False, network=False):
        h = self.CreateFileW(long_path(path), 0x1, 0x7, None, 3, 0x02000000 | 0x40000000, None)
        if not h or h == self.INVALID:
            log('watch %s: CreateFileW error %d' % (path, self._err()))
            return False
        ev = self.CreateEventW(None, True, False, None)
        ov = self.OVERLAPPED()
        ov.hEvent = ev
        rec = {'h': h, 'ev': ev, 'ov': ov, 'size': self.NET_BUF_SIZE if network else self.BUF_SIZE,
               'path': path, 'pending': False, 'dead': False, 'released': False, 'dn': None, 'dyn': dyn}
        rec['buf'] = ctypes.create_string_buffer(rec['size'])
        if not self._issue(rec):
            e = self._err()
            if e == 87 and rec['size'] > self.NET_BUF_SIZE:   # ERROR_INVALID_PARAMETER：网络盘缓冲过大
                rec['size'] = self.NET_BUF_SIZE
                rec['buf'] = ctypes.create_string_buffer(rec['size'])
                ok = self._issue(rec)
            else:
                ok = False
            if not ok:
                log('watch %s: ReadDirectoryChangesW error %d' % (path, self._err()))
                self.CloseHandle(h)
                self.CloseHandle(ev)
                return False
        with self.lock:
            self.w[did] = rec
        if dyn:
            self._register(rec)
        return True

    def _issue(self, rec):
        self.ResetEvent(rec['ev'])
        ok = self.ReadDirectoryChangesW(rec['h'], rec['buf'], rec['size'], True, self.FILTER, None,
                                        ctypes.byref(rec['ov']), None)
        rec['pending'] = bool(ok)
        return bool(ok)

    def _register(self, rec):
        """可移动盘：登记句柄通知，用户“安全弹出”时界面线程收到 DBT_DEVICEQUERYREMOVE 并释放句柄。"""
        hwnd = self.hwnd_getter() if self.hwnd_getter else None
        if not hwnd or rec['dn'] or rec['dead']:
            return
        f = self.DBH()
        f.dbch_size = ctypes.sizeof(self.DBH)
        f.dbch_devicetype = 6   # DBT_DEVTYP_HANDLE
        f.dbch_handle = rec['h']
        rec['dn'] = self.RegisterDeviceNotificationW(hwnd, ctypes.byref(f), 0)

    def register_all(self):
        with self.lock:
            recs = list(self.w.values())
        for rec in recs:
            if rec['dyn']:
                self._register(rec)

    def release_handle(self, h):
        """界面线程：设备即将移除，立即关闭对应目录句柄（否则会阻止安全弹出）。"""
        with self.lock:
            for rec in self.w.values():
                if rec['h'] == h and not rec['released']:
                    rec['released'] = True
                    self.CancelIoEx(h, ctypes.byref(rec['ov']))
                    if rec['dn']:
                        self.UnregisterDeviceNotification(rec['dn'])
                        rec['dn'] = None
                    self.CloseHandle(h)
                    return True
        return False

    def read(self, timeout):
        with self.lock:
            recs = [(d, r) for d, r in self.w.items() if not r['dead']]
        if not recs:
            time.sleep(timeout)
            return []
        evs = [r['ev'] for _d, r in recs[:64]]
        arr = (self.H * len(evs))(*evs)
        rc = self.WaitForMultipleObjects(len(evs), arr, False, int(timeout * 1000))
        if rc == 0x102:     # WAIT_TIMEOUT：超过 64 个根时仍检查其余根
            if len(recs) <= 64:
                return []
        elif rc == 0xFFFFFFFF:
            time.sleep(timeout)
            return []
        out = []
        import ctypes.wintypes as wt
        for did, rec in recs:
            with self.lock:
                if rec['dead']:
                    continue
                if rec['released']:
                    rec['dead'] = True
                    out.append((did, WATCH_LOST, 'released'))
                    continue
                n = wt.DWORD(0)
                ok = self.GetOverlappedResult(rec['h'], ctypes.byref(rec['ov']), ctypes.byref(n), False)
                if not ok:
                    e = self._err()
                    if e == 996:            # ERROR_IO_INCOMPLETE：尚无事件
                        continue
                    rec['pending'] = False
                    if e == 1022:           # ERROR_NOTIFY_ENUM_DIR：变化太多，须整体补扫
                        out.append((did, WATCH_OVERFLOW, ''))
                        if self._issue(rec):
                            continue
                    rec['dead'] = True
                    log('watch %s lost: error %d' % (rec['path'], e))
                    out.append((did, WATCH_LOST, ''))
                    continue
                rec['pending'] = False
                if n.value == 0:
                    out.append((did, WATCH_OVERFLOW, ''))
                else:
                    for act, name in parse_notify(ctypes.string_at(rec['buf'], n.value)):
                        out.append((did, act, name))
                if not self._issue(rec):
                    rec['dead'] = True
                    log('watch %s lost on re-issue: error %d' % (rec['path'], self._err()))
                    out.append((did, WATCH_LOST, ''))
        return out

    def remove(self, did):
        with self.lock:
            rec = self.w.pop(did, None)
            if rec is None:
                return
            if rec['dn']:
                self.UnregisterDeviceNotification(rec['dn'])
                rec['dn'] = None
            if not rec['released']:
                if rec['pending']:
                    self.CancelIoEx(rec['h'], ctypes.byref(rec['ov']))
                self.CloseHandle(rec['h'])
                rec['released'] = True
        if rec['pending']:
            # 等待取消完成后才能释放缓冲区与 OVERLAPPED
            if self.WaitForSingleObject(rec['ev'], 2000) != 0:
                self.grave.append(rec)
                return
        self.CloseHandle(rec['ev'])

    def close(self):
        for d in list(self.w):
            self.remove(d)


class EngineWin(Engine):
    """Windows 引擎：根＝盘符（或配置的目录），每根一个 ReadDirectoryChangesW 监视整棵子树；
    扫描直接取 DirEntry.stat() 的大小/时间；盘符插拔增量加根／撤根。
    与平台相关的探测（盘符、监视器）都可注入，便于在 Linux 上做单元测试。"""
    watcher_factory = DirWatcherWin
    RELEASE_HOLD = 10.0      # 为安全弹出释放句柄后，暂不重新监视的秒数
    LOST_HOLD = 2.0

    def __init__(self, index, cfg):
        Engine.__init__(self, index, cfg)
        self.status['limit'] = 0
        self.dyn = set()
        self.net = set()
        self.drive_mask = None
        self.hold = {}
        self.skip_sweep = False
        self.hwnd = None

    # ---- 可注入的平台探测 ----
    def _root_pairs(self):
        drives = win_drive_list()
        self.net = set(r.lower() for r, t in drives if t == DRIVE_REMOTE)
        return win_select_roots(self.cfg, drives)

    def _drive_mask(self):
        return win_drive_mask()

    # ---- 根与排除 ----
    def _setup_paths(self):
        pairs = [(r, d) for r, d in self._root_pairs() if os.path.isdir(r)]
        self.roots = [r for r, _d in pairs]
        self.dyn = set(dkey(r) for r, d in pairs if d)
        self.excluded = self._compute_excludes()
        self.drive_mask = self._drive_mask()

    def _header(self):
        # 只记录固定根：U 盘、网络盘插拔不应让缓存失效
        base = [r for r in self.roots if dkey(r) not in self.dyn]
        keys = [self._prefix(r) for r in base]
        top = []
        for e in sorted(self.excluded):
            if not any(e.startswith(t.rstrip(SEP) + SEP) for t in top):
                top.append(e)
        top = [e for e in top if any((e + SEP).startswith(k) for k in keys)]
        return {'roots': base, 'excludes': top}

    @staticmethod
    def _prefix(p):
        k = dkey(p)
        return k if k[-1:] == SEP else k + SEP

    @staticmethod
    def _under(p, prefs):
        k = dkey(p)
        k2 = k if k[-1:] == SEP else k + SEP
        for x in prefs:
            if k2.startswith(x):
                return True
        return False

    def _root_dids(self):
        idx = self.index
        return [d for d, p in enumerate(idx.dirs) if p is not None and idx.dir_entry[d] < 0]

    def _unwatched_prefixes(self):
        idx = self.index
        return [self._prefix(idx.dirs[d]) for d in self._root_dids() if d not in self.dir_wd]

    def _after_load(self):
        self._sync_roots()

    def _use_cached_stats(self):
        pass

    def _cached_startup(self):
        self._compute_order()
        self.status.update(state='updating', msg='正在同步自上次以来的变化…')
        self._init_watches()
        self._catch_up(False)

    def _full_scan(self):
        Engine._full_scan(self)
        # 扫描时已取得全部大小/时间，紧随其后的全量补全可以省掉
        self.skip_sweep = not self.abort.is_set()

    def _remove_root(self, rd):
        idx = self.index
        p = idx.dirs[rd]
        if p is None:
            return
        self._unwatch([rd])
        removed = idx.remove_root(rd)
        self._unwatch(removed)
        self.roots = [r for r in self.roots if dkey(r) != dkey(p)]
        self.excluded = self._compute_excludes()
        log('root removed: %s' % p)

    def _sync_roots(self):
        """按当前盘符求根：消失的盘整棵撤掉，新出现的盘扫描并监视。返回是否有变化。"""
        idx = self.index
        pairs = [(r, d) for r, d in self._root_pairs() if os.path.isdir(r)]
        want = [r for r, _d in pairs]
        wk = set(dkey(r) for r in want)
        self.dyn = set(dkey(r) for r, d in pairs if d)
        changed = False
        for d in self._root_dids():
            if dkey(idx.dirs[d]) not in wk:
                self._remove_root(d)
                changed = True
        have = set(dkey(r) for r in self.roots)
        new = [r for r in want if dkey(r) not in have or dkey(r) not in idx.dir_ids]
        self.roots = want
        self.excluded = self._compute_excludes()
        for r in new:
            if dkey(r) in idx.dir_ids:
                continue
            log('root added: %s' % r)
            self.status['msg'] = '正在索引新磁盘 %s …' % r
            with idx.lock:
                d = idx._new_dir(r, -1)
            idx.scan_tree([d], self.excluded, self.abort)
            self._watch([d])
            changed = True
        return changed

    def _check_mounts(self):
        changed = False
        mask = self._drive_mask()
        if mask != self.drive_mask:
            self.drive_mask = mask
            changed = self._sync_roots()
        self._retry_watches()
        return changed

    def _retry_watches(self):
        if self.ino is None:
            return
        idx = self.index
        now = time.time()
        todo = [d for d in self._root_dids()
                if d not in self.dir_wd and self.hold.get(dkey(idx.dirs[d]), 0) <= now]
        if not todo:
            return
        self._watch(todo)
        back = [d for d in todo if d in self.dir_wd]
        if back:
            self._catch_up(False, roots=back)   # 重新监视前的空档内可能漏了变化

    # ---- 监视 ----
    def _init_watches(self):
        self._close_watches()
        try:
            self.ino = self.watcher_factory()
        except Exception as e:
            log('directory watcher unavailable: %s' % e)
            self.status['inotify'] = False
            return
        self.status['inotify'] = True
        try:
            self.ino.hwnd_getter = lambda: self.hwnd
        except Exception:
            pass
        self._watch(self._root_dids())

    def _budget(self):
        return 1 << 30

    def _watch(self, dids):
        if self.ino is None:
            return
        idx = self.index
        now = time.time()
        for d in dids:
            if d >= len(idx.dirs):
                continue
            p = idx.dirs[d]
            if p is None or idx.dir_entry[d] >= 0 or d in self.dir_wd:
                continue
            k = dkey(p)
            if self.hold.get(k, 0) > now:
                self.watch_full = True
                continue
            try:
                ok = self.ino.add(d, p, k in self.dyn, k[:3] in self.net)
            except Exception as e:
                log('watch %s failed: %s' % (p, e))
                ok = False
            if ok:
                self.dir_wd[d] = d
                self.wd_dir[d] = d
            else:
                self.hold[k] = now + 30
                self.watch_full = True
        self.watch_full = any(d not in self.dir_wd for d in self._root_dids())

    def _unwatch(self, dids):
        for d in dids:
            if self.dir_wd.pop(d, None) is not None:
                self.wd_dir.pop(d, None)
                if self.ino is not None:
                    try:
                        self.ino.remove(d)
                    except Exception as e:
                        log('unwatch failed: %s' % e)

    def _set_ready(self):
        idx = self.index
        live = [p for p in idx.dirs if p is not None]
        nd = len(live)
        roots = self._root_dids()
        if self.ino is None or not self.dir_wd:
            w = 0
        elif all(d in self.dir_wd for d in roots):
            w = nd
        else:
            prefs = [self._prefix(idx.dirs[d]) for d in self.dir_wd if idx.dirs[d] is not None]
            w = sum(1 for p in live if self._under(p, prefs))
        self.status.update(state='ready', dirs=nd, watched=w, msg='')

    def _catch_up(self, only_unwatched, roots=None):
        idx = self.index
        prefs = None
        if roots is not None:
            prefs = [self._prefix(idx.dirs[r]) for r in roots if idx.dirs[r] is not None]
        elif only_unwatched:
            prefs = self._unwatched_prefixes()
        if prefs is not None and not prefs:
            return
        nd = len(idx.dirs)
        for d in range(nd):
            if self.stopping or self.abort.is_set():
                return
            p = idx.dirs[d]
            if p is None:
                continue
            if prefs is not None and not self._under(p, prefs):
                continue
            try:
                mt = os.stat(long_path(p)).st_mtime
            except OSError:
                self._refresh(d)
                continue
            if mt != idx.dir_mtime[d]:
                self._refresh(d)
            if d % 5000 == 4999:
                time.sleep(0.001)

    def _nearest_dir(self, path):
        """事件所在目录尚未建索引（新建的子树）时，向上找最近的已索引祖先；途经排除目录则忽略。"""
        idx, ex = self.index, self.excluded
        p = path
        while p is not None:
            k = dkey(p)
            if k in ex:
                return None
            d = idx.dir_ids.get(k)
            if d is not None:
                return d
            p = split_path_sep(p, SEP)[0]
        return None

    def _handle_events(self, events, dirty, touched):
        idx = self.index
        over, lost = [], []
        for rd, act, rel in events:
            if act == WATCH_OVERFLOW:
                over.append(rd)
                continue
            if act == WATCH_LOST:
                lost.append((rd, rel))
                continue
            root = idx.dirs[rd] if 0 <= rd < len(idx.dirs) else None
            if root is None or not rel:
                continue
            full = join_path(root, rel)
            parent, name = split_path_sep(full, SEP)
            if parent is None:
                continue
            pd = idx.dir_ids.get(dkey(parent))
            if pd is None:
                pd = self._nearest_dir(parent)
                if pd is not None:
                    dirty.add(pd)
                continue
            if act == FILE_ACTION_MODIFIED:
                if dkey(full) in idx.dir_ids:
                    continue        # 目录的“修改”只是其内容变化，由子项事件处理
                touched.setdefault(pd, set()).add(name)
            else:
                dirty.add(pd)
                if act in (FILE_ACTION_RENAMED_OLD_NAME, FILE_ACTION_RENAMED_NEW_NAME):
                    # 目录对调（A→T、B→A、T→B）后名字仍在但内容已换：强制整棵重建
                    self.moved.setdefault(pd, set()).add(name)
        for rd in sorted(set(over)):
            if rd < len(idx.dirs) and idx.dirs[rd] is not None:
                self.status['msg'] = '事件溢出，正在补扫…'
                log('watch overflow: %s' % idx.dirs[rd])
                self._catch_up(False, roots=[rd])
                if self.sweep_iter is None:
                    self._start_sweep([self._prefix(idx.dirs[rd])])
                self.status['msg'] = ''
        now = time.time()
        for rd, why in lost:
            self._unwatch([rd])
            p = idx.dirs[rd] if rd < len(idx.dirs) else None
            if p is None:
                continue
            if why == 'released':
                self.hold[dkey(p)] = now + self.RELEASE_HOLD
                self.watch_full = True
                continue
            if not os.path.isdir(p):
                self._remove_root(rd)
                continue
            self.hold[dkey(p)] = now + self.LOST_HOLD
            self.watch_full = True
            self._catch_up(False, roots=[rd])
        return False

    # ---- 大小/时间补全：按目录重列（DirEntry 自带统计），比逐个 stat 快得多 ----
    def _start_sweep(self, scope):
        if scope is None and self.skip_sweep:
            self.skip_sweep = False
            self.sweep_iter = None
            return
        self.sweep_scope = scope
        self.sweep_iter = iter(range(len(self.index.dirs)))

    def _sweep_step(self, budget=64):
        if self.sweep_iter is None:
            return False
        idx = self.index
        scope = self.sweep_scope
        if scope == 'unwatched':
            allowed = self._unwatched_prefixes()
        elif isinstance(scope, list):
            allowed = scope
        else:
            allowed = None
        if allowed is not None and not allowed:
            self.sweep_iter = None
            return False
        n = 0
        for d in self.sweep_iter:
            p = idx.dirs[d] if d < len(idx.dirs) else None
            if p is None or (allowed is not None and not self._under(p, allowed)):
                continue
            self._refresh(d)
            n += 1
            if n >= budget:
                return True
        self.sweep_iter = None
        with idx.lock:
            idx.version += 1
        return False

    def _command(self, cmd):
        name = cmd[0]
        if name == 'devnotify':
            if self.ino is not None and hasattr(self.ino, 'register_all'):
                self.ino.register_all()
            return True
        if name == 'drive_check':
            self.drive_mask = None
            if self._check_mounts():
                self._set_ready()
            return True
        return Engine._command(self, cmd)


def make_engine(index, cfg):
    """按平台选择引擎。"""
    return (EngineWin if IS_WIN else Engine)(index, cfg)


# ----------------------------------------------------------------------------
#  搜索：Everything 语法
# ----------------------------------------------------------------------------
UNITS = {'': 1, 'b': 1, 'k': 1024, 'kb': 1024, 'm': 1024 ** 2, 'mb': 1024 ** 2,
         'g': 1024 ** 3, 'gb': 1024 ** 3, 't': 1024 ** 4, 'tb': 1024 ** 4}
SIZE_WORDS = {
    'empty': (0, 0), 'tiny': (0, 10 * 1024), 'small': (10 * 1024, 100 * 1024),
    'medium': (100 * 1024, 1024 ** 2), 'large': (1024 ** 2, 16 * 1024 ** 2),
    'huge': (16 * 1024 ** 2, 128 * 1024 ** 2), 'gigantic': (128 * 1024 ** 2, 1 << 62),
}

FILTERS = [
    ('所有', None),
    ('文件夹', 'folder:'),
    ('文档', 'ext:doc;docx;wps;wpt;dot;rtf;odt;pdf;ofd;txt;md;xls;xlsx;et;csv;ods;ppt;pptx;dps;odp;vsd;vsdx;html;htm;xml;json;tex;epub;chm'),
    ('图片', 'ext:jpg;jpeg;png;gif;bmp;tif;tiff;webp;svg;ico;heic;raw;cr2;nef;arw;dng;psd;ai;eps'),
    ('音频', 'ext:mp3;wav;flac;aac;m4a;ogg;opus;wma;ape;amr;mid;midi'),
    ('视频', 'ext:mp4;mkv;avi;mov;wmv;flv;webm;m4v;mpg;mpeg;ts;m2ts;3gp;rmvb;rm;insv;lrv'),
    ('压缩包', 'ext:zip;rar;7z;tar;gz;tgz;bz2;xz;zst;lz4;iso;deb;rpm;cab;jar'),
    ('可执行/脚本', 'ext:sh;py;run;appimage;bin;exe;msi;bat;cmd;desktop;so'),
    ('代码', 'ext:c;cc;cpp;cxx;h;hpp;py;java;js;ts;go;rs;cs;m;swift;kt;lua;sql;qml;ui;cmake;pro'),
]


def parse_size(s):
    m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*([a-z]*)\s*$', s.lower())
    if not m or m.group(2) not in UNITS:
        raise ValueError(s)
    return int(float(m.group(1)) * UNITS[m.group(2)])


def size_range(v):
    v = v.strip().lower()
    if v in SIZE_WORDS:
        return SIZE_WORDS[v]
    if '..' in v:
        a, b = v.split('..', 1)
        return (parse_size(a) if a else 0, parse_size(b) if b else 1 << 62)
    for op in ('>=', '<=', '>', '<', '='):
        if v.startswith(op):
            x = parse_size(v[len(op):])
            return {'>=': (x, 1 << 62), '<=': (0, x), '>': (x + 1, 1 << 62),
                    '<': (0, x - 1), '=': (x, x)}[op]
    x = parse_size(v)
    return (x, x)


def _day_start(d):
    return time.mktime(d.timetuple())


def date_range(v):
    v = v.strip().lower()
    today = datetime.date.today()
    one = datetime.timedelta(days=1)
    if '..' in v:
        a, b = v.split('..', 1)
        ra = date_range(a) if a else (0, 0)
        rb = date_range(b) if b else (0, 4e9)
        return (ra[0], rb[1])
    if v == 'today':
        return (_day_start(today), _day_start(today + one))
    if v == 'yesterday':
        return (_day_start(today - one), _day_start(today))
    if v == 'thisweek':
        s = today - datetime.timedelta(days=today.weekday())
        return (_day_start(s), 4e9)
    if v == 'thismonth':
        return (_day_start(today.replace(day=1)), 4e9)
    if v == 'thisyear':
        return (_day_start(today.replace(month=1, day=1)), 4e9)
    m = re.match(r'^(?:last)?(\d+)(d|days?|w|weeks?|m|months?|y|years?)$', v)
    if m:
        k = int(m.group(1))
        u = m.group(2)[0]
        days = {'d': 1, 'w': 7, 'm': 30, 'y': 365}[u] * k
        return (time.time() - days * 86400, 4e9)
    m = re.match(r'^(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?$', v)
    if m:
        y = int(m.group(1))
        if m.group(3):
            d = datetime.date(y, int(m.group(2)), int(m.group(3)))
            return (_day_start(d), _day_start(d + one))
        if m.group(2):
            mo = int(m.group(2))
            d0 = datetime.date(y, mo, 1)
            d1 = datetime.date(y + (mo == 12), mo % 12 + 1, 1)
            return (_day_start(d0), _day_start(d1))
        return (_day_start(datetime.date(y, 1, 1)), _day_start(datetime.date(y + 1, 1, 1)))
    raise ValueError(v)


class Pred(object):
    __slots__ = ('kind', 'text', 'rx', 'arg', 'path', 'cost')

    def __init__(self, kind, text='', rx=None, arg=None, path=False, cost=1):
        self.kind, self.text, self.rx, self.arg, self.path, self.cost = kind, text, rx, arg, path, cost


def split_tokens(q):
    toks, cur, inq = [], [], False
    for ch in q:
        if ch == '"':
            inq = not inq
            cur.append(ch)
        elif ch.isspace() and not inq:
            if cur:
                toks.append(''.join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        toks.append(''.join(cur))
    return toks


def split_or(tok):
    parts, cur, inq = [], [], False
    for ch in tok:
        if ch == '"':
            inq = not inq
            cur.append(ch)
        elif ch == '|' and not inq:
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append(''.join(cur))
    return [p for p in parts if p != '']


def is_abs_term(t):
    """查询词是否为绝对路径（Linux：/…；Windows：C:… 或 \\…）。"""
    if IS_WIN:
        return t.startswith('\\') or re.match(r'^[A-Za-z]:', t) is not None
    return t.startswith('/')


class Query(object):
    """把查询串编译为 [(neg, [Pred,...]), ...]：组间为与，组内为或。"""

    def __init__(self, text, case=False, whole=False, match_path=False, regex=False, extra=None):
        self.text = text
        self.case = case
        self.whole = whole
        self.match_path = match_path
        self.regex = regex
        self.groups = []
        self.highlights = []
        self.error = None
        try:
            self._compile(text, extra)
        except (re.error, ValueError, OverflowError, RecursionError) as e:
            # OverflowError：regex:a{4294967296}；RecursionError：极深嵌套括号——均按语法错误提示，不能让界面崩溃
            self.error = str(e) or type(e).__name__
            self.groups = []

    def _flags(self):
        return 0 if self.case else re.IGNORECASE

    def _compile(self, text, extra):
        if extra:
            for t in split_tokens(extra):
                self.groups.append((False, [self._term(t)]))
        text = text.strip()
        if not text:
            return
        if self.regex:
            self.groups.append((False, [Pred('regex', rx=re.compile(text, self._flags()),
                                             path=self.match_path, cost=5)]))
            return
        toks = []
        for tok in split_tokens(text):
            # “a | b”（竖线两侧有空格）与 “a|b” 等价
            if toks and (tok.startswith('|') or toks[-1].endswith('|')):
                toks[-1] += tok
            else:
                toks.append(tok)
        for tok in toks:
            neg = False
            while tok.startswith('!') and len(tok) > 1:
                neg = not neg
                tok = tok[1:]
            alts = [self._term(a) for a in split_or(tok)]
            alts = [a for a in alts if a is not None]
            if alts:
                self.groups.append((neg, alts))
        self.groups.sort(key=lambda g: (g[0], max(p.cost for p in g[1])))

    def _term(self, t):
        low = t.lower()
        m = re.match(r'^([a-z]+):(.*)$', low, re.S)
        if m and m.group(1) in ('ext', 'file', 'folder', 'dir', 'regex', 'size', 'dm', 'path',
                                'case', 'nocase', 'wholeword', 'ww'):
            key = m.group(1)
            val = t[len(key) + 1:]
            if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                val = val[1:-1]
            if key == 'ext':
                exts = set(e.strip().lower().lstrip('.') for e in val.split(';') if e.strip())
                return Pred('ext', arg=exts, cost=2) if exts else None
            if key == 'file':
                return Pred('file', cost=2) if not val else self._and_kind(val, KIND_FILE)
            if key in ('folder', 'dir'):
                return Pred('folder', cost=2) if not val else self._and_kind(val, KIND_DIR)
            if key == 'regex':
                return Pred('regex', rx=re.compile(val, self._flags()), path=self.match_path, cost=5)
            if key == 'size':
                return Pred('size', arg=size_range(val), cost=8)
            if key == 'dm':
                return Pred('dm', arg=date_range(val), cost=8)
            if key == 'path':
                return self._text_term(val, force_path=True)
            if key in ('case', 'nocase', 'wholeword', 'ww'):
                return self._text_term(val)
        return self._text_term(t)

    def _and_kind(self, val, kind):
        p = self._text_term(val)
        if p.kind == 'all':   # folder:"" / file:" —— 去掉引号后为空，仍须按类型过滤
            return Pred('folder' if kind == KIND_DIR else 'file', cost=2)
        p.arg = kind
        return p

    def _text_term(self, t, force_path=False):
        if len(t) >= 2 and t.startswith('"') and t.endswith('"'):
            t = t[1:-1]
        else:
            t = t.replace('"', '')
        if t == '':
            return Pred('all', cost=0)
        if IS_WIN:
            t = t.replace('/', '\\')   # Windows：'/' 与 '\\' 都按路径分隔符
        sep = SEP
        path = force_path or self.match_path or (sep in t)
        cmp = t if self.case else t.lower()
        if '*' in t or '?' in t:
            pat = fnmatch.translate(cmp)
            if path and not t.startswith('*') and not is_abs_term(t):
                pat = '(?s:.*)' + pat   # 路径通配允许前缀
            for piece in re.split(r'[*?]+', cmp):
                if piece:
                    self.highlights.append(piece)
            return Pred('wild', text=cmp, rx=re.compile(pat), path=path, cost=4)
        if self.whole:
            self.highlights.append(cmp)
            rx = re.compile(r'(?<!\w)' + re.escape(cmp) + r'(?!\w)')
            return Pred('regex', text=cmp, rx=rx, path=path, cost=5)   # text：子串预筛
        self.highlights.append(cmp.split(sep)[-1] or cmp)
        return Pred('sub', text=cmp, path=path, cost=3 if path else 1)

    def is_plain(self):
        t = self.text
        return (not self.regex and not self.whole and t.strip() != '' and
                not re.search(r'[|!":*?/<>\\]', t))


class Searcher(object):
    def __init__(self, index):
        self.index = index
        self.prev = None   # (text, opts, version, extra, raw_results)

    def run(self, q, extra_key=None):
        """返回未排序的条目号列表；调用方持 index.lock。"""
        self.index.ensure_lnames()
        idx = self.index
        if q.error:
            return []
        opts = (q.case, q.whole, q.match_path, q.regex)
        cand = None
        if (self.prev is not None and q.is_plain() and self.prev[1] == opts and
                self.prev[2] == idx.version and self.prev[3] == extra_key and
                self.prev[0] and q.text.startswith(self.prev[0]) and
                Query(self.prev[0]).is_plain()):
            cand = self.prev[4]
        res = cand
        for neg, alts in q.groups:
            if len(alts) == 1 and not neg:
                res = self._filter(alts[0], res)
            else:
                base = res
                hit = set()
                for a in alts:
                    hit.update(self._filter(a, base))
                if base is None:
                    base = self._all()
                if neg:
                    res = [i for i in base if i not in hit]
                else:
                    res = [i for i in base if i in hit]
            if not res:
                res = []
                break
        if res is None:
            res = self._all()
        elif res is cand:
            res = list(res)
        self.prev = (q.text, opts, idx.version, extra_key, res)
        return res

    def _all(self):
        k = self.index.kind
        return [i for i, x in enumerate(k) if x != KIND_DEAD]

    def ensure_stats(self, items):
        idx = self.index
        mt, sz, kind, names, par, dirs = idx.mtime, idx.size, idx.kind, idx.names, idx.parent, idx.dirs
        for i in items:
            if mt[i] < 0 and kind[i] != KIND_DEAD:
                p = dirs[par[i]]
                if p is None:
                    continue
                try:
                    st = os.lstat(join_path(p, names[i]))
                    sz[i] = -1 if kind[i] == KIND_DIR else st.st_size
                    mt[i] = st.st_mtime
                except OSError:
                    sz[i] = 0
                    mt[i] = 0.0

    def _filter(self, p, cand):
        idx = self.index
        kind = idx.kind
        k = p.kind
        case = p.text != '' and p.text != p.text.lower() or False
        if k == 'all':
            return self._all() if cand is None else cand
        if k == 'file':
            src = range(len(kind)) if cand is None else cand
            return [i for i in src if kind[i] == KIND_FILE]
        if k == 'folder':
            src = range(len(kind)) if cand is None else cand
            return [i for i in src if kind[i] == KIND_DIR]
        if k == 'ext':
            ln = idx.lnames
            exts = p.arg
            src = range(len(kind)) if cand is None else cand
            out = []
            for i in src:
                if kind[i] == KIND_FILE:
                    n = ln[i]
                    j = n.rfind('.')
                    if j >= 0 and n[j + 1:] in exts:
                        out.append(i)
            return out
        if k in ('size', 'dm'):
            src = self._all() if cand is None else [i for i in cand if kind[i] != KIND_DEAD]
            self.ensure_stats(src)
            lo, hi = p.arg
            if k == 'size':
                sz = idx.size
                return [i for i in src if kind[i] == KIND_FILE and lo <= sz[i] <= hi]
            mt = idx.mtime
            return [i for i in src if lo <= mt[i] < hi]
        # 文本类
        res = self._text_filter(p, cand)
        if p.arg is not None and k in ('sub', 'wild', 'regex'):
            want = p.arg
            res = [i for i in res if kind[i] == want]
        return res

    def _text_filter(self, p, cand):
        idx = self.index
        lower = not self._case_sensitive(p)
        names = idx.lnames if lower else idx.names
        k = p.kind
        if not p.path:
            if k == 'sub':
                t = p.text
                if cand is None:
                    return [i for i, n in enumerate(names) if t in n]
                return [i for i in cand if t in names[i]]
            m = p.rx.match if k == 'wild' else p.rx.search
            if k == 'regex' and p.text:
                # 全字匹配：先用子串快速预筛，再跑正则（百万条目从 ~400 ms 降到几十 ms）
                t = p.text
                if cand is None:
                    return [i for i, n in enumerate(names) if t in n and m(n)]
                return [i for i in cand if t in names[i] and m(names[i])]
            if cand is None:
                return [i for i, n in enumerate(names) if n and m(n)]
            return [i for i in cand if m(names[i])]
        dp = idx.dir_prefixes(lower)
        par = idx.parent
        if k == 'sub':
            # 先按目录算一遍（目录数远少于条目数），条目只查表，避免逐条拼接完整路径
            t = p.text
            sep = SEP
            if sep not in t:
                dhit = bytearray(1 if t in d else 0 for d in dp)
                if cand is None:
                    return [i for i, n in enumerate(names) if n and (dhit[par[i]] or t in n)]
                return [i for i in cand if dhit[par[i]] or t in names[i]]
            # 文件名不含分隔符：t 出现在 “目录/名称” 中 ⇔ t 整个落在目录前缀里，
            # 或 目录前缀以 t 的最后一个分隔符及之前部分结尾、且名称以其后部分开头
            k2 = t.rfind(sep)
            head, tail = t[:k2 + 1], t[k2 + 1:]
            dhit = bytearray((1 if t in d else (2 if d.endswith(head) else 0)) if d else 0 for d in dp)
            if cand is None:
                cand = range(len(names))
            out = []
            for i in cand:
                h = dhit[par[i]]
                if h == 1 or (h == 2 and names[i].startswith(tail)):
                    if names[i]:
                        out.append(i)
            return out
        m = p.rx.match if k == 'wild' else p.rx.search
        if cand is None:
            return [i for i, n in enumerate(names) if n and m(dp[par[i]] + n)]
        return [i for i in cand if m(dp[par[i]] + names[i])]

    def _case_sensitive(self, p):
        return getattr(self, 'case', False)


# ----------------------------------------------------------------------------
#  Windows 系统集成（无 Qt 依赖的部分，便于单元测试）
# ----------------------------------------------------------------------------
def server_name():
    """单实例本地套接字名。Linux 沿用 qianxun-<uid>；Windows 没有 getuid，用用户名的安全化形式 + 散列。"""
    if hasattr(os, 'getuid'):
        return 'qianxun-%d' % os.getuid()
    import getpass
    import zlib   # 运行库裁掉了 _hashlib，不用 hashlib
    try:
        u = getpass.getuser()
    except Exception:
        u = os.environ.get('USERNAME') or 'user'
    dom = os.environ.get('USERDOMAIN', '')
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', u)[:32]
    h = '%08x' % (zlib.crc32((dom + '\\' + u).encode('utf-8', 'surrogatepass')) & 0xffffffff)
    return 'qianxun-%s-%s' % (safe, h)


HK_MODS = {'ctrl': 0x2, 'control': 0x2, 'alt': 0x1, 'shift': 0x4, 'meta': 0x8, 'win': 0x8}
HK_KEYS = {'space': 0x20, 'tab': 0x09, 'esc': 0x1B, 'escape': 0x1B, 'ins': 0x2D, 'insert': 0x2D,
           'del': 0x2E, 'delete': 0x2E, 'home': 0x24, 'end': 0x23, 'pgup': 0x21, 'pageup': 0x21,
           'pgdown': 0x22, 'pagedown': 0x22, 'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
           'backspace': 0x08, 'return': 0x0D, 'enter': 0x0D, 'pause': 0x13, 'print': 0x2C,
           '`': 0xC0, '~': 0xC0, '-': 0xBD, '=': 0xBB, '+': 0xBB, '[': 0xDB, ']': 0xDD, ';': 0xBA,
           "'": 0xDE, ',': 0xBC, '.': 0xBE, '/': 0xBF, '\\': 0xDC}


def parse_hotkey(s):
    """'Ctrl+Alt+F'（QKeySequence.PortableText）→ (RegisterHotKey 修饰键, 虚拟键码)；无效或为空返回 None。
    无修饰键时只接受 F1–F24，避免全局劫持普通按键。"""
    s = (s or '').strip()
    if not s:
        return None
    if s.endswith('++'):
        parts = s[:-2].split('+') + ['+']
    else:
        parts = s.split('+')
    if len(parts) < 1 or parts[-1].strip() == '':
        return None
    mods = 0
    for p in parts[:-1]:
        m = HK_MODS.get(p.strip().lower())
        if m is None:
            return None
        mods |= m
    k = parts[-1].strip()
    kl = k.lower()
    fkey = re.match(r'^f([1-9]|1[0-9]|2[0-4])$', kl)
    if len(k) == 1 and k.isalnum() and ord(k) < 128:
        vk = ord(k.upper())
    elif fkey:
        vk = 0x6F + int(fkey.group(1))
    elif kl in HK_KEYS:
        vk = HK_KEYS[kl]
    else:
        return None
    if not mods and not fkey:
        return None
    return mods, vk


def launcher_command(env=None, executable=None, script=None, exists=os.path.exists):
    """(快捷方式目标, 命令行)。启动器 QianXun.exe 通过环境变量 QIANXUN_LAUNCHER 告知自身路径；
    缺省（直接用 Python 运行）时为 pythonw.exe + 脚本。"""
    import ntpath
    env = os.environ if env is None else env
    la = env.get('QIANXUN_LAUNCHER')
    if la:
        return la, '"%s"' % la
    exe = executable or sys.executable
    d, b = ntpath.split(exe)
    if b.lower() == 'python.exe' and exists(ntpath.join(d, 'pythonw.exe')):
        exe = ntpath.join(d, 'pythonw.exe')
    script = script or os.path.abspath(__file__)
    return exe, '"%s" "%s"' % (exe, script)


RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_VALUE = 'QianXun'


def win_autostart_get():
    """返回 HKCU\\...\\Run\\QianXun 的命令行（未设置为 ''）。"""
    if not IS_WIN:
        return ''
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            v, _t = winreg.QueryValueEx(k, RUN_VALUE)
            return v or ''
    except OSError:
        return ''


def win_autostart_set(on):
    """登录 Windows 时以 --hidden 启动（写 HKCU，无需管理员）。"""
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, launcher_command()[1] + ' --hidden')
        else:
            try:
                winreg.DeleteValue(k, RUN_VALUE)
            except FileNotFoundError:
                pass


def win_terminal_commands(d, which=None):
    """“在终端中打开”的候选 [(argv, creationflags)]：Windows Terminal → PowerShell → cmd。"""
    which = which or shutil.which
    out = []
    wt = which('wt.exe') or which('wt')
    if wt and ';' not in d:          # wt 把 ';' 当作命令分隔符
        out.append(([wt, '-d', d], 0))
    ps = which('powershell.exe') or which('powershell')
    if ps:
        out.append(([ps, '-NoExit'], 0x10))     # CREATE_NEW_CONSOLE
    out.append(([which('cmd.exe') or 'cmd.exe'], 0x10))
    return out


def win_drive_type(path):
    if not IS_WIN:
        return 0
    try:
        f = ctypes.windll.kernel32.GetDriveTypeW
        f.argtypes = [ctypes.c_wchar_p]
        f.restype = ctypes.c_uint
        root = path[:3] if re.match(r'^[A-Za-z]:\\', path) else None
        if root is None:
            return DRIVE_REMOTE if path.startswith('\\\\') else 0
        return int(f(root))
    except Exception:
        return 0


def win_show_properties(path, hwnd=None):
    """弹出资源管理器的“属性”对话框（ShellExecuteExW，动词 properties）。"""
    import ctypes.wintypes as wt

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [('cbSize', wt.DWORD), ('fMask', ctypes.c_ulong), ('hwnd', wt.HWND), ('lpVerb', wt.LPCWSTR),
                    ('lpFile', wt.LPCWSTR), ('lpParameters', wt.LPCWSTR), ('lpDirectory', wt.LPCWSTR),
                    ('nShow', ctypes.c_int), ('hInstApp', wt.HINSTANCE), ('lpIDList', ctypes.c_void_p),
                    ('lpClass', wt.LPCWSTR), ('hkeyClass', wt.HKEY), ('dwHotKey', wt.DWORD),
                    ('hIconOrMonitor', wt.HANDLE), ('hProcess', wt.HANDLE)]
    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = 0x0000000C | 0x00000400      # SEE_MASK_INVOKEIDLIST | SEE_MASK_FLAG_NO_UI
    sei.hwnd = hwnd
    sei.lpVerb = 'properties'
    sei.lpFile = path
    sei.nShow = 1
    f = ctypes.WinDLL('shell32', use_last_error=True).ShellExecuteExW
    f.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    f.restype = wt.BOOL
    return bool(f(ctypes.byref(sei)))


def win_recycle(path):
    """SHFileOperationW(FO_DELETE, FOF_ALLOWUNDO…) 移到回收站；调用方须先确认所在盘支持回收站。"""
    import ctypes.wintypes as wt

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [('hwnd', wt.HWND), ('wFunc', wt.UINT), ('pFrom', wt.LPCWSTR), ('pTo', wt.LPCWSTR),
                    ('fFlags', wt.WORD), ('fAnyOperationsAborted', wt.BOOL), ('hNameMappings', ctypes.c_void_p),
                    ('lpszProgressTitle', wt.LPCWSTR)]
    op = SHFILEOPSTRUCTW()
    op.wFunc = 3                         # FO_DELETE
    op.pFrom = path + '\0'               # 双 NUL 结尾（ctypes 再补一个）
    op.fFlags = 0x40 | 0x10 | 0x4 | 0x400   # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI
    f = ctypes.WinDLL('shell32').SHFileOperationW
    f.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    f.restype = ctypes.c_int
    r = f(ctypes.byref(op))
    return r == 0 and not op.fAnyOperationsAborted


def win_set_app_id(app_id='QianXun.FileSearch'):
    """任务栏按千寻（而不是 Python）分组并显示千寻图标。"""
    try:
        f = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        f.argtypes = [ctypes.c_wchar_p]
        f(app_id)
    except Exception:
        pass


# ----------------------------------------------------------------------------
#  界面
# ----------------------------------------------------------------------------
#  Qt 绑定兼容层：x86_64 用 PyQt5（Qt5），飞腾 aarch64 离线包用 PySide6（Qt6），
#  系统自带 PyQt5 时优先使用系统的（输入法、主题与系统一致）。
HAVE_QT = False
QT_BINDING = ''
_QT_ERROR = None
_order = ['PyQt5', 'PySide6']
if os.environ.get('QIANXUN_QT') in _order:
    _order.remove(os.environ['QIANXUN_QT'])
    _order.insert(0, os.environ['QIANXUN_QT'])
for _b in _order:
    try:
        if _b == 'PyQt5':
            from PyQt5 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets, QtNetwork as _QtNetwork
            _QAction, _QShortcut = _QtWidgets.QAction, _QtWidgets.QShortcut
            QT_VER = _QtCore.QT_VERSION_STR
        elif _b == 'PySide6':
            from PySide6 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets, QtNetwork as _QtNetwork
            _QAction, _QShortcut = _QtGui.QAction, _QtGui.QShortcut
            QT_VER = _QtCore.qVersion()
        else:
            from PyQt6 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets, QtNetwork as _QtNetwork
            _QAction, _QShortcut = _QtGui.QAction, _QtGui.QShortcut
            QT_VER = _QtCore.QT_VERSION_STR
        QT_BINDING = _b
        HAVE_QT = True
        break
    except ImportError as _e:
        _QT_ERROR = _QT_ERROR or _e

if HAVE_QT:
    Qt = _QtCore.Qt
    QAbstractTableModel, QModelIndex, QTimer, QSize, QRect, QUrl, QMimeData, QByteArray, QPoint, QPointF, QRectF = (
        getattr(_QtCore, n) for n in ('QAbstractTableModel', 'QModelIndex', 'QTimer', 'QSize', 'QRect', 'QUrl',
                                      'QMimeData', 'QByteArray', 'QPoint', 'QPointF', 'QRectF'))
    QMimeDatabase = getattr(_QtCore, 'QMimeDatabase', None)
    (QIcon, QPixmap, QPainter, QColor, QLinearGradient, QPen, QFont, QFontMetrics, QKeySequence, QPalette,
     QPainterPath, QGuiApplication, QDesktopServices) = (
        getattr(_QtGui, n) for n in ('QIcon', 'QPixmap', 'QPainter', 'QColor', 'QLinearGradient', 'QPen', 'QFont',
                                     'QFontMetrics', 'QKeySequence', 'QPalette', 'QPainterPath', 'QGuiApplication',
                                     'QDesktopServices'))
    _W = _QtWidgets
    (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QTreeView, QLabel, QMenu,
     QSystemTrayIcon, QStyledItemDelegate, QStyle, QAbstractItemView, QMessageBox, QFileDialog, QDialog,
     QListWidget, QPushButton, QCheckBox, QDialogButtonBox, QGroupBox, QGridLayout, QInputDialog, QTextBrowser,
     QFileIconProvider) = (getattr(_W, n) for n in (
        'QApplication', 'QMainWindow', 'QWidget', 'QVBoxLayout', 'QHBoxLayout', 'QLineEdit', 'QComboBox',
        'QTreeView', 'QLabel', 'QMenu', 'QSystemTrayIcon', 'QStyledItemDelegate', 'QStyle', 'QAbstractItemView',
        'QMessageBox', 'QFileDialog', 'QDialog', 'QListWidget', 'QPushButton', 'QCheckBox', 'QDialogButtonBox',
        'QGroupBox', 'QGridLayout', 'QInputDialog', 'QTextBrowser', 'QFileIconProvider'))
    QAction, QShortcut = _QAction, _QShortcut
    QLocalServer, QLocalSocket = _QtNetwork.QLocalServer, _QtNetwork.QLocalSocket

    def qexec(obj):
        f = getattr(obj, 'exec_', None) or getattr(obj, 'exec')
        return f()

    def qflag(v):
        """PyQt5 的角色数据要求 int，Qt6 绑定直接用枚举。"""
        return int(v) if QT_BINDING == 'PyQt5' else v

    def qbytes(ba):
        return bytes(ba.data())

    COLS = ['名称', '路径', '大小', '修改时间']

    def make_app_icon():
        icon = QIcon()
        for s in (16, 24, 32, 48, 64, 128, 256):
            pm = QPixmap(s, s)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            k = s / 256.0
            g = QLinearGradient(0, 0, s, s)
            g.setColorAt(0, QColor('#1E4FD8'))
            g.setColorAt(1, QColor('#13A3C2'))
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, s, s), 52 * k, 52 * k)
            p.fillPath(path, g)
            pen = QPen(QColor('white'))
            pen.setWidthF(max(1.5, 22 * k))
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(108 * k, 108 * k), 62 * k, 62 * k)
            pen.setWidthF(max(2.0, 30 * k))
            p.setPen(pen)
            p.drawLine(QPointF(156 * k, 156 * k), QPointF(206 * k, 206 * k))
            if s >= 32:
                pen.setWidthF(max(1.0, 12 * k))
                p.setPen(pen)
                p.setOpacity(0.9)
                for j, (w) in enumerate((70, 54, 38)):
                    y = (86 + j * 22) * k
                    x0 = 108 * k - 35 * k
                    p.drawLine(QPointF(x0, y), QPointF(x0 + w * k, y))
            p.end()
            icon.addPixmap(pm)
        return icon

    def human_size(n):
        if n < 0:
            return ''
        if n < 1024:
            return '%d B' % n
        for u in ('KB', 'MB', 'GB', 'TB'):
            n /= 1024.0
            if n < 1024 or u == 'TB':
                return ('%.0f %s' if n >= 100 else '%.1f %s') % (n, u)

    class IconCache(object):
        PATH_EXTS = ('exe', 'lnk', 'ico', 'url', 'scr', 'cpl', 'msc')   # Windows：每个文件图标不同，按路径缓存

        def __init__(self):
            self.cache = {}
            self.db = QMimeDatabase() if QMimeDatabase else None
            self.prov = prov = QFileIconProvider()
            self.folder = QIcon.fromTheme('folder', prov.icon(QFileIconProvider.Folder))
            self.file = QIcon.fromTheme('text-x-generic', prov.icon(QFileIconProvider.File))
            if IS_WIN:
                from collections import OrderedDict
                self.lru = OrderedDict()

        def get_win(self, name, path_fn):
            """Windows：QIcon.fromTheme 无效，用 QFileIconProvider 按真实文件取系统图标。
            普通扩展名取首次遇到的真实文件、按扩展名缓存；.exe/.lnk/.ico/.url 等按路径缓存（LRU 2000）。"""
            j = name.rfind('.')
            ext = name[j + 1:].lower() if j > 0 else ''
            if ext in self.PATH_EXTS:
                p = path_fn()
                if not p:
                    return self.file
                ic = self.lru.get(p)
                if ic is not None:
                    self.lru.move_to_end(p)
                    return ic
                try:
                    ic = self.prov.icon(_QtCore.QFileInfo(p))
                except Exception:
                    ic = None
                if ic is None or ic.isNull():
                    ic = self.file
                self.lru[p] = ic
                if len(self.lru) > 2000:
                    self.lru.popitem(last=False)
                return ic
            ic = self.cache.get(ext)
            if ic is None:
                p = path_fn()
                try:
                    ic = self.prov.icon(_QtCore.QFileInfo(p)) if p else None
                except Exception:
                    ic = None
                if ic is None or ic.isNull():
                    ic = self.file
                self.cache[ext] = ic
            return ic

        def get(self, name, isdir, path_fn=None):
            if isdir:
                return self.folder
            if IS_WIN and path_fn is not None:
                return self.get_win(name, path_fn)
            j = name.rfind('.')
            ext = name[j + 1:].lower() if j > 0 else ''
            ic = self.cache.get(ext)
            if ic is None:
                ic = self.file
                if ext and self.db is not None:
                    mt = self.db.mimeTypeForFile('x.' + ext, QMimeDatabase.MatchExtension)
                    if mt.isValid() and not mt.isDefault():
                        ic = QIcon.fromTheme(mt.iconName(), QIcon.fromTheme(mt.genericIconName(), self.file))
                self.cache[ext] = ic
            return ic

    class ResultModel(QAbstractTableModel):
        def __init__(self, index, parent=None):
            QAbstractTableModel.__init__(self, parent)
            self.index_ = index
            self.rows = []
            self.icons = IconCache()
            self.fresh = {}
            self.sorter = None
            self.gen = index.gen

        def set_rows(self, rows, gen=None):
            self.beginResetModel()
            self.rows = rows
            self.gen = self.index_.gen if gen is None else gen
            self.fresh = {}
            self.endResetModel()

        def rowCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else len(self.rows)

        def columnCount(self, parent=QModelIndex()):
            return 0 if parent.isValid() else 4

        def headerData(self, section, orientation, role=Qt.DisplayRole):
            if orientation == Qt.Horizontal and role == Qt.DisplayRole:
                return COLS[section]
            if orientation == Qt.Horizontal and role == Qt.TextAlignmentRole and section == 2:
                return qflag(Qt.AlignRight | Qt.AlignVCenter)
            return None

        def entry(self, row):
            # 索引被 clear()/load() 整体替换后，旧条目号会指向别的文件——一律作废，等下一次搜索刷新
            if 0 <= row < len(self.rows) and self.gen == self.index_.gen:
                return self.rows[row]
            return -1

        def _stat(self, i):
            idx = self.index_
            now = time.time()
            t = self.fresh.get(i)
            if t is None or now - t > 10:
                self.fresh[i] = now
                p = idx.fullpath(i)
                if p is not None:
                    try:
                        st = os.lstat(p)
                        idx.size[i] = -1 if idx.kind[i] == KIND_DIR else st.st_size
                        idx.mtime[i] = st.st_mtime
                    except OSError:
                        pass

        def data(self, mi, role=Qt.DisplayRole):
            if not mi.isValid():
                return None
            # 引擎线程逐个数组追加条目，不持锁读取会看到长度不一致的数组（IndexError，PyQt5 下直接 abort）
            with self.index_.lock:
                return self._data(mi, role)

        def _data(self, mi, role):
            i = self.entry(mi.row())
            idx = self.index_
            if i < 0 or i >= len(idx.kind):
                return None
            col = mi.column()
            dead = idx.kind[i] == KIND_DEAD
            if role == Qt.DisplayRole:
                if dead:
                    return '（已删除）' if col == 0 else ''
                if col == 0:
                    return disp(idx.names[i])
                if col == 1:
                    return disp(idx.dirpath(i) or '')
                self._stat(i)
                if col == 2:
                    return '' if idx.kind[i] == KIND_DIR else human_size(idx.size[i])
                return fmt_time(idx.mtime[i], '%Y-%m-%d %H:%M')
            if role == Qt.DecorationRole and col == 0 and not dead:
                return self.icons.get(idx.names[i], idx.kind[i] == KIND_DIR, lambda: idx.fullpath(i))
            if role == Qt.TextAlignmentRole and col == 2:
                return qflag(Qt.AlignRight | Qt.AlignVCenter)
            if role == Qt.ToolTipRole and col in (0, 1) and not dead:
                return disp(idx.fullpath(i) or '')
            return None

        def flags(self, mi):
            f = QAbstractTableModel.flags(self, mi)
            if mi.isValid():
                f |= Qt.ItemIsDragEnabled
            return f

        def mimeTypes(self):
            return ['text/uri-list', 'text/plain']

        def mimeData(self, indexes):
            rows = sorted(set(m.row() for m in indexes))
            with self.index_.lock:
                paths = [self.index_.fullpath(i) for i in (self.entry(r) for r in rows)
                         if i >= 0 and self.index_.kind[i] != KIND_DEAD]
            return make_file_mime([p for p in paths if p])

        def supportedDragActions(self):
            return Qt.CopyAction | Qt.MoveAction | Qt.LinkAction

        def sort(self, column, order=Qt.AscendingOrder):
            if self.sorter is not None:
                self.sorter(column, order == Qt.DescendingOrder)

    def file_url(p):
        """按原始字节百分号编码的 file:// URL：非 UTF-8 文件名也能被文件管理器准确定位。"""
        if IS_WIN:
            return QUrl.fromLocalFile(disp(p))   # Windows 文件名是 UTF-16，无字节名问题
        if disp(p) == p:
            return QUrl.fromLocalFile(p)
        from urllib.parse import quote
        return QUrl.fromEncoded(QByteArray(b'file://' + quote(os.fsencode(p)).encode('ascii')))

    def make_file_mime(paths):
        md = QMimeData()
        urls = [file_url(p) for p in paths]
        md.setUrls(urls)
        md.setText('\n'.join(disp(p) for p in paths))
        if IS_WIN:
            return md   # Windows：Qt 把 URL 列表放成 CF_HDROP，资源管理器可直接粘贴
        gnome = ('copy\n' + '\n'.join(u.toString(QUrl.FullyEncoded) for u in urls)).encode('utf-8')
        md.setData('x-special/gnome-copied-files', QByteArray(gnome))
        md.setData('x-special/mate-copied-files', QByteArray(gnome))
        return md

    class HighlightDelegate(QStyledItemDelegate):
        """名称列高亮匹配片段（Everything 风格加粗）。"""

        def __init__(self, parent=None):
            QStyledItemDelegate.__init__(self, parent)
            self.terms = []

        def paint(self, painter, option, mi):
            if mi.column() != 0 or not self.terms:
                return QStyledItemDelegate.paint(self, painter, option, mi)
            opt = option.__class__(option)
            self.initStyleOption(opt, mi)
            text = opt.text
            opt.text = ''
            w = opt.widget
            style = w.style() if w else QApplication.style()
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, w)
            rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, w)
            low = text.lower()
            if len(low) != len(text):
                low = text
            mark = bytearray(len(text))
            for t in self.terms:
                if not t:
                    continue
                s = 0
                while True:
                    k = low.find(t, s)
                    if k < 0:
                        break
                    mark[k:k + len(t)] = b'\x01' * len(t)
                    s = k + 1
            painter.save()
            sel = opt.state & QStyle.State_Selected
            painter.setPen(opt.palette.color(QPalette.HighlightedText if sel else QPalette.Text))
            normal = QFont(opt.font)
            bold = QFont(opt.font)
            bold.setBold(True)
            x = rect.left() + 3
            right = rect.right() - 2
            j = 0
            n = len(text)
            painter.setClipRect(rect)
            while j < n and x < right:
                b = mark[j]
                e = j
                while e < n and mark[e] == b:
                    e += 1
                seg = text[j:e]
                f = bold if b else normal
                fm = QFontMetrics(f)
                adv = fm.horizontalAdvance(seg) if hasattr(fm, 'horizontalAdvance') else fm.width(seg)
                if x + adv > right:
                    seg = fm.elidedText(seg, Qt.ElideRight, right - x)
                painter.setFont(f)
                painter.drawText(QRect(x, rect.top(), right - x + 1, rect.height()),
                                 qflag(Qt.AlignVCenter | Qt.AlignLeft), seg)
                x += adv
                j = e
            painter.restore()

    class ResultView(QTreeView):
        def __init__(self, win):
            QTreeView.__init__(self)
            self.win = win
            self.setRootIsDecorated(False)
            self.setUniformRowHeights(True)
            self.setAlternatingRowColors(True)
            self.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.setDragEnabled(True)
            self.setDragDropMode(QAbstractItemView.DragOnly)
            self.setAllColumnsShowFocus(True)
            self.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.setContextMenuPolicy(Qt.CustomContextMenu)
            self.setIconSize(QSize(18, 18))

        def keyPressEvent(self, ev):
            k = ev.key()
            mod = ev.modifiers()
            if k in (Qt.Key_Return, Qt.Key_Enter):
                if mod & Qt.ControlModifier:
                    self.win.act_open_folder()
                else:
                    self.win.act_open()
                return
            if k == Qt.Key_Escape:
                self.win.search.setFocus()
                self.win.search.selectAll()
                return
            if k == Qt.Key_Up and self.currentIndex().row() <= 0 and not (mod & Qt.ShiftModifier):
                self.win.search.setFocus()
                return
            QTreeView.keyPressEvent(self, ev)

    class SearchEdit(QLineEdit):
        def __init__(self, win):
            QLineEdit.__init__(self)
            self.win = win

        def keyPressEvent(self, ev):
            k = ev.key()
            if k in (Qt.Key_Down, Qt.Key_PageDown):
                self.win.focus_results()
                return
            if k in (Qt.Key_Return, Qt.Key_Enter):
                self.win.flush_search()
                if ev.modifiers() & Qt.ControlModifier:
                    self.win.focus_results()
                    self.win.act_open_folder()
                else:
                    self.win.focus_results()
                    self.win.act_open()
                return
            if k == Qt.Key_Escape:
                if self.text():
                    self.clear()
                else:
                    self.win.esc_hide()
                return
            QLineEdit.keyPressEvent(self, ev)

    HELP_HTML = """
<h3>千寻 搜索语法（与 Everything 一致）</h3>
<table cellpadding="4" border="1" cellspacing="0">
<tr><th>写法</th><th>含义</th><th>示例</th></tr>
<tr><td>空格</td><td>与（同时包含）</td><td>报告 2026</td></tr>
<tr><td>|</td><td>或</td><td>docx|wps</td></tr>
<tr><td>!</td><td>非（排除）</td><td>报告 !草稿</td></tr>
<tr><td>* ?</td><td>通配符（匹配整个文件名）</td><td>*.pdf　报告??.docx</td></tr>
<tr><td>"…"</td><td>含空格的短语</td><td>"会议 纪要"</td></tr>
<tr><td>含 / 的词、path:</td><td>按完整路径匹配</td><td>home/文档 方案　path:项目</td></tr>
<tr><td>ext:</td><td>扩展名（分号分隔）</td><td>ext:pdf;ofd</td></tr>
<tr><td>file: folder:</td><td>只要文件／只要文件夹</td><td>folder:项目</td></tr>
<tr><td>regex:</td><td>正则表达式</td><td>regex:^IMG_\\d{4}</td></tr>
<tr><td>size:</td><td>大小</td><td>size:&gt;100mb　size:1mb..10mb　size:large</td></tr>
<tr><td>dm:</td><td>修改日期</td><td>dm:today　dm:yesterday　dm:thisweek　dm:last7days　dm:2026-10</td></tr>
</table>
<p>大小别名：empty、tiny(&lt;10KB)、small、medium、large(1–16MB)、huge(16–128MB)、gigantic(&gt;128MB)</p>
<h3>快捷键</h3>
<table cellpadding="4" border="1" cellspacing="0">
<tr><td>Enter</td><td>打开</td><td>Ctrl+Enter</td><td>打开所在文件夹</td></tr>
<tr><td>Ctrl+C</td><td>复制文件（可直接粘贴到文件管理器）</td><td>Ctrl+Shift+C</td><td>复制完整路径</td></tr>
<tr><td>F2</td><td>重命名</td><td>Delete</td><td>移到回收站</td></tr>
<tr><td>Ctrl+I</td><td>区分大小写</td><td>Ctrl+B</td><td>全字匹配</td></tr>
<tr><td>Ctrl+U</td><td>匹配路径</td><td>Ctrl+R</td><td>正则表达式</td></tr>
<tr><td>Ctrl+F</td><td>回到搜索框</td><td>Esc</td><td>清空搜索／隐藏窗口</td></tr>
</table>
<p>全局唤出：在麒麟“设置 → 设备 → 快捷键 → 添加自定义快捷键”中，命令填写
<code>qianxun --toggle</code>（或安装目录下 <code>qianxun.sh --toggle</code>），例如绑定 Alt+空格。</p>
"""
    if IS_WIN:
        HELP_HTML = HELP_HTML.replace(
            '<tr><td>含 / 的词、path:</td><td>按完整路径匹配</td><td>home/文档 方案　path:项目</td></tr>',
            '<tr><td>含 \\ 或 / 的词、path:</td><td>按完整路径匹配（/ 等同 \\）</td>'
            '<td>Users\\文档 方案　d:/项目 报告　path:项目</td></tr>')
        HELP_HTML = HELP_HTML[:HELP_HTML.index('<p>全局唤出')] + (
            '<p>全局唤出：默认 <b>Ctrl+Alt+F</b>（在“工具 → 选项”中可修改或关闭）；'
            '也可运行 <code>QianXun.exe --toggle</code>。</p>'
            '<p>实时监控：每个磁盘一个 ReadDirectoryChangesW 监视，新建、改名、删除约 1 秒内反映到结果中。</p>')

    class OptionsDialog(QDialog):
        def __init__(self, win, cfg):
            QDialog.__init__(self, win)
            self.setWindowTitle('选项')
            self.resize(560, 560)
            self.cfg = dict(cfg)
            lay = QVBoxLayout(self)

            def list_box(title, items, pick_dir=True):
                box = QGroupBox(title)
                g = QGridLayout(box)
                lw = QListWidget()
                lw.addItems(items)
                g.addWidget(lw, 0, 0, 3, 1)
                b1 = QPushButton('添加…')
                b2 = QPushButton('删除')
                g.addWidget(b1, 0, 1)
                g.addWidget(b2, 1, 1)

                def add():
                    d = QFileDialog.getExistingDirectory(self, '选择目录', '' if IS_WIN else '/')
                    if d and IS_WIN:
                        d = win_norm_path(d)
                    if d and not lw.findItems(d, Qt.MatchExactly):
                        lw.addItem(d)

                def rm():
                    for it in lw.selectedItems():
                        lw.takeItem(lw.row(it))
                b1.clicked.connect(add)
                b2.clicked.connect(rm)
                lay.addWidget(box)
                return lw

            self.roots = list_box('索引范围（留空＝所有本地磁盘）' if IS_WIN else '索引范围（默认整个文件系统 /）',
                                  cfg['roots'])
            self.excl = list_box('排除目录（回收站、System Volume Information、WinSxS 已内置排除）' if IS_WIN
                                 else '排除目录', cfg['excludes'])
            self.cb_rm = QCheckBox('索引 U 盘、移动硬盘等可移动磁盘')
            self.cb_rm.setChecked(cfg['index_removable'])
            self.cb_net = QCheckBox('索引网络文件系统（NFS／SMB 等，可能较慢）')
            self.cb_net.setChecked(cfg['index_network'])
            self.cb_tray = QCheckBox('关闭窗口时最小化到托盘（保持实时索引）')
            self.cb_tray.setChecked(cfg['close_to_tray'])
            for c in (self.cb_rm, self.cb_net, self.cb_tray):
                lay.addWidget(c)
            st = win.engine.status
            if IS_WIN:
                self.cb_auto = QCheckBox('登录 Windows 时自动启动（后台托盘）')
                self.cb_auto.setChecked(bool(win_autostart_get()))
                lay.addWidget(self.cb_auto)
                row = QHBoxLayout()
                self.cb_hk = QCheckBox('全局快捷键（唤出／隐藏）：')
                hk = cfg.get('hotkey', '')
                self.cb_hk.setChecked(bool(hk))
                self.ed_hk = _QtWidgets.QKeySequenceEdit(QKeySequence(hk or 'Ctrl+Alt+F'))
                row.addWidget(self.cb_hk)
                row.addWidget(self.ed_hk, 1)
                lay.addLayout(row)
                info = QLabel('实时监控：每个磁盘一个 ReadDirectoryChangesW 监视，已覆盖 {:,} / {:,} 个目录。'.format(
                    st.get('watched', 0), st.get('dirs', 0)))
            else:
                lim = inotify_limit()
                info = QLabel('实时监控：已覆盖 {:,} / {:,} 个目录；系统 inotify 上限 {:,}。'
                              '超出部分每 {} 分钟轮询一次。'.format(
                                  st.get('watched', 0), st.get('dirs', 0), lim, Engine.POLL_INTERVAL // 60))
            info.setWordWrap(True)
            lay.addWidget(info)
            bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            bb.button(QDialogButtonBox.Ok).setText('确定')
            bb.button(QDialogButtonBox.Cancel).setText('取消')
            bb.accepted.connect(self.accept)
            bb.rejected.connect(self.reject)
            lay.addWidget(bb)

        def result_cfg(self):
            c = dict(self.cfg)
            c['roots'] = [self.roots.item(i).text() for i in range(self.roots.count())] or ([] if IS_WIN else ['/'])
            c['excludes'] = [self.excl.item(i).text() for i in range(self.excl.count())]
            c['index_removable'] = self.cb_rm.isChecked()
            c['index_network'] = self.cb_net.isChecked()
            c['close_to_tray'] = self.cb_tray.isChecked()
            if IS_WIN:
                ks = self.ed_hk.keySequence().toString(QKeySequence.PortableText)
                c['hotkey'] = ks if self.cb_hk.isChecked() else ''
            return c

        def autostart(self):
            return IS_WIN and self.cb_auto.isChecked()

    class MainWindow(QMainWindow):
        def __init__(self, cfg, index, engine, app_icon):
            QMainWindow.__init__(self)
            self.cfg = cfg
            self.index = index
            self.engine = engine
            self.searcher = Searcher(index)
            self.quitting = False
            self.hotkey = None
            self.setWindowTitle('%s - 文件秒搜' % APP_NAME)
            self.setWindowIcon(app_icon)
            self.resize(1100, 680)

            central = QWidget()
            v = QVBoxLayout(central)
            v.setContentsMargins(6, 6, 6, 0)
            v.setSpacing(6)
            top = QHBoxLayout()
            self.search = SearchEdit(self)
            self.search.setPlaceholderText('输入文件名即搜　空格=与　|=或　!=非　*.pdf　ext:docx　size:>10mb　dm:today　（F1 查看语法）')
            self.search.setClearButtonEnabled(True)
            f = self.search.font()
            f.setPointSizeF(f.pointSizeF() * 1.15)
            self.search.setFont(f)
            self.search.setMinimumHeight(32)
            top.addWidget(self.search, 1)
            self.filter = QComboBox()
            for name, _ in FILTERS:
                self.filter.addItem(name)
            self.filter.setCurrentIndex(min(max(0, int(cfg.get('filter', 0))), len(FILTERS) - 1))
            self.filter.setMinimumHeight(32)
            top.addWidget(self.filter)
            v.addLayout(top)

            self.model = ResultModel(index, self)
            self.model.sorter = self.sort_results
            self.view = ResultView(self)
            self.view.setModel(self.model)
            self.delegate = HighlightDelegate(self.view)
            self.view.setItemDelegateForColumn(0, self.delegate)
            hdr = self.view.header()
            hdr.setStretchLastSection(True)
            hdr.resizeSection(0, 330)
            hdr.resizeSection(1, 460)
            hdr.resizeSection(2, 90)
            hdr.resizeSection(3, 140)
            hdr.setSectionsMovable(True)
            if cfg.get('header'):
                try:
                    hdr.restoreState(QByteArray.fromBase64(cfg['header'].encode('ascii')))
                except Exception:
                    pass
            self.sort_col = int(cfg.get('sort_col', 0)) % 4
            self.sort_desc = bool(cfg.get('sort_desc', False))
            hdr.setSortIndicator(self.sort_col, Qt.DescendingOrder if self.sort_desc else Qt.AscendingOrder)
            hdr.setSortIndicatorShown(True)
            hdr.setSectionsClickable(True)
            hdr.sortIndicatorChanged.connect(self.on_sort_changed)
            v.addWidget(self.view, 1)
            self.setCentralWidget(central)

            self.lbl_count = QLabel()
            self.lbl_state = QLabel()
            self.statusBar().addWidget(self.lbl_count, 1)
            self.statusBar().addPermanentWidget(self.lbl_state)

            self._build_menu()
            self._build_tray(app_icon)

            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.setInterval(70)
            self.timer.timeout.connect(self.do_search)
            self.search.textChanged.connect(lambda _t: self.timer.start())
            self.filter.currentIndexChanged.connect(lambda _i: self.do_search())
            self.view.doubleClicked.connect(lambda _m: self.act_open())
            self.view.customContextMenuRequested.connect(self.context_menu)
            self.view.selectionModel().selectionChanged.connect(lambda *a: self.update_count())

            self.poll = QTimer(self)
            self.poll.setInterval(200)
            self.poll.timeout.connect(self.on_poll)
            self.poll.start()
            self.last_version = -1
            self.last_struct = -1
            self.stat_query = False
            self.last_search = 0.0
            self.rows_unsorted = False

            if cfg.get('geometry'):
                try:
                    self.restoreGeometry(QByteArray.fromBase64(cfg['geometry'].encode('ascii')))
                except Exception:
                    pass
            self.do_search()

        # ---- 菜单 ----
        def _act(self, menu, text, slot, key=None, checkable=False, checked=False):
            a = QAction(text, self)
            if key:
                a.setShortcut(QKeySequence(key))
                a.setShortcutContext(Qt.WindowShortcut)
            if checkable:
                a.setCheckable(True)
                a.setChecked(checked)
                a.toggled.connect(slot)
            else:
                a.triggered.connect(lambda _c=False: slot())
            menu.addAction(a)
            return a

        def _build_menu(self):
            mb = self.menuBar()
            m = mb.addMenu('文件(&F)')
            self._act(m, '导出搜索结果为 CSV…', self.export_csv, 'Ctrl+S')
            m.addSeparator()
            self._act(m, '退出', self.quit_app, 'Ctrl+Q')
            m = mb.addMenu('搜索(&S)')
            self.a_case = self._act(m, '区分大小写', lambda c: self.set_opt('case', c), 'Ctrl+I', True, self.cfg['case'])
            self.a_whole = self._act(m, '全字匹配', lambda c: self.set_opt('whole_word', c), 'Ctrl+B', True, self.cfg['whole_word'])
            self.a_path = self._act(m, '匹配路径', lambda c: self.set_opt('match_path', c), 'Ctrl+U', True, self.cfg['match_path'])
            self.a_regex = self._act(m, '正则表达式', lambda c: self.set_opt('regex', c), 'Ctrl+R', True, self.cfg['regex'])
            m.addSeparator()
            self._act(m, '回到搜索框', self.focus_search, 'Ctrl+F')
            m = mb.addMenu('工具(&T)')
            self._act(m, '选项…', self.open_options, 'Ctrl+P')
            self._act(m, '立即刷新索引', lambda: self.engine.post('refresh_all'), 'F5')
            self._act(m, '重建索引', self.rebuild)
            if IS_WIN:
                self._act(m, '创建桌面快捷方式', self.make_desktop_shortcut)
            else:
                self._act(m, '提升实时监控上限（需管理员密码）…', self.raise_limit)
            m.addSeparator()
            self._act(m, '打开日志目录', lambda: open_path(CACHE_DIR))
            m = mb.addMenu('帮助(&H)')
            self._act(m, '搜索语法与快捷键', self.show_help, 'F1')
            self._act(m, '关于千寻', self.show_about)

            # 结果区快捷键
            for key, slot in (('Ctrl+C', self.act_copy), ('Ctrl+Shift+C', self.act_copy_path),
                              ('F2', self.act_rename), ('Delete', self.act_trash),
                              ('Alt+Return', self.act_props)):
                sc = QShortcut(QKeySequence(key), self.view)
                sc.setContext(Qt.WidgetShortcut)
                sc.activated.connect(slot)

        def _build_tray(self, icon):
            self.tray = None
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip('%s - 文件秒搜' % APP_NAME)
            m = QMenu()
            a = m.addAction('显示主窗口')
            a.triggered.connect(self.show_raise)
            a = m.addAction('退出')
            a.triggered.connect(self.quit_app)
            self.tray.setContextMenu(m)
            self.tray.activated.connect(self.on_tray)
            self.tray.show()

        def on_tray(self, reason):
            if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
                if self.isVisible() and self.isActiveWindow():
                    self.hide()
                else:
                    self.show_raise()

        # ---- 窗口行为 ----
        def show_raise(self):
            if self.isMinimized():
                self.showNormal()
            self.show()
            self.raise_()
            self.activateWindow()
            self.search.setFocus()
            self.search.selectAll()

        def toggle(self):
            if self.isVisible() and self.isActiveWindow():
                self.hide()
            else:
                self.show_raise()

        def esc_hide(self):
            if self.tray is not None and self.cfg.get('close_to_tray'):
                self.hide()

        def closeEvent(self, ev):
            if not self.quitting and self.tray is not None and self.cfg.get('close_to_tray'):
                ev.ignore()
                self.hide()
                return
            self.quit_app()
            ev.accept()

        def save_state(self):
            self.cfg['geometry'] = qbytes(self.saveGeometry().toBase64()).decode('ascii')
            self.cfg['header'] = qbytes(self.view.header().saveState().toBase64()).decode('ascii')
            self.cfg['sort_col'] = self.sort_col
            self.cfg['sort_desc'] = self.sort_desc
            self.cfg['filter'] = self.filter.currentIndex()
            save_config(self.cfg)

        def quit_app(self):
            if self.quitting:
                return
            self.quitting = True
            self.save_state()
            self.hide()
            if self.tray is not None:
                self.tray.hide()
            self.engine.post('quit')
            self.engine.join(15)
            QApplication.instance().quit()

        def focus_search(self):
            self.search.setFocus()
            self.search.selectAll()

        def focus_results(self):
            self.view.setFocus()
            if self.model.rowCount() and not self.view.currentIndex().isValid():
                self.view.setCurrentIndex(self.model.index(0, 0))

        def set_opt(self, key, val):
            self.cfg[key] = bool(val)
            save_config(self.cfg)
            self.do_search()

        # ---- 搜索 ----
        def flush_search(self):
            if self.timer.isActive():
                self.timer.stop()
                self.do_search()

        def build_query(self):
            extra = FILTERS[self.filter.currentIndex()][1]
            q = Query(self.search.text(), case=self.cfg['case'], whole=self.cfg['whole_word'],
                      match_path=self.cfg['match_path'], regex=self.cfg['regex'], extra=extra)
            return q, extra

        def do_search(self, keep_view=False):
            q, extra = self.build_query()
            self.searcher.case = self.cfg['case']
            t0 = time.time()
            busy = False
            with self.index.lock:
                ver = self.index.version
                sver = self.index.struct_version
                gen = self.index.gen
                res = self.searcher.run(q, extra)
                if len(res) > 300000 or self.sort_col in (1, 2, 3) and len(res) > 50000:
                    busy = True
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                try:
                    res = self._sorted(res)
                finally:
                    if busy:
                        QApplication.restoreOverrideCursor()
            self.last_version = ver
            self.last_struct = sver
            # 结果是否依赖大小/时间（size:、dm: 或按大小/时间排序）
            self.stat_query = self.sort_col in (2, 3) or any(
                p.kind in ('size', 'dm') for _n, alts in q.groups for p in alts)
            self.last_search = time.time()
            self.delegate.terms = q.highlights if not q.regex else []
            sel_entry = -1
            scroll = 0
            if keep_view:
                cur = self.view.currentIndex()
                sel_entry = self.model.entry(cur.row()) if cur.isValid() else -1
                scroll = self.view.verticalScrollBar().value()
            self.model.set_rows(res, gen)
            self.view.viewport().update()
            if keep_view:
                self.view.verticalScrollBar().setValue(scroll)
                if sel_entry >= 0:
                    try:
                        r = res.index(sel_entry) if len(res) < 200000 else -1
                    except ValueError:
                        r = -1
                    if r >= 0:
                        self.view.setCurrentIndex(self.model.index(r, 0))
            else:
                self.view.scrollToTop()
            self.search_ms = (time.time() - t0) * 1000
            if q.error:
                self.lbl_count.setText('语法错误：%s' % q.error)
            else:
                self.update_count()

        def update_count(self):
            n = self.model.rowCount()
            s = '{:,} 个对象'.format(n)
            sel = len(self.view.selectionModel().selectedRows()) if n else 0
            if sel > 1:
                s += '　｜　已选中 {:,} 个'.format(sel)
            if self.rows_unsorted:
                s += '　｜　索引建立中，结果暂未排序'
            self.lbl_count.setText(s)

        def _sorted(self, res):
            idx = self.index
            col, desc = self.sort_col, self.sort_desc
            if col in (0, 1):
                idx.ensure_lnames()
            self.rows_unsorted = False
            if col == 0:
                ln = idx.lnames
                no = idx.name_order
                if len(res) > 120000 and no is not None:
                    order, n0 = no
                    mask = bytearray(len(ln))
                    for i in res:
                        mask[i] = 1
                    out = [i for i in order if i < len(mask) and mask[i]]
                    extra = [i for i in res if i >= n0]
                    if extra:
                        extra.sort(key=ln.__getitem__)
                        out = list(heapq.merge(out, extra, key=ln.__getitem__))
                    res = out
                elif len(res) > 400000:
                    self.rows_unsorted = True
                else:
                    res.sort(key=ln.__getitem__)
            elif col == 1:
                # 两趟稳定排序（先名称、再目录序号），等价于按 (目录, 名称) 排序，但避免百万个元组键
                dp = idx.dir_prefixes(True)
                par, ln = idx.parent, idx.lnames
                key = (idx.dirs_version, 'drank')
                drank = getattr(self, '_drank', None)
                if drank is None or drank[0] != key:
                    rank = array('i', [0]) * len(dp)
                    for r, d in enumerate(sorted(range(len(dp)), key=dp.__getitem__)):
                        rank[d] = r
                    drank = self._drank = (key, rank)
                rank = drank[1]
                res.sort(key=ln.__getitem__)
                res.sort(key=lambda i: rank[par[i]])
            else:
                self.searcher.ensure_stats(res)
                arr = idx.size if col == 2 else idx.mtime
                res.sort(key=arr.__getitem__)
            if desc:
                res.reverse()
            return res

        def on_sort_changed(self, col, order):
            self.sort_col = col
            self.sort_desc = order == Qt.DescendingOrder
            self.do_search(keep_view=False)

        def sort_results(self, col, desc):
            pass   # 排序由 sortIndicatorChanged 统一处理

        def on_poll(self):
            st = self.engine.status
            state = st.get('state')
            idx = self.index
            if state == 'ready':
                w, d = st.get('watched', 0), st.get('dirs', 0)
                if not st.get('inotify', True):
                    mon = '实时监控不可用，每 3 分钟轮询'
                elif d and w < d:
                    mon = '实时监控 {:,}/{:,} 目录，其余定时轮询'.format(w, d)
                else:
                    mon = '实时监控已全覆盖'
                text = '索引就绪：{:,} 个文件和目录　｜　{}'.format(idx.live, mon)
                if st.get('msg'):
                    text = st['msg'] + '　｜　' + text
            else:
                text = st.get('msg') or '…'
            if self.lbl_state.text() != text:
                self.lbl_state.setText(text)
            if not self.isVisible():
                return
            if idx.gen != self.model.gen:
                # 索引整体被替换（重建/加载），旧结果行已作废，立即重搜
                if not self.timer.isActive():
                    self.do_search(keep_view=False)
            elif idx.version != self.last_version and idx.struct_version == self.last_struct \
                    and not self.stat_query:
                # 只有大小/时间变化（如日志文件不断追加）：结果集合与顺序不变，重绘即可，不必反复重搜
                self.last_version = idx.version
                self.view.viewport().update()
            elif idx.version != self.last_version:
                gap = 4.0 if state in ('indexing', 'loading') else (0.25 if len(self.model.rows) < 200000 else 1.5)
                if time.time() - self.last_search >= gap and not self.timer.isActive():
                    self.do_search(keep_view=True)

        # ---- 选中项与操作 ----
        def selected_entries(self):
            rows = sorted(set(m.row() for m in self.view.selectionModel().selectedRows()))
            if not rows and self.view.currentIndex().isValid():
                rows = [self.view.currentIndex().row()]
            out = []
            with self.index.lock:
                for r in rows:
                    i = self.model.entry(r)
                    if i >= 0 and self.index.kind[i] != KIND_DEAD:
                        out.append(i)
            return out

        def selected_paths(self):
            with self.index.lock:
                return [p for p in (self.index.fullpath(i) for i in self.selected_entries()) if p]

        def act_open(self):
            paths = self.selected_paths()
            if len(paths) > 10:
                if QMessageBox.question(self, APP_NAME, '确定同时打开 %d 个项目吗？' % len(paths)) != QMessageBox.Yes:
                    return
            for p in paths:
                open_path(p)

        def act_open_folder(self):
            for p in self.selected_paths()[:10]:
                show_in_folder(p)

        def act_terminal(self):
            ps = self.selected_paths()
            if not ps:
                return
            p = ps[0]
            d = p if os.path.isdir(p) else os.path.dirname(p)
            if IS_WIN:
                for argv, flags in win_terminal_commands(d):
                    try:
                        subprocess.Popen(argv, cwd=d, creationflags=flags)
                        return
                    except OSError:
                        continue
                QMessageBox.information(self, APP_NAME, '未能打开终端。')
                return
            for t in ('mate-terminal', 'ukui-terminal', 'kylin-terminal', 'deepin-terminal',
                      'gnome-terminal', 'konsole', 'xfce4-terminal', 'qterminal', 'x-terminal-emulator', 'xterm'):
                exe = shutil.which(t)
                if exe:
                    subprocess.Popen([exe], cwd=d, start_new_session=True)
                    return
            QMessageBox.information(self, APP_NAME, '未找到终端程序。')

        def act_copy(self):
            ps = self.selected_paths()
            if ps:
                QApplication.clipboard().setMimeData(make_file_mime(ps))
                self.statusBar().showMessage('已复制 %d 个项目，可在文件管理器中粘贴' % len(ps), 3000)

        def act_copy_path(self):
            ps = self.selected_paths()
            if ps:
                QApplication.clipboard().setText('\n'.join(disp(p) for p in ps))
                self.statusBar().showMessage('已复制路径', 2000)

        def act_copy_name(self):
            ps = self.selected_paths()
            if ps:
                QApplication.clipboard().setText('\n'.join(disp(os.path.basename(p)) for p in ps))

        def act_copy_dir(self):
            ps = self.selected_paths()
            if ps:
                QApplication.clipboard().setText('\n'.join(disp(os.path.dirname(p)) for p in ps))

        def act_rename(self):
            ents = self.selected_entries()
            if len(ents) != 1:
                return
            i = ents[0]
            with self.index.lock:
                old = self.index.fullpath(i)
                name = self.index.names[i]
            if not old:
                return
            new, ok = QInputDialog.getText(self, '重命名', '新名称：', QLineEdit.Normal, disp(name))
            if not ok or not new or new == name or new == disp(name):
                # 非 UTF-8 文件名在对话框里显示为 U+FFFD；未改动时直接返回，避免把原字节名改坏
                return
            if new in ('.', '..'):
                QMessageBox.warning(self, APP_NAME, '名称无效。')
                return
            if IS_WIN and re.search(r'[\\/:*?"<>|\x00-\x1f]', new):
                QMessageBox.warning(self, APP_NAME, '名称中不能包含下列字符：\\ / : * ? " < > |')
                return
            if IS_WIN and new.rstrip(' .') != new:
                QMessageBox.warning(self, APP_NAME, '名称不能以空格或句点结尾。')
                return
            if '/' in new:
                QMessageBox.warning(self, APP_NAME, '名称中不能包含“/”。')
                return
            dst = join_path(os.path.dirname(old), new)
            try:
                # FAT/exFAT 不区分大小写：只改大小写时 dst 与原文件是同一项，应允许
                same = os.path.samestat(os.lstat(old), os.lstat(dst))
            except OSError:
                same = False
            if os.path.lexists(dst) and not same:
                QMessageBox.warning(self, APP_NAME, '同名项目已存在。')
                return
            try:
                os.rename(old, dst)
            except OSError as e:
                QMessageBox.warning(self, APP_NAME, '重命名失败：%s' % e.strerror)
                return
            self.engine.post('refresh_path', os.path.dirname(old))

        def act_trash(self):
            ps = self.selected_paths()
            if not ps:
                return
            msg = ('确定将“%s”移到回收站吗？' % disp(os.path.basename(ps[0]))) if len(ps) == 1 \
                else '确定将这 %d 个项目移到回收站吗？' % len(ps)
            if IS_WIN:
                bad = [p for p in ps if win_drive_type(p) not in (DRIVE_FIXED,)]
                if bad:
                    # 可移动盘、网络盘没有回收站，Shell 会直接永久删除——不替用户做这个决定
                    QMessageBox.warning(self, APP_NAME, '以下项目位于可移动磁盘或网络位置，不支持回收站，'
                                        '请在资源管理器中处理：\n' + '\n'.join(disp(p) for p in bad[:10]))
                    return
            if QMessageBox.question(self, APP_NAME, msg) != QMessageBox.Yes:
                return
            failed = []
            for p in ps:
                if not move_to_trash(p):
                    failed.append(p)
                self.engine.post('refresh_path', os.path.dirname(p))
            if failed:
                QMessageBox.warning(self, APP_NAME, '以下项目未能移到回收站：\n' + '\n'.join(disp(p) for p in failed[:10]))

        def act_props(self):
            ps = self.selected_paths()
            if not ps:
                return
            p = ps[0]
            if IS_WIN:
                try:
                    if win_show_properties(p, int(self.winId())):
                        return
                except Exception as e:
                    log('properties: %s' % e)
            try:
                st = os.lstat(p)
            except OSError as e:
                QMessageBox.warning(self, APP_NAME, str(e))
                return
            import stat as _st
            fmt = lambda t: fmt_time(t, '%Y-%m-%d %H:%M:%S')
            if IS_WIN:
                attrs = getattr(st, 'st_file_attributes', 0)
                flags = '　'.join(n for b, n in ((0x1, '只读'), (0x2, '隐藏'), (0x4, '系统'), (0x20, '存档'),
                                                 (0x400, '重解析点'), (0x800, '压缩'), (0x4000, '加密'))
                                 if attrs & b) or '无'
                lines = [
                    '名称：%s' % disp(os.path.basename(p)),
                    '位置：%s' % disp(os.path.dirname(p)),
                    '类型：%s' % ('文件夹' if _st.S_ISDIR(st.st_mode) else '文件'),
                    '大小：%s（%s 字节）' % (human_size(st.st_size), '{:,}'.format(st.st_size)),
                    '修改时间：%s' % fmt(st.st_mtime),
                    '访问时间：%s' % fmt(st.st_atime),
                    '创建时间：%s' % fmt(st.st_ctime),
                    '属性：%s' % flags,
                ]
                QMessageBox.information(self, '属性', '\n'.join(lines))
                return
            import pwd
            import grp
            try:
                owner = pwd.getpwuid(st.st_uid).pw_name
            except KeyError:
                owner = str(st.st_uid)
            try:
                group = grp.getgrgid(st.st_gid).gr_name
            except KeyError:
                group = str(st.st_gid)
            lines = [
                '名称：%s' % disp(os.path.basename(p)),
                '位置：%s' % disp(os.path.dirname(p)),
                '类型：%s' % ('文件夹' if _st.S_ISDIR(st.st_mode) else '符号链接' if _st.S_ISLNK(st.st_mode) else '文件'),
                '大小：%s（%s 字节）' % (human_size(st.st_size), '{:,}'.format(st.st_size)),
                '修改时间：%s' % fmt(st.st_mtime),
                '访问时间：%s' % fmt(st.st_atime),
                '状态改变：%s' % fmt(st.st_ctime),
                '权限：%s　所有者：%s　组：%s' % (_st.filemode(st.st_mode), owner, group),
            ]
            QMessageBox.information(self, '属性', '\n'.join(lines))

        def context_menu(self, pos):
            if not self.selected_entries():
                return
            m = QMenu(self)
            m.addAction('打开', self.act_open)
            m.addAction('打开所在文件夹', self.act_open_folder)
            m.addAction('在终端中打开', self.act_terminal)
            m.addSeparator()
            m.addAction('复制　Ctrl+C', self.act_copy)
            m.addAction('复制完整路径　Ctrl+Shift+C', self.act_copy_path)
            m.addAction('复制文件名', self.act_copy_name)
            m.addAction('复制所在目录路径', self.act_copy_dir)
            m.addSeparator()
            m.addAction('重命名　F2', self.act_rename)
            m.addAction('移到回收站　Delete', self.act_trash)
            m.addSeparator()
            m.addAction('属性', self.act_props)
            m.exec_(self.view.viewport().mapToGlobal(pos)) if hasattr(m, 'exec_') else m.exec(self.view.viewport().mapToGlobal(pos))

        # ---- 工具 ----
        def export_csv(self):
            fn, _ = QFileDialog.getSaveFileName(self, '导出搜索结果', os.path.join(HOME, '千寻搜索结果.csv'),
                                                'CSV 文件 (*.csv)')
            if not fn:
                return
            idx = self.index
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                # 先在锁内取快照（引擎线程可能正在追加/清空数组），再写文件
                with idx.lock:
                    rows = [i for i in (self.model.entry(r) for r in range(len(self.model.rows)))
                            if i >= 0 and idx.kind[i] != KIND_DEAD]
                    self.searcher.ensure_stats(rows)
                    snap = [(idx.names[i], idx.dirpath(i) or '', idx.kind[i], idx.size[i], idx.mtime[i])
                            for i in rows]
                with open(fn, 'w', encoding='utf-8-sig', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['名称', '路径', '大小（字节）', '修改时间'])
                    for name, d, k, sz, m in snap:
                        w.writerow([disp(name), disp(d), '' if k == KIND_DIR else sz, fmt_time(m, '%Y-%m-%d %H:%M:%S')])
            except OSError as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, APP_NAME, '导出失败：%s' % e)
                return
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage('已导出 {:,} 条到 {}'.format(len(rows), fn), 5000)

        def open_options(self):
            dlg = OptionsDialog(self, self.cfg)
            if qexec(dlg) != QDialog.Accepted:
                return
            new = dlg.result_cfg()
            changed = any(new[k] != self.cfg[k] for k in ('roots', 'excludes', 'index_removable', 'index_network'))
            hk_changed = IS_WIN and new.get('hotkey') != self.cfg.get('hotkey')
            self.cfg.update(new)
            save_config(self.cfg)
            if IS_WIN:
                try:
                    if dlg.autostart() != bool(win_autostart_get()):
                        win_autostart_set(dlg.autostart())
                except OSError as e:
                    QMessageBox.warning(self, APP_NAME, '设置开机自启失败：%s' % e)
                if hk_changed and self.hotkey is not None:
                    self.hotkey.register(self.cfg.get('hotkey', ''))
            if changed:
                self.engine.post('rebuild', dict(self.cfg))

        def make_desktop_shortcut(self):
            target, _cmd = launcher_command()
            if not os.environ.get('QIANXUN_LAUNCHER'):
                target = os.path.abspath(__file__)   # 直接用 Python 运行时：指向脚本本身
            QStandardPaths = _QtCore.QStandardPaths
            desk = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
            lnk = os.path.join(desk, '%s.lnk' % APP_NAME)
            try:
                if os.path.exists(lnk):
                    os.remove(lnk)
            except OSError:
                pass
            if _QtCore.QFile.link(target, lnk):
                self.statusBar().showMessage('已在桌面创建快捷方式：%s' % lnk, 5000)
            else:
                QMessageBox.warning(self, APP_NAME, '创建快捷方式失败：%s' % lnk)

        def rebuild(self):
            if QMessageBox.question(self, APP_NAME, '重建索引将重新扫描全部磁盘，确定吗？') == QMessageBox.Yes:
                self.engine.post('rebuild', dict(self.cfg))

        def raise_limit(self):
            cur = inotify_limit()
            target = 524288
            if cur >= target:
                QMessageBox.information(self, APP_NAME, '当前上限已为 {:,}，无需提升。'.format(cur))
                return
            if not shutil.which('pkexec'):
                QMessageBox.information(self, APP_NAME,
                                        '请在终端执行：\nsudo sh -c "echo fs.inotify.max_user_watches=%d > '
                                        '/etc/sysctl.d/90-qianxun.conf && sysctl -w fs.inotify.max_user_watches=%d"'
                                        % (target, target))
                return
            cmd = ('echo fs.inotify.max_user_watches=%d > /etc/sysctl.d/90-qianxun.conf && '
                   'sysctl -w fs.inotify.max_user_watches=%d' % (target, target))
            r = subprocess.call(['pkexec', 'sh', '-c', cmd])
            if r == 0 and inotify_limit() >= target:
                self.engine.post('rewatch')
                QMessageBox.information(self, APP_NAME, '已提升到 {:,}，正在重新挂载实时监控。'.format(target))
            else:
                QMessageBox.warning(self, APP_NAME, '未能提升（已取消或权限不足）。')

        def show_help(self):
            dlg = QDialog(self)
            dlg.setWindowTitle('搜索语法与快捷键')
            dlg.resize(720, 640)
            lay = QVBoxLayout(dlg)
            tb = QTextBrowser()
            tb.setHtml(HELP_HTML)
            lay.addWidget(tb)
            qexec(dlg)

        def show_about(self):
            QMessageBox.about(self, '关于千寻',
                              ('<b>千寻 %s</b><br>Everything 式文件名秒搜工具（Windows 版）。<br><br>'
                               '全盘索引常驻内存，ReadDirectoryChangesW 实时同步；支持 Everything 搜索语法。<br>'
                               if IS_WIN else
                               '<b>千寻 %s</b><br>银河麒麟上的 Everything 式文件名秒搜工具。<br><br>'
                               '全盘索引常驻内存，inotify 实时同步；支持 Everything 搜索语法。<br>') % VERSION +
                              '运行环境：Python %s · Qt %s' % (sys.version.split()[0], QT_VER) + '（%s）' % QT_BINDING)

    def open_path(p):
        if IS_WIN:
            try:
                os.startfile(p)
                return
            except OSError as e:
                log('startfile %s: %s' % (p, e))
                if getattr(e, 'winerror', 0) in (1155, 1223):   # 无关联程序／用户取消
                    try:
                        subprocess.Popen(['rundll32.exe', 'shell32.dll,OpenAs_RunDLL', p])
                    except OSError:
                        pass
                    return
            QDesktopServices.openUrl(QUrl.fromLocalFile(disp(p)))
            return
        exe = shutil.which('xdg-open')
        if exe:
            subprocess.Popen([exe, p], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(disp(p)))

    def show_in_folder(p):
        if IS_WIN:
            explorer = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'explorer.exe')
            try:
                # explorer 自己解析命令行：/select,"路径" 须原样传入
                subprocess.Popen('"%s" /select,"%s"' % (explorer, p))
            except OSError as e:
                log('explorer: %s' % e)
                open_path(os.path.dirname(p))
            return
        uri = file_url(p).toString(QUrl.FullyEncoded)
        peony = shutil.which('peony')
        if peony:
            subprocess.Popen([peony, '--show-items', uri], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        try:
            QDBusInterface = __import__(QT_BINDING + '.QtDBus', fromlist=['x']).QDBusInterface
            QDBusConnection = __import__(QT_BINDING + '.QtDBus', fromlist=['x']).QDBusConnection
            iface = QDBusInterface('org.freedesktop.FileManager1', '/org/freedesktop/FileManager1',
                                   'org.freedesktop.FileManager1', QDBusConnection.sessionBus())
            if iface.isValid():
                r = iface.call('ShowItems', [uri], '')
                if not r.errorName():
                    return
        except Exception:
            pass
        open_path(os.path.dirname(p) or '/')

    def move_to_trash(p):
        if IS_WIN:
            try:
                QFile = _QtCore.QFile
                if hasattr(QFile, 'moveToTrash'):
                    r = QFile.moveToTrash(p)
                    if (r[0] if isinstance(r, tuple) else bool(r)):
                        return True
            except Exception as e:
                log('moveToTrash: %s' % e)
            try:
                return win_recycle(p) and not os.path.lexists(p)
            except Exception as e:
                log('SHFileOperationW: %s' % e)
                return False
        try:
            # Qt 5.15 在家目录回收站建不起来时会把文件挪到当前目录下的 files/（且无 .trashinfo），先确保目录存在
            base = os.path.join(os.environ.get('XDG_DATA_HOME') or os.path.join(HOME, '.local', 'share'), 'Trash')
            for sub in ('files', 'info'):
                os.makedirs(os.path.join(base, sub), mode=0o700, exist_ok=True)
        except OSError:
            pass
        try:
            QFile = _QtCore.QFile
            # 非 UTF-8 文件名经 disp() 转换后已不是原路径，可能误删同名的另一个文件，只走 gio／手工回收站
            if hasattr(QFile, 'moveToTrash') and disp(p) == p:
                r = QFile.moveToTrash(disp(p))
                ok = r[0] if isinstance(r, tuple) else bool(r)
                if ok:
                    return True
        except Exception:
            pass
        gio = shutil.which('gio')
        if gio and subprocess.call([gio, 'trash', '--', p]) == 0:
            return True
        return _trash_freedesktop(p)

    def _trash_freedesktop(p):
        """按 freedesktop 回收站规范移到 ~/.local/share/Trash（仅限同一文件系统）。"""
        try:
            base = os.path.join(os.environ.get('XDG_DATA_HOME') or os.path.join(HOME, '.local', 'share'), 'Trash')
            files, info = os.path.join(base, 'files'), os.path.join(base, 'info')
            os.makedirs(files, exist_ok=True)
            os.makedirs(info, exist_ok=True)
            name = os.path.basename(p)
            cand, k = name, 1
            while os.path.lexists(os.path.join(files, cand)) or os.path.exists(os.path.join(info, cand + '.trashinfo')):
                k += 1
                cand = '%s.%d' % (name, k)
            from urllib.parse import quote
            ti = os.path.join(info, cand + '.trashinfo')
            with open(ti, 'w', encoding='utf-8') as f:
                f.write('[Trash Info]\nPath=%s\nDeletionDate=%s\n' % (
                    quote(os.fsencode(p)), time.strftime('%Y-%m-%dT%H:%M:%S')))
            try:
                os.rename(p, os.path.join(files, cand))
            except OSError:
                os.remove(ti)   # 跨文件系统等失败时不留孤立的 .trashinfo
                raise
            return True
        except OSError:
            return False


    if IS_WIN:
        class WinHotkey(object):
            """全局快捷键：RegisterHotKey（线程级，hwnd=NULL），WM_HOTKEY 由原生事件过滤器转给 win.toggle()。"""
            ID = 0xA51

            def __init__(self, win):
                import ctypes.wintypes as wt
                self.win = win
                self.ok = False
                u = ctypes.WinDLL('user32', use_last_error=True)
                self._reg = u.RegisterHotKey
                self._reg.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
                self._reg.restype = wt.BOOL
                self._unreg = u.UnregisterHotKey
                self._unreg.argtypes = [wt.HWND, ctypes.c_int]
                self._unreg.restype = wt.BOOL

            def register(self, spec):
                self.unregister()
                if not spec:
                    return True
                hk = parse_hotkey(spec)
                if hk is None:
                    self.win.statusBar().showMessage('全局快捷键“%s”无效，请在“工具 → 选项”中重新设置。' % spec, 10000)
                    return False
                self.ok = bool(self._reg(None, self.ID, hk[0] | 0x4000, hk[1]))   # MOD_NOREPEAT
                if not self.ok:
                    log('RegisterHotKey %s failed: %d' % (spec, ctypes.get_last_error()))
                    self.win.statusBar().showMessage(
                        '全局快捷键 %s 注册失败（可能已被其它程序占用），可在“工具 → 选项”中更换。' % spec, 15000)
                return self.ok

            def unregister(self):
                if self.ok:
                    self._unreg(None, self.ID)
                    self.ok = False

        class WinNativeFilter(_QtCore.QAbstractNativeEventFilter):
            """处理 WM_HOTKEY（唤出）与 WM_DEVICECHANGE（盘符插拔；安全弹出前释放目录句柄）。"""

            def __init__(self, win, engine):
                _QtCore.QAbstractNativeEventFilter.__init__(self)
                import ctypes.wintypes as wt
                self.win, self.engine = win, engine
                self.MSG = wt.MSG

            def nativeEventFilter(self, et, message):
                try:
                    et = qbytes(et) if hasattr(et, 'data') else bytes(et)
                    if et == b'windows_generic_MSG':
                        msg = self.MSG.from_address(int(message))
                        if msg.message == 0x0312 and msg.wParam == WinHotkey.ID:      # WM_HOTKEY
                            QTimer.singleShot(0, self.win.toggle)
                        elif msg.message == 0x0219:                                  # WM_DEVICECHANGE
                            self.on_device(msg.wParam, msg.lParam)
                except Exception:
                    log('native filter:\n' + traceback.format_exc())
                return False, 0

            def on_device(self, wp, lp):
                if wp == 0x8001 and lp:          # DBT_DEVICEQUERYREMOVE：立即关闭该盘上的目录句柄
                    dtype = ctypes.c_uint32.from_address(lp + 4).value
                    if dtype == 6:               # DBT_DEVTYP_HANDLE
                        h = ctypes.c_void_p.from_address(lp + 16).value
                        ino = self.engine.ino
                        if ino is not None and hasattr(ino, 'release_handle') and ino.release_handle(h):
                            log('released watch handle for device removal')
                if wp in (0x8000, 0x8002, 0x8004):   # ARRIVAL / QUERYREMOVEFAILED / REMOVECOMPLETE
                    self.engine.post('drive_check')


SERVER_NAME = server_name()


def main():
    args = sys.argv[1:]
    if '--version' in args:
        if sys.stdout is not None:      # pythonw.exe 下没有 stdout
            print('%s %s' % (APP_ID, VERSION))
        return 0
    if not HAVE_QT:
        if sys.stderr is not None:
            sys.stderr.write('千寻需要 PyQt5 或 PySide6：%s\n' % _QT_ERROR)
        log('Qt binding missing: %s' % _QT_ERROR)
        return 1
    if IS_WIN:
        # pythonw.exe 没有控制台：未捕获异常写日志，而不是让 PyQt5 在无提示的情况下 abort 整个进程
        def _hook(t, v, tb):
            log('uncaught exception:\n' + ''.join(traceback.format_exception(t, v, tb)))
        sys.excepthook = _hook
        win_set_app_id()
        try:   # 125%/150% 缩放时不取整，布局与字体比例正确
            QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        except Exception:
            pass
    if QT_BINDING == 'PyQt5' and hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if QT_BINDING == 'PyQt5' and hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    msg = 'toggle' if '--toggle' in args else ('hidden' if '--hidden' in args else 'show')

    if not IS_WIN:
        # 统一窗口身份：WM_CLASS=("qianxun","qianxun")、进程名 qianxun，
        # 使任务栏／Dock 能匹配到 qianxun.desktop（固定到任务栏后才有图标）
        os.environ['RESOURCE_NAME'] = APP_ID
        try:
            ctypes.CDLL(None).prctl(15, APP_ID.encode('ascii'), 0, 0, 0)   # PR_SET_NAME
        except Exception:
            pass
    app = QApplication([APP_ID] + sys.argv[1:])
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName(APP_ID) if hasattr(app, 'setDesktopFileName') else None

    # 单实例：已在运行则唤出
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(400):
        if IS_WIN:
            try:
                ctypes.windll.user32.AllowSetForegroundWindow(-1)   # 让已运行的实例能把窗口提到前台
            except Exception:
                pass
        sock.write(msg.encode('ascii'))
        sock.flush()
        sock.waitForBytesWritten(400)
        sock.disconnectFromServer()
        return 0

    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)

    icon = make_app_icon()
    app.setWindowIcon(icon)
    if IS_WIN:
        fams = set(_QtGui.QFontDatabase().families())
        for fam in ('Microsoft YaHei UI', 'Microsoft YaHei'):
            if fam in fams:
                f = QFont(fam)
                f.setPointSizeF(max(9.0, app.font().pointSizeF()))
                app.setFont(f)
                break
    cfg = load_config()
    index = Index()
    engine = make_engine(index, cfg)
    engine.start()
    win = MainWindow(cfg, index, engine, icon)
    if IS_WIN:
        try:
            engine.hwnd = int(win.winId())
            engine.post('devnotify')
            win.native_filter = WinNativeFilter(win, engine)
            app.installNativeEventFilter(win.native_filter)
            win.hotkey = WinHotkey(win)
            win.hotkey.register(cfg.get('hotkey', ''))
            app.aboutToQuit.connect(win.hotkey.unregister)
        except Exception:
            log('windows integration:\n' + traceback.format_exc())
        try:
            cur = win_autostart_get()
            want = launcher_command()[1] + ' --hidden'
            if cur and cur != want:
                win_autostart_set(True)   # 程序目录被移动后，开机自启项随之更新
        except OSError:
            pass

        def _commit(*_a):
            # 注销/关机：Windows 不发 SIGTERM，在 commitDataRequest 时保存窗口状态与索引
            try:
                win.save_state()
                if engine.is_alive() and index.version != engine.saved_version:
                    engine.post('save')
                    t = time.time()
                    while engine.saved_version != index.version and time.time() - t < 8 and engine.is_alive():
                        time.sleep(0.05)
            except Exception:
                log('commit data:\n' + traceback.format_exc())
        app.commitDataRequest.connect(_commit)
    app.setQuitOnLastWindowClosed(win.tray is None or not cfg.get('close_to_tray'))
    app.aboutToQuit.connect(lambda: (engine.post('quit'), engine.join(15)) if engine.is_alive() else None)

    def on_conn():
        c = server.nextPendingConnection()
        if c is None:
            return

        def rd():
            m = qbytes(c.readAll()).decode('ascii', 'ignore').strip()
            if m == 'toggle':
                win.toggle()
            elif m == 'hidden':
                pass
            else:
                win.show_raise()
        c.readyRead.connect(rd)
        c.disconnected.connect(c.deleteLater)
    server.newConnection.connect(on_conn)

    # 注销/关机时会话发 SIGTERM：走正常退出流程，保存索引与窗口状态（界面 200 ms 轮询定时器保证处理器能及时运行）
    try:
        import signal
        signal.signal(signal.SIGTERM, lambda *_a: QTimer.singleShot(0, win.quit_app))
    except (ValueError, OSError):
        pass

    if msg != 'hidden' or win.tray is None:
        win.show_raise()
    return qexec(app)


if __name__ == '__main__':
    sys.exit(main() or 0)
