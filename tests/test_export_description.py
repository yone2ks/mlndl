"""エクスポーターが description をそのまま出すことのテスト (ADR-0011 D7)"""

from __future__ import annotations

from mlndl import parse
from mlndl.exporter import cytoscape


YAML = """
ndl_version: "1.0"
layer1:
  nodes:
    - {id: r1, description: 東京の WAN ルーター}
    - {id: r2}
  interfaces:
    - {id: r1-e0, node: r1, name: e0}
    - {id: r2-e0, node: r2, name: e0}
  links:
    - id: link-r1-r2
      endpoints: [r1-e0, r2-e0]
      description: KDDI 専用線 KD-0123
layer2:
  vlans:
    - {id: vlan-10, vlan_id: 10, description: 業務系}
    - {id: vlan-20, vlan_id: 20}
layer3:
  interfaces:
    - id: r1-e0-l3
      node: r1
      name: e0
      ip: 10.0.0.0/31
      attaches_to: {interface: r1-e0}
      description: 大阪向け
    - id: r2-e0-l3
      node: r2
      name: e0
      ip: 10.0.0.1/31
      attaches_to: {interface: r2-e0}
control_plane:
  bgp:
    - id: bgp-default
      nodes: [{node: r1, local_as: 65001}, {node: r2, local_as: 65002}]
  routing_neighbors:
    - id: bgp-peer-r1-r2
      type: bgp
      from: {node: r1, update_source: r1-e0-l3}
      to: {node: r2, update_source: r2-e0-l3}
      address_families: [ipv4_unicast]
      description: 拠点間の eBGP
"""


def _elements() -> dict:
    return cytoscape.export(parse(YAML))


def test_node_description():
    nodes = {n["data"]["id"]: n["data"] for n in _elements()["nodes"]}
    assert nodes["r1"]["description"] == "東京の WAN ルーター"
    assert nodes["vlan-10"]["description"] == "業務系"
    assert nodes["r1"]["l3_interfaces"][0]["description"] == "大阪向け"


def test_edge_description():
    edges = {e["data"]["id"]: e["data"] for e in _elements()["edges"]}
    assert edges["link-r1-r2"]["description"] == "KDDI 専用線 KD-0123"
    assert edges["bgp-peer-r1-r2"]["description"] == "拠点間の eBGP"


def test_no_key_when_not_written():
    nodes = {n["data"]["id"]: n["data"] for n in _elements()["nodes"]}
    assert "description" not in nodes["r2"]
    assert "description" not in nodes["vlan-20"]
