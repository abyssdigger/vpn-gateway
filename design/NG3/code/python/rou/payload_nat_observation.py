"""Read-only authoritative observation and comparison of owned payload NAT rules."""

from __future__ import annotations
from dataclasses import dataclass
from ipaddress import IPv4Address
import json
from typing import Iterable
from .interface_identity import InterfaceIdentity
from .nft_namespace_inventory import NftNamespaceObject, NftNamespaceObservation
from .nft_payload_scaffold import PAYLOAD_POSTROUTING_CHAIN, compare_payload_nft_scaffold
from .payload_nat_desired import PayloadMasqueradeSpec, PayloadNatDesiredState, PayloadNatRuleSpec, PayloadProfileSnatSpec

PAYLOAD_NAT_RULE_COMMENT = "vpn-gate:ng3:payload-nat-v1"
PROFILE_SNAT_RULE_COMMENT = "vpn-gate:ng3:profile-snat-v1"

class PayloadNatObservationError(ValueError): pass

@dataclass(frozen=True, slots=True)
class ObservedPayloadMasquerade:
    handle: int
    ingress: InterfaceIdentity | int
    egress: InterfaceIdentity | int
    @property
    def stale(self): return type(self.ingress) is int or type(self.egress) is int

@dataclass(frozen=True, slots=True)
class ObservedPayloadProfileSnat:
    handle: int
    mark: int
    egress: InterfaceIdentity | int
    source_address: IPv4Address
    @property
    def stale(self): return type(self.egress) is int

ObservedPayloadNatRule = ObservedPayloadMasquerade | ObservedPayloadProfileSnat

@dataclass(frozen=True, slots=True)
class PayloadNatRuleConflict:
    handle: int | None
    reason: str

@dataclass(frozen=True, slots=True)
class PayloadNatComparison:
    confirmed: tuple[PayloadNatRuleSpec, ...]
    missing: tuple[PayloadNatRuleSpec, ...]
    stale: tuple[ObservedPayloadNatRule, ...]
    conflicts: tuple[PayloadNatRuleConflict, ...]
    @property
    def conflict_free(self): return not self.conflicts

def compare_payload_nat(observation, interfaces: Iterable[InterfaceIdentity], desired):
    if not isinstance(observation, NftNamespaceObservation): raise PayloadNatObservationError("observation must be NftNamespaceObservation")
    if not isinstance(desired, PayloadNatDesiredState): raise PayloadNatObservationError("desired must be PayloadNatDesiredState")
    if not compare_payload_nft_scaffold(observation).scaffold_confirmed: raise PayloadNatObservationError("NAT table/scaffold ownership is not confirmed")
    by_name={}; by_index={}
    for identity in interfaces:
        if not isinstance(identity, InterfaceIdentity): raise PayloadNatObservationError("inventory must contain InterfaceIdentity")
        if identity.ifname in by_name or identity.ifindex in by_index: raise PayloadNatObservationError("ambiguous current interface inventory")
        by_name[identity.ifname]=identity; by_index[identity.ifindex]=identity
    expected={}
    for spec in desired.rules:
        key=_desired_key(spec, by_name)
        if key in expected: raise PayloadNatObservationError("duplicate desired physical NAT rule")
        expected[key]=spec
    observed=[]; conflicts=[]; handles=set()
    for item in observation.objects:
        if item.kind!="rule": continue
        try: payload=_rule_payload(item)
        except PayloadNatObservationError as exc: conflicts.append(PayloadNatRuleConflict(None,str(exc))); continue
        if payload.get("chain") != PAYLOAD_POSTROUTING_CHAIN: continue
        handle=payload.get("handle")
        if type(handle) is not int or handle < 0: conflicts.append(PayloadNatRuleConflict(None,"invalid NAT rule handle")); continue
        if handle in handles: conflicts.append(PayloadNatRuleConflict(handle,"duplicate NAT rule handle")); continue
        handles.add(handle)
        try: observed.append(_decode_rule(payload,by_name,by_index))
        except PayloadNatObservationError as exc: conflicts.append(PayloadNatRuleConflict(handle,str(exc)))
    physical=set(); confirmed_keys=set(); stale=[]
    for rule in observed:
        key=_observed_key(rule)
        if key in physical: conflicts.append(PayloadNatRuleConflict(rule.handle,"duplicate physical NAT rule")); continue
        physical.add(key)
        if rule.stale: stale.append(rule)
        elif key in expected: confirmed_keys.add(key)
        else: stale.append(rule)
    confirmed=tuple(spec for key,spec in expected.items() if key in confirmed_keys)
    missing=tuple(spec for key,spec in expected.items() if key not in confirmed_keys)
    return PayloadNatComparison(confirmed,missing,tuple(stale),tuple(conflicts))

