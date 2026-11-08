# ADR-0002: ID 命名規則

- **Status**: Accepted
- **Date**: 2026-05-27
- **Deciders**: mlndl-spec-architect (Pass C), mlndl-linguist
- **Pass**: C (再設計後の最終版)
- **Supersedes**: drafts/0002-id-naming-convention.md

## Context

MLNDL の全レイヤー (L1/L2/L3/protocols) は `id` フィールドを介して相互参照する。`attaches_to`、`from`/`to`、`members`、`vrf`、`l3vni` などすべてのクロスレイヤー参照は ID 文字列の解決に依存しており、ID 規則は本仕様の中で最も波及範囲の広い基盤決定である。

Pass A ドラフトは以下の問題を抱えていた:

1. **プレフィックス区切りの不統一**: `vlan100` (区切りなし) と `vrf-tenant-a` (ハイフン) が共存し、「いつ区切るのか」のメンタルモデルが立てられない (linguist / spec-architect / ecosystem-reviewer の共通指摘)
2. **`role` 値との文字セット矛盾**: ADR-0003 で `load_balancer` (アンダースコア付き) が定義される一方、`id` はハイフンのみ許容しており、同一プロジェクト内に 2 系統の文字セット規則が共存していた (ecosystem-reviewer ★最高優先)
3. **`id` と `name` の役割が未明文化**: 「なぜ `peerlink.4094` を id に使えないのか」が利用者に伝わらない (dsl-designer 指摘)
4. **末尾ハイフンを許容してしまう正規表現**: `^[a-z][a-z0-9-]{0,62}$` は `leaf1-` をマッチさせる (dsl-designer 指摘)
5. **アダプター生成 ID の冪等性が未定義** (spec-architect 指摘)
6. **NetBox slug との変換コストが未文書化** (ecosystem-reviewer 指摘)

本 ADR はこれらをゼロから再設計し、ADR-0001〜0004 で共通利用するバリデーション severity 基準も合わせて定義する。

## Decision

### D1. 文字セットと正規表現

ID は次の正規表現を満たさなければならない:

```
^[a-z][a-z0-9]*(-[a-z0-9]+)*$
```

性質:

- 先頭: 英小文字 1 文字 (数値からは始まらない — DNS ラベルと互換)
- 中間: 英小文字・数字・ハイフン
- 末尾: 英小文字または数字 (**末尾ハイフン禁止** — Pass A の正規表現バグを修正)
- **連続ハイフン禁止** (`leaf--1` は不正)
- 最大 63 文字 (DNS ラベル制限を継承)
- **アンダースコア・大文字・ドット・コロン・スペース禁止**

`name` フィールドの文字セットには本規則を適用しない (D4 参照)。

### D2. プレフィックスのセパレータ統一 (`vlan-100` ルール)

すべての ID においてプレフィックスと識別子は **ハイフンで区切る**。例外を設けない。

| 対象 | Pass A (廃止) | Pass C (採用) |
|------|--------------|-------------|
| VLAN | `vlan100` | `vlan-100` |
| L2VNI / L3VNI | `vni10100` | `vni-10100` |
| VRF | `vrf-tenant-a` | 変更なし |
| BGP セッション | `bgp-adj-spine1-leaf1` | `bgp-peer-spine1-leaf1` (`adj` は業界非標準。`peer` は RFC 4271 で確立した語彙) |
| L1 リンク | `link-spine1-leaf1` | 変更なし |
| L1 ノード | `spine1`, `leaf1` | 変更なし (プレフィックスなし。役割は `role` フィールドで表現) |
| L1 IF | `spine1-swp1` | 変更なし (ノード名 + IF 名のハイフン結合) |

メンタルモデル: 「英小文字または数字の塊」を「ハイフン」で連結する。例外なし。

**`bgp-peer-A-B` のノード順序規則**: A/B は `from → to` 方向に揃える (BGP adjacency モデルで `from` が最初に記述するノード)。辞書順ソートを採用する実装も許容するが、同一トポロジーで混在させてはならない。ADR-0001 (routing_adjacencies の `from`/`to` フィールド) と整合させること。

### D3. `id` と `role` 値の文字セットを明示的に分離

`id` と `role` は **異なる文字セット規則** に従う。両 ADR に相互参照を追記する。

