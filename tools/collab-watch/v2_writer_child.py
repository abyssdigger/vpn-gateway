"""Fixed reviewed staged entrypoint. No fork/exec, credential or remote effect."""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import stat
import sys
import time

MAX_CONTROL = 16384
CAPS = ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")
LIBC = ctypes.CDLL(None, use_errno=True)


def require(ok):
    if not ok:
        raise RuntimeError("staged setup/probe rejected")


def prctl(option, value=0):
    result = LIBC.prctl(option, ctypes.c_ulong(value), ctypes.c_ulong(0),
                        ctypes.c_ulong(0), ctypes.c_ulong(0))
    require(result >= 0)
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def remaining(deadline):
    result = deadline - time.monotonic()
    require(result > 0)
    return result


def send(sock, data, deadline):
    require(len(data) <= MAX_CONTROL)
    sock.settimeout(remaining(deadline))
    sock.sendall(data)


def receive(sock, deadline):
    data = bytearray()
    while len(data) <= MAX_CONTROL:
        sock.settimeout(remaining(deadline))
        part = sock.recv(min(4096, MAX_CONTROL + 1 - len(data)))
        if not part:
            break
        data.extend(part)
    require(0 < len(data) <= MAX_CONTROL)
    return json.loads(data.decode("utf-8"))


def setup(uid, gid, isolated, fds, writer):
    prctl(38, 1)  # PR_SET_NO_NEW_PRIVS
    if writer:
        prctl(4, 0)  # PR_SET_DUMPABLE, after exec and before bootstrap
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    report = dict(uid=os.getuid(), euid=os.geteuid(), gid=os.getgid(), egid=os.getegid(),
                  groups=os.getgroups(), caps={key: int(status[key].strip(), 16) for key in CAPS},
                  nnp=prctl(39), dumpable=prctl(3), fds=[])
    for entry in os.listdir("/proc/self/fd"):
        fd = int(entry)
        try:
            os.fstat(fd)
        except OSError as exc:
            require(exc.errno == errno.EBADF)
        else:
            report["fds"].append(fd)
    report["fds"].sort()
    require(report["fds"] == sorted({0, 1, 2, *fds})
            and report["uid"] == report["euid"] == uid and report["gid"] == report["egid"] == gid
            and report["nnp"] == 1 and (not writer or report["dumpable"] == 0)
            and dict(os.environ) == {"LC_ALL": "C.UTF-8"})
    if isolated:
        require(uid > 0 and gid > 0 and not report["groups"] and not any(report["caps"].values())
                and not os.access(__file__, os.W_OK) and not os.access(Path(__file__).parent, os.W_OK))
    return report


