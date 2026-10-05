"""Cytoscape.js JSON エクスポーター (ndl-viz 向け)

設計方針:
  - L1 が常時表示の基盤レイヤー
  - L2 / L3 / BGP は L1 ノードに重ねるオーバーレイ
  - 全エッジの source/target は L1 ノード ID を直接参照（prefix なし）
  - ノードは L1 の `node` タイプのみ。L3 IP・VRF・VLAN 情報はデータに埋め込む
"""

from __future__ import annotations

import json
from collections import defaultdict

from ..schema.layer1 import LacpLag, MlagLag
from ..schema.layer2 import L2VxLAN, L3VxLAN
from ..schema.topology import MLNDLTopology


def export(topology: MLNDLTopology) -> dict:
    elements: dict[str, list] = {"nodes": [], "edges": []}

    # インターフェース ID → ノード ID / 名前マップ
    if_to_node: dict[str, str] = {}
    if_to_name: dict[str, str] = {}
    if topology.layer1:
        for iface in topology.layer1.interfaces:
            if_to_node[iface.id] = iface.node
            if_to_name[iface.id] = iface.name or iface.id

    _export_nodes(topology, elements)
    _export_l1_edges(topology, if_to_node, if_to_name, elements)
    _export_l2_overlay(topology, if_to_name, elements)
    _export_l3_overlay(topology, elements)
    _export_tunnels(topology, elements)
    _export_bgp_overlay(topology, elements)

    return elements


def export_json(topology: MLNDLTopology, indent: int = 2) -> str:
    return json.dumps(export(topology), ensure_ascii=False, indent=indent)


# ---------------------------------------------------------------------------
# ノード（L1 のみ、全レイヤー情報を data に埋め込む）
# ---------------------------------------------------------------------------