| フィールド | 文字セット | 根拠 |
|------------|-----------|------|
| `id` | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` (D1) | クロスレイヤー参照のキー。DNS ラベル互換性が必須 |
| `role` | `^[a-z][a-z0-9_-]*$` (アンダースコア許容) | 識別子ではなくラベル。業界慣用語 (`load_balancer` 等) を尊重 |
| `name` | 任意の UTF-8 文字列 (改行・制御文字を除く) | 人間可読の表示用 (D4 参照) |

**なお、ADR-0003 では `role` 値の正規形を `load-balancer` (ハイフン) として採用することを推奨する**。本 ADR はあくまで「`id` と `role` の文字セットが別ルールであること」のみを規定する。

### D4. `id` と `name` の目的の明文化

| フィールド | 必須性 | 目的 | 性質 | 例 |
|------------|--------|------|------|----|
| `id` | 必須 | 機械可読、クロスレイヤー参照解決のキー | グローバル一意・文字セット制限あり・変更非推奨 | `leaf1-swp51`, `bgp-peer-spine1-leaf1` |
| `name` | 任意 | 人間可読、可視化・レポート・ログ表示 | 一意性不要・UTF-8 自由・変更可能 | `Leaf-1 Uplink to Spine-1`、`スパイン1` |

`peerlink.4094` のような物理名は `name` に書く。`id` には `leaf1-peerlink-4094` のように変換する。これは Kubernetes の `metadata.name` (ID 相当) と表示ラベルの分離に準拠する。`name` が省略された場合、エクスポーターは `id` を表示にフォールバックしてよい。

### D5. グローバル一意性とスコープ規則

- ID は **MLNDL トポロジー全体でグローバル一意**。同一 ID が `layer1.nodes` と `layer2.vlans` に同時に存在することは不正
- バリデーターは全レイヤーの ID を集合化し、重複を検出する
- この一意性が `attaches_to: leaf1-swp51` のような「レイヤー指定なしの参照」を可能にする (ADR-0001 Pass C の `layer` フィールド廃止と相互依存)

### D6. アダプター生成 ID の冪等性ルール

NetBox / neteye からのアダプターは次のルールを守る:

1. **決定的 ID 生成**: 同一ソースデータから同一 ID を生成すること。ランダム接尾辞・タイムスタンプを含めない
2. **ソース ID の保存**: 元システムの主キー (NetBox UUID 等) は `meta.source_refs` (Phase 2) または `name` 拡張に記録する。MLNDL の `id` には含めない
3. **衝突回避戦略**: ソース側で名前衝突がある場合、アダプターは決定的な接尾辞 (`-2`, `-3`…) を **ソート順で** 付与する
4. **slug 正規化** (NetBox → MLNDL):
   - 大文字 → 小文字
   - アンダースコア `_` → ハイフン `-`
   - 連続ハイフンを 1 個に縮約
   - 先頭・末尾のハイフンを除去
   - 63 文字超なら末尾切り詰め後、衝突時は `-N` 接尾辞で解決
5. **変換不能な場合**: 正規化後も D1 の正規表現を満たせない場合 (例: 数字のみの ID) は、アダプターはエラーで停止し利用者に手動マッピングを要求する。**サイレント変換禁止**

### D7. 推奨プレフィックス (規範ではなく規約)

プレフィックスは規約 (conventional) であり、バリデーターは文法 (D1) のみ検証し、プレフィックスから型を推定しない。推奨プレフィックス違反は `warning` を出すが参照解決は通常通り動作する。

| プレフィックス | 対象 | 根拠 |
|---------------|------|------|
| (なし) | L1 ノード (`spine1`, `leaf1`) | ノードは最頻出。短く書けることを優先 |
| `link-` | L1 リンク | Pass A から継続 |
| `vlan-` | L2 VLAN | `vlan-100` ← D2 で統一 |
| `vni-` | L2VNI / L3VNI | `vni-10100` ← D2 で統一。種別は `type` フィールドで |
| `vrf-` | L3 VRF | Pass A から継続 |
| `bgp-peer-` | BGP 隣接関係 | D2 で `bgp-adj-` から変更 |
| `ospf-adj-` | OSPF 隣接関係 | OSPF の "adjacency" は業界標準語彙 |
| `bfd-` | BFD セッション | |
| ~~`mlag-`~~ | ~~MLAG ドメイン（独立エンティティとして将来導入する場合）~~ | [ADR-0023](0023-per-device-lag-and-ethernet-segments.md) で取り下げ (2026-11-08)。MLAG のドメインのエンティティは作らない |
| `lag-` | LAG（`layer1.lag` の全エントリ。機器 1 台の LAG） | 2026-09-17 に `bond-` から変更。構成子名 `lag`（§6 設計決定）と一致し、CLAUDE.md・全 fixture の実態とも一致する。[ADR-0023](0023-per-device-lag-and-ethernet-segments.md) で `type` をなくした |
| `es-` | 複数の機器の脚を束ねる関係 (`layer1.ethernet_segments`) | [ADR-0023](0023-per-device-lag-and-ethernet-segments.md) D2 (2026-11-08 追加)。RFC 7432 の Ethernet Segment の慣用の略 |
| `isis-adj-` | IS-IS 隣接関係 | ADR-0005 D3-1 でスコープ内確定 (Phase 2 以降) |
| `tunnel-` | L3 トンネルインターフェース (GRE/IPIP/IPSec-VTI) | ADR-0005 D3-1 `layer3.tunnel_interfaces` (Phase 2 以降) |
| `subif-` | L2 サブインターフェース (`swp1.100` 等) | ADR-0005 D3-1 `layer2.subinterfaces` (Phase 2 以降) |
| `vtep-` | VXLAN のトンネル端点 (`layer2.vteps`) | drafts/0014 (2026-10-20 追加) |
| `bridge-` | 番号を持たない L2 セグメント (`layer2.bridges`) | ADR-0018 D1 (2026-11-03 追加) |
| `vpc-` | クラウド論理ネットワークの箱 | ADR-0008 D2 / ADR-0009 D1 `parent` の参照先 (Phase 3 以降) |
| `pod-` | オンプレ Clos 増設単位の箱 | 同上。Cisco PoD (Point of Delivery)。**Kubernetes Pod ではない** |
| `tenant-` | テナントの箱 | 同上 |

> **改訂 (2026-09-17)**: LAG の推奨プレフィックスを `bond-` から `lag-` に変更した。
> `port_channels` / `mlag` を `lag` に統合した設計決定（CLAUDE.md §6）の後、CLAUDE.md と全 fixture は
> 一貫して `lag-` を使っており、本表だけが旧来の `bond-` のまま残っていた。`bond-` は Linux / Cumulus の
> 実装語彙であり、mlndl の構成子名 `lag` に合わせる方が内部一貫性が高い。

### D8. バリデーション severity の共通定義 (全 ADR で参照)

本 ADR で ADR-0001〜0004 が共通利用する severity 基準を定義する。他 ADR は本 ADR の D8 を参照する。

| Severity | 意味 | パーサー動作 |
|---------|------|------------|
| `error` | 仕様違反。トポロジーは無効 | 例外を送出 (`ValidationError`) |
| `warning` | 仕様上は合法だが非推奨・規約違反 | `ValidationResult.warnings` に記録。例外は出さない |
| `info` | 注意喚起のみ | `ValidationResult.notes` に記録 |

**`warning` スペルの確定**: `warn` ではなく `warning` (フルスペル) を採用する。ESLint 等の linter 慣用と一致し、Python logging の `WARNING` とも親族関係にある。

`strict` モード (Phase 2 以降で導入予定): `warning` を `error` に昇格させる。Phase 1 では実装しない (warning が出るルールが `attaches_to` 周辺にほぼ限られ、strict の有用性が低いため)。

> **実装状況 (2026-09-17)**: severity 機構と `strict` モードを実装した。
> 本 D8 は「error は例外を送出」としているが、既存 API との互換のため例外は送出せず、次の形にした:
> `validate(topology)` → error のみの list（従来どおり）/ `validate_all(topology, strict=False)` →
> `ValidationResult(errors, warnings, notes)`。CLI は `python -m mlndl validate [--strict]`。

## Consequences

### 影響範囲

- **スキーマ (`schema/topology.py`)**: 共通の `MLNDLId` 型エイリアスを定義し `Field(pattern=..., max_length=63)` を付与
- **スキーマ (全レイヤー)**: `name: str | None = None` を任意フィールドとして追加。制約: 改行・制御文字禁止、最大 255 文字
- **バリデーター (`validator.py`)**: (a) 全レイヤー横断の ID 一意性検査、(b) 推奨プレフィックス照合 (warning)、(c) 全 ID 参照の未定義チェック
- **エクスポーター (`exporter/cytoscape.py`)**: `data.label` に `name ?? id` を使用
- **エクスポーター (`exporter/rfc8345.py`)**: `node-id` / `tp-id` / `link-id` に MLNDL `id` をそのまま使用可能
- **サンプル (`tests/fixtures/`)**: `vlan100` → `vlan-100`、`vni10100` → `vni-10100`、`bgp-adj-*` → `bgp-peer-*` の一括置換
- **文書**: CLAUDE.md の YAML サンプルを全面更新

### 移行コスト

- 既存サンプルへの機械的置換: 中
- NetBox アダプター実装側での D6 正規化ルール実装: 中 (暗黙の責務を明文化しただけで純粋増ではない)
- Phase 1 コードベース: ゼロ (実装着手前)

## Alternatives Considered

### 代替案 A: アンダースコアを `id` でも許容 (NetBox 完全互換)

正規表現を `^[a-z][a-z0-9_-]*[a-z0-9]$` に緩和。

- **却下理由**: 同じ概念に `load_balancer`/`load-balancer` の 2 表記が共存可能になり ID の正規形が定まらない。RFC 1123 / DNS ラベル互換性を失い EVE-NG / Cytoscape との相互運用で問題になりうる。NetBox 変換コストはアダプター側 D6 で吸収する方が正しい関心分離。

### 代替案 B: `vlan100` 形式の維持 (Pass A 現状維持)

VLAN/VNI のみ区切りなしを例外扱い。

- **却下理由**: linguist / spec-architect / ecosystem-reviewer の 3 名が独立に「統一すべき」と指摘。一貫性の価値がタイプ量節約を上回る。Pass A 内部で `bgp-adj-*` はハイフンを使っており、既に自己矛盾していた。

### 代替案 C: `id` フィールド廃止、`name` のみ

- **却下理由**: 「機械可読 ID は安定キー・表示名は変更可能」レイヤー分離が消える。原案の MLNDL も `id` と `name` を分離しており、本パッケージの中核思想に反する。

### 代替案 D: ID にレイヤープレフィックスを必須化 (`l1:spine1` 等)

- **却下理由**: コロンが D1 の文字セットに含まれない。ADR-0001 で廃止した `layer` フィールドが ID 側に再導入されるだけ。グローバル一意の単純さが勝る。

## Pass A との差分

| 観点 | Pass A (廃止) | Pass C (採用) |
|------|--------------|-------------|
| 正規表現 | `^[a-z][a-z0-9-]{0,62}$` (末尾ハイフン許容バグあり) | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` (末尾・連続ハイフン禁止) |
| VLAN / VNI ID | `vlan100`, `vni10100` | `vlan-100`, `vni-10100` |
| BGP セッション | `bgp-adj-*` | `bgp-peer-*` |
| ポートチャネル推奨 | `pc-` (業界前例薄い独自略語) | `bond-` (CLAUDE.md 例・Cumulus 慣習と整合) |
| `id` と `role` の文字セット | 矛盾 (暗黙の共通ルール) | 明示的に分離 (D3) |
| `id` vs `name` の目的 | 未明文化 | D4 で表形式で明文化 |
| アダプター生成 ID 冪等性 | 未定義 | D6 で 5 項目のルールを策定 |
| NetBox slug 変換 | 未定義 | D6.4 で正規化手順を明示 |
| バリデーション severity | 各 ADR でアドホック | D8 で `error / warning / info` を統一定義 |

