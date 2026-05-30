# ADR-0003v2: `layer1.nodes.role` 語彙の再設計

- **Status**: Draft
- **Date**: 2026-05-29
- **Deciders**: mlndl-spec-architect (Pass A2)
- **Pass**: A2 (ADR-0005 Accepted 後の再設計ドラフト)
- **Reopens**: 0003-role-vocabulary.md

## Context

ADR-0005 (Pass C) によって mlndl の表現スコープが「物理構成図 (a)・論理構成図 (b)・物理-論理連携 (c) の三側面」として確定し、新概念のスコープ判定に **D4 フレームワーク (4軸 Yes/No)** が導入された。これにより、ラウンド1 で先送りされた `role` 語彙の確定問題を、語彙列挙ではなく**「`role` フィールドはそもそもどのカテゴリの構成子か」**から再評価できる状態になった。

### ユーザー発話 (Reopen のトリガ)

> 「role で spine, leaf hypervisor とか分ける必要ある?? role が広がりすぎない?? 新しい要素が出たら、都度追加するの? 何をどこまで表現する言語なのか整理した方がよい気がする。」

この発話には三つの構造的な問いが含まれる:

1. **存在意義の問い**: `role` フィールド自体が必要か
2. **語彙膨張の問い**: 新概念が出るたび canonical 集合を拡張するのか
3. **境界の問い**: mlndl がどこまでを「自分の語彙」として持つのか

ADR-0005 D3 は (3) に三側面+D3スコープ表で回答し、D4 は (1)(2) を機械的に判定する道具を提供した。本 ADR は (1)(2) に対する `role` 単体の回答を出す。

### ADR-0005 D4 フレームワークを `role` フィールド (存在自体) に適用

| 判定軸 | `role` フィールドの判定 | 根拠 |
|--------|----------------------|------|
| 削除すると参照整合性が崩れるか | **No** | `role` を参照する `attaches_to` / `members` / `vrf` 等のリンクは存在しない。削除しても他エンティティは解決可能 |
| RFC 8345 ノードグラフから消えるか | **No** | RFC 8345 のノードは ID と supporting で成立。`role` は規定外属性 (現行 ADR-0003 Consequences で `mlndl:role` 拡張として出力と既述) |
| 値の変更でトポロジーの意味境界が変わるか | **No** | `spine` を `leaf` に書き換えても broadcast_domain / 物理リンクの集合は変わらない。Clos の幾何は `links` で決まる |
| `broadcast_domain` / `blast_radius` 検索結果に影響するか | **No (フィルタ用途は除く)** | クエリ結果集合は VLAN/VRF/L1リンク で決定する。`role` は結果の**絞り込みヒント**であって**生成要素**ではない |

**4軸すべて No → ADR-0005 D4 に従えば「注釈 (annotation) 側」に分類されるべき構成子である。** これは現行 ADR-0003 D1 の「ヒントであって制約ではない」という位置づけと矛盾しない一方、「9 値の canonical 集合を mlndl コアが warning 判定する」という現行運用は **注釈に対して過剰に強い意味論的契約を結んでいる**ことを示唆する。

### Pass A2 で再考すべき論点

- 注釈構成子に対し canonical 集合を mlndl が保持し warning を出す責務があるか
- 「新しい要素が出るたびに追加するのか」への構造的回答 (= 成長戦略)
- ndl-viz / eve-lab-builder が `role` を消費する事実と、mlndl の責務境界の整合

## Decision

**採用案: δ (`role: str` を自由形式化、canonical 集合は informative ドキュメント化のみ。mlndl コアは warning を出さない)**

詳細は「5案の等価評価」末尾の推奨理由を参照。要点:

1. `role` は ADR-0005 D4 で注釈に分類される構成子であり、mlndl コアが意味論的契約を持つべきではない
2. 構文制約 (`^[a-z][a-z0-9_-]*$`、ADR-0002 D3) は維持。語彙制約は外す
3. canonical 9 語彙はドキュメント (`docs/role-vocabulary.md`) として informative に提示。ndl-viz / eve-lab-builder の既定スタイル/マッピングの整合点として機能させる
4. 「新しい要素が出るたび ADR を更新する」運用を停止し、ユーザー発話の構造的不満に回答する