def _export_nodes(topology: MLNDLTopology, elements: dict) -> None:
    if not topology.layer1:
        return

    # L3 情報をノード別に集約。IP は構造化配列 l3_interfaces として出力する
    # （旧 "ifname:ip" 文字列パッキングは廃止 — lossy・パース脆弱のため）
    # ip / ipv6 は IPv4Interface / IPv6Interface なので、JSON 化のため str() する (ADR-0011 D5)
    lo_ip:    dict[str, str]         = {}
    lo_ipv6:  dict[str, str]         = {}
    node_l3ifs: dict[str, list[dict]] = defaultdict(list)
    node_vrfs: dict[str, list[str]]  = defaultdict(list)
    node_tunnels: dict[str, list[dict]] = defaultdict(list)
    node_subifs: dict[str, list[dict]] = defaultdict(list)
    vlan_ids = {v.id for v in topology.layer2.vlans} if topology.layer2 else set()

    # サブ IF は親 (L1 IF / LAG) のノードに埋め込む。MLAG 上のサブ IF は両ノードに存在する (ADR-0012)
    parent_nodes: dict[str, list[str]] = {}
    for iface in topology.layer1.interfaces:
        parent_nodes[iface.id] = [iface.node]
    for lag in topology.layer1.lag:
        parent_nodes[lag.id] = [lag.node] if isinstance(lag, LacpLag) else list(lag.nodes)
    subifs = {si.id: si for si in topology.layer2.subinterfaces} if topology.layer2 else {}
    for si in subifs.values():
        entry = {"id": si.id, "parent": si.attaches_to.interface, "vlan_id": si.vlan_id}
        if si.name: entry["name"] = si.name
        for nid in parent_nodes.get(si.attaches_to.interface, []):
            node_subifs[nid].append(entry)
    lag_ids = {lag.id for lag in topology.layer1.lag}
    if topology.layer3:
        for iface in topology.layer3.interfaces:
            if iface.interface == "lo":
                if iface.ip:   lo_ip[iface.node]   = str(iface.ip)
                if iface.ipv6: lo_ipv6[iface.node] = str(iface.ipv6)
            if iface.ip or iface.ipv6:
                ref = iface.attachment_ref()
                vlan = ref if ref in vlan_ids else None
                subif = subifs.get(ref)
                kind = ("loopback" if iface.interface == "lo"
                        else "svi" if vlan
                        else "subinterface" if subif else "routed")
                entry: dict = {"interface": iface.interface, "kind": kind}
                if iface.ip:   entry["ip"]   = str(iface.ip)
                if iface.ipv6: entry["ipv6"] = str(iface.ipv6)
                if iface.vrf:  entry["vrf"]  = iface.vrf
                if vlan:       entry["vlan"] = vlan
                if subif:
                    entry["subinterface"] = subif.id
                    entry["vlan_id"]      = subif.vlan_id
                if ref in lag_ids: entry["lag"] = ref
                gws = [gw.model_dump(mode="json", exclude_none=True)
                       for gw in iface.gateway_redundancy]
                if gws:        entry["gateway_redundancy"] = gws
                node_l3ifs[iface.node].append(entry)
            if iface.vrf and iface.vrf not in node_vrfs[iface.node]:
                node_vrfs[iface.node].append(iface.vrf)
        for tun in topology.layer3.tunnel_interfaces:
            node_tunnels[tun.node].append(
                tun.model_dump(mode="json", exclude_none=True, exclude={"node"})
            )

    # L2 VLAN メンバーシップをノード別に集約
    node_vlans: dict[str, list[str]] = defaultdict(list)
    if topology.layer2:
        for vlan in topology.layer2.vlans:
            for pr in [*vlan.trunk_ports, *vlan.access_ports]:
                if vlan.id not in node_vlans[pr.node]:
                    node_vlans[pr.node].append(vlan.id)

    # BGP AS 番号をノード別に集約（BGP overlay での AS 番号表示用）
    # local_as が直接定義されているノード優先、次に neighbor の remote_as から逆引き
    node_local_as: dict[str, int] = {}
    if topology.protocols:
        for bgp in topology.protocols.bgp:
            for bn in bgp.nodes:
                if bn.local_as and bn.node not in node_local_as:
                    node_local_as[bn.node] = bn.local_as
        # neighbor の remote_as からも補完（leaf 等が nodes に未定義の場合）
        for bgp in topology.protocols.bgp:
            for bn in bgp.nodes:
                for nb in bn.neighbors:
                    if nb.remote_as and nb.node not in node_local_as:
                        node_local_as[nb.node] = nb.remote_as

    for node in topology.layer1.nodes:
        # 基本ラベル（hostname のみ。IP は overlay 有効時に CSS クラスで表示）
        data: dict = {
            "id":    node.id,
            "label": node.name or node.id,
            "layer": "layer1",
            "type":  "node",
        }
        if node.role:           data["role"] = node.role
        if node.implementation: data["implementation"] = node.implementation
        if node.device_type:    data["device_type"] = node.device_type
        if node.labels:         data["labels"] = dict(node.labels)  # ADR-0009 多軸分類

        # L3 データを埋め込む（overlay 有効時に参照）
        if lo_ip.get(node.id):        data["lo_ip"]          = lo_ip[node.id]
        if lo_ipv6.get(node.id):      data["lo_ipv6"]        = lo_ipv6[node.id]
        if node_tunnels[node.id]:     data["tunnels"]        = node_tunnels[node.id]
        if node_subifs[node.id]:      data["subinterfaces"]  = node_subifs[node.id]
        if node_l3ifs[node.id]:       data["l3_interfaces"]  = node_l3ifs[node.id]
        if node_vrfs[node.id]:        data["vrfs"]           = node_vrfs[node.id]

        # L2 VLAN データを埋め込む
        if node_vlans[node.id]:       data["vlans"]    = node_vlans[node.id]

        # BGP AS 番号を埋め込む（BGP overlay での表示用）
        if node_local_as.get(node.id): data["local_as"] = node_local_as[node.id]

        elements["nodes"].append({"data": data})


# ---------------------------------------------------------------------------
# L1 エッジ（物理リンク・LAG タグ付き）
# ---------------------------------------------------------------------------

