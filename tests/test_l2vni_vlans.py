"""ADR-0026 L2VNI に、機器によって番号の違う VLAN を載せる (vlans) のテスト"""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest

from mlndl import parse, parse_file, validate_all
from mlndl.derive import l2vni_node_vlans, vlan_l2vnis, vlan_port_nodes, vlan_svi_nodes
from mlndl.exporter import cytoscape

FIXTURES = Path(__file__).parent / "fixtures"

# leaf1 / leaf2 は ES で server1 (VLAN 20)、leaf3 は VLAN 30、border1 は SVI だけ (VLAN 30)、bgw1 はポートも SVI もない
BASE = """
ndl_version: "1.0"
layer1:
  nodes: [{id: leaf1}, {id: leaf2}, {id: leaf3}, {id: border1}, {id: bgw1}, {id: server1}, {id: server3}]
  interfaces:
    - {id: leaf1-swp1, node: leaf1}
    - {id: leaf2-swp1, node: leaf2}
    - {id: leaf3-swp1, node: leaf3}
    - {id: server1-eth0, node: server1}
    - {id: server1-eth1, node: server1}
    - {id: server3-eth0, node: server3}
  links:
    - {id: link-leaf1-server1, endpoints: [leaf1-swp1, server1-eth0]}
    - {id: link-leaf2-server1, endpoints: [leaf2-swp1, server1-eth1]}
    - {id: link-leaf3-server3, endpoints: [leaf3-swp1, server3-eth0]}
  lag:
    - {id: lag-leaf1-server1, node: leaf1, members: [leaf1-swp1]}
    - {id: lag-leaf2-server1, node: leaf2, members: [leaf2-swp1]}
  ethernet_segments:
    - {id: es-server1, members: [{lag: lag-leaf1-server1}, {lag: lag-leaf2-server1}]}
layer2:
  vlans:
    - {id: vlan-20, vlan_id: 20, trunk_ports: [{ethernet_segment: es-server1}]}
    - {id: vlan-30, vlan_id: 30, access_ports: [{interface: leaf3-swp1}]}
  vteps:
    - {id: vtep-leaf1-leaf2, sources: [leaf1-lo, leaf2-lo], address: 10.0.100.12/32}
    - {id: vtep-leaf3, sources: [leaf3-lo]}
    - {id: vtep-border1, sources: [border1-lo]}
  vxlan:
    - {id: vni-10020, type: l2vni, vni: 10020, vlans: [vlan-20, vlan-30], vteps: [vtep-leaf1-leaf2, vtep-leaf3, vtep-border1]}
layer3:
  vrfs: [{id: vrf-a}, {id: vrf-b}]
  interfaces:
    - {id: leaf1-lo, node: leaf1, name: lo, ip: 10.0.0.1/32}
    - {id: leaf2-lo, node: leaf2, name: lo, ip: 10.0.0.2/32}
    - {id: leaf3-lo, node: leaf3, name: lo, ip: 10.0.0.3/32}
    - {id: border1-lo, node: border1, name: lo, ip: 10.0.0.4/32}
    - {id: bgw1-lo, node: bgw1, name: lo, ip: 10.0.0.5/32}
    - {id: leaf1-vlan-20, node: leaf1, name: vlan20, attaches_to: {vlan: vlan-20}, ip: 10.20.0.1/24, vrf: vrf-a, gateway_redundancy: [{mode: anycast_gateway}]}
    - {id: leaf2-vlan-20, node: leaf2, name: vlan20, attaches_to: {vlan: vlan-20}, ip: 10.20.0.1/24, vrf: vrf-a, gateway_redundancy: [{mode: anycast_gateway}]}
    - {id: leaf3-vlan-30, node: leaf3, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24, vrf: vrf-a, gateway_redundancy: [{mode: anycast_gateway}]}
    - {id: border1-vlan-30, node: border1, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24, vrf: vrf-a, gateway_redundancy: [{mode: anycast_gateway}]}
"""


def _topo(text: str = BASE):
    return parse(text)


def _issues(text: str = BASE, severity: str = "errors") -> list[str]:
    return [f"{e.path}: {e.message}" for e in getattr(validate_all(_topo(text)), severity)]


def _replace(old: str, new: str, text: str = BASE) -> str:
    assert old in text, old
    return text.replace(old, new)


