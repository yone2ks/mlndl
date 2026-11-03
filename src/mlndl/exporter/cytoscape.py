"""Cytoscape.js JSON エクスポーター (ndl-viz 向け)

設計方針:
  - L1 が常時表示の基盤レイヤー
  - L2 / L3 / 制御プレーン (BGP / OSPF / IS-IS) は L1 ノードに重ねるオーバーレイ
  - 全エッジの source/target は L1 ノード ID を直接参照（prefix なし）
  - ノードは L1 の `node` タイプのみ。L3 IP・VRF・VLAN 情報はデータに埋め込む
"""

from __future__ import annotations

import json
from collections import defaultdict

from ..derive import (BgpSessionView, SessionEnd, bgp_session_views, igp_adjacency_views, l3_and_tunnels,
                      l3_attachments, l3_roles, outside_svi_subnet, vlan_endpoints, vlan_svi_networks)
from ..schema.control_plane import BgpSession
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
    _export_bridges(topology, elements)
    _export_tunnels(topology, elements)
    _export_routing_neighbors(topology, elements)

    return elements


def export_json(topology: MLNDLTopology, indent: int = 2) -> str:
    return json.dumps(export(topology), ensure_ascii=False, indent=indent)


def _interface_nodes(topology: MLNDLTopology) -> dict[str, list[str]]:
    """L1 IF / LAG の id → それが載るノード群。MLAG は 2 ノード"""
    nodes: dict[str, list[str]] = {}
    if topology.layer1:
        for iface in topology.layer1.interfaces:
            nodes[iface.id] = [iface.node]
        for lag in topology.layer1.lag:
            nodes[lag.id] = [lag.node] if isinstance(lag, LacpLag) else list(lag.nodes)
    return nodes


# 旧 kind (ndl_version 1.x の間だけ併記)。分類 (ADR-0011 D11) から写し、name では判定しない
_LEGACY_KIND = {"l1_interface": "routed", "lag": "routed", "vlan": "svi",
                "subinterface": "subinterface", "unattached": "loopback"}


def _legacy_lo(cands: list, roles: dict[str, list[str]]):
    """旧 lo_ip / lo_ipv6 にする L3 IF (旧ビューワのための互換値。1.x 限定の推定。ADR-0011 D11)

    unattached の L3 IF のうち、update_source に使われているもの → VTEP の source ではないもの → 先に書かれたもの。
    選び方は docs/exporter-cytoscape.md の「旧キー lo_ip / lo_ipv6」と合わせること
    """
    for pick in (lambda i: "update_source" in roles.get(i.id, []),
                 lambda i: "vtep_source" not in roles.get(i.id, []),
                 lambda i: True):
        for iface in cands:
            if pick(iface):
                return iface
    return None


def _port_nodes(pr, interface_nodes: dict[str, list[str]]) -> list[str]:
    """PortRef が載るノード群。ノードは interface / lag から導出する (ADR-0013 D2)"""
    return interface_nodes.get(pr.target) or ([pr.node] if pr.node else [])


def _vtep_info(topology: MLNDLTopology) -> dict[str, dict]:
    """VTEP の id → {"nodes": 終端するノード, "sources": ノード → L3 IF, アドレス}

    ノードは sources の各 L3 IF から決まる。アドレスは address / address_v6 を使い、
    省略されていれば (sources が 1 つのとき) その L3 IF の ip / ipv6 を使う (ADR-0014 D2)。
    """
    if not topology.layer2 or not topology.layer3:
        return {}
    l3ifs = {i.id: i for i in topology.layer3.interfaces}
    info: dict[str, dict] = {}
    for vtep in topology.layer2.vteps:
        srcs = [l3ifs[s] for s in vtep.sources if s in l3ifs]
        own = srcs[0] if len(vtep.sources) == 1 and srcs else None
        address    = vtep.address    or (own.ip   if own else None)
        address_v6 = vtep.address_v6 or (own.ipv6 if own else None)
        entry: dict = {
            "nodes":   list(dict.fromkeys(i.node for i in srcs)),
            "sources": {i.node: i for i in srcs},
        }
        if address:    entry["address"]    = str(address)
        if address_v6: entry["address_v6"] = str(address_v6)
        info[vtep.id] = entry
    return info


