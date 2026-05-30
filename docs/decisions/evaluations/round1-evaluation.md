# ラウンド1 横断評価メモ (Pass B)

- **Date**: 2026-05-27
- **Evaluators**: mlndl-spec-architect (反論者モード), mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, ecosystem-reviewer (後追い追記)
- **対象ドラフト**: ADR-0001〜0004 (docs/decisions/drafts/)

---

## 評価の目的

Pass A の4つのドラフトを横断的に critique し、以下を浮き彫りにする:

1. **アンカー検出**: どの決定が CLAUDE.md / 設計プランに過度に縛られているか
2. **白紙再設計シミュレーション**: ゼロから設計したら同じ結論になるか
3. **横断矛盾の検出**: ADR 間の前提が食い違っていないか
4. **見落とした論点**: Pass A の「未確定の論点」リストに漏れがないか
5. **「結論ありき」感の有無**: 後付けに見える箇所の指摘

---

## 1. mlndl-spec-architect 評価 (反論者モード)

### アンカー強度の評価

| ADR | アンカー強度 | 主要アンカー元 |
|-----|------------|--------------|
| 0001 attaches_to | **高** | CLAUDE.md「attaches_to に統一」という既成事実 |
| 0002 ID 命名 | **中** | 設計プランのサンプル記法 (spine1, leaf1 等) |
| 0003 role 語彙 | **中** | CLAUDE.md の role 語彙まとめ表 |
| 0004 imp×role | **低〜中** | CLAUDE.md の `implementation: vm/physical/container` 3値固定 |

### ADR-0001: attaches_to

**指摘**:
- `{layer: layer1, interface: leaf1-swp51}` のオブジェクト形式で `layer` フィールドを書く必要があるか? ADR-0002 でグローバル一意 ID が決まっているなら `{interface: leaf1-swp51}` で十分なはず。`layer` フィールドは **ADR-0002 との隠れた矛盾**。
- 同一層内 `attaches_to`（例: vswitch が同一 L1 ノードに attach）のユースケースがドラフトに記載されていない。許容の根拠が不明。
- 「自己参照は不正」だが、ループ検出ロジックの実装コストが記載されていない。
- 代替案C (RFC 8345 の 3 フィールド分割) の却下理由「記述が長くなる」は DSL 設計として正当だが、実際の記述長比較をドラフトが示していない。

**白紙再設計シミュレーション**:  
ID がグローバル一意なら `attaches_to` の値は `{interface: <id>}` か `{link: <id>}` で足り、`layer` は冗長。`layer` を残す理由は「同 ID が別レイヤーに存在する可能性」だが、それは ADR-0002 のグローバル一意性と矛盾する。→ **`layer` フィールドの必要性を Pass C で再検討。**

### ADR-0002: ID 命名規則

**指摘**:
- `load_balancer` (アンダースコア) が role に含まれるのに、ID 規則はハイフンのみ。**ADR-0003/0004 との整合性の問題**。
- `vlan100` (数字直結、区切りなし) と `vrf-tenant-a` (ハイフン区切り) のプレフィックス一貫性の欠如。「後で再考の余地あり」と書いているが Pass B での指摘なのに修正先送りは Pass C で必須再設計。
- アダプター (NetBox) からの自動生成 ID の冪等性がドラフトに記述されていない。同一トポロジーを2回インポートしたとき同一 ID が生成されるか?

**白紙再設計シミュレーション**:  
`vlan100` を `vlan-100` に統一するだけでプレフィックス一貫性が解決する。VLAN ID は数字なので `vlan-100` でも意味は明確。→ **プレフィックスのセパレータ統一が Pass C の中心課題。**

### ADR-0003: role 語彙

**指摘**:
- `host` 削除理由「hypervisor がホストマシンを表すから host は不要」— だが `hypervisor` は実行環境の種類であり、`host` はネットワーク上の「エンドノード」の意味。意味的次元が異なる。削除根拠が弱い。
- `vswitch` / `dvswitch` が L1 ロールとして存在するのは妥当か? vSwitch はハイパーバイザのソフトウェア機能であり、物理トポロジー (L1) の概念ではない。**「mlndl は EVE-NG を知らない」原則と矛盾**。
- `hypervisor` ロールの記述で「EVE-NG にデプロイしない」という表現が出てくる。mlndl は EVE-NG を知らないはずなのに、この記述は上位ツール (eve-lab-builder) の関心事を mlndl スキーマに持ち込んでいる。
- `Literal | str` ハイブリッドの「未知 role は warning を出す」ロジックが pydantic の `field_validator` で実装可能か検証されていない。

