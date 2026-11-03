import os
import re
import sys
import shutil
import subprocess
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'app'))
import qianxun as q  # noqa: E402

FAIL = []


def check(cond, what):
    if not cond:
        FAIL.append(what)
        print('FAIL', what)


def snap(path):
    st = os.lstat(path)
    with open(path, 'rb') as f:
        data = f.read()
    return (st.st_mtime_ns, data)


def py_bytes(version, marker):
    return ("VERSION = '%s'\n# marker %s\n" % (version, marker)).encode()


def write_py(root, version, marker):
    path = os.path.join(root, 'app', 'qianxun.py')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(py_bytes(version, marker))
    return path


def forbid(_inspect):
    raise AssertionError('confirm')


def allow(_inspect):
    return True


def pack(base, name, fr, to, marker):
    src = os.path.join(base, 'src-' + name)
    write_py(src, to, marker)
    dest = os.path.join(base, name + '.zip')
    q.pack_incremental(fr, src, dest)
    return dest, os.path.join(src, 'app', 'qianxun.py')


def planted(root, backup, journal):
    dest = os.path.join(root, 'app', 'qianxun.py')
    folder = os.path.join(root, '.qx-upgrade', 'backup', 'app')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'qianxun.py'), 'wb') as f:
        f.write(backup)
    with open(os.path.join(root, '.qx-upgrade', 'journal'), 'wb') as f:
        f.write(journal)
    return dest


