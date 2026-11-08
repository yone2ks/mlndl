"""参照の宣言 (ADR-0015)

フィールドが別のエンティティの id を指すことを、型に書く。

    vlan: Annotated[str, Ref("layer2.vlans")]
    vteps: Annotated[list[str], Ref("layer2.vteps")] = []
    l3vni: Annotated[str | None, Ref("layer2.vxlan", where=("type", "l3vni"))] = None
    update_source: Annotated[str, Ref("layer3.interfaces", "layer3.tunnel_interfaces")]   # 複数のコレクション

validator は Ref の付いたフィールドをスキーマから見つけ、指している id が実在するかを検査する。
構文を足すときは Ref を書けば参照の検査が付き、validator に検査を書き足す必要はない。

Ref は「参照先が 1 つに決まっている参照」に使う。参照先の種類をキーで選ぶ参照
(attaches_to、VLAN のポートの interface / lag / ethernet_segment、Ethernet Segment の脚。ADR-0001 D8) は、キーごとに参照先を引く別の仕組みで検査する。
複数のコレクションを並べた Ref は、id から種類が決まる参照 (ADR-0002 D5 で id はグローバルに一意) に使う。
参照先の種類で意味が変わらない参照だけで、キーは要らない (ADR-0018 D3)。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, init=False)
class Ref:
    """このフィールドの値 (またはリストの各要素) は、paths のどれかのコレクションにある id である

    paths: YAML の構造どおりのパス。例 "layer2.vlans"。複数並べると、それらの id の和集合を参照先にする
    where: (フィールド名, 値)。コレクションのうち、その値を持つものだけを参照先にする。
           例 ("type", "l3vni") は L3VNI だけ。パスが 1 つのときだけ使う
    """

    paths: tuple[str, ...]
    where: tuple[str, str] | None

    def __init__(self, *paths: str, where: tuple[str, str] | None = None) -> None:
        if not paths:
            raise ValueError("Ref には参照先のパスを 1 つ以上書いてください")
        if where is not None and len(paths) > 1:
            raise ValueError("where はパスが 1 つの Ref にだけ書けます")
        object.__setattr__(self, "paths", paths)
        object.__setattr__(self, "where", where)

    @property
    def label(self) -> str:
        """エラーメッセージで使う参照先の呼び名。複数のパスなら「L3 インターフェース / トンネル」と連結する"""
        if self.where == ("type", "l3vni"):
            return "L3VNI"
        return " / ".join(COLLECTION_LABELS.get(p, p) for p in self.paths)


# 参照先になるコレクションの呼び名。新しいコレクションを Ref で指すときはここに足す
# (足し忘れるとパスがそのまま表示される。tests/test_refs.py が足し忘れを検出する)
COLLECTION_LABELS = {
    "layer1.nodes": "ノード",
    "layer1.interfaces": "L1 インターフェース",
    "layer1.links": "リンク",
    "layer1.lag": "LAG",
    "layer1.ethernet_segments": "Ethernet Segment",
    "layer2.vlans": "VLAN",
    "layer2.bridges": "bridge",
    "layer2.vteps": "VTEP",
    "layer2.vxlan": "VNI",
    "layer2.subinterfaces": "サブインターフェース",
    "layer3.vrfs": "VRF",
    "layer3.interfaces": "L3 インターフェース",
    "layer3.tunnel_interfaces": "トンネル",
    "control_plane.bgp": "BGP インスタンス",
    "control_plane.ospf": "OSPF インスタンス",
    "control_plane.isis": "IS-IS インスタンス",
    "control_plane.routing_neighbors": "セッション",
}
