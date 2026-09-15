# Architecture Decision Records (ADR)

MLNDL の言語設計に関する設計決定を記録するディレクトリ。

## 運用ルール

### 2パス方式

各ラウンドの設計決定は **Pass A → Pass B → Pass C** の3フェーズで行う:

| フェーズ | 内容 | 成果物 |
|---------|------|--------|
| **Pass A** (初回策定) | 既存設計を踏まえたドラフト作成 | `drafts/NNNN-xxx.md` (Status: Draft) |
| **Pass B** (横断評価) | ドラフト群の横断 critique・アンカー検出 | `evaluations/roundN-evaluation.md` |
| **Pass C** (再設計) | Pass A を棚上げ、評価メモのみを入力に再設計 | `NNNN-xxx.md` (Status: Accepted) |

### ADR の Status

- `Draft` — Pass A のドラフト (`drafts/` に置く)
- `Accepted` — Pass C で確定した最終版 (このディレクトリ直下)
- `Superseded by ADR-XXXX` — 後継 ADR によって置き換えられた
- `Reopened by drafts/NNNNvN-<slug>.md` — 新しい上位 ADR の結果を受けて再評価中。ファイルは原本のまま保持し、再設計ドラフトは `drafts/NNNNvN-<slug>.md` に置く。最終的に本ファイルを書き換えて `Accepted` に戻す (他 ADR からのリンクを保全するためファイル名は変更しない)

### ファイル命名

| 種別 | パス | 例 |
|------|------|----|
| テンプレート | `0000-template.md` | — |
| Pass A ドラフト | `drafts/NNNN-<slug>.md` | `drafts/0001-attaches-to.md` |
| Pass B 評価 | `evaluations/roundN-evaluation.md` | `evaluations/round1-evaluation.md` |
| Pass C 最終版 | `NNNN-<slug>.md` | `0001-attaches-to.md` |

Pass A のドラフトは Pass C 完了後も削除しない（変更履歴として保存）。

---

## ADR 一覧

### ラウンド1: 基礎概念 (2026-05-27)

| ADR | タイトル | Status | Pass |
|-----|---------|--------|------|
| [0001](0001-attaches-to.md) | `attaches_to` の使い分け基準 | **Accepted** | C |
| [0002](0002-id-naming-convention.md) | ID 命名規則 | **Accepted** | C |
| [0003](0003-role-vocabulary.md) | `role` 語彙の確定 | **Accepted** | C2 |
| [0004](0004-implementation-role-matrix.md) | `implementation` × `role` の妥当組み合わせ | **Accepted** | C |
| drafts/0001 | 同上 Pass A ドラフト | Draft (archived) | A |
| drafts/0002 | 同上 Pass A ドラフト | Draft (archived) | A |
| drafts/0003 | 同上 Pass A ドラフト | Draft (archived) | A |
| drafts/0004 | 同上 Pass A ドラフト | Draft (archived) | A |

### ラウンド1.5: スコープ再定義と ADR-0003 再設計 (2026-05-29〜)

| ADR | タイトル | Status | Pass |
|-----|---------|--------|------|
| [0005](0005-mlndl-expressive-scope.md) | mlndl の表現スコープ定義 | **Accepted** | C |
| drafts/0005 | 同上 Pass A ドラフト | Draft (archived) | A |
| drafts/0003v2 | `role` 語彙 再設計 (ADR-0003 Reopen) | Draft (archived) | A2 |
| evaluations/round1.5 | ラウンド1.5 横断評価メモ | — | — |

### ラウンド2: リンク端点とメンバーシップ (2026-09-13〜)

| ADR | タイトル | Status | Pass |
|-----|---------|--------|------|
| [0006](0006-endpoints.md) | L1 リンク端点表現 (`endpoints`) | **Accepted** | C |
| drafts/0007 | vNIC / vSwitch / bridges | Draft | A |
| [drafts/0008](drafts/0008-cloud-networks-scope-location.md) | クラウドネットワークの表現 (`parent` / `labels` / `location`) | Draft | C |
| [drafts/0009](drafts/0009-membership-orthogonality.md) | メンバーシップ構成子の直交性 (`attaches_to` / `parent` / `labels`) | Draft | C 相当 |

**ADR-0009 の経緯**: 「箱への所属」の命名を 6 ラウンド × 5 エージェント並列で検討した。
20 語以上が既存ネットワーク用語・プロジェクト内用語と衝突して収束せず、最終的に
**難航の原因が語彙不足ではなく構造の誤り** (階層ネストと多軸分類を 1 構成子で表そうとしていた)
と判明し、2 構成子への分離で決着した。却下語の全リストは ADR-0009 の Alternatives Considered を参照。