### ADR-0004: implementation × role マトリクス

**指摘**:
- マトリクスの目的が「利用者への制約」か「バリデーターの実装指針」か曖昧。`mlndl は EVE-NG を知らない` 原則のもとで、なぜ mlndl がデプロイ上の妥当性を判定するのか?
- `core × container = ❌` の根拠「DC バックボーンはコンテナで実装しない」は現在 (SONiC-VS / SR Linux コンテナが普及) では時代遅れかもしれない。
- `allow_unusual_combination: true` はドメインモデルにバリデーション制御フラグを持ち込む設計であり、DSL の関心分離原則に反する可能性。

### 横断矛盾の整理

| 矛盾 | 関連 ADR | 内容 |
|------|---------|------|
| `layer` フィールドの冗長性 | 0001 ↔ 0002 | グローバル一意 ID なら `layer` は不要なはず |
| アンダースコア vs ハイフン | 0002 ↔ 0003 | `load_balancer` という role 名はアンダースコアだが ID 規則はハイフンのみ |
| vswitch/dvswitch の L1 適合性 | 0003 ↔ 0004 | vSwitch は L1 の物理概念か？ → 全マトリクスが崩れる可能性 |
| EVE-NG 知識の混入 | 0003, 0004 | "EVE-NG にデプロイしない" という記述が mlndl に含まれている |

### Pass C 優先度 (spec-architect)

1. **ADR-0004** — マトリクス設計思想の再検討 (`mlndl は EVE-NG を知らない` 原則との整合)
2. **ADR-0001** — `layer` フィールドの再評価 (ADR-0002 グローバル一意性との整合)
3. **ADR-0002** — プレフィックスセパレータの統一
4. **ADR-0003** — `vswitch/dvswitch` の L1 適合性の再確認

---

## 2. mlndl-linguist 評価

### ADR-0001: attaches_to

**指摘**:
- `attaches_to` は3人称単数動詞形 (`attaches`) で、YAML フィールド名としては珍しい。一般的な YAML は名詞形 (`attachment`, `parent`, `host`) または過去分詞形 (`attached_to`) を使う。
- 同一フィールドが「ノード参照 (文字列)」と「IF/リンク参照 (オブジェクト)」の2つの意味を持つのは **内在的な多義性**。フィールド名だけではどちらの意味かわからない。

**代替候補**: `parent` (Kubernetes Pod-owner 慣行), `runs_on` (ノード限定なら), `bound_to` (より中立的)

### ADR-0002: ID 命名規則

**最重要指摘**: `vlan100` (区切りなし) vs `vrf-tenant-a` (ハイフン区切り) のプレフィックス不統一

- 推奨: `vlan-100` に統一。ハイフン規則はこのプロジェクト全体で一貫させるべき。
- `vni10100` → `vni-10100`、`bgp-adj-xxx` → `bgp-peer-xxx` も合わせて再考。

**`bgp-adj` について**:
- `adj` は BGP 用語では "adjacency" の略だが、業界標準的ではない。
- BGP 業界では `peer` / `session` / `neighbor` が一般的。→ `bgp-peer-spine1-leaf1` の方が明確。

### ADR-0003: role 語彙

**指摘**:
- `dvswitch`: VMware の登録商標 "Distributed vSwitch" の略称。ベンダー固有名詞を仕様に含めることへの懸念。→ `vswitch` 1種類にして `scope: distributed` フィールドで表現する代替案を提示。
- `load_balancer`: role リスト唯一の複合語 (アンダースコア付き)。`firewall` は1語。→ `loadbalancer` (1語) に統一する選択肢。
- `tor`: Top-of-Rack の業界略語。ただし `leaf` との意味的重複が大きく、使い分け基準が明文化されていない。

### ADR-0004: implementation × role マトリクス

**指摘** (linguist 範囲外だが補足):
- `allow_unusual_combination` はフィールド名が長い。`allow_override: true` や `force: true` の方が短く明快。

### Pass C 優先度 (linguist)

1. **ADR-0002** — ID プレフィックスのセパレータ統一 (`vlan100` → `vlan-100`)
2. **ADR-0002** — `bgp-adj` → `bgp-peer` 改名
3. **ADR-0001** — `attaches_to` の多義性をドキュメントで明示するか、フィールドを分割するか

---

