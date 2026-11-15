# ADR-0026 初版の横断評価 (2026-11-15)

対象: `drafts/0026-l2vni-vlans.md` の初版 (コミット `7f2d5c8`、改訂 1 の前)。5 エージェントが並列に評価し、試し書き担当が `passb/` の B1〜B5 を書いた。

前提 (ユーザー決定。蒸し返さない): 案 A (L2VNI の `vlans` リスト) を採る。「VLAN translation」の語は ADR / docs で使わない。
別ファブリックで同じ番号の VLAN を使うときの id の付け方と、ファブリックごとの VNI の番号の使い回しは、この ADR では扱わない。

## 試し書きの検証

`vlans` は未実装なので、各ファイルの `vlans: [a, b, ...]` を `vlan: a` に置き換えた写しで `python -m mlndl validate` を流した (統合担当が実行。試し書き担当は実行できなかった)。
ドラフトと関係のない error はなかった。出た warning は試し書き担当の予想と一致した。

| ファイル | 今の validator | ドラフトどおり実装したら |
|---|---|---|
| B1 (D1 の例の完全な形。ES + leaf3 だけ VLAN 30 + leaf4) | warning: leaf3 に `vlan-20` のポートがない | valid |
| B2 (border1 が SVI だけで参加、番号は別) | warning × 2 (border1・leaf3) | valid (D4 の 2 で border1 の VLAN が決まる) |
| B3a (1 台で 2 VLAN) | warning × 1 (leaf3) | error: 1 台の機器で 2 VLAN |
| B3b (1 VLAN が 2 VNI) | なし | error: 1 つの VLAN が 2 つの L2VNI に |
| B3c (ES の脚が別番号) | warning × 3 (ES の脚の一部だけ × 2、leaf2) | error: ES の脚が別番号 (ES の脚の一部だけの warning は重ねない。改訂 1) |
| B3d (同じ `vlan_id` が 2 エントリ) | warning × 1 (leaf2) | warning: 1 エントリにまとめる |
| B3e (参加機器に VLAN なし) | warning × 1 (leaf3) | warning: 参加機器に `vlans` のどの VLAN もない |
| B4 (全機器で同じ番号) | なし | valid (`vlans: [vlan-100]`) |
| B5 (L2VNI の VLAN と VXLAN を使わない VLAN の混在、L2VNI の中で anycast の IP を食い違わせた) | warning × 1 (leaf3)。IP の食い違いは見逃す | error: L2VNI の anycast gateway の食い違い (D6) |

B3a・B3b・B5 は、今の validator が誤りを見逃すことを示している (この ADR の検査を足す理由)。

## RFC の節番号の確認

network-tech-reviewer は「Ethernet Tag = 0 は RFC 8365 §5.1.3 ではなく RFC 7432 §6.1・§7 が根拠」「内側の VLAN タグの記述は RFC 8365 §4 に近い」とした。
統合担当が RFC の本文 (rfc-editor.org のテキスト版) で確かめたところ、初版の引用は正しかった。

- RFC 8365 §5.1 (VXLAN/NVGRE Encapsulation): 「the ingress VTEP does not include an inner VLAN tag on the encapsulated frame」
- RFC 8365 §5.1.3 (Constructing EVPN BGP Routes): VLAN-based service の Ethernet Tag は「MUST be set to zero」
- RFC 7432 §6.1 (VLAN-Based Service Interface): PE ごとに VID が違えば、各 PE が VID translation を行う

この指摘は採らず、改訂 1 で RFC 8365 §5.1 の要約を「VNI は通常テナントの VID と 1 対 1」まで含めて書き直した。

## 一致した点

- 案 A の骨子 (`vlans` リスト、旧 `vlan` は移動先を示す error、案 B〜E の却下): 5/5。example-author も試し書きの感覚として案 A は妥当とした
- 1 台の機器で 1 つの VNI に VLAN は 1 つまで (error): network-tech は「どの機器も VLAN と VNI を 1 対 1 で対応させる」と確認
- ES の脚の機器で番号が違えば error: network-tech は「実機にも存在しない」と確認
- anycast gateway の検査を VNI 単位にする (D6): network-tech・spec-architect・example-author (B5)。Symmetric / Asymmetric IRB のどちらでも同じ要件
- SVI だけを持つ機器 (centralized gateway・border leaf) を SVI の `node` で数える (D4 の 2): network-tech・example-author (B2)
- エクスポーターは導いた値を出し、ndl-viz では導かない: spec-architect・dsl-designer

## 改訂 1 で反映した指摘