def _l3vni_vteps(topology: MLNDLTopology, vx: L3VxLAN, vteps: dict[str, dict]) -> list[str]:
    """L3VNI が載る VTEP。L3VNI は vteps を持たないので、VRF から導く (ADR-0014 D3)

    その VRF に属する L3 IF を持つノードが終端する VTEP。1 ノードが複数の VTEP を
    終端していれば (Multi-Site BGW 等)、その全部に載るとみなす。
    """
    if not topology.layer3:
        return []
    vrf_nodes = {i.node for i in topology.layer3.interfaces if i.vrf == vx.vrf}
    return [vid for vid, v in vteps.items() if vrf_nodes & set(v["nodes"])]


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
    node_vteps: dict[str, list[dict]] = defaultdict(list)
    vlan_ids = {v.id for v in topology.layer2.vlans} if topology.layer2 else set()

    # サブ IF は親 (L1 IF / LAG) のノードに埋め込む。MLAG 上のサブ IF は両ノードに存在する (ADR-0012)
    parent_nodes = _interface_nodes(topology)
    subifs = {si.id: si for si in topology.layer2.subinterfaces} if topology.layer2 else {}
    for si in subifs.values():
        entry = {"id": si.id, "parent": si.attaches_to.target, "vlan_id": si.vlan_id}
        if si.name: entry["name"] = si.name
        if si.description: entry["description"] = si.description
        for nid in parent_nodes.get(si.attaches_to.target, []):
            node_subifs[nid].append(entry)
    lag_ids = {lag.id for lag in topology.layer1.lag}
    attachments = l3_attachments(topology)
    roles = l3_roles(topology)
    if topology.layer3:
        for iface in topology.layer3.interfaces:
            if iface.ip or iface.ipv6:
                ref = iface.attachment_ref()
                vlan = ref if ref in vlan_ids else None
                subif = subifs.get(ref)
                attachment = attachments[iface.id]
                # 分類と役割は参照から決める (ADR-0011 D11)。attaches_to は YAML と同じ形で出す
                entry: dict = {"id": iface.id, "name": iface.name, "attachment": attachment}
                if iface.attaches_to is not None:
                    entry["attaches_to"] = {iface.attaches_to.kind: iface.attaches_to.target}
                if roles.get(iface.id): entry["roles"] = roles[iface.id]
                # 旧キー (1.x の間だけ): interface (= name)、kind
                entry["interface"] = iface.name
                entry["kind"] = _LEGACY_KIND[attachment]
                if iface.ip:   entry["ip"]   = str(iface.ip)
                if iface.ipv6: entry["ipv6"] = str(iface.ipv6)
                if iface.vrf:  entry["vrf"]  = iface.vrf
                if vlan:       entry["vlan"] = vlan
                if iface.description: entry["description"] = iface.description
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
        # 旧 lo_ip / lo_ipv6 (1.x の間だけ): 互換値として 1 つ選ぶ。名前では選ばない
        for nid in {i.node for i in topology.layer3.interfaces}:
            for fld, out in (("ip", lo_ip), ("ipv6", lo_ipv6)):
                cands = [i for i in topology.layer3.interfaces
                         if i.node == nid and attachments[i.id] == "unattached" and getattr(i, fld) is not None]
                rep = _legacy_lo(cands, roles)
                if rep is not None:
                    out[nid] = str(getattr(rep, fld))
        for tun in topology.layer3.tunnel_interfaces:
            node_tunnels[tun.node].append(
                tun.model_dump(mode="json", exclude_none=True, exclude={"node"})
            )

    # 終端する VTEP をノードに埋め込む。共有 VTEP (sources が複数) は各ノードに載り、
    # shared_with に相手のノードが入る (ADR-0014)
    for vid, v in _vtep_info(topology).items():
        for nid in v["nodes"]:
            entry = {"id": vid, "source": v["sources"][nid].name}
            if "address" in v:    entry["address"]    = v["address"]
            if "address_v6" in v: entry["address_v6"] = v["address_v6"]
            others = [n for n in v["nodes"] if n != nid]
            if others:            entry["shared_with"] = others
            node_vteps[nid].append(entry)

    # L2 VLAN メンバーシップをノード別に集約
    node_vlans: dict[str, list[str]] = defaultdict(list)
    if topology.layer2:
        for vlan in topology.layer2.vlans:
            for pr in [*vlan.trunk_ports, *vlan.access_ports]:
                for nid in _port_nodes(pr, parent_nodes):
                    if vlan.id not in node_vlans[nid]:
                        node_vlans[nid].append(vlan.id)

    # BGP の AS 番号をノード別に (機器カードの表示用)。default VRF のインスタンスを優先し、なければ最初に出てくるもの
    node_local_as: dict[str, int] = {}
    if topology.control_plane:
        for inst in sorted(topology.control_plane.bgp, key=lambda b: b.vrf is not None):
            for n in inst.nodes:
                node_local_as.setdefault(n.node, n.local_as)

    # BGP セッションをノード別に。相手がトポロジー外のセッションも含め、その機器のセッションをすべて入れる
    # (トンネルの tunnels と同じ形。ADR-0010 D11)
    node_bgp_sessions: dict[str, list[dict]] = defaultdict(list)
    for v in bgp_session_views(topology):
        for own, other in ((v.from_, v.to), (v.to, v.from_)):
            if own.node is not None:
                node_bgp_sessions[own.node].append({**_session_data(v), "local": _end_data(own), "peer": _end_data(other)})

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
        if node.description:    data["description"] = node.description

        # L3 データを埋め込む（overlay 有効時に参照）
        if lo_ip.get(node.id):        data["lo_ip"]          = lo_ip[node.id]
        if lo_ipv6.get(node.id):      data["lo_ipv6"]        = lo_ipv6[node.id]
        if node_tunnels[node.id]:     data["tunnels"]        = node_tunnels[node.id]
        if node_subifs[node.id]:      data["subinterfaces"]  = node_subifs[node.id]
        if node_vteps[node.id]:       data["vteps"]          = node_vteps[node.id]
        if node_l3ifs[node.id]:       data["l3_interfaces"]  = node_l3ifs[node.id]
        if node_vrfs[node.id]:        data["vrfs"]           = node_vrfs[node.id]

        # L2 VLAN データを埋め込む
        if node_vlans[node.id]:       data["vlans"]    = node_vlans[node.id]

        # BGP (ADR-0010 D11)
        if node.id in node_local_as:   data["local_as"]     = node_local_as[node.id]
        if node_bgp_sessions[node.id]: data["bgp_sessions"] = node_bgp_sessions[node.id]

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
        if link.description: data["description"] = link.description

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
    interface_nodes = _interface_nodes(topology)

    # VLAN セグメント情報を layer3.interfaces (SVI) からサブネット・VRF を抽出
    # key: vlan.id (例: "vlan-100") → {subnet, vrf}
    # SVI の VLAN は attaches_to: {vlan:} で解決する (ADR-0011 D3)。
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

    # VLAN の端点 (ADR-0013 D7)。vlan_member エッジ (VLAN, ポートのノード) ごとに出す
    endpoints = _vlan_endpoint_data(topology)

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
        if vlan.description:
            data["description"] = vlan.description
        seg = vlan_segment.get(vlan.id, {})
        if seg.get("subnet"):  data["subnet"]  = seg["subnet"]
        if seg.get("subnet_v6"): data["subnet_v6"] = seg["subnet_v6"]
        if seg.get("vrf"):     data["vrf_name"] = seg["vrf"]
        elements["nodes"].append({"data": data})
        # メンバーエッジ（VLAN → L1 ノード）。trunk(tagged) と access(untagged) を
        # 区別して保持する（ビューワのリンク沿い VLAN 表示用）。
        # trunk_ports のうち native=True は untagged 扱い。
        # LAG を指すポートは LAG の id のまま出す。MLAG は両ノードに出す (ADR-0013)
        tagged: dict[str, list[str]] = {}
        untagged: dict[str, list[str]] = {}
        for pr in vlan.trunk_ports:
            name = if_to_name.get(pr.target, pr.target)
            for nid in _port_nodes(pr, interface_nodes):
                (untagged if pr.native else tagged).setdefault(nid, []).append(name)
        for pr in vlan.access_ports:
            name = if_to_name.get(pr.target, pr.target)
            for nid in _port_nodes(pr, interface_nodes):
                untagged.setdefault(nid, []).append(name)
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
            if endpoints.get((vlan.id, node_id)):
                data_e["endpoints"] = endpoints[(vlan.id, node_id)]
            elements["edges"].append({"data": data_e})

    # VxLAN ノード。vteps は L2VNI なら書かれたもの、L3VNI なら VRF から導いたもの
    vteps = _vtep_info(topology)
    for vx in topology.layer2.vxlan:
        data: dict = {"layer": "layer2", "vni": vx.vni}
        if isinstance(vx, L2VxLAN):
            data.update({"id": vx.id, "label": f"L2VNI {vx.vni}", "type": "l2vni",
                         "vlan": vx.vlan})
            if vx.vteps:
                data["vteps"] = list(vx.vteps)       # ADR-0014
        elif isinstance(vx, L3VxLAN):
            data.update({"id": vx.id, "label": f"L3VNI {vx.vni}", "type": "l3vni",
                         "vrf": vx.vrf})
            derived = _l3vni_vteps(topology, vx, vteps)
            if derived:
                data["vteps"] = derived              # ADR-0014 D3
        if vx.description:
            data["description"] = vx.description
        elements["nodes"].append({"data": data})


