"""Layer 2 スキーマ定義 (VLAN / bridge / VTEP / VxLAN / Subinterface)"""

from __future__ import annotations

from ipaddress import IPv4Interface, IPv6Interface
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .layer1 import AttachesToObj, restrict_attach_keys
from .refs import Ref


PORT_KEYS = ("interface", "lag", "ethernet_segment")


class PortTarget(BaseModel):
    """ポートへの参照の共通の形。VLAN のポート (ADR-0013) と bridge のポート (ADR-0018) が使う

    interface / lag / ethernet_segment: どれか 1 つ。参照先の種類をキーで示す (ADR-0001 D8)
               lag のときはメンバーではなく LAG を指す。ethernet_segment は束ねたすべての機器の脚に効く (ADR-0023 D5)
    """

    model_config = ConfigDict(extra="forbid")

    interface: str | None = None
    lag: str | None = None
    ethernet_segment: str | None = None

    @model_validator(mode="after")
    def exactly_one_target(self) -> "PortTarget":
        if sum(1 for k in PORT_KEYS if getattr(self, k) is not None) != 1:
            raise ValueError(
                "ポートは interface (L1 IF)・lag (LAG)・ethernet_segment (Ethernet Segment) のどれか 1 つで指してください"
                " (ADR-0013 D1 / ADR-0023 D5)"
            )
        return self

    @property
    def kind(self) -> str:
        """書かれたキー名 (interface / lag / ethernet_segment)"""
        return next(k for k in PORT_KEYS if getattr(self, k) is not None)

    @property
    def target(self) -> str:
        """参照先の ID"""
        return getattr(self, self.kind)


class PortRef(PortTarget):
    """VLAN が載るポートへの参照（trunk_ports / access_ports 用。ADR-0013）

    interface / lag: PortTarget。lag のときの VLAN の設定は port-channel / bond 側にあり、メンバーはそれを継承する
    node:      廃止予定。ノードは interface / lag から導出する (ADR-0013 D2)。
               ndl_version 1.x の間は受け付け、validator が warning を出して照合する
    native:    trunk 上でこの VLAN を untagged(native VLAN)として流す場合 True。
               access_ports では常に untagged のため通常は未指定。
    """

    node: Annotated[str | None, Ref("layer1.nodes")] = None   # 旧形式
    native: bool = False


class BridgePort(PortTarget):
    """bridge のポート (ADR-0018 D1)。フレームを転送する側 (事業者網なら箱) の L1 IF・LAG・Ethernet Segment。native は持たない"""


class VLAN(BaseModel):
    """VLAN 定義"""

    model_config = ConfigDict(extra="forbid")

    id: str
    vlan_id: int = Field(ge=1, le=4094)     # IEEE 802.1Q VID。0 と 4095 は予約
    name: str | None = None
    trunk_ports: list[PortRef] = []
    access_ports: list[PortRef] = []
    description: str | None = None


class Bridge(BaseModel):
    """番号を持たない 1 つの L2 セグメント (ADR-0018 D1)

    ports のあいだで Ethernet フレームが L2 のまま転送される。事業者網の中の転送 (広域イーサ) に使う。
    - ports には転送する側 (箱) のポートを書く。拠点のルーターのポートは書かない (bridge を使う側)
    - 方式名 (E-LINE / E-LAN / VPLS / EVPN) は書かない。name / description に書く
    - node は持たない (ports から導出する。ADR-0005 D6)
    - vSwitch のための type / uplinks などは drafts/0007 で任意のフィールドとして加算する
    """

    model_config = ConfigDict(extra="forbid")

    id: str                                 # 推奨プレフィックス bridge- (ADR-0002 D7)
    name: str | None = None
    ports: list[BridgePort] = []
    description: str | None = None


class Vtep(BaseModel):
    """VXLAN トンネル端点 (ADR-0014)

    1 つ以上のノードが終端するトンネル端点アドレスとして表す。冗長化の方式名
    (anycast / vPC / virtual VTEP / BGW など) は構文に入れない (ADR-0014 D1)。

    - sources: この VTEP を終端するノードの L3 IF (ループバック) の id。ノードは各 L3 IF から決まる
    - address / address_v6: VTEP のアドレス。sources が 1 つなら省略でき、その L3 IF の ip / ipv6 になる。
      sources が複数 (複数ノードで共有) なら必須
    """

    model_config = ConfigDict(extra="forbid")

    id: str                                         # 推奨プレフィックス vtep- (ADR-0002 D7)
    sources: Annotated[list[str], Ref("layer3.interfaces")] = Field(min_length=1)
    address: IPv4Interface | None = None
    address_v6: IPv6Interface | None = None
    description: str | None = None

    @field_validator("address", mode="before")
    @classmethod
    def address_is_ipv4(cls, v: Any) -> Any:
        if isinstance(v, str) and ":" in v:
            raise ValueError(f"address は IPv4 専用です。IPv6 アドレス '{v}' は address_v6 に書いてください (ADR-0014 D2)")
        return v

    @model_validator(mode="after")
    def shared_vtep_needs_address(self) -> "Vtep":
        if len(self.sources) > 1 and self.address is None and self.address_v6 is None:
            raise ValueError(
                "複数のノードで共有する VTEP には、共有するアドレスを address (または address_v6) に"
                "書いてください。省略できるのは sources が 1 つのときだけです (ADR-0014 D2)"
            )
        return self


