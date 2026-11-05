"""YAML パーサー

セキュリティ要件 (ADR-0004):
- yaml.SafeLoader で読む（yaml.load() 禁止。任意のオブジェクトを作らせない）
- 入力サイズ上限: MAX_TOPOLOGY_BYTES (1MB)

同じマッピングに同じキーを 2 回書くと error にする。YAML の仕様では誤りだが、PyYAML は
後から書いたほうで黙って上書きし、前に書いた区画 (nodes や interfaces) が消える。
"""

from __future__ import annotations

import yaml

from .constants import MAX_TOPOLOGY_BYTES
from .schema.topology import MLNDLTopology


class _SafeLoader(yaml.SafeLoader):
    """yaml.SafeLoader と同じ。同じマッピングの中のキーの重複だけを error にする"""

    def construct_mapping(self, node, deep=False):
        seen: dict = {}
        for key_node, _ in node.value:
            # << (マージキー) の展開で入るキーは重複とみなさない (明示したキーが優先されるのが仕様)
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=deep)
            try:
                first = seen.get(key)
            except TypeError:  # ハッシュできないキーは、このあとの構築で誤りになる
                continue
            if first is not None:
                raise yaml.constructor.ConstructorError(
                    None, None,
                    f"キー {key!r} が重複しています (最初は {first.line + 1} 行目)。"
                    "同じマッピングに同じキーは 1 回だけ書けます",
                    key_node.start_mark,
                )
            seen[key] = key_node.start_mark
        return super().construct_mapping(node, deep=deep)


def parse(source: str | bytes) -> MLNDLTopology:
    """YAML 文字列またはバイト列から MLNDLTopology を生成する。

    Args:
        source: YAML テキスト（str または bytes）

    Returns:
        MLNDLTopology インスタンス

    Raises:
        ValueError: サイズ超過 / バージョン不正
        pydantic.ValidationError: スキーマ検証エラー
        yaml.YAMLError: YAML 構文エラー、同じマッピングでのキーの重複
    """
    if isinstance(source, str):
        source = source.encode("utf-8")

    if len(source) > MAX_TOPOLOGY_BYTES:
        raise ValueError(
            f"入力サイズ ({len(source):,} bytes) が上限 "
            f"({MAX_TOPOLOGY_BYTES:,} bytes) を超えています"
        )

    # yaml.safe_load と同じ手順 (yaml.load は使わない)。ローダーだけをキーの重複を見るものにする
    loader = _SafeLoader(source)
    try:
        data = loader.get_single_data()
    finally:
        loader.dispose()
    if data is None:
        data = {}

    return MLNDLTopology.model_validate(data)


def parse_file(path: str) -> MLNDLTopology:
    """ファイルから MLNDLTopology を生成する。

    Args:
        path: YAML ファイルのパス

    Returns:
        MLNDLTopology インスタンス
    """
    with open(path, "rb") as f:
        return parse(f.read())
