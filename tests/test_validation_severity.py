"""severity 機構 (ADR-0002 D8) と規約 warning / VLAN ID 重複チェックのテスト"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from mlndl import parse, parse_file, validate, validate_all, ValidationResult

FIXTURES = Path(__file__).parent / "fixtures"

def _topo(body: str):
    return parse('ndl_version: "1.0"\n' + body)


L1_TWO_NODES = """
layer1:
  nodes:
    - {id: leaf1}
    - {id: leaf2}
  interfaces:
    - {id: leaf1-swp1, node: leaf1}
    - {id: leaf1-swp2, node: leaf1}
    - {id: leaf2-swp1, node: leaf2}
"""


# ---------------------------------------------------------------------------
# severity の振り分け
# ---------------------------------------------------------------------------

class TestSeverity:
    NO_PREFIX_LINK = L1_TWO_NODES + """
  links:
    - {id: spine-leaf-cable, endpoints: [leaf1-swp1, leaf2-swp1]}
"""

    def test_validate_all_returns_result(self):
        r = validate_all(_topo(self.NO_PREFIX_LINK))
        assert isinstance(r, ValidationResult)
        assert r.errors == []
        assert len(r.warnings) == 1
        assert r.warnings[0].severity == "warning"

    def test_validate_excludes_warnings(self):
        """validate() は後方互換で error だけを返す"""
        assert validate(_topo(self.NO_PREFIX_LINK)) == []

    def test_warning_does_not_break_ok(self):
        assert validate_all(_topo(self.NO_PREFIX_LINK)).ok

    def test_strict_promotes_warning_to_error(self):
        r = validate_all(_topo(self.NO_PREFIX_LINK), strict=True)
        assert r.warnings == []
        assert len(r.errors) == 1
        assert r.errors[0].severity == "error"
        assert "(strict)" in r.errors[0].message
        assert not r.ok

    def test_existing_errors_default_to_error_severity(self):
        r = validate_all(parse_file(FIXTURES / "invalid_missing_node.yaml"))
        assert r.errors
        assert all(e.severity == "error" for e in r.errors)

    @pytest.mark.parametrize(
        "fixture",
        sorted(p.name for p in FIXTURES.glob("valid_*.yaml")),
    )
    def test_valid_fixtures_have_no_warnings(self, fixture):
        """規約 warning が既存の valid fixture で誤検知しないこと"""
        r = validate_all(parse_file(FIXTURES / fixture))
        assert r.errors == []
        assert r.warnings == [], [str(w) for w in r.warnings]


# ---------------------------------------------------------------------------
# 推奨プレフィックス (ADR-0002 D7)
# ---------------------------------------------------------------------------

class TestPrefixWarnings:
    def _warn_paths(self, topo):
        return [w.path for w in validate_all(topo).warnings]

    def test_link_prefix(self):
        ok = _topo(L1_TWO_NODES + "  links:\n    - {id: link-leaf1-leaf2, endpoints: [leaf1-swp1, leaf2-swp1]}\n")
        ng = _topo(L1_TWO_NODES + "  links:\n    - {id: cable-1, endpoints: [leaf1-swp1, leaf2-swp1]}\n")
        assert self._warn_paths(ok) == []
        assert self._warn_paths(ng) == ["layer1.links[0].id"]

    def test_vlan_prefix(self):
        ng = _topo(L1_TWO_NODES + "layer2:\n  vlans:\n    - {id: v100, vlan_id: 100}\n")
        assert self._warn_paths(ng) == ["layer2.vlans[0].id"]

    def test_vni_and_vrf_prefix(self):
        ng = _topo(
            "layer2:\n  vxlan:\n    - {id: l3vni-tenant-a, type: l3vni, vni: 10900, vrf: tenant-a}\n"
            "layer3:\n  vrfs:\n    - {id: tenant-a, l3vni: l3vni-tenant-a}\n"
        )
        assert sorted(self._warn_paths(ng)) == ["layer2.vxlan[0].id", "layer3.vrfs[0].id"]

    @pytest.mark.parametrize("adj_type,good,bad", [
        ("bgp", "bgp-peer-leaf1-leaf2", "bgp-adj-leaf1-leaf2"),
        ("ospf", "ospf-adj-leaf1-leaf2", "ospf-leaf1-leaf2"),
        ("isis", "isis-adj-leaf1-leaf2", "adj-leaf1-leaf2"),
    ])
    def test_adjacency_prefix_depends_on_type(self, adj_type, good, bad):
        ends = {
            "bgp": "from: {node: leaf1, update_source: leaf1-lo}, to: {node: leaf2, update_source: leaf2-lo}",
            "ospf": "from: {node: leaf1, interface: leaf1-lo}, to: {node: leaf2, interface: leaf2-lo}, area: 0",
            "isis": "from: {node: leaf1, interface: leaf1-swp1}, to: {node: leaf2, interface: leaf2-swp1}, level: level-2",
        }[adj_type]
        tmpl = L1_TWO_NODES + (
            # IS-IS の両端は同じリンクに載せる (通り道の食い違いの warning を出さない。ADR-0018 D4)
            "  links:\n    - {id: link-leaf1-leaf2, endpoints: [leaf1-swp1, leaf2-swp1]}\n"
            "layer3:\n  interfaces:\n"
            "    - {id: leaf1-lo, node: leaf1, name: lo, ip: 10.0.0.1/32}\n"
            "    - {id: leaf2-lo, node: leaf2, name: lo, ip: 10.0.0.2/32}\n"
            "control_plane:\n"
            f"  {adj_type}: [{{id: x, nodes: [{{node: leaf1}}, {{node: leaf2}}]}}]\n".replace(
                "{node: leaf1}, {node: leaf2}",
                "{node: leaf1, local_as: 65001}, {node: leaf2, local_as: 65002}" if adj_type == "bgp" else "{node: leaf1}, {node: leaf2}")
            + "  routing_neighbors:\n"
            "    - {id: %s, type: " + adj_type + ", " + ends + "}\n"
        )
        assert self._warn_paths(_topo(tmpl % good)) == []
        assert self._warn_paths(_topo(tmpl % bad)) == ["control_plane.routing_neighbors[0].id"]

    def test_bfd_prefix(self):
        ng = _topo("control_plane:\n  bfd:\n    - {id: timers-default}\n")
        assert self._warn_paths(ng) == ["control_plane.bfd[0].id"]

    @pytest.mark.parametrize("lag_id,warns", [
        ("lag-leaf1-bond0", False),
        ("bond-leaf1", True),   # 2026-09-17 に bond- から lag- へ変更
        ("po1", True),
    ])
    def test_lag_prefix(self, lag_id, warns):
        topo = _topo(L1_TWO_NODES + (
            "  lag:\n    - {id: %s, type: lacp, node: leaf1, members: [leaf1-swp1, leaf1-swp2]}\n" % lag_id
        ))
        assert self._warn_paths(topo) == (["layer1.lag[0].id"] if warns else [])

    def test_warning_does_not_affect_reference_resolution(self):
        """D7: プレフィックス違反でも参照解決は通常どおり動く"""
        topo = _topo(
            "layer2:\n  vxlan:\n    - {id: l3vni-a, type: l3vni, vni: 10900, vrf: tenant-a}\n"
            "layer3:\n  vrfs:\n    - {id: tenant-a, l3vni: l3vni-a}\n"
        )
        assert validate(topo) == []


# ---------------------------------------------------------------------------
# labels のキー (ADR-0009 D3)
# ---------------------------------------------------------------------------

class TestLabelKeyWarnings:
    def _topo_with_labels(self, labels: str):
        return _topo("layer1:\n  nodes:\n    - id: leaf1\n      labels: " + labels + "\n")

    @pytest.mark.parametrize("key", ["AZ", "availability_zone", "availabilityZone", "cost--center", "-env"])
    def test_non_conforming_key_warns(self, key):
        r = validate_all(self._topo_with_labels("{'%s': ap-northeast-1a}" % key))
        assert r.errors == []
        assert [w.path for w in r.warnings] == [f"layer1.nodes[0].labels.{key}"]

    @pytest.mark.parametrize("key", ["az", "cost-center", "rack2", "site-tokyo"])
    def test_conforming_key_is_silent(self, key):
        assert validate_all(self._topo_with_labels("{%s: x}" % key)).warnings == []

    def test_values_are_not_checked(self):
        """値は自由文字列 (ADR-0009 D2)。大文字やアンダースコアでも warning にしない"""
        r = validate_all(self._topo_with_labels("{ticket: PROJ_1234, owner: Net Infra}"))
        assert r.warnings == []


# ---------------------------------------------------------------------------
# VLAN ID の同一ノード内重複 (error)
# ---------------------------------------------------------------------------

class TestVlanIdDuplicate:
    def test_same_vlan_id_on_same_node_is_error(self):
        topo = _topo(L1_TWO_NODES + """