def load_dummy(spec, uid):
    if spec is None:
        return False, True
    require(type(spec) is dict and set(spec) == {"path", "sha256"})
    directory = os.stat(Path(spec["path"]).parent, follow_symlinks=False)
    require(stat.S_ISDIR(directory.st_mode) and stat.S_IMODE(directory.st_mode) == 0o700 and directory.st_uid == uid)
    fd = os.open(spec["path"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600 and info.st_uid == uid)
        secret = os.read(fd, 257)
        require(0 < len(secret) <= 256 and hashlib.sha256(secret).hexdigest() == spec["sha256"])
    finally:
        os.close(fd)
    clean = secret not in Path("/proc/self/cmdline").read_bytes() and all(secret not in k and secret not in v for k, v in os.environb.items())
    require(clean)
    return True, clean


def denied(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        return True
    else:
        os.close(fd)
        return False


def imports():
    # Interpreter started with -I -S -B; only this reviewed installation is added.
    root = Path(__file__).resolve().parent
    require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
            and Path.cwd() == root and all(os.path.isabs(p) for p in sys.path))
    sys.path.insert(0, str(root))
    import v2_writer_ipc as ipc
    return ipc


def worker_report(record):
    # No worker-originated text, arbitrary keys or unbounded values in diagnostics.
    ids = ("uid", "euid", "gid", "egid", "nnp", "dumpable")
    require(type(record) is dict and set(record) == set(ids) | {"groups", "caps", "fds", "file_denied", "proc_denied"})
    require(all(type(record[k]) is int and 0 <= record[k] <= 2**32-1 for k in ids))
    for key in ("groups", "fds"):
        values = record[key]
        require(type(values) is list and len(values) <= 64 and all(type(x) is int and 0 <= x <= 2**32-1 for x in values))
    caps = record["caps"]
    require(type(caps) is dict and set(caps) == set(CAPS) and all(type(x) is int and 0 <= x < 2**64 for x in caps.values()))
    require(all(record[k] is None or type(record[k]) is bool for k in ("file_denied", "proc_denied")))
    return record


def writer(uid, gid, isolated, args):
    fd, control_fd = map(int, args[:2])
    deadline = float(args[2])
    limits = tuple(map(int, args[3:]))
    require(len(limits) == 4)
    for kind, limit in zip((resource.RLIMIT_AS, resource.RLIMIT_CPU, resource.RLIMIT_NOFILE,
                            resource.RLIMIT_NPROC), limits):
        resource.setrlimit(kind, (limit, limit))
        require(resource.getrlimit(kind) == (limit, limit))
    info = setup(uid, gid, isolated, (fd, control_fd), True)
    info["limits"] = list(limits)
    with socket.socket(fileno=control_fd) as control, socket.socket(fileno=fd) as endpoint:
        bootstrap = receive(control, deadline)
        require(type(bootstrap) is dict and set(bootstrap) == {"session", "stores", "probe", "dummy"})
        dummy_ok, argv_clean = load_dummy(bootstrap["dummy"], uid)
        ipc = imports()
        session = ipc.SessionBinding(**bootstrap["session"])
        pin = hashlib.sha256(canonical([bootstrap["session"], bootstrap["stores"]]).encode()).hexdigest()
        probe = bootstrap["probe"]
        require(probe in {"ok", "bound", "memory", "cpu", "fd", "wall", "crash", "worker"})
        diagnostic = dict(setup=info, pin=pin, fault=None, validated=False, worker=None,
                          dummy_ok=dummy_ok, argv_clean=argv_clean)
        send(control, b"R", deadline)

        def handler(request, binding):
            require(binding == session)
            send(control, b"E", deadline)
            if probe == "bound":
                from v2_actuator import _bound
                data = _bound(request["original"])[0]
                require(data["role"] == binding.role and data["incarnation"] == binding.incarnation)
                diagnostic["validated"] = True
            elif probe == "worker":
                require(len(request["original"]) <= 4096)
                record = json.loads(request["original"])
                # Only a fixed reviewed dummy worker report, never identity authority.
                diagnostic["worker"] = worker_report(record)
            elif probe == "memory":
                try:
                    bytearray(limits[0])
                except MemoryError:
                    diagnostic["fault"] = "MEMORY"
                raise RuntimeError("synthetic memory fault")
            elif probe == "fd":
                opened = []
                try:
                    while True:
                        opened.append(os.open("/dev/null", os.O_RDONLY))
                except OSError as exc:
                    require(exc.errno == errno.EMFILE)
                    diagnostic["fault"] = "FD"
                finally:
                    for item in opened:
                        os.close(item)
                raise RuntimeError("synthetic descriptor fault")
            elif probe == "cpu":
                while True:
                    pass
            elif probe == "wall":
                time.sleep(max(0, deadline-time.monotonic()) + 2)
            elif probe == "crash":
                os._exit(23)
            # Explicit synthetic no-effect result; no real writer or store is invoked.
            return dict(state="NO_ATTEMPT", code="TRUSTED_INGRESS_REJECTED", action_key=None)

        outcome = ipc.WriterInvocation(session, handler).serve(endpoint, deadline=deadline)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        diagnostic.update(rss_kib=usage.ru_maxrss, cpu_seconds=usage.ru_utime+usage.ru_stime,
                          outcome=outcome["state"])
        send(control, b"D" + canonical(diagnostic).encode(), deadline)


def worker(uid, gid, isolated, args):
    fd, deadline, abrupt, path, pid, control_fd = int(args[0]), float(args[1]), int(args[2]), args[3], int(args[4]), int(args[5])
    report = setup(uid, gid, isolated, (fd,), False)
    if abrupt:
        os._exit(20)
    report["file_denied"] = denied(path) if path else None
    report["proc_denied"] = (all(denied(f"/proc/{pid}/{target}") for target in
                                  ("environ", "mem", f"fd/{control_fd}")) if path and pid else None)
    require(not path or report["file_denied"] is True and report["proc_denied"] is True)
    ipc = imports()
    outcome = ipc.exchange(socket.socket(fileno=fd), dict(original=canonical(report), reconcile_only=False),
                           deadline=deadline)
    require(outcome == {"state": "RESULT", "result": {"state": "NO_ATTEMPT",
            "code": "TRUSTED_INGRESS_REJECTED", "action_key": None}})


def main():
    kind, uid, gid, isolated = sys.argv[1:5]
    require(kind in ("writer", "worker") and isolated in ("0", "1"))
    (writer if kind == "writer" else worker)(int(uid), int(gid), isolated == "1", sys.argv[5:])


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # No exception/request/secret text on stdout, stderr or IPC.
        os._exit(24)
