"""ADR-0011 layer3 データプレーンのテスト

D3 SVI 参照の一本化 / D4 gateway_redundancy / D5 ip・ipv6 / D6 トンネル / D7 description / D9 検証規則
"""

from __future__ import annotations

import json

import pydantic
import pytest
import yaml

from mlndl import parse, validate, validate_all
from mlndl.exporter import cytoscape, yaml as yaml_exporter


def _topo(body: str):
    return parse('ndl_version: "1.0"\n' + body)


def _errors(body: str) -> list[str]:
    return [str(e) for e in validate(_topo(body))]


def _parse_error(body: str) -> str:
    with pytest.raises(pydantic.ValidationError) as exc:
        _topo(body)
    return str(exc.value)


BASE = """
layer1:
  nodes: [{id: leaf1}, {id: leaf2}]
  interfaces:
    - {id: leaf1-swp1, node: leaf1, name: swp1}
    - {id: leaf1-swp2, node: leaf1, name: swp2}
    - {id: leaf2-swp1, node: leaf2, name: swp1}
layer2:
  vlans:
    - {id: vlan-100, vlan_id: 100, trunk_ports: [{node: leaf1, interface: leaf1-swp1}]}
    - {id: vlan-200, vlan_id: 200, trunk_ports: [{node: leaf1, interface: leaf1-swp1}]}
"""


def _l3(interfaces: str, extra: str = "") -> str:
    return BASE + "layer3:\n  vrfs: [{id: vrf-a}]\n  interfaces:\n" + interfaces + extra


# ---------------------------------------------------------------------------
# D5: ip は IPv4、ipv6 は IPv6
# ---------------------------------------------------------------------------

class TestAddressing:
    def test_dual_stack_parses(self):
        t = _topo(_l3("    - {id: l1, node: leaf1, interface: lo, ip: 10.0.0.1/32, ipv6: 2001:db8::1/128}\n"))
        iface = t.layer3.interfaces[0]
        assert str(iface.ip) == "10.0.0.1/32"
        assert str(iface.ipv6) == "2001:db8::1/128"

    def test_ipv6_only_is_valid(self):
        assert _errors(_l3("    - {id: l1, node: leaf1, interface: lo, ipv6: 2001:db8::1/128}\n")) == []

    def test_no_address_is_valid(self):
        """unnumbered や L2 専用の IF があるため、ip / ipv6 とも未指定を許す"""
        assert _errors(_l3("    - {id: l1, node: leaf1, interface: swp9}\n")) == []

    def test_ipv6_in_ip_points_to_ipv6_field(self):
        msg = _parse_error(_l3("    - {id: l1, node: leaf1, interface: lo, ip: '2001:db8::1/64'}\n"))
        assert "ipv6 に書いてください" in msg

    @pytest.mark.parametrize("bad", ["not-an-ip-address", "10.0.0.1/33", "300.0.0.1/24"])
    def test_invalid_ipv4_is_rejected(self, bad):
        """F2 / F4: 旧実装では validate も export も通っていた"""
        _parse_error(_l3(f"    - {{id: l1, node: leaf1, interface: lo, ip: '{bad}'}}\n"))

    def test_ipv4_in_ipv6_is_rejected(self):
        _parse_error(_l3("    - {id: l1, node: leaf1, interface: lo, ipv6: 10.0.0.1/32}\n"))


# ---------------------------------------------------------------------------
# D3: SVI の参照は attaches_to に一本化
# ---------------------------------------------------------------------------