layer2:
  vlans:
    - id: vlan-100
      vlan_id: 100
      trunk_ports: [{interface: leaf1-swp1}]
    - id: vlan-100-dup
      vlan_id: 100
      access_ports: [{interface: leaf1-swp2}]
""")
        errors = validate(topo)
        assert len(errors) == 1
        assert "leaf1" in errors[0].message
        assert "VLAN ID 100" in errors[0].message

    def test_same_vlan_id_on_different_nodes_is_allowed(self):
        """サイトローカルな番号の再利用は許容する"""
        topo = _topo(L1_TWO_NODES + """
layer2:
  vlans:
    - id: vlan-100
      vlan_id: 100
      trunk_ports: [{interface: leaf1-swp1}]
    - id: vlan-100-site-b
      vlan_id: 100
      trunk_ports: [{interface: leaf2-swp1}]
""")
        assert validate(topo) == []

    def test_one_vlan_on_many_ports_of_same_node_is_allowed(self):
        topo = _topo(L1_TWO_NODES + """
layer2:
  vlans:
    - id: vlan-100
      vlan_id: 100
      trunk_ports:
        - {interface: leaf1-swp1}
        - {interface: leaf1-swp2}
""")
        assert validate(topo) == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCliSeverity:
    SRC = 'ndl_version: "1.0"\n' + L1_TWO_NODES + (
        "  links:\n    - {id: cable-1, endpoints: [leaf1-swp1, leaf2-swp1]}\n"
    )

    def _run(self, tmp_path, *args):
        f = tmp_path / "t.yaml"
        f.write_text(self.SRC)
        return subprocess.run(
            [sys.executable, "-m", "mlndl", "validate", *args, str(f)],
            capture_output=True, text=True,
        )

    def test_warning_exits_zero(self, tmp_path):
        r = self._run(tmp_path)
        assert r.returncode == 0
        assert "WARNING" in r.stderr
        assert "1 warnings" in r.stdout

    def test_strict_exits_nonzero(self, tmp_path):
        r = self._run(tmp_path, "--strict")
        assert r.returncode == 1
        assert "ERROR" in r.stderr

    def test_schema_error_is_reported_without_traceback(self, tmp_path):
        """スキーマ違反 (ここでは ADR-0011 で廃止したキー) は ERROR 行で報告し、トレースバックを出さない"""
        f = tmp_path / "t.yaml"
        f.write_text(
            'ndl_version: "1.0"\n'
            "layer3:\n  interfaces:\n"
            "    - {id: s1, node: n1, name: Vlan10, fhrp: []}\n"
        )
        r = subprocess.run(
            [sys.executable, "-m", "mlndl", "validate", str(f)],
            capture_output=True, text=True,
        )
        assert r.returncode == 1
        assert "Traceback" not in r.stderr
        assert "ERROR    layer3.interfaces[0]:" in r.stderr
        assert "gateway_redundancy" in r.stderr
        # スキーマの誤りがあると後段の検査が走らないことを案内する (round4 E7)
        assert "NOTE" in r.stderr and "続けて実行" in r.stderr