class L2VxLAN(BaseModel):
    """L2VNI — VLAN を VxLAN セグメントにマッピング

    vteps: この VNI が載る VTEP (layer2.vteps[].id)。ADR-0014
    vtep_source / members: 旧形式。ndl_version 1.x の間だけ受け付け、validator が warning を出す
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["l2vni"]
    vni: int
    vlan: Annotated[str, Ref("layer2.vlans")]
    vteps: Annotated[list[str], Ref("layer2.vteps")] = []
    vtep_source: Annotated[str | None, Ref("layer3.interfaces")] = None   # 旧形式
    members: Annotated[list[str] | None, Ref("layer1.nodes")] = None     # 旧形式。書き出しに出ないよう既定は None
    description: str | None = None

    @model_validator(mode="after")
    def vteps_or_legacy(self) -> "L2VxLAN":
        legacy = self.vtep_source is not None or bool(self.members)
        if self.vteps and legacy:
            raise ValueError(
                "vteps と旧形式の vtep_source / members は併記できません。vteps だけを書いてください (ADR-0014 D4)"
            )
        if not self.vteps and self.vtep_source is None:
            raise ValueError("L2VNI が載る VTEP を vteps: [<layer2.vteps の id>] で書いてください (ADR-0014 D3)")
        return self


class L3VxLAN(BaseModel):
    """L3VNI — Symmetric IRB 用 VRF ↔ VNI バインディング"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["l3vni"]
    vni: int
    vrf: Annotated[str, Ref("layer3.vrfs")]
    irb_mode: Literal["symmetric", "asymmetric"] | None = None
    description: str | None = None


# Discriminated Union
VxLAN = Annotated[L2VxLAN | L3VxLAN, Field(discriminator="type")]


class Subinterface(BaseModel):
    """802.1Q サブインターフェース (ADR-0012)

    物理 IF または LAG を 802.1Q タグで分割した論理 IF。L3 は
    layer3.interfaces[].attaches_to: {subinterface: <サブ IF の id>} で載る。

    - node は持たない。基盤 (L1 IF / LAG) から導出できるため (ADR-0005 D6、ADR-0012 D2)
    - vlan_id はこのリンク上の 802.1Q タグ番号であり、layer2.vlans への参照ではない。
      タグの書き換えや拠点ごとの番号再利用でタグと VLAN エンティティは一致しないことがある
    - Q-in-Q (stag_vlan_id / ctag_vlan_id)、ネイティブ (タグなし) サブ IF、
      L2 のサービスインスタンスは範囲外
    """

    model_config = ConfigDict(extra="forbid")

    id: str                                 # 推奨プレフィックス subif- (ADR-0002 D7)
    attaches_to: AttachesToObj              # {interface: <L1 IF の id>} または {lag: <LAG の id>}
    vlan_id: int = Field(ge=1, le=4094)     # IEEE 802.1Q VID。0 と 4095 は予約
    name: str | None = None                 # 機器上の名前 (eth0.10 / Gi0/0.10 / bond0.10)
    description: str | None = None

    @field_validator("attaches_to", mode="before")
    @classmethod
    def object_form_only(cls, v: Any) -> Any:
        if isinstance(v, str):
            raise ValueError(
                "サブインターフェースの attaches_to は {interface: <L1 IF の id>} か {lag: <LAG の id>} で"
                "書いてください。文字列はノード ID の糖衣構文です (ADR-0001, ADR-0012 D4)"
            )
        return v

    @field_validator("attaches_to")
    @classmethod
    def parent_keys(cls, v: AttachesToObj) -> AttachesToObj:
        return restrict_attach_keys(v, frozenset({"interface", "lag"}), "layer2.subinterfaces")


class L2Layer(BaseModel):
    """Layer 2 全体"""

    model_config = ConfigDict(extra="forbid")

    vlans: list[VLAN] = []
    bridges: list[Bridge] = []
    vteps: list[Vtep] = []
    vxlan: list[VxLAN] = []
    subinterfaces: list[Subinterface] = []
