"""YAML エクスポーター"""

from __future__ import annotations

import yaml

from ..schema.topology import MLNDLTopology


def export(topology: MLNDLTopology) -> str:
    """MLNDLTopology を YAML 文字列にシリアライズする。

    - None フィールドは出力しない
    - by_alias=True で from_ → from に変換
    - 文字コード: UTF-8
    """
    data = topology.model_dump(
        mode="json",
        exclude_none=True,
        by_alias=True,
    )
    return yaml.dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