def _export_l1_edges(topology, if_to_node, if_to_name, elements):
    if not topology.layer1:
        return
    l1 = topology.layer1

    # LAG メンバーシップマップ
    lag_membership: dict[str, dict] = {}
    for lag in l1.lag:
        for member in lag.members:
            lag_membership[member] = {
                "lag_id":   lag.id,
                "lag_type": lag.type,
            }

    for link in l1.links:
        ep0, ep1 = link.endpoints[0], link.endpoints[1]
        src = if_to_node.get(ep0, ep0)
        tgt = if_to_node.get(ep1, ep1)
        if src == tgt:
            continue
        data: dict = {
            "id":        link.id,
            "source":    src,
            "target":    tgt,
            "layer":     "layer1",
            "type":      "link",
            "source_if": if_to_name.get(ep0, ep0),
            "target_if": if_to_name.get(ep1, ep1),
        }
        if link.link_speed: data["link_speed"] = link.link_speed
        if link.mtu:        data["mtu"]        = link.mtu
        if link.link_role:  data["link_role"]  = link.link_role

        lag_info = lag_membership.get(ep0) or lag_membership.get(ep1)
        if lag_info:
            data["lag_id"]   = lag_info["lag_id"]
            data["lag_type"] = lag_info["lag_type"]

        elements["edges"].append({"data": data})

    # LAG バンドエッジ（太い半透明の束背景）
    # 各 (src, tgt, lag_id) ペアごとに 1 本だけ追加
    bundle_counts: dict[tuple, dict] = {}
    for link in l1.links:
        ep0, ep1 = link.endpoints[0], link.endpoints[1]
        src = if_to_node.get(ep0, ep0)
        tgt = if_to_node.get(ep1, ep1)
        if src == tgt:
            continue
        lag_info = lag_membership.get(ep0) or lag_membership.get(ep1)
        if not lag_info:
            continue
        key = (min(src, tgt), max(src, tgt), lag_info["lag_id"])
        if key not in bundle_counts:
            bundle_counts[key] = {"src": src, "tgt": tgt,
                                  "lag_id": lag_info["lag_id"],
                                  "lag_type": lag_info["lag_type"],
                                  "count": 0,
                                  "speed": link.link_speed or ""}
        bundle_counts[key]["count"] += 1

    for key, info in bundle_counts.items():
        n = info["count"]
        speed_label = f" {info['speed']}" if info["speed"] else ""
        elements["edges"].append({"data": {
            "id":           f"bundle-{info['lag_id']}-{info['src']}-{info['tgt']}",
            "source":       info["src"],
            "target":       info["tgt"],
            "layer":        "layer1",
            "type":         "lag_bundle",
            "lag_id":       info["lag_id"],
            "lag_type":     info["lag_type"],
            "member_count": n,
            "label":        f"×{n}{speed_label}",
        }})

    # attaches_to（supporting 関係）
    for node in l1.nodes:
        at = node.attaches_to
        if at is None:
            continue
        target = at if isinstance(at, str) else getattr(at, "node", None)
        if target:
            elements["edges"].append({"data": {
                "id":     f"attaches-{node.id}-{target}",
                "source": node.id,
                "target": target,
                "layer":  "cross",
                "type":   "attaches_to",
            }})


# ---------------------------------------------------------------------------
# L2 オーバーレイ（VLAN ノード + メンバーエッジ）
# ---------------------------------------------------------------------------

def _export_l2_overlay(topology, if_to_name, elements):
    if not topology.layer2:
        return

    # VLAN セグメント情報を layer3.interfaces (SVI) からサブネット・VRF を抽出
    # key: vlan.id (例: "vlan-100") → {subnet, vrf}
    # SVI の VLAN は attaches_to (または短縮形 interface: vlan-N) で解決する (ADR-0011 D3)。
    # ip は型で検証済みなので、旧実装の try/except ValueError による握りつぶしは不要になった
    vlan_segment: dict[str, dict] = {}
    if topology.layer3:
        vlan_ids = {vlan.id for vlan in topology.layer2.vlans}
        for iface in topology.layer3.interfaces:
            key = iface.attachment_ref()
            if key not in vlan_ids:
                continue
            seg = vlan_segment.setdefault(key, {})
            if iface.ip and "subnet" not in seg:
                seg["subnet"] = str(iface.ip.network)       # 192.168.100.1/24 → 192.168.100.0/24
            if iface.ipv6 and "subnet_v6" not in seg:
                seg["subnet_v6"] = str(iface.ipv6.network)
            if iface.vrf and "vrf" not in seg:
                seg["vrf"] = iface.vrf

    # VLAN ノード
    for vlan in topology.layer2.vlans:
        data: dict = {
            "id":      vlan.id,
            "label":   f"VLAN {vlan.vlan_id}" + (f"\n{vlan.name}" if vlan.name else ""),
            "layer":   "layer2",
            "type":    "vlan",
            "vlan_id": vlan.vlan_id,
        }
        if vlan.name:
            data["name"] = vlan.name
        seg = vlan_segment.get(vlan.id, {})
        if seg.get("subnet"):  data["subnet"]  = seg["subnet"]
        if seg.get("subnet_v6"): data["subnet_v6"] = seg["subnet_v6"]
        if seg.get("vrf"):     data["vrf_name"] = seg["vrf"]
        elements["nodes"].append({"data": data})
        # メンバーエッジ（VLAN → L1 ノード）。trunk(tagged) と access(untagged) を
        # 区別して保持する（ビューワのリンク沿い VLAN 表示用）。
        # trunk_ports のうち native=True は untagged 扱い。
        tagged: dict[str, list[str]] = {}
        untagged: dict[str, list[str]] = {}
        for pr in vlan.trunk_ports:
            name = if_to_name.get(pr.interface, pr.interface)
            (untagged if pr.native else tagged).setdefault(pr.node, []).append(name)
        for pr in vlan.access_ports:
            name = if_to_name.get(pr.interface, pr.interface)
            untagged.setdefault(pr.node, []).append(name)
        for node_id in {*tagged, *untagged}:
            data_e: dict = {
                "id":     f"vlan-{vlan.id}-{node_id}",
                "source": vlan.id,
                "target": node_id,       # L1 ノード ID を直接参照
                "layer":  "layer2",
                "type":   "vlan_member",
                "vlan_id": vlan.vlan_id,
            }
            if tagged.get(node_id):   data_e["tagged_on"]   = tagged[node_id]
            if untagged.get(node_id): data_e["untagged_on"] = untagged[node_id]
            elements["edges"].append({"data": data_e})

    # VxLAN ノード
    for vx in topology.layer2.vxlan:
        data: dict = {"layer": "layer2", "vni": vx.vni}
        if isinstance(vx, L2VxLAN):
            data.update({"id": vx.id, "label": f"L2VNI {vx.vni}", "type": "l2vni",
                         "vlan": vx.vlan})
        elif isinstance(vx, L3VxLAN):
            data.update({"id": vx.id, "label": f"L3VNI {vx.vni}", "type": "l3vni",
                         "vrf": vx.vrf})
        elements["nodes"].append({"data": data})


