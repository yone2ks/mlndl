"""Layer 2 スキーマ定義 (VLAN / VxLAN)"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class PortRef(BaseModel):
    """node + interface の参照ペア（trunk_ports / access_ports 用）

    native: trunk 上でこの VLAN を untagged(native VLAN)として流す場合 True。
    access_ports では常に untagged のため通常は未指定。
    """

    model_config = ConfigDict(extra="forbid")

    node: str
    interface: str
    native: bool = False


class VLAN(BaseModel):
    """VLAN 定義"""

    model_config = ConfigDict(extra="forbid")

    id: str
    vlan_id: int
    name: str | None = None
    trunk_ports: list[PortRef] = []
    access_ports: list[PortRef] = []


class L2VxLAN(BaseModel):
    """L2VNI — VLAN を VxLAN セグメントにマッピング"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["l2vni"]
    vni: int
    vlan: str               # layer2.vlans[].id を参照
    vtep_source: str        # layer3.interfaces[].id を参照（VTEP ループバック）
    members: list[str] = [] # layer1.nodes[].id を参照


class L3VxLAN(BaseModel):
    """L3VNI — Symmetric IRB 用 VRF ↔ VNI バインディング"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["l3vni"]
    vni: int
    vrf: str                                           # layer3.vrfs[].id を参照
    irb_mode: Literal["symmetric", "asymmetric"] | None = None


# Discriminated Union
VxLAN = Annotated[L2VxLAN | L3VxLAN, Field(discriminator="type")]


class L2Layer(BaseModel):
    """Layer 2 全体"""

    model_config = ConfigDict(extra="forbid")

    vlans: list[VLAN] = []
    vxlan: list[VxLAN] = []
