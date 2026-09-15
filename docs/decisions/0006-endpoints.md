# ADR-0006: L1 物理リンクの端点表現を `endpoints` に統一

- **Status**: Accepted
- **Date**: 2026-06-17
- **Pass**: C（5エージェント並列レビュー後に決定）

## 問題

Layer1 の物理リンク定義に `from`/`to` という有向表現を使っていた。物理ケーブルは無向（どちら側から見ても等価）であるにもかかわらず、`from`/`to` はベクトルを含意する。さらに Python の `from` 予約語回避のため `from_` という不格好なフィールド名が必要だった。

## 決定

L1 `links[].from`/`to` を **`endpoints: [a, b]`**（順序非依存の 2 要素リスト）に変更する。

```yaml
# Before
links:
  - id: link-spine1-leaf1
    from: spine1-swp1
    to: leaf1-swp51

# After
links:
  - id: link-spine1-leaf1
    endpoints: [spine1-swp1, leaf1-swp51]
```

## 根拠

1. **意味論の一致**: 物理イーサネットケーブルは PHY/MAC レベルで対称・無向。配列構文自体が「順序に意味なし＝双方向」を表明する
2. **業界慣習**: NetBox は `termination_a/b`（対称）、Containerlab は `endpoints: [a,b]`（対称）を採用
3. **正規化の改善**: `from: A, to: B` と `from: B, to: A` が同一リンクの別表記になる正規化問題が解消される
4. **`lag.members` との一貫性**: LAG メンバーも順序非依存のリスト。同じメタファーを使う
5. **Python 実装の改善**: `from_` エイリアスが不要になる
6. **今がベストタイミング**: Phase 1 実装初期。fixture 数も少なくマイグレーションコストが最小

## 影響範囲と実装

- `schema/layer1.py`: `L1Link.from_`/`to` → `endpoints: list[str]`（pydantic `min_length=max_length=2`）。self-loop 防止バリデーターを追加
- `validator.py`: `link.from_`/`link.to` → `link.endpoints[0]`/`link.endpoints[1]`
- `exporter/cytoscape.py`: `endpoints[0]→source, endpoints[1]→target`（Cytoscape.js は `source`/`target` 必須のため、有向性はエクスポーター側に封じ込める）
- 全 fixture YAML: `from:`/`to:` → `endpoints:` に書き換え済み

## L3 との非対称性について

`layer3.routing_adjacencies` の `from`/`to` は**維持**する。BGP セッションは `update_source` に主体ノードを持ち論理的に方向がある。L1 だけ無向化することはレイヤー意味論の差を正しく反映しており矛盾ではない。

## RFC 8345 との関係

RFC 8345 の `ietf-network-topology` は `source`/`destination` の有向モデルを採用し、無向リンクを 2 本の有向リンクで表現する。mlndl は RFC 8345 の一段上に位置する抽象レイヤーであり、エクスポーター（`rfc8345.py`）が `endpoints` → `source`/`destination` へ変換する責務を持つ。
