#!/usr/bin/env python3
"""Build QianXun-portable.exe = launcher(-DPORTABLE) + zlib payload (runtime\\ and app\\).
usage: pack_portable.py LAUNCHER_EXE RUNTIME_DIR APP_DIR OUTPUT_EXE
Format: see launcher.c (trailer 72 bytes, index entries u16 len|path|u64 size|u64 csize|u64 off|u32 crc)."""
import os, sys, zlib, struct, hashlib

def main(launcher, runtime, app, out):
    files = []
    for top, d in (("runtime", runtime), ("app", app)):
        for root, dirs, fs in os.walk(d):
            dirs.sort()
            for f in sorted(fs):
                if f.endswith(".pyc") and "__pycache__" not in root and top == "app":
                    continue
                if top == "app" and "__pycache__" in root:
                    continue
                full = os.path.join(root, f)
                rel = top + "/" + os.path.relpath(full, d).replace(os.sep, "/")
                files.append((rel, full))
    files.sort()
    exe = open(launcher, "rb").read()
    buf = bytearray(exe)
    base = len(buf)
    sha = hashlib.sha256()
    index = bytearray()
    for rel, full in files:
        data = open(full, "rb").read()
        comp = zlib.compress(data, 9)
        off = len(buf)
        buf += comp
        sha.update(comp)
        p = rel.encode("utf-8")
        assert all(c < 128 for c in p), "non-ASCII path: " + rel
        index += struct.pack("<H", len(p)) + p + struct.pack("<QQQI", len(data), len(comp), off, zlib.crc32(data) & 0xffffffff)
    idx_off = len(buf)
    buf += index
    sha.update(bytes(index))
    trailer = b"QXPAYLD1" + struct.pack("<QQII", idx_off, len(index), len(files), 0) + sha.digest() + b"1DLYAPXQ"
    assert len(trailer) == 72
    buf += trailer
    with open(out, "wb") as f:
        f.write(buf)
    print("packed %d files, payload %.1f MB -> %s (%.1f MB), hash12=%s" % (
        len(files), (len(buf) - base) / 1e6, out, len(buf) / 1e6, sha.hexdigest()[:12]))

if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