## 3. mlndl-dsl-designer 評価

### ADR-0001: attaches_to

**指摘**:
- `str | AttachesToInterface | AttachesToLink` の Union 型は **形状ベースの判別 (shape-based discriminator)** であり、タグベースではない。pydantic v2 では `model_validator` で明示的に分岐させるか、`Annotated` + `discriminator` を使わないと実行時エラーが出る可能性。
- Kubernetes は同じ問題を「1フィールドに Union を詰め込まず、別フィールドに分ける」で解決 (例: `volumeMount.name` と `volumeMount.mountPath` を分離)。
- MLNDL も `node_ref: str` (ノード参照) と `if_ref: {layer, interface}` を別フィールドにする設計も検討すべき。

### ADR-0002: ID 命名規則

**指摘**:
- `id` フィールド (機械可読, 参照解決用) と `name` フィールド (人間可読, 表示用) の目的の違いが**ドラフトに明文化されていない**。これが欠如すると「なぜ `peerlink.4094` を id に使えないのか?」という利用者の疑問に答えられない。
- 正規表現 `^[a-z][a-z0-9-]{0,62}$` はハイフンで終わる ID (例: `leaf1-`) を許容してしまう。末尾ハイフン禁止の修正: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`。

### ADR-0003: role 語彙

**指摘**:
- `Literal["spine","leaf",...] | str` は Python の静的型チェッカー (mypy / pyright) では実質 `str` と同等に扱われる。IDE 補完は機能するが、**型の恩恵が宣言の見た目ほど大きくない**。
- より有効な設計: `role` フィールドのデフォルト値は `Literal[...]` で IDE 補完を提供し、任意の `str` も受け入れるが、バリデーターで **`role` が Literal 外の値なら warning を出す** (既にドラフトに含まれているが、型定義の見せ方の工夫が必要)。

### ADR-0004: implementation × role マトリクス

**指摘**:
- `allow_unusual_combination: bool = False` をドメインモデル (`L1Node`) に追加するのは **関心分離の観点で問題**。これはバリデーション制御フラグであり、スキーマオブジェクトに属するものではない。
  - 代替案A: バリデーション設定は topology レベルの `validation:` セクションにまとめる
  - 代替案B: モデルから分離した `ValidationProfile` に持たせる
  - 代替案C: pydantic の `model_config` で制御する
- `context={"strict": True}` の end-to-end パス (エラーがどこで raise され、どう伝播するか) がドラフトに設計されていない。実装で詰まる可能性。

### 横断課題: バリデーション severity の不統一

ADR-0001〜0004 を通じて「warning」「error」の使い分け基準が統一されていない:
- ADR-0002: 推奨プレフィックス違反 → warning
- ADR-0003: 未知 role → warning
- ADR-0004: ⚠ cell → warning、❌ cell → strict mode で error

これら 3 ADR にわたる severity 基準を **Pass C では共通化**すべき。

### Pass C 優先度 (dsl-designer)

1. **ADR-0001** — Union 型の型安全性問題 (shape-based discriminator → tagged discriminator へ)
2. **ADR-0004** — `allow_unusual_combination` の関心分離問題
3. **全 ADR** — バリデーション severity レベルの統一基準を策定

---

## 4. network-tech-reviewer 評価

### ADR-0003: role 語彙

**指摘**:

1. **`tor` と `leaf` の重複**  
   Top-of-Rack (ToR) はラック上部に設置されるアクセスレイヤスイッチであり、Three-Tier アーキテクチャでは Clos の `leaf` と意味が重複する。  
   - 使い分けが必要なケース: Three-Tier (Core-Distribution-Access) ではアクセス層スイッチを `tor` と呼ぶが、Clos 構成では同じ物理スイッチを `leaf` と呼ぶ。
   - 1つのデバイスが「ToR でもあり leaf でもある」状況は発生しうる。
   - **提言**: `tor` は削除するか、「Three-Tier アクセス層限定」として明示的に定義する。

2. **`mgmt` ロールの欠落**  
   OOB (Out-of-Band) 管理スイッチは DC の標準コンポーネントだが、Phase 1 の語彙に含まれていない。  
   - `role: mgmt` がないと `management` VLAN / OOB スイッチをどう表現するか不明。
   - **提言**: Phase 1 に `mgmt` を追加するか、明示的に「Phase 2 以降」とドキュメント化。

3. **`load_balancer` の Phase 1 必要性**  
   L1 スキーマのみの Phase 1 では、LB の実際の設定 (VIP、ヘルスチェック、アルゴリズム) は不要。`role: load_balancer` ラベルだけであれば問題ないが、意図が明確か確認が必要。
   - Phase 1 ではすべての role が L1 のラベルとしてのみ機能することを明記すべき。

### ADR-0004: implementation × role マトリクス

**指摘**:

1. **`core × container = ❌` は過剰制約**  
   SONiC Virtual Switch (SONiC-VS) や Nokia SR Linux のコンテナイメージは、Containerlab でコアスイッチ相当として使用される実例がある。  
   - `core × container = ❌` → `⚠` に緩和すべき。  
   - 「DC バックボーン」という説明は Production 環境前提だが、ラボ・テスト環境では普通にある構成。

2. **`spine/leaf × container = ⚠` の緩和**  
   Containerlab の普及により、`spine/leaf/tor × container` は実質 ✅ のレベル。`⚠` は過剰かもしれない。  
   - 少なくともコメントで「Containerlab での使用は一般的」と記載すべき。

3. **`border` の定義曖昧性**  
   `border` は文脈により意味が変わる:  
   - DC 境界ルーター (Data Center Edge)
   - Enterprise の WAN 接続ルーター
   - Multi-DC 間の BGP ピアリングポイント  
   - `border × vm = ✅` の根拠が不明確。

4. **`hypervisor × vm = ⚠` は適切か**  
   ネステッド仮想化は Oracle Cloud / AWS Bare Metal で現実に使われるが、 `nested-esxi` のようなユースケースは非常に特殊。`⚠` よりも **「エスケープハッチ必須」の ❌*** に近い扱いが技術的には適切かもしれない。

### Pass C 優先度 (network-tech-reviewer)

1. **ADR-0003** — `tor` の扱い (削除 or 明確な定義)
2. **ADR-0004** — `core × container` を ❌ → ⚠ に修正、`spine/leaf × container` の注釈追加
3. **ADR-0003** — `border` ロールの定義明確化

---

## 5. ecosystem-reviewer 評価

### ADR-0001: attaches_to

**既存ツール比較**:
| ツール | 対応概念 | 整合度 | 備考 |
|--------|---------|--------|------|
| NetBox | Cable + Interface.connected_endpoints。Device の `parent_device` / `virtual_chassis` が VM→物理の hosting 関係 | 中 | "supporting" を単一フィールドで表現しない |
| Containerlab | `links:` 配列に `{endpoints: ["node1:eth0","node2:eth1"]}`。クロスレイヤー参照は設計思想外 | 低 | 同一層のリンクのみ表現 |
| RFC 8345 | `supporting-node` / `-termination-point` / `-link` の 3 フィールド | 高 | MLNDL は RFC 8345 を 1 フィールドに圧縮 |

**良い乖離**: 1 フィールド圧縮・文字列糖衣・クロスレイヤー参照の明示は DSL として正当な差別化。

**悪い乖離**:
- `str | object` ポリモーフィック型の前例が主要ツールに少なく学習コスト高。→「手書き時のみ文字列を許容。生成側はオブジェクト形式必須」という二層ルールを ADR に追記することで対処できる。
- NetBox Cable の双方向性 → MLNDL 有向リンクへの変換で「from/to の方向決定ルール」が未定義。
- multi-homing (dvSwitch の複数 vmnic 同時 attach) が Phase 2 先送りでは L1 YAML の実用性が下がる可能性。Phase 1.5 として `attaches_to: AttachesTo | list[AttachesTo]` 前倒しを検討。

**Pass C への提言**: `attaches_to` のオブジェクト統一案再評価、NetBox Cable 変換の方向性ルール明記、multi-homing を Phase 1 で `str | list[str]` として許容するかの再検討。

---

### ADR-0002: ID 命名規則

**既存ツール比較**:
| ツール | 対応概念 | 整合度 | 備考 |
|--------|---------|--------|------|
| NetBox | slug: `^[-a-zA-Z0-9_]+$` (アンダースコア許容、大文字許容) | 中 | MLNDL はアンダースコア・大文字禁止で乖離 |
| Containerlab | 英小文字・数字・ハイフン慣習 | 高 | 実質 MLNDL と一致 |
| Kubernetes | `^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$` (RFC 1123) | 高 | 精神的に同じ |

**良い乖離**: 大文字禁止・DNS 63 文字上限は EVE-NG / Cytoscape.js での安全利用として適切。

**悪い乖離**:
- NetBox slug が `cumulus_vx`、`cisco_ios` などアンダースコアを多用するため、NetBox アダプターで変換+衝突回避処理が必要。→ アンダースコア許容 (`^[a-z][a-z0-9_-]{0,62}$`) への緩和を再検討。
- `vlan100` は NetBox の `VLAN.slug` 標準が `vlan-100` であることと乖離。`vlan-100` に統一推奨。
- マルチテナント環境での ID 衝突回避のガイドラインが未定義。

**Pass C への提言**: アンダースコア禁止の最終確定とその根拠の強化、`vlan100` → `vlan-100` への統一、マルチテナントスコーププレフィックスルールの appendix 追加。

---

### ADR-0003: role 語彙

**既存ツール比較**:
| ツール | 対応概念 | 整合度 | 備考 |
|--------|---------|--------|------|
| NetBox | device_role (自由 slug): spine/leaf/core/distribution/access/firewall/server 等 | 高 | MLNDL の Literal は NetBox 主要語彙の約 70% をカバー |
| Containerlab | `kind` (OS/ベンダー種別、例: srl/ceos/linux) | 低 | `kind` と `role` は直交; `kind` は `device_type` の管轄 |
| Ansible | group_vars で spine/leaf/firewall を慣用 | 高 | 実質対応 |

**良い乖離**: `vswitch`/`dvswitch` 明示は virt-heavy 環境に特化した正当な差別化。`Literal | str` ハイブリッドは NetBox の完全自由文字列より型安全性が高い。

**悪い乖離**:
- **`load_balancer` のアンダースコアが ADR-0002 のハイフン専用規則と直接矛盾**。NetBox 慣習は `load-balancer` (ハイフン)。→ `load-balancer` に変更すべき。
- `tor` は NetBox で一般的な device_role でなく、`leaf` で代替されることが多い。使い分け基準の明文化が必要。
- `border` は `border-leaf` と `border-router` で設計思想が大きく異なる。NetBox 慣習に沿うなら 2 語彙に分割を検討。

**NetBox アダプター変換テーブル (概略)**:
```python
NETBOX_TO_MLNDL_ROLE = {
    "spine": "spine", "leaf": "leaf", "access": "leaf",
    "distribution": "core", "core": "core",
    "border-router": "border", "edge": "border",
    "server": "server", "firewall": "firewall",
    "load-balancer": "load-balancer",  # ハイフン統一後
    "hypervisor": "hypervisor",
}
```

**Pass C への提言**: `load_balancer` → `load-balancer` (ADR-0002 との整合)、`tor` の使用基準明文化または削除、`border` の語義明確化。

---

### ADR-0004: implementation × role マトリクス

**既存ツール比較**:
| ツール | 対応概念 | 整合度 | 備考 |
|--------|---------|--------|------|
| NetBox | 物理/仮想を複数テーブルで管理。単一 implementation フィールドなし | 中 | |
| Containerlab | `kind: linux` でコンテナとして何でも表現可能。`core × container ❌` は疑問 | 低 | Cumulus Linux コンテナをコアスイッチとして使う構成は現実的 |
| EVE-NG | `type=qemu` (vm) / `type=docker` (container) と直接対応 | 高 | mlndl の `vm`/`container` は EVE-NG の実装種別に対応 |

**良い乖離**: lenient/strict 二段階モードは Kubernetes の `--dry-run=server` と思想が近く、CI/CD と開発時の両立として優れた設計。

**悪い乖離**:
- `core × container ❌` が Containerlab エコシステムと整合しない。→ `⚠` に緩和推奨。
- `vswitch × container ❌` も Linux bridge / OVS コンテナを排除。→ `⚠` に緩和推奨 (`dvswitch × container ❌` は維持)。
- `allow_unusual_combination` をノードフィールドに持つ設計は他ツール (K8s/Terraform) では前例が少なく誤用リスク高。→ トポロジーレベルの `meta.validation_overrides: [...]` への移動、またはプログラム API の `context={"strict": False}` のみで制御することを推奨。

**Pass C への提言**: `core × container` と `vswitch × container` を `⚠` に緩和。`allow_unusual_combination` を YAML フィールドとしては廃止し API レベルのみで制御。

---

### 総括 (ecosystem-reviewer)

Pass C 優先度 (ecosystem 視点):

| 優先度 | ADR | 理由 |
|--------|-----|------|
| 1 (最高) | **ADR-0003** | `load_balancer` のアンダースコアが ADR-0002 と直接矛盾。Phase 1 コード前に解決必須 |
| 2 (高) | **ADR-0002** | `vlan100` vs `vrf-tenant-a` のプレフィックス一貫性問題と、アンダースコア許容/禁止の最終決定が後続 ADR・全サンプルに波及 |
| 3 (中) | **ADR-0004** | `core × container ❌` が Containerlab ユーザーを排除するリスク。ただし lenient モードがデフォルトなので緊急度は中 |
| 4 (低) | **ADR-0001** | 基本設計は RFC 8345 と整合。multi-homing 先送りは Phase 1 スコープ内で許容範囲 |

**クロスカット注意**: ADR-0002「アンダースコア禁止」と ADR-0003 の `load_balancer` は同一 PR で修正すること。role 値の文字セット規則が `id` フィールドと同じ `^[a-z][a-z0-9-]+$` に従うことを両 ADR に記載すること。

---

## 横断総括

### アンカーが強く効いていた論点

| ADR | アンカー内容 | Pass C での対応方針 |
|-----|-----------|------------------|
| ADR-0001 | CLAUDE.md の「attaches_to に統一」という既成事実 | `layer` フィールドの必要性を ADR-0002 (グローバル一意 ID) と整合させる |
| ADR-0003 | CLAUDE.md の role 語彙まとめ表 (vswitch/dvswitch 含む) | vswitch/dvswitch の L1 概念への適合性を再評価 |
| ADR-0004 | 既存の `implementation: vm/physical/container` 3値固定 | マトリクスの「厳格化の対象」を mlndl の責務範囲に限定する |

### Pass A の結論がそのまま妥当な論点

| ADR | 妥当な決定 | 根拠 |
|-----|---------|------|
| ADR-0001 | 文字列 = ノード参照、オブジェクト = IF/リンク参照 の区別 | 3エージェント共通で論拠が独立している |
| ADR-0002 | グローバル一意 ID | `attaches_to` の文字列値解決を単純化する合理的理由がある |
| ADR-0002 | 最大 63 文字 (DNS ラベル制限) | 技術的根拠が明確 |
| ADR-0003 | `host` → `server` 統一 | linguist・spec-architect 共に合理的と評価 (削除根拠の弱さは別問題) |
| ADR-0004 | lenient デフォルト + strict mode オプション のハイブリッド | CI/CD vs 開発時の体験を両立する設計として合理的 |

### Pass C での再設計優先課題

| 優先度 | 課題 | 関連 ADR |
|-------|------|---------|
| ★★★ | `attaches_to` オブジェクト形式の `layer` フィールド不要説の検証 | ADR-0001, ADR-0002 |
| ★★★ | `vswitch/dvswitch` の L1 ロール適合性の再確認 | ADR-0003 |
| ★★★ | `core × container = ❌` の過剰制約の修正 | ADR-0004 |
| ★★ | ID プレフィックスのセパレータ統一 (`vlan100` → `vlan-100`) | ADR-0002 |
| ★★ | `allow_unusual_combination` の設計位置の再検討 | ADR-0004 |
| ★★ | バリデーション severity 基準の統一 | ADR-0001〜0004 |
| ★ | `tor` ロールの定義明確化または削除 | ADR-0003 |
| ★ | `bgp-adj` → `bgp-peer` 改名検討 | ADR-0002 |
| ★ | `dvswitch` ベンダー固有名詞問題 | ADR-0003 |

---

## Pass C 実行上の注意事項

1. **mlndl-spec-architect への制約**: Pass A のドラフト (`docs/decisions/drafts/` 以下) を参照禁止。参照してよいのは:
   - CLAUDE.md
   - 初期の設計プラン (リポジトリ外。現在は ADR が正)
   - 原案の論文 (必要時。手元の場所は CLAUDE.local.md)
   - 本ファイル (`round1-evaluation.md`) のみ

2. **各専門エージェントへの制約**: Pass A で自分が出したレビューを見ずに再起動する。

3. **優先処理**: ADR-0004 → ADR-0001 → ADR-0002 → ADR-0003 の順で設計。ADR-0001 と ADR-0002 は相互依存 (`layer` フィールドの必要性はグローバル一意 ID の設計に依存) があるため、順番に注意。

4. **「独立に同じ結論に到達した」記録**: Pass C で Pass A と同一の結論になった場合は、必ず「独立に同じ結論に到達した」と明記し、アンカー効果がなかったことを証明する。
