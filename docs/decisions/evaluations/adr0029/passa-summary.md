# ADR-0029 Pass A のまとめ — EVPN Multi-Site を MLNDL でどう書くか

5 つのエージェントの Pass A (独立の案出し) を並べ、一致した所と分かれた所を整理する。各エージェントの報告は同じディレクトリの `passa-*.md`、試し書きは `a1`〜`a3` の YAML。

## 一致した所 (5 つとも)

1. **今の構文では、EVPN Multi-Site のトンネルの段の構造を書けない**。L2VNI の `vteps` は平らなリストで、`derive.l2vni_participants` も全 VTEP の和集合を取る。全サイトの VTEP を並べると、leaf どうしがサイトをまたいで直接トンネルを張るように読める。ndl-viz もそう描く (試し書き a1 の FEEDBACK (5))
2. **それ以外はほぼ今の構文で書ける**。BGW の anycast VTEP (ADR-0014 D6)、BGW が「サイト内の VTEP」と「サイト間の VTEP」を別のエントリで持つこと、BGW どうしの eBGP multihop の EVPN、DCI の underlay、route server
3. **`labels.site` に意味を持たせない**。labels は注釈で参照ではない (ADR-0009)。サイト・ファブリック・トンネルのドメインは 1 対 1 とは限らない (1 拠点に 2 ファブリック、1 ファブリックが 2 拠点)。BGW は 2 つのドメインに面するが `labels.site` は 1 つの値
4. **方式名を構文に入れない** (`multisite` / `bgw` / `tier: multi-site`)。BGW かどうかは「2 つのドメインに VTEP を持つ機器」という関係から導く (ADR-0014 D1・ADR-0005 D4 補則の問い 4)
5. **新しい構成子 (ドメイン) は加算で足せる**。書かなければ今までどおり「全 VTEP が 1 つのドメイン」で、今の見本は書き換えずに済む
6. **載せないもの** (ADR-0022 の粒度): DF election、split horizon、site-id、re-origination のポリシー、advertise-pip など

## 分かれた所

### A. ドメインをどこに書くか

| 書き方 | 出した人 | 形 |
|---|---|---|
| A1. VTEP の属性 | dsl-designer、network-tech-reviewer、linguist | `vteps: [{id, sources, domain: <ドメイン>}]` + ドメインの一覧 |
| A2. ドメインが VTEP を並べる | spec-architect、example-author | `domains: [{id, members: [<VTEP>]}]`、L2VNI が `domains` を指す |
| A3. L2VNI の `vteps` を構造化 | network-tech-reviewer (`vteps_by_domain`)、spec-architect (案 B) | `vteps: [{domain, vteps}]` |

A3 は「L2VNI ごとに同じ分け方を繰り返す」「Union 型になる」「ドメインの名前や説明を置く場所がない」と dsl-designer と spec-architect が退けた。A1 と A2 が残る。

- A1 は「1 つの VTEP は 1 つのドメイン」が型で決まり、L2VNI は変えずに済む。ADR-0005 D6 (node を導く) と同じく、L2VNI のドメインは VTEP から導く
- A2 は ADR-0018 の `bridges` (ポートを並べる箱) と同じ流儀。L2VNI ごとにドメインの一部だけを使う、という書き方もできるが、そのぶん検査が増える

### B. サイト間 (DCI) を 1 つのドメインとして書くか

- **書く** (dsl-designer の `od-dci`、spec-architect の `vxd-dci`): ドメイン = 「中でフルメッシュにトンネルを張る VTEP の集合」と一様に定義できる。BGW はサイトのドメインに 1 つ、DCI のドメインに 1 つ、VTEP を持つ
- **書かない** (network-tech-reviewer): ドメインはサイトごと。`domain` を付けた VTEP を「ドメイン間の VTEP」と読む。属性の有無で意味が変わる
- **VTEP が複数のドメインに属する** (linguist の `fabrics: [a, b]`): DCI に面する VTEP は 2 つのドメインに属する

