# EXP-010 phase A — local relay smoke result

**Status:** PASS
**Environment:** ChatGPT execution container
**Topology:** single network namespace; rootless UDP sockets only
**Purpose:** validate publication/relay/listener/sink workflow before adding a private ROU network namespace

Command:

    python3 vpn-gateway-exp-010-local-smoke.py

Observed output:

    CLIENT_TX: b'exp010-local-smoke'
    RELAY_RX: ('127.0.0.1', 40186) b'exp010-local-smoke'
    RELAY_FWD: ('127.0.0.1', 55129) -> ('127.0.0.1', 17890)
    INTERNAL_RX: ('127.0.0.1', 55129) b'exp010-local-smoke'
    INTERNAL_TX: b'PAYLOAD:exp010-local-smoke'
    INTERNAL_ACK: b'ACK:exp010-local-smoke'
    INTERNAL_PASS: ok
    RELAY_RETURN: ('127.0.0.1', 17890) b'ACK:exp010-local-smoke'
    RELAY_TX: ('127.0.0.1', 40186) b'ACK:exp010-local-smoke'
    RELAY_PASS: ok
    SINK_RX: ('127.0.0.1', 56150) b'PAYLOAD:exp010-local-smoke'
    SINK_PASS: ok
    CLIENT_RX: ('127.0.0.1', 15678) b'ACK:exp010-local-smoke'
    CLIENT_PASS: ok
    OVERALL=PASS

Interpretation:

- a datagram sent to the published port reached the relay;
- the relay forwarded the exact input payload to the internal listener port;
- the internal listener observed that input;
- the internal listener emitted a different payload whose contents depended on the received input;
- a separate sink observed that dependent payload;
- the listener reply returned through the same relay socket to the original client.

This does **not** prove network-namespace traversal. It validates only the socket/relay workflow that EXP-010 phase B will place across the ROU namespace boundary.
