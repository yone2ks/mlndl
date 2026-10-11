"""ADR-0013 VLAN の trunk_ports / access_ports から LAG を指すテスト"""

from __future__ import annotations

import pydantic
import pytest

from mlndl import parse, validate, validate_all
from mlndl.exporter import cytoscape, yaml as yaml_exporter


L1 = """
layer1:
  nodes: [{id: r1}, {id: r2}, {id: r3}, {id: srv1}]
  interfaces:
    - {id: r1-eth0, node: r1}
    - {id: r1-eth1, node: r1}
    - {id: r1-eth2, node: r1}
    - {id: r2-eth0, node: r2}
    - {id: r2-eth1, node: r2}
    - {id: r2-eth2, node: r2}
    - {id: r3-eth0, node: r3}
    - {id: r3-eth1, node: r3}
  lag:
    - {id: lag-r3-po1, type: lacp, node: r3, members: [r3-eth0, r3-eth1]}
    - {id: lag-peer, type: lacp, node: r1, members: [r1-eth2]}
    - id: lag-mlag-a
      type: mlag
      nodes: [r1, r2]
      members: [r1-eth0, r2-eth0]
      peer_link: lag-peer
      peer_link_interface: peerlink.4094
"""


def _topo(*vlans: str):
    return parse('ndl_version: "1.0"\n' + L1 + "layer2:\n  vlans:\n" + "".join(vlans))


def _vlan(trunk: str = "", access: str = "", vid: int = 100, vlan_id: str | None = None) -> str:
    s = f"    - id: {vlan_id or f'vlan-{vid}'}\n      vlan_id: {vid}\n"
    if trunk:
        s += f"      trunk_ports: [{trunk}]\n"
    if access:
        s += f"      access_ports: [{access}]\n"
    return s


def _errors(*vlans: str) -> list[str]:
    return [str(e) for e in validate(_topo(*vlans))]


# ---------------------------------------------------------------------------
# スキーマ
# ---------------------------------------------------------------------------

def test_node_is_optional():
    pr = _topo(_vlan(trunk="{interface: r1-eth1}")).layer2.vlans[0].trunk_ports[0]
    assert (pr.interface, pr.node) == ("r1-eth1", None)


def test_interface_is_required():
    with pytest.raises(pydantic.ValidationError):
        _topo(_vlan(trunk="{node: r1}"))


# ---------------------------------------------------------------------------
# 書けるもの
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trunk", [
    "{interface: lag-r3-po1}",                 # LACP, node なし
    "{node: r3, interface: lag-r3-po1}",       # LACP, node あり (照合される)
    "{interface: lag-mlag-a}",                 # MLAG は 1 エントリで両ノード
    "{interface: lag-peer}",                   # peer-link も書ける
    "{interface: r1-eth1}",                    # L1 IF も node を省略できる
    "{node: r1, interface: r1-eth1}",          # 従来の書き方
])
def test_valid_trunk(trunk):
    assert _errors(_vlan(trunk=trunk)) == []


def test_lag_in_access_ports():
    assert _errors(_vlan(access="{interface: lag-mlag-a}")) == []


def test_no_warning_for_lag_reference():
    r = validate_all(_topo(_vlan(trunk="{interface: lag-mlag-a}")))
    assert r.errors == [] and r.warnings == []


# ---------------------------------------------------------------------------
# error / warning
# ---------------------------------------------------------------------------

def test_mlag_with_node_is_error():
    """MLAG は両ノードに効く。node を書くと片方だけに見えるので書かせない"""
    errs = _errors(_vlan(trunk="{node: r1, interface: lag-mlag-a}"))
    assert len(errs) == 1 and "MLAG" in errs[0] and "node" in errs[0]


def test_lacp_on_other_node():
    errs = _errors(_vlan(trunk="{node: r1, interface: lag-r3-po1}"))
    assert len(errs) == 1 and "lag-r3-po1" in errs[0] and "r3" in errs[0]


def test_l1_interface_on_other_node():
    errs = _errors(_vlan(trunk="{node: r2, interface: r1-eth1}"))
    assert len(errs) == 1 and "ADR-0011 D9" in errs[0]


