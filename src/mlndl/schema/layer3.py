"""Layer 3 スキーマ定義 (VRF / L3Interface / GatewayRedundancy / TunnelInterface)

設計決定:
- ADR-0011 D3: 機器上の名前は name、参照は attaches_to だけ。SVI は attaches_to: {vlan: <VLAN id>}。
  旧 `interface` キーと短縮形 `interface: vlan-N` は移動先を示すエラーにする (ADR-0025 D1)
- ADR-0011 D4: fhrp → gateway_redundancy。mode を discriminator とする Tagged Union
- ADR-0011 D5: ip は IPv4、ipv6 は IPv6。いずれも単数
- ADR-0011 D6: トンネルは自己完結した TunnelInterface で表現する
- ルーティングのセッションは control_plane.routing_neighbors に置く (ADR-0010。control_plane.py)
"""

from __future__ import annotations

import re
from ipaddress import IPv4Address, IPv4Interface, IPv6Address, IPv6Interface
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .layer1 import AttachesTo, AttachesToObj, restrict_attach_keys
from .refs import Ref

# 旧形式: `interface` がこの形で attaches_to がないものは、VLAN を指す短縮形だった (ADR-0011 D10・ADR-0025 D1)
VLAN_SHORTHAND = re.compile(r"^vlan-\d+$")

# L3Interface の attaches_to に書けるキー (ADR-0001 D8)
L3_ATTACH_KEYS = frozenset({"interface", "lag", "vlan", "subinterface"})

def _reject_ipv6_in_ip(value: Any) -> Any:
    """`ip` に IPv6 を書いた場合に、移動先を示すエラーを返す (ADR-0011 D5)"""
    if isinstance(value, str) and ":" in value:
        raise ValueError(
            f"ip は IPv4 専用です。IPv6 アドレス '{value}' は ipv6 に書いてください (ADR-0011 D5)"
        )
    return value


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
    l3vni: Annotated[str | None, Ref("layer2.vxlan", where=("type", "l3vni"))] = None
    route_targets: RouteTargets | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# gateway_redundancy (ADR-0011 D4)
# ---------------------------------------------------------------------------

def _require_link_local_v6(vip: IPv4Address | IPv6Address, mode: str) -> None:
    """RFC 5798 §5.2.9 / §6.1: IPv6 の仮想ルーターの先頭アドレスはリンクローカル"""
    if isinstance(vip, IPv6Address) and not vip.is_link_local:
        raise ValueError(
            f"{mode} の IPv6 VIP はリンクローカル (fe80::/10) である必要があります: '{vip}'"
            f" (RFC 5798 §5.2.9 / §6.1, ADR-0011 D4)"
        )


class VrrpGateway(BaseModel):
    """VRRP によるゲートウェイ冗長。1 インスタンスは単一 AF (RFC 5798)"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["vrrp"]
    group_id: int = Field(ge=1, le=255)             # VRID (RFC 5798 §5.2.3)
    vip: IPv4Address | IPv6Address
    priority: int | None = Field(default=None, ge=1, le=254)
    preempt: bool | None = None
    description: str | None = None

    @model_validator(mode="after")
    def ipv6_vip_is_link_local(self) -> "VrrpGateway":
        _require_link_local_v6(self.vip, "VRRP")
        return self


class HsrpGateway(BaseModel):
    """HSRP によるゲートウェイ冗長 (Cisco)"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["hsrp"]
    group_id: int = Field(ge=0, le=4095)            # HSRPv1 0..255 / HSRPv2 0..4095
    vip: IPv4Address | IPv6Address
    priority: int | None = Field(default=None, ge=0, le=255)
    preempt: bool | None = None
    description: str | None = None

    @model_validator(mode="after")
    def ipv6_vip_is_link_local(self) -> "HsrpGateway":
        _require_link_local_v6(self.vip, "HSRP")
        return self


class AnycastGateway(BaseModel):
    """EVPN distributed anycast gateway (RFC 9135)

    プロトコル交換を持たず、全ノードが同時に active。VIP / group_id は持たない
    (L3Interface の ip / ipv6 自体が anycast アドレス)。
    anycast の MAC アドレスは書かない。MAC は構成図の粒度ではない (ADR-0022 D2)
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["anycast_gateway"]
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_anycast_mac(cls, data: Any) -> Any:
        if isinstance(data, dict) and "anycast_mac" in data:
            raise ValueError(
                "anycast_mac はなくしました。MAC アドレスは構成図の粒度ではないので書きません。"
                "anycast gateway は ip / ipv6 が全ノードで同じことだけを書きます (ADR-0022 D2)"
            )
        return data


GatewayRedundancy = Annotated[
    VrrpGateway | HsrpGateway | AnycastGateway, Field(discriminator="mode")
]


# ---------------------------------------------------------------------------
# L3Interface
# ---------------------------------------------------------------------------

class L3Interface(BaseModel):
    """Layer 3 インターフェース（ループバック / SVI / ルーテッドポート / サブ IF / routed LAG）

    - name: 機器上の名前 (swp51 / Vlan100 / lo)。参照ではない
    - attaches_to: 参照の唯一の手段。参照先の種類をキーで示す (ADR-0001 D8)。
      {interface: <L1 IF>} / {lag: <LAG>} / {vlan: <VLAN>} / {subinterface: <サブ IF>}。
      ループバックのように基盤を持たない L3 IF では省略する
    - 旧形式 (`interface` キー、短縮形 `interface: vlan-N`) は移動先を示すエラーにする。読み替えない (ADR-0025 D1)
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    node: Annotated[str, Ref("layer1.nodes")]   # ノードごとの実体なので必須 (ADR-0005 D6)
    name: str                       # 機器上の名前
    ip: IPv4Interface | None = None     # IPv4 (CIDR)
    ipv6: IPv6Interface | None = None   # IPv6 (CIDR)
    vrf: Annotated[str | None, Ref("layer3.vrfs")] = None
    attaches_to: AttachesToObj | None = None
    gateway_redundancy: list[GatewayRedundancy] = []
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_old_forms(cls, data: Any) -> Any:
        """廃止したキーと旧形式に、移動先を示すエラーを返す (ADR-0011 D10・ADR-0025 D1)"""
        if isinstance(data, dict):
            _reject_removed_keys(data)
        return data

    @field_validator("attaches_to", mode="before")
    @classmethod
    def object_form_only(cls, v: Any) -> Any:
        if isinstance(v, str):
            raise ValueError(
                "L3 インターフェースの attaches_to はオブジェクト形式で書いてください"
                " (文字列はノード ID の糖衣構文です。ADR-0001 D3・D8)"
            )
        return v

    @field_validator("attaches_to")
    @classmethod
    def l3_attach_keys(cls, v: Any) -> Any:
        return restrict_attach_keys(v, L3_ATTACH_KEYS, "layer3.interfaces")

    @field_validator("ip", mode="before")
    @classmethod
    def ip_is_ipv4(cls, v: Any) -> Any:
        return _reject_ipv6_in_ip(v)

    def attachment_ref(self) -> str | None:
        """attaches_to が指す ID (なければ None)"""
        return self.attaches_to.target if self.attaches_to is not None else None