## 5案の等価評価

### α — 現状維持 (canonical 9 語彙を確定語彙として固定)

**概要**: 現行 ADR-0003 (Pass C) の D2 / D6 / D7 をそのまま維持。`spine | leaf | core | border | server | firewall | load-balancer | hypervisor | management` の 9 値を canonical とし、非該当値は warning。

**メリット (義務的列挙)**:
- **実装単純性**: `CANONICAL_ROLES: frozenset[str]` 一つで実装が完結。pydantic `field_validator` での照合も既に書かれている
- **既存 fixture の変更不要**: `tests/fixtures/` の `role: spine` / `role: leaf` 等が引き続き valid
- **ndl-viz の即時利用性**: `exporter/cytoscape.py` で canonical 9 種に対応するスタイル定義が前提でき、Spine-Leaf 整列・色分けが追加実装なしで動く
- **業界一致度**: `spine`/`leaf`/`core`/`border` は DataCenter 業界で確立した語彙。NetBox の DeviceRole slug ともそのまま揃う
- **`container × hypervisor = error` (ADR-0004 D-1) との接続が単純**: canonical 集合に `hypervisor` がある前提で error ルールが書ける
- **ADR としての完成感**: ラウンド1 Pass C で 4 レビュアーが承認済み。再設計のコスト/リスクを払わない選択
- **「曖昧さの少なさ」**: 自由形式化すると `lb`/`load_balancer`/`load-balancer`/`LoadBalancer` の表記揺れが入力 YAML に発生する。canonical 固定はこれを抑止する
- **ドキュメント効果**: 9 値リストが「mlndl が想定する物理ロール像」をユーザーに伝える教育的役割を果たす

**デメリット**:
- ADR-0005 D4 適用で 4 軸すべて No と判定された構成子に対し、mlndl が canonical 集合という意味論的契約を持つ正当性が薄い
- 「新しい要素が出るたび追加するのか」への構造的回答が「都度 ADR 更新する」になり、ユーザー発話の不満に応答できない
- D2 の注記「role は単一軸ではない (位置・機能・実行種別・管理目的の混在)」自体が、canonical 集合の理論的不整合を自認している
- ADR-0003 Consequences で「Phase 2 で `access`/`distribution`/`container-host` 追加検討」と既に予告されており、語彙膨張の予兆が既に ADR 内に存在する

**ユーザー発話への回答**: 「新しい要素は ADR 更新で都度追加する」(構造的回答にならない)

**D4 適用**: `role` 全体は注釈側だが、α は注釈に canonical+warning を載せる。D4 と直接対立はしないが、「注釈側構成子に意味論的契約を載せる」運用上の異物感が残る。

---

### β — canonical 縮小 (トポロジー位置軸のみ 4 値、他は open-string)

**概要**: canonical を `spine | leaf | core | border` の 4 値 (位置軸) に絞る。`server`/`firewall`/`load-balancer`/`hypervisor`/`management` は warning なしの自由文字列として受理。

**メリット**:
- 「単一軸ではない」現行 D2 の注記の不整合を解消できる (位置軸に統一)
- canonical 集合の膨張圧力を「位置軸の追加 (`access`/`distribution`/`super-spine`)」に限定できる
- `hypervisor` を canonical から外せば ADR-0004 D-1 の依存関係を整理する機会になる

**デメリット**:
- `role: server` / `role: firewall` 等の従来 fixture が「warning なし自由文字列」に格下げされる。ndl-viz スタイル定義の根拠が弱くなる
- ADR-0004 D-1 (`container × hypervisor = error`) が、canonical でない値を error 条件に使う構造になり違和感
- 縮小ライン (位置軸のみ) の理論的線引きが「mlndl が DC Clos を主対象とする」という暗黙前提に依存する

**ユーザー発話への回答**: 「位置軸だけ ADR で固定し、機能・用途軸は自由」(部分的回答だが、軸分離の説明責任が新たに発生)

