"""ADR-0002 D1 ID 文法チェックのテスト"""

from __future__ import annotations

import pytest

from mlndl import parse, validate, validate_all
from mlndl.schema.layer1 import L1Layer
from mlndl.schema.layer2 import L2Layer
from mlndl.schema.layer3 import L3Layer
from mlndl.schema.protocols import Protocols


def _grammar_errors(body: str) -> list:
    errs = validate(parse('ndl_version: "1.0"\n' + body))
    return [e for e in errs if "ADR-0002 D1" in e.message]


def _node(node_id: str) -> str:
    return f"layer1:\n  nodes: [{{id: {node_id}}}]\n"


# ---------------------------------------------------------------------------
# 文法そのもの
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", ["r1", "leaf1", "a", "spine-1-a", "x" * 63])
def test_valid_ids(node_id):
    assert _grammar_errors(_node(node_id)) == []


@pytest.mark.parametrize("node_id,reason", [
    ("Leaf1", "大文字"),
    ("leaf_1", "アンダースコア"),
    ("leaf1-", "ハイフン"),
    ("leaf--1", "ハイフン"),
    ("1leaf", "先頭"),
    ("-leaf", "先頭"),
    ("leaf.1", "'.'"),
    ("eth0/1", "'/'"),
    ("leaf１", "'１'"),        # 全角数字は isalnum だが ASCII ではない
    ("x" * 64, "63 文字"),
])
def test_invalid_ids(node_id, reason):
    errs = _grammar_errors(f"layer1:\n  nodes: [{{id: '{node_id}'}}]\n")
    assert [e.path for e in errs] == ["layer1.nodes[0].id"]
    assert reason in errs[0].message
    assert errs[0].severity == "error"


def test_all_reasons_are_reported():
    """理由は 1 つに絞らず全部出す。1 回の修正で直せるように"""
    msg = _grammar_errors(_node("Leaf_1."))[0].message
    assert "大文字" in msg and "アンダースコア" in msg and "'.'" in msg


def test_is_error_even_without_strict():
    """文法は規約 (D7, warning) ではなく仕様 (D1, must)"""
    r = validate_all(parse('ndl_version: "1.0"\n' + _node("Leaf1")))
    assert any("ADR-0002 D1" in e.message for e in r.errors)
    assert not any("ADR-0002 D1" in w.message for w in r.warnings)


def test_labels_key_stays_warning():
    """labels のキーは ID ではないので、従来どおり warning (ADR-0009 D3)"""
    r = validate_all(parse('ndl_version: "1.0"\nlayer1:\n  nodes: [{id: r1, labels: {Rack_A: x}}]\n'))
    assert r.errors == []
    assert [w.path for w in r.warnings] == ["layer1.nodes[0].labels.Rack_A"]


# ---------------------------------------------------------------------------
# すべてのエンティティが対象になっているか
# ---------------------------------------------------------------------------

# 各リストに 1 つずつ文法違反の ID を置いたトポロジー
ALL_SECTIONS = """
layer1:
  nodes: [{id: R1}, {id: r2}]
  interfaces:
    - {id: R1-eth0, node: R1}
    - {id: r2-eth0, node: r2}
  links:
    - {id: Link-r1-r2, endpoints: [R1-eth0, r2-eth0]}
  lag:
    - {id: Lag-r1, type: lacp, node: R1, members: [R1-eth0]}
layer2:
  vlans: [{id: Vlan-10, vlan_id: 10}]
  vxlan:
    - {id: Vni-10010, type: l2vni, vni: 10010, vlan: Vlan-10, vtep_source: R1-lo, members: [R1]}
  subinterfaces:
    - {id: Subif-r2-eth0-20, attaches_to: {interface: r2-eth0}, vlan_id: 20}
layer3:
  vrfs: [{id: Vrf-a}]
  interfaces:
    - {id: R1-lo, node: R1, name: lo, ip: 10.0.0.1/32}
    - {id: r2-lo, node: r2, name: lo, ip: 10.0.0.2/32}
  tunnel_interfaces:
    - {id: Tunnel-r1, node: R1, type: gre, source: R1-lo, destination_interface: r2-lo}
  routing_adjacencies:
    - {id: Bgp-peer-r1-r2, type: bgp, from: {node: R1}, to: {node: r2}}
protocols:
  bfd: [{id: Bfd-a, nodes: [R1]}]
  bgp: [{id: Bgp-a}]
"""

EXPECTED_PATHS = {
    "layer1.nodes[0].id",
    "layer1.interfaces[0].id",
    "layer1.links[0].id",
    "layer1.lag[0].id",
    "layer2.vlans[0].id",
    "layer2.vxlan[0].id",
    "layer2.subinterfaces[0].id",
    "layer3.vrfs[0].id",
    "layer3.interfaces[0].id",
    "layer3.tunnel_interfaces[0].id",
    "layer3.routing_adjacencies[0].id",
    "protocols.bfd[0].id",
    "protocols.bgp[0].id",
}


def test_every_entity_list_is_checked():
    assert {e.path for e in _grammar_errors(ALL_SECTIONS)} == EXPECTED_PATHS


def test_only_grammar_is_wrong_in_all_sections_fixture():
    """上のトポロジーは文法以外は正しい (参照エラーで検査が隠れていないことの確認)"""
    errs = validate(parse('ndl_version: "1.0"\n' + ALL_SECTIONS))
    assert [e for e in errs if "ADR-0002 D1" not in e.message] == []


def test_expected_paths_cover_schema():
    """スキーマにエンティティのリストを足したら、このテストのトポロジーにも足すこと"""
    schema_lists = {
        f"{section}.{name}"
        for section, model in [("layer1", L1Layer), ("layer2", L2Layer),
                               ("layer3", L3Layer), ("protocols", Protocols)]
        for name in model.model_fields
    }
    assert schema_lists == {p.removesuffix("[0].id") for p in EXPECTED_PATHS}
