# ADR-0004: `implementation` × `role` の妥当組み合わせ

- **Status**: Accepted
- **Date**: 2026-05-27
- **Deciders**: mlndl-spec-architect (Pass C), mlndl-dsl-designer, network-tech-reviewer
- **Pass**: C (再設計後の最終版)
- **Supersedes**: drafts/0004-implementation-role-matrix.md

## Context

mlndl は「ネットワークを記述する中間フォーマット」であり、CLAUDE.md の原則として「EVE-NG を知らない。ndl-viz も知らない。純粋な中間フォーマットライブラリ」と確定している。

`implementation` (`vm | physical | container`) と `role` (`spine | leaf | tor | core | ...`) は `L1Node` の独立したフィールドである。両者の妥当な組み合わせを mlndl コアがどこまで判定するかは、Pass A ドラフトの段階で以下の問題が露呈した:

1. **責務越境**: マトリクスの多くのセル (例: `core × container = ❌`) は「DC バックボーンはコンテナで実装しない」という**デプロイ運用上の慣行**に基づいており、mlndl コアが知るべき領域ではない
2. **時代遅れリスク**: SONiC-VS / SR Linux コンテナ / Containerlab の普及により、同セルは既に时代遅れになっている
3. **関心分離違反**: `allow_unusual_combination: bool` を `L1Node` ドメインモデルに置くのは、バリデーション制御フラグとドメイン記述の混在である
4. **`role` 語彙への過剰依存**: ADR-0003 で `role` が `Literal | str` のオープン語彙になるため、固定マトリクスは語彙変更に脆弱

### 根本問題

> マトリクスの目的が「デプロイ適合性の判定」なら、それは mlndl の責務か?

**No**。mlndl の責務は「記述が技術的に成立するか」の最小限チェックまでである。「その組み合わせが運用上ふつうか」は下流ツールが扱う。

### コア責務とプラグイン責務の境界

mlndl コアが**常に** error を出すのは：「**現行ネットワーク技術において実装として物理的・プロトコル仕様的に成立しない**」ケースのみ。

- 物理的不可能性の例: コンテナがハイパーバイザ機能 (ゲスト VM の任意実行) を提供する
- プロトコル仕様レベルの例: VxLAN 利用時の MTU 不足、eBGP ピアで同一 AS 番号 (これらは Phase 2 以降で実装)

「運用慣行から外れるが技術的には成立する」ケース (例: `spine × vm` が Production では非一般的など) は error にしない。ValidationPlugin (Phase 2 以降) に委ねる。

## Decision

### D-1. mlndl コアが行うのは「技術的不可能性チェック」のみ

`L1Node` の `implementation` と `role` を **独立した直交フィールド**として扱う。コアバリデーターが error を発するのは以下 1 件のみ:

| ケース | 根拠 | severity |
|------|------|---------|
| `implementation: container` × `role: hypervisor` | Type-1 / Type-2 ハイパーバイザはコンテナとして動作しない。コンテナ自体がゲスト VM を任意に並列実行するハイパーバイザ機能を提供することは現行技術で不可能 | **error** |

> **ADR-0003 (Pass C2) との接続**: `hypervisor` は ADR-0003 D3 の **normative token** として定義されている。ADR-0003 が `role` を open-form 化 (canonical 集合を informative へ降格) した後も、`hypervisor` という文字列リテラルへのチェックは本 ADR D-1 の規定として独立に維持される。D-1 の error 判定は `role == "hypervisor"` の文字列完全一致で実装し、canonical 集合への依存はない。`role: vmware-esxi` 等の別表記は本 D-1 の対象外 (意図された設計)。

**「技術的不可能性」の判断基準 (将来の error 追加への一貫した指針)**:

> `implementation X` として動作するソフトウェアが `role Y` の機能を提供することが、現行の技術標準または RFC 等の仕様レベルで**原理的に成立しない**場合のみ error とする。「稀」「推奨されない」「運用慣行から外れる」は error の根拠にならない。

これ以外の `implementation × role` の組み合わせはすべて受理する。

**境界事例のガイダンス** (ADR に含む):

