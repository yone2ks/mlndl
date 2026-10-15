"""ADR-0012 802.1Q サブインターフェースのテスト"""

from __future__ import annotations

import pydantic
import pytest

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


L1 = """
layer1:
  nodes: [{id: r1}, {id: r2}, {id: r3}, {id: sw1}]
  interfaces:
    - {id: r1-eth0, node: r1}
    - {id: r1-eth1, node: r1}
    - {id: r1-eth2, node: r1}
    - {id: r2-eth0, node: r2}
    - {id: r2-eth1, node: r2}
    - {id: r3-eth0, node: r3}
  lag:
    - {id: lag-r1-bond0, type: lacp, node: r1, members: [r1-eth1, r1-eth2]}
    - {id: lag-peer, type: lacp, node: r2, members: [r2-eth1]}
    - id: lag-mlag-a
      type: mlag
      nodes: [r1, r2]
      members: [r1-eth0, r2-eth0]
      peer_link: lag-peer
      peer_link_interface: peerlink.4094
"""


def _subifs(*entries: str, l3: str = "") -> str:
    body = L1 + "layer2:\n  subinterfaces:\n" + "".join(entries)
    if l3:
        body += "layer3:\n  interfaces:\n" + l3
    return body


S10 = "    - {id: subif-r1-eth0-10, attaches_to: {interface: r1-eth0}, vlan_id: 10, name: eth0.10}\n"


# ---------------------------------------------------------------------------
# スキーマ
# ---------------------------------------------------------------------------

class TestSchema:
    def test_minimal(self):
        si = _topo(_subifs(S10)).layer2.subinterfaces[0]
        assert (si.attaches_to.kind, si.attaches_to.target, si.vlan_id, si.name) == ("interface", "r1-eth0", 10, "eth0.10")

    @pytest.mark.parametrize("vid", [0, 4095, 4096])
    def test_vlan_id_range(self, vid):
        """IEEE 802.1Q: 0 と 4095 は予約"""
        _parse_error(_subifs(f"    - {{id: subif-x, attaches_to: {{interface: r1-eth0}}, vlan_id: {vid}}}\n"))

    def test_string_attaches_to_is_rejected(self):
        """文字列の attaches_to はノード ID の糖衣構文 (ADR-0001)。サブ IF の親にはならない"""
        msg = _parse_error(_subifs("    - {id: subif-x, attaches_to: r1, vlan_id: 10}\n"))
        assert "{interface:" in msg

    @pytest.mark.parametrize("key", ["node: r1", "link: link-x", "vlan: vlan-10", "subinterface: subif-y"])
    def test_only_interface_or_lag_key(self, key):
        """サブ IF の基盤は L1 IF か LAG だけ (ADR-0001 D8 / ADR-0012 D4)"""
        msg = _parse_error(_subifs(f"    - {{id: subif-x, attaches_to: {{{key}}}, vlan_id: 10}}\n"))
        assert "ADR-0001 D8" in msg

    def test_node_field_does_not_exist(self):
        """node は親から導出する。持たせると二重表現になる (ADR-0012)"""
        _parse_error(_subifs("    - {id: subif-x, node: r1, attaches_to: {interface: r1-eth0}, vlan_id: 10}\n"))

    def test_vlan_reference_field_does_not_exist(self):
        """vlan_id はタグ番号であり、VLAN エンティティへの参照は持たない (ADR-0012)"""
        _parse_error(_subifs("    - {id: subif-x, attaches_to: {interface: r1-eth0}, vlan_id: 10, vlan: vlan-10}\n"))


