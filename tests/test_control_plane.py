"""ADR-0010 制御プレーン (control_plane) のテスト"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from mlndl import parse, parse_file, validate
from mlndl.derive import bgp_session_views
from mlndl.exporter import cytoscape
from mlndl.schema.control_plane import BgpInsideEndpoint, BgpOutsideEndpoint, BgpSession, OspfAdjacency
from mlndl.validator import validate_all

FIXTURES = Path(__file__).parent / "fixtures"

# r1 / r2 を 2 本のリンク (/31 どうし) とループバックで結んだ最小構成
BASE = """ndl_version: "1.0"
layer1:
  nodes: [{id: r1}, {id: r2}, {id: r3}]
  interfaces:
    - {id: r1-eth0, node: r1}
    - {id: r2-eth0, node: r2}
    - {id: r1-eth1, node: r1}
    - {id: r3-eth0, node: r3}
    - {id: r1-eth2, node: r1}
    - {id: r1-eth3, node: r1}
    - {id: r2-eth2, node: r2}
    - {id: r2-eth3, node: r2}
  links:
    - {id: link-r1-r2, endpoints: [r1-eth0, r2-eth0]}
    - {id: link-r1-r3, endpoints: [r1-eth1, r3-eth0]}
    - {id: link-r1-r2-a, endpoints: [r1-eth2, r2-eth2]}
    - {id: link-r1-r2-b, endpoints: [r1-eth3, r2-eth3]}
  lag:
    - {id: lag-r1-po1, node: r1, members: [r1-eth2, r1-eth3]}
    - {id: lag-r2-po1, node: r2, members: [r2-eth2, r2-eth3]}
layer2:
  vlans: [{id: vlan-10, vlan_id: 10}, {id: vlan-20, vlan_id: 20}]
layer3:
  vrfs: [{id: vrf-a}, {id: vrf-b}]
  interfaces:
    - {id: r1-lo, node: r1, name: lo, ip: 10.0.0.1/32}
    - {id: r2-lo, node: r2, name: lo, ip: 10.0.0.2/32}
    - {id: r2-lo6, node: r2, name: lo6, ipv6: 2001:db8::2/128}
    - {id: r1-eth0-l3, node: r1, name: eth0, ip: 10.1.0.0/31, attaches_to: {interface: r1-eth0}}
    - {id: r2-eth0-l3, node: r2, name: eth0, ip: 10.1.0.1/31, attaches_to: {interface: r2-eth0}}
    - {id: r1-eth1-l3, node: r1, name: eth1, ip: 10.1.0.2/31, attaches_to: {interface: r1-eth1}}
    - {id: r3-eth0-l3, node: r3, name: eth0, ip: 10.1.0.3/31, attaches_to: {interface: r3-eth0}}
    - {id: r1-po1-l3, node: r1, name: po1, ip: 10.1.0.4/31, attaches_to: {lag: lag-r1-po1}}
    - {id: r2-po1-l3, node: r2, name: po1, ip: 10.1.0.5/31, attaches_to: {lag: lag-r2-po1}}
    - {id: r1-un, node: r1, name: swp9, attaches_to: {interface: r1-eth1}}
    - {id: r1-vlan10, node: r1, name: Vlan10, attaches_to: {vlan: vlan-10}, ip: 192.168.10.1/24}
    - {id: r2-vlan10, node: r2, name: Vlan10, attaches_to: {vlan: vlan-10}, ip: 192.168.10.2/24}
    - {id: r2-vlan20, node: r2, name: Vlan20, attaches_to: {vlan: vlan-20}, ip: 192.168.20.2/24}
    - {id: r1-a, node: r1, name: a, ip: 172.16.0.1/30, vrf: vrf-a, attaches_to: {interface: r1-eth0}}
    - {id: r2-a, node: r2, name: a, ip: 172.16.0.2/30, vrf: vrf-a, attaches_to: {interface: r2-eth0}}
control_plane:
  bgp:
    - id: bgp-default
      nodes: [{node: r1, local_as: 65001}, {node: r2, local_as: 65002}, {node: r3, local_as: 65001}]
  bfd:
    - {id: bfd-a, nodes: [r1, r2]}
  routing_neighbors:
