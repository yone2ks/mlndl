"""mlndl — Multi-Layer Network Description Language

Public API:
    parse(source)        YAML str/bytes → MLNDLTopology
    parse_file(path)     ファイルパス → MLNDLTopology
    validate(topology)   参照整合性チェック → list[ValidationError]
"""

from .parser import parse, parse_file
from .validator import validate, ValidationError
from .schema.topology import MLNDLTopology

__all__ = [
    "parse",
    "parse_file",
    "validate",
    "ValidationError",
    "MLNDLTopology",
]

__version__ = "0.1.0"