**D4 適用**: canonical 縮小しても「位置軸 4 値の warning」が残るため、D4 全 No 構成子への意味論的契約という構造は α と同じ。

---

### γ — `role` フィールド廃止、`labels: dict[str, str]` (Kubernetes 風タグ) に置換

**概要**: `role` を削除し、`labels: dict[str, str]` フィールドに置き換える。`labels: {topology-role: spine, device-function: switch}` のような任意キー/値タグ運用。

**メリット**:
- ADR-0005 D4 で注釈と判定された構成子の責務に最も忠実
- 「軸ごとに分けたい」「機能ロールと位置ロールを両立したい」要求に対し、構造的に正解
- ndl-viz / eve-lab-builder は `labels["topology-role"]` を読むだけで現行相当の動作を再現できる
- Kubernetes / NetBox tag との親和性が高い

**デメリット**:
- **既存 fixture が全て移行必要** (`role: spine` → `labels: {role: spine}` 等)。移行コスト中〜高
- 現行 ADR-0003 Pass C (Accepted) を完全に置換する Supersedes になる。ラウンド1 の合意を覆す重さ
- ADR-0004 D-1 の `container × hypervisor = error` の参照先が `labels["role"]` 等の規約依存になる
- YAML 記述量が増える (`role: spine` の 1 行が `labels:\n  role: spine` の 2 行に)
- 自由度が高すぎ、ユーザー側で「どのキーを使うべきか」の合意形成コストが mlndl 外で発生する

**ユーザー発話への回答**: 「role は廃止。意味論的ラベル付けは labels に集約」(構造的回答として最強)

**D4 適用**: labels 全体が注釈側に完全に整理される。意味論的契約は mlndl 外 (ndl-viz の規約) に委譲。

---

### δ — `role: str` 自由形式化、canonical 集合は informative ドキュメント化のみ

**概要**: 型は `role: str | None`、構文制約 (`^[a-z][a-z0-9_-]*$`) のみ維持。canonical 9 語彙は `docs/role-vocabulary.md` で「ndl-viz / eve-lab-builder が既定スタイル/マッピングを持つ推奨値」として informative に提示する。mlndl コアは canonical 一致を warning にしない。

**メリット**:
- ADR-0005 D4 全 No 判定との整合が取れる (注釈側構成子に意味論的契約を載せない)
- 既存 fixture の変更不要 (構文制約は維持されるため `role: spine` は valid のまま)
- 「新しい要素が出るたび ADR 更新するのか」への構造的回答: **「mlndl は ADR 更新しない。ndl-viz / eve-lab-builder が消費側で語彙を成長させる」**
- canonical ドキュメントは残るので、ユーザーは推奨値を参照可能。教育的効果は α とほぼ同等を維持
- `container × hypervisor = error` (ADR-0004 D-1) は「文字列値 `hypervisor` への参照」として独立に維持できる (canonical かどうかと独立)
- ラウンド1.5 で確定した「mlndl はコアの責務を最小化、消費側ツールが意味付与を担う」方針 (ADR-0004 / ADR-0005) と一貫
- α からの移行コストが最も低い (validator で warning を出さなくするだけ)

**デメリット**:
- 表記揺れ (`load_balancer` / `load-balancer` / `lb`) を mlndl が抑止しなくなる。アダプター層 (NetBox→mlndl) で正規化責務が発生
- ndl-viz が未知 role に対するデフォルトスタイル動作を明示する必要がある (が、これは ndl-viz 側の責務として ADR-0005 D3-2「行き先」原則に合致)
- 現行 ADR-0003 D5 (`load-balancer` ハイフン正規形) / D7 (warning 規約) は informative ドキュメントへ降格

**ユーザー発話への回答**: 「`role` は注釈なので mlndl は語彙を持たない。推奨値は docs に置き、新値追加で ADR は動かさない」(構造的回答かつ移行コスト最小)

**D4 適用**: 4 軸全 No 構成子の扱いとして最も整合的。

---

### ε — 軸別分割 (`topology_role` / `function_role` / `host_type` などに分離)