**独立に同じ結論に到達した点** (Pass B でも妥当と評価):
- 英小文字 + 数字 + ハイフン基本路線
- 63 文字上限 (DNS ラベル根拠)
- 大文字・アンダースコア禁止 (`id` フィールド限定)
- グローバル一意性
- プレフィックスは規範でなく規約

## ADR-0005 との関係

ADR-0005「mlndl の表現スコープ定義」(Pass C, 2026-05-29) により、Phase 2 以降で実装予定の新エンティティが確定した。本 ADR D7 の推奨プレフィックス表に `isis-adj-` / `tunnel-` / `subif-` を追加済み。

**SVI の ID 命名パターン**: ADR-0005 D2-2 ケース B で SVI エンティティの id は `<node>-<vlan-id>` パターン (例: `leaf1-vlan-100`) を使うことが暗黙示されている。これは D1 の正規表現に準拠しており D7 の推奨プレフィックスとは別の命名軸 (node 接頭辞 + entity-id 結合) を使う。Phase 2 着手時にスキーマ実装と合わせて D7 補足として明示する。

**severity 定義の帰属**: 本 ADR D8 が `error / warning / info` の基準を定義しており、ADR-0001/0004 はここを参照する。ADR-0004 の Pass A との差分表に `severity 定義 | ADR-0004 内 | ADR-0005 に分離` という誤記があるが、正しくは「**ADR-0002 (本 ADR) D8 に分離**」である。