# ---------------------------------------------------------------------------
# スキーマ (D1・D2)
# ---------------------------------------------------------------------------

class TestSchema:
    def test_base_is_valid(self):
        assert _issues() == []
        assert _issues(severity="warnings") == []

    def test_old_vlan_is_error_with_destination(self):
        with pytest.raises(pydantic.ValidationError, match=r"L2VNI の vlan はなくしました。vlans: \[vlan-20\]"):
            _topo(_replace("vlans: [vlan-20, vlan-30], vteps", "vlan: vlan-20, vteps"))

    def test_vlans_needs_one(self):
        with pytest.raises(pydantic.ValidationError):
            _topo(_replace("vlans: [vlan-20, vlan-30], vteps", "vlans: [], vteps"))

    def test_duplicate_in_vlans_is_type_error(self):
        with pytest.raises(pydantic.ValidationError, match="vlan-20 を 2 回"):
            _topo(_replace("vlans: [vlan-20, vlan-30]", "vlans: [vlan-20, vlan-30, vlan-20]"))

    def test_undefined_vlan_is_ref_error(self):
        errs = _issues(_replace("vlans: [vlan-20, vlan-30]", "vlans: [vlan-20, vlan-99]"))
        assert errs == ["layer2.vxlan[0].vlans[1]: 未定義の VLAN 'vlan-99' を参照しています"]


# ---------------------------------------------------------------------------
# 導き方 (D4)
# ---------------------------------------------------------------------------

class TestDerive:
    def test_port_and_svi_nodes(self):
        t = _topo()
        assert vlan_port_nodes(t) == {"vlan-20": {"leaf1", "leaf2"}, "vlan-30": {"leaf3"}}
        assert vlan_svi_nodes(t) == {"vlan-20": {"leaf1", "leaf2"}, "vlan-30": {"leaf3", "border1"}}

    def test_node_vlans_counts_svi_only_and_skips_bgw(self):
        assert l2vni_node_vlans(_topo())["vni-10020"] == [
            ("leaf1", "vlan-20"), ("leaf2", "vlan-20"), ("border1", "vlan-30"), ("leaf3", "vlan-30"),
        ]

    def test_only_vlans_listed_in_the_l2vni(self):
        """SVI の VLAN を vlans に書き忘れると、その機器の VLAN は決まらない"""
        text = _replace("vlans: [vlan-20, vlan-30]", "vlans: [vlan-20]")
        assert l2vni_node_vlans(_topo(text))["vni-10020"] == [("leaf1", "vlan-20"), ("leaf2", "vlan-20")]

    def test_reverse_lookup(self):
        assert vlan_l2vnis(_topo()) == {"vlan-20": ["vni-10020"], "vlan-30": ["vni-10020"]}


# ---------------------------------------------------------------------------
# 検査 (D5)
# ---------------------------------------------------------------------------