class TestSviReference:
    def test_shorthand_resolves_to_vlan(self):
        assert _errors(_l3("    - {id: s1, node: leaf1, interface: vlan-100, ip: 192.168.100.1/24}\n")) == []

    def test_shorthand_to_undefined_vlan_is_error(self):
        """F3: 旧実装は interface: vlan-999 を参照解決していなかった"""
        errs = _errors(_l3("    - {id: s1, node: leaf1, interface: vlan-999}\n"))
        assert any("vlan-999" in e and "定義されていません" in e for e in errs)

    def test_attaches_to_vlan_is_accepted(self):
        """F3: ADR-0005 D2-2 の正規形。旧実装では「未定義のインターフェース」で error になっていた"""
        assert _errors(_l3(
            "    - {id: s1, node: leaf1, interface: Vlan100, attaches_to: {interface: vlan-100}}\n"
        )) == []

    def test_l1_attaches_to_cannot_point_at_vlan(self):
        """VLAN を参照先として許すのは L3Interface だけ"""
        body = BASE.replace(
            "    - {id: leaf2-swp1, node: leaf2, name: swp1}",
            "    - {id: leaf2-swp1, node: leaf2, name: swp1, attaches_to: {interface: vlan-100}}",
        )
        assert any("vlan-100" in e for e in _errors(body))

    def test_shorthand_and_attaches_to_mismatch_is_error(self):
        errs = _errors(_l3(
            "    - {id: s1, node: leaf1, interface: vlan-100, attaches_to: {interface: vlan-200}}\n"
        ))
        assert any("食い違って" in e for e in errs)

    def test_device_style_name_without_attaches_to_warns(self):
        r = validate_all(_topo(_l3("    - {id: s1, node: leaf1, interface: Vlan100}\n")))
        assert r.errors == []
        assert [w.path for w in r.warnings] == ["layer3.interfaces[0].attaches_to"]

    def test_normalization_is_not_written_back(self):
        """短縮形を attaches_to に書き戻すと YAML の往復で入力にないキーが現れる"""
        t = _topo(_l3("    - {id: s1, node: leaf1, interface: vlan-100}\n"))
        assert t.layer3.interfaces[0].attaches_to is None
        assert "attaches_to" not in yaml_exporter.export(t)

    @pytest.mark.parametrize("key,hint", [("vlan", "attaches_to"), ("fhrp", "gateway_redundancy")])
    def test_legacy_keys_point_to_replacement(self, key, hint):
        value = "vlan-100" if key == "vlan" else "[{protocol: vrrp, group_id: 1, vip: 192.168.100.254}]"
        msg = _parse_error(_l3(f"    - {{id: s1, node: leaf1, interface: vlan-100, {key}: {value}}}\n"))
        assert hint in msg and "ADR-0011" in msg

    def test_legacy_protocol_key_points_to_mode(self):
        msg = _parse_error(_l3(
            "    - id: s1\n      node: leaf1\n      interface: vlan-100\n"
            "      gateway_redundancy: [{protocol: vrrp, group_id: 1, vip: 192.168.100.254}]\n"
        ))
        assert "mode に改名" in msg


# ---------------------------------------------------------------------------
# D9: 黙って通っていた矛盾
# ---------------------------------------------------------------------------

class TestSilentContradictions:
    def test_l3_attaches_to_other_nodes_interface(self):
        errs = _errors(_l3(
            "    - {id: r1, node: leaf1, interface: swp1, attaches_to: {interface: leaf2-swp1}}\n"
        ))
        assert any("leaf2" in e and "のものではありません" in e for e in errs)

    def test_trunk_port_on_other_nodes_interface(self):
        body = BASE.replace(
            "{id: vlan-200, vlan_id: 200, trunk_ports: [{node: leaf1, interface: leaf1-swp1}]}",
            "{id: vlan-200, vlan_id: 200, trunk_ports: [{node: leaf1, interface: leaf2-swp1}]}",
        )
        errs = _errors(body)
        assert any("trunk_ports[0].interface" in e and "leaf2" in e for e in errs)

    def test_duplicate_node_interface(self):
        errs = _errors(_l3(
            "    - {id: a, node: leaf1, interface: lo, ip: 10.0.0.1/32}\n"
            "    - {id: b, node: leaf1, interface: lo, ip: 10.0.0.2/32}\n"
        ))
        assert any("重複して定義" in e for e in errs)

    def test_vrf_l3vni_bidirectional_mismatch(self):
        body = BASE + """  vxlan:
    - {id: vni-1, type: l3vni, vni: 10001, vrf: vrf-a}
    - {id: vni-2, type: l3vni, vni: 10002, vrf: vrf-b}
layer3:
  vrfs:
    - {id: vrf-a, l3vni: vni-2}
    - {id: vrf-b, l3vni: vni-1}
"""
        paths = {e.path for e in validate(_topo(body))}
        # VRF → L3VNI 方向と L3VNI → VRF 方向を、それぞれ独立に検出すること
        assert {"layer3.vrfs[0].l3vni", "layer3.vrfs[1].l3vni"} <= paths
        assert {"layer2.vxlan[0].vrf", "layer2.vxlan[1].vrf"} <= paths

    def test_vtep_source_node_not_in_members(self):
        body = _l3("    - {id: leaf2-lo, node: leaf2, interface: lo, ip: 10.0.0.2/32}\n").replace(
            "layer3:",
            "  vxlan:\n    - {id: vni-10100, type: l2vni, vni: 10100, vlan: vlan-100,"
            " vtep_source: leaf2-lo, members: [leaf1]}\nlayer3:",
        )
        assert any("members に含まれていません" in e for e in _errors(body))