def _reject_removed_keys(data: dict) -> None:
    """なくしたキー (ADR-0011 D10) と旧形式の interface キー (ADR-0025 D1) に、移動先を示すエラーを返す"""
    problems = []
    if "interface" in data:
        legacy = data["interface"]
        if data.get("attaches_to") is None and isinstance(legacy, str) and VLAN_SHORTHAND.match(legacy):
            problems.append(
                f"L3 IF の短縮形 interface: {legacy} はなくしました。name: <機器上の名前> と"
                f" attaches_to: {{vlan: {legacy}}} に書き換えてください (ADR-0011 D3・ADR-0025)"
            )
        else:
            problems.append(
                "L3 IF の interface はなくしました。機器上の名前は name に書き、L1 IF などへの参照は"
                " attaches_to: {interface: <L1 IF の id>} のように書きます (ADR-0011 D3・ADR-0025)"
            )
    if "vlan" in data:
        problems.append(
            "vlan は廃止されました。SVI は attaches_to: {vlan: <VLAN id>} で書いてください (ADR-0011 D3)"
        )
    if "fhrp" in data:
        problems.append(
            "fhrp は gateway_redundancy に改名されました。protocol は mode に、"
            "anycast は anycast_gateway になります (ADR-0011 D4)"
        )
    for gw in data.get("gateway_redundancy") or []:
        if isinstance(gw, dict) and "protocol" in gw and "mode" not in gw:
            problems.append("gateway_redundancy の protocol は mode に改名されました (ADR-0011 D4)")
            break
    if problems:
        raise ValueError(" / ".join(problems))


# ---------------------------------------------------------------------------
# TunnelInterface (ADR-0011 D6)
# ---------------------------------------------------------------------------

class TunnelInterface(BaseModel):
    """トンネルインターフェース。source / destination を自分で持つ自己完結型。

    対向がトポロジー内なら destination_interface、外なら destination_ip を使う (排他)。
    両端を結ぶ辺はエクスポーターが導出する (tunnel_links は二重表現になるため作らない)。
    """

    model_config = ConfigDict(extra="forbid")

    id: str                                         # 推奨プレフィックス tunnel- (ADR-0002 D7)
    node: Annotated[str, Ref("layer1.nodes")]
    type: Literal["gre", "ipip", "ipsec_vti", "wireguard"]
    source: Annotated[str, Ref("layer3.interfaces")]   # トンネルの起点
    destination_ip: IPv4Address | IPv6Address | None = None   # トポロジー外の対向
    destination_interface: Annotated[str | None, Ref("layer3.interfaces")] = None
    ip: IPv4Interface | None = None                 # トンネル IF 自体のアドレス
    ipv6: IPv6Interface | None = None
    vrf: Annotated[str | None, Ref("layer3.vrfs")] = None             # トンネル IF が属する VRF (overlay 側)
    transport_vrf: Annotated[str | None, Ref("layer3.vrfs")] = None   # 外側パケットが流れる VRF
    mtu: int | None = Field(default=None, ge=68)    # IPv4 最小 MTU (RFC 791)
    description: str | None = None

    @field_validator("ip", mode="before")
    @classmethod
    def ip_is_ipv4(cls, v: Any) -> Any:
        return _reject_ipv6_in_ip(v)

    @model_validator(mode="after")
    def exactly_one_destination(self) -> "TunnelInterface":
        given = [x for x in (self.destination_ip, self.destination_interface) if x is not None]
        if len(given) != 1:
            raise ValueError(
                "destination_ip と destination_interface はどちらか一方だけを指定してください"
                " (ADR-0011 D6)"
            )
        return self


class L3Layer(BaseModel):
    """Layer 3 全体"""

    model_config = ConfigDict(extra="forbid")

    vrfs: list[VRF] = []
    interfaces: list[L3Interface] = []
    tunnel_interfaces: list[TunnelInterface] = []
