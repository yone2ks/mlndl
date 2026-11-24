"""引用符なしの RD / Route Target の error の文

YAML 1.1 (PyYAML) は引用符なしの 65001:10 を 60 進数の数 (3900070) と読む。
pydantic の既定の文 (Input should be a valid string) ではなく、引用符で囲むよう案内する文にする。
"""

from __future__ import annotations

import pydantic
import pytest

from mlndl import parse, validate_all

DOC = """ndl_version: "1.0"
layer3:
  vrfs:
    - {id: vrf-tenant-a, %s}
"""


def _messages(body: str) -> list[tuple[tuple, str]]:
    with pytest.raises(pydantic.ValidationError) as exc:
        parse(DOC % body)
    return [(e["loc"], e["msg"]) for e in exc.value.errors()]


def test_unquoted_rd():
    ((loc, msg),) = _messages("rd: 65001:10")
    assert loc[-1] == "rd"
    assert '"65001:10" のように引用符で囲んで' in msg and "3900070" in msg


@pytest.mark.parametrize("key", ["import", "export"])
def test_unquoted_route_target(key):
    ((loc, msg),) = _messages('route_targets: {%s: ["65001:100", 65001:10]}' % key)
    assert loc[-1] == key
    assert f"route_targets.{key}" in msg and "引用符で囲んで" in msg and "3900070" in msg


def test_read_value_is_shown():
    """元の値は数から戻せないので、例は一般的なもの。読んだ値は添える"""
    ((_, msg),) = _messages("rd: 65001:20")
    assert "いま読んだ値: 3900080" in msg


def test_sexagesimal_float():
    ((_, msg),) = _messages("rd: 1:10.5")
    assert "引用符で囲んで" in msg


def test_quoted_values_are_valid():
    t = parse(DOC % 'rd: "65001:10", route_targets: {import: ["65001:10"], export: ["10.0.0.1:10"]}')
    assert validate_all(t).errors == []


def test_unquoted_but_read_as_string_is_valid():
    """: のあとが 60 以上なら YAML は文字列のまま読む (引用符は推奨だが error ではない)"""
    t = parse(DOC % "rd: 65001:100, route_targets: {import: [65001:100]}")
    assert validate_all(t).errors == []
