"""ADR-0023 機器ごとの LAG と layer1.ethernet_segments のテスト

VLAN のポートの {ethernet_segment:} は tests/test_portref_lag.py、VTEP の warning は tests/test_vteps.py が見る。
"""

from __future__ import annotations

import pydantic
import pytest

from mlndl import parse, validate_all
from mlndl.derive import ethernet_segments, vlan_endpoints
from mlndl.exporter import cytoscape, yaml as yaml_exporter


L1 = """
layer1:
  nodes: [{id: leaf1}, {id: leaf2}, {id: leaf3}, {id: srv1}, {id: fw1}]
  interfaces:
    - {id: leaf1-swp1, node: leaf1, name: swp1}
    - {id: leaf1-swp2, node: leaf1, name: swp2}
    - {id: leaf1-swp49, node: leaf1, name: swp49}
    - {id: leaf2-swp1, node: leaf2, name: swp1}
    - {id: leaf2-swp49, node: leaf2, name: swp49}
    - {id: leaf3-xe4, node: leaf3, name: xe-0/0/4}
    - {id: leaf2-xe4, node: leaf2, name: xe-0/0/4}
    - {id: srv1-eth0, node: srv1, name: eth0}
    - {id: srv1-eth1, node: srv1, name: eth1}
    - {id: fw1-eth1, node: fw1, name: eth1}
    - {id: fw1-eth2, node: fw1, name: eth2}
  links:
    - {id: link-leaf1-leaf2-peer, endpoints: [leaf1-swp49, leaf2-swp49], link_role: peer-link}
    - {id: link-leaf1-srv1, endpoints: [leaf1-swp1, srv1-eth0]}
    - {id: link-leaf2-srv1, endpoints: [leaf2-swp1, srv1-eth1]}
    - {id: link-leaf2-fw1, endpoints: [leaf2-xe4, fw1-eth1]}
    - {id: link-leaf3-fw1, endpoints: [leaf3-xe4, fw1-eth2]}
  lag:
    - {id: lag-leaf1-peer, node: leaf1, name: peerlink, members: [leaf1-swp49]}
    - {id: lag-leaf2-peer, node: leaf2, name: peerlink, members: [leaf2-swp49]}
    - {id: lag-leaf1-srv1, node: leaf1, name: bond1, members: [leaf1-swp1]}
    - {id: lag-leaf2-srv1, node: leaf2, name: bond1, members: [leaf2-swp1]}
    - {id: lag-leaf1-b, node: leaf1, members: [leaf1-swp2]}
    - {id: lag-srv1-bond0, node: srv1, name: bond0, members: [srv1-eth0, srv1-eth1]}
"""

ES_SRV1 = "    - {id: es-srv1, members: [{lag: lag-leaf1-srv1}, {lag: lag-leaf2-srv1}]}\n"
ES_FW1 = ("    - {id: es-fw1, members: [{interface: leaf2-xe4}, {interface: leaf3-xe4}],"
          " redundancy_mode: single_active}\n")


def _text(*segments: str, rest: str = "") -> str:
    body = 'ndl_version: "1.0"\n' + L1
    if segments:
        body += "  ethernet_segments:\n" + "".join(segments)
    return body + rest


def _topo(*segments: str, rest: str = ""):
    return parse(_text(*segments, rest=rest))


def _result(*segments: str, rest: str = ""):
    return validate_all(_topo(*segments, rest=rest))


# ---------------------------------------------------------------------------
# スキーマ (D1〜D4)
# ---------------------------------------------------------------------------