class TestChecks:
    def test_participant_without_vlan_is_warning(self):
        """bgw1 は VTEP で参加するがポートも SVI もない。中継だけの機器を想定した文面の warning"""
        text = _replace("vtep-border1]}\nlayer3", "vtep-border1, vtep-bgw1]}\nlayer3",
                        _replace("    - {id: vtep-border1, sources: [border1-lo]}\n",
                                 "    - {id: vtep-border1, sources: [border1-lo]}\n    - {id: vtep-bgw1, sources: [bgw1-lo]}\n"))
        assert _issues(text) == []
        warns = _issues(text, "warnings")
        assert len(warns) == 1 and "機器 'bgw1' は VTEP で L2VNI 'vni-10020' に参加していますが" in warns[0]
        assert "VNI を中継するだけの機器なら、このままでかまいません" in warns[0]

    def test_svi_only_participant_is_not_warned(self):
        """border1 は SVI だけで参加する。ポートだけで数えた旧来の warning は出ない"""
        assert not any("border1" in w for w in _issues(severity="warnings"))

    def test_one_device_two_vlans(self):
        text = _replace("{id: vlan-30, vlan_id: 30, access_ports: [{interface: leaf3-swp1}]}",
                        "{id: vlan-30, vlan_id: 30, access_ports: [{interface: leaf3-swp1}]}\n"
                        "    - {id: vlan-31, vlan_id: 31, access_ports: [{interface: leaf3-swp2}]}")
        text = _replace("    - {id: leaf3-swp1, node: leaf3}\n",
                        "    - {id: leaf3-swp1, node: leaf3}\n    - {id: leaf3-swp2, node: leaf3}\n", text)
        text = _replace("vlans: [vlan-20, vlan-30]", "vlans: [vlan-20, vlan-30, vlan-31]", text)
        errs = _issues(text)
        assert len(errs) == 1
        assert errs[0].startswith("layer2.vxlan[0].vlans: 機器 'leaf3' に、L2VNI 'vni-10020' の VLAN が 2 つあります"
                                  " (vlan-30 / vlan-31)")

    def test_one_vlan_in_two_l2vnis(self):
        text = _replace("vtep-border1]}\nlayer3",
                        "vtep-border1]}\n    - {id: vni-10021, type: l2vni, vni: 10021, vlans: [vlan-20], vteps: [vtep-leaf3]}\nlayer3")
        errs = _issues(text)
        assert errs == ["layer2.vxlan[1].vlans[0]: VLAN 'vlan-20' は L2VNI 'vni-10020' と 'vni-10021' の両方の vlans "
                        "にあります。1 つの VLAN は 1 つの L2VNI に載せます (ADR-0026 D5)"]

    def test_es_legs_split_into_different_numbers(self):
        """脚を機器ごとの {lag:} で書いて別の番号に分けたら error。「ES の脚の一部だけ」の warning は重ねない"""
        text = _replace("{id: vlan-20, vlan_id: 20, trunk_ports: [{ethernet_segment: es-server1}]}",
                        "{id: vlan-20, vlan_id: 20, trunk_ports: [{lag: lag-leaf1-server1}]}\n"
                        "    - {id: vlan-21, vlan_id: 21, trunk_ports: [{lag: lag-leaf2-server1}]}")
        text = _replace("vlans: [vlan-20, vlan-30]", "vlans: [vlan-20, vlan-21, vlan-30]", text)
        text = _replace("{id: leaf2-vlan-20, node: leaf2, name: vlan20, attaches_to: {vlan: vlan-20}",
                        "{id: leaf2-vlan-21, node: leaf2, name: vlan21, attaches_to: {vlan: vlan-21}", text)
        errs = _issues(text)
        assert len(errs) == 1 and "Ethernet Segment 'es-server1' の脚が、L2VNI 'vni-10020' の番号の違う VLAN" in errs[0]
        assert "vlan-20 (20) / vlan-21 (21)" in errs[0]
        assert _issues(text, "warnings") == []

    def test_svi_vrf_mismatch(self):
        text = _replace("{id: leaf3-vlan-30, node: leaf3, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24, vrf: vrf-a",
                        "{id: leaf3-vlan-30, node: leaf3, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24, vrf: vrf-b")
        assert _issues(text) == [
            "layer2.vxlan[0].vlans: L2VNI 'vni-10020' の SVI の vrf が食い違っています: 'leaf1-vlan-20' は vrf-a、"
            "'leaf3-vlan-30' は vrf-b。同じブロードキャストドメインのゲートウェイは同じ VRF に置きます (ADR-0026 D5)"
        ]

    def test_same_number_twice_is_warning(self):
        text = _replace("{id: vlan-30, vlan_id: 30,", "{id: vlan-30, vlan_id: 20,")
        warns = _issues(text, "warnings")
        assert any("番号 20 の VLAN が 2 つあります (vlan-20 / vlan-30)" in w for w in warns)

    def test_port_and_svi_with_same_number_on_one_device(self):
        """ポートで vlan-20 (20) を持つ leaf1 が、SVI で別エントリの番号 20 を指したら、同じ機器での重複"""
        text = _replace("    - {id: vlan-30, vlan_id: 30, access_ports: [{interface: leaf3-swp1}]}\n",
                        "    - {id: vlan-30, vlan_id: 30, access_ports: [{interface: leaf3-swp1}]}\n"
                        "    - {id: vlan-20b, vlan_id: 20, access_ports: [{interface: leaf3-swp2}]}\n")
        text = _replace("    - {id: leaf3-swp1, node: leaf3}\n",
                        "    - {id: leaf3-swp1, node: leaf3}\n    - {id: leaf3-swp2, node: leaf3}\n", text)
        text += "    - {id: leaf1-vlan-20b, node: leaf1, name: vlan20b, attaches_to: {vlan: vlan-20b}, ip: 10.21.0.1/24}\n"
        errs = _issues(text)
        assert any("ノード 'leaf1' 上で VLAN ID 20 が重複しています (vlan-20 / vlan-20b)" in e
                   and "SVI が vlan-20b を指しています" in e for e in errs)