## ADR-0009 との関係

ADR-0009「メンバーシップ構成子の直交性」(2026-09-15) により、以下 2 点を本 ADR に追加する。

### 予約語: bare `label` / `tag` の禁止

`labels` を多軸分類の構成子として採用した (ADR-0009 D3) ことに伴い、将来のプロトコル拡張との
衝突を構造的にゼロにするため、**bare `label` / `tag` を mlndl 全体でフィールド名として禁止**する。
整数セマンティクスのプロトコルフィールドには必ず修飾語を付ける:

| 領域 | 禁止 | 採用する名前 |
|------|------|-------------|
| MPLS (Phase 2+) | `label` | `mpls_label` / `label_stack` / `label_action` |
| 802.1Q | `tag` | `vlan_id` (実装済み) |
| Q-in-Q (将来) | `tag` | `stag_vlan_id` / `ctag_vlan_id` |

mlndl は既に 802.1Q を `vlan_id` と命名済みであり、この方針は現状と整合する。

### `labels` のキー命名 (推奨、未強制)

`labels` のキーは本 ADR D1 の ID 正規表現 (`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`) への準拠を**推奨**する。
表記揺れ (`az` / `AZ` / `availability_zone` / `availabilityZone`) を避けるためである。

~~Phase 1 では検証しない~~ → **2026-09-17 実装済み**: 本 ADR D8 の severity 機構の導入に合わせ、
キー構文違反を `warning` として報告する。

