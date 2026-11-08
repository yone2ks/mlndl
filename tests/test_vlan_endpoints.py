"""ADR-0013 D7 VLAN の端点の導出のテスト"""

from __future__ import annotations

from mlndl import parse, validate_all
from mlndl.derive import vlan_endpoints
from mlndl.exporter import cytoscape


def _topo(l1: str, l2: str, l3: str = ""):
    return parse('ndl_version: "1.0"\nlayer1:\n' + l1 + "layer2:\n" + l2 + ("layer3:\n" + l3 if l3 else ""))


def _eps(t, vlan: str):
    return [ep for ep in vlan_endpoints(t) if ep.vlan == vlan]


# leaf1 の swp1 に host1 (L1 IF は eth0、L3 IF の名前は ens3)
ACCESS_L1 = """
  nodes: [{id: leaf1}, {id: host1}]
  interfaces:
    - {id: leaf1-swp1, node: leaf1, name: swp1}
    - {id: host1-eth0, node: host1, name: eth0}
  links:
    - {id: link-leaf1-host1, endpoints: [leaf1-swp1, host1-eth0]}
"""


def test_access_port_resolves_by_reference_not_name():
    """L1 IF と L3 IF の名前が違っても、attaches_to の参照で引く (ADR-0011 D3)"""
    t = _topo(ACCESS_L1,
              "  vlans: [{id: vlan-10, vlan_id: 10, access_ports: [{interface: leaf1-swp1}]}]\n",
              "  interfaces:\n"
              "    - {id: host1-ens3, node: host1, name: ens3, ip: 192.168.10.5/24, attaches_to: {interface: host1-eth0}}\n"
              "    - {id: host1-eth0-x, node: host1, name: eth0, ip: 10.9.9.9/24}\n")   # 名前は一致するが参照していない
    (ep,) = _eps(t, "vlan-10")
    assert (ep.port_node, ep.node, ep.interfaces, ep.resolution) == ("leaf1", "host1", ["host1-eth0"], "direct")
    assert [l3.id for l3 in ep.l3_interfaces] == ["host1-ens3"]


def test_unlinked_port_and_host_without_l3():
    """リンクのないポートは端点を持たない。L3 IF のない対向は no_l3 (IF までは確定)"""
    l1 = ACCESS_L1.replace("  links:", "    - {id: leaf1-swp2, node: leaf1, name: swp2}\n  links:")
    t = _topo(l1, "  vlans: [{id: vlan-10, vlan_id: 10, access_ports: [{interface: leaf1-swp1}, {interface: leaf1-swp2}]}]\n")
    (ep,) = _eps(t, "vlan-10")
    assert ep.resolution == "no_l3" and ep.l3_interfaces == []


# hv1 に trunk。eth0 の上に native (素の L3) と、タグ 100 / 200 のサブ IF
TRUNK_L1 = """
  nodes: [{id: leaf1}, {id: hv1}]
  interfaces:
    - {id: leaf1-swp1, node: leaf1, name: swp1}
    - {id: hv1-eth0, node: hv1, name: eth0}
  links:
    - {id: link-leaf1-hv1, endpoints: [leaf1-swp1, hv1-eth0]}
"""
TRUNK_L2 = """
  vlans:
    - {id: vlan-1, vlan_id: 1, trunk_ports: [{interface: leaf1-swp1, native: true}]}
    - {id: vlan-100, vlan_id: 100, trunk_ports: [{interface: leaf1-swp1}]}
    - {id: vlan-300, vlan_id: 300, trunk_ports: [{interface: leaf1-swp1}]}
  subinterfaces:
    - {id: subif-hv1-eth0-100, attaches_to: {interface: hv1-eth0}, vlan_id: 100, name: eth0.100}
    - {id: subif-hv1-eth0-200, attaches_to: {interface: hv1-eth0}, vlan_id: 200, name: eth0.200}
"""
TRUNK_L3 = """
  interfaces:
    - {id: hv1-mgmt, node: hv1, name: eth0, ip: 10.0.1.5/24, attaches_to: {interface: hv1-eth0}}
    - {id: hv1-v100, node: hv1, name: eth0.100, ip: 10.0.100.5/24, attaches_to: {subinterface: subif-hv1-eth0-100}}
    - {id: hv1-v200, node: hv1, name: eth0.200, ip: 10.0.200.5/24, attaches_to: {subinterface: subif-hv1-eth0-200}}
"""