# ---------------------------------------------------------------------------
# D4: gateway_redundancy
# ---------------------------------------------------------------------------

def _svi(gw: str, ip: str = "ip: 192.168.100.2/24", ipv6: str = "") -> str:
    extra = f"\n      {ipv6}" if ipv6 else ""
    return _l3(
        f"    - id: s1\n      node: leaf1\n      interface: vlan-100\n      {ip}{extra}\n"
        f"      gateway_redundancy:\n{gw}"
    )


class TestGatewayRedundancy:
    def test_vrrp_v4(self):
        assert _errors(_svi("        - {mode: vrrp, group_id: 10, vip: 192.168.100.1}\n")) == []

    def test_dual_stack_vrrp_uses_two_entries(self):
        assert _errors(_svi(
            "        - {mode: vrrp, group_id: 10, vip: 192.168.100.1}\n"
            "        - {mode: vrrp, group_id: 10, vip: 'fe80::1'}\n",
            ipv6="ipv6: 2001:db8:100::2/64",
        )) == []

    @pytest.mark.parametrize("mode", ["vrrp", "hsrp"])
    def test_ipv6_vip_must_be_link_local(self, mode):
        """RFC 5798 §5.2.9 / §6.1"""
        msg = _parse_error(_svi(f"        - {{mode: {mode}, group_id: 10, vip: '2001:db8:100::1'}}\n"))
        assert "リンクローカル" in msg

    def test_duplicate_group_same_af(self):
        errs = _errors(_svi(
            "        - {mode: vrrp, group_id: 10, vip: 192.168.100.1}\n"
            "        - {mode: vrrp, group_id: 10, vip: 192.168.100.3}\n"
        ))
        assert any("group_id 10" in e for e in errs)

    def test_ipv4_vip_outside_subnet(self):
        errs = _errors(_svi("        - {mode: vrrp, group_id: 10, vip: 10.9.9.9}\n"))
        assert any("サブネット" in e for e in errs)

    @pytest.mark.parametrize("gid", [0, 256])
    def test_vrrp_group_id_range(self, gid):
        _parse_error(_svi(f"        - {{mode: vrrp, group_id: {gid}, vip: 192.168.100.1}}\n"))

    def test_anycast_gateway(self):
        assert _errors(_svi("        - {mode: anycast_gateway, anycast_mac: '44:38:39:be:ef:aa'}\n")) == []

    def test_anycast_rejects_group_id(self):
        """単一モデルで optional にすると通ってしまう組み合わせ。Tagged Union で弾く"""
        _parse_error(_svi("        - {mode: anycast_gateway, group_id: 10}\n"))

    def test_anycast_mac_format(self):
        _parse_error(_svi("        - {mode: anycast_gateway, anycast_mac: not-a-mac}\n"))

    def test_mode_anycast_short_name_is_rejected(self):
        _parse_error(_svi("        - {mode: anycast}\n"))


# ---------------------------------------------------------------------------
# D6: トンネル
# ---------------------------------------------------------------------------