| 指摘 | 誰 | 反映 |
|---|---|---|
| D3 の「ブロードキャストドメインを表すのは L2VNI」は VXLAN を使う VLAN でしか成り立たない | linguist | D3 を 2 段に。L2VNI に入らない VLAN は、VLAN のエントリ 1 つが 1 つのドメイン |
| `vlans` を VLAN-aware bundle の MAC-VRF の VLAN と取り違えうる。将来の MAC-VRF は別のキーに | dsl-designer | D3 に明記、範囲外に「`vlans` を流用しない」 |
| ES の脚の番号の error と D3 の「同じ番号なら 1 エントリ」の関係が分かりにくい | example-author・spec-architect | D3 に「ES は相手から 1 本、`{ethernet_segment:}` で書けば番号は 1 つ」 |
| D4 で SVI を数えるのを、L2VNI の導出だけに限ると明記する。他の検査に波及させない | spec-architect | D4 に明記 (同じ機器での `vlan_id` の重複、端点、機器ノードの `vlans` はポートだけ) |
| D4 は参加機器の定義 (VTEP から) を変えない | spec-architect | D4 と Amends に明記 |
| D4 で見るのは `vlans` に書いた VLAN だけ。SVI の VLAN を `vlans` に書かないと決まらない | example-author (B2) | D4 に明記 |
| D5 の「NX-OS が受け付けない」は弱い。ブロードキャストドメインの意味から説明する | network-tech | D5 の説明を書き直した |
| 同じ L2VNI の SVI の `vrf` が食い違うと、トラフィックが別の VRF に入る | network-tech (error)・spec-architect (明記) | **error** を D5 に追加 |
| `vlans` の中の重複は L2VNI のエントリの中で判断できるので型で弾く | dsl-designer | D1・D5 で型に |
| ES の脚の error と ADR-0023 D7 の「ES の脚の一部だけ」の warning が重なる | example-author (B3c) | error を出した VLAN には warning を重ねない |
| D5 の error がある L2VNI で D6 がどう動くか | example-author | D6 を重ねない (ADR-0018 D4 と同じ考え) |
| 参加機器に VLAN がない warning の境界 (`vlans` のどれにもポートも SVI もない) | spec-architect | 今と同じく見ない |
| D6 は `ip`・`ipv6` の両方。拾う SVI は `anycast_gateway` のものだけ | network-tech・spec-architect | D6 に明記 |
| D6 の error のメッセージの主語と添える情報 | example-author (B5) | L2VNI を主語に、2 つの SVI の id・VLAN・値を添える。例を示した |
| `vlan_by_node` の名前は既存の語彙にない (`_by_` の形がない) | linguist・spec-architect・dsl-designer | **`node_vlans: [{node, vlan}]`** (リストの形は dsl-designer、名前は linguist)。`members` (dsl-designer の案) は入力でなくした名前と重なるので採らない |
| 機器ノードの `vlans` に SVI だけの機器を入れるか | spec-architect | 入れない (D4 と同じ線)。Pass C で再確認 |
| L3VNI は双方向、L2VNI は片方向の理由を書かないと、VLAN 側に `vni` を持たせる議論が蒸し返される | dsl-designer | Consequences に段落を足した |
| ポートも SVI もない参加機器 (Multi-Site の BGW) は正しい構成なのに warning が出る | network-tech | Consequences に注記。抑え方は必要になったら決める |
| タイトルの「束ねる」は LAG / ES の「束ねる」と紛れる | linguist | タイトルを「L2VNI に、機器によって番号の違う VLAN を載せる」に |
| 「機器ごとに番号が違う」は全機器で違うと読める | linguist | 初出と範囲外を「機器によって番号が違う」に |
| 1 か所だけ「ブリッジドメイン」が混ざっていた | linguist | 「ブロードキャストドメイン」に統一 |
| D1 の例が `vlans` の 2 行だけで、VTEP・SVI・VRF の姿が分からない | example-author | D1 の例に VTEP と SVI を足し、完全な形は B1 を指した |
| 影響範囲の漏れ: `valid_dual_stack.yaml` (fixture は 5 本)、`tests/test_refs.py` の `BASE`、`validation.ja.md`、`schema.json`、CLAUDE.md の表 | spec-architect | Consequences に足した |
| 足す fixture の列挙 | example-author | Consequences に B1・B2・B3a〜c・B5 相当 |
| ファブリックごとの VNI の使い回し | (ユーザーとの議論) | 範囲外に 1 行 |

## 採らなかった指摘

