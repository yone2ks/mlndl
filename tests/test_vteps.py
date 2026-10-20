"""ADR-0014 VXLAN トンネル端点 (layer2.vteps) のテスト"""

from __future__ import annotations

import pydantic
import pytest
import yaml

from mlndl import parse, validate, validate_all
from mlndl.exporter import cytoscape, yaml as yaml_exporter


L1 = """
layer1:
  nodes: [{id: leaf1}, {id: leaf2}, {id: leaf3}, {id: border1}]
  interfaces:
    - {id: leaf1-swp1, node: leaf1}
    - {id: leaf2-swp1, node: leaf2}
    - {id: leaf1-swp49, node: leaf1}
    - {id: leaf2-swp49, node: leaf2}
  lag:
    - {id: lag-peer, type: lacp, node: leaf1, members: [leaf1-swp49]}
    - id: lag-mlag-a
      type: mlag
      nodes: [leaf1, leaf2]
      members: [leaf1-swp1, leaf2-swp1]
      peer_link: lag-peer
      peer_link_interface: peerlink.4094
"""

L3 = """
layer3:
  interfaces:
    - {id: leaf1-lo1, node: leaf1, name: lo1, ip: 10.0.0.11/32}
    - {id: leaf2-lo1, node: leaf2, name: lo1, ip: 10.0.0.12/32}
    - {id: leaf3-lo1, node: leaf3, name: lo1, ip: 10.0.0.13/32}
    - {id: leaf3-lo2, node: leaf3, name: lo2, ip: 10.0.0.23/32}
    - {id: border1-lo1, node: border1, name: lo1, ip: 10.0.0.21/32, ipv6: '2001:db8::21/128'}
    - {id: border1-lo9, node: border1, name: lo9}
"""

MLAG_A = "    - {id: vtep-mlag-a, sources: [leaf1-lo1, leaf2-lo1], address: 10.0.100.12/32}\n"


def _topo(*vteps: str, vxlan: str = ""):
    body = 'ndl_version: "1.0"\n' + L1 + "layer2:\n  vlans: [{id: vlan-100, vlan_id: 100}]\n"
    body += "  vteps:\n" + "".join(vteps)
    if vxlan:
        body += "  vxlan:\n" + vxlan
    return parse(body + L3)


def _errors(*vteps: str, vxlan: str = "") -> list[str]:
    return [str(e) for e in validate(_topo(*vteps, vxlan=vxlan))]


# ---------------------------------------------------------------------------
# スキーマ
# ---------------------------------------------------------------------------

class TestSchema:
    def test_shared_vtep(self):
        v = _topo(MLAG_A).layer2.vteps[0]
        assert v.sources == ["leaf1-lo1", "leaf2-lo1"] and str(v.address) == "10.0.100.12/32"

    def test_shared_vtep_needs_address(self):
        """共有するアドレスは省略できない。省略できるのは sources が 1 つのときだけ"""
        with pytest.raises(pydantic.ValidationError, match="sources が 1 つのときだけ"):
            _topo("    - {id: vtep-x, sources: [leaf1-lo1, leaf2-lo1]}\n")

    def test_shared_vtep_with_only_ipv6_address(self):
        _topo("    - {id: vtep-x, sources: [leaf1-lo1, leaf2-lo1], address_v6: '2001:db8::100/128'}\n")

    def test_ipv6_in_address_points_to_address_v6(self):
        with pytest.raises(pydantic.ValidationError, match="address_v6"):
            _topo("    - {id: vtep-x, sources: [border1-lo1], address: '2001:db8::1/128'}\n")

    def test_sources_must_not_be_empty(self):
        with pytest.raises(pydantic.ValidationError):
            _topo("    - {id: vtep-x, sources: []}\n")

    @pytest.mark.parametrize("key", ["type: anycast", "anycast_ip: 10.0.100.12/32", "node: leaf1"])
    def test_no_mechanism_or_node_fields(self, key):
        """方式名は構文に出さない。ノードは sources から決まる (ADR-0014 D1)"""
        with pytest.raises(pydantic.ValidationError):
            _topo(f"    - {{id: vtep-x, sources: [border1-lo1], {key}}}\n")


