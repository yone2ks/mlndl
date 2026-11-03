# ADR-0017 初版の横断評価 (2026-11-03)

対象: `drafts/0017-sites-and-wan.md` の初版 (改訂 1 の前)。5 エージェントが並列に評価し、試し書き担当が S1〜S6 を書いた。
検証: `python -m mlndl validate` で S1〜S6a は errors 0、S6b は D5-2 のエラー (通り道の食い違い) 1 件。

## 一致した点

- スキーマを変えず、回線情報を `description` に書くこと (前提として蒸し返さない)
- D5-2 の (c)「`role: provider-network` を validator が特別扱い」は 4/4 が却下 (ADR-0003 の 2 つ目の normative token になる)
- 箱が L3 IF を持たないことは規約にとどめ、validator は検査しない (DSL 担当。検査には role の値を見る必要がある)
- `role: provider-network` の 1 語でよい (言語担当・DSL 担当。NetBox の Provider Network と同じ語)

## 割れた点と改訂 1 での判断

| 論点 | 意見 | 判断 |
|---|---|---|
| D5-2 の候補 | 仕様担当: (b) (拠点のルーターの L3 IF を SVI にすれば今の derive で通る)。DSL 担当: 当面 (a)、(d) は Phase 2 で。ネットワーク担当: (d) が現実の構成を素直に書ける、別 ADR で。試し書き担当: (b) は `vlan_id` 必須と合わない、(d) が現実的 | 当面 (a)、(d) を別 ADR。(b) は却下 — 仕様担当の書き方はルーテッドポートを SVI と書くので実物と違う。拠点がタグなしだと `vlan_id` に書く値がない。VLAN の意味が 2 つに分かれる |
| D3 の判定基準 | 仕様担当: 「事業者の装置が経路の対向になるか」。ネットワーク担当: 広域イーサ (E-Line) は箱に寄せる | 「契約が 2 点間の回線か、事業者網への接続か」で分ける。仕様担当の基準は、広域イーサ越しに自社のルーターどうしが張る構成で箱か線かが経路の設計で変わるので採らない |
| D1 と ADR-0009 D3 | 仕様担当: 値の比較で取り出すだけなので衝突しない。DSL 担当: 注釈が事実上の構造になる。「規約で、ツールはあれば使う」と明記を | 両方を本文に反映。サイトの箱を作るのではなく値で取り出すだけ、`labels.site` は規約で書かなくても valid |
| タイトル | 言語担当: 決定の要約は冗長。「サイト・事業者網・回線情報の書き分け」 | 採用 |
| Status / Pass | 仕様担当: Pass B に | Pass A (改訂 1) のままにする。README の Pass B は評価メモを出す段階で、この文書がそれにあたる |

## 反映した指摘

- **ネットワーク担当**: 迷うサービス (インターネット VPN、閉域接続、SD-WAN) の書き方を D3 に表で足した。D5-1 に閉域接続の例 (サブ IF + L3 IF + トポロジー外の相手) を足した。
  D4 に MTU は既存の `mtu` で足りることを足した。SD-WAN のオーバーレイを D6 に足した。
  「MD5 鍵を description に」は採らない (ADR-0005 D4 補則 問い 1。秘匿情報は書かない) — D4 に明記した
- **言語担当**: 用語の表 (事業者網 / 箱 / 回線 / サイト) を Context に足した。「1 つの要素にしかつかない値」を
  「同じ値を複数の要素が共有しない識別子」に言い換えた。`site` が障害軸と図のグループの両方であることを D1 に書いた。
  `provider-network` を role-vocabulary の「グルーピングの箱」の表に入れることを Consequences に書いた
- **DSL 担当**: D1 に「規約。あれば使い、なければ何もしない」を書いた。(d) のフィールドの形の一例 (`provider_transport: l2 | l3`) を D5-2 に書いた。
  D6 のトンネル IF の課題と D5-2 (d) が同じ問題であることを書いた
- **仕様担当**: Consequences に `docs/exporter-cytoscape.md`、CLAUDE.md の YAML 例、`constants.py` (変更なし) を足した。
  ndl-viz の旧動作からの移行 (サイトの枠と名前が消える。`link_role: wan` を使うサンプルはない) を足した。NetBox アダプターは対象外と書いた
