"""ADR-0015 参照の宣言 (Ref) と id の索引 (resolve) のテスト"""

from __future__ import annotations

import inspect
import types
import typing

import pytest
from pydantic import BaseModel

import mlndl.schema.layer1 as layer1
import mlndl.schema.layer2 as layer2
import mlndl.schema.layer3 as layer3
import mlndl.schema.control_plane as control_plane
import mlndl.schema.topology as topology_mod
from mlndl import IdIndex, Ref, parse, parse_file, validate
from mlndl.index import SECTIONS
from mlndl.schema.refs import COLLECTION_LABELS

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

SCHEMA_MODULES = (layer1, layer2, layer3, control_plane, topology_mod)

# 参照ではない文字列フィールド。新しい文字列フィールドを足したら、参照なら Ref を付け、
# 参照でなければここに足す (どちらもしないと test_every_string_field_is_classified が落ちる)
NOT_REFERENCES = {
    "id", "name", "description", "role", "device_type", "rd", "link_speed", "link_role",
    "peer_link_interface", "system_mac", "anycast_mac", "import_", "export",
    "address_families", "network_types", "ndl_version",
    "net", "area", "level",          # 制御プレーン (ADR-0010): IS-IS の NET、OSPF の area、IS-IS の level
}

# 参照先の種類をキーで選ぶ参照 (ADR-0001 D8 / ADR-0013 D1)。_resolve_ref が検査する
KEYED_REFERENCES = {
    ("AttachesToObj", name) for name in ("node", "interface", "lag", "vlan", "subinterface")
} | {(model, key) for model in ("PortTarget", "PortRef", "BridgePort") for key in ("interface", "lag")} | {
    # attaches_to は文字列 (ノード id の糖衣構文) か AttachesToObj。_check_attaches_to が検査する
    # (セッションは attaches_to を持たない。ADR-0010 D7)
    (model, "attaches_to") for model in ("L1Node", "L1Interface")
}


def _schema_models() -> list[type[BaseModel]]:
    models = []
    for module in SCHEMA_MODULES:
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseModel) and obj.__module__ == module.__name__:
                models.append(obj)
    return models


def _is_string_field(annotation) -> bool:
    """str / str | None / list[str] / list[str] | None"""
    if annotation is str:
        return True
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return any(_is_string_field(a) for a in typing.get_args(annotation) if a is not type(None))
    if origin is list:
        return typing.get_args(annotation) == (str,)
    return False


def _refs():
    for model in _schema_models():
        for name, info in model.model_fields.items():
            for meta in info.metadata:
                if isinstance(meta, Ref):
                    yield model, name, meta


# ---------------------------------------------------------------------------
# 宣言の網羅
# ---------------------------------------------------------------------------

def test_every_string_field_is_classified():
    """文字列フィールドは、Ref・キーで選ぶ参照・参照ではない値のどれかに分類されていること"""
    unclassified = []
    for model in _schema_models():
        for name, info in model.model_fields.items():
            if not _is_string_field(info.annotation):
                continue
            has_ref = any(isinstance(m, Ref) for m in info.metadata)
            if has_ref or name in NOT_REFERENCES or (model.__name__, name) in KEYED_REFERENCES:
                continue
            unclassified.append(f"{model.__name__}.{name}")
    assert unclassified == [], (
        "参照なら Annotated[..., Ref(\"<パス>\")] を付け、参照でなければ NOT_REFERENCES に足してください: "
        + ", ".join(unclassified)
    )


def test_ref_paths_exist_in_schema():
    """Ref のパスは、スキーマにある id 付きのコレクションを指していること"""
    sections = {name: topology_mod.MLNDLTopology.model_fields[name].annotation for name in SECTIONS}
    for model, field, ref in _refs():
        for path in ref.paths:
            section, collection = path.split(".")
            section_type = typing.get_args(sections[section])[0]          # L1Layer | None → L1Layer
            assert collection in section_type.model_fields, f"{model.__name__}.{field}: {path}"


def test_ref_paths_have_labels():
    """エラーメッセージで使う呼び名が登録されていること"""
    for model, field, ref in _refs():
        for path in ref.paths:
            assert path in COLLECTION_LABELS, f"{model.__name__}.{field}: {path} の呼び名がありません"


def test_no_reference_is_left_in_comments():
    """参照先をコメントだけに書いたフィールドが残っていないこと (「を参照」のコメント)"""
    leftovers = []
    for module in SCHEMA_MODULES:
        for lineno, line in enumerate(inspect.getsource(module).splitlines(), 1):
            if "].id を参照" in line:
                leftovers.append(f"{module.__name__}:{lineno}")
    assert leftovers == []


# ---------------------------------------------------------------------------
# 検査とメッセージ
# ---------------------------------------------------------------------------