なお `labels` の**値**は本 ADR の ID 規則に従う必要がない (`ap-northeast-1a` のようにハイフンを
含む値も可)。値は参照ではなく自由文字列である (ADR-0009 D2)。

### 実装同期メモ: D1 の文法チェック (2026-10-11)

D1 の文法は、長らく validator に実装されていなかった (`labels` のキーにだけ使われていた)。
大文字の ID (`tor-sw1-Eth1`) が素通りしていたことで判明し、次の形で実装した。

- **場所**: 「影響範囲」の `MLNDLId` 型 (スキーマでの `Field(pattern=...)`) ではなく、validator の `error` とした。
  パース時に例外で止めると最初の 1 件しか報告できない。validator なら、ほかの参照エラーと一緒に、パスと違反理由
  (大文字・アンダースコア・使えない文字・末尾 / 連続ハイフン・63 文字超) をまとめて返せる
- **対象**: `layer1` / `layer2` / `layer3` / `protocols` にある、`id` を持つエンティティのリストすべて。
  リストはスキーマから列挙するので、エンティティを追加しても対象から漏れない
- **既存 fixture への影響**: なし (導入時点で全 ID が D1 を満たしていた)
- **全レイヤー横断の ID 一意性検査 (2026-11-06 実装)**: 「影響範囲」の (a)。それまでは `{interface: X}` が解決する ID 空間
  (L1 IF / LAG / VLAN / サブ IF) の間と、L3 IF とトンネル IF の間の重複検査だけが実装済みで (ADR-0012 D5・ADR-0018 D3)、
  同じ一覧の中の重複 (機器を同じ id で 2 つ書くなど) は検査されず、後に書いたほうが参照から黙って見えなくなっていた。
  今は `id` を持つすべての一覧を通して、同じ一覧の中も別の一覧との重複も error にする (`validator._check_id_uniqueness`)

## References

- `CLAUDE.md` — `attaches_to` 参照キーとしての ID の役割、YAML サンプルの現行プレフィックス
- `docs/decisions/evaluations/round1-evaluation.md` — Pass B 指摘 (全 5 エージェント)
- ADR-0005 (Pass C) — Phase 2 以降の新エンティティ確定によりプレフィックス表を拡張 (D7)
- RFC 1123 §2.1 — DNS ラベル制約 (63 文字・英小文字+数字+ハイフン・先頭英字・末尾英数)
- RFC 8345 — `node-id` / `tp-id` / `link-id` のグローバル一意性要求
- Kubernetes `metadata.name` 慣習 — 機械可読 ID と表示名の分離
- NetBox slug 仕様 — `^[-a-zA-Z0-9_]+$` (本 ADR は意図的にサブセットを採用)
- 関連 ADR: ADR-0001 (`attaches_to` の `layer` フィールド廃止と相互依存)、ADR-0003 (`role` 値の文字セット規則)、ADR-0004 (`strict` モードへの severity 参照)
