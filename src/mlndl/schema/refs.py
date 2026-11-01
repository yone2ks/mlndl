"""参照の宣言 (ADR-0015)

フィールドが別のエンティティの id を指すことを、型に書く。

    vlan: Annotated[str, Ref("layer2.vlans")]
    vteps: Annotated[list[str], Ref("layer2.vteps")] = []
    l3vni: Annotated[str | None, Ref("layer2.vxlan", where=("type", "l3vni"))] = None

validator は Ref の付いたフィールドをスキーマから見つけ、指している id が実在するかを検査する。
構文を足すときは Ref を書けば参照の検査が付き、validator に検査を書き足す必要はない。

Ref は「参照先が 1 つに決まっている参照」に使う。参照先の種類をキーで選ぶ参照
(attaches_to、VLAN のポートの interface / lag。ADR-0001 D8) は、キーごとに参照先を引く別の仕組みで検査する。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ref:
    """このフィールドの値 (またはリストの各要素) は、path のコレクションにある id である

    path:  YAML の構造どおりのパス。例 "layer2.vlans"
    where: (フィールド名, 値)。コレクションのうち、その値を持つものだけを参照先にする。
           例 ("type", "l3vni") は L3VNI だけ
    """

    path: str
    where: tuple[str, str] | None = None

    @property
    def label(self) -> str:
        """エラーメッセージで使う参照先の呼び名"""
        if self.where == ("type", "l3vni"):
            return "L3VNI"
        return COLLECTION_LABELS.get(self.path, self.path)


# 参照先になるコレクションの呼び名。新しいコレクションを Ref で指すときはここに足す
# (足し忘れるとパスがそのまま表示される。tests/test_refs.py が足し忘れを検出する)
COLLECTION_LABELS = {
    "layer1.nodes": "ノード",
    "layer1.interfaces": "L1 インターフェース",
    "layer1.links": "リンク",
    "layer1.lag": "LAG",
    "layer2.vlans": "VLAN",
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
