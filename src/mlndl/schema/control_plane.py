"""制御プレーンのスキーマ (ADR-0010)

設計決定:
- D2: トップレベル control_plane に、インスタンスごとの設定 (bgp / ospf / isis / bfd) とセッション (routing_neighbors) を置く
- D3: routing_neighbors の 1 エントリ = 1 セッション。type を discriminator とする Tagged Union。
  BGP の端点は、トポロジー内の機器 {node, update_source} かトポロジー外の相手 {address, local_as} のどちらか。
  セッションに attaches_to は書かない (通り道は update_source の L3 IF から導く。D7。derive.bgp_session_views)
- D4: unnumbered は、update_source が ip も ipv6 も持たない L3 IF を指す端
- D5: BGP のエントリは VRF ごとのインスタンス。AS はノードエントリに、AF はセッションに書く
- D8: OSPF / IS-IS はポイントツーポイント前提
"""

from __future__ import annotations

import re
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, field_validator, model_validator

from .refs import Ref

# セッションが運ぶ経路の種類 (NLRI の AFI/SAFI)。トランスポートのアドレスファミリーとは独立 (ADR-0010 Terms)
AddressFamily = Literal["ipv4_unicast", "ipv6_unicast", "l2vpn_evpn", "vpnv4", "vpnv6"]

_DOTTED_QUAD = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


# ---------------------------------------------------------------------------
# インスタンス (ADR-0010 D5・D8)
# ---------------------------------------------------------------------------

class BgpInstanceNode(BaseModel):
    """BGP インスタンスに参加するノードの設定"""

    model_config = ConfigDict(extra="forbid")

    node: Annotated[str, Ref("layer1.nodes")]
    local_as: int


class BgpInstance(BaseModel):
    """1 つの VRF の BGP インスタンス (全ノード分)。vrf を省略すると default VRF"""

    model_config = ConfigDict(extra="forbid")

    id: str
    vrf: Annotated[str | None, Ref("layer3.vrfs")] = None
    nodes: list[BgpInstanceNode] = []
    description: str | None = None


class OspfInstanceNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: Annotated[str, Ref("layer1.nodes")]


class OspfInstance(BaseModel):
    """1 つの OSPF ルーティングドメイン"""

    model_config = ConfigDict(extra="forbid")

    id: str
    vrf: Annotated[str | None, Ref("layer3.vrfs")] = None
    nodes: list[OspfInstanceNode] = []
    description: str | None = None


class IsisInstanceNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: Annotated[str, Ref("layer1.nodes")]
    net: str | None = None          # NET (例 49.0001.0100.0000.0001.00)


class IsisInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    nodes: list[IsisInstanceNode] = []
    description: str | None = None


class BFDConfig(BaseModel):
    """BFD のタイマー。nodes はこのタイマーを使うノード (BFD を張るかはセッションの bfd で決める)"""

    model_config = ConfigDict(extra="forbid")

    id: str
    min_tx: int = 300       # ms
    min_rx: int = 300       # ms
    multiplier: int = 3
    nodes: Annotated[list[str], Ref("layer1.nodes")] = []


# ---------------------------------------------------------------------------
# セッションの端点 (ADR-0010 D3)
# ---------------------------------------------------------------------------

class BgpInsideEndpoint(BaseModel):
    """トポロジー内の機器の端点。update_source は必須 (セッションのアドレスと通り道を決める)"""

    model_config = ConfigDict(extra="forbid")

    node: Annotated[str, Ref("layer1.nodes")]
    update_source: Annotated[str, Ref("layer3.interfaces", "layer3.tunnel_interfaces")]   # トンネル IF も書ける (ADR-0018 D3)
    route_reflector_client: bool = False     # この端が RR クライアント (RFC 4456。neighbor 単位)


class BgpOutsideEndpoint(BaseModel):
    """トポロジー外の相手 (IP と AS しか分からない)。local_as はその相手自身の AS"""

    model_config = ConfigDict(extra="forbid")

    address: IPv4Address | IPv6Address       # 相手のホストアドレス (プレフィックス長なし)
    local_as: int


def _endpoint_tag(value: Any) -> str:
    """node を書いた端はトポロジー内、書いていない端はトポロジー外"""
    if isinstance(value, dict):
        return "inside" if "node" in value else "outside"
    return "inside" if isinstance(value, BgpInsideEndpoint) else "outside"


BgpEndpoint = Annotated[
    Union[Annotated[BgpInsideEndpoint, Tag("inside")], Annotated[BgpOutsideEndpoint, Tag("outside")]],
    Discriminator(_endpoint_tag),
]


class OspfEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: Annotated[str, Ref("layer1.nodes")]
    interface: Annotated[str, Ref("layer3.interfaces", "layer3.tunnel_interfaces")]   # OSPF は IP 上で hello を送る。トンネル IF も書ける (ADR-0018 D3)


class IsisEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: Annotated[str, Ref("layer1.nodes")]
    interface: Annotated[str, Ref("layer1.interfaces")]     # IS-IS は L2 上で IIH を送る


# ---------------------------------------------------------------------------
# セッション (ADR-0010 D3)
# ---------------------------------------------------------------------------

class BgpSession(BaseModel):
    """BGP のセッション 1 本"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    type: Literal["bgp"]
    instance: Annotated[str | None, Ref("control_plane.bgp")] = None
    from_: BgpEndpoint = Field(alias="from")
    to: BgpEndpoint
    address_families: list[AddressFamily] = []
    bfd: bool = False
    description: str | None = None

    @model_validator(mode="after")
    def one_end_inside(self) -> "BgpSession":
        if isinstance(self.from_, BgpOutsideEndpoint) and isinstance(self.to, BgpOutsideEndpoint):
            raise ValueError("両端ともトポロジー外 (address) にはできません。少なくとも一方は node で書いてください (ADR-0010 D3)")
        return self


class OspfAdjacency(BaseModel):
    """OSPF の隣接 1 本 (ポイントツーポイント)"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    type: Literal["ospf"]
    instance: Annotated[str | None, Ref("control_plane.ospf")] = None
    from_: OspfEndpoint = Field(alias="from")
    to: OspfEndpoint
    area: str
    bfd: bool = False
    description: str | None = None

    @field_validator("area", mode="before")
    @classmethod
    def normalize_area(cls, v: Any) -> str:
        """ドット区切り 4 オクテットにそろえる。`0` は `0.0.0.0` (ADR-0010 D8)"""
        s = str(v).strip()
        if s.isdigit():
            n = int(s)
            if n >= 2 ** 32:
                raise ValueError(f"OSPF の area '{s}' が 32 bit に収まりません")
            return ".".join(str((n >> shift) & 0xFF) for shift in (24, 16, 8, 0))
        m = _DOTTED_QUAD.match(s)
        if not m or any(int(x) > 255 for x in m.groups()):
            raise ValueError(f"OSPF の area '{s}' はドット区切り 4 オクテットか整数で書いてください")
        return s


class IsisAdjacency(BaseModel):
    """IS-IS の隣接 1 本 (ポイントツーポイント)"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    type: Literal["isis"]
    instance: Annotated[str | None, Ref("control_plane.isis")] = None
    from_: IsisEndpoint = Field(alias="from")
    to: IsisEndpoint
    level: Literal["level-1", "level-2", "level-all"]       # RFC 9130
    bfd: bool = False
    description: str | None = None


RoutingNeighbor = Annotated[BgpSession | OspfAdjacency | IsisAdjacency, Field(discriminator="type")]


class ControlPlane(BaseModel):
    """制御プレーン全体。インスタンスごとの設定 → セッション の順に書くことを推奨する"""

    model_config = ConfigDict(extra="forbid")

    bgp: list[BgpInstance] = []
    ospf: list[OspfInstance] = []
    isis: list[IsisInstance] = []
    bfd: list[BFDConfig] = []
    routing_neighbors: list[RoutingNeighbor] = []


# ---------------------------------------------------------------------------
# 旧構造 (ADR-0010 D12): 読み替えず、移動先・代わりの書き方を示すエラーにする
# ---------------------------------------------------------------------------

def legacy_control_plane_errors(data: dict) -> list[str]:
    """旧キー (protocols / layer3.routing_adjacencies 等) が書かれていれば、移動先を示すメッセージを返す"""
    messages: list[str] = []
    protocols = data.get("protocols")
    if protocols is not None:
        messages.append("protocols は control_plane に移動しました (ADR-0010)")
        bgps = protocols.get("bgp", []) if isinstance(protocols, dict) else []
        bgps = bgps if isinstance(bgps, list) else []
        if any(isinstance(b, dict) and "role" in b for b in bgps):
            messages.append("protocols.bgp[].role は廃止しました。underlay / overlay はセッションの address_families から導きます (ADR-0010)")
        neighbors = [nb for b in bgps if isinstance(b, dict) for bn in (b.get("nodes") or []) if isinstance(bn, dict)
                     for nb in (bn.get("neighbors") or []) if isinstance(nb, dict)]
        if neighbors:
            messages.append("protocols.bgp[].nodes[].neighbors は廃止しました。セッションは control_plane.routing_neighbors に"
                            " 1 本 1 エントリで書き、各機器の AS はインスタンスの nodes[].local_as に書きます"
                            " (remote_as / type は両端の AS から導きます。ADR-0010)")
    layer3 = data.get("layer3")
    if isinstance(layer3, dict) and "routing_adjacencies" in layer3:
        messages.append("layer3.routing_adjacencies は control_plane.routing_neighbors に移動しました。"
                        "attaches_to は書かず、update_source から導きます (ADR-0010)")
    return messages