# ---------------------------------------------------------------------------
# 書けるもの
# ---------------------------------------------------------------------------

class TestValid:
    @pytest.mark.parametrize("vteps", [
        MLAG_A,                                                                  # 2 ノードで共有
        "    - {id: vtep-border1, sources: [border1-lo1]}\n",                    # 1 ノード。アドレスは lo の ip
        "    - {id: vtep-border1, sources: [border1-lo1], address: 10.0.0.21/32}\n",   # 書いても lo の ip と同じなら可
        "    - {id: vtep-border1, sources: [border1-lo9], address: 10.0.0.99/32}\n",    # lo に ip がなくても address があれば可
        "    - {id: vtep-three, sources: [leaf1-lo1, leaf2-lo1, leaf3-lo1], address: 10.0.9.1/32}\n",  # 3 ノード (BGW など)
    ])
    def test_valid_without_warnings(self, vteps):
        r = validate_all(_topo(vteps))
        assert r.errors == [] and r.warnings == []

    def test_node_can_terminate_two_vteps(self):
        """1 ノードが複数の VTEP を終端する構成 (Multi-Site BGW 等) は、別の L3 IF で書く"""
        r = validate_all(_topo(
            "    - {id: vtep-leaf3, sources: [leaf3-lo1]}\n",
            "    - {id: vtep-leaf3-ms, sources: [leaf3-lo2]}\n",
        ))
        assert r.errors == [] and r.warnings == []

    def test_vni_on_vteps(self):
        r = validate_all(_topo(
            MLAG_A, "    - {id: vtep-border1, sources: [border1-lo1]}\n",
            vxlan="    - {id: vni-10100, type: l2vni, vni: 10100, vlan: vlan-100, vteps: [vtep-mlag-a, vtep-border1]}\n",
        ))
        assert r.errors == [] and r.warnings == []


# ---------------------------------------------------------------------------
# error / warning
# ---------------------------------------------------------------------------

class TestChecks:
    def test_undefined_source(self):
        errs = _errors("    - {id: vtep-x, sources: [nope]}\n")
        assert len(errs) == 1 and "nope" in errs[0]

    def test_same_source_twice_in_vtep(self):
        errs = _errors("    - {id: vtep-x, sources: [leaf1-lo1, leaf1-lo1], address: 10.0.100.1/32}\n")
        assert len(errs) == 1 and "2 回" in errs[0]

    def test_source_used_by_two_vteps(self):
        errs = _errors(MLAG_A, "    - {id: vtep-leaf1, sources: [leaf1-lo1]}\n")
        assert any("vtep-mlag-a" in e and "leaf1-lo1" in e for e in errs)

    def test_two_sources_on_same_node(self):
        errs = _errors("    - {id: vtep-x, sources: [leaf3-lo1, leaf3-lo2], address: 10.0.100.3/32}\n")
        assert len(errs) == 1 and "leaf3" in errs[0]

    def test_single_source_without_any_address(self):
        errs = _errors("    - {id: vtep-x, sources: [border1-lo9]}\n")
        assert len(errs) == 1 and "アドレスが決まりません" in errs[0]

    def test_single_source_address_differs_from_lo(self):
        r = validate_all(_topo("    - {id: vtep-x, sources: [border1-lo1], address: 10.0.0.99/32}\n"))
        assert r.errors == []
        assert [w.path for w in r.warnings] == ["layer2.vteps[0].address"]

    def test_duplicate_address_between_vteps(self):
        """同じアドレスを 2 つの VTEP に書いたら、共有なら 1 つの VTEP にまとめる"""
        errs = _errors(
            "    - {id: vtep-leaf3, sources: [leaf3-lo1]}\n",
            "    - {id: vtep-border1, sources: [border1-lo9], address: 10.0.0.13/32}\n",
        )
        assert len(errs) == 1 and "10.0.0.13" in errs[0] and "vtep-leaf3" in errs[0]

    def test_one_side_of_mlag_is_warning(self):
        """MLAG ペアの片方だけが VTEP を終端している (相方の書き忘れ)"""
        r = validate_all(_topo("    - {id: vtep-leaf1, sources: [leaf1-lo1]}\n"))
        assert r.errors == []
        assert [w.path for w in r.warnings] == ["layer2.vteps[0].sources"]
        assert "lag-mlag-a" in r.warnings[0].message and "leaf2" in r.warnings[0].message

    def test_prefix_warning(self):
        r = validate_all(_topo("    - {id: border1-nve, sources: [border1-lo1]}\n"))
        assert [w.path for w in r.warnings] == ["layer2.vteps[0].id"]

    def test_undefined_vtep_in_vni(self):
        errs = _errors(MLAG_A, vxlan="    - {id: vni-1, type: l2vni, vni: 10001, vlan: vlan-100, vteps: [nope]}\n")
        assert len(errs) == 1 and "未定義の VTEP 'nope'" in errs[0]

    def test_duplicate_vtep_in_vni(self):
        errs = _errors(MLAG_A, vxlan=(
            "    - {id: vni-1, type: l2vni, vni: 10001, vlan: vlan-100, vteps: [vtep-mlag-a, vtep-mlag-a]}\n"))
        assert len(errs) == 1 and "重複" in errs[0]

    def test_vni_needs_vteps(self):
        with pytest.raises(pydantic.ValidationError, match="vteps"):
            _topo(MLAG_A, vxlan="    - {id: vni-1, type: l2vni, vni: 10001, vlan: vlan-100}\n")


