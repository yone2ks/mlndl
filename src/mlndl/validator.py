"""クロスフィールドの整合性バリデーター

検査は 3 種類に分かれる (ADR-0015)。

  1. 参照の存在 — スキーマの Ref 宣言から _check_refs が検査する。どのフィールドがどこを指すかは
     スキーマ (src/mlndl/schema/*.py の Annotated[..., Ref("<パス>")]) を見る。ここには一覧を書かない
  2. キーで参照先を選ぶ参照 — attaches_to と VLAN のポート (ADR-0001 D8 / ADR-0013 D1)。
     _resolve_ref がキーごとに参照先を引く。旧形式 {interface: <LAG 等>} の読み替えもここ
  3. 意味の検査 — ネットワークとしての整合性。手書き。主なもの:
     - ID: 文法 (ADR-0002 D1)、L1 IF / LAG / VLAN / サブ IF の ID 重複、L3 IF とトンネルの ID 重複 (ADR-0002 D5)
     - L1: MLAG の client_lag が LACP を指し、メンバー数が合うか
     - L2: VLAN のポートのノード (旧形式の node との照合、MLAG に node)、LAG とメンバーの併記、
       同じ端点の重複、同一ノード上の vlan_id 重複 (MLAG は両ノードで数える)、サブ IF のタグ重複、
       VNI 番号の重複、VNI に参加するノードの VLAN、VTEP の検査 (ADR-0014 D5)、
       VLAN の端点の IP が SVI のサブネット外 (info。ADR-0013 D7)、
       bridge のポート (同じポートを 2 つの bridge に、LAG とメンバー、ポートが 1 つ、ルーターのポートらしいもの、
       VLAN と bridge の両方にあるポート。ADR-0018 D1)
     - L3: VRF ↔ L3VNI の双方向一致、RD / RT の形式、L3 IF の (node, name) 重複と参照先のノード所属、
       gateway_redundancy (VIP のサブネット・group_id 重複)、anycast gateway の一致、
       トンネル (source のノード、自己トンネル、外側の AF、片側だけのトンネル)
     - control_plane (ADR-0010 D10): インスタンスの省略、端の機器とインスタンス・update_source の機器と VRF、
       両端から導いた通り道の食い違い (BGP は error、OSPF / IS-IS は ndl_version 1.x の間 warning。ADR-0018 D4)、
       トランスポートのアドレスファミリー、セッションの重複、RR は iBGP、
       同一ノード・同一 VRF の AS、同一 VRF の BGP エントリ、default 以外の VRF の EVPN / VPN (warning)、BFD のタイマー
     - 規約 (warning): 推奨プレフィックス (ADR-0002 D7)、SVI らしい名前で attaches_to なし、labels のキー、
       link_speed の正規形 (ADR-0021 D3)
     - 旧形式 (warning): ADR-0011 D10・ADR-0013 D2・ADR-0014 D4

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

from pydantic import BaseModel

from .derive import (bgp_session_views, end_path_labels, igp_adjacency_views, l3_and_tunnels, outside_svi_subnet,
                     vlan_endpoints, vlan_svi_networks)
from .schema.control_plane import BgpInsideEndpoint, BgpSession, OspfAdjacency
from .schema.layer3 import TunnelInterface
from .schema.layer1 import AttachesToObj, LacpLag, MlagLag, canonical_link_speed
from .schema.layer2 import L2VxLAN, L3VxLAN
from .schema.topology import MLNDLTopology
from .schema.refs import COLLECTION_LABELS, Ref
from .index import SECTIONS, IdIndex

_RT_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+:\d+$|^\d+:\d+$")

# ADR-0002 D1
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_ID_MAX_LEN = 63    # DNS ラベルの上限を継承 (ADR-0002 D1)

# ID を持つエンティティのリストを探すセクション。リストの列挙はスキーマから行うので、
# エンティティを追加しても文法チェックの対象から漏れない
_ID_SECTIONS = ("layer1", "layer2", "layer3", "control_plane")

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

    # VTEP id → 終端するノード群 (sources の L3 IF から導出。ADR-0014)
    vtep_nodes: dict[str, set[str]] = {}
    if topology.layer2:
        vtep_nodes = {
            v.id: {l3iface_node[s] for s in v.sources if s in l3iface_node}
            for v in topology.layer2.vteps
        }

    # ── ID の文法 (ADR-0002 D1) ──────────────────────────────────────────
    _check_id_grammar(topology, errors)

    # ── 参照の存在 (ADR-0015): スキーマの Ref を読んで、全参照を検査する ────
    _check_refs(topology, topology.index(), errors)

    # attaches_to / VLAN のポートのキーが指す ID 空間 (ADR-0001 D8)
    spaces = {
        "node": node_ids, "interface": interface_ids, "lag": lag_ids,
        "vlan": vlan_ids, "subinterface": subif_ids,
    }

    # ── ID の一意性 (ADR-0002 D5) ───────────────────────────────────────
    _check_id_uniqueness(topology, errors)

    # ── Layer 1 ──────────────────────────────────────────────────────────
    if topology.layer1:
        _validate_l1(topology.layer1, node_ids, interface_ids, lag_ids, spaces, errors)

    # ── Layer 2 ──────────────────────────────────────────────────────────
    if topology.layer2:
        _validate_l2(
            topology.layer2,
            node_ids, iface_node, lag_nodes, member_lag, spaces,
            vlan_ids, l3vni_ids, vrf_ids, l3interface_ids, l3iface_node, vtep_nodes,
            errors,
        )

    # ── bridge (ADR-0018 D1) ─────────────────────────────────────────────
    if topology.layer2 and topology.layer2.bridges:
        _validate_bridges(topology, spaces, member_lag, errors)

    # ── Layer 3 ──────────────────────────────────────────────────────────
    if topology.layer3:
        _validate_l3(
            topology.layer3, topology.layer2,
            node_ids, iface_node, lag_nodes, subif_nodes, spaces,
            l3vni_ids, vrf_ids, l3interface_ids, l3iface_node, vlan_ids,
            errors,
        )

    # ── VTEP (ADR-0014) ──────────────────────────────────────────────────
    if topology.layer2 and topology.layer2.vteps:
        _validate_vteps(topology, vtep_nodes, errors)

    # ── VLAN の端点 (ADR-0013 D7) ─────────────────────────────────────────
    _check_vlan_endpoints(topology, errors)

    # ── 制御プレーン (ADR-0010) ──────────────────────────────────────────
    if topology.control_plane:
        _validate_control_plane(topology, errors)

    # ── 規約 (warning) ───────────────────────────────────────────────────
    _check_conventions(topology, errors)

    return errors


# ---------------------------------------------------------------------------
# Layer 1
# ---------------------------------------------------------------------------

def _validate_l1(l1, node_ids, interface_ids, lag_ids, spaces, errors):
    # 参照の存在 (node / endpoints / members / peer_link / client_lag) は _check_refs が検査する (ADR-0015)
    for i, lag in enumerate(l1.lag):
        # client_lag: 同一 lag リスト内の LacpLag を参照していること
        if not isinstance(lag, MlagLag) or lag.client_lag not in lag_ids:
            continue
        client = next(x for x in l1.lag if x.id == lag.client_lag)
        if not isinstance(client, LacpLag):
            errors.append(ValidationError(
                f"layer1.lag[{i}].client_lag",
                f"client_lag は LacpLag (type: lacp) を参照する必要があります",
            ))
        elif len(client.members) != len(lag.nodes):            # members 数の対称性
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
        return owners                           # 未定義のノードは _check_refs が検査する
    if kind == "lag" and len(owners) > 1:
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
                 vlan_ids, l3vni_ids, vrf_ids, l3interface_ids, l3iface_node, vtep_nodes, errors):
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
            if vx.vteps:
                participants = _check_vni_vteps(vx, i, vtep_nodes, errors)
            else:
                participants = _check_legacy_vtep_source(vx, i, node_ids, l3interface_ids, l3iface_node, errors)
            # VNI に参加するノードなのに、その VLAN のポートが 1 つもない (round4 E10)。
            # VLAN にポートが書かれていない場合は判断できないので見ない
            carried = vlan_nodes.get(vx.vlan)
            if carried:
                for m in sorted(participants):
                    if m in node_ids and m not in carried:
                        errors.append(ValidationError(
                            f"layer2.vxlan[{i}]",
                            f"VNI に参加するノード '{m}' には VLAN '{vx.vlan}' のポートがありません。"
                            f"VLAN を載せ忘れていないか確認してください (ADR-0011 D9)",
                            "warning",
                        ))


def _validate_bridges(topology: MLNDLTopology, spaces, member_lag, errors) -> None:
    """bridge のポート (ADR-0018 D1)。ポートの形は VLAN のポートと同じ (ADR-0013)"""
    l2 = topology.layer2
    peer: dict[str, str] = {}
    if topology.layer1:
        for link in topology.layer1.links:
            x, y = link.endpoints
            peer[x], peer[y] = y, x
    lag_members = {g.id: set(g.members) for g in topology.layer1.lag} if topology.layer1 else {}
    vlan_ports = {pr.target for v in l2.vlans for pr in [*v.trunk_ports, *v.access_ports]}
    owner: dict[str, str] = {}          # ポートの参照先 → それを書いた最初の bridge
    for i, br in enumerate(l2.bridges):
        if len(br.ports) == 1:
            errors.append(ValidationError(
                f"layer2.bridges[{i}].ports",
                f"bridge '{br.id}' のポートが 1 つしかありません。L2 セグメントは 2 つ以上のポートのあいだでフレームを転送します。"
                f"相手の拠点がトポロジー外なら、このままでかまいません (ADR-0018 D1)",
                "warning",
            ))
        listed = {p.target for p in br.ports}
        legs_of: dict[str, set[str]] = {}
        for j, port in enumerate(br.ports):
            key = pr_key(port)
            path = f"layer2.bridges[{i}].ports[{j}].{key}"
            kind = _resolve_ref(key, port.target, spaces, path, errors)
            if port.target in legs_of:
                errors.append(ValidationError(path, f"'{port.target}' はこの bridge にすでに書かれています (ADR-0018 D1)"))
                continue
            legs_of[port.target] = lag_members.get(port.target, set()) if kind == "lag" else {port.target}
            if port.target in owner and owner[port.target] != br.id:
                errors.append(ValidationError(
                    path,
                    f"'{port.target}' は bridge '{owner[port.target]}' のポートでもあります。1 つのポートは 1 つの L2 セグメントに"
                    f"しか属しません (ADR-0018 D1)",
                ))
            owner.setdefault(port.target, br.id)
            if port.target in vlan_ports:
                errors.append(ValidationError(
                    path,
                    f"'{port.target}' は VLAN のポートにも書かれています。事業者網の箱のポートは bridge にだけ書きます"
                    f" (ADR-0018 D1)",
                    "warning",
                ))
            lag = member_lag.get(port.target) if kind == "interface" else None
            if lag is not None:
                errors.append(ValidationError(
                    path,
                    f"'{port.target}' は LAG '{lag}' のメンバーです。LAG とそのメンバーを同じ bridge に書くことはできません。"
                    f"LAG だけを書いてください (ADR-0018 D1)" if lag in listed else
                    f"'{port.target}' は LAG '{lag}' のメンバーです。bridge には LAG を書いてください (lag: {lag}) (ADR-0018 D1)",
                    "error" if lag in listed else "warning",
                ))
        # ポートの対向が同じ bridge のポートなら、拠点のルーター (bridge を使う側) のポートを書いた疑い
        all_legs = set().union(*legs_of.values()) if legs_of else set()
        for j, port in enumerate(br.ports):
            if any(peer.get(leg) in all_legs for leg in legs_of.get(port.target, ())):
                errors.append(ValidationError(
                    f"layer2.bridges[{i}].ports[{j}].{pr_key(port)}",
                    f"'{port.target}' の L1 リンクの対向も、この bridge のポートです。ports には転送する側 (事業者網の箱) の"
                    f"ポートだけを書き、拠点のルーターのポートは書きません (ADR-0018 D1)",
                    "warning",
                ))


def _check_vni_vteps(vx, i, vtep_nodes, errors) -> set[str]:
    """VNI の vteps を解決し、参加するノード群を返す (ADR-0014 D3)"""
    participants: set[str] = set()
    seen: set[str] = set()
    for j, vt in enumerate(vx.vteps):
        path = f"layer2.vxlan[{i}].vteps[{j}]"
        if vt in seen:
            errors.append(ValidationError(path, f"VTEP '{vt}' が重複しています (ADR-0014 D3)"))
            continue
        seen.add(vt)
        participants |= vtep_nodes.get(vt, set())     # 未定義の VTEP は _check_refs が検査する
    return participants


def _check_legacy_vtep_source(vx, i, node_ids, l3interface_ids, l3iface_node, errors) -> set[str]:
    """旧形式 vtep_source / members (ndl_version 1.x の間だけ受け付ける。ADR-0014 D4)"""
    errors.append(ValidationError(
        f"layer2.vxlan[{i}].vtep_source",
        "vtep_source と members は廃止予定です。layer2.vteps に VTEP を定義し、"
        "vteps: [<VTEP の id>] で参照してください (ADR-0014 D4)",
        "warning",
    ))
    vtep_node = l3iface_node.get(vx.vtep_source)
    if vtep_node is not None and vx.members and vtep_node not in vx.members:
        errors.append(ValidationError(
            f"layer2.vxlan[{i}].vtep_source",
            f"vtep_source '{vx.vtep_source}' のノード '{vtep_node}' が members に含まれていません"
            f" (ADR-0011 D9)",
        ))
    return set(vx.members or []) | ({vtep_node} if vtep_node else set())


def _validate_vteps(topology: MLNDLTopology, vtep_nodes: dict[str, set[str]], errors) -> None:
    """layer2.vteps の検証 (ADR-0014 D5)"""
    l3ifs = {i.id: i for i in topology.layer3.interfaces} if topology.layer3 else {}
    used_by: dict[str, str] = {}             # L3 IF id → それを使う VTEP の id
    by_address: dict[object, str] = {}      # VTEP のアドレス → VTEP の id
    for i, vtep in enumerate(topology.layer2.vteps):
        path = f"layer2.vteps[{i}]"
        node_of: dict[str, str] = {}
        for j, src in enumerate(vtep.sources):
            spath = f"{path}.sources[{j}]"
            iface = l3ifs.get(src)
            if iface is None:
                continue                                # 未定義は _check_refs が検査する
            if src in used_by:
                same = used_by[src] == vtep.id
                errors.append(ValidationError(
                    spath,
                    f"'{src}' はこの VTEP に 2 回書かれています (ADR-0014 D5)" if same else
                    f"'{src}' は VTEP '{used_by[src]}' でも使われています。1 つの L3 IF が終端する VTEP は"
                    f" 1 つです (ADR-0014 D5)",
                ))
                continue
            used_by[src] = vtep.id
            if iface.node in node_of:
                errors.append(ValidationError(
                    spath,
                    f"ノード '{iface.node}' の L3 IF が、この VTEP に '{node_of[iface.node]}' と '{src}' の 2 つ"
                    f"書かれています。1 ノードからは 1 つだけ書きます (ADR-0014 D5)",
                ))
            node_of.setdefault(iface.node, src)

        # アドレス: sources が 1 つなら省略でき、その L3 IF の ip / ipv6 になる (ADR-0014 D2)
        effective = []
        if len(vtep.sources) == 1 and vtep.sources[0] in l3ifs:
            src = l3ifs[vtep.sources[0]]
            for fld, given, own in (("address", vtep.address, src.ip),
                                    ("address_v6", vtep.address_v6, src.ipv6)):
                if given is not None and own is not None and given.ip != own.ip:
                    errors.append(ValidationError(
                        f"{path}.{fld}",
                        f"{fld} {given} が source '{src.id}' のアドレス {own} と異なります。"
                        f"1 ノードの VTEP は source のアドレスを使うので、{fld} は省略できます (ADR-0014 D2)",
                        "warning",
                    ))
                addr = given if given is not None else own
                if addr is not None:
                    effective.append(addr.ip)
            if not effective:
                errors.append(ValidationError(
                    f"{path}.sources[0]",
                    f"VTEP のアドレスが決まりません。source '{src.id}' に ip / ipv6 を書くか、"
                    f"address を書いてください (ADR-0014 D2)",
                ))
        else:
            effective = [a.ip for a in (vtep.address, vtep.address_v6) if a is not None]
        for addr in effective:
            if addr in by_address:
                errors.append(ValidationError(
                    path,
                    f"VTEP のアドレス {addr} が VTEP '{by_address[addr]}' と重複しています。"
                    f"複数のノードで共有するなら、1 つの VTEP の sources に並べてください (ADR-0014 D5)",
                ))
            else:
                by_address[addr] = vtep.id

    # MLAG ペアの片方だけが VTEP を終端している (相方の書き忘れの可能性)
    if topology.layer1:
        for lag in topology.layer1.lag:
            if not isinstance(lag, MlagLag):
                continue
            pair = set(lag.nodes)
            for i, vtep in enumerate(topology.layer2.vteps):
                inside = vtep_nodes.get(vtep.id, set()) & pair
                if len(inside) == 1:
                    (one,) = inside
                    (other,) = pair - inside
                    errors.append(ValidationError(
                        f"layer2.vteps[{i}].sources",
                        f"MLAG '{lag.id}' のノード '{one}' はこの VTEP を終端していますが、相方 '{other}' は"
                        f"含まれていません。MLAG ペアは通常 VTEP を共有します (ADR-0014 D5)",
                        "warning",
                    ))


# ---------------------------------------------------------------------------
# Layer 3
# ---------------------------------------------------------------------------

def _check_vlan_endpoints(topology: MLNDLTopology, errors: list[ValidationError]) -> None:
    """VLAN の端点の IP が、その VLAN の SVI のサブネットに入っているか (info。ADR-0013 D7)

    L2 だけのセグメントや設計途中の構成があるので warning にはしない。
    """
    if not topology.layer3:
        return
    l3_index = {iface.id: i for i, iface in enumerate(topology.layer3.interfaces)}
    svi_nets = vlan_svi_networks(topology)
    seen: set[tuple[str, str]] = set()      # MLAG の両脚から同じ L3 IF に届いても 1 回だけ
    for ep in vlan_endpoints(topology):
        outside = outside_svi_subnet(ep, svi_nets)
        l3 = ep.l3_interfaces[0] if ep.l3_interfaces else None
        if not outside or l3 is None or (ep.vlan, l3.id) in seen:
            continue
        seen.add((ep.vlan, l3.id))
        nets = ", ".join(str(n) for n in svi_nets[ep.vlan])
        errors.append(ValidationError(
            f"layer3.interfaces[{l3_index[l3.id]}]",
            f"VLAN '{ep.vlan}' の端点 '{l3.id}' ({ep.node}) の {', '.join(outside)} が、この VLAN の SVI の"
            f"サブネット ({nets}) に入っていません (ADR-0013 D7)",
            "info",
        ))


def _validate_l3(l3, l2, node_ids, iface_node, lag_nodes, subif_nodes, spaces,
                 l3vni_ids, vrf_ids, l3interface_ids, l3iface_node, vlan_ids, errors):
    l3vni_vrf = {vx.id: vx.vrf for vx in (l2.vxlan if l2 else []) if isinstance(vx, L3VxLAN)}
    vxlan_index = {vx.id: k for k, vx in enumerate(l2.vxlan if l2 else [])}
    vrf_l3vni = {v.id: v.l3vni for v in l3.vrfs}

    # VRF
    for i, vrf in enumerate(l3.vrfs):
        if vrf.l3vni in l3vni_ids and l3vni_vrf.get(vrf.l3vni) != vrf.id:
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
        if tun.source in l3iface_node and tun.node in node_ids and l3iface_node[tun.source] != tun.node:
            errors.append(ValidationError(
                f"{path}.source",
                f"source '{tun.source}' はノード '{l3iface_node[tun.source]}' に属しており、"
                f"トンネルのノード '{tun.node}' のものではありません",
            ))
        if tun.destination_interface in l3iface_node and l3iface_node[tun.destination_interface] == tun.node:
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



# ---------------------------------------------------------------------------
# 制御プレーン (ADR-0010 D10)
# ---------------------------------------------------------------------------

# default 以外の VRF のセッションが運ぶのは珍しい AF (RFC 4364 / RFC 7432)
_DEFAULT_VRF_AFS = ("l2vpn_evpn", "vpnv4", "vpnv6")


def _validate_control_plane(topology: MLNDLTopology, errors: list[ValidationError]) -> None:
    cp = topology.control_plane
    l3ifs = l3_and_tunnels(topology)      # update_source / OSPF の interface はトンネル IF も指せる (ADR-0018 D3)
    l1if_node = {i.id: i.node for i in topology.layer1.interfaces} if topology.layer1 else {}
    instances = {"bgp": cp.bgp, "ospf": cp.ospf, "isis": cp.isis}
    members = {(t, inst.id): {n.node for n in inst.nodes} for t, lst in instances.items() for inst in lst}

    # インスタンス: 同一 VRF に BGP エントリは 1 つ、同一ノード・同一 VRF で AS は 1 つ (F4)
    by_vrf: dict[str | None, list[int]] = {}
    for i, inst in enumerate(cp.bgp):
        by_vrf.setdefault(inst.vrf, []).append(i)
        seen_as: dict[str, int] = {}
        for j, n in enumerate(inst.nodes):
            if n.node in seen_as and seen_as[n.node] != n.local_as:
                errors.append(ValidationError(
                    f"control_plane.bgp[{i}].nodes[{j}]",
                    f"ノード '{n.node}' が同じインスタンスに異なる local_as ({seen_as[n.node]} と {n.local_as}) で書かれています"
                    f"。1 台の BGP スピーカーは 1 つの VRF で 1 つの AS を持ちます (ADR-0010 D5)",
                ))
            seen_as.setdefault(n.node, n.local_as)
    for vrf, idx in by_vrf.items():
        for i in idx[1:]:
            errors.append(ValidationError(
                f"control_plane.bgp[{i}]",
                f"{vrf or 'default'} VRF の BGP インスタンスが 2 つ以上あります ('{cp.bgp[idx[0]].id}' と '{cp.bgp[i].id}')。"
                f"BGP のエントリは VRF ごとに 1 つです。underlay / overlay でエントリを分けず、セッションの address_families で書き分けます (ADR-0010 D5)",
            ))
    instance_vrfs = {inst.vrf for inst in cp.bgp if inst.vrf is not None}

    # セッション: インスタンスの省略と、端の機器がインスタンスに参加しているか
    for i, nb in enumerate(cp.routing_neighbors):
        path = f"control_plane.routing_neighbors[{i}]"
        entries = instances[nb.type]
        if nb.instance is None and len(entries) != 1:
            errors.append(ValidationError(
                f"{path}.instance",
                f"control_plane.{nb.type} のエントリが {len(entries)} つあるので、instance でどれに属するかを指定してください (ADR-0010 D3)",
            ))
            continue
        inst_id = nb.instance or entries[0].id
        for side, ep in (("from", nb.from_), ("to", nb.to)):
            node = getattr(ep, "node", None)
            if node is None:
                continue
            if (nb.type, inst_id) in members and node not in members[(nb.type, inst_id)]:
                errors.append(ValidationError(
                    f"{path}.{side}.node",
                    f"ノード '{node}' がインスタンス '{inst_id}' の nodes にありません (ADR-0010 D5)",
                ))
            # update_source / interface の機器が端の機器と一致するか
            if isinstance(nb, BgpSession):
                ref, owner = ep.update_source, getattr(l3ifs.get(ep.update_source), "node", None)
                field_name = "update_source"
            elif isinstance(nb, OspfAdjacency):
                ref, owner, field_name = ep.interface, getattr(l3ifs.get(ep.interface), "node", None), "interface"
            else:
                ref, owner, field_name = ep.interface, l1if_node.get(ep.interface), "interface"
            if owner is not None and owner != node:
                errors.append(ValidationError(
                    f"{path}.{side}.{field_name}",
                    f"'{ref}' はノード '{owner}' のインターフェースです。この端のノードは '{node}' です (ADR-0010 D3)",
                ))

    # 通り道の食い違い: OSPF / IS-IS は ndl_version 1.x の間 warning、2.0 で error (ADR-0018 D4)
    tunnels = {t.id for t in topology.layer3.tunnel_interfaces} if topology.layer3 else set()
    labels = end_path_labels(topology)
    for v in igp_adjacency_views(topology):
        if v.transport_mismatch:
            errors.append(ValidationError(
                f"control_plane.routing_neighbors[{v.index}]",
                _mismatch_message("interface", v.session.from_.interface, v.session.to.interface, tunnels, labels),
                "warning",
            ))

    # BGP セッション: 導いた値 (derive.bgp_session_views) を検査する
    bfd_nodes = {n for b in cp.bfd for n in b.nodes}
    seen_pairs: dict[tuple, int] = {}
    for v in bgp_session_views(topology):
        path = f"control_plane.routing_neighbors[{v.index}]"
        s = v.session
        # update_source の VRF とインスタンスの VRF
        for side, end in (("from", v.from_), ("to", v.to)):
            iface = end.l3_interface
            if iface is None or v.instance is None:
                continue
            if v.vrf is not None and iface.vrf != v.vrf or v.vrf is None and iface.vrf in instance_vrfs:
                kind = "トンネル" if isinstance(iface, TunnelInterface) else "L3 インターフェース"
                errors.append(ValidationError(
                    f"{path}.{side}.update_source",
                    f"'{iface.id}' は VRF '{iface.vrf or 'default'}' の{kind}ですが、"
                    f"インスタンス '{v.instance.id}' は {v.vrf or 'default'} VRF です (ADR-0010 D10)",
                ))
        if v.transport_mismatch:
            errors.append(ValidationError(
                path, _mismatch_message("update_source", v.from_.l3_interface.id, v.to.l3_interface.id, tunnels, labels),
            ))
        afs_a, afs_b = v.from_.transport_afs, v.to.transport_afs
        if afs_a and afs_b and not afs_a & afs_b:
            errors.append(ValidationError(
                path,
                f"セッションを張るアドレスのアドレスファミリーが一致しません ({_af_names(afs_a)} と {_af_names(afs_b)})"
                f"。トランスポートは同じアドレスファミリーで張ります (ADR-0010 D10)",
            ))
        key = (v.instance.id if v.instance else None,
               frozenset(str(e.l3_interface.id if e.l3_interface else e.address) for e in (v.from_, v.to)))
        if key in seen_pairs:
            errors.append(ValidationError(
                path,
                f"routing_neighbors[{seen_pairs[key]}] と同じ両端 (同じ update_source の組) のセッションです (ADR-0010 D10)",
            ))
        seen_pairs.setdefault(key, v.index)
        rr = any(isinstance(ep, BgpInsideEndpoint) and ep.route_reflector_client for ep in (s.from_, s.to))
        if rr and v.bgp_type == "ebgp":
            errors.append(ValidationError(
                path,
                f"route_reflector_client は iBGP のセッションにしか付けられません (両端の AS は {v.from_.local_as} と {v.to.local_as})。"
                f"ルートリフレクションは iBGP の仕組みです (RFC 4456。ADR-0010 D10)",
            ))
        if v.vrf is not None:
            odd = [af for af in s.address_families if af in _DEFAULT_VRF_AFS]
            if odd:
                errors.append(ValidationError(
                    f"{path}.address_families",
                    f"{v.vrf} のセッションが {', '.join(odd)} を運んでいます。これらの経路は default VRF のセッションで運ぶのが通常です (ADR-0010 D10)",
                    "warning",
                ))
        if s.bfd:
            missing = [e.node for e in (v.from_, v.to) if e.node is not None and e.node not in bfd_nodes]
            if missing:
                errors.append(ValidationError(
                    f"{path}.bfd",
                    f"bfd: true ですが、{', '.join(missing)} はどの control_plane.bfd の nodes にもありません (ADR-0010 D10)",
                ))


def _mismatch_message(field: str, a: str, b: str, tunnels: set[str], labels: dict[str, str]) -> str:
    """通り道の食い違いのメッセージ。両端の通り道を示し、書き手の意図ごとに次の手を示す (ADR-0018 D6)"""
    message = (f"両端の {field} から導いた通り道が食い違います (from の {a} の通り道: {labels.get(a, '?')}、"
               f"to の {b} の通り道: {labels.get(b, '?')})。")
    if (a in tunnels) != (b in tunnels):
        tun, other, side = (a, b, "to") if a in tunnels else (b, a, "from")
        message += (f"{side} 側の '{other}' はトンネル IF ではありません。相手の機器のトンネル IF"
                    f" (destination_interface が '{tun}' の source を指すもの) を書いてください。")
    return message + (
        "次のどれかで直してください: (a) 直結のリンクの上で張るなら、両端の L3 IF を同じ L1 リンクの両端に載せる。"
        "(b) 事業者網をはさむなら、両端のポートの対向 (箱のポート) を同じ layer2.bridges[].ports に書く。"
        f"(c) トンネルの上で張るなら、両端の {field} を対になるトンネル IF にする (ADR-0018 D6)"
    )


# ---------------------------------------------------------------------------
# attaches_to 参照チェック（共通）
# ---------------------------------------------------------------------------

def _ja(label: str) -> str:
    """日本語の地の文に埋め込むとき、英字で始まる語の前後に空白を入れる"""
    return f" {label} " if label[:1].isascii() else label


_KIND_LABEL = {
    "node": "ノード", "interface": "L1 インターフェース", "lag": "LAG", "vlan": "VLAN",
    "subinterface": "サブインターフェース",
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
    """L1 ノード・L1 IF の attaches_to を検証する (書けるキーはスキーマで制限済み)"""
    if isinstance(attaches_to, str):
        if attaches_to not in spaces["node"]:
            errors.append(ValidationError(
                path, f"未定義のノード '{attaches_to}' を参照しています",
            ))
    elif isinstance(attaches_to, AttachesToObj):
        _resolve_ref(attaches_to.kind, attaches_to.target, spaces, f"{path}.{attaches_to.kind}", errors)


def _check_id_uniqueness(topology: MLNDLTopology, errors: list[ValidationError]) -> None:
    """すべての id がトポロジー全体で一意か (ADR-0002 D5)

    同じ一覧の中の重複も、別の一覧との重複も error にする。重複を許すと、参照がどれを指すか決まらず、
    索引 (IdIndex) は先に書いたほうだけを引くので、後に書いたほうが黙って見えなくなる。
    旧形式の {interface: X} の読み替えや、L3 IF とトンネル IF のどちらも指せる update_source も、
    id から種類が一意に決まることに頼っている (ADR-0001 D8、ADR-0018 D3)
    """
    first: dict[str, tuple[str, int]] = {}   # id → 最初に書いた (一覧のパス, 位置)
    for section_name in SECTIONS:
        section = getattr(topology, section_name, None)
        if section is None:
            continue
        for list_name in type(section).model_fields:
            items = getattr(section, list_name)
            if not isinstance(items, list):
                continue
            path = f"{section_name}.{list_name}"
            for i, item in enumerate(items):
                entity_id = getattr(item, "id", None)
                if not isinstance(entity_id, str):
                    continue
                if entity_id not in first:
                    first[entity_id] = (path, i)
                    continue
                first_path, first_i = first[entity_id]
                where = (f"{_collection_label(path)} の中で 2 回使われています ({first_path}[{first_i}] と {path}[{i}])"
                         if first_path == path else
                         f"{_collection_label(first_path)} と {_collection_label(path)} の両方で使われています")
                errors.append(ValidationError(
                    f"{path}[{i}].id",
                    f"ID '{entity_id}' が {where}。ID はグローバルに一意である必要があります (ADR-0002 D5)",
                ))


def _collection_label(path: str) -> str:
    return COLLECTION_LABELS.get(path) or {"control_plane.bfd": "BFD"}.get(path, path)


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


def _check_refs(topology: MLNDLTopology, index: IdIndex, errors: list[ValidationError]) -> None:
    """Ref が付いたフィールドの値が、参照先のコレクションに実在するか (ADR-0015)

    スキーマを辿って Ref を探すので、構文を足しても Ref を書けば検査が付く。
    参照先の種類をキーで選ぶ参照 (attaches_to、VLAN のポート) は _resolve_ref が検査する
    """
    for section_name in _ID_SECTIONS:
        section = getattr(topology, section_name)
        if section is not None:
            _walk_refs(section, section_name, index, errors)


def _walk_refs(model: BaseModel, path: str, index: IdIndex, errors: list[ValidationError]) -> None:
    for name, info in type(model).model_fields.items():
        value = getattr(model, name)
        if value is None:
            continue
        field_path = f"{path}.{info.alias or name}"
        ref = next((m for m in info.metadata if isinstance(m, Ref)), None)
        if ref is not None:
            valid = index.ids(ref.paths, ref.where)
            targets = value if isinstance(value, list) else [value]
            for j, target in enumerate(targets):
                if target not in valid:
                    errors.append(ValidationError(
                        f"{field_path}[{j}]" if isinstance(value, list) else field_path,
                        _undefined_ref_message(ref, target, index),
                    ))
        elif isinstance(value, BaseModel):
            _walk_refs(value, field_path, index, errors)
        elif isinstance(value, list):
            for j, item in enumerate(value):
                if isinstance(item, BaseModel):
                    _walk_refs(item, f"{field_path}[{j}]", index, errors)


def _undefined_ref_message(ref: Ref, target: str, index: IdIndex) -> str:
    message = f"未定義の{_ja(ref.label).rstrip()} '{target}' を参照しています"
    if ref.where is not None and target in index.ids(ref.paths):
        field, value = ref.where
        return f"{message}。'{target}' は {field}: {value} ではありません"
    elsewhere = index.paths_of(target)
    if elsewhere:
        kinds = " / ".join(COLLECTION_LABELS.get(p, p) for p in elsewhere)
        return f"{message}。'{target}' は{_ja(kinds)}です"
    return message


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
            if link.link_speed and (canonical := canonical_link_speed(link.link_speed)) != link.link_speed:
                errors.append(ValidationError(
                    f"layer1.links[{i}].link_speed",
                    f"link_speed '{link.link_speed}' は '{canonical}' と書くとそろいます。"
                    f"数値が 1 以上 1000 未満になる単位で書きます (ADR-0021 D3)",
                    "warning",
                ))
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
        for i, vtep in enumerate(topology.layer2.vteps):
            _warn_prefix(errors, f"layer2.vteps[{i}].id", vtep.id, "vtep-", "VTEP")
        for i, si in enumerate(topology.layer2.subinterfaces):
            _warn_prefix(errors, f"layer2.subinterfaces[{i}].id", si.id, "subif-", "サブインターフェース")
        for i, br in enumerate(topology.layer2.bridges):
            _warn_prefix(errors, f"layer2.bridges[{i}].id", br.id, "bridge-", "bridge")

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

    if topology.control_plane:
        for i, nb in enumerate(topology.control_plane.routing_neighbors):
            _warn_prefix(errors, f"control_plane.routing_neighbors[{i}].id", nb.id,
                         _ADJ_PREFIX[nb.type], "BGP セッション" if nb.type == "bgp" else f"{nb.type.upper()} 隣接")
        for i, bfd in enumerate(topology.control_plane.bfd):
            _warn_prefix(errors, f"control_plane.bfd[{i}].id", bfd.id, "bfd-", "BFD")