def _export_bridges(topology, elements):
    """bridge を要素として出す (ADR-0018 D5)。番号を持たない L2 セグメント。描き方はビューワが決める"""
    if not topology.layer2:
        return
    interface_nodes = _interface_nodes(topology)
    for br in topology.layer2.bridges:
        ports = []
        for port in br.ports:
            entry = {"interface": port.interface} if port.interface is not None else {"lag": port.lag}
            entry["nodes"] = interface_nodes.get(port.target, [])
            ports.append(entry)
        data: dict = {
            "id":    br.id,
            "label": br.name or br.id,
            "layer": "layer2",
            "type":  "bridge",
            "ports": ports,
            "nodes": list(dict.fromkeys(n for p in ports for n in p["nodes"])),
        }
        if br.name:        data["name"] = br.name
        if br.description: data["description"] = br.description
        elements["nodes"].append({"data": data})


def _vlan_endpoint_data(topology) -> dict[tuple[str, str], list[dict]]:
    """(VLAN id, ポートのノード) → そのノードのポートの対向にいる VLAN の端点 (ADR-0013 D7)

    導出は derive.vlan_endpoints が参照 (id) だけで行う。IF の name では引かない (ADR-0011 D3)。
    L3 IF が 1 つに決まれば (direct / tag_match) その名前とアドレスを、決まらなければ (ambiguous) 候補を出す。
    """
    names = {i.id: i.name or i.id for i in topology.layer1.interfaces} if topology.layer1 else {}
    svi_nets = vlan_svi_networks(topology)
    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for ep in vlan_endpoints(topology):
        entry: dict = {
            "node":            ep.node,
            "interfaces":      ep.interfaces,
            "interface_names": [names.get(i, i) for i in ep.interfaces],
            "tagged":          ep.tagged,
            "resolution":      ep.resolution,
        }
        if ep.lag: entry["lag"] = ep.lag
        if ep.resolution in ("direct", "tag_match"):
            l3 = ep.l3_interfaces[0]
            entry["l3_interface"] = l3.id
            entry["name"] = l3.name
            if l3.ip:   entry["ip"]   = str(l3.ip)
            if l3.ipv6: entry["ipv6"] = str(l3.ipv6)
            outside = outside_svi_subnet(ep, svi_nets)
            if outside: entry["outside_svi_subnet"] = outside
        elif ep.resolution == "ambiguous":
            entry["candidates"] = [
                {"l3_interface": c.id, "name": c.name,
                 **({"ip": str(c.ip)} if c.ip else {}), **({"ipv6": str(c.ipv6)} if c.ipv6 else {})}
                for c in ep.l3_interfaces
            ]
        out[(ep.vlan, ep.port_node)].append(entry)
    return out


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
        if tun.description: data["description"] = tun.description
        elements["edges"].append({"data": data})