**概要**: 現行 D2 注記の「位置・機能・実行種別・管理目的の混在」を構造に反映し、`topology_role: spine|leaf|...` / `function_role: firewall|load-balancer|...` / `host_type: hypervisor|...` 等に分割。

**メリット**:
- 「単一軸ではない」問題を構造的に解決
- 各軸内では canonical 集合を理論的に閉じやすい
- 「新軸追加」と「既存軸内の語彙追加」が区別でき、成長戦略が明確化

**デメリット**:
- フィールド数が一気に増え、L1Node スキーマの記述量が膨張
- どの軸に属するか境界が曖昧な値 (`border` は位置か機能か？) が即座に発生する
- 既存 fixture の全面移行が必要 (γ より重い)
- ADR-0004 D-1 が `host_type: hypervisor` を参照する形に書き換えが必要
- 「軸が3つで足りるのか」という新たな膨張問題が発生 (`management` はどの軸か？)

**ユーザー発話への回答**: 「軸ごとに分けたので語彙膨張は軸内で閉じる」(回答だが、移行コストと新たな複雑度のトレードオフが悪い)

**D4 適用**: 各軸が個別に D4 判定対象になるが、いずれも 4 軸全 No (注釈側) と判定される見込み → 注釈側に複数フィールドを構造化する正当性が弱い。

---

### 「新しい要素が出るたびに追加するのか」への各案の構造的回答 (まとめ)

| 案 | 成長戦略 |
|----|---------|
| α | mlndl コアの ADR で都度追加 (構造的回答にならず、ユーザー不満が残る) |
| β | 位置軸のみ ADR 管理、他は自由。部分回答 |
| γ | mlndl は labels 構造だけ提供。語彙は消費側で命名 |
| **δ** | **mlndl は ADR 動かさない。docs/role-vocabulary.md と消費側ツール (ndl-viz / eve-lab-builder) で成長を吸収** |
| ε | 軸内で閉じる (が新軸追加問題が残る) |

## Consequences

### 良い影響 (δ 採用前提)

- ADR-0005 D4 と `role` 取扱いが構造的に整合する
- 「新概念が出るたび mlndl ADR を動かす」運用が停止し、ユーザー発話の構造的不満に応答できる
- mlndl コアのバリデーション責務が縮小し、Phase 1 実装の表面積が下がる
- 既存 fixture の変更がほぼ不要 (構文制約は維持される)
- NetBox / neteye アダプターは「値の正規化責務はアダプター側」と明確化できる

### 悪い影響 / トレードオフ

- 表記揺れの第一防衛線が mlndl から消える。アダプター実装ガイドライン (informative) が必要
- ndl-viz は未知 role へのデフォルトスタイルポリシーを ndl-viz 側 ADR として持つ必要が出る
- ADR-0003 Pass C (Accepted) の D5 (ハイフン正規形)・D6 (型定義)・D7 (severity) の一部が informative ドキュメントへ降格 (decision としては Supersede)
- 現行 ADR-0004 D-1 の `container × hypervisor` の `hypervisor` 文字列が canonical 集合に依存しないことを ADR-0004 側で明文化する追記が必要

### 影響を受けるコンポーネント

- **スキーマ** (`src/mlndl/schema/layer1.py`): `role: str | None`、構文制約 `^[a-z][a-z0-9_-]*$` のみ維持。`CANONICAL_ROLES` 定数は削除または informative 定数として残置 (ndl-viz が import する場合)
- **バリデーター** (`src/mlndl/validator.py`): canonical 集合との照合・warning 生成を削除。`container × hypervisor = error` は ADR-0004 に従い独立に維持
- **エクスポーター** (`exporter/cytoscape.py`): 未知 role への fallback スタイルを明示。canonical 9 種への既定スタイルは ndl-viz 側のデフォルトとして残置可
- **エクスポーター** (`exporter/rfc8345.py`): `mlndl:role` 拡張として出力 (現行通り)
- **サンプル** (`tests/fixtures/`): 既存 `role: spine` 等の値は valid のまま、変更不要
- **文書**:
  - `CLAUDE.md` §5 (`layer1.nodes.role` 語彙) の改訂 — 「9 canonical 語彙確定」→「推奨語彙は `docs/role-vocabulary.md` 参照」
  - 新規 `docs/role-vocabulary.md` (informative) — 現行 D2 の 9 値定義表を移植
  - `ADR-0004` Consequences に「`hypervisor` の error 判定は canonical 集合に依存しない文字列照合」と注記追加

