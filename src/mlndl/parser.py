"""YAML パーサー

セキュリティ要件 (ADR-0004):
- yaml.safe_load() を使用（yaml.load() 禁止）
- 入力サイズ上限: MAX_TOPOLOGY_BYTES (1MB)
"""

from __future__ import annotations

import yaml

from .constants import MAX_TOPOLOGY_BYTES
from .schema.topology import MLNDLTopology


def parse(source: str | bytes) -> MLNDLTopology:
    """YAML 文字列またはバイト列から MLNDLTopology を生成する。

    Args:
        source: YAML テキスト（str または bytes）

    Returns:
        MLNDLTopology インスタンス

    Raises:
        ValueError: サイズ超過 / バージョン不正
        pydantic.ValidationError: スキーマ検証エラー
        yaml.YAMLError: YAML 構文エラー
    """
    if isinstance(source, str):
        source = source.encode("utf-8")

    if len(source) > MAX_TOPOLOGY_BYTES:
        raise ValueError(
            f"入力サイズ ({len(source):,} bytes) が上限 "
            f"({MAX_TOPOLOGY_BYTES:,} bytes) を超えています"
        )

    data = yaml.safe_load(source)
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
