# ADR-0001: `attaches_to` の使い分け基準

- **Status**: Draft
- **Date**: 2026-05-27
- **Deciders**: mlndl-spec-architect (Pass A)
- **Pass**: A (初回策定)

## Context

MLNDL 原案 (NAIST, 2011) では「論理ノードが物理ノードに帰属する」関係を `attachesTo` と呼んだ。これは MLNDL の三層モデル (L1/L2/L3) において、ある層の要素が別の層の要素を「物理基盤」として参照するための核となる概念である。

現代的再実装にあたっては、論文の `attachesTo` を RFC 8345 が定義する 3 レベルの "supporting" 関係 (supporting-node / supporting-termination-point / supporting-link) と対応づける必要がある。CLAUDE.md ですでに「`attaches_to` に統一」する方針は確定しているが、以下の運用上の論点が未明文化である:

- 値が **文字列** (例: `eve-server`) か **オブジェクト** (例: `{layer: layer1, interface: swp51}`) かをどう判別するか
- pydantic v2 で `str | AttachesTo` Union 型をどのように曖昧さなくデシリアライズするか
- 同一要素に対する **複数 supporting** (multi-homing: 例えば dvSwitch アップリンクが複数ホスト vmnic に同時 attach) を許容するか
- **自己参照** (`node-a` の `attaches_to: node-a` 等) のバリデーション
- 文字列形式とオブジェクト形式の使い分けが本質的か、それとも記述短縮のための糖衣構文に過ぎないのか

論文時点では存在しなかった IF / Link レベルの supporting も含めて、現代版で 3 レベルに拡張するのが本 ADR の責務。

## Decision

**`attaches_to` は supporting 関係の統一フィールドとし、値の形式は「参照先が何であるか」によって決まる。**

形式判別ルール (Pass A 案):

| 値の形式 | 解釈 | RFC 8345 対応 | 使用箇所 |
|---------|------|--------------|----------|
| `<node-id>` (文字列) | **ノード参照** — この要素は当該ノード上で実現される | supporting-node | `layer1.nodes[].attaches_to` |
| `{layer: <layer>, interface: <if-id>}` (オブジェクト) | **インターフェース参照** — この論理 IF は当該物理 IF で実現される | supporting-termination-point | `layer1.interfaces[]`, `layer3.interfaces[]` の `attaches_to` |
| `{layer: <layer>, link: <link-id>}` (オブジェクト) | **リンク参照** — このセッション/トンネルは当該リンク上を流れる | supporting-link | `layer3.routing_adjacencies[].attaches_to` |

### pydantic 型定義 (Pass A)

```python
class AttachesToInterface(BaseModel):
    layer: Literal["layer1", "layer2", "layer3"]
    interface: str  # 参照先 interface ID

class AttachesToLink(BaseModel):
    layer: Literal["layer1", "layer2", "layer3"]
    link: str  # 参照先 link ID

# Discriminated Union: interface フィールドが存在するか link フィールドかで判別
AttachesToObject = Union[AttachesToInterface, AttachesToLink]

# トップレベルの型: 文字列 = ノード参照、オブジェクト = IF/Link 参照
AttachesTo = Union[str, AttachesToObject]
```

### YAML 例

```yaml
# ノードレベル: 文字列
layer1:
  nodes:
    - id: spine1
      attaches_to: eve-server

# IF レベル: オブジェクト
layer3:
  interfaces:
    - id: leaf1-swp51-l3
      attaches_to: {layer: layer1, interface: leaf1-swp51}

# リンクレベル: オブジェクト
layer3:
  routing_adjacencies:
    - id: bgp-adj-spine1-leaf1
      attaches_to: {layer: layer1, link: link-spine1-leaf1}
```

### 運用ルール (Pass A 案)