TUNNEL_BASE = _l3(
    "    - {id: leaf1-wan, node: leaf1, interface: swp2, ip: 203.0.113.1/30}\n"
    "    - {id: leaf2-wan, node: leaf2, interface: swp1, ip: 203.0.113.2/30}\n"
)


def _tun(*entries: str) -> str:
    return TUNNEL_BASE + "  tunnel_interfaces:\n" + "".join(entries)


T1 = "    - {id: tunnel-leaf1, node: leaf1, type: gre, source: leaf1-wan, destination_interface: leaf2-wan, ip: 172.31.0.1/30}\n"
T2 = "    - {id: tunnel-leaf2, node: leaf2, type: gre, source: leaf2-wan, destination_interface: leaf1-wan, ip: 172.31.0.2/30}\n"


class TestTunnels:
    def test_internal_pair_is_valid(self):
        assert _errors(_tun(T1, T2)) == []

    def test_external_peer(self):
        assert _errors(_tun(
            "    - {id: tunnel-isp, node: leaf1, type: ipsec_vti, source: leaf1-wan, destination_ip: 198.51.100.9}\n"
        )) == []

    @pytest.mark.parametrize("dest", ["", ", destination_ip: 198.51.100.9, destination_interface: leaf2-wan"])
    def test_destination_is_exactly_one(self, dest):
        msg = _parse_error(_tun(f"    - {{id: tunnel-x, node: leaf1, type: gre, source: leaf1-wan{dest}}}\n"))
        assert "どちらか一方" in msg

    def test_source_must_be_on_same_node(self):
        errs = _errors(_tun(
            "    - {id: tunnel-x, node: leaf1, type: gre, source: leaf2-wan, destination_ip: 198.51.100.9}\n"
        ))
        assert any("source" in e and "leaf2" in e for e in errs)

    def test_undefined_refs(self):
        errs = _errors(_tun(
            "    - {id: tunnel-x, node: leaf1, type: gre, source: leaf1-wan,"
            " destination_interface: nope, vrf: vrf-x, transport_vrf: vrf-y}\n"
        ))
        joined = " ".join(errs)
        assert "nope" in joined and "vrf-x" in joined and "vrf-y" in joined

    def test_prefix_warning(self):
        r = validate_all(_topo(_tun(
            "    - {id: gre0, node: leaf1, type: gre, source: leaf1-wan, destination_ip: 198.51.100.9}\n"
        )))
        assert [w.path for w in r.warnings] == ["layer3.tunnel_interfaces[0].id"]

    def test_unknown_type_rejected(self):
        _parse_error(_tun(
            "    - {id: tunnel-x, node: leaf1, type: dmvpn, source: leaf1-wan, destination_ip: 198.51.100.9}\n"
        ))


# ---------------------------------------------------------------------------
# D7: description
# ---------------------------------------------------------------------------

def test_description_on_every_entity():
    t = _topo("""
layer1:
  nodes: [{id: n1, description: d}]
  interfaces: [{id: n1-e0, node: n1, description: d}, {id: n1-e1, node: n1}]
  links: []
  lag: [{id: lag-n1, type: lacp, node: n1, members: [n1-e0, n1-e1], description: d}]
layer2:
  vlans: [{id: vlan-10, vlan_id: 10, description: d}]
layer3:
  vrfs: [{id: vrf-a, description: d}]
  interfaces:
    - id: n1-lo
      node: n1
      interface: lo
      description: d
""")
    assert validate(t) == []


# ---------------------------------------------------------------------------
# エクスポーター
# ---------------------------------------------------------------------------

