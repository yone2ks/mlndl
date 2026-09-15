"""クロスフィールド参照整合性バリデーター

チェック項目:
  Layer 1:
    - interfaces[].node → nodes
    - links[].from / to → interfaces
    - lag[lacp].node → nodes
    - lag[mlag].nodes[] → nodes
    - lag[].members[] → interfaces
    - lag[mlag].peer_link → lag
    - nodes/interfaces[].attaches_to 参照

  Layer 2:
    - vlans[].trunk_ports/access_ports[].node → L1 nodes
    - vlans[].trunk_ports/access_ports[].interface → L1 interfaces
    - vxlan[l2vni].vlan → layer2.vlans
    - vxlan[l2vni].vtep_source → layer3.interfaces
    - vxlan[l2vni].members[] → L1 nodes
    - vxlan[l3vni].vrf → layer3.vrfs
    - VNI 番号のグローバル一意性

  Layer 3:
    - vrfs[].l3vni → layer2.vxlan (type=l3vni)
    - vrfs[].rd / route_targets フォーマット (ASN:NN or IP:NN)
    - interfaces[].node → L1 nodes
    - interfaces[].vrf → layer3.vrfs
    - interfaces[].attaches_to 参照
    - routing_adjacencies[].from/to.node → L1 nodes
    - routing_adjacencies[].from/to.update_source → layer3.interfaces
    - routing_adjacencies[].attaches_to.link → L1 links

  Protocols:
    - bfd[].nodes[] → L1 nodes
    - bgp[].nodes[].node → L1 nodes
    - bgp[].nodes[].neighbors[].node → L1 nodes
    - eBGP ペア: local_as != remote_as
    - iBGP ペア: local_as == remote_as

  MTU 整合性:
    - VxLAN (l2vni/l3vni) が存在する場合、underlay リンクの MTU >= 1550
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema.layer1 import AttachesToObj, LacpLag, MlagLag
from .schema.layer2 import L2VxLAN, L3VxLAN
from .schema.topology import MLNDLTopology

_RT_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+:\d+$|^\d+:\d+$")


@dataclass
class ValidationError:
    """バリデーションエラー 1 件"""
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def validate(topology: MLNDLTopology) -> list[ValidationError]:
    """トポロジーの参照整合性・整合性ルールを検証する。

    Returns:
        ValidationError のリスト。空リストなら問題なし。
    """
    errors: list[ValidationError] = []

    # ── ID レジストリを収集 ──────────────────────────────────────────────
    node_ids: set[str] = set()
    interface_ids: set[str] = set()
    link_ids: set[str] = set()
    lag_ids: set[str] = set()
    vlan_ids: set[str] = set()
    l3vni_ids: set[str] = set()
    vrf_ids: set[str] = set()
    l3interface_ids: set[str] = set()

    if topology.layer1:
        l1 = topology.layer1
        node_ids = {n.id for n in l1.nodes}
        interface_ids = {i.id for i in l1.interfaces}
        link_ids = {lk.id for lk in l1.links}
        lag_ids = {lag.id for lag in l1.lag}

    if topology.layer2:
        l2 = topology.layer2
        vlan_ids = {v.id for v in l2.vlans}
        l3vni_ids = {v.id for v in l2.vxlan if v.type == "l3vni"}

    if topology.layer3:
        l3 = topology.layer3
        vrf_ids = {v.id for v in l3.vrfs}
        l3interface_ids = {i.id for i in l3.interfaces}

    # ── Layer 1 ──────────────────────────────────────────────────────────
    if topology.layer1:
        _validate_l1(topology.layer1, node_ids, interface_ids, lag_ids, link_ids, errors)

    # ── Layer 2 ──────────────────────────────────────────────────────────
    if topology.layer2:
        _validate_l2(
            topology.layer2,
            node_ids, interface_ids,
            vlan_ids, l3vni_ids, vrf_ids, l3interface_ids,
            errors,
        )

    # ── Layer 3 ──────────────────────────────────────────────────────────
    if topology.layer3:
        _validate_l3(
            topology.layer3,
            node_ids, interface_ids, link_ids,
            l3vni_ids, vrf_ids, l3interface_ids, vlan_ids,
            errors,
        )

    # ── Protocols ────────────────────────────────────────────────────────
    if topology.protocols:
        _validate_protocols(topology.protocols, node_ids, errors)

    # ── MTU 整合性 ───────────────────────────────────────────────────────
    _validate_mtu(topology, errors)

    return errors


# ---------------------------------------------------------------------------
# Layer 1
# ---------------------------------------------------------------------------

def _validate_l1(l1, node_ids, interface_ids, lag_ids, link_ids, errors):
    # interfaces: node 参照
    for i, iface in enumerate(l1.interfaces):
        if iface.node not in node_ids:
            errors.append(ValidationError(
                f"layer1.interfaces[{i}].node",
                f"未定義のノード '{iface.node}' を参照しています",
            ))

    # links: endpoints 参照
    for i, link in enumerate(l1.links):
        for j, ep in enumerate(link.endpoints):
            if ep not in interface_ids:
                errors.append(ValidationError(
                    f"layer1.links[{i}].endpoints[{j}]",
                    f"未定義のインターフェース '{ep}' を参照しています",
                ))

    # lag: members / node(s) / peer_link
    for i, lag in enumerate(l1.lag):
        for j, member in enumerate(lag.members):
            if member not in interface_ids:
                errors.append(ValidationError(
                    f"layer1.lag[{i}].members[{j}]",
                    f"未定義のインターフェース '{member}' を参照しています",
                ))
        if isinstance(lag, LacpLag):
            if lag.node not in node_ids:
                errors.append(ValidationError(
                    f"layer1.lag[{i}].node",
                    f"未定義のノード '{lag.node}' を参照しています",
                ))
        elif isinstance(lag, MlagLag):
            for j, nid in enumerate(lag.nodes):
                if nid not in node_ids:
                    errors.append(ValidationError(
                        f"layer1.lag[{i}].nodes[{j}]",
                        f"未定義のノード '{nid}' を参照しています",
                    ))
            if lag.peer_link not in lag_ids:
                errors.append(ValidationError(
                    f"layer1.lag[{i}].peer_link",
                    f"未定義の lag '{lag.peer_link}' を参照しています",
                ))
            # client_lag: 同一 lag リスト内の LacpLag を参照していること
            if lag.client_lag is not None:
                if lag.client_lag not in lag_ids:
                    errors.append(ValidationError(
                        f"layer1.lag[{i}].client_lag",
                        f"未定義の lag '{lag.client_lag}' を参照しています",
                    ))
                else:
                    client = next((x for x in l1.lag if x.id == lag.client_lag), None)
                    if client is not None and not isinstance(client, LacpLag):
                        errors.append(ValidationError(
                            f"layer1.lag[{i}].client_lag",
                            f"client_lag は LacpLag (type: lacp) を参照する必要があります",
                        ))
                    # members 数の対称性チェック
                    if client is not None and isinstance(client, LacpLag):
                        if len(client.members) != len(lag.nodes):
                            errors.append(ValidationError(
                                f"layer1.lag[{i}].client_lag",
                                f"client_lag '{lag.client_lag}' の members 数 ({len(client.members)}) が"
                                f" MLAG の nodes 数 ({len(lag.nodes)}) と一致しません",
                            ))

    # attaches_to
    for i, node in enumerate(l1.nodes):
        if node.attaches_to is not None:
            _check_attaches_to(
                node.attaches_to, f"layer1.nodes[{i}].attaches_to",
                node_ids, interface_ids, link_ids, errors,
            )
    for i, iface in enumerate(l1.interfaces):
        if iface.attaches_to is not None:
            _check_attaches_to(
                iface.attaches_to, f"layer1.interfaces[{i}].attaches_to",
                node_ids, interface_ids, link_ids, errors,
            )


# ---------------------------------------------------------------------------
# Layer 2
# ---------------------------------------------------------------------------

def _validate_l2(l2, node_ids, interface_ids, vlan_ids, l3vni_ids, vrf_ids, l3interface_ids, errors):
    # VLAN trunk_ports / access_ports
    for i, vlan in enumerate(l2.vlans):
        for j, pr in enumerate(vlan.trunk_ports):
            if pr.node not in node_ids:
                errors.append(ValidationError(
                    f"layer2.vlans[{i}].trunk_ports[{j}].node",
                    f"未定義のノード '{pr.node}' を参照しています",
                ))
            if pr.interface not in interface_ids:
                errors.append(ValidationError(
                    f"layer2.vlans[{i}].trunk_ports[{j}].interface",
                    f"未定義のインターフェース '{pr.interface}' を参照しています",
                ))
        for j, pr in enumerate(vlan.access_ports):
            if pr.node not in node_ids:
                errors.append(ValidationError(
                    f"layer2.vlans[{i}].access_ports[{j}].node",
                    f"未定義のノード '{pr.node}' を参照しています",
                ))
            if pr.interface not in interface_ids:
                errors.append(ValidationError(
                    f"layer2.vlans[{i}].access_ports[{j}].interface",
                    f"未定義のインターフェース '{pr.interface}' を参照しています",
                ))

    # VxLAN — VNI 一意性チェック
    seen_vnis: dict[int, str] = {}
    for i, vx in enumerate(l2.vxlan):
        if vx.vni in seen_vnis:
            errors.append(ValidationError(
                f"layer2.vxlan[{i}].vni",
                f"VNI {vx.vni} が '{seen_vnis[vx.vni]}' と重複しています",
            ))
        else:
            seen_vnis[vx.vni] = vx.id

        if isinstance(vx, L2VxLAN):
            if vx.vlan not in vlan_ids:
                errors.append(ValidationError(
                    f"layer2.vxlan[{i}].vlan",
                    f"未定義の VLAN '{vx.vlan}' を参照しています",
                ))
            if vx.vtep_source not in l3interface_ids:
                errors.append(ValidationError(
                    f"layer2.vxlan[{i}].vtep_source",
                    f"未定義の L3 インターフェース '{vx.vtep_source}' を参照しています",
                ))
            for j, m in enumerate(vx.members):
                if m not in node_ids:
                    errors.append(ValidationError(
                        f"layer2.vxlan[{i}].members[{j}]",
                        f"未定義のノード '{m}' を参照しています",
                    ))
        elif isinstance(vx, L3VxLAN):
            if vx.vrf not in vrf_ids:
                errors.append(ValidationError(
                    f"layer2.vxlan[{i}].vrf",
                    f"未定義の VRF '{vx.vrf}' を参照しています",
                ))


# ---------------------------------------------------------------------------
# Layer 3
# ---------------------------------------------------------------------------

def _validate_l3(l3, node_ids, interface_ids, link_ids, l3vni_ids, vrf_ids, l3interface_ids, vlan_ids, errors):
    # VRF
    for i, vrf in enumerate(l3.vrfs):
        if vrf.l3vni is not None and vrf.l3vni not in l3vni_ids:
            errors.append(ValidationError(
                f"layer3.vrfs[{i}].l3vni",
                f"未定義の L3VNI '{vrf.l3vni}' を参照しています（type=l3vni の vxlan が必要）",
            ))
        # Route Distinguisher / Route Target フォーマット
        if vrf.rd and not _RT_PATTERN.match(vrf.rd):
            errors.append(ValidationError(
                f"layer3.vrfs[{i}].rd",
                f"RD フォーマット不正: '{vrf.rd}'（ASN:NN または IP:NN 形式が必要）",
            ))
        if vrf.route_targets:
            for j, rt in enumerate(vrf.route_targets.import_):
                if not _RT_PATTERN.match(rt):
                    errors.append(ValidationError(
                        f"layer3.vrfs[{i}].route_targets.import[{j}]",
                        f"RT フォーマット不正: '{rt}'",
                    ))
            for j, rt in enumerate(vrf.route_targets.export):
                if not _RT_PATTERN.match(rt):
                    errors.append(ValidationError(
                        f"layer3.vrfs[{i}].route_targets.export[{j}]",
                        f"RT フォーマット不正: '{rt}'",
                    ))

    # L3 Interfaces
    for i, iface in enumerate(l3.interfaces):
        if iface.node not in node_ids:
            errors.append(ValidationError(
                f"layer3.interfaces[{i}].node",
                f"未定義のノード '{iface.node}' を参照しています",
            ))
        if iface.vrf is not None and iface.vrf not in vrf_ids:
            errors.append(ValidationError(
                f"layer3.interfaces[{i}].vrf",
                f"未定義の VRF '{iface.vrf}' を参照しています",
            ))
        if iface.vlan is not None and iface.vlan not in vlan_ids:
            errors.append(ValidationError(
                f"layer3.interfaces[{i}].vlan",
                f"未定義の VLAN '{iface.vlan}' を参照しています（SVI）",
            ))
        if iface.attaches_to is not None:
            _check_attaches_to(
                iface.attaches_to, f"layer3.interfaces[{i}].attaches_to",
                node_ids, interface_ids, link_ids, errors,
            )

    # Routing Adjacencies
    for i, adj in enumerate(l3.routing_adjacencies):
        if adj.from_.node not in node_ids:
            errors.append(ValidationError(
                f"layer3.routing_adjacencies[{i}].from.node",
                f"未定義のノード '{adj.from_.node}' を参照しています",
            ))
        if adj.to.node not in node_ids:
            errors.append(ValidationError(
                f"layer3.routing_adjacencies[{i}].to.node",
                f"未定義のノード '{adj.to.node}' を参照しています",
            ))
        for side, ep in [("from", adj.from_), ("to", adj.to)]:
            if ep.update_source is not None and ep.update_source not in l3interface_ids:
                errors.append(ValidationError(
                    f"layer3.routing_adjacencies[{i}].{side}.update_source",
                    f"未定義の L3 インターフェース '{ep.update_source}' を参照しています",
                ))
        if adj.attaches_to is not None:
            _check_attaches_to(
                adj.attaches_to, f"layer3.routing_adjacencies[{i}].attaches_to",
                node_ids, interface_ids, link_ids, errors,
            )


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

def _validate_protocols(protocols, node_ids, errors):
    # BFD
    for i, bfd in enumerate(protocols.bfd):
        for j, nid in enumerate(bfd.nodes):
            if nid not in node_ids:
                errors.append(ValidationError(
                    f"protocols.bfd[{i}].nodes[{j}]",
                    f"未定義のノード '{nid}' を参照しています",
                ))

    # 同一ノードが複数 BGP プロセスで異なる local_as を持つ矛盾を検出
    # (1 台の機器は通常 1 つの BGP AS。VRF 分離/confederation は別途明示が必要)
    node_local_as: dict[str, set[int]] = {}
    for bgp in protocols.bgp:
        for bn in bgp.nodes:
            if bn.local_as is not None:
                node_local_as.setdefault(bn.node, set()).add(bn.local_as)
    for nid, as_set in node_local_as.items():
        if len(as_set) > 1:
            errors.append(ValidationError(
                f"protocols.bgp (node={nid})",
                f"ノード '{nid}' が複数の異なる local_as {sorted(as_set)} を持っています"
                f"（VRF 分離/confederation の意図なら設計を明示してください）",
            ))

    # BGP
    for i, bgp in enumerate(protocols.bgp):
        for j, bn in enumerate(bgp.nodes):
            if bn.node not in node_ids:
                errors.append(ValidationError(
                    f"protocols.bgp[{i}].nodes[{j}].node",
                    f"未定義のノード '{bn.node}' を参照しています",
                ))
            for k, nb in enumerate(bn.neighbors):
                if nb.node not in node_ids:
                    errors.append(ValidationError(
                        f"protocols.bgp[{i}].nodes[{j}].neighbors[{k}].node",
                        f"未定義のノード '{nb.node}' を参照しています",
                    ))
                # AS 番号整合性チェック
                if nb.type == "ebgp" and bn.local_as is not None and nb.remote_as is not None:
                    if bn.local_as == nb.remote_as:
                        errors.append(ValidationError(
                            f"protocols.bgp[{i}].nodes[{j}].neighbors[{k}]",
                            f"eBGP ピアで同一 AS ({bn.local_as}) が設定されています",
                        ))
                if nb.type == "ibgp" and bn.local_as is not None and nb.remote_as is not None:
                    if bn.local_as != nb.remote_as:
                        errors.append(ValidationError(
                            f"protocols.bgp[{i}].nodes[{j}].neighbors[{k}]",
                            f"iBGP ピアで異なる AS ({bn.local_as} vs {nb.remote_as}) が設定されています",
                        ))


# ---------------------------------------------------------------------------
# MTU 整合性
# ---------------------------------------------------------------------------

def _validate_mtu(topology: MLNDLTopology, errors: list[ValidationError]) -> None:
    """VxLAN underlay の MTU >= 1550 を確認（VxLAN ドメイン内のリンクのみ対象）

    旧実装はトポロジー全体に VxLAN が 1 つでもあれば全 underlay リンクを検査し、
    マルチサイト構成で VxLAN を使わないサイトの underlay まで誤検出していた。
    本実装は VxLAN に参加するノード（VTEP メンバー + vtep_source 保有ノード）
    集合を求め、両端がその集合に属する underlay リンクのみ検査する。
    """
    if topology.layer2 is None or topology.layer1 is None:
        return

    # VxLAN ドメインに参加するノード集合
    vtep_nodes: set[str] = set()
    l3if_node = {i.id: i.node for i in topology.layer3.interfaces} if topology.layer3 else {}
    for vx in topology.layer2.vxlan:
        if isinstance(vx, L2VxLAN):
            vtep_nodes.update(vx.members)
            if vx.vtep_source in l3if_node:
                vtep_nodes.add(l3if_node[vx.vtep_source])
    if not vtep_nodes:
        return

    iface_node = {i.id: i.node for i in topology.layer1.interfaces}
    for i, link in enumerate(topology.layer1.links):
        if link.link_role != "underlay" or link.mtu is None or link.mtu >= 1550:
            continue
        # 両端ノードが VxLAN ドメインに属する underlay リンクのみ検査
        sn = iface_node.get(link.endpoints[0])
        tn = iface_node.get(link.endpoints[1])
        if sn in vtep_nodes and tn in vtep_nodes:
            errors.append(ValidationError(
                f"layer1.links[{i}].mtu",
                f"VxLAN underlay は MTU >= 1550 が必要です（現在: {link.mtu}）",
            ))


# ---------------------------------------------------------------------------
# attaches_to 参照チェック（共通）
# ---------------------------------------------------------------------------

def _check_attaches_to(attaches_to, path, node_ids, interface_ids, link_ids, errors):
    if isinstance(attaches_to, str):
        if attaches_to not in node_ids:
            errors.append(ValidationError(
                path, f"未定義のノード '{attaches_to}' を参照しています",
            ))
    elif isinstance(attaches_to, AttachesToObj):
        if attaches_to.node is not None and attaches_to.node not in node_ids:
            errors.append(ValidationError(
                f"{path}.node", f"未定義のノード '{attaches_to.node}' を参照しています",
            ))
        if attaches_to.interface is not None and attaches_to.interface not in interface_ids:
            errors.append(ValidationError(
                f"{path}.interface",
                f"未定義のインターフェース '{attaches_to.interface}' を参照しています",
            ))
        if attaches_to.link is not None and attaches_to.link not in link_ids:
            errors.append(ValidationError(
                f"{path}.link", f"未定義のリンク '{attaches_to.link}' を参照しています",
            ))
