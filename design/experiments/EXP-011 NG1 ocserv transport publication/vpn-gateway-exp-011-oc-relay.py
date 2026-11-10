#!/usr/bin/env python3
"""EXP-011: one-client TCP+UDP publication relay for ocserv.

Not production code. It deliberately implements only the minimum needed to prove:
  host TCP/UDP :PORT -> relay -> ocserv in ROU netns :PORT
"""

import argparse
import selectors
import socket
import threading
import time


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


def tcp_session(client: socket.socket, peer, target) -> None:
    print(f"TCP_ACCEPT peer={peer[0]}:{peer[1]}", flush=True)
    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    upstream.settimeout(10)
    upstream.connect(target)
    upstream.settimeout(None)
    print(f"TCP_CONNECT target={target[0]}:{target[1]}", flush=True)

    a = threading.Thread(target=pump, args=(client, upstream), daemon=True)
    b = threading.Thread(target=pump, args=(upstream, client), daemon=True)
    a.start()
    b.start()
    a.join()
    b.join()
    client.close()
    upstream.close()
    print(f"TCP_CLOSE peer={peer[0]}:{peer[1]}", flush=True)


def tcp_loop(bind_addr: str, port: int, target_addr: str) -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((bind_addr, port))
    listener.listen(32)
    print(f"TCP_LISTEN {bind_addr}:{port} -> {target_addr}:{port}", flush=True)
    while True:
        client, peer = listener.accept()
        threading.Thread(
            target=tcp_session,
            args=(client, peer, (target_addr, port)),
            daemon=True,
        ).start()


def udp_loop(bind_addr: str, source_addr: str, port: int, target_addr: str) -> None:
    external = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    external.bind((bind_addr, port))

    internal = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    internal.bind((source_addr, 0))
    internal.connect((target_addr, port))

    selector = selectors.DefaultSelector()
    selector.register(external, selectors.EVENT_READ, "external")
    selector.register(internal, selectors.EVENT_READ, "internal")

    client_peer = None
    print(
        f"UDP_LISTEN {bind_addr}:{port} -> {target_addr}:{port} "
        f"source={internal.getsockname()[0]}:{internal.getsockname()[1]}",
        flush=True,
    )

    while True:
        for key, _ in selector.select(timeout=5):
            if key.data == "external":
                data, peer = external.recvfrom(65535)
                if client_peer != peer:
                    client_peer = peer
                    print(f"UDP_PEER peer={peer[0]}:{peer[1]}", flush=True)
                internal.send(data)
                print(f"UDP_C2S bytes={len(data)}", flush=True)
            else:
                data = internal.recv(65535)
                if client_peer is not None:
                    external.sendto(data, client_peer)
                    print(f"UDP_S2C bytes={len(data)}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--listen-address", default="0.0.0.0")
    p.add_argument("--internal-source-address", required=True)
    p.add_argument("--target-address", required=True)
    p.add_argument("--port", type=int, required=True)
    args = p.parse_args()

    tcp = threading.Thread(
        target=tcp_loop,
        args=(args.listen_address, args.port, args.target_address),
        daemon=True,
    )
    udp = threading.Thread(
        target=udp_loop,
        args=(
            args.listen_address,
            args.internal_source_address,
            args.port,
            args.target_address,
        ),
        daemon=True,
    )
    tcp.start()
    udp.start()

    print("EXP011_RELAY_READY", flush=True)
    while tcp.is_alive() and udp.is_alive():
        time.sleep(1)
    raise SystemExit("relay worker stopped")


if __name__ == "__main__":
    main()
