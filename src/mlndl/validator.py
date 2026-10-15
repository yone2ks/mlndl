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
    - vlans[].trunk_ports/access_ports[].node → L1 nodes (省略可。ADR-0013)
    - vlans[].trunk_ports/access_ports[].interface → L1 interfaces ∪ lag (ADR-0013)
    - vxlan[l2vni].vlan → layer2.vlans
    - vxlan[l2vni].vtep_source → layer3.interfaces
    - vxlan[l2vni].members[] → L1 nodes
    - vxlan[l2vni].vtep_source の node が members に含まれるか
    - trunk_ports/access_ports の interface が、同じ node に属するか。MLAG には node を書けない
    - 同じ VLAN に LAG とそのメンバーを書いていないか (error)。メンバーだけなら warning
    - 同じ VLAN に同じ interface を 2 回書いていないか
    - subinterfaces[].attaches_to.interface → L1 interfaces ∪ lag (ADR-0012)
    - 同一の親 (L1 IF / LAG) 上で subinterfaces[].vlan_id が重複していないか

  ID の文法 (ADR-0002 D1):
    - layer1 / layer2 / layer3 / protocols の全エンティティの id が正規表現に従い、63 文字以内か

  ID 空間 (ADR-0002 D5 / ADR-0012):
    - L1 interface / LAG / VLAN / サブ IF の ID は互いに重複しないこと
      ({interface: X} は X をこれらの空間で解決するため、重複すると解決先が曖昧になる)
    - vxlan[l3vni].vrf → layer3.vrfs
    - VNI 番号のグローバル一意性

  Layer 3 (ADR-0011):
    - vrfs[].l3vni → layer2.vxlan (type=l3vni)。L3VxLAN.vrf との双方向一致
    - vrfs[].rd / route_targets フォーマット (ASN:NN or IP:NN)
    - interfaces[].node → L1 nodes
    - interfaces[].vrf → layer3.vrfs
    - interfaces[].attaches_to → L1 interfaces ∪ lag ∪ layer2.vlans ∪ layer2.subinterfaces
      (L3Interface のみ。ADR-0011 D3 / ADR-0012)
    - interfaces[].interface: vlan-N の短縮形 → layer2.vlans
    - 短縮形と明示した attaches_to の食い違い
    - attaches_to が L1 IF / LAG / サブ IF を指す場合、その node (群) に L3 IF の node が含まれるか
    - 同一 (node, interface) の重複
    - gateway_redundancy: IPv4 VIP のサブネット一致、同一 IF・同一 mode・同一 AF の group_id 重複
    - anycast_gateway: 同じ VLAN に載る SVI 群で ip / ipv6 / anycast_mac が一致するか
    - tunnel_interfaces[]: node / source / destination_interface / vrf / transport_vrf 参照、
      source が同じ node の L3 IF か、destination_interface が別ノードか、
      source と destination の外側のアドレスファミリーが一致するか
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

  VLAN ID:
    - 同一ノード上で、別の VLAN エントリが同じ vlan_id を使っていないか

  規約 (severity = warning / ADR-0002 D7・ADR-0009 D3):
    - 推奨プレフィックス: link- / lag- / vlan- / vni- / vrf- / tunnel- / subif- / bfd- /
      bgp-peer- / ospf-adj- / isis-adj-
    - interface が VLAN らしき名前なのに attaches_to が未指定 (ADR-0011 D3)
    - labels のキーが ADR-0002 D1 の ID 正規表現に従っているか

Severity (ADR-0002 D8):
  error   仕様違反。トポロジーは無効
  warning 仕様上は合法だが規約違反。validate() の戻り値には含めない
  info    注意喚起のみ

  validate(topology)              → error のみの list（後方互換）
  validate_all(topology, strict=) → ValidationResult(errors / warnings / notes)
                                    strict=True で warning を error に昇格
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .schema.layer1 import AttachesToObj, LacpLag, MlagLag
from .schema.layer2 import L2VxLAN, L3VxLAN
from .schema.topology import MLNDLTopology

_RT_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+:\d+$|^\d+:\d+$")

# ADR-0002 D1
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_ID_MAX_LEN = 63    # DNS ラベルの上限を継承 (ADR-0002 D1)

# ID を持つエンティティのリストを探すセクション。リストの列挙はスキーマから行うので、
# エンティティを追加しても文法チェックの対象から漏れない
_ID_SECTIONS = ("layer1", "layer2", "layer3", "protocols")

# ADR-0002 D7 推奨プレフィックス（隣接関係は type ごとに異なる）
_ADJ_PREFIX = {"bgp": "bgp-peer-", "ospf": "ospf-adj-", "isis": "isis-adj-"}

