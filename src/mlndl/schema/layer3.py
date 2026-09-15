"""Layer 3 スキーマ定義 (VRF / L3Interface / RoutingAdjacency)"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .layer1 import AttachesTo


class RouteTargets(BaseModel):
    """BGP Route Target (import/export)"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    import_: list[str] = Field(default=[], alias="import")  # Python 予約語回避
    export: list[str] = []


class VRF(BaseModel):
    """VRF 定義"""

    model_config = ConfigDict(extra="forbid")

    id: str
    rd: str | None = None           # Route Distinguisher — ASN:NN または IP:NN
    l3vni: str | None = None        # layer2.vxlan[l3vni].id を参照
    route_targets: RouteTargets | None = None


class FhrpInstance(BaseModel):
    """FHRP（VRRP / HSRP）インスタンス設定（per-node SVI スコープ）"""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["vrrp", "hsrp"]
    group_id: int
    vip: str
    priority: int | None = None
    preempt: bool | None = None


class L3Interface(BaseModel):
    """Layer 3 インターフェース（ループバック / SVI / ルーテッドポート）"""

    model_config = ConfigDict(extra="forbid")

    id: str
    node: str                       # layer1.nodes[].id を参照
    interface: str                  # 論理 IF 名 (lo, vlan-100, swp51 等)
    ip: str | None = None           # IPv4/IPv6 アドレス（CIDR 表記）
    vrf: str | None = None          # layer3.vrfs[].id を参照
    vlan: str | None = None         # SVI の場合、対応する layer2.vlans[].id への明示参照
    attaches_to: AttachesTo | None = None
    fhrp: list[FhrpInstance] = []


class RoutingAdjEndpoint(BaseModel):
    """ルーティング隣接関係の片端"""

    model_config = ConfigDict(extra="forbid")

    node: str                       # layer1.nodes[].id を参照
    update_source: str | None = None  # layer3.interfaces[].id を参照


class RoutingAdjacency(BaseModel):
    """ルーティング隣接関係（BGP / OSPF / IS-IS）"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    type: Literal["bgp", "ospf", "isis"]
    from_: RoutingAdjEndpoint = Field(alias="from")  # Python 予約語回避
    to: RoutingAdjEndpoint
    attaches_to: AttachesTo | None = None


class L3Layer(BaseModel):
    """Layer 3 全体"""

    model_config = ConfigDict(extra="forbid")

    vrfs: list[VRF] = []
    interfaces: list[L3Interface] = []
    routing_adjacencies: list[RoutingAdjacency] = []
