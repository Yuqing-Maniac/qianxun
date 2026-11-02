"""Shared setup for the Windows-port unit tests (run on Linux; no Qt needed)."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'app')
sys.path.insert(0, APP)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'qa'))

_tmp_home = tempfile.mkdtemp(prefix='win_home_')
os.environ['XDG_CONFIG_HOME'] = os.path.join(_tmp_home, 'cfg')
os.environ['XDG_CACHE_HOME'] = os.path.join(_tmp_home, 'cache')
os.environ.setdefault('QIANXUN_QT', 'none')   # no Qt import needed for these tests

import qianxun as q  # noqa: E402

FAIL = []


def check(name, cond, detail=''):
    if cond:
        print('PASS', name)
    else:
        FAIL.append(name)
        print('FAIL', name, detail)


class WinMode(object):
    """Temporarily switch the module's path semantics to Windows (IS_WIN / SEP)."""

    def __enter__(self):
        self.old = (q.IS_WIN, q.SEP)
        q.IS_WIN, q.SEP = True, '\\'
        return self

    def __exit__(self, *a):
        q.IS_WIN, q.SEP = self.old


def done():
    print('WIN TESTS FAILED:', ', '.join(FAIL) if FAIL else 'none')
    sys.exit(1 if FAIL else 0)
