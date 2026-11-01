"""Pure helpers of the Windows port: FILE_NOTIFY_INFORMATION parser, path helpers, roots/excludes,
data dir, hotkey parsing, launcher command, terminal candidates. Runs on Linux."""
import struct

from win_common import q, check, done, WinMode


def fni(records):
    """Build a FILE_NOTIFY_INFORMATION chain like ReadDirectoryChangesW does (DWORD-aligned entries)."""
    out = b''
    blobs = []
    for act, name in records:
        nb = name.encode('utf-16-le', 'surrogatepass')
        body = struct.pack('<III', 0, act, len(nb)) + nb
        body += b'\0' * ((-len(body)) % 4)
        blobs.append(bytearray(body))
    for i, b in enumerate(blobs):
        if i < len(blobs) - 1:
            struct.pack_into('<I', b, 0, len(b))
        out += bytes(b)
    return out


# ---- parse_notify ----
recs = [(1, 'a.txt'), (4, '目录\\旧名.docx'), (5, '目录\\新名.docx'), (2, 'x'), (3, 'deep\\er\\f.bin')]
check('parse_notify chain', q.parse_notify(fni(recs)) == recs, q.parse_notify(fni(recs)))
check('parse_notify single', q.parse_notify(fni([(1, 'z')])) == [(1, 'z')])
check('parse_notify empty', q.parse_notify(b'') == [])
lone = 'bad\ud800name'
check('parse_notify lone surrogate', q.parse_notify(fni([(1, lone)])) == [(1, lone)])
emoji = '照片😀.jpg'
check('parse_notify astral', q.parse_notify(fni([(1, emoji)])) == [(1, emoji)])
data = fni(recs)
check('parse_notify truncated', q.parse_notify(data[:30]) == recs[:1], q.parse_notify(data[:30]))
bad = bytearray(fni([(1, 'a'), (2, 'b')]))
struct.pack_into('<I', bad, 0, 4)   # corrupt NextEntryOffset (<12) must not loop forever
check('parse_notify corrupt offset', q.parse_notify(bytes(bad)) == [(1, 'a')])

# ---- path helpers ----
J = q.join_path_sep
check('join win root', J('C:\\', 'Users', '\\') == 'C:\\Users')
check('join win dir', J('C:\\Users', 'a b', '\\') == 'C:\\Users\\a b')
check('join unc root', J('\\\\srv\\share\\', 'x', '\\') == '\\\\srv\\share\\x')
check('join linux root', J('/', 'etc', '/') == '/etc' and J('/etc', 'x', '/') == '/etc/x')
check('join_path linux identical', q.join_path('/', 'a') == '/a' and q.join_path('/a', 'b') == '/a/b')
S = q.split_path_sep
check('split win', S('C:\\Users\\a.txt', '\\') == ('C:\\Users', 'a.txt'))
check('split win root child', S('C:\\a', '\\') == ('C:\\', 'a'))
check('split win root', S('C:\\', '\\')[0] is None)
check('split unc', S('\\\\srv\\share\\x', '\\') == ('\\\\srv\\share\\', 'x'))
check('split linux', S('/a', '/') == ('/', 'a') and S('/a/b', '/') == ('/a', 'b') and S('/', '/')[0] is None)
N = lambda p: q.win_norm_path(p, abspath=lambda x: 'ABS:' + x)
check('norm slash', N('c:/Users/x/') == 'C:\\Users\\x', N('c:/Users/x/'))
check('norm drive', N('d:') == 'D:\\' and N('D:\\') == 'D:\\', (N('d:'), N('D:\\')))
check('norm dots', N('C:\\a\\..\\b\\.\\c') == 'C:\\b\\c')
check('norm unc', N('\\\\srv\\share\\dir\\') == '\\\\srv\\share\\dir', N('\\\\srv\\share\\dir\\'))
check('norm relative', N('rel\\x').startswith('ABS:'))
check('long_path', q.long_path('C:\\' + 'a' * 250, True).startswith('\\\\?\\C:\\') and
      q.long_path('\\\\s\\h\\' + 'a' * 250, True).startswith('\\\\?\\UNC\\s\\h\\') and
      q.long_path('C:\\short', True) == 'C:\\short' and q.long_path('/' + 'a' * 300) == '/' + 'a' * 300)
check('disp lone surrogate', q.disp('x\ud800y') == 'x?y', repr(q.disp('x\ud800y')))
check('disp surrogateescape unchanged', q.disp(b'a\xffb'.decode('utf-8', 'surrogateescape')) == 'a\ufffdb')
check('dkey linux identity', q.dkey('/A/b') == '/A/b')
with WinMode():
    check('dkey win lower', q.dkey('C:\\Users\\ABC') == 'c:\\users\\abc')
    check('join_path win', q.join_path('C:\\', 'x') == 'C:\\x' and q.join_path('C:\\x', 'y') == 'C:\\x\\y')