# ---------------------------------------------------------------------------
# 制御プレーンのセッション (ADR-0010 D11)
# ---------------------------------------------------------------------------

def _end_data(end: SessionEnd) -> dict:
    """セッションの片端。トポロジー外の相手は address と local_as だけ"""
    data: dict = {}
    if end.node is not None:    data["node"] = end.node
    if end.address is not None: data["address"] = str(end.address)
    iface = end.l3_interface
    if iface is not None:
        data["l3_interface"] = iface.id         # トンネル IF のこともある (ADR-0018 D3)
        name = getattr(iface, "name", None)      # トンネル IF は name を持たない
        if name: data["interface_name"] = name
        if iface.ip:   data["ip"]   = str(iface.ip)
        if iface.ipv6: data["ipv6"] = str(iface.ipv6)
        if end.unnumbered: data["unnumbered"] = True
    if end.local_as is not None:   data["local_as"] = end.local_as
    if end.route_reflector_client: data["route_reflector_client"] = True
    return data


def _session_data(v: BgpSessionView) -> dict:
    """BGP セッションの、端に依らない値。どれも参照をたどって決めた値 (derive.bgp_session_views)"""
    data: dict = {"id": v.session.id}
    if v.instance is not None: data["instance"] = v.instance.id
    if v.vrf is not None:      data["vrf"] = v.vrf
    if v.bgp_type is not None: data["bgp_type"] = v.bgp_type
    data["address_families"] = list(v.session.address_families)
    if v.transport is not None:
        data["transport_link"] = v.transport.as_dict()
    data["bfd"] = v.session.bfd
    if v.session.description: data["description"] = v.session.description
    return data