def test_native_vs_tagged_trunk():
    """native は素の L3 IF で確定。tagged はタグの一致するサブ IF で推定。一致しなければ L3 IF なし"""
    t = _topo(TRUNK_L1, TRUNK_L2, TRUNK_L3)
    (native,) = _eps(t, "vlan-1")
    assert (native.resolution, [x.id for x in native.l3_interfaces]) == ("direct", ["hv1-mgmt"])
    (v100,) = _eps(t, "vlan-100")
    assert (v100.tagged, v100.resolution, [x.id for x in v100.l3_interfaces]) == (True, "tag_match", ["hv1-v100"])
    # 素の L3 IF (mgmt) は tagged の VLAN の IP ではない
    (v300,) = _eps(t, "vlan-300")
    assert (v300.resolution, v300.l3_interfaces) == ("no_l3", [])


def test_two_l3_on_one_interface_is_ambiguous():
    t = _topo(ACCESS_L1,
              "  vlans: [{id: vlan-10, vlan_id: 10, access_ports: [{interface: leaf1-swp1}]}]\n",
              "  interfaces:\n"
              "    - {id: host1-a, node: host1, name: eth0, ip: 192.168.10.5/24, attaches_to: {interface: host1-eth0}}\n"
              "    - {id: host1-b, node: host1, name: eth0:1, ip: 192.168.10.6/24, attaches_to: {interface: host1-eth0}}\n")
    (ep,) = _eps(t, "vlan-10")
    assert ep.resolution == "ambiguous" and {x.id for x in ep.l3_interfaces} == {"host1-a", "host1-b"}


MLAG_L1 = """
  nodes: [{id: leaf1}, {id: leaf2}, {id: srv1}]
  interfaces:
    - {id: leaf1-swp1, node: leaf1, name: swp1}
    - {id: leaf2-swp1, node: leaf2, name: swp1}
    - {id: leaf1-swp49, node: leaf1, name: swp49}
    - {id: srv1-eth0, node: srv1, name: eth0}
    - {id: srv1-eth1, node: srv1, name: eth1}
  links:
    - {id: link-leaf1-srv1, endpoints: [leaf1-swp1, srv1-eth0]}
    - {id: link-leaf2-srv1, endpoints: [leaf2-swp1, srv1-eth1]}
  lag:
    - {id: lag-peer, node: leaf1, members: [leaf1-swp49]}
    - {id: lag-leaf1-srv1, node: leaf1, members: [leaf1-swp1]}
    - {id: lag-leaf2-srv1, node: leaf2, members: [leaf2-swp1]}
    - {id: lag-srv1-bond0, node: srv1, members: [srv1-eth0, srv1-eth1]}
  ethernet_segments:
    - {id: es-srv1, members: [{lag: lag-leaf1-srv1}, {lag: lag-leaf2-srv1}]}
"""


def test_mlag_to_host_bond():
    """Ethernet Segment の脚は、ポートのノードごとに 1 つの端点。L3 IF は bond の上のもの (ADR-0023)"""
    t = _topo(MLAG_L1,
              "  vlans: [{id: vlan-10, vlan_id: 10, access_ports: [{ethernet_segment: es-srv1}]}]\n",
              "  interfaces:\n"
              "    - {id: srv1-bond0, node: srv1, name: bond0, ip: 10.1.10.10/24, attaches_to: {lag: lag-srv1-bond0}}\n")
    eps = _eps(t, "vlan-10")
    assert sorted((ep.port_node, tuple(ep.interfaces)) for ep in eps) == [
        ("leaf1", ("srv1-eth0",)), ("leaf2", ("srv1-eth1",))]
    assert all(ep.lag == "lag-srv1-bond0" and ep.resolution == "direct"
               and ep.l3_interfaces[0].id == "srv1-bond0" for ep in eps)


