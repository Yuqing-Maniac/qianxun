"""Taskbar pinning identity: portable path resolution and native Windows property readback."""
import ctypes
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'app'))
import qianxun as q


class IdentityTests(unittest.TestCase):
    def test_persistent_launcher_with_spaces_and_unicode(self):
        entry = r'D:\中文 软件\QianXun.exe'
        values = q.win_taskbar_identity({'QIANXUN_LAUNCHER': entry},
                                       r'C:\temp\rt-123456789abc\app\qianxun.py',
                                       lambda p: p == entry)
        self.assertEqual(values[2], '"' + entry + '"')
        self.assertEqual(values[3], entry + ',0')
        self.assertEqual(values[4], '千寻')
        self.assertEqual(values[5], 'QianXun.FileSearch')
        self.assertFalse(values[9])

    def test_moved_folder_recovers_outer_entry(self):
        entry = r'E:\移动 软件\QianXun.exe'
        values = q.win_taskbar_identity({'QIANXUN_LAUNCHER': r'C:\old\QianXun.exe'},
                                       r'E:\移动 软件\QianXun\app\qianxun.py',
                                       lambda p: p == entry)
        self.assertEqual(values[3], entry + ',0')

    def test_development_session_does_not_pin_python(self):
        values = q.win_taskbar_identity({'QIANXUN_LAUNCHER': r'C:\Python\pythonw.exe'},
                                       r'C:\src\app\qianxun.py', lambda p: True)
        # It may find an actual product entry, but may never use pythonw.exe.
        self.assertNotIn('pythonw', str(values).lower())
        values = q.win_taskbar_identity({}, r'C:\src\app\qianxun.py', lambda p: False)
        self.assertTrue(values[9])
        self.assertIsNone(values[2])
        self.assertIsNone(values[3])

    @unittest.skipUnless(os.name == 'nt', 'native Windows property store')
    def test_native_property_roundtrip_and_cleanup(self):
        from ctypes import wintypes
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                         wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                         wintypes.HINSTANCE, ctypes.c_void_p]
        user.CreateWindowExW.restype = wintypes.HWND
        user.DestroyWindow.argtypes = [wintypes.HWND]
        user.DestroyWindow.restype = wintypes.BOOL
        hwnd = user.CreateWindowExW(0, 'STATIC', 'QianXun identity test', 0,
                                    0, 0, 0, 0, None, None, None, None)
        self.assertTrue(hwnd, ctypes.get_last_error())
        try:
            values = q.win_taskbar_identity({'QIANXUN_LAUNCHER': r'D:\中文 软件\QianXun.exe'},
                                           exists=lambda p: True)
            self.assertEqual(q._win_taskbar_store(hwnd, values), values)
            self.assertEqual(q._win_taskbar_store(hwnd), values)
            cleared = {pid: None for pid in q.TASKBAR_PROPERTY_IDS}
            self.assertEqual(q._win_taskbar_store(hwnd, cleared), cleared)
        finally:
            q._win_taskbar_store(hwnd, {pid: None for pid in q.TASKBAR_PROPERTY_IDS})
            user.DestroyWindow(hwnd)


if __name__ == '__main__':
    unittest.main()