- **KubeVirt / virt-launcher Pod**: Pod (コンテナ) がホストカーネルの KVM を介して VM を起動する。これはコンテナが VM のフロントエンドであり、コンテナ自体がハイパーバイザ機能を提供するわけではない。→ `implementation: vm` として記述する。
- **Kata Containers / gVisor**: 「コンテナ風 VM sandbox」。単一コンテナを VM 内で実行するランタイムであり、ゲスト VM を任意に並列起動するハイパーバイザではない。→ `container × hypervisor` には該当しない。
- **Firecracker MicroVM / Cloud Hypervisor**: コンテナランタイムから起動される軽量 VMM。ランタイムの実装であり、MLNDL での role は `hypervisor` ではなく `server` 等で表現する。

バリデーションエラーメッセージ例:
```
ValidationError: implementation=container と role=hypervisor の組み合わせは技術的に成立しません。
ヒント: KubeVirt の virt-launcher Pod や Kata Containers 環境は
        implementation=vm として記述してください。
```

### D-2. バリデーション severity の定義は ADR-0002 で行う

`error / warning / info` の 3 段階定義は、ADR-0001〜0004 すべてに横断する関心事であるため、**ADR-0002 (ID 命名規則) の D8** として定義する (ADR-0002 は最も基礎的な規則 ADR であり、他の ADR が参照する共通基盤に適している)。

本 ADR では上記 D-1 の 1 件が `error` であることを宣言するにとどめ、severity の詳細定義は ADR-0002 D8 に委ねる。`strict` モードの設計は Phase 2 以降で実施する。

### D-3. `allow_unusual_combination` フラグは採用しない

`L1Node.allow_unusual_combination: bool` は採用しない。理由:
- D-1 の縮小によりコアが warning/error を出す組み合わせがほぼ無くなるため、エスケープハッチ自体が不要
- ドメインモデルにバリデーション制御フラグを持ち込むのは関心分離違反 (dsl-designer Pass B 指摘)
- 外部プラグインが警告を出す場合、その抑止はプラグイン設定側で行う

### D-4. 運用慣行チェックは外部実装に委ねる (Phase 2 計画)

「core はコンテナより物理が一般的」のような慣行レベルの助言は、mlndl コアでなく利用層 (eve-lab-builder, ndl-viz, CI ポリシー) が自前で実装する。mlndl は **Phase 1 でプラグイン機構を公開しない**。

Phase 2 以降の計画:
- `ValidationPlugin` インターフェースの設計と公開 API 化
- 利用ツールが `plugins=` 引数で注入する形式
- 具体的なプラグインはそれぞれの利用ツールのリポジトリで管理する

配布方針: mlndl は公式の慣行チェックプラグインを配布しない。利用ツールが独自のルールセットを保持する (Terraform provider と HCL コアの関係に近い)。

### D-5. `tor` vs `leaf` の語彙整理は ADR-0003 の責務

`tor` ロールと `leaf` ロールの使い分け基準は ADR-0003 で扱う。本 ADR では両ロールを平等に受理し、語彙定義の責務は ADR-0003 に委ねる。

## Consequences

### 良い影響

- **「mlndl は EVE-NG を知らない」原則が ADR レベルで強化される**: デプロイ慣行は下流に押し出され、mlndl は純粋な中間フォーマットとして機能する
- **時間耐性**: SONiC-VS、SR Linux コンテナ、Containerlab 等の新技術普及でマトリクスが陳腐化するリスクがなくなる
- **`role` 語彙との疎結合**: ADR-0003 が `role` を `Literal | str` のオープン語彙にしても本 ADR の規定は壊れない
- **関心分離**: `L1Node` モデルにバリデーション制御フラグが入らず、pydantic モデルが純粋な記述子として保たれる
- **一貫した判断基準**: 「技術的不可能性のみ error」という明文化された基準により、将来の error 追加判断が一貫する

### 悪い影響 / 受容するトレードオフ

- **「無防備」に見える可能性**: `role: spine` + `implementation: container` を書いてもコアは通す。慣行違反検出は外部プラグイン責任。→ Phase 1 スコープ (L1 のみ・パーサ確立) では許容する
- **外部プラグイン機構は Phase 2 以降**: Phase 1 では慣行チェックのフックがない。eve-lab-builder は自前でデータを検証する必要がある
- **プロトコル仕様レベルの error は Phase 2 で実装**: VxLAN MTU 不足、eBGP AS 矛盾、VNI ユニーク性等は Phase 2 以降のバリデーター実装で対応する

