"""プロトコル設定スキーマ (BFD / BGP)"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict

from .refs import Ref


class BFDConfig(BaseModel):
    """BFD タイマー設定"""

    model_config = ConfigDict(extra="forbid")

    id: str
    min_tx: int = 300       # ms
    min_rx: int = 300       # ms
    multiplier: int = 3
    nodes: Annotated[list[str], Ref("layer1.nodes")] = []


class BGPNeighbor(BaseModel):
    """BGP ネイバー"""

    model_config = ConfigDict(extra="forbid")

    node: Annotated[str, Ref("layer1.nodes")]
    remote_as: int | None = None
    type: Literal["ebgp", "ibgp"] | None = None
    bfd: bool = False
    role: str | None = None                         # route_reflector / route_reflector_client
    address_families: list[str] = []                # l2vpn_evpn / ipv4_unicast 等


class BGPNode(BaseModel):
    """BGP プロセス内のノード設定"""

    model_config = ConfigDict(extra="forbid")

    node: Annotated[str, Ref("layer1.nodes")]
    local_as: int | None = None
    role: str | None = None         # route_reflector 等
    neighbors: list[BGPNeighbor] = []


class BGPProcess(BaseModel):
    """BGP プロセス定義"""

    model_config = ConfigDict(extra="forbid")

    id: str
    role: str | None = None         # underlay / overlay
    nodes: list[BGPNode] = []


class Protocols(BaseModel):
    """プロトコル全体"""

    model_config = ConfigDict(extra="forbid")

    bfd: list[BFDConfig] = []
    bgp: list[BGPProcess] = []
