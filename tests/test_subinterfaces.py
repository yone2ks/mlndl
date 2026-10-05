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
        assert (si.attaches_to.interface, si.vlan_id, si.name) == ("r1-eth0", 10, "eth0.10")

    @pytest.mark.parametrize("vid", [0, 4095, 4096])
    def test_vlan_id_range(self, vid):
        """IEEE 802.1Q: 0 と 4095 は予約"""
        _parse_error(_subifs(f"    - {{id: subif-x, attaches_to: {{interface: r1-eth0}}, vlan_id: {vid}}}\n"))

    def test_string_attaches_to_is_rejected(self):
        """文字列の attaches_to はノード ID の糖衣構文 (ADR-0001)。サブ IF の親にはならない"""
        msg = _parse_error(_subifs("    - {id: subif-x, attaches_to: r1, vlan_id: 10}\n"))
        assert "{interface:" in msg

    @pytest.mark.parametrize("key", ["node: r1", "link: link-x"])
    def test_non_interface_key_is_rejected(self, key):
        _parse_error(_subifs(f"    - {{id: subif-x, attaches_to: {{{key}}}, vlan_id: 10}}\n"))

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
            "    - {id: subif-r1-bond0-10, attaches_to: {interface: lag-r1-bond0}, vlan_id: 10}\n"
        )) == []

    def test_undefined_parent(self):
        errs = _errors(_subifs("    - {id: subif-x, attaches_to: {interface: nope}, vlan_id: 10}\n"))
        assert any("nope" in e for e in errs)

    def test_parent_cannot_be_vlan(self):
        """VLAN を親にできるのは L3Interface (SVI) だけ"""
        body = _subifs("    - {id: subif-x, attaches_to: {interface: vlan-10}, vlan_id: 10}\n").replace(
            "layer2:\n", "layer2:\n  vlans: [{id: vlan-10, vlan_id: 10}]\n")
        assert any("vlan-10" in e for e in _errors(body))

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
            "    - {id: r3-eth0, node: r3, attaches_to: {interface: subif-r1-eth0-10}}",
        )
        assert any("subif-r1-eth0-10" in e for e in _errors(body))

    def test_id_space_collision(self):
        """{interface: X} は複数の ID 空間で X を引くので、ID が重複すると解決先が曖昧になる"""
        body = _subifs("    - {id: r1-eth1, attaches_to: {interface: r1-eth0}, vlan_id: 10}\n")
        assert any("ADR-0002 D5" in e and "r1-eth1" in e for e in _errors(body))

    def test_prefix_warning(self):
        r = validate_all(_topo(_subifs("    - {id: eth0-10, attaches_to: {interface: r1-eth0}, vlan_id: 10}\n")))
        assert [w.path for w in r.warnings] == ["layer2.subinterfaces[0].id"]


class TestL3OnSubinterface:
    def test_l3_on_subif(self):
        assert _errors(_subifs(S10, l3=(
            "    - {id: r1-eth0-10, node: r1, interface: eth0.10,"
            " attaches_to: {interface: subif-r1-eth0-10}, ip: 192.168.10.1/24}\n"
        ))) == []

    def test_l3_on_other_nodes_subif(self):
        errs = _errors(_subifs(S10, l3=(
            "    - {id: r2-x, node: r2, interface: eth0.10, attaches_to: {interface: subif-r1-eth0-10}}\n"
        )))
        assert any("サブインターフェース" in e and "r2" in e for e in errs)

    def test_routed_lag(self):
        assert _errors(_subifs(S10, l3=(
            "    - {id: r1-bond0, node: r1, interface: bond0, attaches_to: {interface: lag-r1-bond0},"
            " ip: 10.0.0.1/30}\n"
        ))) == []

    def test_routed_lag_on_other_node(self):
        errs = _errors(_subifs(S10, l3=(
            "    - {id: r2-bond0, node: r2, interface: bond0, attaches_to: {interface: lag-r1-bond0}}\n"
        )))
        assert any("LAG" in e and "r2" in e for e in errs)

    @pytest.mark.parametrize("node,ok", [("r1", True), ("r2", True), ("r3", False)])
    def test_subif_on_mlag_belongs_to_both_nodes(self, node, ok):
        errs = _errors(_subifs(
            "    - {id: subif-mlag-a-10, attaches_to: {interface: lag-mlag-a}, vlan_id: 10}\n",
            l3=f"    - {{id: {node}-x, node: {node}, interface: po1.10, attaches_to: {{interface: subif-mlag-a-10}}}}\n",
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
            "    - {id: r1-eth0-10, node: r1, interface: eth0.10,"
            " attaches_to: {interface: subif-r1-eth0-10}, ip: 192.168.10.1/24}\n"
            "    - {id: r1-bond0, node: r1, interface: bond0, attaches_to: {interface: lag-r1-bond0},"
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
            "    - {id: subif-mlag-a-10, attaches_to: {interface: lag-mlag-a}, vlan_id: 10}\n"
        )))
        assert "subinterfaces" in self._node(out, "r1")
        assert "subinterfaces" in self._node(out, "r2")
        assert "subinterfaces" not in self._node(out, "r3")

    def test_yaml_round_trip(self):
        t1 = _topo(_subifs(S10, l3=(
            "    - {id: r1-eth0-10, node: r1, interface: eth0.10,"
            " attaches_to: {interface: subif-r1-eth0-10}, ip: 192.168.10.1/24}\n"
        )))
        t2 = parse(yaml_exporter.export(t1))
        assert t1.model_dump() == t2.model_dump()