Severity = Literal["error", "warning", "info"]


@dataclass
class ValidationError:
    """バリデーション結果 1 件。severity は ADR-0002 D8 に従う"""
    path: str
    message: str
    severity: Severity = "error"

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class ValidationResult:
    """validate_all() の戻り値"""
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    notes: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """error が 1 件もなければ True（warning / info は問わない）"""
        return not self.errors


def validate(topology: MLNDLTopology) -> list[ValidationError]:
    """トポロジーの参照整合性・整合性ルールを検証する。

    Returns:
        severity が error の ValidationError のリスト。空リストなら問題なし。
        warning / info を含めた結果が必要な場合は validate_all() を使う。
    """
    return validate_all(topology).errors


def validate_all(topology: MLNDLTopology, *, strict: bool = False) -> ValidationResult:
    """error / warning / info をすべて返す。

    Args:
        strict: True なら warning を error に昇格する (ADR-0002 D8 の strict モード)
    """
    issues = _collect(topology)
    result = ValidationResult()
    for issue in issues:
        if issue.severity == "warning" and strict:
            issue = ValidationError(issue.path, f"{issue.message} (strict)", "error")
        {"error": result.errors, "warning": result.warnings, "info": result.notes}[issue.severity].append(issue)
    return result


def _collect(topology: MLNDLTopology) -> list[ValidationError]:
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
    iface_node: dict[str, str] = {}      # L1 interface id → node id
    lag_nodes: dict[str, set[str]] = {}  # LAG id → node id 群 (lacp は 1、mlag は 2)
    member_lag: dict[str, str] = {}      # LAG のメンバー L1 IF id → LAG id
    subif_ids: set[str] = set()
    subif_nodes: dict[str, set[str]] = {}  # サブ IF id → 親から導出した node id 群
    l3iface_node: dict[str, str] = {}    # L3 interface id → node id

    if topology.layer1:
        l1 = topology.layer1
        node_ids = {n.id for n in l1.nodes}
        interface_ids = {i.id for i in l1.interfaces}
        link_ids = {lk.id for lk in l1.links}
        lag_ids = {lag.id for lag in l1.lag}
        iface_node = {i.id: i.node for i in l1.interfaces}
        lag_nodes = {
            lag.id: ({lag.node} if isinstance(lag, LacpLag) else set(lag.nodes)) for lag in l1.lag
        }
        member_lag = {m: lag.id for lag in l1.lag for m in lag.members}

    if topology.layer2:
        l2 = topology.layer2
        vlan_ids = {v.id for v in l2.vlans}
        l3vni_ids = {v.id for v in l2.vxlan if v.type == "l3vni"}
        subif_ids = {si.id for si in l2.subinterfaces}
        for si in l2.subinterfaces:
            parent = si.attaches_to.target
            if parent in iface_node:
                subif_nodes[si.id] = {iface_node[parent]}
            elif parent in lag_nodes:
                subif_nodes[si.id] = set(lag_nodes[parent])

    if topology.layer3:
        l3 = topology.layer3
        vrf_ids = {v.id for v in l3.vrfs}
        l3interface_ids = {i.id for i in l3.interfaces}
        l3iface_node = {i.id: i.node for i in l3.interfaces}

    # ── ID の文法 (ADR-0002 D1) ──────────────────────────────────────────
    _check_id_grammar(topology, errors)

    # attaches_to / VLAN のポートのキーが指す ID 空間 (ADR-0001 D8)
    spaces = {
        "node": node_ids, "interface": interface_ids, "lag": lag_ids,
        "vlan": vlan_ids, "subinterface": subif_ids, "link": link_ids,
    }

    # ── ID 空間の重複 (ADR-0002 D5) ─────────────────────────────────────
    _check_interface_id_spaces(
        {"L1 インターフェース": interface_ids, "LAG": lag_ids,
         "VLAN": vlan_ids, "サブインターフェース": subif_ids},
        errors,
    )

    # ── Layer 1 ──────────────────────────────────────────────────────────
    if topology.layer1:
        _validate_l1(topology.layer1, node_ids, interface_ids, lag_ids, spaces, errors)

    # ── Layer 2 ──────────────────────────────────────────────────────────
    if topology.layer2:
        _validate_l2(
            topology.layer2,
            node_ids, iface_node, lag_nodes, member_lag, spaces,
            vlan_ids, l3vni_ids, vrf_ids, l3interface_ids, l3iface_node,
            errors,
        )

    # ── Layer 3 ──────────────────────────────────────────────────────────
    if topology.layer3:
        _validate_l3(
            topology.layer3, topology.layer2,
            node_ids, iface_node, lag_nodes, subif_nodes, spaces,
            l3vni_ids, vrf_ids, l3interface_ids, l3iface_node, vlan_ids,
            errors,
        )

    # ── Protocols ────────────────────────────────────────────────────────
    if topology.protocols:
        _validate_protocols(topology.protocols, node_ids, errors)

    # ── MTU 整合性 ───────────────────────────────────────────────────────
    _validate_mtu(topology, errors)

    # ── 規約 (warning) ───────────────────────────────────────────────────
    _check_conventions(topology, errors)

    return errors