class TestExport:
    def test_cytoscape_serializes_typed_addresses(self):
        """IPv4Interface はそのままでは json.dumps できない (TypeError)"""
        t = _topo(_l3(
            "    - {id: l1, node: leaf1, interface: lo, ip: 10.0.0.1/32, ipv6: 2001:db8::1/128}\n"
            "    - {id: s1, node: leaf1, interface: Vlan100, ip: 192.168.100.1/24,"
            " ipv6: 2001:db8:100::1/64, attaches_to: {interface: vlan-100}}\n"
        ))
        out = json.loads(cytoscape.export_json(t))
        leaf1 = next(n["data"] for n in out["nodes"] if n["data"]["id"] == "leaf1")
        assert leaf1["lo_ip"] == "10.0.0.1/32"
        assert leaf1["lo_ipv6"] == "2001:db8::1/128"
        svi = next(x for x in leaf1["l3_interfaces"] if x["interface"] == "Vlan100")
        assert svi["kind"] == "svi" and svi["vlan"] == "vlan-100"
        vlan = next(n["data"] for n in out["nodes"] if n["data"]["id"] == "vlan-100")
        assert vlan["subnet"] == "192.168.100.0/24"
        assert vlan["subnet_v6"] == "2001:db8:100::/64"

    def test_cytoscape_derives_one_tunnel_edge_per_pair(self):
        out = cytoscape.export(_topo(_tun(T1, T2)))
        tunnels = [e["data"] for e in out["edges"] if e["data"]["type"] == "tunnel"]
        assert len(tunnels) == 1
        assert {tunnels[0]["source"], tunnels[0]["target"]} == {"leaf1", "leaf2"}

    def test_yaml_round_trip(self):
        """D11: 往復で model_dump() が一致すること"""
        t1 = _topo(_tun(T1, T2).replace(
            "    - {id: leaf1-wan,",
            "    - id: s1\n      node: leaf1\n      interface: vlan-100\n"
            "      ip: 192.168.100.2/24\n      ipv6: 2001:db8:100::2/64\n"
            "      gateway_redundancy:\n"
            "        - {mode: vrrp, group_id: 10, vip: 192.168.100.1}\n"
            "        - {mode: vrrp, group_id: 10, vip: 'fe80::1'}\n"
            "    - {id: leaf1-wan,",
        ))
        t2 = parse(yaml_exporter.export(t1))
        assert t1.model_dump() == t2.model_dump()
        assert yaml.safe_load(yaml_exporter.export(t1)) == yaml.safe_load(yaml_exporter.export(t2))


# ---------------------------------------------------------------------------
# ラウンド4 Pass B で見つかった検出漏れ (evaluations/round4-evaluation.md E1〜E4)
# ---------------------------------------------------------------------------

def _anycast_pair(ip2: str = "192.168.100.1/24", mac2: str = "44:38:39:be:ef:aa",
                  ipv6_2: str = "2001:db8:100::1/64", vlan2: str = "vlan-100") -> str:
    return _l3(
        "    - id: leaf1-vlan-100\n      node: leaf1\n      interface: vlan-100\n"
        "      ip: 192.168.100.1/24\n      ipv6: 2001:db8:100::1/64\n"
        "      gateway_redundancy: [{mode: anycast_gateway, anycast_mac: '44:38:39:be:ef:aa'}]\n"
        f"    - id: leaf2-svi\n      node: leaf2\n      interface: Vlan100\n"
        f"      attaches_to: {{interface: {vlan2}}}\n      ip: {ip2}\n      ipv6: {ipv6_2}\n"
        f"      gateway_redundancy: [{{mode: anycast_gateway, anycast_mac: '{mac2}'}}]\n"
    )


