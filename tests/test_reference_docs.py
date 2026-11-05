"""docs/reference (言語リファレンス) がスキーマから古くなっていないか"""
import inspect
import typing
from pathlib import Path

from pydantic import BaseModel

from mlndl.__main__ import json_schema
from mlndl.schema.topology import MLNDLTopology

REFERENCE = Path(__file__).resolve().parent.parent / "docs" / "reference"


def _models(annotation) -> list[type[BaseModel]]:
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return [annotation]
    return [m for arg in typing.get_args(annotation) for m in _models(arg)]


def _all_models() -> list[type[BaseModel]]:
    seen: list[type[BaseModel]] = []
    stack = [MLNDLTopology]
    while stack:
        model = stack.pop()
        if model in seen:
            continue
        seen.append(model)
        for field in model.model_fields.values():
            stack.extend(_models(field.annotation))
    return seen


def test_schema_json_is_up_to_date():
    # スキーマを変えたら: python -m mlndl schema > docs/reference/schema.json
    assert (REFERENCE / "schema.json").read_text() == json_schema()


def test_every_key_is_documented():
    # スキーマに足したキーは、言語リファレンスのどこかに `key` の形で書く
    text = "\n".join(p.read_text() for p in REFERENCE.glob("*.md"))
    missing = sorted({
        f"{model.__name__}.{field.alias or name}"
        for model in _all_models()
        for name, field in model.model_fields.items()
        if f"`{field.alias or name}`" not in text and f"`{field.alias or name}:" not in text
    })
    assert not missing, f"言語リファレンスに書かれていないキー: {missing}"