### Phase 1 への影響範囲

- **スキーマ** (`schema/layer1.py`): `L1Node.implementation` と `L1Node.role` の field 定義はそのまま。`allow_unusual_combination` は追加しない
- **バリデーター** (`validator.py`): D-1 の 1 件 (`container × hypervisor → error`) のみ `model_validator(mode="after")` で実装する
- **エクスポーター**: 影響なし
- **サンプル** (`tests/fixtures/`): 既存サンプルに影響なし。`invalid_container_hypervisor.yaml` の fixture を追加する

### 段階 2 (ADR-0003 Reopen) との依存関係 — ラウンド1.5 影響評価より

ADR-0005 (2026-05-29 Accepted) を受けた影響評価 (B 判定) で以下を確認した:

- **シナリオ A/B (最有力)**: ADR-0003 段階2 で `hypervisor` が canonical roles に残る / open-form 語彙に移行する → D-1 の技術的不可能性ルールは維持。「canonical でなくても `role: hypervisor` という記述に対してルールは有効」と文言整理するだけで足りる
- **シナリオ C (低確率)**: `hypervisor` という概念が仕様から削除・禁止される → D-1 が空殻化し ADR-0004 は Supersedes 候補になる

**段階2 完了後の再確認事項**: `role: hypervisor` の扱い確定後に D-1 の文言と Appendix の `vswitch/dvswitch` 行を更新する。

### Phase 2 以降のバリデーター実装候補 (network-tech-reviewer 申し送り)

以下はプロトコル仕様レベルで成立しない組み合わせであり、Phase 2 でコアバリデーターの error として実装すること:

- VxLAN 利用時の underlay MTU < 1550 (実装したが、[ADR-0020](0020-remove-l1-link-mtu.md) で L1 リンクの `mtu` とあわせてなくした)
- MLAG ペアで `system-mac` 不一致
- eBGP ピアで同一 AS 番号 / iBGP ピアで異なる AS 番号
- VNI グローバルユニーク性違反
- VRF ↔ L3VNI バインディング欠如

これらは CLAUDE.md のバリデーション項目表にも記載されており、L2/L3 スキーマ実装時に対応する。

## Alternatives Considered

### Alternative A: Pass A の完全マトリクス維持

全組み合わせに `✅/⚠/❌` を割り当て、`allow_unusual_combination` でエスケープ。

- **却下理由**: 責務越境 (`mlndl は EVE-NG を知らない` 原則違反)、時代遅れリスク、`role` 語彙への過剰依存。Pass B で spec-architect・dsl-designer・network-tech-reviewer・ecosystem-reviewer の 4 エージェントが独立に同様の問題を指摘。

### Alternative B: マトリクスの一部 + プラグイン委譲

mlndl コアに「最小限のマトリクス」(hypervisor 関連数セル) を保持し、それ以外はプラグインへ。

- **却下理由**: 「最小限」の境界線が恣意的。本 ADR は D-1 の「container × hypervisor」1 件に絞ることで、議論可能な水準まで縮小した。

### Alternative C: マトリクス全廃 (D-1 も削除)

いかなる組み合わせも受理する。

- **却下理由**: 「コンテナがハイパーバイザ機能を提供する」のような物理的に成立しない記述を通すのは品質を下げる。1 件のみ残すのは「技術的整合性の最低ライン」として正当化できる。

### Alternative D: マトリクスを YAML 外部設定化

`mlndl/config/role_implementation_matrix.yaml` に外出しし、ユーザーがカスタマイズ可能に。

- **却下理由**: mlndl がマトリクスの仕様 (フォーマット、拡張方法) を背負う。D-4 (外部プラグイン) の方が責務分離が明快。

## Appendix: 参考マトリクス (informative — 非規範的)

> ⚠️ **このマトリクスは informative です。mlndl コアのバリデーターはこの表を参照しません。**
> 現代 DC 技術の進化 (SONiC コンテナ、SR Linux、Containerlab 等) により記述内容は変化します。
> Production 利用の判断は利用ツールまたはネットワーク設計者が行ってください。

