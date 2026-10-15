"""ADR-0013 VLAN の trunk_ports / access_ports (L1 IF は {interface:}、LAG は {lag:}) のテスト"""

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

def test_interface_or_lag():
    pr = _topo(_vlan(trunk="{interface: r1-eth1}, {lag: lag-r3-po1}")).layer2.vlans[0].trunk_ports
    assert [(p.interface, p.lag, p.target) for p in pr] == [
        ("r1-eth1", None, "r1-eth1"), (None, "lag-r3-po1", "lag-r3-po1")]


@pytest.mark.parametrize("port", ["{node: r1}", "{interface: r1-eth1, lag: lag-r3-po1}"])
def test_exactly_one_of_interface_or_lag(port):
    with pytest.raises(pydantic.ValidationError):
        _topo(_vlan(trunk=port))


# ---------------------------------------------------------------------------
# 書けるもの
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trunk", [
    "{lag: lag-r3-po1}",                       # LACP
    "{lag: lag-mlag-a}",                       # MLAG は 1 エントリで両ノード
    "{lag: lag-peer}",                         # peer-link も書ける
    "{interface: r1-eth1}",                    # L1 IF
])
def test_valid_trunk(trunk):
    r = validate_all(_topo(_vlan(trunk=trunk)))
    assert r.errors == [] and r.warnings == []


def test_lag_in_access_ports():
    assert _errors(_vlan(access="{lag: lag-mlag-a}")) == []


# ---------------------------------------------------------------------------
# error / warning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("port,hint", [
    ("{interface: nope}", None),
    ("{lag: nope}", None),
    ("{interface: vlan-100}", "VLAN"),      # VLAN は VLAN のポートにならない
    ("{lag: r1-eth1}", "{interface: r1-eth1}"),   # キーの取り違え
])
def test_undefined_reference(port, hint):
    errs = _errors(_vlan(trunk=port))
    assert len(errs) == 1 and "未定義" in errs[0]
    if hint:
        assert hint in errs[0]


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
    assert "lag: lag-mlag-a" in r.warnings[0].message


def test_member_only_is_error_in_strict():
    r = validate_all(_topo(_vlan(trunk="{interface: r3-eth0}")), strict=True)
    assert len(r.errors) == 1


@pytest.mark.parametrize("trunk,access", [
    ("{lag: lag-mlag-a}, {lag: lag-mlag-a}", ""),
    ("{lag: lag-mlag-a}", "{lag: lag-mlag-a}"),
    ("{interface: r1-eth1}", "{interface: r1-eth1}"),
])
def test_same_port_twice_in_vlan(trunk, access):
    errs = _errors(_vlan(trunk=trunk, access=access))
    assert len(errs) == 1 and "にも書かれています" in errs[0]


def test_same_lag_in_different_vlans():
    assert _errors(_vlan(trunk="{lag: lag-mlag-a}", vid=100),
                   _vlan(trunk="{lag: lag-mlag-a}", vid=200)) == []


def test_vlan_id_clash_expands_mlag_to_both_nodes():
    """MLAG に載せた VLAN は r2 にも存在する。r2 の別エントリと vlan_id が重なれば検出する"""
    errs = _errors(
        _vlan(trunk="{lag: lag-mlag-a}", vlan_id="vlan-a"),
        _vlan(trunk="{interface: r2-eth1}", vlan_id="vlan-b"),
    )
    assert len(errs) == 1 and "r2" in errs[0] and "100" in errs[0]


# ---------------------------------------------------------------------------
# 旧形式 (ndl_version 1.x の間だけ受け付ける。ADR-0013 D2、ADR-0001 D8)
# ---------------------------------------------------------------------------

def test_legacy_node_is_warning():
    r = validate_all(_topo(_vlan(trunk="{node: r1, interface: r1-eth1}")))
    assert r.errors == []
    assert [w.path for w in r.warnings] == ["layer2.vlans[0].trunk_ports[0].node"]
    assert "node を消してください" in r.warnings[0].message


def test_legacy_interface_key_for_lag_is_warning():
    r = validate_all(_topo(_vlan(trunk="{interface: lag-mlag-a}")))
    assert r.errors == []
    assert [w.path for w in r.warnings] == ["layer2.vlans[0].trunk_ports[0].interface"]
    assert "{lag: lag-mlag-a}" in r.warnings[0].message


@pytest.mark.parametrize("port,needle", [
    ("{node: r1, lag: lag-mlag-a}", "MLAG"),                  # MLAG は両ノードに効く
    ("{node: r1, lag: lag-r3-po1}", "lag-r3-po1"),            # 別ノードの LAG
    ("{node: r2, interface: r1-eth1}", "r1-eth1"),            # 別ノードの IF
    ("{node: nope, interface: r1-eth1}", "nope"),
])
def test_legacy_node_is_still_checked(port, needle):
    errs = _errors(_vlan(trunk=port))
    assert len(errs) == 1 and needle in errs[0]


# ---------------------------------------------------------------------------
# エクスポーター
# ---------------------------------------------------------------------------

def _data(out, kind, eid):
    return next(x["data"] for x in out[kind] if x["data"]["id"] == eid)


def test_cytoscape_mlag_vlan_on_both_nodes():
    out = cytoscape.export(_topo(_vlan(trunk="{lag: lag-mlag-a}")))
    for nid in ("r1", "r2"):
        assert _data(out, "nodes", nid)["vlans"] == ["vlan-100"]
        assert _data(out, "edges", f"vlan-vlan-100-{nid}")["tagged_on"] == ["lag-mlag-a"]
    assert "vlans" not in _data(out, "nodes", "r3")


def test_cytoscape_access_lag_is_untagged():
    out = cytoscape.export(_topo(_vlan(access="{lag: lag-r3-po1}")))
    assert _data(out, "edges", "vlan-vlan-100-r3")["untagged_on"] == ["lag-r3-po1"]


def test_yaml_round_trip():
    t1 = _topo(_vlan(trunk="{lag: lag-mlag-a}", access="{interface: r3-eth0}"))
    t2 = parse(yaml_exporter.export(t1))
    assert t1.model_dump() == t2.model_dump()
