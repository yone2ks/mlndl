"""導出する関係 — 構文を足さず、既存の参照 (id) をたどって求める

  vlan_endpoints(topology)    VLAN の端点 (ADR-0013 D7)
  vlan_svi_networks(topology) VLAN の SVI のサブネット

エクスポーターと validator が同じ関数を使う。参照先が存在しない id は黙って飛ばす
(存在の検査は validator の _check_refs が行う)。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from ipaddress import IPv4Network, IPv6Network
from typing import Literal

from .schema.layer3 import L3Interface
from .schema.topology import MLNDLTopology

Resolution = Literal["direct", "tag_match", "ambiguous", "no_l3"]


@dataclass
class VlanEndpoint:
    """VLAN の端点 — VLAN のポートの対向で、その VLAN のフレームを受ける機器の IF (ADR-0013 D7)

    - port_node: VLAN のポートを持つノード。端点はこのノードにローカル
    - node: 端点の機器
    - interfaces: 端点の L1 IF の id (bond のメンバーで複数の脚が届けば複数)
    - lag: 端点側の LAG (bond)。なければ None
    - tagged: ポートがフレームにタグを付けるか (native でない trunk_ports)
    - resolution: direct (参照で確定) / tag_match (タグの一致から推定) / ambiguous (候補が複数) / no_l3 (L3 IF なし)
    - l3_interfaces: 候補の L3 IF。direct / tag_match ならちょうど 1 つ
    """

    vlan: str
    port_node: str
    node: str
    interfaces: list[str]
    lag: str | None
    tagged: bool
    resolution: Resolution
    l3_interfaces: list[L3Interface] = field(default_factory=list)


def vlan_endpoints(topology: MLNDLTopology) -> list[VlanEndpoint]:
    """VLAN の端点を、ポート → L1 リンクの対向 → 対向の L3 IF の順にたどって求める (1 ホップ)"""
    if not topology.layer1 or not topology.layer2:
        return []
    l1 = topology.layer1
    l1ifs = {i.id: i for i in l1.interfaces}
    lags = {g.id: g for g in l1.lag}
    lags_of: dict[str, list[str]] = defaultdict(list)       # L1 IF id → それをメンバーに持つ LAG
    for g in l1.lag:
        for m in g.members:
            lags_of[m].append(g.id)
    peer: dict[str, str] = {}                                # L1 IF id → リンクの対向の L1 IF id
    for link in l1.links:
        a, b = link.endpoints
        peer[a], peer[b] = b, a
    subifs_on: dict[str, list] = defaultdict(list)           # 基盤 (L1 IF / LAG の id) → その上のサブ IF
    for si in topology.layer2.subinterfaces:
        subifs_on[si.attaches_to.target].append(si)
    l3_on: dict[str, list[L3Interface]] = defaultdict(list)  # attaches_to の参照先 id → L3 IF
    if topology.layer3:
        for iface in topology.layer3.interfaces:
            ref = iface.attachment_ref()
            if ref is not None:
                l3_on[ref].append(iface)

    result: list[VlanEndpoint] = []
    for vlan in topology.layer2.vlans:
        ports = [(pr, False) for pr in vlan.access_ports] + [(pr, not pr.native) for pr in vlan.trunk_ports]
        port_ids = {pr.target for pr, _ in ports}
        groups: dict[tuple[str, str, str], VlanEndpoint] = {}
        for pr, tagged in ports:
            # 旧形式 {interface: <LAG id>} (ADR-0011 D10) も LAG として読む
            lag_id = pr.lag if pr.lag is not None else (pr.interface if pr.interface in lags else None)
            legs = list(lags[lag_id].members) if lag_id else [pr.interface]
            for x in legs:
                y = peer.get(x)
                if x not in l1ifs or y not in l1ifs:
                    continue
                # 対向もこの VLAN のポートなら、ポートを持つノード同士のリンク (D7 手順 3)
                if y in port_ids or any(g in port_ids for g in lags_of[y]):
                    continue
                host = l1ifs[y].node
                host_lag = next((g for g in lags_of[y] if g in lags), None)
                key = (l1ifs[x].node, host, host_lag or y)
                ep = groups.get(key)
                if ep is None:
                    bases = [y] + ([host_lag] if host_lag else [])
                    if tagged:
                        cands = [l3 for b in bases for si in subifs_on[b] if si.vlan_id == vlan.vlan_id
                                 for l3 in l3_on[si.id]]
                    else:
                        cands = [l3 for b in bases for l3 in l3_on[b]]
                    resolution: Resolution = (
                        "no_l3" if not cands
                        else "ambiguous" if len(cands) > 1
                        else "tag_match" if tagged else "direct"
                    )
                    ep = VlanEndpoint(vlan.id, l1ifs[x].node, host, [], host_lag, tagged, resolution, cands)
                    groups[key] = ep
                    result.append(ep)
                if y not in ep.interfaces:
                    ep.interfaces.append(y)
    return result


def vlan_svi_networks(topology: MLNDLTopology) -> dict[str, list[IPv4Network | IPv6Network]]:
    """VLAN の id → その VLAN の SVI (attaches_to: {vlan:}) のサブネット"""
    nets: dict[str, list[IPv4Network | IPv6Network]] = defaultdict(list)
    if topology.layer3:
        for iface in topology.layer3.interfaces:
            if iface.attaches_to is None or iface.attaches_to.kind != "vlan":
                continue
            for addr in (iface.ip, iface.ipv6):
                if addr is not None and addr.network not in nets[iface.attaches_to.target]:
                    nets[iface.attaches_to.target].append(addr.network)
    return nets


def outside_svi_subnet(endpoint: VlanEndpoint, svi_nets: dict[str, list[IPv4Network | IPv6Network]]) -> list[str]:
    """端点の IP のうち、その VLAN の同じアドレスファミリーの SVI のどのサブネットにも入らないもの (ADR-0013 D7 検査)"""
    if endpoint.resolution not in ("direct", "tag_match"):
        return []
    nets = svi_nets.get(endpoint.vlan, [])
    out: list[str] = []
    for addr in (endpoint.l3_interfaces[0].ip, endpoint.l3_interfaces[0].ipv6):
        if addr is None:
            continue
        same_af = [n for n in nets if n.version == addr.version]
        if same_af and not any(addr.ip in n for n in same_af):
            out.append(str(addr))
    return out
