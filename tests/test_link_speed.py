"""link_speed の書式 (ADR-0021)"""
from __future__ import annotations

import pytest

from mlndl import parse
from mlndl.exporter import yaml as yaml_exporter
from mlndl.schema.layer1 import canonical_link_speed, link_speed_bps
from mlndl.validator import validate_all


def _topo(speed: str) -> str:
    return (
        'ndl_version: "1.0"\n'
        "layer1:\n"
        "  nodes: [{id: a}, {id: b}]\n"
        "  interfaces: [{id: a-e1, node: a}, {id: b-e1, node: b}]\n"
        f"  links: [{{id: link-a-b, endpoints: [a-e1, b-e1], link_speed: {speed}}}]\n"
    )


@pytest.mark.parametrize("speed", ["10G", "2.5G", "1.6T", "1.544M", "155.52M", "9.95328G", "64K", "9.6K", "800G", "100M"])
def test_canonical_values_pass_without_warning(speed):
    result = validate_all(parse(_topo(speed)))
    assert result.ok
    assert not [w for w in result.warnings if "link_speed" in w.path]


@pytest.mark.parametrize("speed, fixed, reason", [
    ("10g", "10G", "大文字"),
    ("64k", "64K", "大文字"),
    ("10Gbps", "10G", "bps"),
    ("10Gb", "10G", "bps"),
    ('"10 G"', "10G", "空白"),
    (".5G", "0.5G", "数値"),
    ("10.G", "10G", "数値"),
    ("01G", "1G", "数値"),
])
def test_format_error_shows_fix(speed, fixed, reason):
    with pytest.raises(Exception) as e:
        parse(_topo(speed))
    assert f"'{fixed}' と書きます" in str(e.value)
    assert reason in str(e.value)


@pytest.mark.parametrize("speed", ["10GB", "10GBps"])
def test_bytes_are_rejected(speed):
    with pytest.raises(Exception, match="バイト"):
        parse(_topo(speed))


@pytest.mark.parametrize("speed", ["10000", "10", '"10000"'])
def test_number_without_unit_is_error_and_not_guessed(speed):
    with pytest.raises(Exception, match="単位が要ります"):
        parse(_topo(speed))


@pytest.mark.parametrize("speed", ["0G", "0.0G", "-10G", "1e3G", "fast", "10P"])
def test_other_malformed_values_are_errors(speed):
    with pytest.raises(Exception, match="ADR-0021"):
        parse(_topo(speed))


@pytest.mark.parametrize("speed, canonical", [
    ("1000G", "1T"),
    ("1000M", "1G"),
    ("1000K", "1M"),
    ("2500M", "2.5G"),
    ("2048K", "2.048M"),
    ("1544K", "1.544M"),
    ("0.5G", "500M"),
    ("0.064M", "64K"),
    ("10.0G", "10G"),
    ("1.5440M", "1.544M"),
])
def test_non_canonical_is_warning_and_kept_as_written(speed, canonical):
    topo = parse(_topo(speed))
    result = validate_all(topo)
    assert result.ok
    warnings = [w for w in result.warnings if w.path == "layer1.links[0].link_speed"]
    assert len(warnings) == 1 and f"'{canonical}'" in warnings[0].message
    # 表記は書き換えない (ADR-0021 D3)
    assert topo.layer1.links[0].link_speed == speed
    assert f"link_speed: {speed}" in yaml_exporter.export(topo)


@pytest.mark.parametrize("speed", ["0.3K", "1200T"])
def test_no_shift_beyond_end_units(speed):
    assert canonical_link_speed(speed) == speed
    assert validate_all(parse(_topo(speed))).warnings == []


def test_values_are_decimal_bits_per_second():
    assert link_speed_bps("1K") == 1000
    assert link_speed_bps("2.5G") == link_speed_bps("2500M") == 2_500_000_000
    assert link_speed_bps("1.6T") == 1_600_000_000_000
