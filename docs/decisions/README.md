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
| [0005](0005-mlndl-expressive-scope.md) | mlndl の表現スコープ定義 (2026-10-04 に ADR-0011 で部分改訂) | **Accepted** | C |
| drafts/0005 | 同上 Pass A ドラフト | Draft (archived) | A |
| drafts/0003v2 | `role` 語彙 再設計 (ADR-0003 Reopen) | Draft (archived) | A2 |
| evaluations/round1.5 | ラウンド1.5 横断評価メモ | — | — |

### ラウンド2: リンク端点とメンバーシップ (2026-09-13〜)

| ADR | タイトル | Status | Pass |
|-----|---------|--------|------|
| [0006](0006-endpoints.md) | L1 リンク端点表現 (`endpoints`) | **Accepted** | C |
| drafts/0007 | vNIC / vSwitch / bridges | Draft | A |
| [drafts/0008](drafts/0008-cloud-networks-scope-location.md) | クラウドネットワークの表現 (`parent` / `labels` / `location`) | Draft | C |
| [0009](0009-membership-orthogonality.md) | メンバーシップ構成子の直交性 (`attaches_to` / `parent` / `labels`) | **Accepted** | C 相当 |

**ADR-0009 の経緯**: 「箱への所属」の命名を 6 ラウンド × 5 エージェント並列で検討した。
20 語以上が既存ネットワーク用語・プロジェクト内用語と衝突して収束せず、最終的に
**難航の原因が語彙不足ではなく構造の誤り** (階層ネストと多軸分類を 1 構成子で表そうとしていた)
と判明し、2 構成子への分離で決着した。却下語の全リストは ADR-0009 の Alternatives Considered を参照。

### ラウンド3: 制御プレーンの分離 (2026-09-18〜2026-11-01)

| ADR | タイトル | Status | Pass |
|-----|---------|--------|------|
| [0010](0010-control-plane-separation.md) | control plane と data plane の分離 (`control_plane` / `routing_neighbors`) (2026-11-01 実装) | **Accepted** | C |
| [drafts/0010](drafts/0010-control-plane-separation.md) | 同上 Pass A ドラフト (r1〜r4) | Superseded by 0010 | A r4 |
| [evaluations/round3](evaluations/round3-evaluation.md) | ラウンド3 横断評価メモ (Pass B) と Pass C の結果 | — | — |
| [evaluations/adr0010](evaluations/adr0010/README.md) | ADR-0010 実証 YAML | — | — |

「BGP は Layer 的にどこに入るか」という問いから、`layer1/2/3` が OSI 層番号ではなく RFC 8345 のデータプレーン層であること、
BGP 隣接が `layer3.routing_adjacencies` と `protocols.bgp` に二重に書けて fixture が矛盾を含んだまま valid になっていることが判明した。
2026-09-20 に BGP エントリの単位 (D8) を決めないまま中断し、layer3 までを先に確定させた (ラウンド4)。
2026-11-01 に ndl-viz の表示 (1 組に最大 6 本の線) をきっかけに再開し、「線 1 本 = セッション 1 本」を推定なしで描ける形として、
VRF ごとの BGP インスタンス、1 エントリ 1 セッション、セッションの通り道は `update_source` から導く (ADR-0001 の `{link:}` キーは削除)、
underlay / overlay は構文に入れず AF と VRF から導く、に決めた。

### ラウンド4: layer3 データプレーンの確定 (2026-09-20〜2026-10-15)

| ADR | タイトル | Status | Pass |
|-----|---------|--------|------|
| [0011](0011-layer3-data-plane.md) | layer3 データプレーン | **Accepted** | C |
| [0012](0012-subinterfaces.md) | 802.1Q サブインターフェース | **Accepted** | C |
| [0013](0013-vlan-ports-on-lag.md) | VLAN のポート (trunk_ports / access_ports) | **Accepted** | C |
| [drafts/0011](drafts/0011-layer3-data-plane.md) | layer3 データプレーンの確定 | Superseded by 0011 | A r2 |
| [evaluations/adr0011](evaluations/adr0011/README.md) | ADR-0011 実測資料 (試し書き / 矛盾の実例 / 案比較) | — | — |
| [drafts/0012](drafts/0012-subinterfaces.md) | 802.1Q サブインターフェース | Superseded by 0012 | A |
| [evaluations/adr0012](evaluations/adr0012/README.md) | ADR-0012 設計比較 YAML | — | — |
| [drafts/0013](drafts/0013-vlan-ports-on-lag.md) | VLAN の trunk_ports / access_ports から LAG を指す | Superseded by 0013 | A |
| [evaluations/adr0013](evaluations/adr0013/README.md) | ADR-0013 設計比較 YAML | — | — |
| [evaluations/round4](evaluations/round4-evaluation.md) | ラウンド4 横断評価メモ (ADR-0011〜0013 の Pass B) | — | — |
| evaluations/round4/passc/ | Pass C の案比較 YAML (参照キー・`name`・`node`) | — | — |

ADR-0010 を保留した上で、先に L1〜L3 のデータプレーンを確定させる作業。
表現原理 (関係の成立に必要な情報は書き、個別経路は書かない)、スタティックルートのスコープ外化、
SVI 表現の一本化、`fhrp` → `gateway_redundancy`、デュアルスタック (`ip` / `ipv6`)、トンネルを扱う。
Pass C (2026-10-15) で、参照先の種類を `attaches_to` のキーで示す形 (ADR-0001 D8)、`L3Interface.name`、VLAN のポートとサブ IF に `node` を書かない形 (ADR-0005 D6)、表現の「指針」(ADR-0005 D4 補則) を決めた。旧形式は ndl_version 1.x の間だけ warning 付きで受け付ける。

### ラウンド5: VXLAN の表現 (2026-10-20〜)

| ADR | タイトル | Status | Pass |
|-----|---------|--------|------|
| [drafts/0014](drafts/0014-vteps.md) | VXLAN のトンネル端点 (VTEP) (実装済み) | Draft | A |
| [evaluations/adr0014](evaluations/adr0014/README.md) | ADR-0014 設計比較 YAML (1 回目の 4 案と、方式中立モデルの 7 構成) | — | — |
| [drafts/0015](drafts/0015-declarative-references.md) | 参照先をスキーマに宣言する (Ref) (実装済み) | Draft | A |
| [evaluations/declarative-refs](evaluations/declarative-refs/comparison.md) | ADR-0015 試し書き (構文を足す作業の比較) | — | — |

ADR-0011 の「書けないまま残るもの」を優先順に扱う。ADR-0014 で、構文は関係の形で決め、方式名は構文に入れない
という原則を ADR-0005 D4 補則に加えた。
ADR-0015 では、参照先をスキーマに `Ref` で宣言し、参照の存在の検査を汎用化した (ライブラリの実装方針)。
