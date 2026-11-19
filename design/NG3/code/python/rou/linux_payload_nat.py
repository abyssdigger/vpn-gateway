"""Strict Linux nft Driver for bounded payload NAT ownership."""
from __future__ import annotations
from dataclasses import dataclass
from .interface_inventory import parse_ip_link_inventory
from .linux_nft_scaffold import NftScriptRunner
from .nft_namespace_inventory import parse_nft_namespace_ruleset
from .payload_nat_desired import PayloadMasqueradeSpec, PayloadNatRuleSpec, PayloadProfileSnatSpec
from .payload_nat_mutation import PayloadNatPhysicalSnapshot

@dataclass(slots=True)
class LinuxPayloadNatBackend:
    runner: NftScriptRunner
    namespace: str
    def __post_init__(self):
        if not isinstance(self.namespace,str) or not self.namespace: raise ValueError("namespace must be a non-empty string")
    def _cmd(self,*args): return ("ip","netns","exec",self.namespace,*args)
    def _links(self): return parse_ip_link_inventory(self.runner.run(self._cmd("ip","-j","link","show")))
    def observe_nat_snapshot(self):
        before=self._links(); nft=parse_nft_namespace_ruleset(self.runner.run(self._cmd("nft","-j","list","ruleset"))); after=self._links()
        if before!=after: raise RuntimeError("interface identity inventory drift during nft observation")
        return PayloadNatPhysicalSnapshot(nft,before)
    def add_nat_rule(self,spec: PayloadNatRuleSpec):
        if isinstance(spec,PayloadMasqueradeSpec):
            script=("add rule ip vpn_gate payload_postrouting "+f"meta iif {spec.ingress.ifindex} meta oif {spec.egress.ifindex} "+'masquerade comment "vpn-gate:ng3:payload-nat-v1"\n')
        elif isinstance(spec,PayloadProfileSnatSpec):
            script=("add rule ip vpn_gate payload_postrouting "+f"ct mark {hex(spec.mark)} meta oif {spec.egress.ifindex} "+f"snat to {spec.source_address} "+'comment "vpn-gate:ng3:profile-snat-v1"\n')
        else: raise ValueError("spec must be a supported payload NAT rule")
        self.runner.run_script(self._cmd("nft","-f","-"),script)
    def delete_nat_rule(self,handle:int):
        if type(handle) is not int or handle<0: raise ValueError("handle must be a non-negative integer")
        self.runner.run(self._cmd("nft","delete","rule","ip","vpn_gate","payload_postrouting","handle",str(handle)))
