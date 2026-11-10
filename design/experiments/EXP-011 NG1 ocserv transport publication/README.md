# EXP-011 — NG1 ROU transport publication with ocserv/OpenConnect

Status: **PREPARED — live run pending**

## Objective

Replace the EXP-010 dummy UDP listener with a real ocserv endpoint and prove that one
ROU publication facade carries both OpenConnect transport channels:

- TCP/TLS/CSTP control + backup data channel;
- UDP/DTLS primary data channel.

ocserv/OpenConnect deliberately uses both channels. The server provides the UDP/DTLS
endpoint after the TLS session is established, so this first experiment keeps one identical
published/internal port for both protocols.

## Topology

    remote OpenConnect client
             |
             | TCP 45443 + UDP 45443
             v
    host address :45443
             |
       EXP-011 relay
       TCP + UDP
             |
           exp11h
      192.0.2.1/30
             |
          veth pair
             |
           host0
      192.0.2.2/30
             |
        ROU netns
             |
       ocserv :45443
       TCP + UDP/DTLS
             |
          vpnsX

The existing production ocserv on host port 44443 is not modified.

## Why 45443 -> 45443

EXP-010 already proved generic UDP port translation independently of a VPN protocol.

OpenConnect negotiates its UDP/DTLS channel over the established TLS/CSTP session and the
server supplies the UDP endpoint. Therefore EXP-011 first isolates the architectural question:
can the ROU publication layer relay both real OC transports through the namespace boundary?

Port-number translation for protocols that advertise transport endpoints is a separate
protocol-semantic question and is not required for this proof.

## Preconditions

Server/test host:

- Debian with root;
- `ip netns`/veth support;
- ocserv installed;
- existing working ocserv configuration, certificates and user authentication;
- host TCP/UDP 45443 unused.

Remote client:

- working OpenConnect;
- server CA trusted;
- test hostname resolves to the server/test host address;
- credentials for the copied ocserv authentication setup.

## Temporary ocserv instance

The experiment should derive a temporary config from the known-good local ocserv config,
but must not modify the original file.

Required differences:

    tcp-port = 45443
    udp-port = 45443
    listen-host = 192.0.2.2
    udp-listen-host = 192.0.2.2

The temporary instance runs with:

    ip netns exec <exp11-ns> ocserv -f -c <temporary-config>

Certificate/key/authentication paths may remain the same because a network namespace does
not create a separate mount namespace.

Any runtime socket/pid paths that would collide with the production instance must be made
experiment-specific.

## Publication relay

Artifact:

    vpn-gateway-exp-011-oc-relay.py

It is intentionally a one-client proof relay, not production implementation.

TCP:

- accepts host-side connections on 45443;
- opens matching TCP connections to 192.0.2.2:45443;
- copies byte streams bidirectionally;
- permits multiple sequential/concurrent TCP sessions.

UDP:

- listens host-side on 45443;
- maintains one stable internal UDP socket toward 192.0.2.2:45443;
- associates the most recently observed external UDP peer with that internal socket;
- copies datagrams bidirectionally.

The one-client limitation matches this experiment's scope.

## Hypotheses

### H1 — TCP publication

OpenConnect reaches ocserv through the host-side TCP publication and establishes the
TLS/CSTP channel.

Evidence:

- relay logs at least one `TCP_ACCEPT` and `TCP_CONNECT`;
- client reaches authenticated/configured VPN state.

### H2 — UDP/DTLS publication

After CSTP establishment OpenConnect establishes DTLS through the host-side UDP publication.

Evidence:

- relay logs `UDP_PEER`, `UDP_C2S`, and `UDP_S2C`;
- client log reports DTLS established/connected.

### H3 — tunnel interface materialization

ocserv creates its configured VPN client interface inside the ROU namespace, not in main NS.

Evidence:

    ip -n <exp11-ns> -br link
    ip -n <exp11-ns> -br addr

shows the ocserv-created interface while main NS does not contain it.

### H4 — production isolation

The existing host ocserv on 44443 remains untouched and EXP-011 uses only its temporary
namespace, veth, temporary config and host publication port 45443.

### H5 — cleanup

Stopping EXP-011 removes experiment relay/processes, veth and network namespace without
modifying the production ocserv configuration.

## PASS criterion

EXP-011 is COMPLETE — PASS when H1-H5 are confirmed and the client explicitly shows both
TLS/CSTP and DTLS transport established through the publication relay.

## Deferred question

A mapping such as:

    45443/tcp>44443
    45443/udp>44443

may require additional handling because OpenConnect learns the UDP/DTLS endpoint through
the server protocol. EXP-011 does not assume arbitrary port translation is transparent for
such application-level advertised endpoints. That issue should be tested separately only
after the same-port real-protocol proof passes.