# ---------------------------------------------------------------------------
# Layer 1
# ---------------------------------------------------------------------------

def _validate_l1(l1, node_ids, interface_ids, lag_ids, spaces, errors):
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
            _check_attaches_to(node.attaches_to, f"layer1.nodes[{i}].attaches_to", spaces, errors)
    for i, iface in enumerate(l1.interfaces):
        if iface.attaches_to is not None:
            _check_attaches_to(iface.attaches_to, f"layer1.interfaces[{i}].attaches_to", spaces, errors)


# ---------------------------------------------------------------------------
# Layer 2
# ---------------------------------------------------------------------------

def _port_nodes(pr, kind, path, iface_node, lag_nodes, node_ids, errors) -> set[str]:
    """VLAN のポートが載るノード群を返す (ADR-0013 D2)

    node は書かない (interface / lag から導出する)。ndl_version 1.x の間は旧形式として受け付けて
    warning を出し、導出したノードと照合する。MLAG は両ノードに効くので node を書くと error
    """
    if kind == "interface":
        owners = {iface_node[pr.target]}
    elif kind == "lag":
        owners = set(lag_nodes[pr.target])
    else:
        return set()
    if pr.node is None:
        return owners
    errors.append(ValidationError(
        f"{path}.node",
        f"VLAN のポートには node を書きません。ノードは '{pr.target}' から導出します。"
        f"node を消してください (ADR-0013 D2)",
        "warning",
    ))
    if pr.node not in node_ids:
        errors.append(ValidationError(f"{path}.node", f"未定義のノード '{pr.node}' を参照しています"))
    elif kind == "lag" and len(owners) > 1:
        errors.append(ValidationError(
            f"{path}.node",
            f"MLAG '{pr.target}' は {' / '.join(sorted(owners))} の両方に効くため、node は書けません (ADR-0013 D2)",
        ))
    elif pr.node not in owners:
        what = "インターフェース" if kind == "interface" else "LAG"
        errors.append(ValidationError(
            f"{path}.{pr_key(pr)}",
            f"{what} '{pr.target}' はノード '{next(iter(owners))}' に属しており、"
            f"'{pr.node}' のものではありません (ADR-0013 D2)",
        ))
    return owners


def pr_key(pr) -> str:
    """PortRef に書かれた参照キー (interface / lag)"""
    return "interface" if pr.interface is not None else "lag"