def test_undefined_node():
    errs = _errors(_vlan(trunk="{node: nope, interface: r1-eth1}"))
    assert any("nope" in e for e in errs)


@pytest.mark.parametrize("ref", ["nope", "vlan-100"])
def test_undefined_interface(ref):
    """VLAN やサブ IF は VLAN のポートにならない。指せるのは L1 IF と LAG だけ"""
    errs = _errors(_vlan(trunk=f"{{interface: {ref}}}"))
    assert any("L1 インターフェースまたは LAG" in e and ref in e for e in errs)


def test_lag_and_member_in_same_vlan_is_error():
    errs = _errors(_vlan(trunk="{interface: lag-r3-po1}, {interface: r3-eth0}"))
    assert len(errs) == 1 and "r3-eth0" in errs[0] and "lag-r3-po1" in errs[0]


def test_lag_in_trunk_and_member_in_access_is_error():
    errs = _errors(_vlan(trunk="{interface: lag-r3-po1}", access="{interface: r3-eth1}"))
    assert len(errs) == 1 and "r3-eth1" in errs[0]


def test_member_only_is_warning():
    """既存の書き方 (メンバーを並べる) は壊さず warning にとどめる"""
    r = validate_all(_topo(_vlan(trunk="{node: r1, interface: r1-eth0}, {node: r2, interface: r2-eth0}")))
    assert r.errors == []
    assert [w.path for w in r.warnings] == [
        "layer2.vlans[0].trunk_ports[0].interface",
        "layer2.vlans[0].trunk_ports[1].interface",
    ]
    assert "interface: lag-mlag-a" in r.warnings[0].message


def test_member_only_is_error_in_strict():
    r = validate_all(_topo(_vlan(trunk="{interface: r3-eth0}")), strict=True)
    assert len(r.errors) == 1


@pytest.mark.parametrize("trunk,access", [
    ("{interface: lag-mlag-a}, {interface: lag-mlag-a}", ""),
    ("{interface: lag-mlag-a}", "{interface: lag-mlag-a}"),
    ("{node: r1, interface: r1-eth1}", "{interface: r1-eth1}"),
])
def test_same_interface_twice_in_vlan(trunk, access):
    errs = _errors(_vlan(trunk=trunk, access=access))
    assert len(errs) == 1 and "にも書かれています" in errs[0]


def test_same_lag_in_different_vlans():
    assert _errors(_vlan(trunk="{interface: lag-mlag-a}", vid=100),
                   _vlan(trunk="{interface: lag-mlag-a}", vid=200)) == []


def test_vlan_id_clash_expands_mlag_to_both_nodes():
    """MLAG に載せた VLAN は r2 にも存在する。r2 の別エントリと vlan_id が重なれば検出する"""
    errs = _errors(
        _vlan(trunk="{interface: lag-mlag-a}", vlan_id="vlan-a"),
        _vlan(trunk="{interface: r2-eth1}", vlan_id="vlan-b"),
    )
    assert len(errs) == 1 and "r2" in errs[0] and "100" in errs[0]


# ---------------------------------------------------------------------------
# エクスポーター
# ---------------------------------------------------------------------------

def _data(out, kind, eid):
    return next(x["data"] for x in out[kind] if x["data"]["id"] == eid)


def test_cytoscape_mlag_vlan_on_both_nodes():
    out = cytoscape.export(_topo(_vlan(trunk="{interface: lag-mlag-a}")))
    for nid in ("r1", "r2"):
        assert _data(out, "nodes", nid)["vlans"] == ["vlan-100"]
        assert _data(out, "edges", f"vlan-vlan-100-{nid}")["tagged_on"] == ["lag-mlag-a"]
    assert "vlans" not in _data(out, "nodes", "r3")


def test_cytoscape_access_lag_is_untagged():
    out = cytoscape.export(_topo(_vlan(access="{interface: lag-r3-po1}")))
    assert _data(out, "edges", "vlan-vlan-100-r3")["untagged_on"] == ["lag-r3-po1"]


def test_yaml_round_trip_without_node():
    t1 = _topo(_vlan(trunk="{interface: lag-mlag-a}", access="{interface: r3-eth0}"))
    t2 = parse(yaml_exporter.export(t1))
    assert t1.model_dump() == t2.model_dump()
