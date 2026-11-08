"""ADR-0013 VLAN の trunk_ports / access_ports (L1 IF は {interface:}、LAG は {lag:}、
Ethernet Segment は {ethernet_segment:}。ADR-0023 D5) のテスト"""

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
    - {id: lag-r3-po1, node: r3, members: [r3-eth0, r3-eth1]}
    - {id: lag-peer, node: r1, members: [r1-eth2]}
    - {id: lag-r1-a, node: r1, members: [r1-eth0]}
    - {id: lag-r2-a, node: r2, members: [r2-eth0]}
  ethernet_segments:
    - {id: es-a, members: [{lag: lag-r1-a}, {lag: lag-r2-a}]}
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

def test_interface_or_lag():
    pr = _topo(_vlan(trunk="{interface: r1-eth1}, {lag: lag-r3-po1}")).layer2.vlans[0].trunk_ports
    assert [(p.interface, p.lag, p.target) for p in pr] == [
        ("r1-eth1", None, "r1-eth1"), (None, "lag-r3-po1", "lag-r3-po1")]


@pytest.mark.parametrize("port", ["{node: r1}", "{interface: r1-eth1, lag: lag-r3-po1}",
                                  "{lag: lag-r3-po1, ethernet_segment: es-a}"])
def test_exactly_one_of_interface_or_lag(port):
    with pytest.raises(pydantic.ValidationError):
        _topo(_vlan(trunk=port))


# ---------------------------------------------------------------------------
# 書けるもの
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trunk", [
    "{lag: lag-r3-po1}",                       # LACP
    "{ethernet_segment: es-a}",                # Ethernet Segment は 1 エントリで脚の全機器
    "{lag: lag-peer}",                         # peer-link も書ける
    "{interface: r1-eth1}",                    # L1 IF
])
def test_valid_trunk(trunk):
    r = validate_all(_topo(_vlan(trunk=trunk)))
    assert r.errors == [] and r.warnings == []


def test_lag_in_access_ports():
    assert _errors(_vlan(access="{lag: lag-r3-po1}")) == []


def test_segment_in_access_ports():
    assert _errors(_vlan(access="{ethernet_segment: es-a}")) == []


# ---------------------------------------------------------------------------
# error / warning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("port,hint", [
    ("{interface: nope}", None),
    ("{lag: nope}", None),
    ("{interface: vlan-100}", "VLAN で、ここには書けません"),      # VLAN は VLAN のポートにならない
])
def test_undefined_reference(port, hint):
    errs = _errors(_vlan(trunk=port))
    assert len(errs) == 1 and "未定義" in errs[0]
    if hint:
        assert hint in errs[0]


@pytest.mark.parametrize("port,move", [
    ("{lag: r1-eth1}", "{interface: r1-eth1}"),      # キーの取り違え
    ("{interface: lag-r3-po1}", "{lag: lag-r3-po1}"),  # 旧形式。読み替えない (ADR-0025 D1)
])
def test_wrong_key_shows_right_key(port, move):
    errs = _errors(_vlan(trunk=port))
    assert len(errs) == 1 and f"{move} と書いてください" in errs[0]


def test_lag_and_member_in_same_vlan_is_error():
    errs = _errors(_vlan(trunk="{lag: lag-r3-po1}, {interface: r3-eth0}"))
    assert len(errs) == 1 and "r3-eth0" in errs[0] and "lag-r3-po1" in errs[0]


def test_lag_in_trunk_and_member_in_access_is_error():
    errs = _errors(_vlan(trunk="{lag: lag-r3-po1}", access="{interface: r3-eth1}"))
    assert len(errs) == 1 and "r3-eth1" in errs[0]


def test_member_only_is_warning():
    """メンバーを並べる書き方は warning にとどめ、LAG を指すよう促す"""
    r = validate_all(_topo(_vlan(trunk="{interface: r1-eth0}, {interface: r2-eth0}")))
    assert r.errors == []
    assert [w.path for w in r.warnings] == [
        "layer2.vlans[0].trunk_ports[0].interface",
        "layer2.vlans[0].trunk_ports[1].interface",
    ]
    assert "lag: lag-r1-a" in r.warnings[0].message


def test_member_only_is_error_in_strict():
    r = validate_all(_topo(_vlan(trunk="{interface: r3-eth0}")), strict=True)
    assert len(r.errors) == 1