class TestSchema:
    def test_valid_without_warnings(self):
        r = _result(ES_SRV1, ES_FW1)
        assert r.errors == [] and r.warnings == []

    def test_members_are_lag_or_interface(self):
        """脚は {lag:} か {interface:}。single-active で物理 IF に直接 ESI を設定する構成は {interface:} (D3)"""
        es_srv1, es_fw1 = _topo(ES_SRV1, ES_FW1).layer1.ethernet_segments
        assert [(m.kind, m.target) for m in es_srv1.members] == [("lag", "lag-leaf1-srv1"), ("lag", "lag-leaf2-srv1")]
        assert [(m.kind, m.target) for m in es_fw1.members] == [("interface", "leaf2-xe4"), ("interface", "leaf3-xe4")]

    def test_redundancy_mode_has_no_default(self):
        """書かなければ「書いていない」。all_active で埋めない (D4)"""
        es_srv1, es_fw1 = _topo(ES_SRV1, ES_FW1).layer1.ethernet_segments
        assert es_srv1.redundancy_mode is None
        assert es_fw1.redundancy_mode == "single_active"

    @pytest.mark.parametrize("mode", ["active_standby", "port_active", "all-active"])
    def test_redundancy_mode_values(self, mode):
        with pytest.raises(pydantic.ValidationError):
            _topo(f"    - {{id: es-x, members: [{{lag: lag-leaf1-srv1}}, {{lag: lag-leaf2-srv1}}], redundancy_mode: {mode}}}\n")

    def test_at_least_two_members(self):
        with pytest.raises(pydantic.ValidationError, match="2 つ以上"):
            _topo("    - {id: es-x, members: [{lag: lag-leaf1-srv1}]}\n")

    @pytest.mark.parametrize("member", ["{lag: lag-leaf1-srv1, interface: leaf2-xe4}", "{node: leaf1}", "lag-leaf1-srv1"])
    def test_member_needs_exactly_one_key(self, member):
        with pytest.raises(pydantic.ValidationError):
            _topo(f"    - {{id: es-x, members: [{member}, {{lag: lag-leaf2-srv1}}]}}\n")

    @pytest.mark.parametrize("key", ["esi: '00:11:22:33:44:55:66:77:88:99'", "system_mac: '44:38:39:ff:00:0a'",
                                     "domain_id: 10", "peer_links: [lag-leaf1-peer, lag-leaf2-peer]"])
    def test_granularity_keys_are_rejected(self, key):
        """ESI の値・MAC・ドメインの番号・ピアリンクは書かない (ADR-0022 / ADR-0023 D6)"""
        with pytest.raises(pydantic.ValidationError, match="書きません"):
            _topo(f"    - {{id: es-x, members: [{{lag: lag-leaf1-srv1}}, {{lag: lag-leaf2-srv1}}], {key}}}\n")

    def test_l3_interface_cannot_attach_to_segment(self):
        """L3 IF は機器ごとの LAG を指す (D5)"""
        with pytest.raises(pydantic.ValidationError, match="機器ごとの LAG"):
            _topo(ES_SRV1, rest=("layer3:\n  interfaces:\n"
                                 "    - {id: leaf1-bond1, node: leaf1, name: bond1, attaches_to: {ethernet_segment: es-srv1}}\n"))

    @pytest.mark.parametrize("lag,needle", [
        ("{id: lag-x, type: mlag, nodes: [leaf1, leaf2], members: [leaf1-swp1, leaf2-swp1]}", "ethernet_segments"),
        ("{id: lag-x, node: leaf1, members: [leaf1-swp1], peer_link: lag-leaf1-peer}", "peer_link"),
        ("{id: lag-x, node: leaf1, members: [leaf1-swp1], system_mac: '44:38:39:ff:00:0a'}", "system_mac"),
        ("{id: lag-x, type: lacp, node: leaf1, members: [leaf1-swp1]}", "type を消して"),
    ])
    def test_old_lag_forms_are_errors(self, lag, needle):
        """旧形式は移動先を示す error。読み替えはしない (D9)"""
        with pytest.raises(pydantic.ValidationError, match=needle):
            parse(_text().replace("  lag:\n", f"  lag:\n    - {lag}\n"))


# ---------------------------------------------------------------------------
# 検査 (D7)
# ---------------------------------------------------------------------------

class TestChecks:
    def test_two_legs_on_same_node(self):
        r = _result("    - {id: es-x, members: [{lag: lag-leaf1-srv1}, {lag: lag-leaf1-b}]}\n")
        assert [e.path for e in r.errors] == ["layer1.ethernet_segments[0].members[1].lag"]
        assert "leaf1" in r.errors[0].message and "機器ごとに 1 つ" in r.errors[0].message

    def test_leg_in_two_segments(self):
        r = _result(ES_SRV1, "    - {id: es-y, members: [{lag: lag-leaf1-srv1}, {interface: leaf3-xe4}]}\n")
        assert [e.path for e in r.errors] == ["layer1.ethernet_segments[1].members[0].lag"]
        assert "es-srv1" in r.errors[0].message

    def test_member_interface_of_leg_lag_in_another_segment(self):
        """脚の LAG のメンバーを、別の ES の脚にしても同じ脚の重複"""
        r = _result(ES_SRV1, "    - {id: es-y, members: [{interface: leaf1-swp1}, {interface: leaf3-xe4}]}\n")
        assert any(e.path == "layer1.ethernet_segments[1].members[0].interface" and "es-srv1" in e.message
                   for e in r.errors)

    def test_lag_and_its_member_in_same_segment(self):
        r = _result("    - {id: es-x, members: [{lag: lag-leaf1-srv1}, {interface: leaf1-swp1}, {lag: lag-leaf2-srv1}]}\n")
        assert [e.path for e in r.errors] == ["layer1.ethernet_segments[0].members[1].interface"]
        assert "LAG だけを書いて" in r.errors[0].message

    def test_member_of_lag_is_warning(self):
        """脚が LAG なのにメンバーの IF を書いたら、LAG を指すよう促す"""
        r = _result("    - {id: es-x, members: [{interface: leaf1-swp1}, {lag: lag-leaf2-srv1}]}\n")
        assert r.errors == []
        assert [w.path for w in r.warnings] == ["layer1.ethernet_segments[0].members[0].interface"]
        assert "lag: lag-leaf1-srv1" in r.warnings[0].message

    def test_peer_link_as_legs_is_error(self):
        """脚どうしが L1 リンクでつながっていたら、ピアリンクを脚にした疑い (D6)"""
        r = _result("    - {id: es-x, members: [{lag: lag-leaf1-peer}, {lag: lag-leaf2-peer}]}\n")
        assert [e.path for e in r.errors] == ["layer1.ethernet_segments[0].members[0]"]
        assert "ピアリンク" in r.errors[0].message

    @pytest.mark.parametrize("member,hint", [
        ("{lag: nope}", None),
        ("{interface: nope}", None),
        ("{lag: leaf3-xe4}", "{interface: leaf3-xe4}"),        # キーの取り違え
        ("{interface: lag-leaf1-b}", "{lag: lag-leaf1-b}"),
    ])
    def test_undefined_member(self, member, hint):
        r = _result(f"    - {{id: es-x, members: [{member}, {{lag: lag-leaf2-srv1}}]}}\n")
        assert len(r.errors) == 1 and "未定義" in r.errors[0].message
        if hint:
            assert hint in r.errors[0].message

    def test_prefix_warning(self):
        r = _result("    - {id: srv1-mh, members: [{lag: lag-leaf1-srv1}, {lag: lag-leaf2-srv1}]}\n")
        assert [w.path for w in r.warnings] == ["layer1.ethernet_segments[0].id"]


