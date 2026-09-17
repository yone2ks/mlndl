"""mlndl — Multi-Layer Network Description Language

Public API:
    parse(source)        YAML str/bytes → MLNDLTopology
    parse_file(path)     ファイルパス → MLNDLTopology
    validate(topology)       参照整合性チェック → list[ValidationError]（error のみ）
    validate_all(topology)   error / warning / info → ValidationResult
"""

from .parser import parse, parse_file
from .validator import validate, validate_all, ValidationError, ValidationResult
from .schema.topology import MLNDLTopology

__all__ = [
    "parse",
    "parse_file",
    "validate",
    "validate_all",
    "ValidationError",
    "ValidationResult",
    "MLNDLTopology",
]

__version__ = "0.1.0"
