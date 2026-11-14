"""The portable archive root is one folder plus one entry file."""
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CHECK = os.path.join(ROOT, 'build', 'portable_layout.py')


def run(args):
    return subprocess.run([sys.executable, CHECK] + args, capture_output=True, text=True)


def fill(stage):
    os.makedirs(os.path.join(stage, 'qianxun', 'app'))
    os.makedirs(os.path.join(stage, 'qianxun', 'runtime'))
    for rel in ('qianxun/app/qianxun.py', 'qianxun/app/qianxun-256.png', 'qianxun/runtime/python'):
        path = os.path.join(stage, *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(b'x')
    entry = os.path.join(stage, 'qianxun.sh')
    with open(entry, 'w', encoding='utf-8') as fh:
        fh.write('#!/bin/sh\n')
    os.chmod(entry, 0o755)


def main():
    failed = []

    def check(ok, name):
        print(('PASS' if ok else 'FAIL'), name)
        if not ok:
            failed.append(name)

    tmp = tempfile.mkdtemp(prefix='qx-layout-')
    try:
        stage = os.path.join(tmp, 'stage')
        os.makedirs(stage)
        fill(stage)
        needs = ['qianxun/app/qianxun.py', 'qianxun/app/qianxun-256.png', 'qianxun/runtime/python']
        base = ['tree', stage, '--folder', 'qianxun', '--entry', 'qianxun.sh']
        for rel in needs:
            base.extend(['--need', rel])
        good = run(base)
        check(good.returncode == 0, 'complete tree passes')

        os.remove(os.path.join(stage, 'qianxun', 'app', 'qianxun-256.png'))
        missing = run(base)
        check(missing.returncode != 0 and 'qianxun-256.png' in missing.stderr, 'missing icon fails')
        with open(os.path.join(stage, 'qianxun', 'app', 'qianxun-256.png'), 'wb') as fh:
            fh.write(b'x')

        with open(os.path.join(stage, 'README.txt'), 'w', encoding='utf-8') as fh:
            fh.write('extra\n')
        extra = run(base)
        check(extra.returncode != 0 and 'top level' in extra.stderr, 'third top-level name fails')
        os.remove(os.path.join(stage, 'README.txt'))

        link = os.path.join(stage, 'qianxun', 'runtime', 'link')
        os.symlink('python', link)
        linked = run(base)
        check(linked.returncode != 0 and 'symlink' in linked.stderr, 'symlink fails')
        os.remove(link)

        zpath = os.path.join(tmp, 'ok.zip')
        with zipfile.ZipFile(zpath, 'w') as zf:
            for dirpath, _dirs, files in os.walk(stage):
                for name in files:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, stage).replace(os.sep, '/')
                    zf.write(full, rel)
        zargs = ['archive', zpath, '--folder', 'qianxun', '--entry', 'qianxun.sh']
        for rel in needs:
            zargs.extend(['--need', rel])
        zgood = run(zargs)
        check(zgood.returncode == 0, 'zip passes')

        tpath = os.path.join(tmp, 'ok.tar.gz')
        with tarfile.open(tpath, 'w:gz') as tf:
            for dirpath, _dirs, files in os.walk(stage):
                for name in files:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, stage).replace(os.sep, '/')
                    tf.add(full, rel)
        targs = ['archive', tpath, '--folder', 'qianxun', '--entry', 'qianxun.sh']
        for rel in needs:
            targs.extend(['--need', rel])
        tgood = run(targs)
        check(tgood.returncode == 0, 'tar.gz passes')

        note = run(['exe', os.path.join(stage, 'qianxun.sh')])
        check(note.returncode != 0 and 'no icon' in note.stderr, 'script is not an icon exe')
    finally:
        shutil.rmtree(tmp)

    if failed:
        print('FAILED', ', '.join(failed))
        return 1
    print('FAILED: none')
    return 0


if __name__ == '__main__':
    sys.exit(main())
