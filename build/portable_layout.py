"""Check a portable package before it is shipped.

A portable archive has exactly two top-level names: one folder and one entry
file. Required runtime files and the icon must be present and non-empty.
Symlinks and non-ASCII names fail the build.
"""
import os
import stat
import sys
import tarfile
import zipfile


def _die(msg):
    raise SystemExit('portable layout: ' + msg)


def _ascii(name):
    try:
        name.encode('ascii')
    except UnicodeEncodeError:
        _die('non-ascii name: ' + name)


def _tops(names):
    found = set()
    for name in names:
        name = name.replace('\\', '/').strip('/')
        if not name:
            continue
        found.add(name.split('/')[0])
    return found


def _require_pair(found, folder, entry):
    if found != {folder, entry}:
        _die('top level is %s, want %s and %s' % (', '.join(sorted(found)) or '(empty)', folder, entry))


def check_tree(stage, folder, entry, needs):
    stage = os.path.abspath(stage)
    if not os.path.isdir(stage):
        _die('stage is not a directory: ' + stage)
    found = set()
    for name in os.listdir(stage):
        _ascii(name)
        path = os.path.join(stage, name)
        if os.path.islink(path):
            _die('symlink: ' + name)
        found.add(name)
    _require_pair(found, folder, entry)
    entry_path = os.path.join(stage, entry)
    folder_path = os.path.join(stage, folder)
    if not os.path.isfile(entry_path) or os.path.getsize(entry_path) == 0:
        _die('entry is missing or empty: ' + entry)
    if not os.path.isdir(folder_path):
        _die('folder is missing: ' + folder)
    for rel in needs:
        _ascii(rel)
        path = os.path.join(stage, *rel.split('/'))
        if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) == 0:
            _die('missing or empty: ' + rel)
    for dirpath, dirnames, filenames in os.walk(stage, followlinks=False):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, stage).replace(os.sep, '/')
            _ascii(rel)
            if os.path.islink(path):
                _die('symlink: ' + rel)


def _zip_symlink(info):
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def check_zip(path, folder, entry, needs):
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        _die('bad zip %s: %s' % (path, exc))
    try:
        infos = zf.infolist()
        names = []
        for info in infos:
            _ascii(info.filename)
            if _zip_symlink(info):
                _die('symlink in zip: ' + info.filename)
            names.append(info.filename)
        _require_pair(_tops(names), folder, entry)
        have = {n.replace('\\', '/').rstrip('/') for n in names}
        for rel in needs:
            if rel not in have:
                _die('zip missing ' + rel)
            info = zf.getinfo(rel)
            if info.file_size == 0:
                _die('zip empty ' + rel)
    finally:
        zf.close()


def check_tar(path, folder, entry, needs):
    try:
        tf = tarfile.open(path, 'r:*')
    except (OSError, tarfile.TarError) as exc:
        _die('bad tar %s: %s' % (path, exc))
    try:
        names = []
        by_name = {}
        for info in tf.getmembers():
            _ascii(info.name)
            if info.issym() or info.islnk():
                _die('symlink in tar: ' + info.name)
            names.append(info.name)
            by_name[info.name.rstrip('/')] = info
        _require_pair(_tops(names), folder, entry)
        for rel in needs:
            info = by_name.get(rel)
            if info is None or not info.isfile() or info.size == 0:
                _die('tar missing or empty: ' + rel)
    finally:
        tf.close()


def check_archive(path, folder, entry, needs):
    if path.endswith('.zip'):
        check_zip(path, folder, entry, needs)
    elif path.endswith('.tar.gz') or path.endswith('.tgz'):
        check_tar(path, folder, entry, needs)
    else:
        _die('unknown archive: ' + path)


def pe_has_icon(path):
    """True when the PE has an RT_GROUP_ICON (14) or RT_ICON (3) resource."""
    with open(path, 'rb') as fh:
        data = fh.read()
    if len(data) < 0x40 or data[:2] != b'MZ':
        return False
    pe = int.from_bytes(data[0x3C:0x40], 'little')
    if pe + 24 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        return False
    nsec = int.from_bytes(data[pe + 6:pe + 8], 'little')
    optsz = int.from_bytes(data[pe + 20:pe + 22], 'little')
    magic = int.from_bytes(data[pe + 24:pe + 26], 'little')
    if magic == 0x10B:
        dd = pe + 24 + 96
    elif magic == 0x20B:
        dd = pe + 24 + 112
    else:
        return False
    if dd + 24 > len(data):
        return False
    rva = int.from_bytes(data[dd + 16:dd + 20], 'little')
    size = int.from_bytes(data[dd + 20:dd + 24], 'little')
    if rva == 0 or size == 0:
        return False
    sec = pe + 24 + optsz
    offset = None
    for i in range(nsec):
        s = sec + i * 40
        if s + 24 > len(data):
            return False
        vsz = int.from_bytes(data[s + 8:s + 12], 'little')
        va = int.from_bytes(data[s + 12:s + 16], 'little')
        rawsz = int.from_bytes(data[s + 16:s + 20], 'little')
        raw = int.from_bytes(data[s + 20:s + 24], 'little')
        span = max(vsz, rawsz)
        if va <= rva < va + span:
            offset = raw + (rva - va)
            break
    if offset is None or offset + 16 > len(data):
        return False
    named = int.from_bytes(data[offset + 12:offset + 14], 'little')
    ident = int.from_bytes(data[offset + 14:offset + 16], 'little')
    entry = offset + 16
    for _i in range(named + ident):
        if entry + 4 > len(data):
            return False
        name = int.from_bytes(data[entry:entry + 4], 'little')
        if name in (3, 14):
            return True
        entry += 8
    return False


def check_exe(path):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        _die('exe missing: ' + path)
    if not pe_has_icon(path):
        _die('exe has no icon resource: ' + path)


def _parse(argv):
    if len(argv) < 3:
        _die('usage: portable_layout.py tree|archive|exe PATH [--folder F --entry E --need REL ...]')
    cmd, path = argv[1], argv[2]
    folder = entry = None
    needs = []
    i = 3
    while i < len(argv):
        flag = argv[i]
        if flag in ('--folder', '--entry', '--need'):
            if i + 1 >= len(argv):
                _die('missing value for ' + flag)
            value = argv[i + 1]
            i += 2
            if flag == '--folder':
                folder = value
            elif flag == '--entry':
                entry = value
            else:
                needs.append(value)
        else:
            _die('unknown argument ' + flag)
    return cmd, path, folder, entry, needs


def main(argv):
    cmd, path, folder, entry, needs = _parse(argv)
    if cmd == 'exe':
        check_exe(path)
        print('icon ok', path)
        return
    if not folder or not entry:
        _die('tree and archive checks need --folder and --entry')
    if cmd == 'tree':
        check_tree(path, folder, entry, needs)
    elif cmd == 'archive':
        check_archive(path, folder, entry, needs)
    else:
        _die('unknown command ' + cmd)
    print('layout ok', path)


if __name__ == '__main__':
    main(sys.argv)
