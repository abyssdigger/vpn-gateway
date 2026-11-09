from __future__ import annotations

# Compatibility surface for the mechanically split RC2 implementation.
# Class/function bodies remain those of the RC2.5.1 monolith.

import os

from .constants import *
from .errors import *
from .models import *
from .config import ConfigLoader
from .profile import VpnProfile
from .kernel import KernelInterface, SubprocessKernelInterface
from .runtime import InstanceLock, SystemdNotifier
from .daemon import VpnGatewayDaemon
from .cli import _build_arg_parser, _configure_logging, _print_config_issues, main
