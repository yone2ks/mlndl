"""ADR-0018 事業者網やトンネルを越えるセッションの通り道 (layer2.bridges・トンネル IF の update_source) のテスト"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from mlndl import parse, parse_file
from mlndl.derive import bgp_session_views, igp_adjacency_views
from mlndl.exporter import cytoscape
from mlndl.validator import validate_all

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "valid_wan_bridge_tunnel.yaml"
TEXT = FIXTURE.read_text()


def _topo(*replacements: tuple[str, str]):
    text = TEXT
    for old, new in replacements:
        assert old in text, old
        text = text.replace(old, new)
    return parse(text)


def _msgs(topo, severity: str = "error") -> list[str]:
    r = validate_all(topo)
    return [f"{e.path}: {e.message}" for e in {"error": r.errors, "warning": r.warnings}[severity]]


def _views(topo):
    return {v.session.id: v for v in [*bgp_session_views(topo), *igp_adjacency_views(topo)]}


# fixture の bridge の ports を差し替える
PORTS = """        - {interface: net-wideether-tokyo}
        - {interface: net-wideether-osaka}
"""
# bridge のエントリの最後の行。この後ろに layer2 のほかのリストや bridge を足す
BRIDGE_END = "      description: Port-based wide-area Ethernet between Tokyo and Osaka\n"
# bridge にポートを書かない (箱の中を L2 で透過させない)
NO_BRIDGE = ("      ports:                                  # 箱のポートだけを書く。拠点のルーターのポートは書かない\n" + PORTS,
             "      ports: []\n")


def test_fixture_is_valid_without_warnings():
    r = validate_all(parse_file(FIXTURE))
    assert r.errors == [] and r.warnings == [] and r.notes == []


# ---------------------------------------------------------------------------
# スキーマ (D1)
# ---------------------------------------------------------------------------

class TestSchema:
    def test_port_needs_exactly_one_key(self):
        with pytest.raises(PydanticValidationError, match="どちらか一方"):
            _topo((PORTS, "        - {interface: net-wideether-tokyo, lag: lag-x}\n"))

    def test_port_has_no_native_or_node(self):
        with pytest.raises(PydanticValidationError):
            _topo((PORTS, "        - {interface: net-wideether-tokyo, native: true}\n"))
        with pytest.raises(PydanticValidationError):
            _topo((PORTS, "        - {interface: net-wideether-tokyo, node: net-wideether}\n"))

    def test_bridge_has_no_members(self):
        with pytest.raises(PydanticValidationError):
            _topo(("      ports:  ", "      members:"))


# ---------------------------------------------------------------------------
# 通り道 (D2・D3・D4)
# ---------------------------------------------------------------------------

class TestTransport:
    def test_bridge_and_tunnel(self):
        views = _views(parse_file(FIXTURE))
        assert views["bgp-peer-tokyo-osaka"].transport.as_dict() == {"bridge": "bridge-wideether"}
        assert views["ospf-adj-tokyo-osaka"].transport.as_dict() == {"bridge": "bridge-wideether"}
        assert views["bgp-peer-tokyo-fukuoka-gre"].transport.as_dict() == {
            "tunnel": ["tunnel-tokyo-fukuoka", "tunnel-fukuoka-tokyo"]}

    def test_without_bridge_is_mismatch(self):
        """箱をはさんでも、bridge を書かなければ L2 で透過しない"""
        topo = _topo(NO_BRIDGE)
        v = _views(topo)["bgp-peer-tokyo-osaka"]
        assert v.transport is None and v.transport_mismatch

    def test_router_ports_are_not_needed(self):
        """bridge に届くかは、拠点のルーターのポートの対向で決まる (1 ホップ)"""
        assert not _views(parse_file(FIXTURE))["bgp-peer-tokyo-osaka"].transport_mismatch

    def test_lag_reaches_bridge(self):
        """拠点側が LAG でも、メンバーの対向が bridge のポートなら届く。片側だけ LAG でもよい"""
        topo = _topo(
            ("    - {id: tokyo-rtr-ge1, node: tokyo-rtr, name: ge-0/0/1}\n",
             "    - {id: tokyo-rtr-ge1, node: tokyo-rtr, name: ge-0/0/1}\n"
             "    - {id: tokyo-rtr-ge2, node: tokyo-rtr, name: ge-0/0/2}\n"
             "    - {id: net-wideether-tokyo2, node: net-wideether, name: tokyo-2}\n"),
            ("    - {id: link-osaka-wideether,",
             "    - {id: link-tokyo-wideether-2, endpoints: [tokyo-rtr-ge2, net-wideether-tokyo2]}\n"
             "    - {id: link-osaka-wideether,"),
            ("layer2:\n", "  lag:\n    - {id: lag-tokyo-po1, type: lacp, node: tokyo-rtr, members: [tokyo-rtr-ge0, tokyo-rtr-ge2]}\n\nlayer2:\n"),
            (PORTS, PORTS + "        - {interface: net-wideether-tokyo2}\n"),
            ("attaches_to: {interface: tokyo-rtr-ge0}}", "attaches_to: {lag: lag-tokyo-po1}}"),
        )
        assert _views(topo)["bgp-peer-tokyo-osaka"].transport.as_dict() == {"bridge": "bridge-wideether"}

    def test_two_hops_do_not_reach(self):
        """拠点の L2 スイッチをはさむと、ルーターのポートの対向はスイッチなので届かない (D8)"""
        topo = _topo(
            ("    - {id: net-wideether, ",
             "    - {id: tokyo-sw, role: leaf}\n    - {id: net-wideether, "),
            ("    - {id: net-wideether-tokyo, node: net-wideether, name: tokyo}\n",
             "    - {id: net-wideether-tokyo, node: net-wideether, name: tokyo}\n"
             "    - {id: tokyo-sw-p1, node: tokyo-sw}\n    - {id: tokyo-sw-p2, node: tokyo-sw}\n"),
            ("    - {id: link-tokyo-wideether, endpoints: [tokyo-rtr-ge0, net-wideether-tokyo], link_speed: 1G}\n",
             "    - {id: link-tokyo-rtr-sw, endpoints: [tokyo-rtr-ge0, tokyo-sw-p1]}\n"
             "    - {id: link-tokyo-sw-wideether, endpoints: [tokyo-sw-p2, net-wideether-tokyo]}\n"),
        )
        assert _views(topo)["bgp-peer-tokyo-osaka"].transport_mismatch

    def test_subinterface_tags_are_not_compared_across_bridge(self):
        """タグ変換のある契約 (EVPL) では両拠点のタグが違うのが正しい"""
        topo = _topo(
            (BRIDGE_END, BRIDGE_END + "  subinterfaces:\n"
                    "    - {id: subif-tokyo-ge0-100, attaches_to: {interface: tokyo-rtr-ge0}, vlan_id: 100}\n"
                    "    - {id: subif-osaka-ge0-200, attaches_to: {interface: osaka-rtr-ge0}, vlan_id: 200}\n"),
            ("attaches_to: {interface: tokyo-rtr-ge0}}", "attaches_to: {subinterface: subif-tokyo-ge0-100}}"),
            ("attaches_to: {interface: osaka-rtr-ge0}}", "attaches_to: {subinterface: subif-osaka-ge0-200}}"),
        )
        assert _views(topo)["bgp-peer-tokyo-osaka"].transport.as_dict() == {"bridge": "bridge-wideether"}

    def test_tunnel_on_one_side_is_mismatch(self):
        topo = _topo(("update_source: tunnel-fukuoka-tokyo}", "update_source: fukuoka-rtr-inet}"))
        v = _views(topo)["bgp-peer-tokyo-fukuoka-gre"]
        assert v.transport is None and v.transport_mismatch

    def test_unpaired_tunnels_are_mismatch(self):
        topo = _topo(("destination_interface: tokyo-rtr-inet,", "destination_interface: fukuoka-rtr-inet,"))
        assert _views(topo)["bgp-peer-tokyo-fukuoka-gre"].transport_mismatch

    def test_destination_ip_is_not_checked(self):
        """destination_ip のトンネルは対を確かめられないので、通り道を導かず食い違いともしない"""
        topo = _topo(("destination_interface: tokyo-rtr-inet,", "destination_ip: 198.51.100.2,"))
        v = _views(topo)["bgp-peer-tokyo-fukuoka-gre"]
        assert v.transport is None and not v.transport_mismatch


# ---------------------------------------------------------------------------
# 検査
# ---------------------------------------------------------------------------

class TestChecks:
    def test_bgp_mismatch_message(self):
        msgs = _msgs(_topo((PORTS, "        - {interface: net-wideether-tokyo}\n")))
        (msg,) = [m for m in msgs if m.startswith("control_plane.routing_neighbors[0]")]
        assert "リンク link-tokyo-wideether (bridge bridge-wideether に届く)" in msg
        assert "リンク link-osaka-wideether" in msg and "(b) 事業者網をはさむなら" in msg

    def test_one_side_tunnel_message(self):
        (msg,) = _msgs(_topo(("update_source: tunnel-fukuoka-tokyo}", "update_source: fukuoka-rtr-inet}")))
        assert "to 側の 'fukuoka-rtr-inet' はトンネル IF ではありません" in msg

    def test_ospf_mismatch_is_warning(self):
        topo = _topo(NO_BRIDGE)
        assert [m for m in _msgs(topo) if "ospf" in m or "[2]" in m] == []
        (warning,) = [m for m in _msgs(topo, "warning") if m.startswith("control_plane.routing_neighbors[2]")]
        assert "両端の interface から導いた通り道が食い違います" in warning

    def test_isis_over_bridge(self):
        topo = _topo(
            ("  ospf:\n", "  isis:\n    - {id: isis-wan, nodes: [{node: tokyo-rtr}, {node: osaka-rtr}]}\n  ospf:\n"),
            ("      address_families: [ipv4_unicast]\n    - id: ospf-adj-tokyo-osaka",
             "      address_families: [ipv4_unicast]\n"
             "    - {id: isis-adj-tokyo-osaka, type: isis, from: {node: tokyo-rtr, interface: tokyo-rtr-ge0},"
             " to: {node: osaka-rtr, interface: osaka-rtr-ge0}, level: level-2}\n"
             "    - id: ospf-adj-tokyo-osaka"),
        )
        assert _views(topo)["isis-adj-tokyo-osaka"].transport.as_dict() == {"bridge": "bridge-wideether"}
        assert validate_all(topo).warnings == []

    def test_tunnel_reference_is_accepted_and_labelled(self):
        (msg,) = _msgs(_topo(("update_source: tunnel-fukuoka-tokyo}", "update_source: tunnel-nope}")))
        assert "未定義の L3 インターフェース / トンネル 'tunnel-nope' を参照しています" in msg

    def test_tunnel_vrf_is_the_overlay_vrf(self):
        topo = _topo(("ip: 172.31.0.2/30}", "ip: 172.31.0.2/30, vrf: vrf-a}"),
                     ("layer3:\n", "layer3:\n  vrfs: [{id: vrf-a}]\n"),
                     ("  bgp:\n", "  bgp:\n    - {id: bgp-a, vrf: vrf-a, nodes: [{node: fukuoka-rtr, local_as: 65003}]}\n"),
                     ("      address_families: [ipv4_unicast]\n    - id: ospf",
                      "      address_families: [ipv4_unicast]\n      instance: bgp-default\n    - id: ospf"),
                     ("    - id: bgp-peer-tokyo-osaka\n      type: bgp\n",
                      "    - id: bgp-peer-tokyo-osaka\n      type: bgp\n      instance: bgp-default\n"))
        msgs = _msgs(topo)
        assert any("'tunnel-fukuoka-tokyo' は VRF 'vrf-a' のトンネルですが" in m for m in msgs)

    def test_l3_interface_and_tunnel_ids_are_unique(self):
        topo = _topo(("{id: tunnel-tokyo-fukuoka,", "{id: tokyo-rtr-inet,"),
                     ("update_source: tunnel-tokyo-fukuoka}", "update_source: tokyo-rtr-inet}"))
        assert any("'tokyo-rtr-inet' が L3 インターフェース と トンネル の両方で使われています" in m for m in _msgs(topo))

    def test_same_port_in_two_bridges(self):
        topo = _topo((BRIDGE_END, BRIDGE_END + "    - {id: bridge-other, ports: [{interface: net-wideether-tokyo}, "
                                    "{interface: net-wideether-osaka}]}\n"))
        msgs = _msgs(topo)
        assert len(msgs) == 2 and all("は bridge 'bridge-wideether' のポートでもあります" in m for m in msgs)

    def test_same_port_twice(self):
        (msg,) = _msgs(_topo((PORTS, PORTS + "        - {interface: net-wideether-osaka}\n")))
        assert msg.startswith("layer2.bridges[0].ports[2].interface") and "すでに書かれています" in msg

    def test_wrong_key(self):
        msgs = _msgs(_topo((PORTS, "        - {lag: net-wideether-tokyo}\n        - {interface: net-wideether-osaka}\n")))
        (msg,) = [m for m in msgs if m.startswith("layer2.bridges")]   # 届かないので通り道の食い違いも出る
        assert "{interface: net-wideether-tokyo} の誤りではありませんか" in msg

    def test_one_port_is_warning(self):
        topo = _topo((PORTS, "        - {interface: net-wideether-tokyo}\n"))
        assert any(m.startswith("layer2.bridges[0].ports:") and "1 つしかありません" in m for m in _msgs(topo, "warning"))

    def test_router_port_is_warning(self):
        topo = _topo((PORTS, PORTS + "        - {interface: tokyo-rtr-ge0}\n"))
        warnings = [m for m in _msgs(topo, "warning") if "対向も、この bridge のポートです" in m]
        assert [w.split(":")[0] for w in warnings] == ["layer2.bridges[0].ports[0].interface", "layer2.bridges[0].ports[2].interface"]

    def test_vlan_and_bridge_port_is_warning(self):
        topo = _topo(("layer2:\n", "layer2:\n  vlans: [{id: vlan-10, vlan_id: 10, access_ports: [{interface: net-wideether-tokyo}]}]\n"))
        assert any("VLAN のポートにも書かれています" in m for m in _msgs(topo, "warning"))

    def test_lag_and_member(self):
        lag = ("layer2:\n", "  lag:\n    - {id: lag-we-tokyo, type: lacp, node: net-wideether, members: [net-wideether-tokyo]}\n\nlayer2:\n")
        both = _topo(lag, (PORTS, PORTS + "        - {lag: lag-we-tokyo}\n"))
        assert any("LAG とそのメンバーを同じ bridge に書くことはできません" in m for m in _msgs(both))
        member_only = _topo(lag)
        assert any("bridge には LAG を書いてください" in m for m in _msgs(member_only, "warning"))

    def test_prefix(self):
        topo = _topo(("id: bridge-wideether", "id: we220"), ("bridge-wideether", "we220"))
        assert any("推奨プレフィックス 'bridge-'" in m for m in _msgs(topo, "warning"))


# ---------------------------------------------------------------------------
# エクスポーター (D5)
# ---------------------------------------------------------------------------

class TestExport:
    def _elements(self):
        out = cytoscape.export(parse_file(FIXTURE))
        return {e["data"]["id"]: e["data"] for e in [*out["nodes"], *out["edges"]]}

    def test_bridge_element(self):
        br = self._elements()["bridge-wideether"]
        assert br["type"] == "bridge" and br["layer"] == "layer2" and br["nodes"] == ["net-wideether"]
        assert br["ports"][0] == {"interface": "net-wideether-tokyo", "nodes": ["net-wideether"]}
        assert br["name"] == "WE-220" and "description" in br

    def test_transport_links(self):
        els = self._elements()
        assert els["bgp-peer-tokyo-osaka"]["transport_link"] == {"bridge": "bridge-wideether"}
        assert els["ospf-adj-tokyo-osaka"]["transport_link"] == {"bridge": "bridge-wideether"}
        gre = els["bgp-peer-tokyo-fukuoka-gre"]
        assert gre["transport_link"] == {"tunnel": ["tunnel-tokyo-fukuoka", "tunnel-fukuoka-tokyo"]}
        assert gre["from"]["l3_interface"] == "tunnel-tokyo-fukuoka" and "interface_name" not in gre["from"]
