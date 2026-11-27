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



def _systemctl(*args):
    """Read only bounded properties of the fixed evidence service."""
    import subprocess
    result = subprocess.run(
        ['/usr/bin/systemctl', *args], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding='ascii', timeout=5,
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    if len(result.stdout) > 4096:
        raise Unavailable('oversized service observation')
    return result.stdout


def _enable_required(fd):
    from v2_writer_containment import pin
    import stat
    if not REQUIRED <= set(read_control(fd, 'cgroup.controllers').split()):
        raise Unavailable('missing required controllers')
    if read_control(fd, 'cgroup.procs').strip():
        raise Unavailable('internal processes prevent delegation')
    missing = REQUIRED - set(read_control(fd, 'cgroup.subtree_control').split())
    if missing:
        control = os.open('cgroup.subtree_control',
                          os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=fd)
        try:
            st = os.fstat(control)
            if (pin(control).mount_id != pin(fd).mount_id or st.st_uid != 0
                    or st.st_mode & 0o022 or not stat.S_ISREG(st.st_mode)):
                raise Unavailable('unsafe delegation control')
            data = ' '.join('+' + name for name in sorted(missing)).encode('ascii')
            if os.write(control, data) != len(data):
                raise Unavailable('incomplete delegation write')
        finally:
            os.close(control)
    if not REQUIRED <= set(read_control(fd, 'cgroup.subtree_control').split()):
        raise Unavailable('delegation not established')


def provision_systemd(unit, source_commit):
    """Fixed GitHub-hosted disposable B1 vehicle, never a general provisioner.

    Called as the transient unit's main process. Trust the reviewed checkout,
    pinned system interpreter and disposable hosted systemd manager, not arbitrary
    worker inputs. Only the fresh test sibling becomes the runner's owned root.
    Outer service teardown remains separate from B1 evidence.
    """
    from v2_writer_containment import pin, child_directories, resolve_cgroup_path
    import stat
    mount_fd = slice_fd = unit_fd = manager_fd = test_fd = -1
    phase = 'service-identity'
    try:
        if (not re.fullmatch(r'vpng-b1-[1-9][0-9]{0,19}-[1-9][0-9]{0,9}\.service', unit)
                or not re.fullmatch(r'[0-9a-f]{40}', source_commit)
                or os.getresuid() != (0, 0, 0)
                or os.getresgid() != (0, 0, 0)
                or len(os.listdir('/proc/self/task')) != 1):
            raise Unavailable('invalid fixed service inputs')
        if (Path('/proc/1/comm').read_text().strip() != 'systemd'
                or os.path.realpath('/proc/1/exe') not in
                ('/usr/lib/systemd/systemd', '/lib/systemd/systemd')
                or namespace_ids() != tuple(os.stat(f'/proc/1/ns/{n}').st_ino
                                            for n in NAMESPACES)):
            raise Unavailable('not the host systemd namespace')
        version = _systemctl('--version').splitlines()[0]
        match = re.match(r'systemd ([0-9]+)(?:\s|$)', version)
        if not match or len(version) > 200:
            raise Unavailable('invalid systemd version')
        print(json.dumps({'vehicle': 'systemd-delegated-test', 'systemd_version': version}),
              flush=True)
        if int(match[1]) < 254:
            raise Unavailable('DelegateSubgroup unsupported')
        group = '/system.slice/' + unit
        fields = ('MainPID', 'ControlGroup', 'Delegate', 'User', 'Slice')
        observed = _systemctl('show', *('--property=' + f for f in fields), unit)
        rows = [line.split('=', 1) for line in observed.splitlines()]
        wanted = {'MainPID': str(os.getpid()), 'ControlGroup': group,
                  'Delegate': 'yes', 'User': 'root', 'Slice': 'system.slice'}
        if len(rows) != len(wanted) or dict(rows) != wanted:
            raise Unavailable('unexpected unit properties')
        membership = Path('/proc/self/cgroup').read_text(encoding='ascii')
        if membership != '0::' + group + '/manager\n':
            raise Unavailable('manager subgroup mismatch')
        phase = 'delegation-preflight'
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        mount_fd = os.open('/sys/fs/cgroup', flags)
        slice_fd = os.open('system.slice', flags, dir_fd=mount_fd)
        unit_fd = os.open(unit, flags, dir_fd=slice_fd)
        manager_fd = os.open('manager', flags, dir_fd=unit_fd)
        mount_id = pin(mount_fd).mount_id
        mounts = Path('/proc/self/mountinfo').read_text(encoding='utf-8')
        unit_path, manager_path = resolve_cgroup_path(
            mounts, membership, os.readlink(f'/proc/self/fd/{unit_fd}'),
            mount_id, membership_check=True)
        if str(unit_path) != group or str(manager_path) != group + '/manager':
            raise Unavailable('unsafe delegation mapping')
        for fd in (mount_fd, slice_fd, unit_fd, manager_fd):
            st = os.fstat(fd)
            if (pin(fd).mount_id != mount_id or st.st_uid != 0
                    or st.st_mode & 0o022 or not stat.S_ISDIR(st.st_mode)
                    or os.fstatvfs(fd).f_flag & os.ST_RDONLY):
                raise Unavailable('unprotected delegation path')
        if (read_control(unit_fd, 'cgroup.type').strip() != 'domain'
                or read_control(unit_fd, 'cgroup.procs').strip()
                or read_control(manager_fd, 'cgroup.procs').split() != [str(os.getpid())]
                or child_directories(manager_fd)
                or not {'manager'} <= child_directories(unit_fd) <= {'manager', '.control'}
                or not REQUIRED <= set(read_control(unit_fd, 'cgroup.controllers').split())
                or len(os.listdir('/proc/self/task')) != 1):
            raise Unavailable('invalid exclusive service inventory')
        phase = 'test-root'
        # Never adopt existing test directories; no repair above this unit.
        _enable_required(unit_fd)
        os.mkdir('test', 0o700, dir_fd=unit_fd)
        test_fd = os.open('test', flags, dir_fd=unit_fd)
        if (pin(test_fd).mount_id != mount_id
                or os.readlink(f'/proc/self/fd/{test_fd}') != '/sys/fs/cgroup' + group + '/test'):
            raise Unavailable('test root identity mismatch')
        verify_empty_root(test_fd)
        _enable_required(test_fd)
        expected = pin(test_fd)
        ns = namespace_ids()
        preflight(test_fd, expected, REQUIRED)
        verify_empty_root(test_fd)
        if ns != tuple(os.stat(f'/proc/1/ns/{n}').st_ino for n in NAMESPACES):
            raise Unavailable('namespace drift')
        # No ancestor/control directory FD is passed into the strict runner.
        for fd in (manager_fd, unit_fd, slice_fd, mount_fd):
            os.close(fd)
        manager_fd = unit_fd = slice_fd = mount_fd = -1
        for name in os.listdir('/proc/self/fd'):
            fd = int(name)
            if fd > 2 and fd != test_fd:
                try:
                    os.close(fd)
                except OSError as exc:
                    import errno
                    if exc.errno != errno.EBADF:
                        raise
        return main(['--root-fd', str(test_fd), '--root-pin',
                     str(expected.dev), str(expected.ino), str(expected.mount_id),
                     '--namespace-pins', *(str(x) for x in ns),
                     '--source-commit', source_commit])
    except Exception:
        print(json.dumps({'status': 'UNAVAILABLE', 'phase': phase,
                          'completed': 0, 'required': len(CASES)}), flush=True)
        return 2
    finally:
        for fd in (test_fd, manager_fd, unit_fd, slice_fd, mount_fd):
            if fd >= 0:
                os.close(fd)


if __name__=='__main__':
    sys.exit(main())
