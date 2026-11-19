"""mlndl — Multi-Layer Network Description Language

Public API:
    parse(source)        YAML str/bytes → MLNDLTopology
    parse_file(path)     ファイルパス → MLNDLTopology
    validate(topology)       参照整合性チェック → list[ValidationError]（error のみ）
    validate_all(topology)   error / warning / info → ValidationResult
    topology.resolve(id)     id からエンティティを引く (ADR-0015)
    topology.index()         id の索引 (IdIndex)
    LANGUAGE_VERSION         この mlndl が読める最も新しい ndl_version (ADR-0027 D6)
    UnsupportedVersionError  YAML の ndl_version がこの mlndl より新しい (ValueError のサブクラス。ADR-0027 D5)

互換の約束 (どれを 1.x の間変えないか) は ADR-0027。
"""

from .parser import parse, parse_file
from .validator import validate, validate_all, ValidationError, ValidationResult
from .schema.topology import MLNDLTopology
from .index import IdIndex
from .schema.refs import Ref
from .version import LANGUAGE_VERSION, UnsupportedVersionError, __version__

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
    "LANGUAGE_VERSION",
    "UnsupportedVersionError",
]