# ---------------------------------------------------------------------------
# L3 オーバーレイ（Routing Adjacency エッジ）
# ---------------------------------------------------------------------------

def _export_l3_overlay(topology, elements):
    if not topology.layer3:
        return

    for adj in topology.layer3.routing_adjacencies:
        elements["edges"].append({"data": {
            "id":       f"l3-{adj.id}",
            "source":   adj.from_.node,   # L1 ノード ID を直接参照
            "target":   adj.to.node,
            "layer":    "layer3",
            "type":     "routing_adjacency",
            "adj_type": adj.type,
        }})


# ---------------------------------------------------------------------------
# トンネル (ADR-0011 D6)
# ---------------------------------------------------------------------------

def _export_tunnels(topology, elements):
    """対向がトポロジー内にあるトンネルを辺として出力する。

    トンネル IF は destination を自分で持つので、辺は導出する (tunnel_links は持たない)。
    A→B と B→A の両方が書かれていれば 1 本にまとめる。対向が destination_ip のみの
    トンネルは、ノードの data["tunnels"] にだけ現れる。
    """
    if not topology.layer3:
        return
    l3if_node = {i.id: i.node for i in topology.layer3.interfaces}
    seen: set[tuple[str, str]] = set()
    for tun in topology.layer3.tunnel_interfaces:
        peer = l3if_node.get(tun.destination_interface) if tun.destination_interface else None
        if peer is None or peer == tun.node:
            continue
        pair = tuple(sorted((tun.node, peer)))
        if pair in seen:
            continue
        seen.add(pair)
        data: dict = {
            "id":          f"tunnel-{tun.id}",
            "source":      tun.node,
            "target":      peer,
            "layer":       "layer3",
            "type":        "tunnel",
            "tunnel_type": tun.type,
        }
        if tun.vrf: data["vrf"] = tun.vrf
        elements["edges"].append({"data": data})


# ---------------------------------------------------------------------------
# BGP オーバーレイ（BGP セッション エッジ）
# ---------------------------------------------------------------------------

def _export_bgp_overlay(topology, elements):
    if not topology.protocols:
        return

    seen: set[str] = set()
    for bgp in topology.protocols.bgp:
        for bn in bgp.nodes:
            for nb in bn.neighbors:
                key = f"{bn.node}-{nb.node}-{bgp.id}"
                if key in seen:
                    continue
                seen.add(key)

                as_label = ""
                if bn.local_as and nb.remote_as:
                    as_label = f"AS{bn.local_as}→{nb.remote_as}"

                elements["edges"].append({"data": {
                    "id":              f"bgp-{key}",
                    "source":          bn.node,    # L1 ノード ID を直接参照
                    "target":          nb.node,
                    "layer":           "protocols",
                    "type":            "bgp_session",
                    "bgp_type":        nb.type or "unknown",
                    "label":           as_label,
                    "process":         bgp.id,
                    "process_role":    bgp.role,
                    "bfd":             nb.bfd,
                    "local_as":        bn.local_as,
                    "remote_as":       nb.remote_as,
                    "address_families": nb.address_families,
                }})