# ---------------------------------------------------------------------------
# anycast gateway (D6)
# ---------------------------------------------------------------------------

class TestAnycast:
    def test_mismatch_across_vlans_of_one_l2vni(self):
        text = _replace("{id: leaf3-vlan-30, node: leaf3, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24",
                        "{id: leaf3-vlan-30, node: leaf3, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.2/24")
        assert _issues(text) == [
            "layer3.interfaces[7].ip: L2VNI 'vni-10020' の anycast gateway で ip が食い違っています: "
            "'leaf3-vlan-30' (VLAN 'vlan-30') は 10.20.0.2/24、'leaf1-vlan-20' (VLAN 'vlan-20') は 10.20.0.1/24。"
            "anycast gateway は VNI のすべての機器で同じアドレスにします (ADR-0026 D6)"
        ]

    def test_vlan_outside_l2vni_is_checked_per_vlan(self):
        text = _replace("vlans: [vlan-20, vlan-30]", "vlans: [vlan-20]")
        # vlan-30 は L2VNI の外。leaf3 と border1 で比べ、vlan-20 とは比べない
        text = _replace("{id: border1-vlan-30, node: border1, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24",
                        "{id: border1-vlan-30, node: border1, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.30.0.1/24",
                        _replace("{id: leaf3-vlan-30, node: leaf3, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24",
                                 "{id: leaf3-vlan-30, node: leaf3, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.30.0.1/24",
                                 text))
        assert _issues(text) == []

    def test_anycast_and_vrrp_mixed_is_warning(self):
        text = _replace(
            "{id: border1-vlan-30, node: border1, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24, vrf: vrf-a, gateway_redundancy: [{mode: anycast_gateway}]}",
            "{id: border1-vlan-30, node: border1, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.2/24, vrf: vrf-a, gateway_redundancy: [{mode: vrrp, group_id: 1, vip: 10.20.0.1}]}")
        assert _issues(text) == []
        warns = _issues(text, "warnings")
        assert len(warns) == 1 and "L2VNI 'vni-10020' のゲートウェイで" in warns[0] and "は vrrp です" in warns[0]

    def test_svi_without_redundancy_is_not_mixed(self):
        """冗長を持たない SVI (管理用など) は混在に数えない"""
        text = BASE + "    - {id: leaf3-vlan-30-mgmt, node: leaf3, name: mgmt, attaches_to: {vlan: vlan-30}, ip: 10.20.0.9/24}\n"
        assert not any("ゲートウェイで" in w for w in _issues(text, "warnings"))


# ---------------------------------------------------------------------------
# エクスポーター (D7) と fixture
# ---------------------------------------------------------------------------

class TestExport:
    def test_l2vni_node_has_vlans_and_node_vlans(self):
        out = cytoscape.export(_topo())
        vni = next(n["data"] for n in out["nodes"] if n["data"]["id"] == "vni-10020")
        assert vni["vlans"] == ["vlan-20", "vlan-30"] and "vlan" not in vni
        assert vni["node_vlans"] == [
            {"node": "leaf1", "vlan": "vlan-20"}, {"node": "leaf2", "vlan": "vlan-20"},
            {"node": "border1", "vlan": "vlan-30"}, {"node": "leaf3", "vlan": "vlan-30"},
        ]

    def test_device_vlans_stay_port_based(self):
        """機器ノードの vlans と vlan_member エッジはポートだけ (SVI だけの border1 は載らない)"""
        out = cytoscape.export(_topo())
        nodes = {n["data"]["id"]: n["data"] for n in out["nodes"]}
        assert "vlans" not in nodes["border1"]
        members = {(e["data"]["source"], e["data"]["target"]) for e in out["edges"] if e["data"].get("type") == "vlan_member"}
        assert ("vlan-30", "border1") not in members and ("vlan-30", "leaf3") in members


@pytest.mark.parametrize("name", ["valid_l2vni_mixed_vlans.yaml", "valid_l2vni_svi_only.yaml"])
def test_fixtures(name):
    result = validate_all(parse_file(FIXTURES / name))
    assert result.errors == [] and result.warnings == []
