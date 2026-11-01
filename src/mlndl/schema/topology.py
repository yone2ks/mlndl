"""MLNDLTopology — ルートモデル"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from .layer1 import L1Layer
from .layer2 import L2Layer
from .layer3 import L3Layer
from .control_plane import ControlPlane, legacy_control_plane_errors


class Meta(BaseModel):
    """トポロジーメタデータ"""

    model_config = ConfigDict(extra="allow")  # 将来フィールドを許容

    name: str | None = None
    network_types: list[str] = []


class MLNDLTopology(BaseModel):
    """MLNDL トポロジーのルートモデル"""

    model_config = ConfigDict(extra="forbid")

    ndl_version: str = "1.0"
    meta: Meta | None = None
    layer1: L1Layer | None = None
    layer2: L2Layer | None = None
    layer3: L3Layer | None = None
    control_plane: ControlPlane | None = None

    @model_validator(mode="before")
    @classmethod
    def check_version(cls, data: object) -> object:
        """ndl_version のメジャーバージョンが 1 であることを確認"""
        if not isinstance(data, dict):
            return data
        ver = str(data.get("ndl_version", "1.0"))
        try:
            major = int(ver.split(".")[0])
        except (ValueError, IndexError):
            raise ValueError(f"ndl_version のフォーマットが不正です: {ver!r}")
        if major != 1:
            raise ValueError(
                f"サポートされていない MLNDL バージョン: {ver!r}。1.x が必要です"
            )
        return data

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_control_plane(cls, data: object) -> object:
        """旧構造 (protocols / layer3.routing_adjacencies) には移動先を示すエラーを返す。読み替えはしない (ADR-0010 D12)"""
        if isinstance(data, dict):
            messages = legacy_control_plane_errors(data)
            if messages:
                raise ValueError("\n".join(messages))
        return data

    def index(self):
        """id の索引 (mlndl.index.IdIndex) を作る。何度も引くときはこれを使い回す"""
        from ..index import IdIndex
        return IdIndex(self)

    def resolve(self, entity_id: str, path: str | None = None):
        """id からエンティティを引く。見つからなければ None (ADR-0015)

        例: topology.resolve("vtep-leaf1-leaf2") → Vtep。
        path ("layer2.vxlan" など) を省略すると全コレクションから探す
        """
        return self.index().get(entity_id, path)
