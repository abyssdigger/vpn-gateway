from __future__ import annotations

import json
import re

from rou.command_backend import CommandResult
from rou.nft_policy import (
    NftTableDesiredState,
    _numeric_interface_refs_from_definition,
    normalize_nft_list,
)


class FakeNftBackend:
    """Small in-memory backend for Planner/status tests.

    It emulates only the production nft observation/apply contract. Routing/sysctl commands
    are recorded and otherwise succeed.
    """

    def __init__(
        self,
        filter_state: NftTableDesiredState,
        nat_state: NftTableDesiredState,
    ):
        self.calls = []
        self.tables = {
            filter_state.name: (
                filter_state.canonical,
                filter_state.numeric_interface_refs,
            ),
            nat_state.name: (
                nat_state.canonical,
                nat_state.numeric_interface_refs,
            ),
        }

    @staticmethod
    def _table_name(argv):
        try:
            index = argv.index("table")
        except ValueError:
            return None
        if index + 2 >= len(argv):
            return None
        return argv[index + 2]

    @staticmethod
    def _json_for_refs(refs):
        items = [{"metainfo": {"json_schema_version": 1}}]
        for kind, value in refs:
            items.append(
                {
                    "rule": {
                        "expr": [
                            {
                                "match": {
                                    "op": "==",
                                    "left": {"meta": {"key": kind}},
                                    "right": str(value),
                                }
                            }
                        ]
                    }
                }
            )
        return json.dumps({"nftables": items})

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append((argv, input_text, check))

        # nft -f - : replace one owned table.
        if argv[-3:] == ("nft", "-f", "-") and input_text is not None:
            match = re.search(r"table\s+ip\s+(vpng_filter|vpng_nat)\s*\{", input_text)
            if match is None:
                return CommandResult(argv, 1, "", "unsupported nft script")
            table = match.group(1)
            definition = input_text[match.start():]
            canonical = normalize_nft_list(definition)
            refs = _numeric_interface_refs_from_definition(definition)
            self.tables[table] = (canonical, refs)
            return CommandResult(argv, 0, "", "")

        if argv[-4:] == ("nft", "-j", "-n", "list") or (
            "nft" in argv and "list" in argv and "ruleset" in argv
        ):
            items = [
                {"metainfo": {"json_schema_version": 1}}
            ]
            for name in sorted(self.tables):
                items.append(
                    {"table": {"family": "ip", "name": name}}
                )
            return CommandResult(
                argv,
                0,
                json.dumps({"nftables": items}),
                "",
            )

        if "nft" in argv and "delete" in argv and "table" in argv:
            table = self._table_name(argv)
            if table in self.tables:
                del self.tables[table]
                return CommandResult(argv, 0, "", "")
            return CommandResult(argv, 1, "", "No such file or directory")

        # Existence probe / table observation.
        if "nft" in argv and "list" in argv and "table" in argv:
            table = self._table_name(argv)
            if table not in self.tables:
                return CommandResult(argv, 1, "", "No such file or directory")

            canonical, refs = self.tables[table]
            if "-j" in argv:
                return CommandResult(
                    argv,
                    0,
                    self._json_for_refs(refs),
                    "",
                )
            return CommandResult(argv, 0, canonical + "\n", "")

        return CommandResult(argv, 0, "", "")
