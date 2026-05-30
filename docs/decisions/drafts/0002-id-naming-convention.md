# ADR-0002: ID 命名規則

- **Status**: Draft
- **Date**: 2026-05-27
- **Deciders**: mlndl-spec-architect (Pass A)
- **Pass**: A (初回策定)

## Context

MLNDL YAML 内のあらゆる要素 (ノード / IF / リンク / VLAN / VRF / VxLAN / BGP セッション 等) は `id:` フィールドで識別される。CLAUDE.md と設計プランのサンプルでは慣習的にいくつかのパターンが使われているが、明文化された命名規則がない。

サンプルから抽出される現状パターン:

| エンティティ | 慣習パターン | 例 |
|------------|------------|----|
| ノード | 短い英数字小文字 | `spine1`, `leaf1`, `eve-server` |
| インターフェース | `<node>-<intf>` | `spine1-swp1`, `leaf1-swp51` |
| リンク | `link-<a>-<b>` | `link-spine1-leaf1`, `link-mlag-peerlink` |
| VLAN | `vlan<id>` | `vlan100` |
| VRF | `vrf-<name>` | `vrf-default`, `vrf-tenant-a` |
| VxLAN | `vni<id>` | `vni10100`, `vni10900` |
| BGP セッション | `bgp-adj-<a>-<b>` / `bgp-<role>` | `bgp-adj-spine1-leaf1`, `bgp-underlay` |
| Port Channel | `<node>-<name>` | `leaf1-bond0` |
| MLAG | `mlag-<name>` | `mlag-leaf-pair` |

論点:

1. セパレータ統一 (`-` vs `_` vs `.` vs `:`)
2. ID の **スコープ**: グローバル一意か、エンティティ種別内でのみ一意か
3. 使用可能文字 (正規表現) と長さ上限
4. プレフィックス規則の有無 (`link-`, `vni`, `vlan`, `vrf-` 等を必須化するか)
5. 手書き ID と、アダプター (NetBox / neteye) からの自動生成 ID の整合

## Decision

**Pass A 案: 緩いグローバル一意 + 慣習的プレフィックス推奨 (必須化はしない)。**

### 規則

1. **文字セット**: 英小文字・数字・ハイフン (`-`) のみ許可。正規表現 `^[a-z][a-z0-9-]{0,62}$` (先頭は英字、最大 63 文字)。
   - アンダースコア (`_`) は **不採用** — シェル/CLI と相性が悪く、YAML ファイル名としても扱いづらい。
   - ドット (`.`) は **不採用** — インターフェース名 (`peerlink.4094` 等) との混同を避ける。これらは `name:` フィールドに入れ、`id:` は別の値にする。
   - コロン (`:`) は **不採用** — Route Target (`65001:100`) の値部に使うため衝突を避ける。

2. **スコープ**: **グローバル一意** (`MLNDLTopology` 全体で唯一)。
   - `attaches_to` (ADR-0001) で文字列値をノード ID として解決する以上、ID をグローバル一意にしておくと曖昧さがなくなる。

3. **長さ**: 最大 63 文字 (DNS ラベル制限と揃え、Cytoscape.js / EVE-NG 双方で安全)。

4. **プレフィックス規則 (推奨パターン、必須ではない)**:

| エンティティ | 推奨パターン | 必須/推奨 |
|------------|------------|----------|
| `layer1.nodes[].id` | 自由 (例: `spine1`, `eve-server`) | 自由 |
| `layer1.interfaces[].id` | `<node-id>-<intf-name>` (例: `spine1-swp1`) | 推奨 |
| `layer1.links[].id` | `link-<from>-<to>` または `link-<purpose>` | 推奨 (`link-` プレフィックス) |
| `layer1.port_channels[].id` | `<node-id>-<lag-name>` (例: `leaf1-bond0`) | 推奨 |
| `layer1.mlag[].id` | `mlag-<name>` | 推奨 (`mlag-` プレフィックス) |
| `layer2.vlans[].id` | `vlan<vlan-id>` (例: `vlan100`) | 推奨 |
| `layer2.vxlan[].id` | `vni<vni>` (例: `vni10100`) | 推奨 |
| `layer3.vrfs[].id` | `vrf-<name>` (例: `vrf-tenant-a`) | 推奨 (`vrf-` プレフィックス) |
| `layer3.interfaces[].id` | `<node>-<intf>-l3` (例: `leaf1-swp51-l3`) | 自由 |
| `layer3.routing_adjacencies[].id` | `<proto>-adj-<a>-<b>` | 推奨 |
| `protocols.bgp[].id` / `ospf[].id` / `bfd[].id` | `<proto>-<role>` (例: `bgp-underlay`) | 推奨 |