@pytest.mark.parametrize("trunk,access", [
    ("{lag: lag-r3-po1}, {lag: lag-r3-po1}", ""),
    ("{ethernet_segment: es-a}", "{ethernet_segment: es-a}"),
    ("{interface: r1-eth1}", "{interface: r1-eth1}"),
])
def test_same_port_twice_in_vlan(trunk, access):
    errs = _errors(_vlan(trunk=trunk, access=access))
    assert len(errs) == 1 and "にも書かれています" in errs[0]


def test_same_lag_in_different_vlans():
    assert _errors(_vlan(trunk="{ethernet_segment: es-a}", vid=100),
                   _vlan(trunk="{ethernet_segment: es-a}", vid=200)) == []


def test_vlan_id_clash_expands_segment_to_all_nodes():
    """Ethernet Segment に載せた VLAN は r2 にも存在する。r2 の別エントリと vlan_id が重なれば検出する"""
    errs = _errors(
        _vlan(trunk="{ethernet_segment: es-a}", vlan_id="vlan-a"),
        _vlan(trunk="{interface: r2-eth1}", vlan_id="vlan-b"),
    )
    assert len(errs) == 1 and "r2" in errs[0] and "100" in errs[0]


@pytest.mark.parametrize("trunk,needle", [
    ("{ethernet_segment: es-a}, {lag: lag-r1-a}", "lag-r1-a"),         # ES とその脚
    ("{ethernet_segment: es-a}, {interface: r2-eth0}", "r2-eth0"),     # ES と、脚の LAG のメンバー
])
def test_segment_and_its_leg_in_same_vlan_is_error(trunk, needle):
    """ES とその脚を同じ VLAN に併記できない (ADR-0023 D7)"""
    errs = _errors(_vlan(trunk=trunk))
    assert len(errs) == 1 and needle in errs[0] and "es-a" in errs[0]


def test_part_of_segment_is_warning():
    """ES の脚の一部だけに VLAN を載せた (MLAG の片側だけの典型的な誤り) は warning (ADR-0023 D7)"""
    r = validate_all(_topo(_vlan(trunk="{lag: lag-r1-a}")))
    assert r.errors == []
    assert [w.path for w in r.warnings] == ["layer2.vlans[0].trunk_ports[0]"]
    assert "lag-r2-a" in r.warnings[0].message and "{ethernet_segment: es-a}" in r.warnings[0].message


def test_all_legs_of_segment_is_not_warning():
    """脚をすべて機器ごとに書くのは、ES を書くのと同じ意味なので warning にしない"""
    r = validate_all(_topo(_vlan(trunk="{lag: lag-r1-a}, {lag: lag-r2-a}")))
    assert r.errors == [] and r.warnings == []


# ---------------------------------------------------------------------------
# 旧形式は移動先を示す error (ADR-0025 D1)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("port", [
    "{node: r1, interface: r1-eth1}",
    "{node: r1, ethernet_segment: es-a}",
])
def test_port_node_is_error(port):
    with pytest.raises(pydantic.ValidationError, match=r"VLAN のポートの node はなくしました.*ADR-0025"):
        _topo(_vlan(trunk=port))


# ---------------------------------------------------------------------------
# エクスポーター
# ---------------------------------------------------------------------------

def _data(out, kind, eid):
    return next(x["data"] for x in out[kind] if x["data"]["id"] == eid)


def test_cytoscape_segment_vlan_on_all_nodes():
    """ES のポートは、機器ごとにその機器の脚 (LAG の id) に開いて出す (ADR-0023 D8)"""
    out = cytoscape.export(_topo(_vlan(trunk="{ethernet_segment: es-a}")))
    for nid in ("r1", "r2"):
        assert _data(out, "nodes", nid)["vlans"] == ["vlan-100"]
        assert _data(out, "edges", f"vlan-vlan-100-{nid}")["tagged_on"] == [f"lag-{nid}-a"]
    assert "vlans" not in _data(out, "nodes", "r3")


def test_cytoscape_access_lag_is_untagged():
    out = cytoscape.export(_topo(_vlan(access="{lag: lag-r3-po1}")))
    assert _data(out, "edges", "vlan-vlan-100-r3")["untagged_on"] == ["lag-r3-po1"]


def test_yaml_round_trip():
    t1 = _topo(_vlan(trunk="{ethernet_segment: es-a}", access="{interface: r3-eth0}"))
    t2 = parse(yaml_exporter.export(t1))
    assert t1.model_dump() == t2.model_dump()