base = tempfile.mkdtemp(prefix='qx-upgrade-')
try:
    noop_root = os.path.join(base, 'noop')
    noop_py = write_py(noop_root, '1.2.0', 'same')
    before = snap(noop_py)
    noop_zip, _src = pack(base, 'noop', '1.2.0', '1.2.0', 'same')
    with zipfile.ZipFile(noop_zip) as zf:
        check(zf.namelist() == [q.UPGRADE_META, q.UPGRADE_ALLOW[0]], 'noop member order')
        check(zf.read(q.UPGRADE_META) == b'1.2.0\n1.2.0\n', 'noop meta')
    got = q.apply_upgrade(noop_zip, noop_root, forbid, '1.2.0')
    check(got.outcome == 'already' and not got.needs_restart, 'noop already')
    check(snap(noop_py) == before, 'noop bytes')
    check(not os.path.exists(os.path.join(noop_root, '.qx-upgrade')), 'noop leaves no journal')
    kind, text = q.upgrade_notice(got)
    check(kind == 'information' and text == '已是 1.2.0，未修改任何文件。', 'noop notice')

    up_root = os.path.join(base, 'up')
    up_py = write_py(up_root, '1.2.0', 'old')
    side = {}
    for name, body in (('portable.txt', b'keep-portable\n'), ('config.json', b'{"keep": true}\n')):
        path = os.path.join(up_root, name)
        with open(path, 'wb') as f:
            f.write(body)
        side[path] = snap(path)
    up_zip, up_src = pack(base, 'up', '1.2.0', '1.2.1', 'new')
    seen = []

    def yes(ins):
        seen.append(ins)
        return True

    got = q.apply_upgrade(up_zip, up_root, yes, '1.2.0')
    check(got.outcome == 'applied' and got.needs_restart, 'upgrade applied')
    written = open(up_py, 'rb').read()
    check(written == open(up_src, 'rb').read(), 'payload replaced qianxun.py')
    check(b"VERSION = '1.2.1'\n" in written, 'version line is 1.2.1')
    check(all(snap(path) == old for path, old in side.items()), 'portable.txt and config.json unchanged')
    check(not os.path.exists(os.path.join(up_root, '.qx-write-probe')), 'write probe removed')
    check(len(seen) == 1 and seen[0].from_version == '1.2.0' and seen[0].to_version == '1.2.1', 'confirm versions')
    check(seen[0].disk_version == '1.2.0' and seen[0].paths == q.UPGRADE_ALLOW, 'confirm disk and paths')
    check(seen[0].root == os.path.abspath(up_root), 'confirm root')
    check(q.upgrade_confirm_text(seen[0]) == (
        '将把千寻从 1.2.0 升级到 1.2.1。\n安装目录：%s\n只替换这些文件：app/qianxun.py。'
        '配置、索引和日志不会改动。\n确定后会退出并重新打开千寻。') % os.path.abspath(up_root),
          'confirm body')
    kind, text = q.upgrade_notice(got)
    check(kind == 'status' and text == '已写入 1.2.1。正在退出并重新打开千寻。只关窗口会留在托盘，仍是旧程序。',
          'applied notice')

    held = snap(up_py)
    again = q.apply_upgrade(up_zip, up_root, forbid, '1.2.1')
    check(again.outcome == 'already' and not again.needs_restart, 'second apply already')
    check(snap(up_py) == held, 'second apply keeps bytes')
    kind, text = q.upgrade_notice(again)
    check(kind == 'information' and text == '已是 1.2.1，未修改任何文件。', 'second notice')
    stale = q.apply_upgrade(up_zip, up_root, forbid, '1.2.0')
    check(stale.outcome == 'already' and stale.needs_restart, 'already restarts when the process is older')
    check(snap(up_py) == held, 'restart case does not rewrite')
    kind, text = q.upgrade_notice(stale)
    check(kind == 'status' and text == '文件已是 1.2.1。正在退出并重新打开千寻。', 'restart notice')

    cancel_root = os.path.join(base, 'cancel')
    cancel_py = write_py(cancel_root, '1.2.0', 'stay')
    cancel_before = snap(cancel_py)
    got = q.apply_upgrade(up_zip, cancel_root, lambda _ins: False, '1.2.0')
    check(got.outcome == 'cancelled', 'confirm false cancels')
    check(snap(cancel_py) == cancel_before, 'cancel keeps bytes')
    check(not os.path.exists(os.path.join(cancel_root, '.qx-upgrade')), 'cancel writes no journal')
    check(q.upgrade_notice(got) == ('', ''), 'cancel has no dialog')

    mid_root = os.path.join(base, 'mid')
    mid_py = write_py(mid_root, '1.2.1', 'mid')
    mid_zip, mid_src = pack(base, 'mid', '1.2.0', '1.2.2', 'later')
    got = q.apply_upgrade(mid_zip, mid_root, allow, '1.2.1')
    check(got.outcome == 'applied', 'interval 1.2.1 accepts 1.2.0 to 1.2.2')
    check(open(mid_py, 'rb').read() == open(mid_src, 'rb').read(), 'interval wrote 1.2.2')

    old_root = os.path.join(base, 'old')
    old_py = write_py(old_root, '1.1.0', 'ancient')
    old_before = snap(old_py)
    got = q.apply_upgrade(up_zip, old_root, forbid, '1.1.0')
    check(got.outcome == 'refused' and got.reason == 'version', '1.1.0 is too old')
    check(snap(old_py) == old_before, 'too old keeps bytes')
    check(not os.path.exists(os.path.join(old_root, '.qx-upgrade')), 'too old writes nothing')
    kind, text = q.upgrade_notice(got)
    check(text == '当前版本是 1.1.0，此升级包要求不低于 1.2.0、低于 1.2.1。版本不一致时不会改动文件。',
          'version notice')

    new_root = os.path.join(base, 'newer')
    new_py = write_py(new_root, '1.3.0', 'ahead')
    new_before = snap(new_py)
    got = q.apply_upgrade(up_zip, new_root, forbid, '1.3.0')
    check(got.outcome == 'refused' and got.reason == 'version', '1.3.0 refuses a 1.2.1 pack')
    check(snap(new_py) == new_before, 'downgrade keeps bytes')

    bad_root = os.path.join(base, 'bad')
    bad_py = write_py(bad_root, '1.2.0', 'old')
    bad_before = snap(bad_py)
    payload = py_bytes('1.2.1', 'new')
    cases = (
        ('extra', [('app/qianxun.py', payload), ('extra.txt', b'x')], 'bad_path'),
        ('dotdot', [('app/qianxun.py', payload), ('../x', b'x')], 'bad_path'),
        ('cjk', [('app/qianxun.py', payload), ('说明.txt', b'x')], 'bad_path'),
    )
    for name, members, reason in cases:
        path = os.path.join(base, name + '.zip')
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr(q.UPGRADE_META, b'1.2.0\n1.2.1\n')
            for member, data in members:
                zf.writestr(member, data)
        got = q.apply_upgrade(path, bad_root, forbid, '1.2.0')
        check(got.outcome == 'refused' and got.reason == reason, '%s refused' % name)
        check(snap(bad_py) == bad_before, '%s writes nothing' % name)
    kind, text = q.upgrade_notice(got)
    check(text == '升级包里有不允许的路径，已拒绝，未改动任何文件。', 'bad path notice')

    opt = '/opt/qianxun'
    if os.path.exists(opt):
        opt_py = os.path.join(opt, 'app', 'qianxun.py')
        opt_before = open(opt_py, 'rb').read() if os.path.isfile(opt_py) else None
        try:
            disk = None
            if opt_before is not None:
                found = re.search(br"^VERSION = '(\d+)\.(\d+)\.(\d+)'", opt_before, re.M)
                if found:
                    disk = '%d.%d.%d' % tuple(int(part) for part in found.groups())
            if disk is not None:
                parts = tuple(int(part) for part in disk.split('.'))
                nxt = '%d.%d.%d' % (parts[0], parts[1], parts[2] + 1)
                opt_zip, _opt_src = pack(base, 'opt', disk, nxt, 'opt')
                got = q.apply_upgrade(opt_zip, opt, allow, disk)
                check(got.outcome == 'refused' and got.reason == 'opt', 'opt refuses an in-range pack')
            else:
                got = q.apply_upgrade(up_zip, opt, forbid, '1.2.0')
                check(got.outcome == 'refused', 'opt refuses')
            if opt_before is not None:
                check(open(opt_py, 'rb').read() == opt_before, 'opt bytes unchanged')
        finally:
            if opt_before is not None and os.path.isfile(opt_py) and open(opt_py, 'rb').read() != opt_before:
                with open(opt_py, 'wb') as f:
                    f.write(opt_before)
                check(False, 'restored /opt/qianxun after an unexpected write')
    else:
        print('skip /opt/qianxun')

    ro_root = os.path.join(base, 'ro')
    ro_py = write_py(ro_root, '1.2.0', 'ro')
    ro_before = snap(ro_py)
    os.chmod(ro_root, 0o555)
    try:
        got = q.apply_upgrade(up_zip, ro_root, forbid, '1.2.0')
        check(got.outcome == 'refused' and got.reason == 'nowrite', 'unwritable root refuses')
        check(snap(ro_py) == ro_before, 'unwritable root keeps bytes')
        check(q.upgrade_notice(got)[1].startswith('此目录不能增量升级：'), 'unwritable notice')
    finally:
        os.chmod(ro_root, 0o755)

    rt_root = os.path.join(base, 'rt-0123456789ab')
    rt_py = write_py(rt_root, '1.2.0', 'rt')
    rt_before = snap(rt_py)
    with open(os.path.join(rt_root, '.complete'), 'wb') as f:
        f.write(b'')
    got = q.apply_upgrade(up_zip, rt_root, forbid, '1.2.0')
    check(got.outcome == 'refused' and got.reason == 'extract', 'extract dir refuses')
    check(snap(rt_py) == rt_before, 'extract dir keeps bytes')
    check('请改用解压后的文件夹版' in q.upgrade_notice(got)[1], 'extract notice')

    rec_root = os.path.join(base, 'rec')
    os.makedirs(os.path.join(rec_root, 'app'))
    old_body = py_bytes('1.2.0', 'backup')
    new_body = py_bytes('1.2.1', 'half')
    rec_py = planted(rec_root, old_body, (
        'state=progress\nfrom=1.2.0\nto=1.2.1\npath=app/qianxun.py\nabsent=0\n').encode('ascii'))
    with open(rec_py, 'wb') as f:
        f.write(new_body)
    note = q.reconcile_upgrade(rec_root)
    check(note == '上次增量升级中断，已恢复升级前的文件。', 'reconcile sentence')
    check(open(rec_py, 'rb').read() == old_body, 'reconcile restores backup')
    check(q.reconcile_upgrade(rec_root) is None, 'second reconcile is quiet')
    check(open(rec_py, 'rb').read() == old_body, 'second reconcile keeps the backup')

    crash_root = os.path.join(base, 'crash')
    os.makedirs(os.path.join(crash_root, 'app'))
    crash_py = planted(crash_root, old_body, (
        'state=progress\nfrom=1.2.0\nto=1.2.1\npath=app/qianxun.py\nabsent=0\n').encode('ascii'))
    with open(crash_py, 'wb') as f:
        f.write(new_body)
    third = py_bytes('1.2.1', 'should-not-land')
    crash_zip = os.path.join(base, 'crash.zip')
    with zipfile.ZipFile(crash_zip, 'w') as zf:
        zf.writestr(q.UPGRADE_META, b'1.2.0\n1.2.1\n')
        zf.writestr('app/qianxun.py', third)
    got = q.apply_upgrade(crash_zip, crash_root, allow, '1.2.0')
    check(got.outcome == 'rolled_back', 'crashed apply does not continue into the zip')
    check(open(crash_py, 'rb').read() == old_body, 'crashed apply restores backup only')

    swap_root = os.path.join(base, 'swap')
    swap_py = write_py(swap_root, '1.2.0', 'old')
    swap_zip, _swap_src = pack(base, 'swap', '1.2.0', '1.2.1', 'first')

    def swap(_ins):
        src = os.path.join(base, 'src-swap2')
        write_py(src, '1.2.1', 'second')
        os.remove(swap_zip)
        q.pack_incremental('1.2.0', src, swap_zip)
        return True

    got = q.apply_upgrade(swap_zip, swap_root, swap, '1.2.0')
    check(got.outcome == 'applied', 'reread still applies')
    check(open(swap_py, 'rb').read() == py_bytes('1.2.1', 'second'), 'reread writes the zip from after confirm')

    trash_root = os.path.join(base, 'trash')
    trash_py = write_py(trash_root, '1.2.0', 'old')
    trash_before = snap(trash_py)
    trash_zip, _trash_src = pack(base, 'trash', '1.2.0', '1.2.1', 'gone')

    def trash(_ins):
        with open(trash_zip, 'wb') as f:
            f.write(b'not a zip')
        return True

    got = q.apply_upgrade(trash_zip, trash_root, trash, '1.2.0')
    check(got.outcome == 'refused' and got.reason == 'bad_zip', 'reread of a broken zip refuses')
    check(snap(trash_py) == trash_before, 'broken reread writes nothing')
    check(q.upgrade_notice(got)[1] == '无法读取升级包。请选择千寻增量包，而不是完整安装包。', 'bad zip notice')

    repo = os.path.abspath(os.path.join(HERE, '..', '..'))
    script = os.path.join(repo, 'app', 'qianxun.py')
    cli_out = os.path.join(base, 'cli.zip')
    proc = subprocess.run([sys.executable, script, '--pack-incremental', '1.1.0', repo, cli_out],
                          capture_output=True, text=True)
    check(proc.returncode == 0 and proc.stdout.strip() == os.path.abspath(cli_out), 'pack cli prints dest')
    check(os.path.isfile(cli_out), 'pack cli writes the zip')
    refused = subprocess.run([sys.executable, script, '--pack-incremental', '9.9.9', repo, cli_out],
                             capture_output=True, text=True)
    check(refused.returncode == 1 and refused.stdout == '', 'pack cli refuses a newer from_version')
    arity = subprocess.run([sys.executable, script, '--pack-incremental', '1.1.0', repo],
                           capture_output=True, text=True)
    check(arity.returncode == 1 and arity.stdout == '', 'pack cli requires three arguments')

    down = os.path.join(base, 'down.zip')
    down_tree = os.path.join(base, 'down-tree')
    write_py(down_tree, '1.2.0', 'tree')
    try:
        q.pack_incremental('1.2.1', down_tree, down)
        check(False, 'pack 1.2.1 to 1.2.0 should refuse')
    except q.UpgradeError:
        check(not os.path.exists(down), 'refused pack writes no zip')
finally:
    shutil.rmtree(base, ignore_errors=True)

print('UPGRADE FAILED:', FAIL if FAIL else 'none')
sys.exit(1 if FAIL else 0)
