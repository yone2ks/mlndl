"""Phase 2 ユニットテスト (L2/L3/protocols スキーマ + validator 完全実装)"""

from __future__ import annotations

from pathlib import Path

import pytest

from mlndl import parse, parse_file, validate
from mlndl.schema.layer2 import L2VxLAN, L3VxLAN
from mlndl.schema.layer3 import VRF, L3Interface

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# フルトポロジーのパース
# ---------------------------------------------------------------------------

class TestFullDCParse:
    def test_parse_full_dc(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        assert t.layer1 is not None
        assert t.layer2 is not None
        assert t.layer3 is not None
        assert t.protocols is not None

    def test_layer2_vlans(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        assert len(t.layer2.vlans) == 1
        assert t.layer2.vlans[0].vlan_id == 100

    def test_layer2_vxlan_types(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        vxlans = {v.id: v for v in t.layer2.vxlan}
        assert isinstance(vxlans["vni-10100"], L2VxLAN)
        assert isinstance(vxlans["vni-10900"], L3VxLAN)
        assert vxlans["vni-10100"].vni == 10100
        assert vxlans["vni-10900"].vni == 10900

    def test_layer3_vrfs(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        assert len(t.layer3.vrfs) == 2
        vrfs = {v.id: v for v in t.layer3.vrfs}
        vrf = vrfs["vrf-tenant-a"]
        assert vrf.rd == "65001:100"
        assert vrf.l3vni == "vni-10900"

    def test_layer3_route_targets(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        vrfs = {v.id: v for v in t.layer3.vrfs}
        vrf = vrfs["vrf-tenant-a"]
        assert vrf.route_targets is not None
        assert "65001:100" in vrf.route_targets.import_
        assert "65001:100" in vrf.route_targets.export

    def test_layer3_interfaces(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        iface_ids = {i.id for i in t.layer3.interfaces}
        assert "spine1-lo" in iface_ids
        assert "leaf1-lo" in iface_ids

    def test_layer3_routing_adjacencies(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        assert len(t.layer3.routing_adjacencies) == 4  # spine1×2 + spine2×2
        adj = t.layer3.routing_adjacencies[0]
        assert adj.from_.node == "spine1"
        assert adj.to.node == "leaf1"
        assert adj.attaches_to is not None

    def test_protocols_bfd(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        assert len(t.protocols.bfd) == 1
        bfd = t.protocols.bfd[0]
        assert bfd.min_tx == 300
        assert "spine1" in bfd.nodes

    def test_protocols_bgp(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        bgp_procs = {b.id: b for b in t.protocols.bgp}
        assert "bgp-underlay" in bgp_procs
        assert "bgp-evpn" in bgp_procs

    def test_protocols_bgp_neighbors(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        underlay = next(b for b in t.protocols.bgp if b.id == "bgp-underlay")
        spine = underlay.nodes[0]
        assert spine.local_as == 65000
        nb = spine.neighbors[0]
        assert nb.type == "ebgp"
        assert nb.bfd is True


# ---------------------------------------------------------------------------
# バリデーター: フルトポロジー
# ---------------------------------------------------------------------------

class TestValidatorFullDC:
    def test_full_dc_no_errors(self):
        t = parse_file(FIXTURES / "valid_full_dc.yaml")
        errors = validate(t)
        assert errors == [], "\n".join(str(e) for e in errors)


# ---------------------------------------------------------------------------
# バリデーター: VNI 重複
# ---------------------------------------------------------------------------

class TestValidatorVniDuplicate:
    def test_vni_duplicate_detected(self):
        t = parse_file(FIXTURES / "invalid_vni_duplicate.yaml")
        errors = validate(t)
        paths = [e.path for e in errors]
        assert any("vni" in p for p in paths)
        assert any("重複" in e.message for e in errors)


# ---------------------------------------------------------------------------
# バリデーター: MTU 整合性
# ---------------------------------------------------------------------------

class TestValidatorMtu:
    def test_mtu_too_low_for_vxlan(self):
        t = parse_file(FIXTURES / "invalid_mtu_vxlan.yaml")
        errors = validate(t)
        paths = [e.path for e in errors]
        assert any("mtu" in p for p in paths)
        assert any("1550" in e.message for e in errors)


# ---------------------------------------------------------------------------
# バリデーター: BGP AS 番号
# ---------------------------------------------------------------------------

class TestValidatorBGPAS:
    def test_ebgp_same_as_error(self):
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes:
    - id: spine1
    - id: leaf1
protocols:
  bgp:
    - id: bgp-test
      nodes:
        - node: spine1
          local_as: 65000
          neighbors:
            - node: leaf1
              remote_as: 65000
              type: ebgp
"""
        t = parse(yaml_str)
        errors = validate(t)
        assert any("eBGP" in e.message for e in errors)

    def test_ibgp_different_as_error(self):
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes:
    - id: spine1
    - id: leaf1
protocols:
  bgp:
    - id: bgp-test
      nodes:
        - node: spine1
          local_as: 65000
          neighbors:
            - node: leaf1
              remote_as: 65001
              type: ibgp
"""
        t = parse(yaml_str)
        errors = validate(t)
        assert any("iBGP" in e.message for e in errors)

    def test_ebgp_different_as_ok(self):
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes:
    - id: spine1
    - id: leaf1
protocols:
  bgp:
    - id: bgp-test
      nodes:
        - node: spine1
          local_as: 65000
          neighbors:
            - node: leaf1
              remote_as: 65001
              type: ebgp
"""
        t = parse(yaml_str)
        errors = validate(t)
        bgp_errors = [e for e in errors if "bgp" in e.path.lower()]
        assert bgp_errors == []


# ---------------------------------------------------------------------------
# バリデーター: Route Target フォーマット
# ---------------------------------------------------------------------------

class TestValidatorRouteTarget:
    def test_invalid_rd_format(self):
        yaml_str = b"""
ndl_version: "1.0"
layer3:
  vrfs:
    - id: vrf-a
      rd: "invalid-format"
"""
        t = parse(yaml_str)
        errors = validate(t)
        assert any("RD" in e.message for e in errors)

    def test_valid_rd_asn_format(self):
        yaml_str = b"""
ndl_version: "1.0"
layer3:
  vrfs:
    - id: vrf-a
      rd: "65001:100"
"""
        t = parse(yaml_str)
        errors = validate(t)
        rd_errors = [e for e in errors if "rd" in e.path.lower()]
        assert rd_errors == []

    def test_valid_rd_ip_format(self):
        yaml_str = b"""
ndl_version: "1.0"
layer3:
  vrfs:
    - id: vrf-a
      rd: "10.0.0.1:100"
"""
        t = parse(yaml_str)
        errors = validate(t)
        rd_errors = [e for e in errors if "rd" in e.path.lower()]
        assert rd_errors == []


# ---------------------------------------------------------------------------
# スキーマバリデーション: Layer 2/3
# ---------------------------------------------------------------------------

class TestSchemaL2L3:
    def test_vxlan_unknown_type_error(self):
        yaml_str = b"""
ndl_version: "1.0"
layer2:
  vxlan:
    - id: vni-1
      type: unknown
      vni: 100
"""
        with pytest.raises(Exception):
            parse(yaml_str)

    def test_gateway_redundancy_invalid_mode(self):
        yaml_str = b"""
ndl_version: "1.0"
layer3:
  interfaces:
    - id: iface1
      node: node1
      interface: vlan-100
      gateway_redundancy:
        - mode: unknown_mode
          group_id: 1
          vip: 10.0.0.1
"""
        with pytest.raises(Exception):
            parse(yaml_str)

