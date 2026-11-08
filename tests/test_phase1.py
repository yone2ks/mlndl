"""Phase 1 ユニットテスト"""

from __future__ import annotations

from pathlib import Path

import pytest

import mlndl
from mlndl import parse, parse_file, validate
from mlndl.exporter import cytoscape, yaml as yaml_exporter
from mlndl.schema.layer1 import EthernetSegment, Lag

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# パーサー
# ---------------------------------------------------------------------------

class TestParser:
    def test_parse_valid_simple(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        assert t.ndl_version == "1.0"
        assert t.meta is not None
        assert t.meta.name == "simple-spine-leaf"
        assert t.layer1 is not None

    def test_parse_valid_simple_nodes(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        l1 = t.layer1
        assert len(l1.nodes) == 3
        node_ids = {n.id for n in l1.nodes}
        assert "spine1" in node_ids
        assert "leaf1" in node_ids
        assert "eve-server" in node_ids

    def test_parse_valid_simple_links(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        l1 = t.layer1
        assert len(l1.links) == 1
        link = l1.links[0]
        assert link.endpoints == ["spine1-swp1", "leaf1-swp51"]
        assert link.link_speed == "10G"

    def test_parse_valid_with_lag(self):
        t = parse_file(FIXTURES / "valid_l1_with_lag.yaml")
        l1 = t.layer1
        assert len(l1.lag) == 4
        assert len(l1.ethernet_segments) == 1

    def test_parse_lag_and_ethernet_segment(self):
        """LAG は機器 1 台 (ADR-0023 D1)。複数の機器の LAG は ethernet_segments で束ねる (D2)"""
        t = parse_file(FIXTURES / "valid_l1_with_lag.yaml")
        lags = {lag.id: lag for lag in t.layer1.lag}

        peer_link = lags["lag-leaf1-peer"]
        assert isinstance(peer_link, Lag)
        assert peer_link.node == "leaf1"
        assert peer_link.name == "peerlink"
        assert peer_link.members == ["leaf1-swp49", "leaf1-swp50"]

        es = t.layer1.ethernet_segments[0]
        assert isinstance(es, EthernetSegment)
        assert [(m.kind, m.target) for m in es.members] == [("lag", "lag-leaf1-server1"), ("lag", "lag-leaf2-server1")]
        assert es.redundancy_mode is None       # 既定値で埋めない (ADR-0023 D4)

    def test_parse_empty_yaml(self):
        t = parse(b"")
        assert t.ndl_version == "1.0"
        assert t.layer1 is None

    def test_parse_from_string(self):
        t = parse('ndl_version: "1.0"\n')
        assert t.ndl_version == "1.0"


# ---------------------------------------------------------------------------
# バージョンチェック
# ---------------------------------------------------------------------------

class TestVersionCheck:
    def test_version_2_raises(self):
        with pytest.raises(Exception, match="バージョン"):
            parse(b'ndl_version: "2.0"\n')

    def test_version_1_1_ok(self):
        t = parse(b'ndl_version: "1.1"\n')
        assert t.ndl_version == "1.1"

    def test_invalid_version_format_raises(self):
        with pytest.raises(Exception):
            parse(b'ndl_version: "abc"\n')


# ---------------------------------------------------------------------------
# セキュリティ
# ---------------------------------------------------------------------------

class TestSecurity:
    def test_size_limit(self):
        from mlndl.constants import MAX_TOPOLOGY_BYTES
        big = b"x" * (MAX_TOPOLOGY_BYTES + 1)
        with pytest.raises(ValueError, match="上限"):
            parse(big)

    def test_size_at_limit_ok(self):
        from mlndl.constants import MAX_TOPOLOGY_BYTES
        # ちょうど上限サイズの有効な YAML（ほぼすべてスペース）
        content = b'ndl_version: "1.0"\n'
        padding = b"# " + b"x" * (MAX_TOPOLOGY_BYTES - len(content) - 3) + b"\n"
        parse(content + padding)  # 例外が出なければ OK


# ---------------------------------------------------------------------------
# スキーマバリデーション（pydantic）
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_container_hypervisor_error(self):
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes:
    - id: node1
      implementation: container
      role: hypervisor
"""
        with pytest.raises(Exception, match="ADR-0004"):
            parse(yaml_str)

    def test_old_mlag_lag_is_error(self):
        """旧 type: mlag は、機器ごとの LAG と ethernet_segments への移動先を示す error (ADR-0023 D9)"""
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes:
    - id: leaf1
  interfaces: []
  lag:
    - id: lag1
      type: mlag
      nodes: [leaf1]
      members: []
      peer_link: lag-pl
      peer_link_interface: peerlink.4094
"""
        with pytest.raises(Exception, match="ethernet_segments"):
            parse(yaml_str)

    def test_old_lacp_type_is_error(self):
        """旧 type: lacp は、type を消すよう示す error (ADR-0023 D1)"""
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes: [{id: leaf1}]
  interfaces: [{id: leaf1-swp1, node: leaf1}]
  lag:
    - {id: lag-leaf1-po1, type: lacp, node: leaf1, members: [leaf1-swp1]}
"""
        with pytest.raises(Exception, match="type を消して"):
            parse(yaml_str)

    def test_attaches_to_two_keys_error(self):
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes:
    - id: node1
      attaches_to:
        node: host1
        interface: eth0
"""
        with pytest.raises(Exception):
            parse(yaml_str)

    def test_unknown_field_error(self):
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes:
    - id: node1
      unknown_field: value
"""
        with pytest.raises(Exception):
            parse(yaml_str)

    def test_invalid_implementation_error(self):
        yaml_str = b"""
ndl_version: "1.0"
layer1:
  nodes:
    - id: node1
      implementation: virtual
"""
        with pytest.raises(Exception):
            parse(yaml_str)


# ---------------------------------------------------------------------------
# バリデーター（参照整合性）
# ---------------------------------------------------------------------------

class TestValidator:
    def test_valid_simple_no_errors(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        errors = validate(t)
        assert errors == []

    def test_valid_with_lag_no_errors(self):
        t = parse_file(FIXTURES / "valid_l1_with_lag.yaml")
        errors = validate(t)
        assert errors == []

    def test_invalid_missing_node(self):
        t = parse_file(FIXTURES / "invalid_missing_node.yaml")
        errors = validate(t)
        assert len(errors) >= 2
        paths = [e.path for e in errors]
        # ghost-node 参照エラー
        assert any("node" in p for p in paths)
        # undefined-interface 参照エラー
        assert any("endpoints" in p for p in paths)

    def test_validate_returns_validation_error_objects(self):
        t = parse_file(FIXTURES / "invalid_missing_node.yaml")
        errors = validate(t)
        for e in errors:
            assert isinstance(e, mlndl.ValidationError)
            assert e.path
            assert e.message

    def test_empty_topology_no_errors(self):
        t = parse(b'ndl_version: "1.0"\n')
        errors = validate(t)
        assert errors == []


# ---------------------------------------------------------------------------
# エクスポーター: YAML
# ---------------------------------------------------------------------------

class TestYamlExporter:
    def test_export_contains_version(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = yaml_exporter.export(t)
        assert "ndl_version" in result

    def test_export_contains_node_ids(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = yaml_exporter.export(t)
        assert "spine1" in result
        assert "leaf1" in result

    def test_export_endpoints(self):
        """endpoints フィールドが正しくシリアライズされること"""
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = yaml_exporter.export(t)
        assert "endpoints:" in result
        assert "from_:" not in result
        assert "from:" not in result

    def test_roundtrip(self):
        """parse → export → parse でデータが保持されること"""
        original = parse_file(FIXTURES / "valid_l1_simple.yaml")
        exported = yaml_exporter.export(original)
        restored = parse(exported.encode())
        assert restored.layer1 is not None
        assert len(restored.layer1.nodes) == len(original.layer1.nodes)
        assert len(restored.layer1.links) == len(original.layer1.links)


# ---------------------------------------------------------------------------
# エクスポーター: Cytoscape.js
# ---------------------------------------------------------------------------

class TestCytoscapeExporter:
    def test_export_has_nodes_and_edges(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = cytoscape.export(t)
        assert "nodes" in result
        assert "edges" in result

    def test_export_node_ids(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = cytoscape.export(t)
        node_ids = {n["data"]["id"] for n in result["nodes"]}
        assert "spine1" in node_ids
        assert "leaf1" in node_ids

    def test_export_interface_parent(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = cytoscape.export(t)
        iface_nodes = [n for n in result["nodes"] if n["data"].get("type") == "interface"]
        for iface in iface_nodes:
            assert "parent" in iface["data"]

    def test_export_link_edge(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = cytoscape.export(t)
        link_edges = [e for e in result["edges"] if e["data"].get("type") == "link"]
        assert len(link_edges) == 1
        edge = link_edges[0]
        assert edge["data"]["source"] == "spine1"
        assert edge["data"]["target"] == "leaf1"

    def test_export_attaches_to_edge(self):
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = cytoscape.export(t)
        attaches_edges = [e for e in result["edges"] if e["data"].get("type") == "attaches_to"]
        # spine1 と leaf1 が eve-server に attaches_to
        assert len(attaches_edges) == 2

    def test_export_json_is_valid_string(self):
        import json
        t = parse_file(FIXTURES / "valid_l1_simple.yaml")
        result = cytoscape.export_json(t)
        parsed = json.loads(result)
        assert "nodes" in parsed

    def test_export_empty_topology(self):
        t = parse(b'ndl_version: "1.0"\n')
        result = cytoscape.export(t)
        assert result == {"nodes": [], "edges": []}


# ---------------------------------------------------------------------------
# labels — 多軸分類 (ADR-0009)
# ---------------------------------------------------------------------------

class TestLabels:
    def test_parse_labels_map(self):
        t = parse_file(FIXTURES / "valid_labels_multi_axis.yaml")
        leaf1 = next(n for n in t.layer1.nodes if n.id == "leaf1")
        assert leaf1.labels["az"] == "ap-northeast-1a"
        assert leaf1.labels["pod"] == "pod-tokyo"

    def test_labels_optional(self):
        """labels 未指定は valid（None）"""
        t = parse_file(FIXTURES / "valid_labels_multi_axis.yaml")
        spine1 = next(n for n in t.layer1.nodes if n.id == "spine1")
        assert spine1.labels is None

    def test_labels_arbitrary_keys_accepted(self):
        """推奨語彙にないキーも valid — コアは値域チェックしない (ADR-0009 D3)"""
        t = parse_file(FIXTURES / "valid_labels_multi_axis.yaml")
        leaf1 = next(n for n in t.layer1.nodes if n.id == "leaf1")
        assert leaf1.labels["ticket"] == "PROJ-1234"
        assert leaf1.labels["cost-center"] == "eng-platform"

    def test_labels_non_string_value_rejected(self):
        """値は str のみ (Phase 1)"""
        with pytest.raises(Exception):
            parse(
                'ndl_version: "1.0"\n'
                "layer1:\n"
                "  nodes:\n"
                "    - id: leaf1\n"
                "      labels:\n"
                "        vlan: 100\n"
            )

    def test_labels_no_validation_errors(self):
        t = parse_file(FIXTURES / "valid_labels_multi_axis.yaml")
        assert validate(t) == []

    def test_labels_not_emitted_when_absent(self):
        """labels 未指定のノードは YAML 出力に labels キーを持たない"""
        t = parse_file(FIXTURES / "valid_labels_multi_axis.yaml")
        out = yaml_exporter.export(t)
        assert "cost-center: eng-platform" in out
        # spine1 ブロックに labels が現れないこと
        spine_block = out.split("id: spine1")[1].split("- id:")[0]
        assert "labels" not in spine_block

    def test_cytoscape_exports_labels(self):
        t = parse_file(FIXTURES / "valid_labels_multi_axis.yaml")
        result = cytoscape.export(t)
        by_id = {n["data"]["id"]: n["data"] for n in result["nodes"]}
        assert by_id["leaf1"]["labels"]["pod"] == "pod-tokyo"
        # 未指定ノードには labels キー自体を出さない
        assert "labels" not in by_id["spine1"]

    def test_labels_roundtrip(self):
        t = parse_file(FIXTURES / "valid_labels_multi_axis.yaml")
        t2 = parse(yaml_exporter.export(t))
        leaf1 = next(n for n in t2.layer1.nodes if n.id == "leaf1")
        assert leaf1.labels["env"] == "prod"
