"""Layer 1 (物理トポロジー) スキーマ定義

設計決定:
- attaches_to: ADR-0001 — str | {node:} | {interface:} | {link:}
- role: ADR-0003 C2 — 自由文字列、コアは値域チェックなし
- implementation: ADR-0004 — vm | physical | container
- lag: §6 設計決定 — type: lacp | mlag の Discriminated Union
- id 命名規則: ADR-0002 — ^[a-z][a-z0-9]*(-[a-z0-9]+)*$（推奨、強制なし）
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# attaches_to (ADR-0001)
# ---------------------------------------------------------------------------

class AttachesToObj(BaseModel):
    """attaches_to のオブジェクト形式。node / interface / link のいずれか 1 キーのみ有効。"""

    model_config = ConfigDict(extra="forbid")

    node: str | None = None
    interface: str | None = None
    link: str | None = None

    @model_validator(mode="after")
    def exactly_one_key(self) -> "AttachesToObj":
        set_keys = sum(
            1 for v in [self.node, self.interface, self.link] if v is not None
        )
        if set_keys != 1:
            raise ValueError(
                "attaches_to オブジェクトは node / interface / link のいずれか 1 キーのみ指定してください"
            )
        return self


# 文字列形式（ノードID 糖衣構文）とオブジェクト形式の Union
AttachesTo = str | AttachesToObj


# ---------------------------------------------------------------------------
# L1Node
# ---------------------------------------------------------------------------

class L1Node(BaseModel):
    """Layer 1 ノード（物理・仮想を問わず「箱」を表す）"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None
    implementation: Literal["vm", "physical", "container"] | None = None
    role: str | None = None  # 自由文字列。推奨語彙: docs/role-vocabulary.md
    device_type: str | None = None  # 抽象キー。eve-lab-builder で変換
    attaches_to: AttachesTo | None = None
    overrides: dict[str, Any] | None = None  # 上位ツール向け任意上書き

    @model_validator(mode="after")
    def reject_container_hypervisor(self) -> "L1Node":
        """ADR-0004 D-1: container × hypervisor は技術的に成立しない"""
        if self.implementation == "container" and self.role == "hypervisor":
            raise ValueError(
                "implementation=container と role=hypervisor の組み合わせは"
                "技術的に成立しません (ADR-0004 D-1)"
            )
        return self


# ---------------------------------------------------------------------------
# L1Interface
# ---------------------------------------------------------------------------

class L1Interface(BaseModel):
    """Layer 1 インターフェース（物理ポート）"""

    model_config = ConfigDict(extra="forbid")

    id: str
    node: str  # 所属ノード ID
    name: str | None = None
    attaches_to: AttachesTo | None = None


# ---------------------------------------------------------------------------
# L1Link
# ---------------------------------------------------------------------------

class L1Link(BaseModel):
    """Layer 1 物理リンク（ケーブル）"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_: str = Field(alias="from")  # Python 予約語回避
    to: str
    link_speed: str | None = None   # 例: "10G", "100G"
    mtu: int | None = None
    link_role: str | None = None    # underlay / access / peer-link / management / uplink


# ---------------------------------------------------------------------------
# LAG (LACP + MLAG 統合) — §6 設計決定
# ---------------------------------------------------------------------------

class LacpConfig(BaseModel):
    """LACP パラメータ"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["active", "passive", "on"] = "active"
    min_links: int = 1


class LacpLag(BaseModel):
    """単一ノードの LACP bond"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["lacp"]
    node: str          # 単数形: 1 ノード
    members: list[str]  # インターフェース ID リスト
    lacp: LacpConfig | None = None


class MlagLag(BaseModel):
    """マルチシャーシ LAG (MLAG)"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["mlag"]
    nodes: list[str]    # 複数形: 必ず 2 ノード
    members: list[str]  # インターフェース ID リスト（両ノード分）
    lacp: LacpConfig | None = None
    peer_link: str                  # 同一 lag リスト内の LacpLag.id を参照
    peer_link_interface: str        # 例: "peerlink.4094"
    domain_id: int | None = None

    @model_validator(mode="after")
    def exactly_two_nodes(self) -> "MlagLag":
        if len(self.nodes) != 2:
            raise ValueError("MLAG は正確に 2 ノードが必要です")
        return self


# Discriminated Union — type フィールドで分岐
Lag = Annotated[LacpLag | MlagLag, Field(discriminator="type")]


# ---------------------------------------------------------------------------
# L1Layer
# ---------------------------------------------------------------------------

class L1Layer(BaseModel):
    """Layer 1 全体（nodes / interfaces / links / lag）"""

    model_config = ConfigDict(extra="forbid")

    nodes: list[L1Node] = []
    interfaces: list[L1Interface] = []
    links: list[L1Link] = []
    lag: list[Lag] = []
