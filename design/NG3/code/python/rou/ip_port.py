"""Canonical IP transport-port scalar bounds shared across policy layers."""

IP_PORT_MIN = 1
IP_PORT_MAX = (1 << 16) - 1


def is_ip_port(value: object) -> bool:
    """Return whether value is a non-boolean integer in the IP port range."""
    return type(value) is int and IP_PORT_MIN <= value <= IP_PORT_MAX
