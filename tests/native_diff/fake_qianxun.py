#!/usr/bin/env python3
"""Python stand-in for QianXun --cli (harness validation). Same CLI as the native exe; computes results with the oracle.
FAKE_FAULT=drop|extra|case|crash|footer|dup|loop|order  injects a bug so the harness' detection can be tested."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oracle_lib as ol  # noqa: E402

PFX = os.environ.get('WINEPREFIX', os.path.join(HERE, 'prefix64'))


def lin(p):
    if p[1:3] == ':\\':
        base = os.path.join(PFX, 'drive_c') if p[0].upper() == 'C' else '/'
        return os.path.join(base, *p[3:].split('\\')) if len(p) > 3 else base
    return p


def main():
    a = sys.argv[1:]
    kw = dict(text='', case=False, whole=False, path=False, regex=False, filter=0)
    roots, out = [], None
    i = 0
    while i < len(a):
        x = a[i]
        if x == '--root':
            roots.append(a[i + 1]); i += 1
        elif x == '--query':
            kw['text'] = a[i + 1]; i += 1
        elif x == '--out':
            out = a[i + 1]; i += 1
        elif x == '--filter':
            kw['filter'] = int(a[i + 1]); i += 1
        elif x in ('--case', '--whole', '--path', '--regex'):
            kw[x[2:]] = True
        i += 1
    fault = os.environ.get('FAKE_FAULT', '')
    paths = []
    for r in roots:
        idx, _ = ol.build_index(lin(r).rstrip('\\'), r.rstrip('\\'))
        t0 = time.time()
        p, err = ol.run_query(idx, kw)
        ms = int((time.time() - t0) * 1000)
        paths += p
    paths.sort(key=ol.sort_key)
    if fault == 'drop' and paths:
        paths = paths[1:]
    elif fault == 'extra':
        paths.append('C:\\corpus\\bogus_extra.txt')
    elif fault == 'case' and paths:
        paths[0] = paths[0].lower()
    elif fault == 'crash' and kw['text'].startswith('report'):
        sys.exit(3)
    elif fault == 'dup' and paths:
        paths.append(paths[0])
    elif fault == 'loop':
        paths.append('C:\\corpus\\special\\loop\\up\\special\\names\\readme')
    elif fault == 'order':
        paths = paths[::-1]
    lin_out = lin(out)
    os.makedirs(os.path.dirname(lin_out), exist_ok=True)
    with open(lin_out, 'w', encoding='utf-8', newline='\n') as f:
        for p in paths:
            f.write(p + '\n')
        if fault != 'footer':
            f.write('#count=%d #ms=%d\n' % (len(paths), ms))


main()
