"""ADR-0028 1.0 の前の名前と型の直し

D1 一覧の名前 (lags / vxlans)、D2 IS-IS の level、D3 空のリスト、D4 LAG の束ね方 (lacp.mode・static・min_links) と既定値、
D5 値域、D7 旧名・旧値の error
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pydantic
import pytest

from mlndl import parse, validate_all
from mlndl.exporter import cytoscape

ROOT = Path(__file__).parent.parent

L1 = """ndl_version: "1.0"
layer1:
  nodes:
    - {id: leaf1}
    - {id: leaf2}
  interfaces:
    - {id: leaf1-swp1, node: leaf1, name: swp1}
    - {id: leaf1-swp2, node: leaf1, name: swp2}
    - {id: leaf2-swp1, node: leaf2, name: swp1}
  links:
    - {id: link-leaf1-leaf2, endpoints: [leaf1-swp1, leaf2-swp1]}
"""

LAG = "    - {id: lag-leaf1-bond1, node: leaf1, members: [leaf1-swp1, leaf1-swp2]%s}\n"


def _lag(extra: str = "") -> str:
    return L1 + "  lags:\n" + LAG % extra


L3_AND_BGP = """layer3:
  interfaces:
    - {id: leaf1-swp1-l3, node: leaf1, name: swp1, ip: 10.0.0.0/31, attaches_to: {interface: leaf1-swp1}}
    - {id: leaf2-swp1-l3, node: leaf2, name: swp1, ip: 10.0.0.1/31, attaches_to: {interface: leaf2-swp1}}
control_plane:
  bgp:
    - {id: bgp-default, nodes: [{node: leaf1, local_as: %s}, {node: leaf2, local_as: 65002}]}
  routing_neighbors:
    - {id: bgp-peer-leaf1-leaf2, type: bgp, from: {node: leaf1, update_source: leaf1-swp1-l3},
       to: {node: leaf2, update_source: leaf2-swp1-l3}%s}
"""


def _bgp(local_as: str = "65001", session: str = ", address_families: [ipv4_unicast]") -> str:
    return L1 + L3_AND_BGP % (local_as, session)


def _error(text: str) -> pydantic.ValidationError:
    with pytest.raises(pydantic.ValidationError) as exc:
        parse(text)
    return exc.value


def _messages(text: str) -> list[str]:
    return [e["msg"] for e in _error(text).errors()]


def _ok(text: str):
    t = parse(text)
    r = validate_all(t)
    assert r.errors == [] and r.warnings == [], (r.errors, r.warnings)
    return t


# ---------------------------------------------------------------------------
# D1・D7: 一覧の名前
# ---------------------------------------------------------------------------

class TestCollectionNames:
    def test_lags_and_vxlans(self):
        t = _ok(_lag())
        assert [g.id for g in t.layer1.lags] == ["lag-leaf1-bond1"]

    def test_old_lag_points_to_lags(self):
        (msg,) = _messages(L1 + "  lag:\n" + LAG % "")
        assert "layer1.lag は layer1.lags に改名しました" in msg

    def test_old_vxlan_points_to_vxlans(self):
        (msg,) = _messages(L1 + "layer2:\n  vxlan: []\n")
        assert "layer2.vxlan は layer2.vxlans に改名しました" in msg

    def test_old_name_is_not_repeated_as_extra_input(self):
        """旧名と未知のキーを一緒に書いても、出るのは移動先の案内だけ (extra="forbid" と重ならない)"""
        errors = _error(L1 + "  lag: []\n  foo: 1\n").errors()
        assert len(errors) == 1 and "layer1.lags に改名しました" in errors[0]["msg"]

    def test_reference_keys_stay_singular(self):
        """1 つを指す参照キーは単数のまま: attaches_to: {lag:}"""
        _ok(_lag() + "layer3:\n  interfaces:\n"
                     "    - {id: leaf1-bond1-l3, node: leaf1, name: bond1, ip: 10.9.0.0/31, attaches_to: {lag: lag-leaf1-bond1}}\n")

    def test_error_paths_use_new_names(self):
        r = validate_all(parse(_lag().replace("members: [leaf1-swp1, leaf1-swp2]", "members: [leaf1-swp9]")))
        assert [e.path for e in r.errors] == ["layer1.lags[0].members[0]"]


# ---------------------------------------------------------------------------
# D2・D7: IS-IS の level
# ---------------------------------------------------------------------------

ISIS = L1 + """control_plane:
  isis:
    - {id: isis-default, nodes: [{node: leaf1}, {node: leaf2}]}
  routing_neighbors:
    - {id: isis-adj-leaf1-leaf2, type: isis, from: {node: leaf1, interface: leaf1-swp1},
       to: {node: leaf2, interface: leaf2-swp1}, level: %s}