class TestAnycastConsistency:
    """E1: anycast gateway は全ノードが同じアドレスと MAC で応答する"""

    def test_consistent_pair(self):
        assert _errors(_anycast_pair()) == []

    def test_mac_notation_does_not_matter(self):
        assert _errors(_anycast_pair(mac2="4438.39be.efaa")) == []

    @pytest.mark.parametrize("kw,field", [
        ({"ip2": "192.168.100.9/24"}, "layer3.interfaces[1].ip"),
        ({"ipv6_2": "2001:db8:100::9/64"}, "layer3.interfaces[1].ipv6"),
        ({"mac2": "44:38:39:be:ef:bb"}, "layer3.interfaces[1].gateway_redundancy[0].anycast_mac"),
    ])
    def test_mismatch_is_error(self, kw, field):
        errs = validate(_topo(_anycast_pair(**kw)))
        assert [e.path for e in errs] == [field]

    def test_different_vlans_are_not_compared(self):
        assert _errors(_anycast_pair(ip2="192.168.200.1/24", ipv6_2="2001:db8:200::1/64", vlan2="vlan-200")) == []

    def test_vrrp_svis_are_not_compared(self):
        """VRRP では各ノードが別の実 IP を持つのが正しい"""
        body = _l3(
            "    - {id: s1, node: leaf1, interface: vlan-100, ip: 192.168.100.2/24,"
            " gateway_redundancy: [{mode: vrrp, group_id: 10, vip: 192.168.100.1}]}\n"
            "    - {id: s2, node: leaf2, interface: Vlan100, attaches_to: {interface: vlan-100},"
            " ip: 192.168.100.3/24, gateway_redundancy: [{mode: vrrp, group_id: 10, vip: 192.168.100.1}]}\n"
        )
        assert _errors(body) == []


class TestTunnelGaps:
    def test_destination_on_same_node_is_error(self):
        """E2: 対向に自分のノードの IF を指すと、エクスポーターは辺を黙って捨てていた"""
        body = TUNNEL_BASE.replace(
            "    - {id: leaf2-wan,",
            "    - {id: leaf1-lo, node: leaf1, interface: lo, ip: 10.0.0.1/32}\n    - {id: leaf2-wan,",
        ) + "  tunnel_interfaces:\n" + (
            "    - {id: tunnel-x, node: leaf1, type: gre, source: leaf1-wan, destination_interface: leaf1-lo}\n"
        )
        errs = validate(_topo(body))
        assert [e.path for e in errs] == ["layer3.tunnel_interfaces[0].destination_interface"]

    def test_outer_af_mismatch_with_destination_ip(self):
        """E3: IPv4 だけの source から IPv6 の宛先へはトンネルを組めない"""
        errs = validate(_topo(_tun(
            "    - {id: tunnel-x, node: leaf1, type: gre, source: leaf1-wan, destination_ip: '2001:db8::9'}\n"
        )))
        assert [e.path for e in errs] == ["layer3.tunnel_interfaces[0].source"]
        assert "IPv4" in errs[0].message and "IPv6" in errs[0].message

    def test_outer_af_mismatch_with_destination_interface(self):
        body = TUNNEL_BASE.replace(
            "    - {id: leaf2-wan, node: leaf2, interface: swp1, ip: 203.0.113.2/30}",
            "    - {id: leaf2-wan, node: leaf2, interface: swp1, ipv6: '2001:db8:f::2/64'}",
        ) + "  tunnel_interfaces:\n" + T1
        assert [e.path for e in validate(_topo(body))] == ["layer3.tunnel_interfaces[0].source"]

    def test_dual_stack_source_matches_either_af(self):
        body = TUNNEL_BASE.replace(
            "ip: 203.0.113.1/30}", "ip: 203.0.113.1/30, ipv6: '2001:db8:f::1/64'}",
        ) + "  tunnel_interfaces:\n" + (
            "    - {id: tunnel-x, node: leaf1, type: gre, source: leaf1-wan, destination_ip: '2001:db8::9'}\n"
        )
        assert _errors(body) == []


class TestShorthandMismatchWithNonVlan:
    def test_shorthand_with_l1_attaches_to_is_error(self):
        """E4: interface: vlan-100 は VLAN の短縮形として読まれる。L1 IF を指す attaches_to と食い違う"""
        errs = validate(_topo(_l3(
            "    - {id: s1, node: leaf1, interface: vlan-100, attaches_to: {interface: leaf1-swp2}}\n"
        )))
        assert [e.path for e in errs] == ["layer3.interfaces[0].attaches_to"]
        assert "leaf1-swp2" in errs[0].message

    def test_shorthand_with_same_vlan_is_fine(self):
        assert _errors(_l3(
            "    - {id: s1, node: leaf1, interface: vlan-100, attaches_to: {interface: vlan-100}}\n"
        )) == []
