#!/usr/bin/env python3
from __future__ import annotations

import argparse
import selectors
import socket
import threading
import time
from dataclasses import dataclass

UDP_IDLE_SECONDS = 600.0


def log(msg: str) -> None:
    print(msg, flush=True)


def pump(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for sock in (src, dst):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def tcp_session(client: socket.socket, peer: tuple[str, int], target: tuple[str, int]) -> None:
    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    log(f"TCP_ACCEPT peer={peer[0]}:{peer[1]}")
    try:
        upstream.settimeout(10)
        upstream.connect(target)
        upstream.settimeout(None)
        log(f"TCP_CONNECT peer={peer[0]}:{peer[1]} target={target[0]}:{target[1]}")
        a = threading.Thread(target=pump, args=(client, upstream), daemon=True)
        b = threading.Thread(target=pump, args=(upstream, client), daemon=True)
        a.start(); b.start(); a.join(); b.join()
    except OSError as exc:
        log(f"TCP_ERROR peer={peer[0]}:{peer[1]} error={exc}")
    finally:
        client.close(); upstream.close()
        log(f"TCP_CLOSE peer={peer[0]}:{peer[1]}")


def tcp_loop(bind_addr: str, port: int, target_addr: str) -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((bind_addr, port))
    listener.listen(64)
    log(f"TCP_LISTEN {bind_addr}:{port} -> {target_addr}:{port}")
    while True:
        client, peer = listener.accept()
        threading.Thread(target=tcp_session, args=(client, peer, (target_addr, port)), daemon=True).start()


@dataclass
class UdpAssociation:
    sock: socket.socket
    peer: tuple[str, int]
    last_seen: float


def udp_loop(bind_addr: str, source_addr: str, port: int, target_addr: str) -> None:
    external = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    external.bind((bind_addr, port))
    external.setblocking(False)

    sel = selectors.DefaultSelector()
    sel.register(external, selectors.EVENT_READ, ("external", None))
    by_peer: dict[tuple[str, int], UdpAssociation] = {}
    by_fd: dict[int, UdpAssociation] = {}
    log(f"UDP_LISTEN {bind_addr}:{port} -> {target_addr}:{port}")

    def create(peer: tuple[str, int]) -> UdpAssociation:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((source_addr, 0))
        sock.connect((target_addr, port))
        sock.setblocking(False)
        assoc = UdpAssociation(sock=sock, peer=peer, last_seen=time.monotonic())
        by_peer[peer] = assoc
        by_fd[sock.fileno()] = assoc
        sel.register(sock, selectors.EVENT_READ, ("internal", sock.fileno()))
        src = sock.getsockname()
        log(f"UDP_ASSOC peer={peer[0]}:{peer[1]} source={src[0]}:{src[1]} target={target_addr}:{port}")
        return assoc

    def expire(now: float) -> None:
        for assoc in list(by_peer.values()):
            if now - assoc.last_seen < UDP_IDLE_SECONDS:
                continue
            fd = assoc.sock.fileno()
            try:
                sel.unregister(assoc.sock)
            except Exception:
                pass
            by_peer.pop(assoc.peer, None)
            by_fd.pop(fd, None)
            assoc.sock.close()
            log(f"UDP_EXPIRE peer={assoc.peer[0]}:{assoc.peer[1]}")

    while True:
        events = sel.select(timeout=5)
        now = time.monotonic()
        for key, _ in events:
            kind, token = key.data
            if kind == "external":
                data, peer = external.recvfrom(65535)
                assoc = by_peer.get(peer) or create(peer)
                assoc.last_seen = now
                assoc.sock.send(data)
                log(f"UDP_C2S peer={peer[0]}:{peer[1]} bytes={len(data)}")
            else:
                assoc = by_fd.get(token)
                if assoc is None:
                    continue
                data = assoc.sock.recv(65535)
                assoc.last_seen = now
                external.sendto(data, assoc.peer)
                log(f"UDP_S2C peer={assoc.peer[0]}:{assoc.peer[1]} bytes={len(data)}")
        expire(now)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--listen-address", default="0.0.0.0")
    p.add_argument("--internal-source-address", required=True)
    p.add_argument("--target-address", required=True)
    p.add_argument("--port", required=True, type=int)
    a = p.parse_args()
    tcp = threading.Thread(target=tcp_loop, args=(a.listen_address, a.port, a.target_address), daemon=True)
    udp = threading.Thread(target=udp_loop, args=(a.listen_address, a.internal_source_address, a.port, a.target_address), daemon=True)
    tcp.start(); udp.start()
    log("ROU_V0_RELAY_READY")
    while tcp.is_alive() and udp.is_alive():
        time.sleep(1)
    raise SystemExit("publication relay worker stopped")


if __name__ == "__main__":
    main()