- **RFC 8365 の節番号の付け替え** (network-tech): 採らない — 本文で確かめて初版の引用が正しかった (上の「RFC の節番号の確認」)
- **D2 のメッセージを「なくなりました」に** (linguist): 採らない — ADR-0024・ADR-0025 のメッセージは「なくしました」でそろっている
- **D5 の error のメッセージの主語を機器に** (linguist): 実装のときに決める。表の行は条件の説明で、メッセージの文面ではない
- **SVI から機器を導くことを全体に広げる** (`derive.vlan_members` に一本化。dsl-designer): 改訂 1 では採らない — 同じ機器での `vlan_id` の重複、VLAN の端点、
  エクスポーターの `vlan_member` エッジの意味が変わる。範囲を L2VNI に限る spec-architect の案を採り、Pass C の論点に残す
- **SVI の VLAN が `vlans` に入っていないときの info** (example-author): 採らない — 参加機器に VLAN がない warning で拾える。優先度も低い (example-author 自身)
- **ポートを持たない SVI に warning** (example-author の疑問): 採らない — centralized gateway・border leaf で普通の構成 (network-tech)
- **番号の違う VLAN に同じ anycast MAC を設定する必要が図から読めない** (example-author の疑問): 採らない — MAC は構成図に書かない (ADR-0022)

## 残る論点 (Pass C 向け)

1. **「VLAN の機器」の導き方を 1 つにするか**: 改訂 1 は SVI を数えるのを L2VNI の導出だけに限った。全体に広げる (dsl-designer) と、同じ機器での `vlan_id` の重複の検査 (SVI の機器も数える)、
   VLAN の端点 (ADR-0013 D7)、エクスポーターの機器ノードの `vlans` と `vlan_member` エッジ (今は「その機器にポートがある」の意味) が変わる。どちらが正しいかを決める
2. **エクスポーターのキー `node_vlans`**: 名前と形 (`[{node, vlan}]`) を ndl-viz の描き方から確かめる
3. **BGW のような参加機器の warning**: 改訂 1 は出したままにした。正しい構成で warning が出ることを受け入れるか
4. **アンカーの確認**: Pass A では 4/5 が案 A、example-author が案 C。ユーザーの「機器の設定の書き方と整合するのは C ではないか」という問いに対し、Pass A は案 A のままとした。
   Pass C でゼロから設計して同じ結論になるかを確かめる

## Pass C への Input サマリ

**Pass C で参照するもの**: 本評価メモ、Accepted の ADR (特に 0005・0011・0013・0014・0015・0022・0023・0025)、CLAUDE.md、`docs/exporter-cytoscape.md`、
`docs/reference/layer2.ja.md`・`validation.ja.md`、試し書き (`evaluations/adr0026/passb/` の B1〜B5)、
実装 (`src/mlndl/schema/layer2.py`・`derive.py`・`validator.py` の `_validate_l2` と `_check_anycast_consistency`・`exporter/cytoscape.py`)。
**drafts/0026 は参照しない** (Pass C の原則)。

### 前提 (ユーザー決定。蒸し返さない)

- 機器によって VLAN の番号が違う L2VNI を書けるようにする
- 「VLAN translation」の語は使わない。アクセスポートでの番号の付け替え、VLAN-aware bundle、ファブリックごとの VNI の使い回しは範囲外
- 1.0 の前なので破壊的な変更を許し、旧形式は読み替えずに移動先を示す error にする (ADR-0025)

### 確定すべき論点 (優先順)

1. **参照の向き**: L2VNI が VLAN を指す (案 A) か、VLAN が L2VNI を指す (案 C) か。機器の設定の書き方 (案 C の向き)、L3VNI と VRF の双方向の参照、
   VTEP を L2VNI 側に集めた ADR-0014 との一貫性、1 つの VLAN が 2 つの VNI に入ることを型で防げるか、を比べる
2. **VLAN のエントリの意味**: L2VNI に入る VLAN と入らない VLAN で、ブロードキャストドメインを表すものが変わることの書き方。同じ番号は 1 エントリ、という分け方
3. **機器とその機器の VLAN の導き方**: ポートと SVI のどちらから、どの範囲で (上の残る論点 1)
4. **検査**: 1 台で 2 VLAN、1 VLAN が 2 VNI、ES の脚が別番号、SVI の VRF の食い違い、参加機器に VLAN がないときの warning とその境界、重ねて出さない規則
5. **anycast gateway の一致の単位**: VNI 単位と VLAN 単位の切り替え
6. **エクスポーター**: L2VNI のノードに出すものと、ndl-viz の描き方
7. **影響範囲**: 本評価メモの「改訂 1 で反映した指摘」の最後の 3 行

## Pass C の結果 (2026-11-15)

