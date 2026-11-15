"""Verify a release ZIP with the actual previous updater, without changing the installed app."""
import argparse
import hashlib
import importlib.util
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--old-source', required=True)
parser.add_argument('--package', required=True)
args = parser.parse_args()
old_source = Path(args.old_source).resolve()
package = Path(args.package).resolve()
original = old_source.read_bytes()
spec = importlib.util.spec_from_file_location('previous_qianxun', old_source)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
fr, to, files = old._read_pack(str(package))
assert old._ver_tuple(old.VERSION) < to, 'Release version must exceed the installed version'
assert fr <= old._ver_tuple(old.VERSION), 'Installed version is outside the supported upgrade range'

with tempfile.TemporaryDirectory(prefix='qx-release-') as td:
    install = Path(td) / 'QianXun'
    target = install / 'app' / 'qianxun.py'
    target.parent.mkdir(parents=True)
    target.write_bytes(original)
    consent = []
    def confirm(info):
        consent.append(info)
        return True
    result = old.apply_upgrade(str(package), str(install), confirm, old.VERSION)
    assert result.outcome == 'applied', (result.outcome, result.reason)
    assert result.needs_restart
    assert len(consent) == 1
    assert target.read_bytes() == files['app/qianxun.py']
    repeat = old.apply_upgrade(str(package), str(install), confirm, old._fmt_ver(to))
    assert repeat.outcome == 'already', repeat.outcome
    assert len(consent) == 1, 'Idempotent reapply should not ask to overwrite'
    # A newer installed release must not be overwritten by this older ZIP.
    newer = (to[0], to[1], to[2] + 1)
    newer_source = ("VERSION = '%s'\n" % old._fmt_ver(newer)).encode('ascii')
    target.write_bytes(newer_source)
    refused = old.apply_upgrade(str(package), str(install), confirm, old._fmt_ver(newer))
    assert refused.outcome == 'refused' and refused.reason == 'version'
    assert target.read_bytes() == newer_source
assert old_source.read_bytes() == original, 'Installed source must remain untouched'
print('PASS %s -> %s: applied; repeat: already; downgrade: refused; installation untouched' %
      (old.VERSION, old._fmt_ver(to)))
print('SHA256', hashlib.sha256(package.read_bytes()).hexdigest())