### 移行コスト

- 実装: 低 (validator の warning 生成削除と canonical 定数の整理のみ)
- ドキュメント: 中 (CLAUDE.md §5 改訂 + 新規 docs ファイル作成 + ADR-0004 追記)
- 既存 fixture: 変更不要
- 消費側ツール (ndl-viz / eve-lab-builder): 「未知 role への fallback ポリシー」を各 ADR / 設計に明文化する作業が発生 (mlndl リポジトリ外)

## Alternatives Considered

5案の等価評価セクションを参照。Pass A2 の最終判断順位:

1. **δ 採用** — D4 整合 / 移行コスト最小 / ユーザー発話への構造的回答 / 消費側責務分離の方針 (ADR-0004/0005) と一貫
2. γ — 構造的には最も正しいが移行コストとラウンド1合意の覆しが重い。Phase 2 以降で再評価候補
3. α — 「現状維持で良いか」の比較基準として保持。δ 不採用なら α に戻る
4. β — 軸分離の説明責任を負う割に部分的回答に留まる
5. ε — 移行コストと新たな複雑度のトレードオフが悪く、注釈側構成子に対し過剰設計

## Pass A との差分 / Pass C との差分

ラウンド1 Pass C (現行 Accepted) との主要差分:

| 領域 | 現行 ADR-0003 Pass C | 本 Pass A2 (δ採用) |
|------|---------------------|-------------------|
| D2 canonical 集合 | 9 値の確定語彙として規範化 | informative ドキュメント (`docs/role-vocabulary.md`) に降格 |
| D5 正規形 (ハイフン) | `load-balancer` を canonical 正規形として確定、`load_balancer` は warning | アダプター実装ガイドラインへ移動。mlndl コアは warning を出さない |
| D6 型定義 | `str \| None` + canonical 照合 validator | `str \| None` + 構文制約のみ。canonical 照合を削除 |
| D7 severity 表 | non-canonical を warning | warning 行を削除。文字セット違反 error と ADR-0004 由来 error のみ残置 |
| 成長戦略 | Phase 2 で `access`/`container-host` 追加検討 (ADR 更新前提) | mlndl ADR は動かさない。消費側ツールが成長を吸収 |

**独立に同じ結論に到達した点**:
- `role` は optional な意味論的ラベルである (D1)
- 構文制約 `^[a-z][a-z0-9_-]*$` (ADR-0002 D3 由来)
- `container × hypervisor = error` は維持 (ADR-0004 D-1)

**Pass C との変更理由**:
- ADR-0005 D4 (4軸 Yes/No フレームワーク) がラウンド1.5 で確定し、`role` 全体が「注釈側」と機械的に判定される根拠が成立した
- ユーザー発話「新しい要素が出るたび追加するのか」に対し、ラウンド1 Pass C が構造的回答を持たなかった

## References

- `docs/decisions/0005-mlndl-expressive-scope.md` — D4 判定フレームワーク (本 ADR の主入力)
- `docs/decisions/evaluations/round1.5-evaluation.md` — 段階1 Pass B 評価
- `docs/decisions/0003-role-vocabulary.md` — 現行 Accepted (本 ADR で Reopen)
- `docs/decisions/0002-id-naming-convention.md` — D3 文字セット規則 / D8 severity 定義
- `docs/decisions/0004-implementation-role-matrix.md` — D-1 `container × hypervisor` (本 ADR と独立に維持)
- `CLAUDE.md` §5 — `layer1.nodes.role` 語彙 (本 ADR で改訂対象)
- RFC 8345 — `role` は規定外属性 (`mlndl:role` 拡張として出力)
- MLNDL 原案 (NAIST, 2011) — `role` 概念は本来三層モデルに含まれず、注釈相当の位置づけ