| role | physical | vm | container |
|------|---------|----|-----------| 
| `spine` | 標準的 | ラボ・テスト用途で一般的 | Containerlab で一般的 |
| `leaf` | 標準的 | ラボ・テスト用途で一般的 | Containerlab で一般的 |
| `tor` | 標準的 | ラボ可 | ラボ可 |
| `core` | 標準的 | ラボ可 | ラボ・Production 共に実例あり (SONiC, SR Linux container) |
| `border` | 標準的 | 標準的 (VNF: CSR1000v, vMX, vEOS-router) | ラボ可 |
| `server` | 標準的 | 標準的 | 標準的 |
| `hypervisor` | 標準的 | ネステッド仮想化 (稀) | **コア error** (現行技術では技術的に成立しない) |
| `router` | 標準的 | 標準的 (VNF) | ラボ可 |
| `firewall` | 標準的 | 標準的 (VNF) | ラボ可 |
| `load-balancer` | 標準的 (F5, A10) | 標準的 (VNF) | 標準的 (NGINX, HAProxy) |

*注: ADR-0003 (Pass C2) により `role` は open-form (自由文字列) になった。このマトリクスは `CANONICAL_ROLES` の推奨語彙を列挙する informative 参考表であり、mlndl コアはこの表を参照しない。`vswitch`/`dvswitch` は ADR-0003 (Pass C2) により L1 canonical roles に含まれない (Phase 2 L2 スキーマで扱う) ため、このマトリクスから削除した。*

## Pass A との差分

| 項目 | Pass A | Pass C |
|------|--------|--------|
| マトリクスの範囲 | 全 `implementation × role` セルに `✅/⚠/❌` | 1 件 (`container × hypervisor = error`) のみ |
| mlndl 内への配置 | コアバリデーター内 | 1 件のみコア。慣行チェックは外部プラグイン (Phase 2) |
| `core × container` | `❌` | **受理** (SONiC / Containerlab は Production・ラボ双方で一般的) |
| `allow_unusual_combination` | `L1Node` に追加 | **廃止** (関心分離違反・不要化) |
| severity 定義 | ADR-0004 内で定義 | **ADR-0002 D8 に分離** |
| `strict` モード | Phase 1 で実装 | **Phase 2 以降** (Phase 1 では warning が出るルールがないため) |
| ADR の normativity | マトリクス全体が normative | Appendix は **informative** |
| `role` 語彙への依存 | 全語彙に依存 | `hypervisor` のみ参照 |

**独立に同じ結論に到達した点** (Pass A との一致):
- `allow_unusual_combination` をドメインモデルに置かない方向性 (dsl-designer も独立に同様指摘)
- lenient/strict のハイブリッドアプローチ (ただし Phase 1 では strict を実装しない点が変更)

**Pass A から大きく逸脱した点**:
- 「マトリクスを mlndl コアから外す」構造変更。Pass A は「マトリクスを残してエスケープハッチをつける」設計だったが、Pass C は「マトリクスそのものを mlndl の責務から外す」。round1-evaluation の「責務越境」指摘 (4 エージェント共通) を最重要視した結果。

## ADR-0005 との関係

ADR-0005「mlndl の表現スコープ定義」(Pass C, 2026-05-29) との影響評価結果: **B (最小修正)**。

- 本 ADR D-1 の「技術的不可能性のみ error」方針は ADR-0005 D1/D3 の三側面スコープ設計と整合する
- 本 ADR D-4 の「慣行チェックは外部プラグイン」方針は ADR-0005 D3-2 の「スコープ外の行き先」設計と整合する
- Pass A との差分表の `severity 定義` 行が「ADR-0005 に分離」と誤記されていたため「ADR-0002 D8 に分離」に修正済み
- 段階2 (ADR-0003 Reopen) の結果次第で D-1 文言と Appendix `vswitch/dvswitch` 行の調整が必要 (上記 Consequences 参照)

## References

- `CLAUDE.md` — 「mlndl は EVE-NG を知らない」原則、`implementation` 値定義、バリデーション項目表
- `docs/decisions/evaluations/round1-evaluation.md` — Pass B 横断評価 (全 5 エージェント)
- ADR-0005 (Pass C) — mlndl の三側面スコープ定義。影響評価: B 判定
- ADR-0003 — `role` 語彙 (`tor`/`vswitch`/`dvswitch` 等の去就)。段階2 Reopen により本 ADR の再確認が必要
- ADR-0002 D8 — バリデーション severity 階層 (`error / warning / info` の統一定義)
- RFC 8345 — Supporting 関係の概念
