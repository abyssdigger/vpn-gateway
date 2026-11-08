from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from .config import ConfigLoader
from .constants import DEFAULT_CONFIG_PATH, LOG, VERSION
from .daemon import VpnGatewayDaemon
from .errors import ConfigError, GatewayError
from .kernel import SubprocessKernelInterface
from .models import ConfigCheckResult, ConfigIssueLevel

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vpn-gatewayd")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"config path (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate/lint config without runtime lock or kernel side effects",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    return parser


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _print_config_issues(result: ConfigCheckResult) -> None:
    order = {
        ConfigIssueLevel.ERROR: 0,
        ConfigIssueLevel.WARNING: 1,
        ConfigIssueLevel.NOTE: 2,
    }
    for issue in sorted(
        result.issues,
        key=lambda item: (order[item.level], item.location, item.message),
    ):
        print(
            f"{issue.level.name}: {issue.location}: {issue.message}",
            file=sys.stderr,
        )


def main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()
    args = _build_arg_parser().parse_args(argv)

    loader = ConfigLoader()

    if args.check_config:
        try:
            result = loader.check(args.config)
        except ConfigError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        _print_config_issues(result)
        return 1 if result.has_errors else 0

    # Deliberately do not load config here.  Normal lifecycle requires:
    # LOCK -> CLEANUP -> LOAD + VALIDATE -> APPLY -> RUN.
    kernel = SubprocessKernelInterface()
    daemon = VpnGatewayDaemon(
        config_path=args.config,
        kernel=kernel,
        config_loader=loader,
    )

    try:
        daemon.serve()
    except NotImplementedError as exc:
        LOG.error("skeleton method is not implemented: %s", exc)
        return 2
    except (GatewayError, OSError) as exc:
        LOG.error("%s", exc)
        return 1
    finally:
        kernel.close()

    return 0


