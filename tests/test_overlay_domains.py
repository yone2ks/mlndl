"""ADR-0029 オーバーレイのドメイン (layer2.overlay_domains と VTEP の overlay_domain) のテスト"""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest
import yaml

from mlndl import parse, validate, validate_all
from mlndl.derive import (IMPLICIT_DOMAIN, l2vni_domain_gateways, l2vni_tunnel_pairs, l3vni_overlay_domains,
                          l3vni_tunnel_pairs, vtep_overlay_domains)
from mlndl.exporter import cytoscape

FIXTURES = Path(__file__).parent / "fixtures"
MULTISITE = FIXTURES / "valid_evpn_multisite.yaml"
BGWS = {"a-bgw1", "a-bgw2", "b-bgw1", "b-bgw2"}


def _data() -> dict:
    return yaml.safe_load(MULTISITE.read_text())


def _topo(data: dict):
    return parse(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _vtep(data: dict, vid: str) -> dict:
    return next(v for v in data["layer2"]["vteps"] if v["id"] == vid)


def _l2vni(data: dict) -> dict:
    return next(v for v in data["layer2"]["vxlans"] if v["type"] == "l2vni")


def _messages(result, severity: str) -> list[str]:
    items = result.errors if severity == "error" else result.warnings
    return [e.message for e in items]


# ── 見本 ─────────────────────────────────────────────────────────────────

def test_multisite_fixture_is_valid_without_warnings():
    result = validate_all(_topo(_data()))
    assert result.errors == []
    assert result.warnings == []          # BGW の ADR-0026 D5 の 10 の warning も出ない (D6)


def test_fixtures_without_domains_are_unchanged():
    t = parse((FIXTURES / "valid_full_dc.yaml").read_text())
    assert set(vtep_overlay_domains(t).values()) == {IMPLICIT_DOMAIN}
    assert validate(t) == []


# ── 導出 (D4) ────────────────────────────────────────────────────────────

def test_tunnel_pairs_stay_inside_each_domain():
    t = _topo(_data())
    pairs = l2vni_tunnel_pairs(t)["vni-10100"]
    assert len(pairs) == 7                # サイトの中が 3 対ずつ + DCI が 1 対 (全 VTEP のフルメッシュなら 28 対)
    domain_of = vtep_overlay_domains(t)
    assert all(domain_of[a] == domain_of[b] == d for a, b, d in pairs)
    assert ("vtep-a-bgw-msvip", "vtep-b-bgw-msvip", "od-dci") in pairs


def test_bgws_are_the_domain_gateways():
    assert l2vni_domain_gateways(_topo(_data()))["vni-10100"] == BGWS


def test_l3vni_takes_the_domains_of_the_l2vnis_in_its_vrf():
    t = _topo(_data())
    assert set(l3vni_overlay_domains(t)["vni-10900"]) == {"od-site-a", "od-site-b", "od-dci"}
    assert len(l3vni_tunnel_pairs(t)["vni-10900"]) == 7


def test_implicit_domain_keeps_the_full_mesh():
    data = _data()
    data["layer2"].pop("overlay_domains")
    for v in data["layer2"]["vteps"]:
        v.pop("overlay_domain")
    t = _topo(data)
    assert len(l2vni_tunnel_pairs(t)["vni-10100"]) == 28
    assert l2vni_domain_gateways(t)["vni-10100"] == set()


# ── 検査 (D5・D6) ────────────────────────────────────────────────────────

def test_l2vni_across_domains_without_a_gateway_is_an_error():
    data = _data()
    _l2vni(data)["vteps"] = [t for t in _l2vni(data)["vteps"] if not t.endswith("-msvip")]
    errors = [e.message for e in validate(_topo(data))]
    assert any("2 つのオーバーレイのドメイン (od-site-a / od-site-b)" in m and "ドメインをつなぐ機器" in m for m in errors)


def test_mixing_vteps_with_and_without_a_domain_is_an_error():
    data = _data()
    _vtep(data, "vtep-b-leaf1").pop("overlay_domain")
    errors = [e.message for e in validate(_topo(data))]
    assert any("vtep-b-leaf1 には書いてありません" in m for m in errors)
    assert not any("ドメインをつなぐ機器" in m for m in errors)     # 重ねて出さない


def test_undefined_domain_is_reported_once():
    data = _data()
    _vtep(data, "vtep-a-leaf1")["overlay_domain"] = "od-nowhere"
    errors = [e.message for e in validate(_topo(data))]
    assert any("未定義のオーバーレイのドメイン 'od-nowhere'" in m for m in errors)
    assert not any("ドメインをつなぐ機器" in m for m in errors)


def test_domain_without_vteps_is_a_warning():
    data = _data()
    data["layer2"]["overlay_domains"].append({"id": "od-spare"})
    result = validate_all(_topo(data))
    assert result.errors == []
    assert any("'od-spare' に属する VTEP がありません" in m for m in _messages(result, "warning"))


def test_domain_with_one_vtep_is_not_reported():
    data = _data()
    data["layer2"]["overlay_domains"].append({"id": "od-lab"})
    _vtep(data, "vtep-a-leaf2")["overlay_domain"] = "od-lab"
    result = validate_all(_topo(data))
    assert not any("od-lab" in m for m in _messages(result, "error") + _messages(result, "warning"))


def test_domain_prefix_is_recommended():
    data = _data()
    data["layer2"]["overlay_domains"][0]["id"] = "east"
    for v in data["layer2"]["vteps"]:
        if v["overlay_domain"] == "od-site-a":
            v["overlay_domain"] = "east"
    result = validate_all(_topo(data))
    assert any("推奨プレフィックス 'od-'" in m for m in _messages(result, "warning"))


def test_bgw_warning_comes_back_without_domains():
    data = _data()
    data["layer2"].pop("overlay_domains")
    for v in data["layer2"]["vteps"]:
        v.pop("overlay_domain")
    warnings = _messages(validate_all(_topo(data)), "warning")
    flagged = {n for n in BGWS if any(f"機器 '{n}' は VTEP で L2VNI" in m for m in warnings)}
    assert flagged == BGWS


def test_overlay_domain_rejects_unknown_keys():
    data = _data()
    data["layer2"]["overlay_domains"][0]["members"] = ["vtep-a-leaf1"]
    with pytest.raises((pydantic.ValidationError, ValueError)):
        _topo(data)


# ── エクスポーター (D7) ──────────────────────────────────────────────────

def _cy(data: dict) -> dict:
    return cytoscape.export(_topo(data))


def test_exporter_outputs_domains_and_tunnel_pairs():
    out = _cy(_data())
    nodes = {n["data"]["id"]: n["data"] for n in out["nodes"]}
    assert nodes["od-dci"]["type"] == "overlay_domain"
    assert nodes["od-dci"]["vteps"] == ["vtep-a-bgw-msvip", "vtep-b-bgw-msvip"]
    l2 = nodes["vni-10100"]
    assert {"endpoints": ["vtep-a-bgw-msvip", "vtep-b-bgw-msvip"], "overlay_domain": "od-dci"} in l2["tunnel_pairs"]
    assert len(l2["tunnel_pairs"]) == 7
    l3 = nodes["vni-10900"]
    assert set(l3["overlay_domains"]) == {"od-site-a", "od-site-b", "od-dci"}
    assert "vtep-a-bgw-msvip" in l3["vteps"]          # BGW は VRF の L3 IF を書かないが、トンネルの対から足す
    bgw_vteps = {v["id"]: v.get("overlay_domain") for v in nodes["a-bgw1"]["vteps"]}
    assert bgw_vteps == {"vtep-a-bgw-vip": "od-site-a", "vtep-a-bgw-msvip": "od-dci"}


def test_exporter_says_nothing_new_without_domains():
    out = cytoscape.export(parse((FIXTURES / "valid_full_dc.yaml").read_text()))
    for n in out["nodes"]:
        d = n["data"]
        assert d["type"] != "overlay_domain"
        assert "tunnel_pairs" not in d and "overlay_domains" not in d
        assert all("overlay_domain" not in v for v in d.get("vteps", []) if isinstance(v, dict))