# ---------------------------------------------------------------------------
# validator
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid(self):
        assert _errors(_subifs(S10)) == []

    def test_parent_lag(self):
        assert _errors(_subifs(
            "    - {id: subif-r1-bond0-10, attaches_to: {lag: lag-r1-bond0}, vlan_id: 10}\n"
        )) == []

    def test_undefined_parent(self):
        errs = _errors(_subifs("    - {id: subif-x, attaches_to: {interface: nope}, vlan_id: 10}\n"))
        assert any("nope" in e for e in errs)

    def test_interface_key_pointing_at_vlan(self):
        """{interface:} は L1 IF 専用。VLAN の ID を書くと、種類を示して未定義にする"""
        body = _subifs("    - {id: subif-x, attaches_to: {interface: vlan-10}, vlan_id: 10}\n").replace(
            "layer2:\n", "layer2:\n  vlans: [{id: vlan-10, vlan_id: 10}]\n")
        errs = _errors(body)
        assert len(errs) == 1 and "vlan-10" in errs[0] and "VLAN" in errs[0]

    def test_duplicate_tag_on_same_parent(self):
        errs = _errors(_subifs(
            S10, "    - {id: subif-r1-eth0-10b, attaches_to: {interface: r1-eth0}, vlan_id: 10}\n"
        ))
        assert any("重複" in e and "10" in e for e in errs)

    def test_same_tag_on_different_parents(self):
        assert _errors(_subifs(
            S10, "    - {id: subif-r2-eth0-10, attaches_to: {interface: r2-eth0}, vlan_id: 10}\n"
        )) == []

    def test_no_link_to_layer2_vlans(self):
        """タグ 10 に対応する VLAN がなくても、親ポートが trunk になくても、error も warning も出さない。
        Cisco / Arista では routed サブ IF の親ポートは switchport にできないため、照合すると誤検知になる"""
        r = validate_all(_topo(_subifs(S10)))
        assert r.errors == [] and r.warnings == []

    def test_l1_interface_cannot_attach_to_subif(self):
        body = _subifs(S10).replace(
            "    - {id: r3-eth0, node: r3}",
            "    - {id: r3-eth0, node: r3, attaches_to: {subinterface: subif-r1-eth0-10}}",
        )
        assert "ADR-0001 D8" in _parse_error(body)

    def test_id_space_collision(self):
        """ID はグローバルに一意。旧形式 {interface: X} の読み替えも、X の空間が一意に決まることに頼る"""
        body = _subifs("    - {id: r1-eth1, attaches_to: {interface: r1-eth0}, vlan_id: 10}\n")
        assert any("ADR-0002 D5" in e and "r1-eth1" in e for e in _errors(body))

    def test_prefix_warning(self):
        r = validate_all(_topo(_subifs("    - {id: eth0-10, attaches_to: {interface: r1-eth0}, vlan_id: 10}\n")))
        assert [w.path for w in r.warnings] == ["layer2.subinterfaces[0].id"]


class TestL3OnSubinterface:
    def test_l3_on_subif(self):
        assert _errors(_subifs(S10, l3=(
            "    - {id: r1-eth0-10, node: r1, name: eth0.10,"
            " attaches_to: {subinterface: subif-r1-eth0-10}, ip: 192.168.10.1/24}\n"
        ))) == []

    def test_l3_on_other_nodes_subif(self):
        errs = _errors(_subifs(S10, l3=(
            "    - {id: r2-x, node: r2, name: eth0.10, attaches_to: {subinterface: subif-r1-eth0-10}}\n"
        )))
        assert any("サブインターフェース" in e and "r2" in e for e in errs)

    def test_routed_lag(self):
        assert _errors(_subifs(S10, l3=(
            "    - {id: r1-bond0, node: r1, name: bond0, attaches_to: {lag: lag-r1-bond0},"
            " ip: 10.0.0.1/30}\n"
        ))) == []

    def test_routed_lag_on_other_node(self):
        errs = _errors(_subifs(S10, l3=(
            "    - {id: r2-bond0, node: r2, name: bond0, attaches_to: {lag: lag-r1-bond0}}\n"
        )))
        assert any("LAG" in e and "r2" in e for e in errs)

    @pytest.mark.parametrize("node,ok", [("r1", True), ("r2", True), ("r3", False)])
    def test_subif_on_mlag_belongs_to_both_nodes(self, node, ok):
        errs = _errors(_subifs(
            "    - {id: subif-mlag-a-10, attaches_to: {lag: lag-mlag-a}, vlan_id: 10}\n",
            l3=f"    - {{id: {node}-x, node: {node}, name: po1.10, attaches_to: {{subinterface: subif-mlag-a-10}}}}\n",
        ))
        assert (errs == []) is ok