1. **文字列値の解釈は常にノード参照**: 文字列が現れたら必ず `MLNDLTopology` 内のノード ID を引く。
2. **`interface` と `link` を同一オブジェクトに併記することは不可** (バリデーションエラー)。
3. **multi-homing は Phase 2 で再評価**: Phase 1 (L1 のみ) ではスカラのみ。配列形式は Phase 2 で導入検討。
4. **自己参照は不正**: `node-a.attaches_to == "node-a"` および IF の `attaches_to.interface == 自身の id` はバリデーションエラー。
5. **層方向の制約**: `attaches_to.layer` は同層 (intra-layer) と下位層 (cross-layer) のみ許可。**上位層への attaches は不正**。
6. **デシリアライズ優先順位** (pydantic): 入力が `str` なら無条件にノード参照。`dict` なら `link` キーの有無で `AttachesToLink` を優先判定、なければ `AttachesToInterface`。

## Consequences

**良い影響:**

- 論文の `attachesTo` 概念を 1 フィールドで継承でき、教えやすい
- RFC 8345 の 3 レベル supporting 関係に明示的に対応するため `exporter/rfc8345.py` の実装がストレート
- 文字列糖衣により、最多頻度の「VM がホストに乗る」ケースが 1 行で書ける (記述コスト最小)
- broadcast_domain / blast_radius クエリでは `attaches_to` グラフを辿るだけで物理依存を解決できる

**悪い影響 / トレードオフ:**

- 文字列とオブジェクトが混在することによる学習コストの増加 (dsl-designer 観点で要レビュー)
- pydantic Union 型は厳密モードでデシリアライズ曖昧性が起きうる (実装時に discriminator 指定がやや煩雑)
- multi-homing をスカラのみで表現できないため、dvSwitch のように複数 ESXi にまたがるケースを Phase 2 で再設計する余地が残る
- 同層と異層を 1 フィールドで両立させると、レイヤー違反を防ぐ追加バリデーションが必要

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer1.py` (L1Node, L1Interface), `src/mlndl/schema/layer3.py` (L3Interface, RoutingAdjacency)
- バリデーター: 文字列値ノード ID の存在検証 / オブジェクト値の interface・link ID 存在検証 / 自己参照禁止 / 層方向チェック
- エクスポーター: `exporter/rfc8345.py` (supporting-* への 1:1 マッピング), `exporter/cytoscape.py` (親子関係・破線エッジ)
- サンプル: `tests/fixtures/valid_l1_simple.yaml` に文字列形式サンプルを追加
- 文書: CLAUDE.md セクション 1 に本 ADR への参照リンクを追加

## Alternatives Considered

- **案A** *(採用案)*: 文字列 = ノード参照、オブジェクト = レイヤー横断 (IF/Link) 参照
  - 最頻ケースを短く書ける
  - 論文の `attachesTo` の意味合いを最も直感的に表現

- **案B**: すべてオブジェクト形式に統一 (`attaches_to: {node: eve-server}`)
  - 却下理由: 最頻ケースで毎回 `{node: ...}` を書かされるコスト増大。原案の精神 (短く・直感的) からも乖離。

- **案C**: RFC 8345 に厳密対応して `supporting_node` / `supporting_termination_point` / `supporting_link` の 3 フィールドに分割
  - 却下理由: RFC 8345 のフィールド名が長く、手書き YAML 体験を著しく損なう。エクスポーター内部で 3 種に分解すれば RFC 互換性は保てるため、対外 API では 1 フィールドにまとめる方が DSL 設計として優位。

## Pass A との差分 *(Pass C のみ記載)*

(Pass C で記述)

## References

- 関連 ADR: ADR-0002 (ID 命名規則 — `attaches_to` の値となる ID のフォーマットに依存)
- CLAUDE.md: 「重要な設計決定 1. `attaches_to`」セクション
- 設計プラン: 初期の設計プラン (リポジトリ外。現在は ADR が正) (`attaches_to` 統一フィールド名の節)
- 原案の論文: 手元の場所は CLAUDE.local.md (`attachesTo` 概念)
- 外部資料: RFC 8345 (Section 4.2 Supporting Relationships), RFC 8944, RFC 8346
