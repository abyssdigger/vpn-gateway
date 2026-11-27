"""Strict B1 test-only runner; never provisions or repairs the host cgroup tree.

The trusted external provisioner supplies an exclusive, empty, writable
root and passes its pinned directory descriptor plus independently recorded
identity. A missing premise yields nonzero exit, not skip or fallback.
No production credentials, command payloads or arbitrary executable inputs.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import signal
import json
import os
import platform
import sys
from v2_writer_containment import Pin, Unavailable, preflight, run_generation, read_control, verify_empty_root

CASES = ('release', 'eof', 'invalid', 'timeout')
REQUIRED = frozenset({'cpu','memory','pids'})
NAMESPACES = ('mnt','pid','cgroup','user')


def namespace_ids():
    return tuple(os.stat(f'/proc/self/ns/{name}').st_ino for name in NAMESPACES)


SOURCE_FILES = ('v2_writer_containment.py', 'v2_containment_gate.py',
                'run_v2_containment_evidence.py', 'test_v2_writer_containment.py')

def source_digests():
    base = Path(__file__).resolve().parent
    return {name: hashlib.sha256((base/name).read_bytes()).hexdigest()
            for name in SOURCE_FILES}

def verify_case(case, result):
    # Require actual case-specific lifecycle evidence, not a truthy marker.
    success = case == 'release'
    wanted = {
        'case': 'released' if success else case,
        'reaped': 2 if success else 1,
        'removed': True,
        'placement_verified': True,
        'adopted_membership_verified': success,
        'probe_report_verified': success,
        'root_empty_verified': True,
        'reap_statuses': sorted([[os.CLD_EXITED, 0], [os.CLD_KILLED, int(signal.SIGKILL)]])
                          if success else [[os.CLD_EXITED, 43]],
    }
    if case not in CASES or type(result) is not dict or set(result) != set(wanted):
        raise Unavailable('invalid case evidence shape')
    for key, expected in wanted.items():
        actual = result[key]
        if type(actual) is not type(expected) or actual != expected:
            raise Unavailable('incomplete case evidence')
    for row in result['reap_statuses']:
        if type(row) is not list or len(row) != 2 or any(type(x) is not int for x in row):
            raise Unavailable('invalid reap status evidence')


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--root-fd', type=int, required=True)
    p.add_argument('--root-pin', type=int, nargs=3, required=True,
                   metavar=('DEV','INO','MNT_ID'))
    p.add_argument('--namespace-pins', type=int, nargs=4, required=True,
                   metavar=('MNT','PID','CGROUP','USER'))
    p.add_argument('--source-commit', required=True)
    a=p.parse_args(argv)
    results=[]
    phase='preflight'
    metadata={}
    try:
        if not re.fullmatch(r'[0-9a-f]{40}', a.source_commit):
            raise Unavailable('invalid declared source commit')
        metadata={'declared_source_commit':a.source_commit, 'source_sha256':source_digests(),
                  'kernel':platform.release()}
    except Exception:
        print(json.dumps({'status':'UNAVAILABLE','phase':'source','completed':0,'required':len(CASES)}))
        return 2
    try:
        if a.root_fd<=2 or os.getresuid()!=(0,0,0):
            raise Unavailable('invalid trusted owner/root FD')
        if namespace_ids()!=tuple(a.namespace_pins):
            raise Unavailable('namespace mismatch')
        expected=Pin(*a.root_pin)
        preflight(a.root_fd,expected,REQUIRED)
        verify_empty_root(a.root_fd)
        metadata['required_controllers']=sorted(REQUIRED)
        metadata['controllers_delegated']=REQUIRED <= set(read_control(a.root_fd,'cgroup.subtree_control').split())
        metadata['root_pin'] = list(a.root_pin)
        metadata['namespace_pins'] = list(a.namespace_pins)
        for case in CASES:
            phase=case
            if namespace_ids()!=tuple(a.namespace_pins):
                raise Unavailable('namespace changed')
            result=run_generation(a.root_fd,expected,REQUIRED,case=case)
            verify_case(case, result)
            results.append(result)
        phase='final'
        if namespace_ids()!=tuple(a.namespace_pins):
            raise Unavailable('namespace changed')
        preflight(a.root_fd,expected,REQUIRED)
        verify_empty_root(a.root_fd)
        if source_digests()!=metadata['source_sha256']:
            raise Unavailable('source changed during evidence')
    except Exception:
        # Bound diagnostics: no paths, tracebacks, child outputs or environment.
        print(json.dumps({'status':'UNAVAILABLE' if phase=='preflight' else 'FAIL','phase':phase,
                          'completed':len(results),'required':len(CASES),**metadata}))
        return 2
    print(json.dumps({'status':'PASS',**metadata,
                      'required':len(CASES),'skips':0,'cases':results}))
    return 0


if __name__=='__main__':
    sys.exit(main())