def _desired_key(spec, by_name):
    current=set(by_name.values())
    if isinstance(spec,PayloadMasqueradeSpec):
        if spec.ingress not in current or spec.egress not in current: raise PayloadNatObservationError("desired NAT endpoints are not current")
        return ("masquerade",spec.ingress,spec.egress)
    if isinstance(spec,PayloadProfileSnatSpec):
        if spec.egress not in current: raise PayloadNatObservationError("desired Profile SNAT egress is not current")
        return ("snat",spec.mark,spec.egress,spec.source_address)
    raise PayloadNatObservationError("invalid desired NAT spec")

def _observed_key(rule):
    if isinstance(rule,ObservedPayloadMasquerade): return ("masquerade",rule.ingress,rule.egress)
    return ("snat",rule.mark,rule.egress,rule.source_address)

def _rule_payload(item: NftNamespaceObject):
    try: row=json.loads(item.canonical_json)
    except (TypeError,ValueError): raise PayloadNatObservationError("invalid canonical NAT rule JSON") from None
    if not isinstance(row,dict) or set(row)!={"rule"} or not isinstance(row["rule"],dict): raise PayloadNatObservationError("invalid canonical NAT rule shape")
    return row["rule"]

def _decode_rule(payload,by_name,by_index):
    allowed={"family","table","chain","handle","comment","expr"}
    if set(payload)-allowed: raise PayloadNatObservationError("unsupported NAT rule fields")
    if (payload.get("family"),payload.get("table"),payload.get("chain")) != ("ip","vpn_gate",PAYLOAD_POSTROUTING_CHAIN): raise PayloadNatObservationError("wrong NAT rule scope")
    expr=payload.get("expr")
    if not isinstance(expr,list) or len(expr)!=3: raise PayloadNatObservationError("NAT rule must contain exactly three expressions")
    if payload.get("comment")==PAYLOAD_NAT_RULE_COMMENT:
        ingress=_match_interface(expr[0],"iif",by_name,by_index); egress=_match_interface(expr[1],"oif",by_name,by_index)
        if expr[2] not in ({"masquerade":None},{"masquerade":{}}): raise PayloadNatObservationError("unsupported masquerade action")
        return ObservedPayloadMasquerade(payload["handle"],ingress,egress)
    if payload.get("comment")==PROFILE_SNAT_RULE_COMMENT:
        mark=_match_ct_mark(expr[0]); egress=_match_interface(expr[1],"oif",by_name,by_index)
        action=expr[2]
        if not isinstance(action,dict) or set(action)!={"snat"} or not isinstance(action["snat"],dict) or set(action["snat"])!={"addr"}: raise PayloadNatObservationError("unsupported Profile SNAT action")
        try: address=IPv4Address(action["snat"]["addr"])
        except (TypeError,ValueError): raise PayloadNatObservationError("invalid Profile SNAT address") from None
        return ObservedPayloadProfileSnat(payload["handle"],mark,egress,address)
    raise PayloadNatObservationError("missing/wrong NAT owner comment")

def _match_ct_mark(expr):
    if not isinstance(expr,dict) or set(expr)!={"match"}: raise PayloadNatObservationError("invalid ct mark match")
    m=expr["match"]
    if not isinstance(m,dict) or set(m)!={"op","left","right"} or m["op"]!="==" or m["left"]!={"ct":{"key":"mark"}}: raise PayloadNatObservationError("invalid ct mark match expression")
    value=m["right"]
    try: mark=value if type(value) is int else int(value,0)
    except (TypeError,ValueError): raise PayloadNatObservationError("invalid ct mark operand") from None
    if not 1 <= mark <= 0xFFFFFFFF: raise PayloadNatObservationError("invalid ct mark value")
    return mark

def _match_interface(expr,key,by_name,by_index):
    if not isinstance(expr,dict) or set(expr)!={"match"}: raise PayloadNatObservationError(f"invalid {key} match")
    m=expr["match"]
    if not isinstance(m,dict) or set(m)!={"op","left","right"} or m["op"]!="==" or m["left"]!={"meta":{"key":key}}: raise PayloadNatObservationError(f"invalid {key} match expression")
    operand=m["right"]
    if type(operand) is not str or not operand: raise PayloadNatObservationError(f"invalid {key} interface operand")
    if operand.isascii() and operand.isdecimal():
        index=int(operand)
        if index<=0: raise PayloadNatObservationError(f"invalid {key} interface index")
        return by_index.get(index,index)
    identity=by_name.get(operand)
    if identity is None: raise PayloadNatObservationError(f"unresolved {key} interface name")
    return identity
