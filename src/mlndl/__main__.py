"""mlndl CLI

使い方:
  python -m mlndl export --format cytoscape topology.yaml > topology.json
  python -m mlndl export --format yaml topology.yaml
  python -m mlndl validate topology.yaml
"""

import argparse
import sys

from .parser import parse_file
from .validator import validate
from .exporter import cytoscape, yaml as yaml_exporter


def cmd_export(args):
    topology = parse_file(args.file)
    if args.format == 'cytoscape':
        print(cytoscape.export_json(topology))
    elif args.format == 'yaml':
        print(yaml_exporter.export(topology))
    else:
        print(f"Unknown format: {args.format}", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args):
    topology = parse_file(args.file)
    errors = validate(topology)
    if errors:
        for e in errors:
            print(f"ERROR  {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("OK — no validation errors")


def main():
    parser = argparse.ArgumentParser(prog='python -m mlndl', description='mlndl CLI')
    sub = parser.add_subparsers(dest='command')

    p_export = sub.add_parser('export', help='トポロジーをエクスポート')
    p_export.add_argument('file', help='YAML ファイルパス')
    p_export.add_argument('--format', choices=['cytoscape', 'yaml'], default='cytoscape')

    p_validate = sub.add_parser('validate', help='バリデーション実行')
    p_validate.add_argument('file', help='YAML ファイルパス')

    args = parser.parse_args()
    if args.command == 'export':
        cmd_export(args)
    elif args.command == 'validate':
        cmd_validate(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