def _export_routing_neighbors(topology, elements):
    """セッションを辺として出力する。1 セッション = 1 辺。

    BGP は両端がトポロジー内のセッションだけを辺にする (相手がトポロジー外のものは、ノードの data["bgp_sessions"] にだけ現れる)。
    通り道 (transport_link) は YAML の attaches_to ではなく、update_source の L3 IF から導いた値 (ADR-0010 D7)。
    """
    if not topology.control_plane:
        return
    for v in bgp_session_views(topology):
        if v.from_.node is None or v.to.node is None:
            continue
        elements["edges"].append({"data": {
            **_session_data(v),
            "source":   v.from_.node,
            "target":   v.to.node,
            "layer":    "control_plane",
            "type":     "routing_neighbor",
            "protocol": "bgp",
            "from":     _end_data(v.from_),
            "to":       _end_data(v.to),
        }})

    l3ifs = l3_and_tunnels(topology)        # OSPF の interface はトンネル IF も指せる (ADR-0018 D3)
    l1ifs = {i.id: i for i in topology.layer1.interfaces} if topology.layer1 else {}
    transports = {v.index: v.transport for v in igp_adjacency_views(topology)}
    for index, nb in enumerate(topology.control_plane.routing_neighbors):
        if isinstance(nb, BgpSession):
            continue
        ifaces = l3ifs if nb.type == "ospf" else l1ifs
        ends = []
        for ep in (nb.from_, nb.to):
            end = {"node": ep.node, "interface": ep.interface}
            name = getattr(ifaces.get(ep.interface), "name", None)
            if name: end["interface_name"] = name
            ends.append(end)
        data: dict = {
            "id":       nb.id,
            "source":   nb.from_.node,
            "target":   nb.to.node,
            "layer":    "control_plane",
            "type":     "routing_neighbor",
            "protocol": nb.type,
            "from":     ends[0],
            "to":       ends[1],
            "bfd":      nb.bfd,
        }
        if nb.instance: data["instance"] = nb.instance
        if transports.get(index) is not None: data["transport_link"] = transports[index].as_dict()   # ADR-0018 D4
        if nb.type == "ospf": data["area"] = nb.area
        else:                 data["level"] = nb.level
        if nb.description: data["description"] = nb.description
        elements["edges"].append({"data": data})
