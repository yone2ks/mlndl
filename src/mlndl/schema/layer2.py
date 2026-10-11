"""Layer 2 スキーマ定義 (VLAN / VxLAN / Subinterface)"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .layer1 import AttachesToObj


class PortRef(BaseModel):
    """VLAN が載るポートへの参照（trunk_ports / access_ports 用。ADR-0013）

    interface: L1 IF の id または LAG の id。LAG のときはメンバーではなく LAG を指す
               (VLAN の設定は port-channel / bond 側にあり、メンバーはそれを継承する)
    node:      省略可。interface から導出できる。書いた場合は validator が照合する。
               MLAG は両ノードに効くので node を書けない
    native:    trunk 上でこの VLAN を untagged(native VLAN)として流す場合 True。
               access_ports では常に untagged のため通常は未指定。
    """

    model_config = ConfigDict(extra="forbid")

    interface: str
    node: str | None = None
    native: bool = False


class VLAN(BaseModel):
    """VLAN 定義"""

    model_config = ConfigDict(extra="forbid")

    id: str
    vlan_id: int
    name: str | None = None
    trunk_ports: list[PortRef] = []
    access_ports: list[PortRef] = []
    description: str | None = None


class L2VxLAN(BaseModel):
    """L2VNI — VLAN を VxLAN セグメントにマッピング"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["l2vni"]
    vni: int
    vlan: str               # layer2.vlans[].id を参照
    vtep_source: str        # layer3.interfaces[].id を参照（VTEP ループバック）
    members: list[str] = [] # layer1.nodes[].id を参照
    description: str | None = None


class L3VxLAN(BaseModel):
    """L3VNI — Symmetric IRB 用 VRF ↔ VNI バインディング"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["l3vni"]
    vni: int
    vrf: str                                           # layer3.vrfs[].id を参照
    irb_mode: Literal["symmetric", "asymmetric"] | None = None
    description: str | None = None


# Discriminated Union
VxLAN = Annotated[L2VxLAN | L3VxLAN, Field(discriminator="type")]


class Subinterface(BaseModel):
    """802.1Q サブインターフェース (ADR-0012)

    物理 IF または LAG を 802.1Q タグで分割した論理 IF。L3 は
    layer3.interfaces[].attaches_to: {interface: <サブ IF の id>} で載る。

    - node は持たない。親 (L1 IF / LAG) から導出できるため (二重表現を作らない)
    - vlan_id はこのリンク上の 802.1Q タグ番号であり、layer2.vlans への参照ではない。
      タグの書き換えや拠点ごとの番号再利用でタグと VLAN エンティティは一致しないことがある
    - Q-in-Q (stag_vlan_id / ctag_vlan_id)、ネイティブ (タグなし) サブ IF、
      L2 のサービスインスタンスは範囲外
    """

    model_config = ConfigDict(extra="forbid")

    id: str                                 # 推奨プレフィックス subif- (ADR-0002 D7)
    attaches_to: AttachesToObj              # {interface: <L1 IF の id または LAG の id>}
    vlan_id: int = Field(ge=1, le=4094)     # IEEE 802.1Q VID。0 と 4095 は予約
    name: str | None = None                 # 機器上の名前 (eth0.10 / Gi0/0.10 / bond0.10)
    description: str | None = None

    @field_validator("attaches_to", mode="before")
    @classmethod
    def object_form_only(cls, v: Any) -> Any:
        if isinstance(v, str):
            raise ValueError(
                "サブインターフェースの attaches_to は {interface: <L1 IF または LAG の id>} で"
                "書いてください。文字列はノード ID の糖衣構文です (ADR-0001, ADR-0012)"
            )
        return v

    @model_validator(mode="after")
    def parent_is_interface(self) -> "Subinterface":
        if self.attaches_to.interface is None:
            raise ValueError(
                "サブインターフェースの attaches_to は interface キーで親 (L1 IF または LAG) を"
                "指してください (ADR-0012)"
            )
        return self


class L2Layer(BaseModel):
    """Layer 2 全体"""

    model_config = ConfigDict(extra="forbid")

    vlans: list[VLAN] = []
    vxlan: list[VxLAN] = []
    subinterfaces: list[Subinterface] = []