5 エージェントが drafts/0026 を読まずに本メモから再設計した。参照の向きは 4/5 が案 A (spec-architect・linguist・dsl-designer・network-tech-reviewer)、example-author が案 C で、
Pass A と同じ割れ方になった。dsl-designer は Pass B の前の自分の推奨を疑ってゼロから比べ直しても案 A だった。**ユーザーが案 A で確定した**。
ほかの論点は改訂 1 と同じ骨子で、細部で割れた点は統合担当が決めた。確定版は [ADR-0026](../../0026-l2vni-vlans.md)。試し書きは [passc/](passc/README.md) (P1〜P4)。

**試し書きの検証**: 案 A の `vlans: [a, ...]` を `vlan: a` に、案 C の VLAN の `l2vni` を外して L2VNI の `vlan` に置き換えた写しで `python -m mlndl validate` を流した (統合担当)。
error はなく、warning は今の単数の `vlan` では番号の違う機器・SVI だけの機器・BGW を数えられないことによるものだけだった。

| ファイル | 今の validator | この ADR を実装したら |
|---|---|---|
| P1 (B1 を案 C で) | warning × 1 (leaf3) | (案 C は採らない) |
| P2 案 A / 案 C (L2VNI 3 つ、VLAN 6 つ、うち 1 つは VXLAN を使わない) | warning × 2 (leaf3・leaf4) | 案 A で valid |
| P3 案 A / 案 C (NX-OS 2 台の設定を写したもの) | warning × 1 (n9k-2) | 案 A で valid |
| P4 (SVI だけの border1、ポートも SVI もない BGW) | warning × 3 (bgw1・border1・leaf3) | warning × 1 (bgw1。D5 の 10。受け入れる) |

**案 A と案 C の比較 (P1〜P3)**:

| 観点 | 案 A | 案 C |
|---|---|---|
| 記述量 (P2) | 4 行 | 5 行 |
| 「VNI に載る VLAN と VTEP」 | L2VNI 1 か所 | L2VNI と全 VLAN の 2 か所 |
| 「この VLAN はどの VNI か」 | 全 L2VNI を探す | VLAN のエントリで見える |
| 1 VLAN が 2 VNI | validator の error | 型で防げる |
| 設定からの変換 (P3) | 全機器を読んでから VNI ごとに集める | 行がほぼ 1 対 1 |

**割れた点と判断**:

| 論点 | 意見 | 判断 |
|---|---|---|
| 参照の向き | 4/5 が案 A、example-author が案 C | **案 A** (ユーザー決定) |
| 同じ機器での `vlan_id` の重複の検査に SVI を数えるか | spec-architect・network-tech: ポートだけ。dsl-designer: ポート ∪ SVI | **ポート ∪ SVI**。ポートで `vlan-100` (番号 100)、SVI で別エントリ `vlan-100b` (番号 100) を指す矛盾は、ほかの検査では拾えない (network-tech の「結果は同じ」はこの場合に成り立たない) |
| 「VLAN の機器」の関数 | Pass B の dsl-designer: 1 つにまとめる。Pass C の dsl-designer: ポート / SVI の 2 つ、使う側で合わせる | **2 つ**。端点・`vlan_member` エッジはポートだけのまま |
| `anycast_gateway` と `vrrp` の混在 | network-tech: error | **warning**。移行の途中で一時的に混ざることがある |
| エクスポーターの `vlan_member` エッジに SVI だけの機器を入れるか | network-tech: 入れる。spec-architect・dsl-designer: 入れない | **入れない**。「その機器にポートがある」の意味を保つ |

**改訂 1 に足したもの**:

- D4: `vlan_port_nodes` / `vlan_svi_nodes` と、使う場所ごとの表。参加機器と参加機器の VLAN の区別 (example-author)
- D5: 番号付きの表。「1 つの VLAN が 2 つの L2VNI に」の error がある VLAN を他の検査から外す (spec-architect)。D5 の 10 のメッセージの形 (example-author)
- D6: `anycast_gateway` を持たない SVI との混在の warning (network-tech)
- D7: `node_vlans` は YAML に書けない、機器ノードの `vlans` との書き分け (linguist)
- 範囲外: Asymmetric IRB、VNI stitching、L2VNI の Route Target (network-tech)
- 改訂の注記の文案 (spec-architect)

**採らなかった指摘**:

- linguist の concepts.ja.md の文案のうち「L2VNI に入らない VLAN は `vlan_id` の値がドメインを識別する (同じ番号を複数のエントリに分けない)」: 採らない — 別の機器で同じ番号を別のドメインに使うことを今も許している。
  「L2VNI と VLAN は多対多」も誤り (1 対多)。D3 の文案は統合担当が直した
- network-tech の「案 A なら 1 VLAN が 2 VNI を型で禁止できる」: 誤り (型で防げるのは案 C)。結論 (案 A) には影響しない