BASE = """ndl_version: "1.0"
layer1:
  nodes: [{id: r1}, {id: r2}]
  interfaces: [{id: r1-eth0, node: r1}, {id: r2-eth0, node: r2}]
layer2:
  vlans: [{id: vlan-100, vlan_id: 100}]
  vxlan:
    - {id: vni-10100, type: l2vni, vni: 10100, vlan: vlan-100, vteps: [vtep-r1]}
  vteps: [{id: vtep-r1, sources: [r1-lo]}]
layer3:
  vrfs: [{id: vrf-a}]
  interfaces: [{id: r1-lo, node: r1, name: lo, ip: 10.0.0.1/32}]
"""


def _errors(body: str):
    return validate(parse(body))


def test_base_is_valid():
    assert _errors(BASE) == []


def test_undefined_reference_message():
    errs = _errors(BASE.replace("interfaces: [{id: r1-eth0, node: r1}", "interfaces: [{id: r1-eth0, node: nope}"))
    assert [(e.path, e.message) for e in errs] == [
        ("layer1.interfaces[0].node", "未定義のノード 'nope' を参照しています"),
    ]


def test_hint_when_id_exists_in_another_collection():
    """別の種類のコレクションにある id を指したら、何であるかを添える"""
    errs = _errors(BASE.replace("vlan: vlan-100, vteps", "vlan: vrf-a, vteps"))
    assert [e.message for e in errs] == ["未定義の VLAN 'vrf-a' を参照しています。'vrf-a' は VRF です"]


def test_where_filter():
    """VRF の l3vni は type: l3vni の VNI だけを指せる"""
    errs = _errors(BASE.replace("vrfs: [{id: vrf-a}]", "vrfs: [{id: vrf-a, l3vni: vni-10100}]"))
    assert [(e.path, e.message) for e in errs] == [
        ("layer3.vrfs[0].l3vni", "未定義の L3VNI 'vni-10100' を参照しています。'vni-10100' は type: l3vni ではありません"),
    ]


def test_list_reference_path_has_index():
    errs = _errors(BASE.replace("vteps: [vtep-r1]}", "vteps: [vtep-r1, nope]}"))
    assert [e.path for e in errs] == ["layer2.vxlan[0].vteps[1]"]


def test_alias_is_used_in_path():
    """from は Python の予約語なので from_ だが、パスは YAML どおり from"""
    body = BASE + ("control_plane:\n  bgp: [{id: bgp-default, nodes: [{node: r1, local_as: 65001}]}]\n"
                   "  routing_neighbors:\n    - {id: bgp-peer-a, type: bgp, from: {node: nope, update_source: r1-lo},"
                   " to: {address: 192.0.2.1, local_as: 65002}}\n")
    assert [e.path for e in _errors(body)][0] == "control_plane.routing_neighbors[0].from.node"


# ---------------------------------------------------------------------------
# 索引と resolve
# ---------------------------------------------------------------------------

def test_resolve():
    t = parse_file(FIXTURES / "valid_full_dc.yaml")
    vtep = t.resolve("vtep-leaf1-leaf2")
    assert type(vtep).__name__ == "Vtep" and vtep.sources == ["leaf1-lo", "leaf2-lo"]
    assert t.resolve("leaf1").id == "leaf1"
    assert t.resolve("nope") is None


def test_resolve_with_path():
    t = parse_file(FIXTURES / "valid_full_dc.yaml")
    assert t.resolve("vni-10100", "layer2.vxlan").vni == 10100
    assert t.resolve("vni-10100", "layer2.vlans") is None


def test_resolve_ambiguous_id_needs_path():
    """ノードと L1 IF に同じ id があると、どちらを返すか決められない"""
    t = parse(BASE.replace("{id: r2-eth0, node: r2}", "{id: r2, node: r2}"))
    with pytest.raises(LookupError, match="path を指定"):
        t.resolve("r2")
    assert t.resolve("r2", "layer1.interfaces").node == "r2"


def test_index_ids_with_where():
    t = parse_file(FIXTURES / "valid_full_dc.yaml")
    index = t.index()
    assert isinstance(index, IdIndex)
    assert index.ids("layer2.vxlan", ("type", "l3vni")) == {"vni-10900"}
    assert "layer2.vteps" in index.paths()


def test_new_syntax_gets_reference_check_from_ref_alone():
    """構文を足すとき、Ref を書くだけで参照の検査が付く (validator に手を入れない)"""
    from typing import Annotated

    from mlndl.validator import _walk_refs

    class PeerKeepalive(BaseModel):        # 例: 将来の MLAG の peer-keepalive
        source: Annotated[str, Ref("layer3.interfaces")]

    errors: list = []
    _walk_refs(PeerKeepalive(source="nope"), "layer1.lag[0].peer_keepalive", parse(BASE).index(), errors)
    assert [(e.path, e.message) for e in errors] == [
        ("layer1.lag[0].peer_keepalive.source", "未定義の L3 インターフェース 'nope' を参照しています"),
    ]