def test_links_between_ports_are_not_endpoints_and_one_hop_only():
    """スイッチ間の trunk (両端とも VLAN のポート) は数えない。端点は 1 ホップで、L2 スイッチの先はそのスイッチのポートから"""
    l1 = """
  nodes: [{id: leaf1}, {id: sw1}, {id: host1}]
  interfaces:
    - {id: leaf1-swp1, node: leaf1, name: swp1}
    - {id: sw1-up, node: sw1, name: gi0/1}
    - {id: sw1-down, node: sw1, name: gi0/2}
    - {id: host1-eth0, node: host1, name: eth0}
  links:
    - {id: link-leaf1-sw1, endpoints: [leaf1-swp1, sw1-up]}
    - {id: link-sw1-host1, endpoints: [sw1-down, host1-eth0]}
"""
    l3 = "  interfaces:\n    - {id: host1-l3, node: host1, name: eth0, ip: 192.168.30.10/24, attaches_to: {interface: host1-eth0}}\n"
    both = _topo(l1, "  vlans: [{id: vlan-30, vlan_id: 30, trunk_ports: [{interface: leaf1-swp1}, {interface: sw1-up}],"
                     " access_ports: [{interface: sw1-down}]}]\n", l3)
    assert [(ep.port_node, ep.node, ep.resolution) for ep in _eps(both, "vlan-30")] == [("sw1", "host1", "direct")]
    # 途中のスイッチの VLAN 設定がなければ、その先はたどらない (sw1 は L3 IF のない端点)
    leaf_only = _topo(l1, "  vlans: [{id: vlan-30, vlan_id: 30, trunk_ports: [{interface: leaf1-swp1}]}]\n", l3)
    assert [(ep.node, ep.resolution) for ep in _eps(leaf_only, "vlan-30")] == [("sw1", "no_l3")]


def test_outside_svi_subnet_is_info():
    l3 = ("  interfaces:\n"
          "    - {id: leaf1-vlan-10, node: leaf1, name: Vlan10, ip: 172.16.10.1/24, attaches_to: {vlan: vlan-10}}\n"
          "    - {id: host1-l3, node: host1, name: eth0, ip: 172.16.20.5/24, attaches_to: {interface: host1-eth0}}\n")
    t = _topo(ACCESS_L1, "  vlans: [{id: vlan-10, vlan_id: 10, access_ports: [{interface: leaf1-swp1}]}]\n", l3)
    r = validate_all(t)
    assert not r.errors
    assert [n.path for n in r.notes] == ["layer3.interfaces[1]"] and "172.16.10.0/24" in r.notes[0].message
    member = next(e["data"] for e in cytoscape.export(t)["edges"] if e["data"]["type"] == "vlan_member")
    assert member["endpoints"][0]["outside_svi_subnet"] == ["172.16.20.5/24"]
    # SVI のない VLAN (L2 だけのセグメント) は検査しない
    t2 = _topo(ACCESS_L1, "  vlans: [{id: vlan-10, vlan_id: 10, access_ports: [{interface: leaf1-swp1}]}]\n",
               "  interfaces:\n    - {id: host1-l3, node: host1, name: eth0, ip: 172.16.20.5/24,"
               " attaches_to: {interface: host1-eth0}}\n")
    assert not validate_all(t2).notes


def test_cytoscape_endpoints_on_vlan_member():
    t = _topo(TRUNK_L1, TRUNK_L2, TRUNK_L3)
    edges = {e["data"]["source"]: e["data"] for e in cytoscape.export(t)["edges"] if e["data"]["type"] == "vlan_member"}
    assert edges["vlan-100"]["endpoints"] == [{
        "node": "hv1", "interfaces": ["hv1-eth0"], "interface_names": ["eth0"], "tagged": True,
        "resolution": "tag_match", "l3_interface": "hv1-v100", "name": "eth0.100", "ip": "10.0.100.5/24",
    }]
    assert edges["vlan-300"]["endpoints"][0]["resolution"] == "no_l3"
    assert "ip" not in edges["vlan-300"]["endpoints"][0]