- **試し書き担当**: 箱の IF の `name` は拠点名、`name` には事業者名を含めてよい、同じ ISP の拠点は 1 つの箱、箱の ID にプレフィックスは定めない、
  `description` は一部を取り出さない、を D3 / D4 に書いた。(a) は片側からしか書けないことを D5-2 に書いた

## 試し書き担当の報告の訂正

S6a のコメントは「逆向きを書くと同じ両端の重複で error」としていたが、実際には通る (相手が address なので重複とみなされない)。
ただし 1 つのセッションを 2 エントリに書くことになり ADR-0010 に反するので、結論 (片側からしか書けない) は変わらない。コメントを直した。

## 残る論点 (Pass C 向け)

- D5-2 (d) を別 ADR にするか、Phase 2 の `layer2.bridges` と合わせるか
- `labels.site` の値の書き方の例をそろえるか (`label-vocabulary.md` の例は `site-tokyo`、試し書きは `tokyo`)

## Pass B のあとに分かったこと (2026-11-03)

- **ndl-viz の実装と確認**: `labels.site` によるサイトの枠、`role: provider-network` の雲 (サイトの上の列)、`link_role: wan` の特別扱いの削除を実装し、
  `examples/wan-sites.yaml` (4 拠点 + 事業者網の箱 4 つ: IP-VPN・広域イーサ・インターネット・Direct Connect) と `tests/fixtures/valid_multisite_wan.yaml`
  (`labels.site` を追加) で表示を確かめた。複数のサイトにまたがる VLAN の札はどのサイトの枠にも入れない。トポロジー外の BGP の相手 (PE・AWS) は
  線にならず機器のカードに出る (雲に向けて線を引かない)
- **OSPF / IS-IS は箱をはさんでも通る**: ADR-0010 D7 の通り道の検査は BGP のセッションだけにかかる。OSPF の両端の `interface` が箱の両側の別のリンクに
  載っても error にならない (S6a の BGP を OSPF に置き換えて確認)。D5-2 で書けないのは「両端が自分の機器の BGP」だけ。
  ただし 3 拠点以上の広域イーサで OSPF を張るとマルチアクセスになり、ADR-0010 D8 (ポイントツーポイント前提) の範囲外
- **D5-2 (d) の時期 (ユーザー決定)**: Phase 2 の `layer2.bridges` を待たず、ADR-0017 を確定させた直後に別の ADR で扱う

## Pass C への Input サマリ

**Pass C で参照するもの**: 本評価メモ、Accepted の ADR (0001〜0006・0009〜0013)、drafts/0008・0014・0015、CLAUDE.md、`docs/role-vocabulary.md`、
`docs/label-vocabulary.md`、`docs/exporter-cytoscape.md`、試し書き (`evaluations/adr-site-boundary/`、`evaluations/adr-wan-circuits/`、`evaluations/adr0017/`)、
`examples/wan-sites.yaml`。**drafts/0017 は参照しない** (Pass C の原則)。

### 前提 (ユーザー決定。蒸し返さない)

- スキーマと validator は変えない。回線 ID・事業者名・契約帯域などは `description` に人が読む文で書く
- `labels` は同じ値で複数の要素をまとめる分類 (図で枠や色にする)。識別子は書かない
- 箱をはさむセッションの構文の追加 (旧 D5-2 (d)) はこの ADR では決めず、次の ADR で扱う

### 確定すべき論点 (優先順)