"""


def _session(body: str, instances: str | None = None) -> str:
    text = BASE + "    " + body + "\n"
    if instances is not None:
        text = text.replace(
            "  bgp:\n    - id: bgp-default\n      nodes: [{node: r1, local_as: 65001}, {node: r2, local_as: 65002}, {node: r3, local_as: 65001}]\n",
            instances)
    return text


def _msgs(text: str, severity: str = "error") -> list[str]:
    r = validate_all(parse(text))
    return [f"{e.path}: {e.message}" for e in {"error": r.errors, "warning": r.warnings}[severity]]


OK_SESSION = "- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r1-eth0-l3}, to: {node: r2, update_source: r2-eth0-l3}}"


def test_base_session_is_valid():
    assert _msgs(_session(OK_SESSION)) == []


# ---------------------------------------------------------------------------
# スキーマ (D3・D12)
# ---------------------------------------------------------------------------

class TestSchema:
    def test_endpoint_forms(self):
        t = parse(_session("- {id: bgp-peer-r1-isp, type: bgp, from: {node: r1, update_source: r1-lo},"
                           " to: {address: 203.0.113.1, local_as: 64500}}"))
        s = t.control_plane.routing_neighbors[0]
        assert isinstance(s.from_, BgpInsideEndpoint) and isinstance(s.to, BgpOutsideEndpoint)

    def test_update_source_is_required(self):
        with pytest.raises(PydanticValidationError, match="update_source"):
            parse(_session("- {id: bgp-peer-x, type: bgp, from: {node: r1}, to: {node: r2, update_source: r2-lo}}"))

    def test_node_and_address_cannot_mix(self):
        with pytest.raises(PydanticValidationError, match="address"):
            parse(_session("- {id: bgp-peer-x, type: bgp, from: {node: r1, update_source: r1-lo, address: 10.0.0.9},"
                           " to: {node: r2, update_source: r2-lo}}"))

    def test_outside_needs_local_as_and_host_address(self):
        with pytest.raises(PydanticValidationError):
            parse(_session("- {id: bgp-peer-x, type: bgp, from: {node: r1, update_source: r1-lo}, to: {address: 203.0.113.1}}"))
        with pytest.raises(PydanticValidationError):
            parse(_session("- {id: bgp-peer-x, type: bgp, from: {node: r1, update_source: r1-lo},"
                           " to: {address: 203.0.113.1/30, local_as: 64500}}"))

    def test_both_outside_is_rejected(self):
        with pytest.raises(PydanticValidationError, match="両端ともトポロジー外"):
            parse(_session("- {id: bgp-peer-x, type: bgp, from: {address: 192.0.2.1, local_as: 1},"
                           " to: {address: 192.0.2.2, local_as: 2}}"))

    def test_session_has_no_attaches_to(self):
        with pytest.raises(PydanticValidationError):
            parse(_session(OK_SESSION[:-1] + ", attaches_to: {link: link-r1-r2}}"))

    def test_ospf_area_is_normalized(self):
        t = parse(_session("- {id: ospf-adj-r1-r2, type: ospf, from: {node: r1, interface: r1-eth0-l3},"
                           " to: {node: r2, interface: r2-eth0-l3}, area: 0}",
                           "  ospf: [{id: ospf-a, nodes: [{node: r1}, {node: r2}]}]\n"))
        assert isinstance(t.control_plane.routing_neighbors[0], OspfAdjacency)
        assert t.control_plane.routing_neighbors[0].area == "0.0.0.0"

    @pytest.mark.parametrize("legacy,expected", [
        ("protocols:\n  bgp: [{id: bgp-a, role: underlay}]\n", ["control_plane に移動", "role は廃止"]),
        ("protocols:\n  bgp: [{id: bgp-a, nodes: [{node: r1, neighbors: [{node: r2, remote_as: 2}]}]}]\n",
         ["neighbors は廃止"]),
        ("layer3:\n  routing_adjacencies: []\n", ["routing_neighbors に移動しました。attaches_to は書かず"]),
    ])
    def test_legacy_keys_point_to_new_place(self, legacy, expected):
        with pytest.raises(PydanticValidationError) as exc:
            parse('ndl_version: "1.0"\n' + legacy)
        for text in expected:
            assert text in str(exc.value)

    def test_link_key_is_removed(self):
        """ADR-0001 の {link:} キーは ADR-0010 で削除"""
        body = BASE.replace("    - {id: r3-eth0, node: r3}", "    - {id: r3-eth0, node: r3, attaches_to: {link: link-r1-r2}}")
        with pytest.raises(PydanticValidationError, match="ADR-0010"):
            parse(body)


# ---------------------------------------------------------------------------
# 導出 (D7・D11)
# ---------------------------------------------------------------------------

class TestDerive:
    def _view(self, body: str):
        (v,) = bgp_session_views(parse(_session(body)))
        return v

    def test_single_hop_link(self):
        v = self._view(OK_SESSION)
        assert v.transport.link == "link-r1-r2" and not v.transport_mismatch
        assert v.bgp_type == "ebgp" and (v.from_.local_as, v.to.local_as) == (65001, 65002)

    def test_lag(self):
        v = self._view("- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r1-po1-l3}, to: {node: r2, update_source: r2-po1-l3}}")
        assert v.transport.lags == ["lag-r1-po1", "lag-r2-po1"]

    def test_loopback_is_multihop(self):
        v = self._view("- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r1-lo}, to: {node: r2, update_source: r2-lo}}")
        assert v.transport is None and not v.transport_mismatch

    def test_svi_has_no_transport(self):
        v = self._view("- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r1-vlan10}, to: {node: r2, update_source: r2-vlan10}}")
        assert v.transport is None and not v.transport_mismatch

    def test_unnumbered(self):
        v = self._view("- {id: bgp-peer-r1-r3, type: bgp, from: {node: r1, update_source: r1-un}, to: {node: r3, update_source: r3-eth0-l3}}")
        assert v.from_.unnumbered and not v.to.unnumbered
        assert v.transport.link == "link-r1-r3"

    def test_ibgp(self):
        v = self._view("- {id: bgp-peer-r1-r3, type: bgp, from: {node: r1, update_source: r1-eth1-l3}, to: {node: r3, update_source: r3-eth0-l3}}")
        assert v.bgp_type == "ibgp"


# ---------------------------------------------------------------------------
# 検査 (D10)
# ---------------------------------------------------------------------------

TWO_INSTANCES = (
    "  bgp:\n"
    "    - {id: bgp-default, nodes: [{node: r1, local_as: 65001}, {node: r2, local_as: 65002}]}\n"
    "    - {id: bgp-a, vrf: vrf-a, nodes: [{node: r1, local_as: 65001}, {node: r2, local_as: 65002}]}\n"
)


class TestChecks:
    def test_instance_required_when_several(self):
        msgs = _msgs(_session(OK_SESSION, TWO_INSTANCES))
        assert len(msgs) == 1 and msgs[0].startswith("control_plane.routing_neighbors[0].instance")

    def test_node_must_be_in_instance(self):
        msgs = _msgs(_session(OK_SESSION, "  bgp:\n    - {id: bgp-default, nodes: [{node: r1, local_as: 65001}]}\n"))
        assert msgs == ["control_plane.routing_neighbors[0].to.node: ノード 'r2' がインスタンス 'bgp-default' の nodes にありません (ADR-0010 D5)"]

    def test_update_source_of_other_node(self):
        msgs = _msgs(_session("- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r2-lo}, to: {node: r2, update_source: r2-eth0-l3}}"))
        assert any(m.startswith("control_plane.routing_neighbors[0].from.update_source: 'r2-lo' はノード 'r2'") for m in msgs)

    def test_vrf_of_update_source(self):
        """VRF-lite の書き間違い: tenant の IF を default のインスタンスで使う"""
        msgs = _msgs(_session("- {id: bgp-peer-r1-r2, type: bgp, instance: bgp-default, from: {node: r1, update_source: r1-a},"
                              " to: {node: r2, update_source: r2-a}}", TWO_INSTANCES))
        assert len(msgs) == 2 and all("VRF 'vrf-a'" in m for m in msgs)
        ok = _session("- {id: bgp-peer-r1-r2-a, type: bgp, instance: bgp-a, from: {node: r1, update_source: r1-a},"
                      " to: {node: r2, update_source: r2-a}}", TWO_INSTANCES)
        assert _msgs(ok) == []

    def test_transport_mismatch(self):
        msgs = _msgs(_session("- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r1-eth1-l3}, to: {node: r2, update_source: r2-eth0-l3}}"))
        assert len(msgs) == 1 and "通り道が食い違います" in msgs[0]
        assert "リンク link-r1-r3" in msgs[0] and "リンク link-r1-r2" in msgs[0]

    def test_svi_on_different_vlans_is_mismatch(self):
        msgs = _msgs(_session("- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r1-vlan10}, to: {node: r2, update_source: r2-vlan20}}"))
        assert len(msgs) == 1 and "VLAN vlan-10" in msgs[0] and "VLAN vlan-20" in msgs[0]

    def test_transport_af(self):
        msgs = _msgs(_session("- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r1-lo}, to: {node: r2, update_source: r2-lo6}}"))
        assert len(msgs) == 1 and "IPv4 と IPv6" in msgs[0]
        msgs = _msgs(_session("- {id: bgp-peer-r1-isp, type: bgp, from: {node: r1, update_source: r1-lo}, to: {address: '2001:db8::99', local_as: 64500}}"))
        assert len(msgs) == 1 and "アドレスファミリーが一致しません" in msgs[0]

    def test_unnumbered_skips_transport_af(self):
        assert _msgs(_session("- {id: bgp-peer-r1-r3, type: bgp, from: {node: r1, update_source: r1-un}, to: {node: r3, update_source: r3-eth0-l3}}")) == []

    def test_duplicate_session(self):
        dup = OK_SESSION + "\n    " + OK_SESSION.replace("bgp-peer-r1-r2", "bgp-peer-r1-r2-again")
        msgs = _msgs(_session(dup))
        assert len(msgs) == 1 and "同じ両端" in msgs[0]

    def test_route_reflector_client_needs_ibgp(self):
        msgs = _msgs(_session("- {id: bgp-peer-r1-r2, type: bgp, from: {node: r1, update_source: r1-eth0-l3},"
                              " to: {node: r2, update_source: r2-eth0-l3, route_reflector_client: true}}"))
        assert len(msgs) == 1 and "iBGP" in msgs[0]

    def test_same_node_two_as_in_instance(self):
        msgs = _msgs(_session(OK_SESSION, "  bgp:\n    - {id: bgp-default, nodes: [{node: r1, local_as: 65001},"
                                          " {node: r1, local_as: 65009}, {node: r2, local_as: 65002}]}\n"))
        assert len(msgs) == 1 and "異なる local_as" in msgs[0]

    def test_two_instances_in_same_vrf(self):
        """underlay / overlay でエントリを分けた旧来の書き方 (ADR-0010 F4・D5)"""
        msgs = _msgs(_session(OK_SESSION.replace("type: bgp,", "type: bgp, instance: bgp-underlay,"),
                              "  bgp:\n    - {id: bgp-underlay, nodes: [{node: r1, local_as: 65001}, {node: r2, local_as: 65002}]}\n"
                              "    - {id: bgp-overlay, nodes: [{node: r1, local_as: 65000}, {node: r2, local_as: 65000}]}\n"))
        assert len(msgs) == 1 and "default VRF の BGP インスタンスが 2 つ以上" in msgs[0]

    def test_evpn_in_tenant_vrf_warns(self):
        body = _session("- {id: bgp-peer-r1-r2-a, type: bgp, instance: bgp-a, from: {node: r1, update_source: r1-a},"
                        " to: {node: r2, update_source: r2-a}, address_families: [l2vpn_evpn]}", TWO_INSTANCES)
        assert _msgs(body) == []
        assert len(_msgs(body, "warning")) == 1

    def test_bfd_needs_timer_nodes(self):
        msgs = _msgs(_session("- {id: bgp-peer-r1-r3, type: bgp, from: {node: r1, update_source: r1-eth1-l3},"
                              " to: {node: r3, update_source: r3-eth0-l3}, bfd: true}"))
        assert len(msgs) == 1 and "r3" in msgs[0]

    def test_ospf_interface_of_other_node(self):
        msgs = _msgs(_session("- {id: ospf-adj-r1-r2, type: ospf, from: {node: r1, interface: r2-eth0-l3},"
                              " to: {node: r2, interface: r2-eth0-l3}, area: 0}",
                              "  ospf: [{id: ospf-a, nodes: [{node: r1}, {node: r2}]}]\n"))
        assert len(msgs) == 1 and msgs[0].startswith("control_plane.routing_neighbors[0].from.interface")


# ---------------------------------------------------------------------------
# fixture とエクスポーター (D11)
# ---------------------------------------------------------------------------

class TestFixturesAndExport:
    @pytest.mark.parametrize("name", ["valid_full_dc.yaml", "valid_multi_vlan.yaml", "valid_multisite_wan.yaml"])
    def test_fixtures_are_valid(self, name):
        assert validate(parse_file(FIXTURES / name)) == []

    def _cy(self, name):
        return cytoscape.export(parse_file(FIXTURES / name))

    def test_one_edge_per_session(self):
        out = self._cy("valid_full_dc.yaml")
        edges = [e["data"] for e in out["edges"] if e["data"]["type"] == "routing_neighbor"]
        assert len(edges) == 8
        assert not [e for e in out["edges"] if e["data"]["type"] in ("bgp_session", "routing_adjacency")]
        underlay = next(e for e in edges if e["id"] == "bgp-peer-spine1-leaf1")
        assert underlay["bgp_type"] == "ebgp" and underlay["transport_link"] == {"link": "link-spine1-leaf1"}
        assert underlay["from"]["ip"] == "10.1.0.0/31" and underlay["from"]["local_as"] == 65000
        assert underlay["to"]["interface_name"] == "swp51"
        overlay = next(e for e in edges if e["id"] == "bgp-peer-spine1-leaf1-overlay")
        assert "transport_link" not in overlay and overlay["address_families"] == ["l2vpn_evpn"]

    def test_unnumbered_in_export(self):
        edge = next(e["data"] for e in self._cy("valid_multi_vlan.yaml")["edges"] if e["data"]["id"] == "bgp-peer-spine1-leaf1")
        assert edge["from"]["unnumbered"] is True and "ip" not in edge["from"]
        assert edge["address_families"] == ["ipv4_unicast", "l2vpn_evpn"]

    def test_outside_peer_is_node_data_only(self):
        out = self._cy("valid_multisite_wan.yaml")
        assert not any(e["data"]["id"] == "bgp-peer-cm-core1-isp" for e in out["edges"])
        core1 = next(n["data"] for n in out["nodes"] if n["data"]["id"] == "cm-core1")
        isp = next(s for s in core1["bgp_sessions"] if s["id"] == "bgp-peer-cm-core1-isp")
        assert isp["peer"] == {"address": "203.0.113.1", "local_as": 64500}
        assert isp["local"]["node"] == "cm-core1" and isp["bgp_type"] == "ebgp"
        assert core1["local_as"] == 65100

    def test_ospf_edge(self):
        edge = next(e["data"] for e in self._cy("valid_multisite_wan.yaml")["edges"]
                    if e["data"].get("protocol") == "ospf")
        assert edge["area"] == "0.0.0.0" and edge["from"]["interface"].endswith("-l3")

    def test_route_reflector_client_in_export(self):
        edge = next(e["data"] for e in self._cy("valid_multisite_wan.yaml")["edges"]
                    if e["data"]["id"] == "bgp-peer-dc-spine1-leaf1")
        assert edge["bgp_type"] == "ibgp" and edge["to"]["route_reflector_client"] is True
