# mlndl

マルチレイヤのネットワーク記述言語 **MLNDL** (Multi-Layer Network Description Language) の Python 実装です。
物理 (L1)・L2・L3・制御プレーンのトポロジーを 1 つの YAML に書き、層どうしのつながり (どの論理 IF がどの物理ポートの上にあるか等) を id の参照で表します。
MLNDL 原案 (NAIST, 2011) を、RFC 8345 の supporting 関係を下敷きに pydantic v2 で再実装したものです。

mlndl はスキーマ・パーサー・バリデーター・エクスポーターだけを持つ中間フォーマットのライブラリで、可視化やデプロイのツールは知りません。

```
neteye / NetBox / 手書き YAML  →  mlndl  →  ndl-viz (可視化) / eve-lab-builder (EVE-NG へのデプロイ)
```

## 使い方

Python 3.11 以上が必要です。

```bash
pip install -e ".[dev]"
```

```bash
python -m mlndl validate examples/wan-sites.yaml
```

```bash
python -m mlndl export --format cytoscape examples/wan-sites.yaml
```

- `validate` は error を出し、warning / info も表示します。`--strict` で warning を error として扱います
- `export` は ndl-viz 向けの Cytoscape.js JSON (`--format cytoscape`) か、正規化した YAML (`--format yaml`) を出します

Python からは次のように使います。

```python
from mlndl.parser import parse_file
from mlndl.validator import validate_all

topology = parse_file("examples/wan-sites.yaml")
result = validate_all(topology)
```

## YAML の例

```yaml
ndl_version: "1.0"
layer1:
  nodes:
    - {id: spine1, role: spine, implementation: vm}
    - {id: leaf1, role: leaf, implementation: vm}
  interfaces:
    - {id: spine1-swp1, node: spine1, name: swp1}
    - {id: leaf1-swp51, node: leaf1, name: swp51}
  links:
    - {id: link-spine1-leaf1, endpoints: [spine1-swp1, leaf1-swp51], mtu: 9216}
layer3:
  interfaces:
    - {id: spine1-swp1-l3, node: spine1, name: swp1, ip: 10.1.0.0/31, attaches_to: {interface: spine1-swp1}}
    - {id: leaf1-swp51-l3, node: leaf1, name: swp51, ip: 10.1.0.1/31, attaches_to: {interface: leaf1-swp51}}
```

もっと大きな例は `examples/` (EVPN の Spine-Leaf、マルチサイトの WAN など) にあります。

## ドキュメント

- `docs/decisions/` — 言語の設計決定 (ADR) とその評価の記録。フィールドの意味と、なぜそう決めたかはここが正です
- `docs/exporter-cytoscape.md` — Cytoscape.js 出力の形
- `docs/role-vocabulary.md` / `docs/label-vocabulary.md` — `role` と `labels` の推奨語彙
- `CLAUDE.md` — 確定した設計の要約と、検査項目の一覧

## テスト

```bash
python -m pytest
```

## ライセンス

MIT License (`LICENSE`)