1. **サイト**: `labels.site` で書くこと、規約としての強さ (書かなくても valid、ツールはあれば使う)、サイト間のリンクの取り出し方、値の書き方 (`tokyo` か `site-tokyo` か。`label-vocabulary.md` の例は `site-tokyo`、試し書きと wan-sites は `tokyo`)
2. **線か箱か**: 判定基準 (契約の形)、迷うサービス (広域イーサの 2 拠点、インターネット VPN、閉域接続、SD-WAN、ダークファイバ / 波長) の書き方
3. **箱の書き方**: `role` の語 (`provider-network`)、`name` / `implementation` / `labels.site` / 箱の IF の `name` / ID のプレフィックス、箱が L3 IF を持たないことを検査するか
4. **`description`**: 書式を決めないこと、ツールがパースしないこと、何を書くか (秘匿情報は書かない)
5. **`link_role`** に WAN の推奨値を足すか
6. **箱をはさむセッション**: 事業者の機器はトポロジー外の相手。両端が自分の機器の BGP は当面どう書くか、OSPF / IS-IS が通ることをどう書くか、次の ADR に渡す問い
7. **扱わないもの**、NetBox からの変換 (informative)
8. **関連文書の改訂**: role-vocabulary (グルーピングの箱の表)、label-vocabulary (冒頭、`site` の行、ndl-viz での利用、適用範囲の拡大)、exporter-cytoscape (`description`)、CLAUDE.md、ADR の README

---

## Pass C の結果 (2026-11-03)

5 エージェントが drafts/0017 を読まずに本メモから再設計した。割れた論点はなく、ユーザーの判断を待つものはなかった。確定版は [ADR-0017](../../0017-sites-and-wan.md)。
試し書きは [passc/](passc/README.md) (P1〜P4。P2b だけ error、ほかは valid)。

| 論点 | 結論 | 経緯 |
|---|---|---|
| 1. サイト | `labels.site`。規約で、ツールはあれば使い、なければ何もしない。**値はサイトの名前をそのまま (`tokyo`)** | 値の書き方は 5/5 が `tokyo`。キーと同じ語を値に重ねる理由がなく、値は図の枠の名前になる (linguist)。`az` / `tenant` と同じ書き方。`label-vocabulary.md` の例を直す |
| 2. 線か箱か | 契約の形で分ける。L2 専用線・ダークファイバ・DWDM の波長は線、2 拠点の広域イーサ・モバイル閉域網は箱 | network-tech-reviewer がサービス仕様 (end-to-end と UNI) の分け方と一致すると確認。迷うサービスの表を広げた (example-author の P3) |
| 3. 箱 | `provider-network` の 1 語。箱と箱の IF の `name` は、機器がないので「人が読む呼び名」と読む (ADR-0011 D3 と矛盾しない) | `name` の読み方を本文に書くのは linguist |
| 4. `description` | 書式を決めず、パースしない。推奨の書き方の例も示さない。書かないものに事前共有鍵・SNMP コミュニティ・担当者の連絡先を足した | 書かないものは network-tech-reviewer |
| 5. `link_role` | WAN の推奨値を足さない | network-tech-reviewer は「自社の専用線は `wan`、事業者網へのリンクは `access`」を出したが、前者は位置で取り出せ、後者は既存の `access` と意味が衝突するので採らない |
| 6. 箱をはさむセッション | BGP は片側をトポロジー外として書く。OSPF / IS-IS は 2 拠点なら両端 `node` で通る。3 拠点以上の広域イーサは範囲外。次の ADR に問い 5 つを渡す | example-author は 3 拠点以上を 2 端点の組に展開する書き方を推したが、ADR-0010 D8 が意味が壊れるとした書き方なので推奨しない。dsl-designer の「BGP も OSPF も当面は同じ書き方」は、OSPF にトポロジー外の端点の形がないので採らない。error のメッセージの改善は次の ADR の問いに入れた (validator は変えない) |
| 7. 扱わないもの・NetBox | Pass B のまま | — |
| 8. 文書 | role-vocabulary・label-vocabulary・exporter-cytoscape・CLAUDE.md・README を改訂。既存の ADR は改訂しない | spec-architect |

**ネットワーク担当の wan-sites への指摘**: DX の `vlan_id` は AWS が割り当てることと、GRE の上の BGP が書けていないこと (トンネル IF を `update_source` にできない) をコメントに足した。
広域イーサのリンクの MTU は書いていない。事業者の仕様は最大フレーム長 (Ethernet ヘッダーを含む) で示されるが、`L1Link.mtu` の値がヘッダーを含むかは決まっていない (validator の 1550 はヘッダーを含まない値として働く)。
