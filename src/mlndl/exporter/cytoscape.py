"""Cytoscape.js JSON エクスポーター (ndl-viz 向け)

出力形式:
  {
    "nodes": [ {"data": {...}}, ... ],
    "edges": [ {"data": {...}}, ... ]
  }

ノード種別:
  - type: "node"        — L1Node
  - type: "interface"   — L1Interface (parent = ノード ID)

エッジ種別:
  - type: "link"        — L1Link (物理ケーブル)
  - type: "attaches_to" — supporting 関係 (クロスレイヤー)
  - type: "lag_member"  — LAG メンバー関係
"""

from __future__ import annotations

import json

from ..schema.layer1 import AttachesToObj, LacpLag, MlagLag
from ..schema.topology import MLNDLTopology


def export(topology: MLNDLTopology) -> dict:
    """MLNDLTopology を Cytoscape.js elements 辞書に変換する。"""
    elements: dict[str, list] = {"nodes": [], "edges": []}

    if topology.layer1 is None:
        return elements

    l1 = topology.layer1

    # --- L1 ノード ---
    for node in l1.nodes:
        data: dict = {
            "id": node.id,
            "label": node.name or node.id,
            "layer": "layer1",
            "type": "node",
        }
        if node.role:
            data["role"] = node.role
        if node.implementation:
            data["implementation"] = node.implementation
        if node.device_type:
            data["device_type"] = node.device_type
        elements["nodes"].append({"data": data})

    # --- L1 インターフェース (compound node として親ノードに属する) ---
    for iface in l1.interfaces:
        data = {
            "id": iface.id,
            "label": iface.name or iface.id,
            "layer": "layer1",
            "type": "interface",
            "parent": iface.node,
        }
        elements["nodes"].append({"data": data})

    # --- L1 リンク (物理ケーブル) ---
    for link in l1.links:
        data = {
            "id": link.id,
            "source": link.from_,
            "target": link.to,
            "layer": "layer1",
            "type": "link",
        }
        if link.link_speed:
            data["link_speed"] = link.link_speed
        if link.mtu:
            data["mtu"] = link.mtu
        if link.link_role:
            data["link_role"] = link.link_role
        elements["edges"].append({"data": data})

    # --- attaches_to エッジ (supporting 関係) ---
    for node in l1.nodes:
        if node.attaches_to is not None:
            target = _resolve_node_target(node.attaches_to)
            if target:
                elements["edges"].append({"data": {
                    "id": f"attaches-{node.id}-{target}",
                    "source": node.id,
                    "target": target,
                    "type": "attaches_to",
                    "layer": "cross",
                }})

    # --- LAG メンバー エッジ ---
    for lag in l1.lag:
        if isinstance(lag, LacpLag):
            for member in lag.members:
                elements["edges"].append({"data": {
                    "id": f"lag-member-{lag.id}-{member}",
                    "source": lag.id,
                    "target": member,
                    "type": "lag_member",
                    "lag_type": "lacp",
                    "layer": "layer1",
                }})
        elif isinstance(lag, MlagLag):
            for member in lag.members:
                elements["edges"].append({"data": {
                    "id": f"lag-member-{lag.id}-{member}",
                    "source": lag.id,
                    "target": member,
                    "type": "lag_member",
                    "lag_type": "mlag",
                    "layer": "layer1",
                }})

    return elements


def export_json(topology: MLNDLTopology, indent: int = 2) -> str:
    """Cytoscape.js elements を JSON 文字列として返す。"""
    return json.dumps(export(topology), ensure_ascii=False, indent=indent)


def _resolve_node_target(attaches_to: str | AttachesToObj) -> str | None:
    """attaches_to からノード ID を解決する（ノード参照のみ）"""
    if isinstance(attaches_to, str):
        return attaches_to
    if isinstance(attaches_to, AttachesToObj) and attaches_to.node:
        return attaches_to.node
    return None
