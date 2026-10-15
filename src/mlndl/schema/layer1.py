"""Layer 1 (物理トポロジー) スキーマ定義

設計決定:
- attaches_to: ADR-0001 — str | {node:} | {interface:} | {lag:} | {vlan:} | {subinterface:} | {link:}
  参照先の種類はキーで示す (ADR-0001 D8)。どのキーを書けるかはエンティティごとに決まる
- role: ADR-0003 C2 — 自由文字列、コアは値域チェックなし
- implementation: ADR-0004 — vm | physical | container
- lag: §6 設計決定 — type: lacp | mlag の Discriminated Union
- labels: ADR-0009 — 多軸分類の注釈側構成子。コアは値域・キー域チェックなし
- description: ADR-0011 D7 — 全エンティティに任意の自由記述
- id 命名規則: ADR-0002 — ^[a-z][a-z0-9]*(-[a-z0-9]+)*$（推奨、強制なし）
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# attaches_to (ADR-0001)
# ---------------------------------------------------------------------------

ATTACH_KEYS = ("node", "interface", "lag", "vlan", "subinterface", "link")


class AttachesToObj(BaseModel):
    """attaches_to のオブジェクト形式。ATTACH_KEYS のいずれか 1 キーだけを書く。

    キー名が参照先の種類を示す (ADR-0001 D2・D8):
      node → layer1.nodes / interface → layer1.interfaces (L1 IF のみ) / lag → layer1.lag /
      vlan → layer2.vlans / subinterface → layer2.subinterfaces / link → layer1.links
    """

    model_config = ConfigDict(extra="forbid")

    node: str | None = None
    interface: str | None = None
    lag: str | None = None
    vlan: str | None = None
    subinterface: str | None = None
    link: str | None = None

    @model_validator(mode="after")
    def exactly_one_key(self) -> "AttachesToObj":
        if sum(1 for k in ATTACH_KEYS if getattr(self, k) is not None) != 1:
            raise ValueError(
                "attaches_to オブジェクトは " + " / ".join(ATTACH_KEYS) + " のいずれか 1 キーだけを指定してください"
            )
        return self

    @property
    def kind(self) -> str:
        """書かれたキー名 (参照先の種類)"""
        return next(k for k in ATTACH_KEYS if getattr(self, k) is not None)

    @property
    def target(self) -> str:
        """参照先の ID"""
        return getattr(self, self.kind)


# 文字列形式（ノードID 糖衣構文）とオブジェクト形式の Union
AttachesTo = str | AttachesToObj

# ADR-0001 D1〜D7 で定めた従来のキー。L1 と routing_adjacencies はこれだけを書ける
L1_ATTACH_KEYS = frozenset({"node", "interface", "link"})


def restrict_attach_keys(value: Any, allowed: frozenset[str], owner: str) -> Any:
    """エンティティごとに書ける attaches_to のキーを制限する (ADR-0001 D8)"""
    if isinstance(value, AttachesToObj) and value.kind not in allowed:
        keys = " / ".join(f"{{{k}:}}" for k in ATTACH_KEYS if k in allowed)
        raise ValueError(
            f"{owner} の attaches_to に {{{value.kind}:}} は書けません。書けるのは {keys} です (ADR-0001 D8)"
        )
    return value


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
    # ADR-0009: 多軸分類。任意の key-value。コアは値域・キー域を検証しない。
    # 推奨軸名: docs/label-vocabulary.md（informative）
    labels: dict[str, str] | None = None
    overrides: dict[str, Any] | None = None  # 上位ツール向け任意上書き
    description: str | None = None

    @field_validator("attaches_to")
    @classmethod
    def l1_attach_keys(cls, v: Any) -> Any:
        return restrict_attach_keys(v, L1_ATTACH_KEYS, "layer1.nodes")

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
    description: str | None = None

    @field_validator("attaches_to")
    @classmethod
    def l1_attach_keys(cls, v: Any) -> Any:
        return restrict_attach_keys(v, L1_ATTACH_KEYS, "layer1.interfaces")


# ---------------------------------------------------------------------------
# L1Link
# ---------------------------------------------------------------------------

class L1Link(BaseModel):
    """Layer 1 物理リンク（ケーブル）

    ADR-0006: 物理リンクは無向。endpoints は順序非依存の 2 要素リスト。
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    endpoints: list[str] = Field(min_length=2, max_length=2)
    link_speed: str | None = None   # 例: "10G", "100G"
    mtu: int | None = None
    link_role: str | None = None    # 自由文字列。推奨: underlay / access / trunk / peer-link / management / uplink
    description: str | None = None

    @model_validator(mode="after")
    def endpoints_distinct(self) -> "L1Link":
        if self.endpoints[0] == self.endpoints[1]:
            raise ValueError("endpoints の両端に同一インターフェースを指定できません（self-loop）")
        return self


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
    description: str | None = None


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
    system_mac: str | None = None   # 両ノード共通の MLAG system MAC（例: "44:38:39:ff:00:0a"）
    client_lag: str | None = None   # 対向ノード側の LacpLag.id（単方向参照）
    description: str | None = None

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