"""


class TestIsisLevel:
    @pytest.mark.parametrize("level", ["level_1", "level_2", "level_all"])
    def test_underscore(self, level):
        t = _ok(ISIS % level)
        assert t.control_plane.routing_neighbors[0].level == level

    @pytest.mark.parametrize("old,new", [("level-1", "level_1"), ("level-2", "level_2"), ("level-all", "level_all")])
    def test_hyphen_points_to_underscore(self, old, new):
        (msg,) = _messages(ISIS % old)
        assert "ハイフンではなく下線" in msg and f"{old} → {new}" in msg

    def test_exported_as_written(self):
        out = cytoscape.export(parse(ISIS % "level_2"))
        (edge,) = [e for e in out["edges"] if e["data"]["type"] == "routing_neighbor"]
        assert edge["data"]["level"] == "level_2"


# ---------------------------------------------------------------------------
# D4・D7: LAG の束ね方
# ---------------------------------------------------------------------------

class TestLacp:
    @pytest.mark.parametrize("mode", ["active", "passive", "static"])
    def test_modes(self, mode):
        t = _ok(_lag(f", lacp: {{mode: {mode}}}"))
        assert t.layer1.lags[0].lacp.mode == mode

    def test_lacp_not_written(self):
        """lacp を書かない LAG は「束ね方を書いていない」。既定値で埋めない"""
        lag = _ok(_lag()).layer1.lags[0]
        assert lag.lacp is None and lag.min_links is None

    def test_quoted_on_points_to_static(self):
        (msg,) = _messages(_lag(', lacp: {mode: "on"}'))
        assert "on は static に改名しました" in msg

    @pytest.mark.parametrize("raw", ["on", "off", "yes", "true"])
    def test_yaml_boolean(self, raw):
        """引用符なしの on などは YAML 1.1 で真偽値になる"""
        (msg,) = _messages(_lag(f", lacp: {{mode: {raw}}}"))
        assert "真偽値として読みました" in msg and "mode: static" in msg

    def test_empty_lacp(self):
        (msg,) = _messages(_lag(", lacp: {}"))
        assert "lacp を書くなら mode を書きます" in msg

    def test_min_links_under_lacp_points_to_lag(self):
        (msg,) = _messages(_lag(", lacp: {mode: active, min_links: 2}"))
        assert "LAG の直下 (lags[].min_links) に移しました" in msg

    def test_min_links_on_lag(self):
        """min_links は LACP と独立 (static の LAG でも、lacp を書かない LAG でも書ける)"""
        assert _ok(_lag(", lacp: {mode: static}, min_links: 2")).layer1.lags[0].min_links == 2
        assert _ok(_lag(", min_links: 1")).layer1.lags[0].lacp is None

    def test_export_writes_only_what_is_written(self):
        t = parse(_lag(", lacp: {mode: static}, min_links: 2"))
        (node,) = [n for n in cytoscape.export(t)["nodes"] if n["data"]["id"] == "leaf1"]
        (lag,) = node["data"]["lags"]
        assert lag["lacp"] == {"mode": "static"} and lag["min_links"] == 2
        (node,) = [n for n in cytoscape.export(parse(_lag()))["nodes"] if n["data"]["id"] == "leaf1"]
        assert "lacp" not in node["data"]["lags"][0] and "min_links" not in node["data"]["lags"][0]


# ---------------------------------------------------------------------------
# D3: 要素なしでは成り立たないリスト
# ---------------------------------------------------------------------------

L2 = """layer2:
  vlans: [{id: vlan-10, vlan_id: 10}]
