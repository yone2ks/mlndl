"""Layer 1 (物理トポロジー) スキーマ定義

設計決定:
- attaches_to: ADR-0001 — str | {node:} | {interface:} | {lag:} | {vlan:} | {subinterface:}
  ({link:} は ADR-0010 で削除。セッションの通り道は update_source から導く)
  参照先の種類はキーで示す (ADR-0001 D8)。どのキーを書けるかはエンティティごとに決まる
- role: ADR-0003 C2 — 自由文字列、コアは値域チェックなし
- implementation: ADR-0004 — vm | physical | container
- lag: ADR-0023 — 常に機器 1 台の LAG。複数の機器の LAG は ethernet_segments で束ねる
- labels: ADR-0009 — 多軸分類の注釈側構成子。コアは値域・キー域チェックなし
- description: ADR-0011 D7 — 全エンティティに任意の自由記述
- id 命名規則: ADR-0002 — ^[a-z][a-z0-9]*(-[a-z0-9]+)*$（推奨、強制なし）
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .refs import Ref


# ---------------------------------------------------------------------------
# attaches_to (ADR-0001)
# ---------------------------------------------------------------------------

ATTACH_KEYS = ("node", "interface", "lag", "vlan", "subinterface")


class AttachesToObj(BaseModel):
    """attaches_to のオブジェクト形式。ATTACH_KEYS のいずれか 1 キーだけを書く。

    キー名が参照先の種類を示す (ADR-0001 D2・D8):
      node → layer1.nodes / interface → layer1.interfaces (L1 IF のみ) / lag → layer1.lag /
      vlan → layer2.vlans / subinterface → layer2.subinterfaces
    """

    model_config = ConfigDict(extra="forbid")

    node: str | None = None
    interface: str | None = None
    lag: str | None = None
    vlan: str | None = None
    subinterface: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_link(cls, data: Any) -> Any:
        """{link:} は ADR-0010 で削除した。移動先を示すエラーを返す。{ethernet_segment:} は書けない理由を示す"""
        if isinstance(data, dict) and "link" in data:
            raise ValueError(
                "attaches_to の {link:} は廃止しました。セッションの通り道は update_source の L3 IF から導きます (ADR-0010 D7)"
            )
        if isinstance(data, dict) and "ethernet_segment" in data:
            raise ValueError(
                "attaches_to に {ethernet_segment:} は書けません。L3 IF とサブ IF は機器ごとに IP や設定が違うので、"
                "機器ごとの LAG を {lag: <LAG の id>} で指します (ADR-0023 D5)"
            )
        return data

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

# L1 ノード・L1 IF が書けるキー (ADR-0001 D8。{link:} は ADR-0010 で削除)
L1_ATTACH_KEYS = frozenset({"node", "interface"})


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
    # overrides は ADR-0024 でなくした。下流のツールの値は下流のツールの設定で機器の id を引いて持つ
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_overrides(cls, data: Any) -> Any:
        """overrides は ADR-0024 でなくした。理由と移動先を示すエラーを返す"""
        if isinstance(data, dict) and "overrides" in data:
            raise ValueError(
                "layer1.nodes の overrides はなくしました。機器ごとの CPU・RAM・イメージなどは、"
                "下流のツール (eve-lab-builder など) の設定で機器の id を引いて書きます。"
                "人が読む補足は description に書きます (ADR-0024)"
            )
        return data

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
    node: Annotated[str, Ref("layer1.nodes")]  # 所属ノード ID
    name: str | None = None
    attaches_to: AttachesTo | None = None
    description: str | None = None

    @field_validator("attaches_to")
    @classmethod
    def l1_attach_keys(cls, v: Any) -> Any:
        return restrict_attach_keys(v, L1_ATTACH_KEYS, "layer1.interfaces")


# ---------------------------------------------------------------------------
# link_speed の書式 (ADR-0021)
# ---------------------------------------------------------------------------

LINK_SPEED_PATTERN = r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?[KMGT]$"
_LINK_SPEED = re.compile(r"^(?P<num>0|[1-9][0-9]*(?:\.[0-9]+)?|0\.[0-9]+)(?P<unit>[KMGT])$")
# 直し方を示すために、よくある書き違い (小文字・bps・空白・数値の形) をゆるく読む
_LINK_SPEED_LOOSE = re.compile(
    r"^\s*(?P<num>[0-9]*\.?[0-9]*)\s*(?P<unit>[kmgtKMGT])\s*(?P<suffix>bps|b/s|bit/s|b|bE|Bps|B/s|B|byte|bytes)?\s*$"
)
_LINK_SPEED_UNITS = ("K", "M", "G", "T")      # 小さい順
_LINK_SPEED_SCALE = {u: Decimal(1000) ** (i + 1) for i, u in enumerate(_LINK_SPEED_UNITS)}


def link_speed_bps(value: str) -> Decimal:
    """書式に合う link_speed をビット毎秒に直す (10 進。1K = 1000 bps)"""
    m = _LINK_SPEED.match(value)
    if m is None:
        raise ValueError(f"link_speed の書式ではありません: '{value}'")
    return Decimal(m.group("num")) * _LINK_SPEED_SCALE[m.group("unit")]


def canonical_link_speed(value: str) -> str:
    """正規形: 数値が 1 以上 1000 未満になる単位で書き、余分な 0 を付けない (ADR-0021 D3)。
    K より下・T より上へはずらさない"""
    bps = link_speed_bps(value)
    unit = _LINK_SPEED_UNITS[0] if bps < _LINK_SPEED_SCALE["K"] else _LINK_SPEED_UNITS[-1]
    for u in _LINK_SPEED_UNITS:
        if 1 <= bps / _LINK_SPEED_SCALE[u] < 1000:
            unit = u
            break
    text = format(bps / _LINK_SPEED_SCALE[unit], "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text + unit


def _link_speed_error(value: Any) -> str:
    """書式に合わない link_speed に、直し方を添えたメッセージを返す (ADR-0021 D2)"""
    form = "<数値><K|M|G|T> の形で書きます (例: 100M / 10G / 1.6T)"
    text = str(value).strip()
    if isinstance(value, (int, float)) or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text):
        return (f"link_speed '{text}' には単位が要ります。単位 (K / M / G / T) を付けて書きます (例: 10G)。"
                f"Mbps か Kbps かが分からないので、値は推測しません (ADR-0021)")
    m = _LINK_SPEED_LOOSE.match(text)
    if m:
        suffix = m.group("suffix") or ""
        if suffix in ("Bps", "B/s", "B", "byte", "bytes"):
            return (f"link_speed '{value}' の B はバイトです。link_speed はビット毎秒で、"
                    f"単位は K / M / G / T だけを書きます (ADR-0021)")
        num = m.group("num").rstrip(".")
        if num.startswith("."):
            num = "0" + num
        if "." not in num:
            num = num.lstrip("0") or "0"
        else:
            whole, frac = num.split(".", 1)
            num = (whole.lstrip("0") or "0") + "." + frac
        fixed = num + m.group("unit").upper()
        if _LINK_SPEED.match(fixed) and Decimal(num) > 0:
            reasons = []
            if m.group("unit").islower():
                reasons.append("単位は大文字")
            if suffix:
                reasons.append("bps などは付けない")
            if " " in text:
                reasons.append("空白を入れない")
            if num != m.group("num"):
                reasons.append("数値は 0.5 / 10 / 1 のように書く")
            return f"link_speed '{value}' は '{fixed}' と書きます ({'。'.join(reasons)}。ADR-0021)"
    return f"link_speed '{value}' は 0 より大きい {form} (ADR-0021)"


def check_link_speed(value: Any) -> Any:
    """link_speed の書式を検査する (ADR-0021 D1・D2)。値は書き換えない"""
    if value is None:
        return value
    if isinstance(value, str) and _LINK_SPEED.match(value) and link_speed_bps(value) > 0:
        return value
    raise ValueError(_link_speed_error(value))


# ---------------------------------------------------------------------------
# L1Link
# ---------------------------------------------------------------------------

class L1Link(BaseModel):
    """Layer 1 物理リンク（ケーブル）

    ADR-0006: 物理リンクは無向。endpoints は順序非依存の 2 要素リスト。
    ADR-0020: MTU はインターフェースの設定なので、リンクには書かない (mtu はなくした)。
    ADR-0021: link_speed は <数値><K|M|G|T> (10 進のビット毎秒)。
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    endpoints: Annotated[list[str], Ref("layer1.interfaces")] = Field(min_length=2, max_length=2)
    link_speed: str | None = Field(default=None, pattern=LINK_SPEED_PATTERN)   # 例: "10G", "2.5G", "1.6T"
    link_role: str | None = None    # 自由文字列。推奨: underlay / access / trunk / peer-link / management / uplink
    description: str | None = None

    @field_validator("link_speed", mode="before")
    @classmethod
    def link_speed_format(cls, v: Any) -> Any:
        return check_link_speed(v)

    @model_validator(mode="before")
    @classmethod
    def reject_mtu(cls, data: Any) -> Any:
        """mtu は ADR-0020 でなくした。なくした理由を示すエラーを返す"""
        if isinstance(data, dict) and "mtu" in data:
            raise ValueError(
                "layer1.links の mtu はなくしました。MTU はインターフェースの設定で、"
                "リンク (ケーブル) の性質ではないためです (ADR-0020)"
            )
        return data

    @model_validator(mode="after")
    def endpoints_distinct(self) -> "L1Link":
        if self.endpoints[0] == self.endpoints[1]:
            raise ValueError("endpoints の両端に同一インターフェースを指定できません（self-loop）")
        return self


