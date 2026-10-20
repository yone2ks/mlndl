"""mlndl — Multi-Layer Network Description Language

Public API:
    parse(source)        YAML str/bytes → MLNDLTopology
    parse_file(path)     ファイルパス → MLNDLTopology
    validate(topology)       参照整合性チェック → list[ValidationError]（error のみ）
    validate_all(topology)   error / warning / info → ValidationResult
    topology.resolve(id)     id からエンティティを引く (ADR-0015)
    topology.index()         id の索引 (IdIndex)
"""

from .parser import parse, parse_file
from .validator import validate, validate_all, ValidationError, ValidationResult
from .schema.topology import MLNDLTopology
from .index import IdIndex
from .schema.refs import Ref

__all__ = [
    "parse",
    "parse_file",
    "validate",
    "validate_all",
    "ValidationError",
    "ValidationResult",
    "MLNDLTopology",
    "IdIndex",
    "Ref",
]

__version__ = "0.1.0"
