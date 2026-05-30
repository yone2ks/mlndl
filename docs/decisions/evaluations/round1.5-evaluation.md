# ラウンド1.5 横断評価メモ

- **作成**: mlndl-spec-architect (critical evaluator モード)
- **日付**: 2026-05-29
- **評価対象**: `drafts/0005-mlndl-expressive-scope.md` (Pass A ドラフト)
- **レビュアー**: mlndl-linguist / mlndl-dsl-designer / network-tech-reviewer / ecosystem-reviewer

---

## 章構成

- [段階1: ADR-0005 スコープ定義 の Pass B 評価](#段階1-pass-b-評価)
- [既存 ADR 影響評価](#既存-adr-影響評価) ← ADR-0005 Accepted 後に追記
- [段階2: ADR-0003 再設計 の Pass B 評価](#段階2-pass-b-評価) ← 段階2 完了後に追記

---

## 段階1 Pass B 評価

### 1. アンカー検出

| アンカー候補 | 評価 |
|------------|------|
| CLAUDE.md「EVE-NG を知らない」原則 | **妥当なアンカー** — D3-2 の「含めない」リストの根拠として機能しており、出発点として適切 |
| RFC 8345 supporting model | **妥当なアンカー** — 原案の三層モデル継承の媒体として適切。エクスポーター設計を拘束するがそれが目的 |
| ADR-0001 の `attaches_to` 単一手段方針 | **妥当なアンカー** — D2-4 で再引用。ただし「`{interface: X}` の X が指せる層」を ADR-0001 本文に追記する波及が必要 |
| Phase 1 = L1 のみ実装 | **妥当なアンカー** — D5 に明示済み。スコープ「含む」と「Phase 1 実装」の混同だけ要注意 |

### 2. Pass C で意識すべき指摘 (優先順)

#### ★ 高優先 (Pass C のドラフトに直接影響)

**P1: D3-1 列ヘッダの時制矛盾 (linguist)**
- 問題: 「含む (Phase 1 + Phase 2)」は Phase 2 未実装のものを「含む」と書く時制矛盾
- 修正案: 「スコープ内 (将来 Phase を含む)」と「Phase 1 実装」の 2 列または 1 列＋注記に変更
- ADR-0005 D5 で三軸と Phase の対応表を持っているので、D3-1 との二重管理を避けるよう整理する

**P2: D1「(c) は純粋な軸ではなく操作的分類」を明記 (dsl-designer)**
- 問題: (c) 物理-論理連携は (a)(b) の間の**関係**であり、独立した軸ではない。ADR-0005 自身が port_channel/MLAG は (a)(b) 境界をまたぐと認めており内部矛盾
- 修正案: D1 冒頭に「(c) は (a)(b) を結ぶ関係軸であり、厳密な MECE 分類ではなく `attaches_to` を独立概念として語るための操作的分類である」と明記

**P3: SVI の二段表現規則が未定義 (network-tech)**
- 問題: D2-2 では「routed 物理 IF」の L1+L3 二段表現を規定しているが、SVI (`interface vlan-100` に IP を設定する場合) の表現規則がない
- D3-1 (b) `layer3.interfaces` の note に「SVI は `interface: vlan-100` と書き、`layer2.vlans[id=vlan-100]` を暗黙参照とする (explicit `attaches_to` は Optional)」等の規則を追記

**P4: 「アグリゲーション primitive」→「リンクアグリゲーション (LAG)」(linguist 高優先)**
- 問題: 「アグリゲーション primitive」は和英混在かつ DSL 文脈での `primitive` が別意を連想
- 修正案: D1 の port_channel / mlag 分類語を「リンクアグリゲーション (LAG) primitive」→「**リンクアグリゲーション (LAG)**」に変更

#### ★ 中優先 (内容の精度向上)

**P5: `address_families` の値域未確定 (network-tech)**
- D3-1 で BGP `address_families` を含む旨を記述しているが、許容値 (`ipv4_unicast | ipv6_unicast | l2vpn_evpn | vpnv4 | vpnv6`) が明示されていない
- 修正案: D3-1 (b) BGP 記述に `address_families: [ipv4_unicast | ipv6_unicast | l2vpn_evpn | vpnv4 | vpnv6]` の値域を追記

**P6: BGP unnumbered での `remote-as external/internal` 対応 (network-tech)**
- 問題: BGP unnumbered では remote-as を ASN ではなく `external`/`internal` キーワードで指定する (Cumulus FRR / FRRouting の慣習)
- 修正案: D3-1 の BGP unnumbered 節に「`remote_as: <ASN> | external | internal`」と値域を拡張明記

**P7: EVPN advertise フラグ群の扱い (network-tech)**
- 問題: `advertise-default-gw` / `advertise-pip` は MLAG + Symmetric IRB で事実上必須。「Phase 2 で再判断」のまま確定すると「MLAG+EVPN を書けるが実機で動かない」構成を生む
- 修正案: Consequences に「**EVPN advertise フラグ群 (`advertise-default-gw` / `advertise-pip` 等) は Phase 2 で D3-1「含む」側に確定することを想定**する。Phase 2 着手時に最初に判断すべき項目」と明記

**P8: tunnel_interfaces と tunnel_links の対称性注釈 (dsl-designer)**
- 問題: D3-1 (b) に `tunnel_interfaces` (entity) と `tunnel_links` (関係) が並ぶが、関係性の説明が欠落
- 修正案: 「`tunnel_interfaces` は L3Interface の一種 (entity)、`tunnel_links` は L1Link と同型の両端関係 (relation)。両者が揃って一本のトンネルを表現する」と注釈追記

**P9: NetBox Interface type 振り分けマトリクス (ecosystem)**
- 問題: D3-1 に NetBox の Interface type (`virtual`, `lag`, `bridge` 等) → mlndl 層の振り分けルールがない。アダプター実装時に判断が分散する
- 修正案: D3-1 末尾に補足表:
  ```
  | NetBox type        | mlndl 層                   |
  |--------------------|---------------------------|
  | 1000base-t / 10gbase-x 等 | layer1.interfaces     |
  | lag               | layer1.port_channels        |
  | virtual (parent あり) | layer2.subinterfaces     |
  | virtual (parent なし・IP あり) | layer3.interfaces   |
  | bridge            | Phase 2 で再判断             |
  ```

**P10: 「三軸」→「三側面」の検討 (linguist)**
- 問題: 「軸」は数学的な直交概念を連想させ、(a)(b)(c) が独立でないことと矛盾
- 修正案: 「**三側面**」を推奨。「三観点」も可。「三層」は L1/L2/L3 と衝突のため不可
- Pass C 担当者への判断委任 (「三軸」のまま「操作的分類」と注記する選択肢もある)

#### ★ 低優先 (申し送り・Phase 2 課題)

**P11: `meta.site/rack` を Phase 1 optional 許可の検討 (ecosystem)**
- 問題: NetBox → mlndl 変換時に物理配置情報が失われると、ndl-viz の拠点別グループ化が不可
- 修正案: D3-1 Phase 1 に `nodes[].meta: {site: str, rack: str}` を optional で追加検討
- Pass C 判断: 採用するか Phase 2 申し送りとするかを spec-architect が決定

**P12: MLAG system-mac の「上位ツール導出」は実装困難 (network-tech)**
- 問題: ベンダー間で system-mac の derivation rule が統一されていない (Arista/Cumulus/NX-OS で異なる)
- Consequences に「Phase 2 で anycast_mac / MLAG system-mac は「L3/MLAG スキーマに例外保持」がほぼ確定の方向」と明記推奨

**P13: 新規グレー領域 3 件 (network-tech)**
- Breakout port (100G→4x25G): L1 物理表現に parent 子関係が必要。Phase 2 議題
- EVPN Ethernet Segment (ESI/ES-LAG): MLAG 代替の EVPN A-A multihoming。Phase 2 議題
- Loopback 意図タグ: BGP RID 専用 vs VTEP source 専用の区別。validator で意図ずれ検出の要否

**P14: OpenConfig 往復変換の非対称性の明記 (ecosystem)**
- mlndl → OpenConfig は「片方向エクスポート」として割り切る前提を Consequences に明記推奨
- Phase 2 直後に PoC を試作して変換複雑度を実測する申し送り (ラウンド1.5 プランに既記載)

**P15: D4 見出し語・本文表現の軽微修正 (linguist)**
- 「判定枠組」→「判定フレームワーク」(中)
- 「段階 2 を縛らない範囲」→「段階 2 の結論に依存せず確定できる範囲」(中)
- D3-1 列ヘッダと合わせて Pass C で統一

### 3. 横断矛盾の検出

| 矛盾候補 | 評価 |
|---------|------|
| ADR-0001 D2 で廃止した `{layer: layer1, interface: X}` の復活リスク | **問題なし** — D2-3 で「層を明示しない」と再確認済み |
| D3-1 に `address_families: [l2vpn_evpn]` を含むのに `advertise-default-gw` を D3-2 に置く | **矛盾あり** — EVPN `address_families` を「含む」としながら EVPN 動作の必須フラグを「含めない」では実用上破綻。Consequences で Phase 2 確定を予告して緩和 |
| BFD timer を「唯一の例外」とする一方、BGP/OSPF timer は「上位ツール」へ | **整合** — BFD は隣接の存在条件 (timer が隣接形成の可否を決める) であり、BGP/OSPF timer は隣接確立後のチューニング。区別は妥当 |
| D2-2「routed 物理 IF の二段表現」vs D3-1 が `layer3.interfaces` を単一リストで記述 | **潜在矛盾** — SVI の二段表現規則 (P3) が未定義なので統一規範が不完全。Pass C で解消 |

### 4. 「アンカー」として警戒すべき点 (Pass C への引き継ぎ)

1. **「三軸」という命名がユーザー発話の引用** — ユーザーが「物理構成図・論理構成図・物理と論理の間の連携」と発話した三区分を、spec-architect が Pass A でそのまま (a)(b)(c) の「軸」と命名した。これは適切な継承だが、「三軸」の MECE 性への過剰な主張がアンカーになりうる。Pass C では「三側面」や「操作的分類」という柔軟な表現を検討する
2. **RFC 8345 supporting model の優先** — D2-1 で OpenConfig のネストを「採用しない」と明言した。これは意図的な差別化だが、今後 OpenConfig アダプターを実装する際の障壁になる。Pass C でも維持するが、「OpenConfig → mlndl は片方向エクスポート」という制限を Consequences に明記すべき

### 5. Pass C への Input サマリ

**Pass C で spec-architect が参照するもの**:
- 本評価メモのみ (drafts/0005 は参照禁止)
- CLAUDE.md、ADR-0001/0002/0003/0004 (Accepted 版)

**Pass C で確定すべき主要論点**:
1. 「三軸」vs「三側面」の呼称
2. (c) の独立軸性 vs 操作的分類の扱い
3. D3-1 の含む/スコープ内の時制整理 (D5 との二重管理解消)
4. SVI 二段表現規則の明示
5. EVPN advertise フラグ群の Phase 2 確定予告の明記方法
6. NetBox Interface type 振り分けマトリクスの採否
7. `meta.site/rack` の Phase 1 追加 vs Phase 2 申し送り

**独立に同じ結論に到達した点 (Pass A の正当性が高い箇所)**:
- 「MAC アドレスは原則扱わない」— linguist/dsl/nw-tech/ecosystem の全員が直接異議なし
- `attaches_to` 単一手段方針 — DSL designer・ecosystem の両名が整合と判定
- RFC 8345 supporting model への準拠方針 — ecosystem が RFC 8345 と ◎ と評価
- BFD timer を例外として保持 — network-tech が構造的正当性を確認

---

## 既存 ADR 影響評価

- **実施**: mlndl-spec-architect (critical evaluator モード)
- **実施日**: 2026-05-29
- **評価対象**: ADR-0001 / ADR-0002 / ADR-0004 (Accepted 版) — ADR-0005 (Accepted, Pass C) との整合確認
- **判定基準**: A (整合) / B (最小修正) / C (Supersedes 候補)

---

### 判定サマリ

| ADR | タイトル | 判定 | 要対応 |
|-----|---------|------|--------|
| ADR-0001 | `attaches_to` の使い分け基準 | **B (最小修正)** | `{interface: X}` の X が指せる層の詳細を ADR-0005 D2-3 へ委譲する注記 + References 追加 |
| ADR-0002 | ID 命名規則 | **B (最小修正)** | D7 に Phase 2 用推奨プレフィックス追加 + Pass A 差分表の誤記修正 + References 追加 |
| ADR-0004 | `implementation × role` の妥当組み合わせ | **B (最小修正、段階2 結果次第で C 候補)** | Consequences に段階2 の影響可能性を明記 + Pass A 差分表の誤記修正 + References 追加 |

---

### ADR-0001 詳細 — 判定: B (最小修正)

#### 整合性確認

| ADR-0001 の記述 | ADR-0005 との関係 | 判定 |
|----------------|------------------|------|
| D1: `attaches_to` 単一フィールドで supporting 関係を表現 | ADR-0005 D2-4 が「単一手段方針」を再確認 | ✅ 完全整合 |
| D2: タグ付き Union (`{node:}` / `{interface:}` / `{link:}`) | ADR-0005 D2-3 の表でそれぞれの用途が明確化 | ✅ 完全整合 |
| D3: 文字列糖衣はノード参照のみ | ADR-0005 D3-1 での Phase 1 実装記述と整合 | ✅ 完全整合 |
| D5: レイヤー方向制約 (同層・下位層への attach = 許容) | ADR-0005 D2-3 の SVI: L3 IF → L2 VLAN (上位→下位方向=supporting の正方向) と整合 | ✅ 矛盾なし |

#### 不足している記述

**問題**: ADR-0001 D2 では `attaches_to: {interface: X}` を定義しているが、X が指せる層を網羅的に記述していない。ADR-0005 D2-3 がこの詳細を新規規定したが、ADR-0001 から ADR-0005 への参照がない。

**追記対象**: ADR-0001 に「ADR-0005 との関係」セクションを新設し以下を記載:
- `{interface: X}` の X が指せる層の詳細は ADR-0005 D2-3 を参照
- L1 物理 IF (`leaf1-swp51`) / L2 VLAN SVI 経由 (`vlan-100`) / L2 サブインターフェース Phase 2 (`leaf1-swp1-100`)
- References に ADR-0005 追加

**リスク評価**: なし (既存の decision 内容は変更しない純粋な参照追加)

---

### ADR-0002 詳細 — 判定: B (最小修正)

#### 整合性確認

| ADR-0002 の記述 | ADR-0005 との関係 | 判定 |
|----------------|------------------|------|
| D1: 正規表現 `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` | ADR-0005 の新エンティティ ID (例: `leaf1-vlan-100`, `vni-10100`) も全て準拠 | ✅ 完全整合 |
| D5: グローバル一意性 | ADR-0005 D2-3 で「layer フィールドなしで層が一意に決定する (ADR-0001 D2)」と再確認 | ✅ 完全整合 |
| D7: 推奨プレフィックス | ADR-0005 で新しく登場した `tunnel_interfaces` / `tunnel_links` / `subinterfaces` / IS-IS 隣接 のプレフィックスが未定義 | ⚠️ 要補完 |

#### 不足している記述

**問題 1: D7 に Phase 2 用プレフィックスが未追加**

ADR-0005 D3-1 でスコープ内 (Phase 2 以降) として新規追加した概念のうち、推奨プレフィックスが未定義のもの:
- `tunnel_interfaces`: `tunnel-` (例: `tunnel-leaf1-gre0`)
- `layer2.subinterfaces`: `subif-` (例: `subif-leaf1-swp1-100`)
- IS-IS 隣接: `isis-adj-` (ADR-0002 D7 には `ospf-adj-` はあるが `isis-adj-` がない)

**問題 2: Pass A との差分表に誤記**

ADR-0004 の「Pass A との差分」表に `severity 定義 | ADR-0004 内で定義 | **ADR-0005 に分離**` という誤記がある (正しくは `ADR-0002 に分離`)。この誤記は ADR-0004 の Pass A との差分表に存在するが、根本的には ADR-0002 が参照されるべきであることを ADR-0002 の「ADR-0005 との関係」節で補足することで混乱を防ぐ。

**追記対象**: ADR-0002 D7 に Phase 2 用推奨プレフィックス行を追加、「ADR-0005 との関係」セクション新設、References に ADR-0005 追加

**リスク評価**: 低 (D7 は「規範ではなく規約」であり、追加は後方互換)

---

### ADR-0004 詳細 — 判定: B (最小修正)、ただし段階 2 次第で C 候補

#### 整合性確認

| ADR-0004 の記述 | ADR-0005 との関係 | 判定 |
|----------------|------------------|------|
| D-1: `container × hypervisor = error` (唯一のコアルール) | ADR-0005 D3-1 では `role: hypervisor` が Phase 1 の L1 nodes に存在。技術的不可能性 (コンテナはゲスト VM を任意並列起動するハイパーバイザ機能を提供できない) は ADR-0005 とは独立した技術事実であり変わらない | ✅ 整合。ただし条件付き |
| D-3: `allow_unusual_combination` 廃止 | ADR-0005 D2 / D4 の「注釈 vs 構成要素」方針と整合 | ✅ 完全整合 |
| D-4: 慣行チェックは外部プラグインへ | ADR-0005 D3-2 (スコープ外の「行き先」明示) と整合 | ✅ 完全整合 |
| Appendix: `vswitch / dvswitch` の行 | CLAUDE.md §7 および ADR-0003 で vswitch/dvswitch は L1 非canonical と確定。Appendix 自体は informative であり既存注記 (*注: ADR-0003 の結論に従って更新*) がある | ⚠️ 段階 2 後に更新が必要 |
| Pass A との差分表: `severity 定義 | ADR-0004 内 | ADR-0005 に分離` | **誤記**: ADR-0002 D8 が severity を定義しており、ADR-0005 ではない | ❌ 誤記 → 修正必要 |

#### 段階 2 との依存関係

**シナリオ A**: ADR-0003 段階 2 で `hypervisor` が canonical roles に残る → ADR-0004 D-1 は完全にそのまま有効。判定 B で完結。

**シナリオ B**: ADR-0003 段階 2 で `hypervisor` が canonical roles から除外されるが `role: hypervisor` という文字列記述自体は禁止されない (open-form 化) → ADR-0004 D-1 の error ルールは技術的に依然有効。「canonical でなくても技術的不可能性の原則は維持」と文言整理するだけで足りる。判定 B で完結。

**シナリオ C**: ADR-0003 段階 2 で `hypervisor` という概念が仕様から削除・禁止される → ADR-0004 D-1 が空殻化し、ADR-0004 全体が有効な error 規定を持たなくなる → **C (Supersedes) 候補**。

**現段階判断**: シナリオ C は最も非現実的 (「hypervisor という概念が存在しない」は技術的にあり得ない)。シナリオ A または B で確定する確率が高いため、現段階では **B 判定**。段階 2 完了後に再確認する申し送りを記録。

#### 追記対象

1. Consequences に「段階2 依存の注記」を追加
2. Pass A との差分表の誤記 (`ADR-0005 に分離` → `ADR-0002 に分離`) を修正
3. References に ADR-0005 追加

---

### 横断矛盾の最終確認

ADR-0001〜0004 間の矛盾で ADR-0005 に起因するものはないことを確認:

| 確認項目 | 結果 |
|---------|------|
| ADR-0001 D5 (下位層 attach = 許容) と ADR-0005 D2-3 (L3 IF → L2 VLAN) | ✅ 矛盾なし (L3→L2 は supporting の正方向) |
| ADR-0002 D5 (グローバル一意) と ADR-0005 D3-1 (`leaf1-vlan-100` 等の新 ID) | ✅ 矛盾なし (新 ID はすべて正規表現に準拠) |
| ADR-0004 D-1 (`container × hypervisor`) と ADR-0005 D1 (三側面) | ✅ 矛盾なし (技術的不可能性はスコープ定義と直交) |
| ADR-0003 (9 canonical roles) と ADR-0005 D3 (`role` 語彙への適用は段階2 以降) | ✅ 意図的な保留。矛盾ではなく未確定 |

---

### 後続アクション

**B 判定 ADR への修正 (本セクション完了後に即時実施)**:

| 対象 | 修正内容 |
|------|---------|
| ADR-0001 | 「ADR-0005 との関係」セクション追加 + References 更新 |
| ADR-0002 | D7 に Phase 2 プレフィックス追加 + 「ADR-0005 との関係」セクション追加 + References 更新 |
| ADR-0004 | Consequences に段階2 依存注記追加 + Pass A 差分表の誤記修正 + 「ADR-0005 との関係」セクション追加 + References 更新 |

**段階 2 完了後の再確認**:
- ADR-0004: `role: hypervisor` の去就確定後に D-1 文言を必要に応じて調整
- ADR-0004 Appendix: `vswitch / dvswitch` 行を ADR-0003 段階2 結論に合わせて更新

---

## 段階2 Pass B2 評価

- **実施**: mlndl-spec-architect (critical evaluator モード)
- **実施日**: 2026-05-29
- **評価対象**: `drafts/0003v2-role-vocabulary.md` (Pass A2 ドラフト)
- **レビュアー**: mlndl-linguist (L) / mlndl-dsl-designer (D) / network-tech-reviewer (N) / ecosystem-reviewer (E) / mlndl-example-author (YEx) — 5 並列

---

### 1. アンカー検出

| アンカー候補 | 評価 |
|------------|------|
| ADR-0005 D4 (4軸 Yes/No) が `role` 全体に「4軸全 No = 注釈側」と判定した | **適切な根拠** — 5 レビュアー全員が D4 適用の論理を妥当と評価 |
| δ案採用という Pass A2 の Decision | **事前収束への警戒** — 5案等価評価が実質的に δ 方向でまとまっているが、α (現状維持) のメリット列挙が義務的に行われており Pass C の独立再設計を妨げない |
| `container × hypervisor = error` の維持 (ADR-0004 継承) | **正当なアンカー** — ただし N3・D2 で「文字列照合という実装に落とし穴がある」という構造的指摘が出た。Pass C で补強必須 |

---

### 2. Pass C で意識すべき指摘 (優先順)

#### ★ 高優先 (Pass C のドラフトに直接影響)

**N3: `hypervisor` の normative token 化が未規定 (network-tech — 最重要)**
- 問題: δ 採用後 `role` の canonical 集合が informative 化されるため、ADR-0004 D-1 の `container × hypervisor = error` ルールが文字列リテラル照合になる。`role: hypervisor` のみ valid で `role: vmware-esxi` / `role: kvm-host` では error が silently bypass される
- 修正案: 「ADR-0004 が参照する語彙 (現行 `hypervisor` 1 語) は **normative tokens** として ADR-0003v2 が保持し、厳密一致でチェックする。canonical 集合を informative 化しても normative tokens は例外保持する」と Decision に明示
- 重要度: **クリティカル** — 実装段階で発見すると修正コストが跳ね上がる危険な未定義動作

**N2: `layer1.nodes.role` の変更範囲が不明 (network-tech)**
- 問題: ADR-0003v2 の対象範囲が `layer1.nodes.role` のみか全 `role` フィールドか不明。CLAUDE.md YAML サンプルには `bgp.nodes[].role: route_reflector`、`link_role: underlay` 等の `role` フィールドが複数存在する
- 修正案: Decision セクションに「本 ADR の対象は `layer1.nodes.role` のみ。`bgp.nodes[].role`、`layer1.links[].link_role`、`gateway_redundancy.protocol` 等の他 `role` フィールドは本 ADR の対象外であり、各 ADR が独立に意味論的契約を維持する」と境界を明記

**D1: `CANONICAL_ROLES` 定数の扱いを両論併記で Pass C に委ねるのは不十分 (dsl-designer)**
- 問題: Consequences の「削除または informative 定数として残置」が Pass C への先送りになっている
- 修正案: **informative 定数として `src/mlndl/constants.py` に残置する**方針を Pass C で確定。ndl-viz が `from mlndl import CANONICAL_ROLES` で import できる API を維持する。理由: 消費側が独自にハードコードすることで "mlndl の推奨語彙の単一情報源" が失われる

**D2: `container × hypervisor = error` の実装方法が未記述 (dsl-designer)**
- 問題: 「文字列照合として独立に維持」とあるが pydantic 実装レベルの記述がない
- 修正案: Pass C で以下の擬似コードを Decision に追加:
  ```python
  @model_validator(mode="after")
  def _reject_container_hypervisor(self):
      if self.implementation == "container" and self.role == "hypervisor":
          raise ValueError("...")
      return self
  ```
  これにより「canonical 集合への依存ゼロでリテラル照合が成立する」ことが実装上で証明される

**YEx-H3: δ 採用後の「推奨値準拠の動機」が不在 (example-author)**
- 問題: docs/role-vocabulary.md の推奨値を守る動機がユーザーにない。`role: ngfw` / `role: firewall` で迷った試し書き体験として確認済み
- 修正案: Consequences に「docs/role-vocabulary.md の推奨値は ndl-viz 既定スタイル適用の前提条件。推奨値以外の `role` 値では ndl-viz はフォールバックスタイル (グレーノード) を使用する」を明記。これで書き手の動機が回復する

**E3: D4 適用表の 4 軸目「フィルタ用途は除く」が曖昧 (ecosystem)**
- 問題: 「broadcast_domain / blast_radius 検索結果に影響するか: No (フィルタ用途は除く)」は「フィルタ用途は結果に影響する」と矛盾するように読める
- 修正案: 「No — 検索結果の**範囲**は変わらない。`role` はフィルタリング用のメタデータであり、broadcast_domain の形成要素ではない。クエリの絞り込み条件として使われる場合も、絞り込みが変わるのはフィルタ条件 (= クエリ側の意図) であって、トポロジーの意味境界ではない」と書き直す

**L1: 「注釈 (annotation)」用語が ADR-0005 D4 と微妙にずれる (linguist)**
- 問題: ADR-0005 D4 の表では「注釈 (スコープ外候補)」と書かれているが、本 ADR は「`role` はスコープ内に残しつつ意味論的契約のないラベル」を「注釈側構成子」と呼んでいる。読者が混同する
- 修正案: 初出で「**注釈側構成子** — ADR-0005 D4 の分類で 4 軸全 No と判定された構成子。スコープ外ではないが、mlndl コアが意味論的契約 (canonical 集合・warning) を持つべきでないカテゴリ」と定義節を設ける

#### ★ 中優先 (内容の精度向上)

**N5: ValidationPlugin が `role` を使う可能性を Consequences に予告 (network-tech)**
- MLAG+EVPN ベストプラクティス linter (Phase 3+ ValidationPlugin) は「`role: spine` なのに VTEP source を持つ」等を検出するために `role` 値を入力として使いうる
- 修正案: Consequences に「canonical 9 語彙は 『mlndl コアは契約しないが、ValidationPlugin (Phase 3+) の契約点として保全する』 — informative 定数残置 (D1) の理由でもある」と明記

**N4: β 案の評価が DC Clos に偏っている (network-tech)**
- β の位置軸 4 値は SP コア (`pe`/`p`/`asbr`/`rr`) やエンタープライズ 3-Tier (`access`/`distribution`/`core`) では不足する
- 修正案: β のデメリットに「SP/Enterprise 3-Tier では位置軸が 5〜7 値に膨らむ → α の語彙膨張問題を縮小再現するだけ」を追記

**D3: δ 採用後も `hypervisor` 1 語が事実上 reserved word になる (dsl-designer)**
- 問題: 「mlndl は語彙を持たない」という δ の表向きの主張と、`hypervisor` への文字列照合という実装上の現実に齟齬
- 修正案: Consequences に「ADR-0004 D-1 が参照する `hypervisor` は mlndl コアが事実上の reserved word として保持する。canonical 集合 informative 化後の唯一の例外語彙」と明記

**L3: 「成長戦略」という経営語彙の違和感 (linguist)**
- 「語彙拡張責務 (vocabulary extension responsibility)」「語彙進化方針 (vocabulary evolution policy)」に統一推奨

**E1: NetBox アダプターガイドラインが Consequences に未記述 (ecosystem)**
- δ 採用後の NetBox DeviceRole slug → mlndl role 変換で「推奨変換表」が必要
- 修正案: docs/role-vocabulary.md に NetBox slug 慣用値との対応表 (例: `top-of-rack` → `leaf`) を追加することを Consequences に予告

**L5: `role: str | None` の表記揺れ (linguist)**
- `role: str` と `role: str | None` が混在。全箇所で `role: str | None = None` に統一

#### ★ 低優先 (申し送り・Phase 2 課題)

**D6: 将来 `labels` 導入時の `role` との二重表現問題 (dsl-designer)**
- 「将来 `labels` 導入時は `role` フィールドを Supersede 対象とする」を申し送りとして明記

**N6: BGP AS 整合性チェックは `role` 依存しない方針の明記 (network-tech)**
- Phase 2 の AS 矛盾検出は `bgp.nodes[].local_as` の直接比較で行い、`role` 値に依存しないことを Consequences に明記

**YEx-H1: ε 案は Phase 1 で採用不可 (example-author)**
- 試し書きで確認: `firewall1` 1 件書くだけで「topology_role vs function_role vs host_type」の判断コストが発生し Phase 1 での採用は不適切

---

### 3. 横断矛盾の検出

| 矛盾候補 | 評価 |
|---------|------|
| δ「mlndl は語彙を持たない」vs ADR-0004 D-1「`hypervisor` を error 条件にする」 | **矛盾あり (N3)** — `hypervisor` を normative token として明示例外化することで解消可能 |
| δ「注釈側構成子に意味論的契約を持たない」vs「NDL-viz スタイルに canonical 9 値が必要」 | **矛盾ではなく責務分離** — mlndl は契約しないが docs 推奨値は informative に存在する。YEx-H3 の「推奨値準拠の動機」を明記すれば整合 |
| δ「canonical 集合 informative」vs ADR-0003 D5「`load-balancer` ハイフン正規形」 | **軽微な矛盾** — D5 は informative ドキュメント (`docs/role-vocabulary.md`) に降格するが、ADR 本文では「降格」と明示すべき |
| ADR-0005 D4「注釈 (スコープ外候補)」vs ADR-0003v2「注釈側構成子 (スコープ内)」 | **用語の混同リスク (L1)** — 定義節で区別することで解消 |

---

### 4. 「アンカー」として警戒すべき点 (Pass C への引き継ぎ)

1. **「5案評価 → δ が最も合理的」という結論がアンカーになる可能性**: 5 レビュアーの評価がδを支持する方向に集約しているが、Pass C の spec-architect は Pass A2 ドラフトを参照禁止として `evaluations/round1.5-evaluation.md` のみを入力に「白紙で同じ結論に到達するか」を確認する。到達できれば δ の独立的正当性が高い
2. **N3 (normative token) の重要性を見落とす可能性**: `hypervisor` 1 語の扱いが「実装上の瑣末事」に見えるが、バリデータの未定義動作に直結する最重要指摘。Pass C で必ず明示的に扱うこと

---

### 5. Pass C への Input サマリ

**Pass C で spec-architect が参照するもの**:
- **本評価メモのみ** (drafts/0003v2 は参照禁止)
- ADR-0005 / ADR-0001〜0004 (Accepted 版) / CLAUDE.md

**Pass C で確定すべき主要論点**:
1. δ vs α の採否 — D4 フレームワーク適用結果を独立に再評価
2. `hypervisor` normative token の明示 (N3 必須)
3. `CANONICAL_ROLES` 定数の残置 vs 削除 (D1 推奨: 残置)
4. `layer1.nodes.role` の適用範囲宣言 (N2)
5. 「注釈側構成子」の用語定義 (L1)
6. δ 採用後の推奨値準拠動機の仕組み (YEx-H3)
7. γ / ε の Phase 2+ 申し送り

**独立に同じ結論に到達した点 (Pass A2 の正当性が高い箇所)**:
- `role` の D4 全 No 判定 — 5 レビュアー全員が異議なし
- δ が Phase 1 での移行コスト最小 — linguist/dsl-designer/example-author が独立に確認
- ε は Phase 1 で採用不可 — dsl-designer / example-author が独立に確認
- `container × hypervisor = error` は canonical 依存なしで維持可能 — dsl-designer / network-tech が独立に確認 (ただし実装方法の明示が必要)