def _validate_l2(l2, node_ids, iface_node, lag_nodes, member_lag, spaces,
                 vlan_ids, l3vni_ids, vrf_ids, l3interface_ids, l3iface_node, errors):
    # VLAN trunk_ports / access_ports (ADR-0013)
    # interface (L1 IF) か lag (LAG) で指す。node は書かず、参照先から導出する
    vlans_on_node: dict[tuple[str, int], list[str]] = {}
    vlan_nodes: dict[str, set[str]] = {}
    for i, vlan in enumerate(l2.vlans):
        ports = [(f"trunk_ports[{j}]", pr) for j, pr in enumerate(vlan.trunk_ports)]
        ports += [(f"access_ports[{j}]", pr) for j, pr in enumerate(vlan.access_ports)]
        listed = {pr.target for _, pr in ports}
        seen: dict[str, str] = {}
        for where, pr in ports:
            path = f"layer2.vlans[{i}].{where}"
            if pr.target in seen:
                errors.append(ValidationError(
                    f"{path}.{pr_key(pr)}",
                    f"'{pr.target}' はこの VLAN の {seen[pr.target]} にも書かれています (ADR-0013 D4)",
                ))
            else:
                seen[pr.target] = where
            kind = _resolve_ref(pr_key(pr), pr.target, spaces, f"{path}.{pr_key(pr)}", errors,
                                legacy_kinds=("lag",))
            nodes = _port_nodes(pr, kind, path, iface_node, lag_nodes, node_ids, errors)
            vlan_nodes.setdefault(vlan.id, set()).update(nodes)
            for node in nodes:
                owners = vlans_on_node.setdefault((node, vlan.vlan_id), [])
                if vlan.id not in owners:
                    owners.append(vlan.id)

            # LAG のメンバーに VLAN は設定しない。設定は LAG 側にあり、メンバーはそれを継承する
            lag = member_lag.get(pr.target) if kind == "interface" else None
            if lag is None:
                continue
            if lag in listed:
                errors.append(ValidationError(
                    f"{path}.interface",
                    f"'{pr.target}' は LAG '{lag}' のメンバーです。LAG とそのメンバーを同じ VLAN に"
                    f"書くことはできません。LAG だけを書いてください (ADR-0013 D3)",
                ))
            else:
                errors.append(ValidationError(
                    f"{path}.interface",
                    f"'{pr.target}' は LAG '{lag}' のメンバーです。VLAN は LAG を指して書いてください"
                    f" (lag: {lag}) (ADR-0013 D3)",
                    "warning",
                ))

    # VLAN ID — 同一ノード上で別の VLAN エントリが同じ vlan_id を使っていないか
    # (別ノードで同じ番号を使うのはサイトローカルな再利用として許容する)
    for (node, vid), owners in vlans_on_node.items():
        if len(owners) > 1:
            errors.append(ValidationError(
                f"layer2.vlans[{', '.join(owners)}]",
                f"ノード '{node}' 上で VLAN ID {vid} が重複しています ({' / '.join(owners)})",
            ))

    # Subinterfaces (ADR-0012)
    seen_tag: dict[tuple[str, int], int] = {}
    for i, si in enumerate(l2.subinterfaces):
        at = si.attaches_to
        _resolve_ref(at.kind, at.target, spaces, f"layer2.subinterfaces[{i}].attaches_to.{at.kind}",
                     errors, legacy_kinds=("lag",))
        key = (at.target, si.vlan_id)
        if key in seen_tag:
            errors.append(ValidationError(
                f"layer2.subinterfaces[{i}].vlan_id",
                f"'{at.target}' 上で VLAN タグ {si.vlan_id} が subinterfaces[{seen_tag[key]}] と"
                f"重複しています (ADR-0012 D5)",
            ))
        else:
            seen_tag[key] = i

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
            vtep_node = l3iface_node.get(vx.vtep_source)
            if vtep_node is not None and vx.members and vtep_node not in vx.members:
                errors.append(ValidationError(
                    f"layer2.vxlan[{i}].vtep_source",
                    f"vtep_source '{vx.vtep_source}' のノード '{vtep_node}' が members に含まれていません"
                    f" (ADR-0011 D9)",
                ))
            # VNI のメンバーなのに、その VLAN のポートが 1 つもないノード (round4 E10)。
            # VLAN にポートが書かれていない場合は判断できないので見ない
            carried = vlan_nodes.get(vx.vlan)
            if carried:
                for j, m in enumerate(vx.members):
                    if m in node_ids and m not in carried:
                        errors.append(ValidationError(
                            f"layer2.vxlan[{i}].members[{j}]",
                            f"VNI のメンバー '{m}' には VLAN '{vx.vlan}' のポートがありません。"
                            f"VLAN を載せ忘れていないか確認してください (ADR-0011 D9)",
                            "warning",
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

def _validate_l3(l3, l2, node_ids, iface_node, lag_nodes, subif_nodes, spaces,
                 l3vni_ids, vrf_ids, l3interface_ids, l3iface_node, vlan_ids, errors):
    l3vni_vrf = {vx.id: vx.vrf for vx in (l2.vxlan if l2 else []) if isinstance(vx, L3VxLAN)}
    vxlan_index = {vx.id: k for k, vx in enumerate(l2.vxlan if l2 else [])}
    vrf_l3vni = {v.id: v.l3vni for v in l3.vrfs}

    # VRF
    for i, vrf in enumerate(l3.vrfs):
        if vrf.l3vni is not None and vrf.l3vni not in l3vni_ids:
            errors.append(ValidationError(
                f"layer3.vrfs[{i}].l3vni",
                f"未定義の L3VNI '{vrf.l3vni}' を参照しています（type=l3vni の vxlan が必要）",
            ))
        elif vrf.l3vni is not None and l3vni_vrf.get(vrf.l3vni) != vrf.id:
            errors.append(ValidationError(
                f"layer3.vrfs[{i}].l3vni",
                f"VRF '{vrf.id}' は L3VNI '{vrf.l3vni}' を指していますが、その L3VNI は"
                f" VRF '{l3vni_vrf.get(vrf.l3vni)}' を指しています (ADR-0011 D9)",
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

    # L3VNI → VRF の逆方向。VRF 側が別の L3VNI を指していれば矛盾
    for vx_id, vrf_id in l3vni_vrf.items():
        other = vrf_l3vni.get(vrf_id)
        if other is not None and other != vx_id and other in l3vni_ids:
            errors.append(ValidationError(
                f"layer2.vxlan[{vxlan_index[vx_id]}].vrf",
                f"L3VNI '{vx_id}' は VRF '{vrf_id}' を指していますが、その VRF は"
                f" L3VNI '{other}' を指しています (ADR-0011 D9)",
            ))

    # L3 Interfaces (ADR-0011 D3・D4・D9)
    seen_if: dict[tuple[str, str], str] = {}
    for i, iface in enumerate(l3.interfaces):
        path = f"layer3.interfaces[{i}]"
        if iface.node not in node_ids:
            errors.append(ValidationError(
                f"{path}.node", f"未定義のノード '{iface.node}' を参照しています",
            ))
        if iface.vrf is not None and iface.vrf not in vrf_ids:
            errors.append(ValidationError(
                f"{path}.vrf", f"未定義の VRF '{iface.vrf}' を参照しています",
            ))

        key = (iface.node, iface.name)
        if key in seen_if:
            errors.append(ValidationError(
                f"{path}.name",
                f"ノード '{iface.node}' のインターフェース '{iface.name}' が"
                f" '{seen_if[key]}' と重複して定義されています (ADR-0011 D9)",
            ))
        else:
            seen_if[key] = iface.id

        # 旧形式 (interface キー、短縮形 interface: vlan-N) を読み替えた箇所 (ADR-0011 D10)
        for fld, message in iface.deprecations:
            errors.append(ValidationError(f"{path}.{fld}", message, "warning"))

        # 参照解決と、参照先の node (群) に L3 IF の node が含まれるか (ADR-0001 D8 / ADR-0011 D9)
        at = iface.attaches_to
        if at is not None:
            kind = _resolve_ref(at.kind, at.target, spaces, f"{path}.attaches_to.{at.kind}", errors,
                                legacy_kinds=("lag", "vlan", "subinterface"))
            if kind == "interface":
                owners = {iface_node[at.target]}
            elif kind == "lag":
                owners = lag_nodes[at.target]
            elif kind == "subinterface":
                owners = subif_nodes.get(at.target)     # 基盤が未定義なら None
            else:
                owners = None                           # VLAN は node を持たない
            if owners and iface.node in node_ids and iface.node not in owners:
                errors.append(ValidationError(
                    f"{path}.attaches_to.{at.kind}",
                    f"{_KIND_LABEL[kind]} '{at.target}' はノード {'/'.join(sorted(owners))} のものであり、"
                    f"'{iface.node}' のものではありません (ADR-0011 D9)",
                ))

        # gateway_redundancy
        seen_group: dict[tuple[str, int, int], int] = {}
        for j, gw in enumerate(iface.gateway_redundancy):
            gpath = f"{path}.gateway_redundancy[{j}]"
            if gw.mode == "anycast_gateway":
                continue
            af = gw.vip.version
            gkey = (gw.mode, af, gw.group_id)
            if gkey in seen_group:
                errors.append(ValidationError(
                    f"{gpath}.group_id",
                    f"{gw.mode} の group_id {gw.group_id} (IPv{af}) が"
                    f" gateway_redundancy[{seen_group[gkey]}] と重複しています (ADR-0011 D9)",
                ))
            else:
                seen_group[gkey] = j
            if af == 4 and iface.ip is not None and gw.vip not in iface.ip.network:
                errors.append(ValidationError(
                    f"{gpath}.vip",
                    f"VIP {gw.vip} がインターフェースのサブネット {iface.ip.network} に含まれていません"
                    f" (ADR-0011 D9)",
                ))
            elif af == 4 and iface.ip is None:
                # VIP だけがあって IF 自身の IPv4 がない。サブネットが決まらず VRRP / HSRP は組めない (round4 E9)
                errors.append(ValidationError(
                    f"{gpath}.vip",
                    f"IPv4 の VIP {gw.vip} がありますが、インターフェースに ip がありません。"
                    f"ip を書いてください (ADR-0011 D9)",
                    "warning",
                ))

    _check_anycast_consistency(l3, vlan_ids, errors)

    # Tunnel Interfaces (ADR-0011 D6)
    l3iface = {iface.id: iface for iface in l3.interfaces}
    for i, tun in enumerate(l3.tunnel_interfaces):
        path = f"layer3.tunnel_interfaces[{i}]"
        if tun.node not in node_ids:
            errors.append(ValidationError(
                f"{path}.node", f"未定義のノード '{tun.node}' を参照しています",
            ))
        if tun.source not in l3interface_ids:
            errors.append(ValidationError(
                f"{path}.source", f"未定義の L3 インターフェース '{tun.source}' を参照しています",
            ))
        elif tun.node in node_ids and l3iface_node[tun.source] != tun.node:
            errors.append(ValidationError(
                f"{path}.source",
                f"source '{tun.source}' はノード '{l3iface_node[tun.source]}' に属しており、"
                f"トンネルのノード '{tun.node}' のものではありません",
            ))
        if tun.destination_interface is not None and tun.destination_interface not in l3interface_ids:
            errors.append(ValidationError(
                f"{path}.destination_interface",
                f"未定義の L3 インターフェース '{tun.destination_interface}' を参照しています",
            ))
        elif tun.destination_interface is not None and l3iface_node[tun.destination_interface] == tun.node:
            errors.append(ValidationError(
                f"{path}.destination_interface",
                f"destination_interface '{tun.destination_interface}' はトンネルと同じノード"
                f" '{tun.node}' のものです。対向ノードの L3 インターフェースを指してください (ADR-0011 D6)",
            ))

        # 外側のパケットは source と destination が同じ AF でないと組めない
        src_afs = _l3_afs(l3iface.get(tun.source))
        if tun.destination_ip is not None:
            dst_afs = {tun.destination_ip.version}
        else:
            dst_afs = _l3_afs(l3iface.get(tun.destination_interface))
        if src_afs and dst_afs and not (src_afs & dst_afs):
            errors.append(ValidationError(
                f"{path}.source",
                f"source '{tun.source}' のアドレスは {_af_names(src_afs)}、destination は"
                f" {_af_names(dst_afs)} で、外側のアドレスファミリーが一致しません (ADR-0011 D6)",
            ))
        for fld in ("vrf", "transport_vrf"):
            v = getattr(tun, fld)
            if v is not None and v not in vrf_ids:
                errors.append(ValidationError(
                    f"{path}.{fld}", f"未定義の VRF '{v}' を参照しています",
                ))

    # 対向がトポロジー内なのに、逆向きのトンネルが書かれていない (round4 E8)
    back = {(t.source, t.destination_interface) for t in l3.tunnel_interfaces}
    for i, tun in enumerate(l3.tunnel_interfaces):
        if (tun.destination_interface in l3iface_node
                and l3iface_node[tun.destination_interface] != tun.node
                and (tun.destination_interface, tun.source) not in back):
            errors.append(ValidationError(
                f"layer3.tunnel_interfaces[{i}]",
                f"対向 '{tun.destination_interface}' のノード '{l3iface_node[tun.destination_interface]}' に、"
                f"逆向きのトンネル (source: {tun.destination_interface}, destination_interface: {tun.source}) が"
                f"ありません (ADR-0011 D6)",
                "info",
            ))

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
            _check_attaches_to(adj.attaches_to, f"layer3.routing_adjacencies[{i}].attaches_to", spaces, errors)


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

def _ja(label: str) -> str:
    """日本語の地の文に埋め込むとき、英字で始まる語の前後に空白を入れる"""
    return f" {label} " if label[:1].isascii() else label


_KIND_LABEL = {
    "node": "ノード", "interface": "L1 インターフェース", "lag": "LAG", "vlan": "VLAN",
    "subinterface": "サブインターフェース", "link": "リンク",
}


def _resolve_ref(kind, target, spaces, path, errors, *, legacy_kinds=()) -> str | None:
    """キー kind で書かれた参照 target を、そのキーの ID 空間で解決する (ADR-0001 D8)

    解決できた種類を返す。未定義なら error を出して None を返す。
    legacy_kinds: {interface: X} で X が L1 IF 以外を指す旧形式 (ndl_version 1.x の間だけ受け付ける)。
    X がこれらの空間にあれば warning を出してその種類として扱う
    """
    if target in spaces[kind]:
        return kind
    if kind == "interface":
        for k in legacy_kinds:
            if target in spaces[k]:
                errors.append(ValidationError(
                    path,
                    f"{{interface: {target}}} は{_ja(_KIND_LABEL[k])}を指しています。{{{k}: {target}}} と"
                    f"書いてください。{{interface:}} は L1 インターフェース専用です (ADR-0001 D8)",
                    "warning",
                ))
                return k
    actual = next((k for k, ids in spaces.items() if target in ids), None)
    hint = f"。'{target}' は{_ja(_KIND_LABEL[actual])}です。{{{actual}: {target}}} の誤りではありませんか" if actual else ""
    errors.append(ValidationError(path, f"未定義の{_ja(_KIND_LABEL[kind]).rstrip()} '{target}' を参照しています{hint}"))
    return None


def _check_attaches_to(attaches_to, path, spaces, errors):
    """L1 と routing_adjacencies の attaches_to を検証する (書けるキーはスキーマで制限済み)"""
    if isinstance(attaches_to, str):
        if attaches_to not in spaces["node"]:
            errors.append(ValidationError(
                path, f"未定義のノード '{attaches_to}' を参照しています",
            ))
    elif isinstance(attaches_to, AttachesToObj):
        _resolve_ref(attaches_to.kind, attaches_to.target, spaces, f"{path}.{attaches_to.kind}", errors)


def _check_interface_id_spaces(spaces: dict[str, set[str]], errors: list[ValidationError]) -> None:
    """参照先になる ID 空間どうしが重複していないか (ADR-0002 D5)

    キーで種類を示すようになっても (ADR-0001 D8)、旧形式の {interface: X} を読み替えるには
    X がどの空間にあるかが一意に決まる必要がある。ID のグローバル一意性の一部でもある
    """
    names = list(spaces)
    for a_i, a in enumerate(names):
        for b in names[a_i + 1:]:
            for dup in sorted(spaces[a] & spaces[b]):
                errors.append(ValidationError(
                    f"id '{dup}'",
                    f"ID '{dup}' が {a} と {b} の両方で使われています。"
                    f"ID はグローバルに一意である必要があります (ADR-0002 D5)",
                ))


def _id_grammar_problems(entity_id: str) -> list[str]:
    """ADR-0002 D1 に違反している理由を返す。違反がなければ空リスト"""
    if _ID_PATTERN.match(entity_id):
        return [] if len(entity_id) <= _ID_MAX_LEN else [
            f"{_ID_MAX_LEN} 文字を超えています ({len(entity_id)} 文字)"
        ]
    problems = []
    if not entity_id[:1].islower() or not entity_id[:1].isascii():
        problems.append("先頭は英小文字にしてください")
    if any(c.isupper() for c in entity_id):
        problems.append("大文字は使えません")
    if "_" in entity_id:
        problems.append("アンダースコアは使えません。ハイフンで区切ってください")
    if entity_id.endswith("-") or "--" in entity_id:
        problems.append("末尾のハイフンと連続したハイフンは使えません")
    others = sorted({c for c in entity_id if not (c.isascii() and (c.isalnum() or c in "-_"))})
    if others:
        problems.append("使えない文字を含みます: " + " ".join(repr(c) for c in others))
    if len(entity_id) > _ID_MAX_LEN:
        problems.append(f"{_ID_MAX_LEN} 文字を超えています ({len(entity_id)} 文字)")
    return problems


def _check_id_grammar(topology: MLNDLTopology, errors: list[ValidationError]) -> None:
    """すべてのエンティティの id が ADR-0002 D1 の文法に従っているか (error)

    ID は参照のキーであり、DNS ラベルとして下流ツールにそのまま渡りうる。
    アダプターに暗黙の正規化を許さない (ADR-0002 D6 の 5) のと対になる検査。
    """
    for section_name in _ID_SECTIONS:
        section = getattr(topology, section_name)
        if section is None:
            continue
        for list_name in type(section).model_fields:
            entities = getattr(section, list_name)
            if not isinstance(entities, list):
                continue
            for i, entity in enumerate(entities):
                entity_id = getattr(entity, "id", None)
                if not isinstance(entity_id, str):
                    continue
                problems = _id_grammar_problems(entity_id)
                if problems:
                    errors.append(ValidationError(
                        f"{section_name}.{list_name}[{i}].id",
                        f"ID '{entity_id}' は ID の文法 ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ に"
                        f"従っていません: {' / '.join(problems)} (ADR-0002 D1)",
                    ))


def _l3_afs(iface) -> set[int]:
    """L3 IF が持つアドレスファミリー (4 / 6) の集合"""
    if iface is None:
        return set()
    return {af for af, addr in ((4, iface.ip), (6, iface.ipv6)) if addr is not None}


def _af_names(afs: set[int]) -> str:
    return " / ".join(f"IPv{af}" for af in sorted(afs))


def _normalize_mac(mac: str) -> str:
    return "".join(c for c in mac.lower() if c in "0123456789abcdef")


def _check_anycast_consistency(l3, vlan_ids, errors: list[ValidationError]) -> None:
    """同じ VLAN に載る anycast gateway の SVI 群で、IP と MAC が揃っているか (ADR-0011 D4)

    anycast gateway は全ノードが同じアドレスと MAC で応答する。1 台でも違えば、
    そのノードに着いたホストのゲートウェイが変わってしまう。未指定の値は比べない。
    """
    groups: dict[str, list[tuple[int, object]]] = {}
    for i, iface in enumerate(l3.interfaces):
        ref = iface.attachment_ref()
        if ref in vlan_ids and any(gw.mode == "anycast_gateway" for gw in iface.gateway_redundancy):
            groups.setdefault(ref, []).append((i, iface))
    for vlan, members in groups.items():
        if len(members) < 2:
            continue
        first_i, first = members[0]
        first_mac = next((gw.anycast_mac for gw in first.gateway_redundancy
                          if gw.mode == "anycast_gateway" and gw.anycast_mac), None)
        for i, iface in members[1:]:
            path = f"layer3.interfaces[{i}]"
            for fld in ("ip", "ipv6"):
                a, b = getattr(first, fld), getattr(iface, fld)
                if a is not None and b is not None and a != b:
                    errors.append(ValidationError(
                        f"{path}.{fld}",
                        f"VLAN '{vlan}' の anycast gateway で {fld} が {b} ですが、"
                        f"layer3.interfaces[{first_i}] ('{first.id}') は {a} です。"
                        f"anycast gateway は全ノードで同じアドレスにします (ADR-0011 D4)",
                    ))
            for j, gw in enumerate(iface.gateway_redundancy):
                if (gw.mode == "anycast_gateway" and gw.anycast_mac and first_mac
                        and _normalize_mac(gw.anycast_mac) != _normalize_mac(first_mac)):
                    errors.append(ValidationError(
                        f"{path}.gateway_redundancy[{j}].anycast_mac",
                        f"VLAN '{vlan}' の anycast gateway で anycast_mac が {gw.anycast_mac} ですが、"
                        f"'{first.id}' は {first_mac} です (ADR-0011 D4)",
                    ))


# ---------------------------------------------------------------------------
# 規約 (severity = warning)
# ---------------------------------------------------------------------------

def _warn_prefix(errors, path: str, entity_id: str, prefix: str, what: str) -> None:
    if not entity_id.startswith(prefix):
        errors.append(ValidationError(
            path,
            f"{what} の ID '{entity_id}' は推奨プレフィックス '{prefix}' で始まっていません (ADR-0002 D7)",
            "warning",
        ))


def _check_conventions(topology: MLNDLTopology, errors: list[ValidationError]) -> None:
    if topology.layer1:
        for i, link in enumerate(topology.layer1.links):
            _warn_prefix(errors, f"layer1.links[{i}].id", link.id, "link-", "L1 リンク")
        for i, lag in enumerate(topology.layer1.lag):
            _warn_prefix(errors, f"layer1.lag[{i}].id", lag.id, "lag-", "LAG")
        for i, node in enumerate(topology.layer1.nodes):
            for key in (node.labels or {}):
                if not _ID_PATTERN.match(key):
                    errors.append(ValidationError(
                        f"layer1.nodes[{i}].labels.{key}",
                        f"labels のキー '{key}' は ID 正規表現 ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ に"
                        f"従っていません。表記揺れの原因になります (ADR-0009 D3)",
                        "warning",
                    ))

    if topology.layer2:
        for i, vlan in enumerate(topology.layer2.vlans):
            _warn_prefix(errors, f"layer2.vlans[{i}].id", vlan.id, "vlan-", "VLAN")
        for i, vx in enumerate(topology.layer2.vxlan):
            _warn_prefix(errors, f"layer2.vxlan[{i}].id", vx.id, "vni-", "VNI")
        for i, si in enumerate(topology.layer2.subinterfaces):
            _warn_prefix(errors, f"layer2.subinterfaces[{i}].id", si.id, "subif-", "サブインターフェース")

    if topology.layer3:
        for i, vrf in enumerate(topology.layer3.vrfs):
            _warn_prefix(errors, f"layer3.vrfs[{i}].id", vrf.id, "vrf-", "VRF")
        for i, tun in enumerate(topology.layer3.tunnel_interfaces):
            _warn_prefix(errors, f"layer3.tunnel_interfaces[{i}].id", tun.id, "tunnel-", "トンネル")
        for i, iface in enumerate(topology.layer3.interfaces):
            # SVI のつもりで VLAN に紐づけ忘れた書き方を拾う (ADR-0011 D3)
            if iface.attaches_to is None and "vlan" in iface.name.lower():
                errors.append(ValidationError(
                    f"layer3.interfaces[{i}].attaches_to",
                    f"name '{iface.name}' は SVI に見えますが VLAN に紐づいていません。"
                    f"attaches_to: {{vlan: <VLAN id>}} を指定してください (ADR-0011 D3)",
                    "warning",
                ))
        for i, adj in enumerate(topology.layer3.routing_adjacencies):
            _warn_prefix(errors, f"layer3.routing_adjacencies[{i}].id", adj.id,
                         _ADJ_PREFIX[adj.type], f"{adj.type.upper()} 隣接")

    if topology.protocols:
        for i, bfd in enumerate(topology.protocols.bfd):
            _warn_prefix(errors, f"protocols.bfd[{i}].id", bfd.id, "bfd-", "BFD")