推奨パターンは linter で warning を出すが、エラーにはしない。

5. **手書き vs 自動生成**:
   - 手書き: 上記推奨に従う。
   - アダプター生成 (NetBox / neteye): 推奨パターンを必ず適用。NetBox の `slug` フィールドを活用し、衝突時はサフィックス (`-2`, `-3`) で回避。

### YAML 例 (Pass A 規則準拠)

```yaml
layer1:
  nodes:
    - id: spine1                 # 自由
    - id: eve-server             # 自由 (ハイフン OK)
  interfaces:
    - id: spine1-swp1            # <node>-<intf> パターン
      node: spine1
      name: swp1                 # 表示名は name: に
  links:
    - id: link-spine1-leaf1      # link- プレフィックス
      from: spine1-swp1
      to: leaf1-swp51

layer3:
  vrfs:
    - id: vrf-tenant-a           # vrf- プレフィックス
      rd: "65001:100"            # RT 値はコロン許容 (id: とは別フィールド)
```

## Consequences

**良い影響:**

- ハイフンのみのシンプルな文字セットで、YAML / シェル / URL / DNS どこでも安全に扱える
- プレフィックスを推奨することで、サンプルファイルが自己説明的になる (`link-` を見れば即リンクと分かる)
- グローバル一意により `attaches_to` の文字列値解決が単純化 (ADR-0001 と整合)
- DNS ラベル長制限 63 文字は EVE-NG / Cytoscape ID として安全マージン

**悪い影響 / トレードオフ:**

- アンダースコア・ドットを禁止することで、既存の慣習名 (`peerlink.4094` 等) を ID 化するとき書き換えが必要 (`id` と `name` を分けているため名前は維持できる)
- プレフィックス必須化を見送ったため、サンプル間で書き方がブレる懸念 (linter warning で誘導)
- `vlan100` (区切りなし) と `vrf-tenant-a` (ハイフン区切り) でプレフィックスの一貫性が揺れている点は Pass B / C で再考の余地あり

**影響を受けるコンポーネント:**

- スキーマ: 全モデルの `id: str` フィールドに `Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")` を追加
- バリデーター: グローバル ID 一意性チェック (`validator.py`)
- エクスポーター: `exporter/rfc8345.py` / `exporter/cytoscape.py` はそのまま使える
- サンプル: 既存サンプルは規則準拠 (見直しの必要なし)

## Alternatives Considered

- **案A** *(採用案)*: 緩いグローバル一意 + 慣習的プレフィックス推奨
  - 現状サンプルとの後方互換性が高く、利用者の自由度を保ちつつ推奨で揃える

- **案B**: エンティティ種別プレフィックスを撤廃し純粋なユーザー定義名にする (例: `vlan100` ではなく `production`)
  - 却下理由: `attaches_to: production` のような記述で「production が何か」が ID だけでは判別不能。デバッグ時の grep でも種別を絞れない。

- **案C**: `<layer>/<type>/<name>` の階層パス形式 (例: `l1/node/spine1`, `l2/vlan/100`)
  - 却下理由: 毎回のキー記述が長くなる。`attaches_to: l1/node/eve-server` は冗長。原案の精神 (簡潔な記述) と乖離。

- **案D**: グローバル一意ではなくエンティティ種別内のみ一意
  - 却下理由: `attaches_to` 解決時にどの名前空間を引くか曖昧になる。スコープ修飾子が必要になり案 C と同様の冗長化を招く。

## Pass A との差分 *(Pass C のみ記載)*

(Pass C で記述)

## References

- 関連 ADR: ADR-0001 (`attaches_to` の値となる ID フォーマット)
- CLAUDE.md: NDL YAML フォーマット概要 (サンプル)
- 設計プラン: 初期の設計プラン (リポジトリ外。現在は ADR が正)
- 外部資料: RFC 1035 (DNS ラベル長制限), RFC 8345 (node-id は string でよい)