"""


class TestNotEmpty:
    def test_lag_members(self):
        (msg,) = _messages(L1 + "  lags:\n    - {id: lag-leaf1-bond1, node: leaf1, members: []}\n")
        assert "束ねる L1 IF の id を 1 つ以上" in msg

    def test_single_member_lag(self):
        _ok(_lag().replace("members: [leaf1-swp1, leaf1-swp2]", "members: [leaf1-swp2]"))

    def test_ethernet_segment_members(self):
        (msg,) = _messages(_lag() + "  ethernet_segments:\n    - {id: es-a, members: [{lag: lag-leaf1-bond1}]}\n")
        assert "2 つ以上書きます" in msg and "layer1.lags に書けば足ります" in msg

    @pytest.mark.parametrize("ports", ["", ", ports: []"])
    def test_bridge_ports(self, ports):
        (msg,) = _messages(L1 + f"layer2:\n  bridges:\n    - {{id: bridge-a{ports}}}\n")
        assert "bridge の ports に" in msg

    @pytest.mark.parametrize("vteps", ["", ", vteps: []"])
    def test_l2vni_vteps(self, vteps):
        (msg,) = _messages(L1 + L2 + f"  vxlans:\n    - {{id: vni-10010, type: l2vni, vni: 10010, vlans: [vlan-10]{vteps}}}\n")
        assert "vteps: [<layer2.vteps の id>] で書いてください" in msg

    @pytest.mark.parametrize("afs", ["", ", address_families: []"])
    def test_address_families(self, afs):
        (msg,) = _messages(_bgp(session=afs))
        assert "address_families に 1 つ以上" in msg and "[l2vpn_evpn]" in msg

    def test_empty_lists_that_mean_something_are_allowed(self):
        """空に意味のあるリスト (VLAN のポート、インスタンスの nodes) は空のまま書ける"""
        _ok(L1 + "layer2:\n  vlans: [{id: vlan-10, vlan_id: 10, trunk_ports: [], access_ports: []}]\n"
            "control_plane:\n  bgp: [{id: bgp-default, nodes: []}]\n")

    def test_schema_json_has_min_items(self):
        schema = json.loads((ROOT / "docs/reference/schema.json").read_text())
        defs = schema["$defs"]
        assert defs["Lag"]["properties"]["members"]["minItems"] == 1
        assert defs["Bridge"]["properties"]["ports"]["minItems"] == 1
        assert defs["L2VxLAN"]["properties"]["vteps"]["minItems"] == 1
        assert defs["BgpSession"]["properties"]["address_families"]["minItems"] == 1
        assert defs["EthernetSegment"]["properties"]["members"]["minItems"] == 2


# ---------------------------------------------------------------------------
# D4・D5: 既定値と値域
# ---------------------------------------------------------------------------

BFD = L1 + "control_plane:\n  bfd:\n    - {id: bfd-a, nodes: [leaf1, leaf2]%s}\n"


class TestRanges:
    @pytest.mark.parametrize("local_as", ["1", "4294967295", "65535", "23456"])
    def test_local_as_ok(self, local_as):
        _ok(_bgp(local_as))

    @pytest.mark.parametrize("local_as", ["0", "4294967296", "-1"])
    def test_local_as_out_of_range(self, local_as):
        assert len(_messages(_bgp(local_as))) == 1

    def test_outside_local_as(self):
        text = _bgp().replace("to: {node: leaf2, update_source: leaf2-swp1-l3}", "to: {address: 192.0.2.1, local_as: 0}")
        (msg,) = _messages(text)
        assert "greater than or equal to 1" in msg

    @pytest.mark.parametrize("vni,ok", [(1, True), (16777215, True), (0, False), (16777216, False)])
    def test_vni(self, vni, ok):
        text = L1 + "layer2:\n  vxlans:\n    - {id: vni-x, type: l3vni, vni: %d, vrf: vrf-a}\n" \
                    "layer3:\n  vrfs: [{id: vrf-a, l3vni: vni-x}]\n" % vni
        if ok:
            parse(text)
        else:
            assert len(_messages(text)) == 1

    def test_bfd_timers_have_no_default(self):
        bfd = parse(BFD % "").control_plane.bfd[0]
        assert (bfd.min_tx, bfd.min_rx, bfd.multiplier) == (None, None, None)

    @pytest.mark.parametrize("timers,ok", [
        (", min_tx: 1, min_rx: 1, multiplier: 1", True),
        (", min_tx: 300, min_rx: 300, multiplier: 255", True),
        (", min_tx: 0", False),
        (", min_rx: 0", False),
        (", multiplier: 0", False),
        (", multiplier: 256", False),
    ])
    def test_bfd_ranges(self, timers, ok):
        if ok:
            parse(BFD % timers)
        else:
            assert len(_messages(BFD % timers)) == 1

    def test_min_links_range(self):
        assert len(_messages(_lag(", min_links: 0"))) == 1

    @pytest.mark.parametrize("mtu,ok", [(68, True), (65535, True), (67, False), (65536, False)])
    def test_tunnel_mtu(self, mtu, ok):
        text = L1 + """layer3:
  interfaces:
    - {id: leaf1-swp1-l3, node: leaf1, name: swp1, ip: 10.0.0.0/31, attaches_to: {interface: leaf1-swp1}}
  tunnel_interfaces:
    - {id: tunnel-leaf1-x, node: leaf1, type: gre, source: leaf1-swp1-l3, destination_ip: 192.0.2.9, mtu: %d}
""" % mtu
        if ok:
            parse(text)
        else:
            assert len(_messages(text)) == 1


# ---------------------------------------------------------------------------
# 試し書き (Pass C) と CLI
# ---------------------------------------------------------------------------

PASSC = ROOT / "docs/decisions/evaluations/adr0028/passc"


def test_passc_sample_is_valid_without_warnings():
    """1.0 の形で書いた見本 (試し書き P1) は error も warning もない"""
    r = validate_all(parse((PASSC / "p1-full-1.0.yaml").read_bytes()))
    assert r.errors == [] and r.warnings == []


def test_cli_shows_guidance_for_old_names(tmp_path):
    f = tmp_path / "t.yaml"
    f.write_text(L1 + "  lag: []\n")
    r = subprocess.run([sys.executable, "-m", "mlndl", "validate", str(f)], capture_output=True, text=True)
    assert r.returncode == 1
    assert "layer1: layer1.lag は layer1.lags に改名しました" in r.stderr and "Extra inputs" not in r.stderr