# ---------------------------------------------------------------------------
# 導出と bridge のポート
# ---------------------------------------------------------------------------

def test_derive_segments():
    segs = ethernet_segments(_topo(ES_SRV1, ES_FW1))
    assert segs["es-srv1"].nodes == ["leaf1", "leaf2"] and segs["es-srv1"].legs == ["leaf1-swp1", "leaf2-swp1"]
    assert segs["es-fw1"].nodes == ["leaf2", "leaf3"] and segs["es-fw1"].legs == ["leaf2-xe4", "leaf3-xe4"]


def test_vlan_endpoints_through_interface_legs():
    """脚が物理 IF の ES でも、VLAN の端点は脚ごとにたどる (ADR-0013 D7)"""
    t = _topo(ES_FW1, rest="layer2:\n  vlans: [{id: vlan-300, vlan_id: 300, access_ports: [{ethernet_segment: es-fw1}]}]\n")
    eps = vlan_endpoints(t)
    assert sorted((ep.port_node, ep.node, tuple(ep.interfaces)) for ep in eps) == [
        ("leaf2", "fw1", ("fw1-eth1",)), ("leaf3", "fw1", ("fw1-eth2",))]


BRIDGE = """layer2:
  bridges:
    - id: bridge-svc
      ports: [{ethernet_segment: es-srv1}, {interface: leaf3-xe4}]
"""


def test_segment_in_bridge_ports():
    r = _result(ES_SRV1, rest=BRIDGE)
    assert r.errors == [] and r.warnings == []


def test_segment_and_its_leg_in_same_bridge_is_error():
    r = _result(ES_SRV1, rest=BRIDGE.replace("{interface: leaf3-xe4}", "{lag: lag-leaf2-srv1}"))
    assert [e.path for e in r.errors] == ["layer2.bridges[0].ports[1].lag"]
    assert "es-srv1" in r.errors[0].message


# ---------------------------------------------------------------------------
# エクスポーター (D8)
# ---------------------------------------------------------------------------

def _data(out, kind, eid):
    return next(x["data"] for x in out[kind] if x["data"]["id"] == eid)


def test_cytoscape_segment_element():
    out = cytoscape.export(_topo(ES_SRV1, ES_FW1))
    srv1 = _data(out, "nodes", "es-srv1")
    assert srv1["type"] == "ethernet_segment" and srv1["layer"] == "layer1"
    assert srv1["members"] == [{"lag": "lag-leaf1-srv1", "node": "leaf1"}, {"lag": "lag-leaf2-srv1", "node": "leaf2"}]
    assert srv1["nodes"] == ["leaf1", "leaf2"]
    assert "redundancy_mode" not in srv1               # 書かれていなければ出さない
    assert _data(out, "nodes", "es-fw1")["redundancy_mode"] == "single_active"


def test_cytoscape_links_carry_segment():
    """リンクに ES を載せる。lag_type はなくした (ビューワは ethernet_segment で枠を描く)"""
    out = cytoscape.export(_topo(ES_SRV1, ES_FW1))
    link = _data(out, "edges", "link-leaf1-srv1")
    assert link["ethernet_segment"] == "es-srv1" and link["lag_id"] == "lag-leaf1-srv1"
    assert _data(out, "edges", "link-leaf3-fw1")["ethernet_segment"] == "es-fw1"
    assert "ethernet_segment" not in _data(out, "edges", "link-leaf1-leaf2-peer")
    assert not any("lag_type" in e["data"] for e in out["edges"])


def test_cytoscape_bridge_port_segment():
    out = cytoscape.export(_topo(ES_SRV1, rest=BRIDGE))
    ports = _data(out, "nodes", "bridge-svc")["ports"]
    assert ports[0] == {"ethernet_segment": "es-srv1", "nodes": ["leaf1", "leaf2"]}


def test_yaml_round_trip():
    t1 = _topo(ES_SRV1, ES_FW1, rest=BRIDGE)
    t2 = parse(yaml_exporter.export(t1))
    assert t1.model_dump() == t2.model_dump()
