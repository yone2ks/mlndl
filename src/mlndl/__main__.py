"""mlndl CLI

使い方:
  python -m mlndl export --format cytoscape topology.yaml > topology.json
  python -m mlndl export --format yaml topology.yaml
  python -m mlndl validate topology.yaml
  python -m mlndl validate --strict topology.yaml   # warning も error として扱う
"""

import argparse
import sys

import pydantic
import yaml

from .parser import parse_file
from .validator import validate_all
from .exporter import cytoscape, yaml as yaml_exporter


def _load(path):
    """YAML を読み込む。スキーマ違反はトレースバックではなく ERROR 行で報告して終了する"""
    try:
        return parse_file(path)
    except pydantic.ValidationError as exc:
        for err in exc.errors():
            loc = "".join(f"[{x}]" if isinstance(x, int) else f".{x}" for x in err["loc"]).lstrip(".")
            msg = err["msg"].removeprefix("Value error, ")
            print(f"ERROR    {loc}: {msg}", file=sys.stderr)
        # スキーマを通らないとモデルができず、参照の整合性などの検査まで進めない (round4 E7)
        print("NOTE     上の誤りはスキーマの段階で見つかったものです。直すと参照の整合性などの検査が"
              "続けて実行され、ほかの誤りが見つかることがあります", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as exc:  # YAML の構文の誤り・キーの重複
        print(f"ERROR    {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:  # サイズ上限・バージョン不一致など
        print(f"ERROR    {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_export(args):
    topology = _load(args.file)
    if args.format == 'cytoscape':
        print(cytoscape.export_json(topology))
    elif args.format == 'yaml':
        print(yaml_exporter.export(topology))
    else:
        print(f"Unknown format: {args.format}", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args):
    topology = _load(args.file)
    result = validate_all(topology, strict=args.strict)
    for e in result.errors:
        print(f"ERROR    {e}", file=sys.stderr)
    for w in result.warnings:
        print(f"WARNING  {w}", file=sys.stderr)
    for n in result.notes:
        print(f"INFO     {n}", file=sys.stderr)
    if not result.ok:
        sys.exit(1)
    suffix = f" ({len(result.warnings)} warnings)" if result.warnings else ""
    print(f"OK — no validation errors{suffix}")


def main():
    parser = argparse.ArgumentParser(prog='python -m mlndl', description='mlndl CLI')
    sub = parser.add_subparsers(dest='command')

    p_export = sub.add_parser('export', help='トポロジーをエクスポート')
    p_export.add_argument('file', help='YAML ファイルパス')
    p_export.add_argument('--format', choices=['cytoscape', 'yaml'], default='cytoscape')

    p_validate = sub.add_parser('validate', help='バリデーション実行')
    p_validate.add_argument('file', help='YAML ファイルパス')
    p_validate.add_argument('--strict', action='store_true',
                            help='warning を error に昇格する (ADR-0002 D8)')

    args = parser.parse_args()
    if args.command == 'export':
        cmd_export(args)
    elif args.command == 'validate':
        cmd_validate(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
