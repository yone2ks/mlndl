# ADR-0029 Pass B — mlndl-linguist

前提: Pass A の推奨モデル (ドメイン = 中でフルメッシュにトンネルを張る VTEP の集合、1 つの VTEP は 1 つのドメイン、DCI もドメイン、BGW は 2 つのドメインに VTEP を 1 つずつ持つ)。

## 1. ドメインの一覧の名前

Pass A で `fabrics` を推したが、DCI の集合を「fabric」と呼ぶのは運用者の感覚と合わない (NX-OS・NDFC・Apstra で DCI を fabric と呼ぶ運用はない)。

| 候補 | 直感性 | 多義性のなさ | 業界の慣用 | 内部の一貫性 (ADR-0028) | 総合 |
|---|---|---|---|---|---|
| `overlay_domains` / `overlay_domain:` | A | B (L2VNI の broadcast domain と「domain」が重なるが層が違う) | A (RFC 8365 の "overlay"、Cisco の "overlay domain") | A (2 語の名前は `ethernet_segments` の先例) | **A** |
| `vxlan_domains` / `vxlan_domain:` | A | A | B (Geneve・MPLSoUDP などを見据えると狭い) | A | A |
| `tunnel_domains` | B | C (`tunnel_interfaces` と層がずれる) | C | B | C |
| `vtep_domains` | B | A | C | B | C |
| `evpn_domains` | A | A | B (方式名寄り。静的 VXLAN を排除する) | A | B |
| `fabrics` | B (DCI に合わない) | C (ASIC・SP の fabric) | A | A | C |
| `meshes` | B | D (BGP の full-mesh・Service Mesh と衝突) | B | A | D |

**推奨: `overlay_domains` + `overlay_domain:`**

- 「underlay ではなく、オーバーレイの張り方の単位」が語から読める
- DCI も「オーバーレイのドメイン」と自然に呼べる
- VXLAN 以外の NVO が入っても語の範囲で対応できる
- `overlay` は構文のキーとしては初出。underlay は `link_role: underlay` (推奨値) だけ
- 2 語にして「何の domain か」を限定し、多義性を抑える
- 推奨プレフィックス: `od-` (ADR-0002 D7 に足す)

次点は `vxlan_domains`。差は小さいので最後はユーザーの判断。

## 2. 参照キー

- **A1 (VTEP の属性)**: `overlay_domain:` (単数形)。「1 つの VTEP は 1 つのドメイン」が型で決まるので必ず単数形。BGW は VTEP を 2 エントリ書くので、Pass A の `fabric:` と `fabrics:` の併置の問題は消える
- **A2 (ドメイン側に並べる場合)**: `members` ではなく `vteps:`。`members` は LAG と ES で「同じ役目の要素」の意味で使っており、三度目の別の意味になる。A1 を採ればこの問題は消える

## 3. `role: border-gateway` を推奨語彙に足すか

- 足す側: Multi-Site の見本では必ず出る。`border` (AS の境界・DC のエッジ) と BGW (オーバーレイの仲介) は意味が違う
- 慎重側: BGW かどうかは構造から導けるので、`role` は人への目印だけ
- `bgw` は BGP と紛らわしいので値に採らない

**推奨: 推奨の 9 語 (CANONICAL_ROLES) には足さず、`docs/role-vocabulary.md` の informative の節に追記する** (`distribution` / `access` と同じ扱い)。文案:

> `border-gateway` — EVPN Multi-Site などで、2 つ以上のオーバーレイのドメインに面してオーバーレイを仲介する機器。ベンダーによって "BGW"、"Border Gateway"、"Data Center Gateway" と呼ばれる。BGW かどうかは `overlay_domains` の構造から導けるので、`role` の値は読者と ndl-viz のための目印。`bgw` という値は BGP と紛らわしいので使わない。

## 4. 日本語での呼び方と concepts.ja.md の案

- `overlay_domains` → **「オーバーレイのドメイン」**。単に「ドメイン」はブロードキャストドメインと、「トンネルのドメイン」はトンネル IF (GRE など) と紛らわしい

concepts.ja.md の文案:

> `labels.site` は物理の拠点を注釈するためのもので、トンネルの張り方は決めない。VTEP どうしがどこまでフルメッシュでトンネルを張るかは `overlay_domains` で表し、同じドメインに属する VTEP どうしだけがトンネルの対になる。1 つの拠点に複数のドメインを置く構成や、複数の拠点を 1 つのドメインが覆う構成 (DCI、stretched fabric) も、この 2 つが独立しているから書き分けられる。

## 5. 推奨のまとめ

1. 一覧は `layer2.overlay_domains`、参照キーは `overlay_domain:` (単数形、A1)、プレフィックスは `od-`
2. A1 を採る。A2 なら `members` ではなく `vteps:`
3. `role: border-gateway` は role-vocabulary の informative の節に追記。推奨の 9 語は変えない
4. 日本語は「オーバーレイのドメイン」。リファレンスで overlay を 1 文で定義する

## 6. ユーザーに判断してもらう論点

1. 一覧の名前: `overlay_domains` (推奨) か `vxlan_domains`
2. プレフィックス: `od-` (推奨) か `overlay-`
3. `role: border-gateway`: (a) informative の節に追記 (推奨) / (b) 推奨の語彙を 10 語に / (c) 何もしない
4. `anycast` / `multisite` / `stretched` などの修飾をドメインのフィールドに書くか: 書かない (推奨)。要るなら `labels` と `description`

## 残る懸念

- `overlay` は既存のキーにない語なので、リファレンスで「VXLAN などでカプセル化された上位の網」と 1 文で定義する
- 「domain」の多義は 2 語でも完全には消えない。concepts とリファレンスで用途を 1 回限定する
- VTEP 以外 (bridge・トンネル) にドメインを広げるときは名前が足りなくなるかもしれないが、今は予定がない