# ---- roots ----
drives = [('C:\\', q.DRIVE_FIXED), ('D:\\', q.DRIVE_FIXED), ('E:\\', q.DRIVE_REMOVABLE), ('F:\\', q.DRIVE_CDROM),
          ('R:\\', q.DRIVE_RAMDISK), ('Z:\\', q.DRIVE_REMOTE)]
base = {'roots': [], 'index_removable': False, 'index_network': False}
check('roots fixed only', q.win_select_roots(base, drives) == [('C:\\', False), ('D:\\', False), ('R:\\', False)])
r = q.win_select_roots(dict(base, index_removable=True, index_network=True), drives)
check('roots +removable +network', r == [('C:\\', False), ('D:\\', False), ('R:\\', False), ('E:\\', True), ('Z:\\', True)], r)
r = q.win_select_roots(dict(base, roots=['d:/work', 'D:\\Work\\']), drives)
check('roots explicit dedupe', r == [('D:\\work', False)], r)
r = q.win_select_roots(dict(base, roots=['e:\\photos'], index_removable=True), drives)
check('roots explicit on removable is dynamic', r == [('E:\\photos', True), ('E:\\', True)], r)

# ---- excludes ----
ex = q.win_excludes({'excludes': ['c:/Temp/'], }, ['C:\\', 'D:\\data'], sysroot='C:\\Windows')
want = {'c:\\temp', 'c:\\windows\\winsxs', 'c:\\$recycle.bin', 'c:\\system volume information',
        'd:\\$recycle.bin', 'd:\\system volume information'}
check('excludes', ex == want, ex ^ want)
ex = q.win_excludes({'excludes': ['D:\\data']}, ['D:\\data'], sysroot='C:\\Windows')
check('excludes never drop a root', 'd:\\data' not in ex)

# ---- data dir ----
env = {'LOCALAPPDATA': 'C:\\Users\\u\\AppData\\Local', 'QIANXUN_LAUNCHER': 'D:\\Tools\\QianXun\\QianXun.exe'}
script = 'D:\\Tools\\QianXun\\app\\qianxun.py'
check('data dir default', q.win_data_dir(env, script, exists=lambda p: False) == 'C:\\Users\\u\\AppData\\Local\\QianXun')
check('data dir portable', q.win_data_dir(env, script, exists=lambda p: p == 'D:\\Tools\\QianXun\\portable.txt')
      == 'D:\\Tools\\QianXun\\data')
check('data dir portable no launcher', q.win_data_dir({'LOCALAPPDATA': 'L:'}, script,
                                                     exists=lambda p: p == 'D:\\Tools\\QianXun\\portable.txt')
      == 'D:\\Tools\\QianXun\\data')
check('data dir no LOCALAPPDATA', q.win_data_dir({'USERPROFILE': 'C:\\Users\\u'}, script, exists=lambda p: False)
      == 'C:\\Users\\u\\AppData\\Local\\QianXun')

# ---- hotkey ----
H = q.parse_hotkey
check('hotkey default', H('Ctrl+Alt+F') == (0x3, 0x46))
check('hotkey meta/shift/space', H('Meta+Shift+Space') == (0x8 | 0x4, 0x20))
check('hotkey F-key alone', H('F9') == (0, 0x78) and H('Ctrl+F12') == (0x2, 0x7B))
check('hotkey digit', H('Alt+1') == (0x1, 0x31))
check('hotkey backquote', H('Ctrl+`') == (0x2, 0xC0))
check('hotkey plus', H('Ctrl++') == (0x2, 0xBB))
check('hotkey invalid', H('') is None and H('F') is None and H('Ctrl+') is None and H('Hyper+X') is None
      and H('Ctrl+Foo') is None)

# ---- launcher / terminal / server name ----
check('launcher env', q.launcher_command({'QIANXUN_LAUNCHER': 'C:\\A B\\QianXun.exe'})
      == ('C:\\A B\\QianXun.exe', '"C:\\A B\\QianXun.exe"'))
t, c = q.launcher_command({}, 'C:\\rt\\python.exe', 'C:\\app\\qianxun.py', exists=lambda p: True)
check('launcher python → pythonw', t == 'C:\\rt\\pythonw.exe' and c == '"C:\\rt\\pythonw.exe" "C:\\app\\qianxun.py"', (t, c))
avail = {'wt.exe': 'C:\\WA\\wt.exe', 'powershell.exe': 'C:\\PS\\powershell.exe', 'cmd.exe': 'C:\\W\\cmd.exe'}
tc = q.win_terminal_commands('D:\\a b', avail.get)
check('terminal wt first', tc[0] == (['C:\\WA\\wt.exe', '-d', 'D:\\a b'], 0) and tc[1][1] == 0x10 and len(tc) == 3)
tc = q.win_terminal_commands('D:\\a;b', avail.get)
check('terminal skip wt with ;', tc[0][0][0] == 'C:\\PS\\powershell.exe')
tc = q.win_terminal_commands('C:\\', lambda n: None)
check('terminal cmd fallback', tc == [(['cmd.exe'], 0x10)])
import os
check('server name linux unchanged', q.SERVER_NAME == 'qianxun-%d' % os.getuid())
done()
