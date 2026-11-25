# ADR-0029 Pass B — mlndl-example-author

## 作ったファイル

- `b1-domain-on-vtep.yaml` — 書く場所 A1 (VTEP に `domain:`、`overlay_domains` は id と description の一覧)
- `b2-domain-members.yaml` — 書く場所 A2 (`overlay_domains` が `members: [<VTEP>]` を並べる)
- `b3-three-sites.yaml` — サイト C を足した変形を b1 の書き方で (layer2 と DCI の部分)
- `b4-stretched.yaml` — ドメイン 1 つの stretched fabric (書かない形を推し、書く形を参考に併記)
- `a1-current-syntax.yaml` を上書き: BGP のインスタンスと L3 IF の `vrf: vrf-default` を外し、labels のキー `fabric_role` を `fabric-role` に (まとめの付記への対応)

b1〜b4 は仮の構文で、今の mlndl では通らない。layer2 は全部書き、layer1 / layer3 / control_plane は「a1 と同じ」として省略。

(まとめの注: 上書きした a1 に `vrf: vrf-default` が残っていたので、まとめるときに消した。a1 は `validate` を通り、`--strict` で残るのは BGW の 4 つの warning (ADR-0026 D5 の 10。BGW は VLAN のポートも SVI も持たない) だけ。この warning を抑えることは Pass B の論点 4)

## A1 (b1) と A2 (b2) の比較

**記述量**: A2 のほうが明らかに多い。VTEP の `sources` / `address` を書いたあと、`members` に同じ VTEP の id を並べ直すので、8 つの VTEP を 2 か所で保守する。A1 は VTEP の行の末尾に `domain: od-xxx` が増えるだけで、ドメイン側は id と description だけ。VTEP の数に比例して差が開く。

**誤りやすさ**:

- 「2 つのドメインに入れてしまう」: A1 は単数のフィールドなので YAML の段階で起こらない。A2 は同じ VTEP を 2 つのドメインの `members` に書けてしまい、検査で弾くことになる
- 「どのドメインにも入れ忘れる」: どちらでも起きる。A1 は行の末尾の 1 語なので、目で見て漏れを拾いやすい

**読みやすさ**: 目的で分かれる。A2 は「このドメインに何が属するか」が 1 か所にまとまり、ADR-0018 の `bridges` の `ports`・ADR-0023 の ES の `members` と同じ流儀。A1 はドメインの中身を見渡すには VTEP の行を縦に眺めるか、集計が要る。

## 3 サイト (b3)

サイト C を足すのに触ったのは「`overlay_domains` に 1 行」「VTEP を 4 行」「L2VNI の `vteps` に 4 つ」だけで、既存の記述には触らない。DCI は「3 つの BGW の VTEP のフルメッシュ」で `od-dci` 1 つにまとまり、ドメインの数は増えなかった。「ドメイン = フルメッシュの集合」という定義の見返り。

一方、DCI がフルメッシュでない構成 (hub-and-spoke、直列) は、このモデルのままでは書けない。同じ Multi-Site の VIP が複数の 2 点間のドメインに属する必要が出て、「1 つの VTEP は 1 つのドメイン」が崩れる。範囲を「stretched + フルメッシュの DCI」に限ると明記するのが現実的。

## stretched (b4)

ドメインが 1 つで済む構成では、`overlay_domains` を**書かない**形がはっきり自然。VTEP も VNI も今の構文のまま。今の 5 本の fixture が書き換えなしで valid のままになる。

## 推奨

**書く場所は A1**。(i) 誤りの余地が型で狭まる、(ii) 記述量が少なく、VTEP との対応が 1 行で読める、(iii) ドメインを書かない場合 (b4) との境界が自然 (単数のフィールドの省略)。A2 は `bridges` と表面の流儀は揃うが、`bridges` の `ports` は箱に属するポート (実体の帰属) で、ここのドメインは VTEP の分類の軸なので、VTEP 側に単数のフィールドで置くほうが意味にも合う。

L3VNI には b1 でも `domain` を書かない (`vteps` を持たない)。L3VNI のドメインは、その VRF の L3 IF を持つ機器が終端する VTEP のドメインから導く。

## 名前について

`overlay_domains` で書いていて、`od-site-a` と `od-dci` が同じ列に並ぶ所で少し違和感があった。どちらも「中でフルメッシュ」という意味では同じ概念だが、ユーザーの語彙では別物に感じる。`fabrics` は DCI を呼びにくく、`evpn_domains` は静的 VXLAN に使いにくい。`overlay_domains` は少し長いが、どの構成 (stretched / multi-site / DCI だけ) にも当てはまり、誤読は少なそう。`vxlan_domains` も妥当。プレフィックスは `od-` で収まったが、運用者には `fabric-` のほうが覚えやすいかもしれない。

## 言語全体への細かい feedback

- labels のキーは ADR-0002 D1 で下線が書けない。`fabric_role` と書きたくなる。推奨語彙の文書に注意書きがあるとよい
- `vrf: vrf-default` を書かない流儀が `docs/reference/` から読み取りにくい。既存の fixture の多くが書いているので、どちらが正しいか迷う。1.0 の前に fixture をそろえる作業が要る
