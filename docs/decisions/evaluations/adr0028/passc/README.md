# ADR-0028 Pass C — 試し書き

`docs/decisions/drafts/0028-names-and-types.md` は見ずに、Pass C の原則で書いた。
入力は `../evaluation.md` の「残る論点」と「Pass C への Input サマリ」。
名前は `lags` / `vxlans`、IS-IS の `level_1` / `level_2` / `level_all`、
`lacp.mode` は `active` / `passive` / `static` で既定値なし、`min_links` も既定値なし、
BFD のタイマーも既定値なし、`vteps` / `address_families` / `lags[].members` /
`bridges[].ports` は 1 つ以上で必須、ES の `members` は 2 つ以上を前提とした。

## ファイル一覧

| ファイル | 想定結果 | 確かめること |
|---|---|---|
| [p1-full-1.0.yaml](p1-full-1.0.yaml) | valid | 1.0 の見本として利用者が最初に読むものになるつもりで書いた小さな完全な構成。L1・LAG (`lacp` を `active` / `static` / 書かないで混ぜる)・ES (MLAG)・VLAN・L2VNI と L3VNI・VTEP (ノード共有)・VRF・SVI と anycast gateway・BGP の underlay (eBGP + BFD) と overlay (eBGP EVPN)・BFD タイマー・IS-IS 1 本 (level_2)・bridge (事業者網 provider-wan の中の L2 転送) を含む。改名した所以外は今の validator で error / warning が出ないよう気を付けた |
| [p2-old-forms.yaml](p2-old-forms.yaml) | error 多数 | 改名した旧名・旧値を 1 ファイルにまとめて書く: `layer1.lag:` (単数)、`layer2.vxlan:` (単数)、IS-IS `level: level-2` (ハイフン)、`lacp: { mode: on }` (引用符なし。YAML 1.1 が真偽値 True と読む)、`lacp: { mode: "on" }` (引用符あり。文字列 'on')。ファイルの先頭のコメントに期待するメッセージの案を 5 本 |
| [p3-empty-and-missing.yaml](p3-empty-and-missing.yaml) | error | ADR-0028 D3・D4 で「1 つ以上を必須」「書くなら中身を書く」とした所に、空と省略を書く: `layer2.bridges[].ports: []`、`layer2.vxlans[].vteps` キーを省略、`layer1.lags[].lacp: {}`、BGP セッションの `address_families: []` と `address_families` キー省略。今の実装では一部しか error にならない (ports 空・address_families は素通り、lacp: {} は defaults で埋まる)。ADR-0028 の実装後にすべて error になるはず |

## 読み方 — それぞれの YAML の先頭のコメント

すべての YAML ファイルの先頭に、次を書いた:

- 何を確かめるためのファイルか
- valid / error の別
- error なら、どの規則で、期待するメッセージの案
- 今の実装でどうなるか (改名以外の検査)
- 改名した所 (今の形に戻せば今の validator を通るはず)

## 検証の仕方 (改名を戻した機械的な検証用のメモ)

p1 は valid のつもりで書いた。改名した所だけを「今の形」に戻せば、今の validator で
error / warning なしで通るはず。戻し方:

- `lags:` → `lag:`
- `vxlans:` → `vxlan:`
- `level: level_2` → `level: level-2`
- `lacp: { mode: static }` → `lacp: { mode: "on" }`
  (引用符を忘れると YAML 1.1 が真偽値 True と読む。これは ADR-0028 D4 の改名の
  動機そのもの)

p2 は上の旧名・旧値を書いてあるので、ADR-0028 の実装後は移動先を示す error になる。
今の validator (改名前の状態) では、旧名 `lag:` / `vxlan:` / `level: level-2` は正しい
名前として受け取られる。`lacp: { mode: on }` (引用符なし) は `mode` が真偽値 True として
入り、Literal["active", "passive", "on"] の値域の外になるため今でも error
(Pass B の b1 で確かめた)。

p3 は 4 種の誤りを含むが、今の validator では次のとおり:

- `bridges[].ports: []` — 今は素通り (ADR-0028 D3 で error)
- `vxlans[].vteps` 省略 — 今は `needs_vteps` で error (ADR-0028 D3 で型レベルに移すだけ)
- `lacp: {}` — 今は defaults で埋まり valid (ADR-0028 D4 で error)
- `address_families: []` と省略 — 今はどちらも素通り (ADR-0028 D3 で error)

## `min_links` の置き場所 (Pass C で決定)

書いた時点では未決だった。ユーザーが LAG の直下 (`lags[].min_links`) に移すと決め (ADR-0028 D4)、
統合担当が p1 をその形に直した。p2 の `lacp: { mode: active, min_links: 2 }` は、旧形式 (`lacp.min_links`) の例として残す。
