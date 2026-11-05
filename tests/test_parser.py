"""parser: YAML の読み込み (キーの重複・マージキー)"""
import pytest
import yaml

from mlndl.parser import parse

HEAD = 'ndl_version: "1.0"\n'


def test_duplicate_section_key_is_error():
    # 区画を 2 回書くと、前の区画が黙って消えていた
    src = HEAD + """
layer1:
  nodes:
    - {id: leaf1}
  nodes:
    - {id: leaf2}
"""
    with pytest.raises(yaml.YAMLError, match="キー 'nodes' が重複しています"):
        parse(src)


def test_duplicate_key_in_list_item_is_error():
    src = HEAD + """
layer1:
  nodes:
    - id: leaf1
      role: leaf
      role: spine
"""
    with pytest.raises(yaml.YAMLError, match="キー 'role' が重複しています"):
        parse(src)


def test_duplicate_top_level_key_is_error():
    with pytest.raises(yaml.YAMLError, match="キー 'layer1' が重複しています"):
        parse(HEAD + "layer1: {nodes: [{id: a}]}\nlayer1: {nodes: [{id: b}]}\n")


def test_same_key_in_different_mappings_is_fine():
    t = parse(HEAD + """
layer1:
  nodes:
    - {id: leaf1, role: leaf}
    - {id: leaf2, role: leaf}
""")
    assert [n.id for n in t.layer1.nodes] == ["leaf1", "leaf2"]


def test_merge_key_override_is_not_duplicate():
    # << で取り込んだキーを、明示したキーで上書きするのは YAML の仕様どおり (重複ではない)
    t = parse(HEAD + """
layer1:
  nodes:
    - &leaf {id: leaf1, implementation: vm, role: leaf}
    - {<<: *leaf, id: leaf2}
""")
    assert [(n.id, n.role) for n in t.layer1.nodes] == [("leaf1", "leaf"), ("leaf2", "leaf")]
