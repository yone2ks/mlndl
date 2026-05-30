# ADR-0003: `layer1.nodes.role` 語彙の確定

- **Status**: Accepted
- **Date**: 2026-05-29
- **Deciders**: mlndl-spec-architect (Pass C2), mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, ecosystem-reviewer, mlndl-example-author
- **Pass**: C2 (ラウンド1.5 再設計後の最終版)
- **Supersedes**: drafts/0003v2-role-vocabulary.md (Pass A2 ドラフト)
- **Supersedes (original)**: drafts/0003-layer1-role-vocabulary.md (ラウンド1 Pass A ドラフト)

## Context

ラウンド1 Pass C で `layer1.nodes.role` を 9 個の canonical 語彙 (`spine | leaf | core | border | server | firewall | load-balancer | hypervisor | management`) に固定し、未知値は `warning` という設計を確定した。

ラウンド1.5 で ADR-0005「mlndl の表現スコープ定義」が Accepted となり、その D4「構成要素 vs 注釈の判定フレームワーク」(4 軸 Yes/No) を `layer1.nodes.role` に独立に適用した結果、以下の判定が得られた:

| 判定軸 | `layer1.nodes.role` への適用 |
|--------|---------------------------|
| 削除すると参照整合性が崩れるか | **No** — `role` を消してもどの ID 参照も壊れない |
| RFC 8345 ノードグラフから消えるか | **No** — ノード・リンク・supporting 関係に影響なし |
| 値の変更でトポロジーの意味境界が変わるか | **No** — `role: spine` を `role: leaf` に書き換えても broadcast_domain も blast_radius も変わらない |
| `broadcast_domain` / `blast_radius` 検索結果に影響するか | **No** — クエリ範囲はトポロジー構造に依存し、`role` 値には依存しない (フィルタ条件として使う場合は呼び出し側の絞り込み意図であり、トポロジーの意味境界ではない) |

4 軸すべて No → ADR-0005 D4 の判定上 **注釈側**。「mlndl コアが意味論的契約 (canonical 集合・warning) を持つべきでないカテゴリ」に分類される。

これを受けてユーザーから ADR-0003 の Reopen 指示が出され、Pass A2 / Pass B2 (5 並列レビュー: linguist / dsl-designer / network-tech / ecosystem / example-author) / Pass C2 (本 ADR) を経て最終確定する。Pass C2 は Pass A2 ドラフトを参照禁止とし、`evaluations/round1.5-evaluation.md` 段階2 章のみを入力にゼロから再設計した。

ただし ADR-0004 D-1 (`container × hypervisor = error`) は `hypervisor` という文字列リテラルに依存しており、canonical 集合を informative 化した場合の取り扱いに矛盾が生じうる (N3 クリティカル指摘)。本 ADR はこれを D3 の normative tokens として明示的に解消する。

## Decision

### D1. `role` フィールドの位置づけ

`layer1.nodes.role` は **注釈側構成子 (annotational element)** とする。ADR-0005 D4 で 4 軸すべて No と判定された構成子であり、スコープ内 (mlndl YAML として記述可能) ではあるが、**mlndl コアは canonical 集合・warning などの意味論的契約を持たない**。

**注釈側構成子の定義**:

> ADR-0005 D4 の 4 判定軸すべてに No と判定された構成子。スコープ外ではない (記述は許される) が、mlndl コアが意味論的契約 (canonical 値域・warning) を持つべきでないカテゴリ。値の解釈・スタイル適用・拡張は下流ツール (ndl-viz / ValidationPlugin / NetBox アダプター等) の責務。

これは ADR-0005 D4 表の「注釈 (スコープ外候補)」とは区別される。後者は記述自体をスコープ外に置く候補、本 ADR の「注釈側構成子」はスコープ内のラベル系フィールドである。

### D2. 型と構文制約

```python
class L1Node(BaseModel):
    role: str | None = None  # 任意。未指定でも valid。
```