B は A と組み合わせて決まる。「ドメインの中ではフルメッシュ、1 つの VTEP は 1 つのドメイン、DCI も 1 つのドメイン」がいちばん規則が少ない (導出は「同じドメインの VTEP どうしがトンネルの対」だけ)。

### C. 名前

| 候補 | 出した人 | 長所 | 懸念 |
|---|---|---|---|
| `fabrics` | linguist、example-author (`vxlan_fabrics`) | 運用者の語 (NX-OS・NDFC・Apstra・CloudVision)。`labels.site` と棲み分けられる | DCI のドメインを「fabric」と呼ぶのは不自然。ASIC の fabric と紛らわしい |
| `overlay_domains` | dsl-designer | 何のドメインかが分かる | 2 語。「domain」は broadcast domain などと多義 |
| `vxlan_domains` | spec-architect | VXLAN のトンネルの範囲だと分かる | 同上 |
| `evpn_domains` | network-tech-reviewer | 制御プレーンの境界と分かる | 静的な VXLAN にも使うなら EVPN は狭い |

B で「DCI もドメイン」を採るなら、`fabric` は DCI に合わない。

### D. VNI stitching

- 先送り (deferred.md 50 行目のまま): spec-architect、dsl-designer、network-tech-reviewer。見本は全サイトで同じ VNI 番号にする
- 名前の候補だけ出した: linguist (`vni_stitches`、`endpoints` で向きなし)、example-author (a2 の `stitching.between_vnis`)

### E. L3VNI

L3VNI は `vteps` を持たない (ADR-0014 D3)。L3VNI のトンネルの範囲をどう読むか (L2VNI と同じくドメインから導くか、VRF の VTEP から導くか) は誰も結論を出していない。

## Pass B に送る推奨

1. **モデル**: ドメイン = 「中でフルメッシュにトンネルを張る VTEP の集合」。1 つの VTEP は 1 つのドメインに属する。DCI も 1 つのドメイン。BGW は 2 つのドメインに VTEP を 1 つずつ持つ。トンネルの対は「同じ L2VNI に参加し、同じドメインに属する VTEP どうし」
2. **書く場所**: A1 (VTEP の属性 `domain:` + ドメインの一覧) を主案に、A2 と比べる
3. **名前**: B の決定に合わせて `overlay_domains` / `vxlan_domains` / `fabrics` を比べる
4. **範囲**: VNI stitching・RT の付け替え・ファブリックごとの VNI の使い回しは先送り。全サイトで同じ VNI 番号の構成だけ
5. **見本**: `tests/fixtures/valid_evpn_multisite.yaml` (試し書き a1 をもとに)

## Pass B で確かめること

1. A1 と A2 のどちらで書くか。今の 5 本の fixture が書き換えなしで valid のままか
2. 「DCI もドメイン」で、BGW の VTEP の id とドメインの id が冗長に見えないか (試し書きで)
3. 検査: ドメインをまたぐ L2VNI に、ドメインをまたぐ機器 (BGW) がないとき。ドメインに VTEP が 1 つ。サイト間の EVPN セッションの両端と、ドメインの境界が食い違うとき。それぞれの severity
4. BGW の warning (ADR-0026 D5 の 10) を「2 つのドメインに VTEP を持つ機器」なら抑えるか
5. L3VNI のトンネルの範囲をどう導くか
6. エクスポーターと ndl-viz: トンネルの対を出すか、ドメインを枠で描くか
7. `role: border-gateway` を推奨語彙に足すか (ADR-0003)
8. `labels.site` とドメインの違いを concepts.ja.md でどう説明するか

## 付記: 試し書きで見つかった別の問題

試し書き a1 は BGP のインスタンスに `vrf: vrf-default` と書いた。mlndl では「`vrf` を書かない = default VRF」で、`vrf-default` は名前の付いた別の VRF として扱う。そのため EVPN のセッションに「vrf-default のセッションが l2vpn_evpn を運んでいます。これらの経路は default VRF のセッションで運ぶのが通常です」という warning が出る。文が自己矛盾に見えて分かりにくい。fixture の多くも L3 IF に `vrf: vrf-default` と書いている (書き方の推奨では「default VRF なら書かない」)。この ADR とは別に直す。
