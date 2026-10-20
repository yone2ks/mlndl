"""id の索引 (ADR-0015)

トポロジーの中で id を持つエンティティを、YAML の構造どおりのパス (例 "layer2.vlans") ごとに引けるようにする。
validator の参照検査と、利用者向けの MLNDLTopology.resolve() が使う。

    index = topology.index()
    index.get("vtep-leaf1-leaf2")            # → Vtep
    index.get("vni-10100", "layer2.vxlan")   # パスを指定して引く
    index.ids("layer1.nodes")                # → {"spine1", "leaf1", ...}
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# id を持つエンティティのリストを探すセクション。リストはスキーマから列挙するので、
# エンティティを足しても索引から漏れない
SECTIONS = ("layer1", "layer2", "layer3", "protocols")


class IdIndex:
    """パス → {id: エンティティ} の索引。作った時点のトポロジーを写す (後の変更は反映しない)"""

    def __init__(self, topology: Any) -> None:
        self._by_path: dict[str, dict[str, BaseModel]] = {}
        for section_name in SECTIONS:
            section = getattr(topology, section_name, None)
            if section is None:
                continue
            for list_name in type(section).model_fields:
                items = getattr(section, list_name)
                if not isinstance(items, list):
                    continue
                entities = {}
                for item in items:
                    entity_id = getattr(item, "id", None)
                    if isinstance(entity_id, str):
                        entities.setdefault(entity_id, item)   # 同じリストに重複があれば先のもの
                if entities:
                    self._by_path[f"{section_name}.{list_name}"] = entities

    def paths(self) -> list[str]:
        """id を持つエンティティがあるパスの一覧"""
        return list(self._by_path)

    def ids(self, path: str, where: tuple[str, str] | None = None) -> set[str]:
        """path にある id の集合。where=(フィールド名, 値) なら、その値を持つものだけ"""
        entities = self._by_path.get(path, {})
        if where is None:
            return set(entities)
        field, value = where
        return {i for i, e in entities.items() if getattr(e, field, None) == value}

    def paths_of(self, entity_id: str) -> list[str]:
        """entity_id があるパスの一覧 (ID はグローバルに一意なので、ふつうは 0 か 1 つ)"""
        return [p for p, entities in self._by_path.items() if entity_id in entities]

    def get(self, entity_id: str, path: str | None = None) -> BaseModel | None:
        """id からエンティティを引く。見つからなければ None

        path を省略すると全パスから探す。複数のパスで見つかった場合は (ID の重複。ADR-0002 D5 違反)
        どれを返すか決められないので LookupError を出す。そのときは path を指定する
        """
        if path is not None:
            return self._by_path.get(path, {}).get(entity_id)
        found = self.paths_of(entity_id)
        if len(found) > 1:
            raise LookupError(
                f"id '{entity_id}' が複数のコレクション ({', '.join(found)}) にあります。path を指定してください"
            )
        return self._by_path[found[0]][entity_id] if found else None