- **型**: `str | None`
- **既定値**: `None`
- **構文制約**: `role` は ID ではないため ADR-0002 D1 の ID 正規表現は適用しない。ただし慣習として小文字・ハイフン区切り (`load-balancer`, `route-reflector`) を推奨する (`docs/role-vocabulary.md` に informative として記載)
- **mlndl コアによる値域チェック**: 行わない (D3 の normative tokens を除く)
- **`warning` 発行**: 行わない

### D3. Normative tokens (ADR-0004 との接続)

ADR-0004 D-1 の `container × hypervisor = error` ルールが文字列リテラルに依存するため、**`role` 値のうち他 ADR が contract する語彙を `normative tokens` として本 ADR が例外保持する**。

現行の normative tokens は 1 語のみ:

| Token | 参照元 ADR | 用途 |
|-------|-----------|------|
| `hypervisor` | ADR-0004 D-1 | `implementation: container` との組み合わせで error |

実装方針:

```python
@model_validator(mode="after")
def _reject_container_hypervisor(self) -> "L1Node":
    # ADR-0004 D-1: normative token "hypervisor" との文字列リテラル照合
    if self.implementation == "container" and self.role == "hypervisor":
        raise ValueError(
            "implementation=container と role=hypervisor の組み合わせは"
            "技術的に成立しません (ADR-0004 D-1)"
        )
    return self
```

- canonical 集合への依存はゼロ。`role: hypervisor` というリテラルにのみ依存する
- `role: vmware-esxi` / `role: kvm-host` 等は **D-1 の error 対象外** — これは「`hypervisor` という normative token を選択した結果の意図された挙動」であり、mlndl のバグではない
- 将来 normative tokens が増える場合、追加する ADR 側が本 ADR D3 への追記を明示的に行う

### D4. `CANONICAL_ROLES` 定数の扱い

`src/mlndl/constants.py` に **informative 定数** として残置する:

```python
# informative — mlndl コアのバリデーターはこの定数を参照しない。
# ndl-viz の既定スタイル適用、ValidationPlugin の語彙チェック、
# NetBox アダプターの DeviceRole 変換などの下流ツール用。
CANONICAL_ROLES: frozenset[str] = frozenset({
    "spine", "leaf", "core", "border",
    "server", "firewall", "load-balancer",
    "hypervisor", "management",
})
```

- mlndl コアのバリデーターは参照しない (`role` 値域チェックはしない)
- `from mlndl import CANONICAL_ROLES` で下流ツールが import 可能
- 「mlndl の推奨語彙の単一情報源 (single source of truth)」として保全し、ndl-viz / ValidationPlugin / アダプターがハードコードによる分散を起こさないようにする
- 削除案は却下: 削除すると下流が独自にハードコードすることになり推奨語彙の単一情報源が失われる

### D5. 適用範囲宣言

本 ADR の対象は **`layer1.nodes.role` のみ** とする。

mlndl YAML 内の他の `role` 系フィールドは本 ADR の対象外であり、各 ADR / スキーマが独立に意味論的契約を維持する:

| フィールド | 所管 | 意味論的契約 |
|-----------|------|------------|
| `layer1.links[].link_role` | layer1 スキーマ | 列挙型 (`underlay \| access \| peer-link \| management \| uplink`) を維持 |
| `protocols.bgp.role` | protocols スキーマ | 列挙型 (`underlay \| overlay`) を維持 |
| `protocols.bgp.nodes[].role` / `neighbors[].role` | protocols スキーマ | 列挙型 (`route_reflector \| route_reflector_client` 等) を維持 |
| `layer3.gateway_redundancy.protocol` | layer3 スキーマ | 列挙型 (`anycast_gateway \| vrrp`) を維持 |

これらは ADR-0005 D4 の「値の変更でトポロジーの意味境界が変わるか」軸で Yes となるため注釈側構成子ではなく、本 ADR の規定 (オープン語彙化) は適用しない。

### D6. 推奨語彙と `docs/role-vocabulary.md`

`docs/role-vocabulary.md` を新設し、以下を informative ドキュメントとして提供する:

- D4 の `CANONICAL_ROLES` 9 語彙とその意味
- 慣習表記 (小文字・ハイフン区切り、`load-balancer` ハイフン正規形)
- NetBox `DeviceRole` slug → mlndl role 変換表 (例: `top-of-rack` → `leaf`, `border-leaf` → `border`)
- **ndl-viz 既定スタイル適用の条件**: 「推奨値以外の `role` 値では ndl-viz はフォールバックスタイル (グレーノード) を使用する」と明記し、推奨値準拠の動機を文書側で担保する

ラウンド1 Pass C で確定していた `load-balancer` ハイフン正規形 (旧 D5) は本 ADR から `docs/role-vocabulary.md` (informative) に**降格**する。

## Consequences

### 良い影響

- **ADR-0005 D4 の判定結果が一貫適用される**: `role` は注釈側構成子として整理され、コア仕様と informative 規約の責務が分離する
- **新興・ベンダー固有 role への耐久性**: `smart-nic` / `dpu-offload` / `service-mesh-gw` 等が出ても ADR 更新不要。「新しい要素が出るたびに追加するのか」というユーザー発話への構造的回答
- **NetBox / OpenConfig 連携**: 任意の slug を mlndl `role` に転写できる。canonical でなくともパース可能
- **下流ツールの単一情報源 (CANONICAL_ROLES) 保全**: 推奨語彙の分散を防止
- **ADR-0004 D-1 の実装が明確化**: normative token 化により `hypervisor` リテラル照合が「意図された設計」として明文化される

### 悪い影響 / トレードオフ

- **コアが typo を検出できない**: `role: spien` (typo) も valid。検出は ValidationPlugin (Phase 3+) または ndl-viz のフォールバックスタイルで提示される
- **`hypervisor` 1 語のみが事実上の reserved word**: 「mlndl は語彙を持たない」という建前と、ADR-0004 が参照する 1 語の例外保持という現実は表向き齟齬する。D3 の normative tokens として明示することで設計上は整理されるが、説明コストは残る
- **推奨値準拠の動機が docs + ndl-viz の連動に依存**: ndl-viz が存在しないコンテキストでは推奨値準拠の動機が弱い

### Phase 1 への影響範囲

- **スキーマ** (`schema/layer1.py`): `role: str | None = None` に変更。`Literal[...]` 制約は削除
- **バリデーター** (`validator.py`): `role` 値域チェックと未知値 `warning` を削除。D3 の `container × hypervisor` エラーチェックは ADR-0004 の実装範囲として残置
- **定数** (`src/mlndl/constants.py`): `CANONICAL_ROLES` を新設 (informative)
- **ドキュメント**: `docs/role-vocabulary.md` 新設、CLAUDE.md §5 の記述を簡略化 (canonical 集合は informative 文書へのリンクに置き換え)
- **エクスポーター**: 影響なし (`mlndl:role` 拡張として出力は現行通り)
- **サンプル**: 既存 fixtures は影響なし (推奨語彙のまま記述されているため)

### Phase 2+ 申し送り

- **γ (labels 化)**: `labels: dict[str, str]` への移行は Phase 1 では採用しない。将来 labels フィールド導入時に `role` を Supersede 対象とする
- **ε (複合フィールド分割)**: `topology_role / function_role / host_type` は Phase 1 で採用不可 (試し書き検証で判断コストが過大と確認)。将来 labels 導入時に再評価
- **ValidationPlugin の語彙チェック (Phase 3+)**: `CANONICAL_ROLES` を契約点として linter 系プラグイン (「`role: spine` なのに VTEP source を持つ」検出等) が利用する想定

## Alternatives Considered

### α: ラウンド1 Pass C の維持 (canonical 9 値 + warning)

- **却下理由**: ADR-0005 D4 の独立適用で 4 軸全 No と判定された。`role` がトポロジーの意味境界に寄与しないにもかかわらず mlndl コアが値域を持つのは ADR-0005 の方針と矛盾する。また新興 role への拡張性が低く、「新しい要素が出るたびに追加するのか」というユーザー発話への構造的回答にならない

### β: 位置軸 enum + 機能軸 free