# ---------------------------------------------------------------------------
# エクスポーター
# ---------------------------------------------------------------------------

class TestExport:
    def _node(self, out, nid):
        return next(n["data"] for n in out["nodes"] if n["data"]["id"] == nid)

    def test_cytoscape_embeds_subifs_and_kinds(self):
        out = cytoscape.export(_topo(_subifs(S10, l3=(
            "    - {id: r1-eth0-10, node: r1, name: eth0.10,"
            " attaches_to: {subinterface: subif-r1-eth0-10}, ip: 192.168.10.1/24}\n"
            "    - {id: r1-bond0, node: r1, name: bond0, attaches_to: {lag: lag-r1-bond0},"
            " ip: 10.0.0.1/30}\n"
        ))))
        r1 = self._node(out, "r1")
        assert r1["subinterfaces"] == [
            {"id": "subif-r1-eth0-10", "parent": "r1-eth0", "vlan_id": 10, "name": "eth0.10"}
        ]
        kinds = {x["interface"]: x for x in r1["l3_interfaces"]}
        assert kinds["eth0.10"]["kind"] == "subinterface" and kinds["eth0.10"]["vlan_id"] == 10
        assert kinds["bond0"]["kind"] == "routed" and kinds["bond0"]["lag"] == "lag-r1-bond0"

    def test_cytoscape_mlag_subif_on_both_nodes(self):
        out = cytoscape.export(_topo(_subifs(
            "    - {id: subif-mlag-a-10, attaches_to: {lag: lag-mlag-a}, vlan_id: 10}\n"
        )))
        assert "subinterfaces" in self._node(out, "r1")
        assert "subinterfaces" in self._node(out, "r2")
        assert "subinterfaces" not in self._node(out, "r3")

    def test_yaml_round_trip(self):
        t1 = _topo(_subifs(S10, l3=(
            "    - {id: r1-eth0-10, node: r1, name: eth0.10,"
            " attaches_to: {subinterface: subif-r1-eth0-10}, ip: 192.168.10.1/24}\n"
        )))
        t2 = parse(yaml_exporter.export(t1))
        assert t1.model_dump() == t2.model_dump()


# ---------------------------------------------------------------------------
# 旧形式 (ndl_version 1.x の間だけ受け付ける。ADR-0001 D8)
# ---------------------------------------------------------------------------

class TestLegacyInterfaceKey:
    def test_subif_on_lag_via_interface_key(self):
        r = validate_all(_topo(_subifs(
            "    - {id: subif-r1-bond0-10, attaches_to: {interface: lag-r1-bond0}, vlan_id: 10}\n"
        )))
        assert r.errors == []
        assert [w.path for w in r.warnings] == ["layer2.subinterfaces[0].attaches_to.interface"]
        assert "{lag: lag-r1-bond0}" in r.warnings[0].message

    @pytest.mark.parametrize("ref,key", [("subif-r1-eth0-10", "subinterface"), ("lag-r1-bond0", "lag")])
    def test_l3_via_interface_key(self, ref, key):
        r = validate_all(_topo(_subifs(S10, l3=(
            f"    - {{id: r1-x, node: r1, name: x, attaches_to: {{interface: {ref}}}}}\n"
        ))))
        assert r.errors == []
        assert [w.path for w in r.warnings] == ["layer3.interfaces[0].attaches_to.interface"]
        assert f"{{{key}: {ref}}}" in r.warnings[0].message

    def test_legacy_reference_still_checks_node(self):
        errs = _errors(_subifs(S10, l3=(
            "    - {id: r2-x, node: r2, name: x, attaches_to: {interface: subif-r1-eth0-10}}\n"
        )))
        assert any("サブインターフェース" in e and "r2" in e for e in errs)
