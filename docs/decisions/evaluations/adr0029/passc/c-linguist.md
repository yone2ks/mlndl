# ADR-0029 Pass C — mlndl-linguist (利用者向けの文と validator のメッセージの案)

ユーザーの判断 (A1 / `overlay_domains` / `overlay_domain:` / `od-` / `border-gateway` は informative) を前提に、既存の文体 (layer2.ja.md と concepts.ja.md は です・ます、role-vocabulary.md の informative の節は記述体) に合わせた。

## 1. `docs/reference/layer2.ja.md`

### (a) 冒頭のキーの一覧に 1 行 (`vteps` の前)

| キー | 型 | 説明 |
|---|---|---|
| `overlay_domains` | [[オーバーレイのドメイン](#overlay_domains)] | VTEP をフルメッシュのトンネルで束ねる単位 (EVPN Multi-Site など) |

### (b) 新しい節 `## overlay_domains` (`## vteps` の前)

> VXLAN のトンネルをフルメッシュで張る VTEP の集合 (ADR-0029)。EVPN Multi-Site のサイト内 (fabric) と DCI のように、同じ L2VNI でもトンネルを分けたいときに書きます。方式名 (Multi-Site、anycast VTEP など) は書きません。
>
> ```yaml
> overlay_domains:
>   - {id: od-site-a, description: Site A intra-fabric}
>   - {id: od-site-b, description: Site B intra-fabric}
>   - {id: od-dci,    description: Multi-Site DCI}
> ```
>
> | キー | 型 | 必須 | 説明 |
> |---|---|---|---|
> | `id` | id | ○ | 推奨プレフィックス `od-` |
> | `description` | 文字列 | | |
>
> 同じ L2VNI でも、トンネルは**同じドメインの VTEP どうしだけ**に張ります。ドメインをまたぐ VTEP の対にはトンネルは張られません。`overlay_domains` は任意で、書かなければすべての VTEP は暗黙の 1 つのドメインに属し、同じ L2VNI の VTEP のあいだはフルメッシュです。
>
> 2 つ以上のドメインに参加する L2VNI では、両方のドメインに VTEP を持つ機器 (境界ゲートウェイ、BGW) が、ドメインのあいだをつなぎます。BGW かどうかは書かず、同じ機器の L3 IF が違うドメインの VTEP の `sources` に現れることから導きます。`role: border-gateway` は参考の値で、validator は読みません。

### (c) `## vteps` の表に 1 行

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `overlay_domain` | id | | `layer2.overlay_domains` | この VTEP が属するドメイン。省略できる (`overlay_domains` を書かない構成では暗黙の 1 つのドメインに属する)。1 つの VTEP は 1 つのドメインまで |

## 2. `docs/concepts.ja.md` (「層」の節の L2VNI の段落の後)

> VXLAN のトンネルは、既定では同じ L2VNI に参加する VTEP どうしフルメッシュで張られます。EVPN Multi-Site のように、サイト内 (fabric) とサイト間 (DCI) でトンネルを階層に分けたい場合は、`layer2.overlay_domains` でドメインを分け、各 VTEP に `overlay_domain:` を書きます。ドメインの中はフルメッシュで、ドメインをまたぐ VTEP の対にはトンネルは張られません。2 つのドメインに VTEP を 1 つずつ持つ機器が、そのあいだをつなぐ境界ゲートウェイ (BGW) になります。BGW であることは書かず、2 つのドメインの VTEP の `sources` に同じ機器の L3 IF が現れるかから導きます (`role: border-gateway` は参考の情報で、検査には使いません)。
>
> `labels.site` は機器がどの拠点に置かれているかを示す注釈で、`overlay_domains` はトンネルをどう張るかの構造です。多くの場合サイトとドメインは重なりますが、stretched fabric (複数のサイトを 1 つのファブリックで運用する) のようにサイトが違っても同じドメインに属する構成や、1 つのサイトを複数のドメインに分ける構成もありうるので、2 つは別のキーに分けています。

## 3. `docs/role-vocabulary.md` (「グルーピングの箱」の後、「将来の拡張」の前に新しい informative の節)

> ## informative 慣用語彙: EVPN Multi-Site の境界
>
> EVPN Multi-Site で、サイト内 (fabric) と DCI の 2 つのオーバーレイのドメインの両方で VXLAN を終端する機器 (RFC 9014 の Border Gateway) を指す語。CANONICAL_ROLES には含めない (ADR-0003 C2 のオープン語彙の方針を保つ) が、慣用の語として推奨する。mlndl のコアは `role` の値を読まない。
>
> | 語彙 | 意味 | 備考 |
> |---|---|---|
> | `border-gateway` | EVPN Multi-Site の境界に置かれ、サイト側と DCI 側の両方で VXLAN を終端する機器 | NX-OS の Multi-Site の BGW、Arista の BGW など。実機を `leaf` や `border` として書くこともあり、どの値を使うかは利用者の判断。構造としての BGW は、`overlay_domains` の 2 つのドメインに同じ機器の L3 IF が `sources` として現れることから導くので、`role` の値に依存しない |

`load-balancer` と同じくハイフン区切り。`border_gateway` は使わない。

## 4. validator のメッセージの案

形は「見つかった状態」の 1 文 + 「直し方」の 1 文。severity は決めず、error と warning のどちらにも使える文にした。

- **(a) ドメインをまたぐ L2VNI に BGW がない**: 「L2VNI vni-10100 の VTEP は 2 つのオーバーレイのドメイン ({od-site-a, od-dci}) にまたがっていますが、両方のドメインに VTEP を持つ機器がありません。ドメインをまたぐ L2VNI には、両方のドメインの VTEP を終端する機器 (境界ゲートウェイ) が 1 台以上要ります。該当する機器にもう片方のドメインの VTEP を足すか、すべての VTEP を同じ overlay_domain にそろえてください。」
- **(b) 未定義のドメイン**: 「vteps[vtep-a-bgw-vip].overlay_domain = od-site-a は layer2.overlay_domains に定義されていません。overlay_domains に `- {id: od-site-a, ...}` を足すか、VTEP の overlay_domain を既存のドメインの id に直してください。」
- **(c) VTEP がないドメイン**: 「layer2.overlay_domains[od-dci-spare] を参照する VTEP がありません。使わないドメインは overlay_domains から外すか、どの VTEP の overlay_domain に書くか決めてください。」
- **(d) VTEP が 1 つのドメイン**: 「layer2.overlay_domains[od-site-c] に属する VTEP が 1 つ (vtep-c-leaf1) しかありません。1 つの VTEP だけのドメインでは、同じドメインの中のトンネルの対が作れません。別の VTEP を同じドメインに置くか、このドメインを overlay_domains から外してください。」
- **(e) 混在**: 「L2VNI vni-10100 に参加する VTEP のうち、一部 ({vtep-a-leaf1, vtep-a-leaf2}) にだけ overlay_domain が書かれていて、残り ({vtep-b-leaf1}) には書かれていません。同じ L2VNI の中で overlay_domain を書くか書かないかはそろえてください。書くなら参加する全 VTEP に、書かないなら暗黙の 1 つのドメインとして扱います。」

## 5. 用語の使い方の決まり

- **オーバーレイ**: カタカナで書く。単独では使わず「オーバーレイのドメイン」のように名詞を伴う。構文名 (`overlay_domains`) と並べるときは英語の表記
- **ドメイン**: ブロードキャストドメイン・障害ドメインと紛れないよう、初出は「オーバーレイのドメイン (`overlay_domains`)」と構文名を添える。2 回目以降は「ドメイン」と略してよい。紛れうる段落では略さない
- **BGW**: 初出は「境界ゲートウェイ (BGW)」、以降は BGW。「ボーダーゲートウェイ」は使わない。BGP と並ぶ段落では「境界ゲートウェイ (BGW)」と書き直す
- `role` の値は `border-gateway` (ハイフン)

## 6. 自信がない点

1. 「ドメイン」の略を 2 回目以降に許したが、ブロードキャストドメイン・障害ドメインとの混同はありうる。略を禁じて常に「オーバーレイのドメイン」と書く規約にもできる
2. 「境界ゲートウェイ」という訳語。NX-OS 系の文書では「ボーダー ゲートウェイ」が多い
3. concepts.ja.md の 2 段落目 (`labels.site` との違い) が重いかもしれない。concepts は 1 段落にし、違いは layer2.ja.md の節の末尾に置く案もある
