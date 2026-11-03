"""導出する関係 — 構文を足さず、既存の参照 (id) をたどって求める

  vlan_endpoints(topology)    VLAN の端点 (ADR-0013 D7)
  vlan_svi_networks(topology) VLAN の SVI のサブネット
  l3_attachments(topology)    L3 IF が何の上に載るか (ADR-0011 D11)
  l3_roles(topology)          L3 IF がほかから参照されている役割 (ADR-0011 D11)
  bgp_session_views(topology) BGP セッションの両端・AS・eBGP / iBGP・通り道 (ADR-0010 D7・D11)
  igp_adjacency_views(topology) OSPF / IS-IS の隣接の通り道 (ADR-0018 D4)
  end_path_labels(topology)   セッションの端ごとの通り道の呼び名 (食い違いのメッセージ用。ADR-0018 D6)

通り道は、両端の基盤が同じリンク / LAG でつながるか、同じ bridge に届くか (ADR-0018 D2)、
対になるトンネル IF か (ADR-0018 D3) で決める。

エクスポーターと validator が同じ関数を使う。参照先が存在しない id は黙って飛ばす
(存在の検査は validator の _check_refs が行う)。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Literal

from .schema.control_plane import BgpInsideEndpoint, BgpInstance, BgpSession, IsisAdjacency, OspfAdjacency
from .schema.layer3 import L3Interface, TunnelInterface
from .schema.topology import MLNDLTopology

Resolution = Literal["direct", "tag_match", "ambiguous", "no_l3"]
Attachment = Literal["l1_interface", "lag", "vlan", "subinterface", "unattached"]
Role = Literal["update_source", "vtep_source"]


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


def l3_attachments(topology: MLNDLTopology) -> dict[str, Attachment]:
    """L3 IF の id → 何の上に載るか (ADR-0011 D11)

    attaches_to のキーで決め、name では決めない。attaches_to がなければ unattached
    (ループバックとはみなさない)。旧形式 {interface: <LAG / VLAN / サブ IF の id>} (ADR-0011 D10) は、
    validator と同じく参照先の種類で読む。
    """
    if not topology.layer3:
        return {}
    lag_ids = {g.id for g in topology.layer1.lag} if topology.layer1 else set()
    vlan_ids = {v.id for v in topology.layer2.vlans} if topology.layer2 else set()
    subif_ids = {si.id for si in topology.layer2.subinterfaces} if topology.layer2 else set()
    by_key: dict[str, Attachment] = {"interface": "l1_interface", "lag": "lag", "vlan": "vlan",
                                     "subinterface": "subinterface"}
    out: dict[str, Attachment] = {}
    for iface in topology.layer3.interfaces:
        at = iface.attaches_to
        if at is None:
            out[iface.id] = "unattached"
        elif at.kind == "interface" and at.target in lag_ids:
            out[iface.id] = "lag"
        elif at.kind == "interface" and at.target in vlan_ids:
            out[iface.id] = "vlan"
        elif at.kind == "interface" and at.target in subif_ids:
            out[iface.id] = "subinterface"
        else:
            out[iface.id] = by_key[at.kind]
    return out


def l3_roles(topology: MLNDLTopology) -> dict[str, list[Role]]:
    """L3 IF の id → ほかのエンティティから参照されている役割 (ADR-0011 D11)

    update_source: control_plane.routing_neighbors の BGP セッションの update_source が指している (ADR-0010)
    vtep_source:   layer2.vteps の sources が指している (ADR-0014)
    """
    roles: dict[str, list[Role]] = defaultdict(list)

    def add(l3_id: str | None, role: Role) -> None:
        if l3_id is not None and role not in roles[l3_id]:
            roles[l3_id].append(role)

    if topology.control_plane:
        for session in topology.control_plane.routing_neighbors:
            if isinstance(session, BgpSession):
                for end in (session.from_, session.to):
                    if isinstance(end, BgpInsideEndpoint):
                        add(end.update_source, "update_source")
    if topology.layer2:
        for vtep in topology.layer2.vteps:
            for src in vtep.sources:
                add(src, "vtep_source")
    return dict(roles)


# ---------------------------------------------------------------------------
# BGP セッション (ADR-0010)
# ---------------------------------------------------------------------------

@dataclass
class SessionEnd:
    """セッションの片端。トポロジー外の相手は node と l3_interface が None で、address を持つ

    l3_interface: update_source が指す L3 IF かトンネル IF (ADR-0018 D3)。どちらも id / node / ip / ipv6 / vrf を持つ
    """

    node: str | None
    l3_interface: L3Interface | TunnelInterface | None
    address: IPv4Address | IPv6Address | None
    local_as: int | None
    route_reflector_client: bool = False

    @property
    def unnumbered(self) -> bool:
        """update_source が ip も ipv6 も持たない L3 IF を指す (ADR-0010 D4)"""
        return self.l3_interface is not None and self.l3_interface.ip is None and self.l3_interface.ipv6 is None

    @property
    def transport_afs(self) -> set[int]:
        """セッションを張る IP のアドレスファミリー (4 / 6)。unnumbered なら空"""
        if self.address is not None:
            return {self.address.version}
        if self.l3_interface is None:
            return set()
        return {a.version for a in (self.l3_interface.ip, self.l3_interface.ipv6) if a is not None}


@dataclass
class TransportLink:
    """single-hop のセッションが流れる通り道。どれか 1 つだけを持つ

    - link: リンク 1 本
    - lags: 両端の LAG (from 側, to 側)
    - bridge: 両端が届く bridge (ADR-0018 D2)
    - tunnels: 対になるトンネル IF (from 側, to 側) (ADR-0018 D3)
    """

    link: str | None = None
    lags: list[str] = field(default_factory=list)
    bridge: str | None = None
    tunnels: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """エクスポーターの transport_link の値 (ADR-0010 D11・ADR-0018 D5)"""
        if self.link:
            return {"link": self.link}
        if self.lags:
            return {"lag": list(self.lags)}
        if self.bridge:
            return {"bridge": self.bridge}
        return {"tunnel": list(self.tunnels)}


@dataclass
class BgpSessionView:
    """参照をたどって決めた BGP セッションの値。validator とエクスポーターが共有する (ADR-0010 D11)

    - instance: セッションが属するインスタンス (instance 省略時は、BGP のエントリがちょうど 1 つならそれ)
    - bgp_type: 両端の AS が決まれば ebgp / ibgp
    - transport: single-hop なら通り道。multihop・SVI・トポロジー外の相手なら None (D7)
    - transport_mismatch: 両端の update_source から導いた通り道が食い違う
    """

    index: int
    session: BgpSession
    instance: BgpInstance | None
    from_: SessionEnd
    to: SessionEnd
    bgp_type: Literal["ebgp", "ibgp"] | None
    transport: TransportLink | None
    transport_mismatch: bool

    @property
    def vrf(self) -> str | None:
        """インスタンスの VRF。None は default VRF"""
        return self.instance.vrf if self.instance else None


def bgp_session_views(topology: MLNDLTopology) -> list[BgpSessionView]:
    """control_plane.routing_neighbors の BGP セッションごとに、両端・AS・通り道を求める"""
    cp = topology.control_plane
    if cp is None:
        return []
    instances = {b.id: b for b in cp.bgp}
    only = cp.bgp[0] if len(cp.bgp) == 1 else None
    l3ifs = l3_and_tunnels(topology)
    basis = _l3_basis(topology)
    fabric = _Fabric(topology)

    views: list[BgpSessionView] = []
    for i, session in enumerate(cp.routing_neighbors):
        if not isinstance(session, BgpSession):
            continue
        inst = instances.get(session.instance) if session.instance else only
        as_of = {n.node: n.local_as for n in inst.nodes} if inst else {}

        def end(ep) -> SessionEnd:
            if isinstance(ep, BgpInsideEndpoint):
                return SessionEnd(ep.node, l3ifs.get(ep.update_source), None, as_of.get(ep.node),
                                  ep.route_reflector_client)
            return SessionEnd(None, None, ep.address, ep.local_as)

        a, b = end(session.from_), end(session.to)
        bgp_type = None
        if a.local_as is not None and b.local_as is not None:
            bgp_type = "ibgp" if a.local_as == b.local_as else "ebgp"
        transport, mismatch = None, False
        if a.l3_interface is not None and b.l3_interface is not None:
            transport, mismatch = _transport(basis.get(a.l3_interface.id), basis.get(b.l3_interface.id), fabric)
        views.append(BgpSessionView(i, session, inst, a, b, bgp_type, transport, mismatch))
    return views


@dataclass
class AdjacencyView:
    """OSPF / IS-IS の隣接の通り道 (ADR-0018 D4)。両端は interface の id (OSPF は L3 IF かトンネル IF、IS-IS は L1 IF)"""

    index: int
    session: OspfAdjacency | IsisAdjacency
    transport: TransportLink | None
    transport_mismatch: bool


def igp_adjacency_views(topology: MLNDLTopology) -> list[AdjacencyView]:
    """control_plane.routing_neighbors の OSPF / IS-IS の隣接ごとに、通り道を求める (BGP と同じ規則)"""
    cp = topology.control_plane
    if cp is None:
        return []
    basis = _l3_basis(topology)
    fabric = _Fabric(topology)
    l1ifs = {i.id for i in topology.layer1.interfaces} if topology.layer1 else set()
    views: list[AdjacencyView] = []
    for i, session in enumerate(cp.routing_neighbors):
        if isinstance(session, OspfAdjacency):
            a, b = basis.get(session.from_.interface), basis.get(session.to.interface)
        elif isinstance(session, IsisAdjacency):
            # IS-IS の interface は L1 IF。L3 IF から基盤をたどる 1 段を省く (ADR-0018 D2)
            a, b = (("l1", ep.interface, None) if ep.interface in l1ifs else None for ep in (session.from_, session.to))
        else:
            continue
        transport, mismatch = _transport(a, b, fabric)
        views.append(AdjacencyView(i, session, transport, mismatch))
    return views


def l3_and_tunnels(topology: MLNDLTopology) -> dict[str, L3Interface | TunnelInterface]:
    """update_source / OSPF の interface が指せるもの: L3 IF とトンネル IF (ADR-0018 D3)"""
    if not topology.layer3:
        return {}
    return {i.id: i for i in [*topology.layer3.interfaces, *topology.layer3.tunnel_interfaces]}


# L3 IF の基盤: ("l1", L1 IF id, タグ) / ("lag", LAG id, タグ) / ("vlan", VLAN id, None) / ("tunnel", トンネル IF id, None)。
# タグはサブ IF の vlan_id
_Basis = tuple[str, str, int | None]


def _l3_basis(topology: MLNDLTopology) -> dict[str, _Basis]:
    """L3 IF / トンネル IF の id → 何の上に載るか。サブ IF はその基盤 (L1 IF / LAG) とタグに展開する

    トンネル IF は 4 つ目の種類として足す (ADR-0018 D3)。l3_attachments (ADR-0011 D11) には入れない
    """
    if not topology.layer3:
        return {}
    attachments = l3_attachments(topology)
    subifs = {si.id: si for si in topology.layer2.subinterfaces} if topology.layer2 else {}
    out: dict[str, _Basis] = {}
    for iface in topology.layer3.interfaces:
        ref = iface.attachment_ref()
        kind = attachments.get(iface.id)
        if ref is None or kind == "unattached":
            continue
        if kind == "subinterface" and ref in subifs:
            base = subifs[ref].attaches_to
            out[iface.id] = ("lag" if base.kind == "lag" else "l1", base.target, subifs[ref].vlan_id)
        elif kind == "l1_interface":
            out[iface.id] = ("l1", ref, None)
        elif kind in ("lag", "vlan"):
            out[iface.id] = (kind, ref, None)
    for tun in topology.layer3.tunnel_interfaces:
        out[tun.id] = ("tunnel", tun.id, None)
    return out


def _l1_peers(topology: MLNDLTopology) -> tuple[dict[str, str], dict[frozenset[str], str]]:
    """L1 IF id → リンクの対向の L1 IF id、L1 IF の組 → リンク id"""
    peer: dict[str, str] = {}
    link_of: dict[frozenset[str], str] = {}
    if topology.layer1:
        for link in topology.layer1.links:
            x, y = link.endpoints
            peer[x], peer[y] = y, x
            link_of[frozenset((x, y))] = link.id
    return peer, link_of


def end_path_labels(topology: MLNDLTopology) -> dict[str, str]:
    """セッションの端 (L3 IF / トンネル IF / L1 IF) の id → その端から見た通り道の呼び名

    通り道の食い違いのメッセージで、両端がそれぞれ何の上にあるかを示すのに使う (ADR-0018 D6)
    """
    fabric = _Fabric(topology)
    bases: dict[str, _Basis | None] = {}
    if topology.layer1:
        bases.update({i.id: ("l1", i.id, None) for i in topology.layer1.interfaces})
    basis = _l3_basis(topology)
    bases.update({i: basis.get(i) for i in l3_and_tunnels(topology)})

    def label(b: _Basis | None) -> str:
        if b is None:
            return "なし (ループバック等)"
        kind, ref, tag = b
        if kind == "tunnel":
            return f"トンネル {ref}"
        if kind == "vlan":
            return f"VLAN {ref}"
        if kind == "lag":
            text = f"LAG {ref}"
        else:
            other = fabric.peer.get(ref)
            text = f"リンク {fabric.link_of[frozenset((ref, other))]}" if other else f"{ref} (リンクなし)"
        if tag is not None:
            text += f" のタグ {tag}"
        reached = sorted(fabric.reached_bridges(b))
        if reached:
            text += f" (bridge {' / '.join(reached)} に届く)"
        return text

    return {i: label(b) for i, b in bases.items()}


class _Fabric:
    """通り道を導くのに使う L1 のつながり・bridge・トンネル"""

    def __init__(self, topology: MLNDLTopology) -> None:
        self.peer, self.link_of = _l1_peers(topology)
        l1 = topology.layer1
        self.lag_members = {g.id: set(g.members) for g in l1.lag} if l1 else {}
        # L1 IF id → それをポートに持つ bridge (LAG のポートはメンバーに展開する)
        self.bridges_of: dict[str, set[str]] = defaultdict(set)
        if topology.layer2:
            for br in topology.layer2.bridges:
                for port in br.ports:
                    legs = self.lag_members.get(port.lag, set()) if port.lag is not None else {port.interface}
                    for leg in legs:
                        self.bridges_of[leg].add(br.id)
        self.tunnels = {t.id: t for t in topology.layer3.tunnel_interfaces} if topology.layer3 else {}

    def reached_bridges(self, basis: _Basis) -> set[str]:
        """基盤の L1 リンクの対向がポートになっている bridge (1 ホップ。ADR-0018 D2)"""
        legs = self.lag_members.get(basis[1], set()) if basis[0] == "lag" else {basis[1]}
        out: set[str] = set()
        for leg in legs:
            out |= self.bridges_of.get(self.peer.get(leg, ""), set())
        return out


def _transport(a: _Basis | None, b: _Basis | None, fabric: _Fabric) -> tuple[TransportLink | None, bool]:
    """両端の基盤から通り道を導く (ADR-0010 D7・ADR-0018 D2 / D3)。戻り値は (通り道, 食い違い)

    - トンネル IF: 両端が対になるトンネル IF なら通り道。片方だけトンネル IF、または対になっていなければ食い違い。
      どちらかが destination_ip (相手がトポロジー外) なら対を確かめられないので、導かず食い違いともしない
    - どちらかが基盤なし (ループバック等): multihop。食い違いとはしない
    - SVI: 通り道は決めない。両端とも SVI なら同じ VLAN でなければ食い違い (片方だけ SVI は、ルーテッド IF との接続として正当)
    - 直結の IF / LAG / サブ IF: 両端が同じリンク (または LAG のメンバーどうし) でつながり、タグが一致すれば single-hop。
      そうでなくても両端が同じ bridge に届けば single-hop (タグは比べない。タグ変換のある契約では違うのが正しい)。
      どちらでもなければ食い違い
    """
    if (a is not None and a[0] == "tunnel") or (b is not None and b[0] == "tunnel"):
        if a is None or b is None or a[0] != b[0]:
            return None, True
        x, y = fabric.tunnels.get(a[1]), fabric.tunnels.get(b[1])
        if x is None or y is None or x.destination_interface is None or y.destination_interface is None:
            return None, False
        if x.destination_interface == y.source and y.destination_interface == x.source:
            return TransportLink(tunnels=[a[1], b[1]]), False
        return None, True
    if a is None or b is None:
        return None, False
    if a[0] == "vlan" or b[0] == "vlan":
        return None, a[0] == b[0] == "vlan" and a[1] != b[1]
    direct = _direct(a, b, fabric)
    if direct is not None:
        return direct, False
    common = fabric.reached_bridges(a) & fabric.reached_bridges(b)
    if common:
        return TransportLink(bridge=sorted(common)[0]), False
    return None, True


def _direct(a: _Basis, b: _Basis, fabric: _Fabric) -> TransportLink | None:
    """両端が同じリンク (または LAG のメンバーどうし) でつながり、タグが一致すれば通り道"""
    if a[2] != b[2] or a[0] != b[0]:
        return None
    if a[0] == "l1":
        if fabric.peer.get(a[1]) != b[1]:
            return None
        link = fabric.link_of.get(frozenset((a[1], b[1])))
        return TransportLink(link=link) if link else None
    members_b = fabric.lag_members.get(b[1], set())
    if any(fabric.peer.get(m) in members_b for m in fabric.lag_members.get(a[1], set())):
        return TransportLink(lags=[a[1], b[1]])
    return None