# ---------------------------------------------------------------------------
# 旧形式 (ndl_version 1.x の間だけ受け付ける。ADR-0014 D4)
# ---------------------------------------------------------------------------

class TestLegacy:
    LEGACY = "    - {id: vni-1, type: l2vni, vni: 10001, vlan: vlan-100, vtep_source: leaf1-lo1, members: [leaf1, leaf2]}\n"

    def test_legacy_is_warning(self):
        r = validate_all(_topo(MLAG_A, vxlan=self.LEGACY))
        assert r.errors == []
        assert [w.path for w in r.warnings] == ["layer2.vxlan[0].vtep_source"]
        assert "layer2.vteps" in r.warnings[0].message

    def test_legacy_and_vteps_together_is_error(self):
        with pytest.raises(pydantic.ValidationError, match="併記"):
            _topo(MLAG_A, vxlan=(
                "    - {id: vni-1, type: l2vni, vni: 10001, vlan: vlan-100, vteps: [vtep-mlag-a],"
                " vtep_source: leaf1-lo1}\n"))


# ---------------------------------------------------------------------------
# MTU とエクスポーター
# ---------------------------------------------------------------------------

def test_mtu_domain_uses_vtep_sources():
    """VTEP を終端するノードどうしの underlay リンクは MTU >= 1550"""
    body = 'ndl_version: "1.0"\n' + L1.replace(
        "  lag:",
        "  links:\n    - {id: link-x, endpoints: [leaf1-swp1, leaf2-swp1], mtu: 1500, link_role: underlay}\n  lag:",
    ) + "layer2:\n  vteps:\n" + MLAG_A + L3
    errs = [str(e) for e in validate(parse(body))]
    assert any("1550" in e for e in errs)


def test_cytoscape_vni_lists_vteps():
    out = cytoscape.export(_topo(
        MLAG_A, vxlan="    - {id: vni-10100, type: l2vni, vni: 10100, vlan: vlan-100, vteps: [vtep-mlag-a]}\n"))
    vni = next(n["data"] for n in out["nodes"] if n["data"]["id"] == "vni-10100")
    assert vni["vteps"] == ["vtep-mlag-a"]


def test_yaml_round_trip():
    t1 = _topo(MLAG_A, "    - {id: vtep-border1, sources: [border1-lo1]}\n",
               vxlan="    - {id: vni-10100, type: l2vni, vni: 10100, vlan: vlan-100, vteps: [vtep-mlag-a]}\n")
    out = yaml_exporter.export(t1)
    vni = yaml.safe_load(out)["layer2"]["vxlan"][0]
    assert "members" not in vni and "vtep_source" not in vni     # 旧形式のキーは書き出さない
    t2 = parse(out)
    assert t1.model_dump() == t2.model_dump()