- **却下理由**: SP コア (`pe`/`p`/`asbr`/`rr`) やエンタープライズ 3-Tier (`access`/`distribution`/`core`) では位置軸が 5〜7 値に膨らみ、α の語彙膨張問題を縮小再現するだけ

### γ: `labels: dict[str, str]` 化 (Kubernetes 風)

- **却下理由**: Phase 1 では構造が過剰。キー名規約がないと機能しない。Phase 2+ 申し送り

### ε: 複合フィールド分割 (`topology_role` / `function_role` / `host_type`)

- **却下理由**: 試し書き検証で Phase 1 採用不可と確認。`firewall1` 1 件書くだけで軸判断コストが発生する

### (採用) δ: オープン語彙化 + informative 推奨値 + normative tokens 例外

- **採用理由**: ADR-0005 D4 判定と整合し、ADR-0004 D-1 の挙動も normative tokens 明示で明確化される。下流ツールとの責務分離が最も明快。移行コスト最小 (Literal 削除と warning 削除のみ)

## Pass A との差分 (ラウンド1 Pass C → 本 Pass C2)

| 項目 | ラウンド1 Pass C | Pass C2 |
|------|----------------|---------|
| `role` 型 | `Literal[9 値] \| str` (canonical 集合に意味論的契約あり) | `str \| None` (注釈側構成子。コアは値域チェックしない) |
| 未知値の扱い | `warning` 発行 | 何もしない (warning も発行しない) |
| canonical 集合の所在 | ADR 本文に列挙 (normative) | `src/mlndl/constants.py` の `CANONICAL_ROLES` (informative) + `docs/role-vocabulary.md` |
| `hypervisor` の扱い | canonical の 1 値 | **normative token** として D3 で例外保持 (新規) |
| `load-balancer` ハイフン正規形 | ADR D5 (normative) | `docs/role-vocabulary.md` に降格 (informative) |
| 適用範囲宣言 | 暗黙 (全 `role` フィールドに適用と読めた) | **`layer1.nodes.role` のみ** と明示 (D5、新規) |
| 推奨値準拠の動機 | warning による検出 | ndl-viz フォールバックスタイル + docs (新規) |
| `vswitch` / `dvswitch` | canonical から除外 (Phase 2 L2 へ) | 同左 (変更なし) |

### Pass C2 で独立に同じ結論に到達した箇所

- **δ 採用**: ADR-0005 D4 の 4 軸を `role` に独立適用した結果、Pass A2 と同じく 4 軸全 No と判定。注釈側構成子化が ADR-0005 と整合する唯一の合理的選択
- **`CANONICAL_ROLES` informative 残置**: 下流ツール (ndl-viz / NetBox アダプター / ValidationPlugin) の単一情報源としての必要性は Pass A2 ドラフトを見ずとも下流影響分析から導出
- **`hypervisor` の normative token 化**: ADR-0004 D-1 が `hypervisor` リテラルに依存している以上、canonical informative 化と D-1 維持を両立するには normative token 概念の導入以外に無矛盾な解がない
- **ε の Phase 1 不採用**: Phase 1 = L1 のみのスコープと「Phase 1 スコープ最小化」原則から独立に導出

## References

- `CLAUDE.md` — §5 `layer1.nodes.role` 語彙、§7 仮想化環境の L1 表現
- `docs/decisions/evaluations/round1.5-evaluation.md` — 段階2 Pass B2 評価メモ
- `docs/decisions/0004-implementation-role-matrix.md` (Accepted) — D-1 が本 ADR D3 の normative token を参照
- `docs/decisions/0005-mlndl-expressive-scope.md` (Accepted) — D4 判定フレームワーク (本 ADR の主根拠)
- `docs/decisions/0001-attaches-to.md` (Accepted)
- `docs/decisions/0002-id-naming-convention.md` (Accepted) — D8 severity 定義
- RFC 8345 — node/link supporting model (注釈フィールドは supporting 関係に直接寄与しない)
- MLNDL 原案 (NAIST, 2011) — `role` 相当の意味論的ラベルは MLNDL 原案にも存在せず、本 ADR の注釈側化は原案の精神と整合