# ---------------------------------------------------------------------------
# LAG — 機器 1 台の上の port-channel / bond / ae (ADR-0023)
# ---------------------------------------------------------------------------

class LacpConfig(BaseModel):
    """LACP パラメータ"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["active", "passive", "on"] = "active"
    min_links: int = 1


# 複数の機器にまたがる LAG (旧 type: mlag) だけが持っていたキー。どれも書かない (ADR-0022 / ADR-0023)
_MULTI_CHASSIS_KEYS = ("nodes", "peer_link", "peer_link_interface", "domain_id", "system_mac", "client_lag")


class Lag(BaseModel):
    """機器 1 台の LAG (ADR-0023 D1)

    MLAG / vPC / MC-LAG / ESI-LAG でも、実機の LAG IF は機器ごとにある。それを 1 台ずつ書き、
    複数の機器の LAG を相手から 1 本に見せる関係は layer1.ethernet_segments で束ねる。
    スタック / VSS / Virtual Chassis は 1 台の論理機器なので、筐体をまたぐ LAG もここに 1 つ書く。
    """

    model_config = ConfigDict(extra="forbid")

    id: str                                             # 推奨プレフィックス lag- (ADR-0002 D7)
    node: Annotated[str, Ref("layer1.nodes")]
    name: str | None = None                             # 機器上の名前 (Port-Channel10 / bond0 / ae0)
    members: Annotated[list[str], Ref("layer1.interfaces")]
    lacp: LacpConfig | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_old_forms(cls, data: Any) -> Any:
        """旧形式の type: lacp / type: mlag と、MLAG だけが持っていたキーに、移動先を示すエラーを返す"""
        if not isinstance(data, dict):
            return data
        old = [k for k in _MULTI_CHASSIS_KEYS if k in data]
        if data.get("type") == "mlag" or old:
            raise ValueError(
                "複数の機器にまたがる LAG (MLAG / vPC / MC-LAG / ESI-LAG) は、機器ごとの LAG を layer1.lag に 1 つずつ"
                "書き (node は 1 つ)、それらを layer1.ethernet_segments の members で束ねます。"
                + (f"{' / '.join(old)} は書きません。" if old else "")
                + "ピアリンクは 2 台をつなぐ普通の LAG として書き、ドメインの番号や MAC は構成図に書きません"
                " (ADR-0022 / ADR-0023)"
            )
        if "type" in data:
            raise ValueError(
                "layer1.lag の type はなくしました。LAG は常に機器 1 台の LAG なので、type を消してください (ADR-0023 D1)"
            )
        return data


# ---------------------------------------------------------------------------
# Ethernet Segment — 複数の機器の脚を相手から 1 本に見せる関係 (ADR-0023)
# ---------------------------------------------------------------------------

class SegmentMember(BaseModel):
    """Ethernet Segment の脚。{lag: <LAG の id>} か {interface: <L1 IF の id>} のどちらか一方 (ADR-0023 D3)

    脚が LAG でない構成 (single-active で物理 IF に直接 ESI を設定する) は {interface:} で書く
    """

    model_config = ConfigDict(extra="forbid")

    interface: str | None = None
    lag: str | None = None

    @model_validator(mode="after")
    def exactly_one_target(self) -> "SegmentMember":
        if (self.interface is None) == (self.lag is None):
            raise ValueError(
                "Ethernet Segment の脚は lag (LAG) か interface (L1 IF) のどちらか一方で指してください (ADR-0023 D3)"
            )
        return self

    @property
    def kind(self) -> str:
        """書かれたキー名 (interface / lag)"""
        return "interface" if self.interface is not None else "lag"

    @property
    def target(self) -> str:
        """参照先の ID"""
        return self.interface if self.interface is not None else self.lag


class EthernetSegment(BaseModel):
    """複数の機器の脚 (LAG か L1 IF) を、相手 (ホスト / CE) から 1 本に見せる関係 (ADR-0023 D2)

    RFC 7432 の Ethernet Segment。MLAG / vPC / MC-LAG / EVPN multihoming をこの 1 つの形で書き、方式名は書かない。
    - members: 脚。2 つ以上で、機器はすべて別
    - redundancy_mode: all_active (脚がそろって転送する) / single_active (同時に転送するのは 1 本)。
      既定値はなく、書かなければ「書いていない」(ADR-0023 D4)。どの脚が転送するか (DF) は書かない
    - ESI の値・LACP system-id・domain_id・vPC 番号 / clag-id・ピアリンクは書かない (ADR-0022)
    """

    model_config = ConfigDict(extra="forbid")

    id: str                                             # 推奨プレフィックス es- (ADR-0002 D7)
    name: str | None = None
    members: list[SegmentMember]
    redundancy_mode: Literal["all_active", "single_active"] | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_granularity(cls, data: Any) -> Any:
        """構成図の粒度に合わない値に、書かない理由を示すエラーを返す (ADR-0022)"""
        if isinstance(data, dict):
            old = [k for k in ("esi", "system_mac", "domain_id", "peer_link", "peer_links") if k in data]
            if old:
                raise ValueError(
                    f"ethernet_segments に {' / '.join(old)} は書きません。ESI の値・MAC・ドメインの番号は装置の設定の"
                    f"粒度で、ピアリンクは 2 台をつなぐ普通の LAG として書きます (ADR-0022 / ADR-0023)"
                )
        return data

    @field_validator("members")
    @classmethod
    def at_least_two(cls, v: list[SegmentMember]) -> list[SegmentMember]:
        if len(v) < 2:
            raise ValueError(
                "ethernet_segments の members は 2 つ以上書きます。1 台の機器だけの LAG は layer1.lag に書けば足ります"
                " (ADR-0023 D2)"
            )
        return v


# ---------------------------------------------------------------------------
# L1Layer
# ---------------------------------------------------------------------------

class L1Layer(BaseModel):
    """Layer 1 全体（nodes / interfaces / links / lag / ethernet_segments）"""

    model_config = ConfigDict(extra="forbid")

    nodes: list[L1Node] = []
    interfaces: list[L1Interface] = []
    links: list[L1Link] = []
    lag: list[Lag] = []
    ethernet_segments: list[EthernetSegment] = []
