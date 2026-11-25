# ADR-0029: オーバーレイのドメイン — EVPN Multi-Site のトンネルの範囲を書く (`overlay_domains`)

- **Status**: Accepted (2026-11-26 に Pass C で確定し、同日に実装。スキーマ・derive・validator・エクスポーター・fixture・docs。ndl-viz の対応はこれから)
- **Date**: 2026-11-26
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー (書く場所は VTEP の属性、名前は `overlay_domains` / `overlay_domain:` / `od-`、1 本のループバックで 2 つのドメインを終端する構成は先送り、`role: border-gateway` は informative)
- **Pass**: C ([Pass B のまとめ](evaluations/adr0029/passb/summary.md) を入力に再設計)
- **Supersedes**: なし (Pass A は ADR の本文を書かず、[5 つの報告とまとめ](evaluations/adr0029/passa-summary.md) と試し書き a1〜a3 で検討した)
- **Amends**: [ADR-0014](0014-vteps.md) D2 (VTEP に `overlay_domain` を足す)、[ADR-0026](0026-l2vni-vlans.md) D5 の 10 (ドメインをまたぐ機器は warning の対象外)
- **関連**: ADR-0002 D7 (推奨プレフィックス)、ADR-0005 D4 補則の問い 4 (方式名を構文に入れない)、ADR-0009 (`labels` は注釈)、[ADR-0010](0010-control-plane-separation.md) (制御プレーンとデータプレーンの独立)、ADR-0015 (`Ref`)、ADR-0017 (`labels.site`)、ADR-0022 (粒度)、ADR-0023 (子が親を単数で指す)、ADR-0027 (加算の約束)

## Context

EVPN Multi-Site (RFC 9014 の GW を使う接続) では、サイトの中は leaf と BGW (Border Gateway) がフルメッシュに VXLAN のトンネルを張り、サイトのあいだは BGW どうしだけがトンネルを張る。leaf はサイトをまたいで直接トンネルを張らない。BGW は、サイトの中向けの VTEP と、サイトのあいだ向けの VTEP (Multi-Site の VIP) を別に持つ。

今の MLNDL ではこの張り方を書けない。L2VNI の `vteps` は「この VNI を終端する VTEP」を平らに並べるだけで、`derive.l2vni_participants` も全 VTEP の和集合を取る。2 サイトの 8 つの VTEP を並べると、読む人も ndl-viz も、どの 2 つの VTEP のあいだにもトンネルがある (28 対) と読む。実際のトンネルは 7 対 (各サイトの中の leaf 2 つと BGW の VIP の 3 対ずつと、サイトのあいだの Multi-Site の VIP どうしの 1 対) しかない (試し書き [a1](evaluations/adr0029/a1-current-syntax.yaml) の FEEDBACK 5)。

ほかの要素は今の構文で書ける (Pass A で 5 つのエージェントが一致)。BGW の anycast の VTEP (ADR-0014 D6)、BGW がサイトの中とサイトのあいだの VTEP を別のエントリで持つこと、BGW どうしの eBGP multihop の EVPN、DCI の underlay、route server。足りないのは「トンネルを張る範囲」だけである。

`labels.site` からは導けない。`labels` は注釈で参照ではなく (ADR-0009)、サイトとトンネルの範囲は 1 対 1 ではない (1 つの拠点に 2 つのファブリック、2 つの拠点を 1 つのファブリックで張る stretched fabric)。BGW は 2 つの範囲に面するが、`labels.site` は 1 つの値しか持てない。

## Decision

### D1. モデル

**オーバーレイのドメイン** (以下「ドメイン」) = 中でフルメッシュに VXLAN のトンネルを張る VTEP の集合。

- 1 つの VTEP は 1 つのドメインに属する (多対多にしない)
- サイトのあいだ (DCI) も 1 つのドメインとして書く。DCI のための別の構成子は作らない
- 2 つのドメインのあいだをつなぐ機器 (BGW) は、ドメインごとに別の VTEP を 1 つずつ持つ。ADR-0014 D6 の表の「Multi-Site BGW の anycast」の書き方 (サイトの中の VTEP と Multi-Site の VIP を別のエントリ) のままで、各エントリにドメインを書く
- トンネルの対は「同じ L2VNI に参加し、同じドメインに属する VTEP どうし」
- 方式名 (Multi-Site・anycast・stretched・BGW) は構文に書かない (ADR-0005 D4 補則の問い 4、ADR-0014 D1)。BGW かどうかは「2 つ以上のドメインに VTEP を持つ機器」という関係から導く

### D2. 構文

```yaml
layer2:
  overlay_domains:                       # 任意。書かなければ全 VTEP が 1 つの暗黙のドメイン (D3)
    - {id: od-east, description: East site fabric}
    - {id: od-west, description: West site fabric}
    - {id: od-dci,  description: Inter-site (DCI)}

  vteps:
    - {id: vtep-a-leaf1,     sources: [a-leaf1-lo], overlay_domain: od-east}
    - {id: vtep-a-bgw-vip,   sources: [a-bgw1-lo1, a-bgw2-lo1], address: 10.0.100.1/32, overlay_domain: od-east}
    - {id: vtep-a-bgw-msvip, sources: [a-bgw1-lo2, a-bgw2-lo2], address: 10.0.200.1/32, overlay_domain: od-dci}
    # west 側も同じ形

  vxlans:
    - id: vni-10100
      type: l2vni
      vni: 10100
      vlans: [vlan-100]
      vteps: [vtep-a-leaf1, vtep-a-bgw-vip, vtep-a-bgw-msvip, ...]   # 書き方は変えない
```

| キー | 型 | 必須 | 説明 |
|---|---|---|---|
| `layer2.overlay_domains[].id` | id | ○ | 推奨プレフィックス `od-` (ADR-0002 D7 に足す) |
| `layer2.overlay_domains[].name` | 文字列 | | 表示名 |
| `layer2.overlay_domains[].description` | 文字列 | | |
| `layer2.vteps[].overlay_domain` | id (`Ref("layer2.overlay_domains")`) | | この VTEP が属するドメイン |

- ドメインのエントリは VTEP を並べない (`members` を持たない)。VTEP がドメインを単数で指す (ADR-0023 の `lags[].node` と同じ「子が親を指す」形)。1 つの VTEP は 1 つのドメインであることが型で決まり、同じ情報を 2 か所に書かない
- L2VNI と L3VNI のスキーマは変えない。参加機器の導き方 (ADR-0014 D3・ADR-0026 D4) も変えない
- 加算の変更 (ADR-0027 D2)。今の見本は書き換えなしで valid

### D3. 暗黙のドメイン

どの VTEP にも `overlay_domain` を書かなければ、全 VTEP が 1 つの暗黙のドメインに属し、今までどおり同じ L2VNI の VTEP どうしがフルメッシュになる。stretched fabric や 1 つの DC はこの形で書く (`overlay_domains` を書かない形が自然。試し書き [b4](evaluations/adr0029/b4-stretched.yaml))。

一部の VTEP にだけ書くことは許さない (D5 の 3)。書くなら全 VTEP に書く。暗黙のドメインは YAML から参照できず、エクスポーターも出さない。

### D4. 導出

- **VTEP のドメイン**: VTEP の id → ドメインの id (暗黙のドメインは内部の値)
- **L2VNI のトンネルの対**: L2VNI の id → 同じドメインに属し、その L2VNI の `vteps` にある VTEP の順不同の対。ドメインをまたぐ対は出さない
- **ドメインをまたぐ機器**: L2VNI の id → その L2VNI の 2 つ以上のドメインに VTEP を持つ機器 (= BGW)。機器が終端する VTEP は `sources` の L3 IF の `node` から導く (ADR-0014)
- **L3VNI のドメインとトンネルの対**: 同じ VRF の L2VNI (`vlans` のどれかの SVI がその VRF にある L2VNI) のドメインの和集合と、トンネルの対の和集合

L3VNI の導き方は Pass B で割れた (「VRF の L3 IF を持つ機器の VTEP から導く」案と「同じ VRF の L2VNI の和集合」案)。Pass C で spec-architect・dsl-designer・network-tech-reviewer がそれぞれ独立に和集合の案を採った。BGW は普通 tenant の VRF の L3 IF を MLNDL に書かない (L3VNI 用の SVI は IP を持たず、構成図の粒度の外) ので、前者の案では BGW が L3VNI に入らない。実機では Symmetric IRB の L3VNI も BGW がサイトのあいだに中継する。

関数の名前と戻り値の形は実装で決める (derive は参考の扱い。ADR-0027)。

### D5. 検査

| # | 検査 | severity |
|---|---|---|
| 1 | `vteps[].overlay_domain` が `layer2.overlay_domains` に定義されているか (`Ref` の汎用の検査) | error |
| 2 | `overlay_domain` を書いた VTEP と書かない VTEP が、トポロジーの中に混ざっていないか | error |
| 3 | L2VNI の VTEP が 2 つ以上のドメインにまたがるのに、その L2VNI の 2 つ以上のドメインに VTEP を持つ機器が 1 台もない | error |
| 4 | どの VTEP も属さないドメイン | warning |
| 5 | id の文法・一意性・推奨プレフィックス `od-` | 既存の検査 (error / error / warning) |

- **3 が核心の検査**。ドメインをつなぐ機器がなければ、その L2VNI はドメインごとに分断される。stretched や 1 つの DC (ドメインが 1 つ) は対象にならない
- **2**: 混ぜると「書かない VTEP は暗黙のドメインか、書き忘れか」が分からない。直し方 (全部に書くか、全部書かないか) をメッセージで示す
- **4**: warning。ドメインを先に宣言し、VTEP をあとで足す書き方 (ADR-0028 D3 の「エントリを先に宣言するもの」) を妨げない
- **重ねて出さない**: 2 の error があるとき、3 は出さない

**検査しないもの**:

- **VTEP が 1 つだけのドメイン** と **1 つのドメインに L2VNI の VTEP が 1 つだけ**: stretched や「あとで BGW を足す」構成で偽の警告になる
- **`overlay_domains` が 1 つだけ**: stretched で意図を明示するために 1 つ書くことがある
- **サイトのあいだの EVPN のセッションとドメインの境界の照合**: セッションの端 (BGW の lo0) とトンネルの端 (Multi-Site の VIP) は別の L3 IF でよく、route server の構成では両端が BGW にならない。ADR-0010 のとおり制御プレーンとデータプレーンは独立に導く
- **3 つ以上のドメインにまたがる L2VNI で、ドメインの対ごとにつなぐ機器があるか**: 3 は「2 つ以上のドメインに VTEP を持つ機器が 1 台あるか」で判定する。DCI がフルメッシュの 1 つのドメインなら十分 (hub-and-spoke は範囲外)
- **`labels.site` とドメインの対応**: stretched では同じドメインに別のサイトの機器が入る。正しい構成

### D6. ADR-0026 D5 の 10 の warning を抑える

ADR-0026 D5 の 10 (「L2VNI の参加機器に、`vlans` のどの VLAN のポートも SVI もない」) は、VNI を中継するだけの BGW で必ず出る (試し書き a1 で 4 件)。D4 の「ドメインをまたぐ機器」にあたる機器は、その L2VNI について warning を出さない。暗黙のドメインだけの構成では今までどおり出る。

BGW という役割は書かず、構造から拾う (ADR-0022 の粒度を保つ)。

### D7. エクスポーター (Cytoscape)

規範のキーとして足す (`docs/exporter-cytoscape.md`)。どれも書いたときだけ出し、暗黙のドメインは出さない。

- `type: overlay_domain` のノード: `id`・`label` (`name` か `id`)・`layer: layer2`・`description`・`vteps` (このドメインの VTEP の id)
- 機器のノードの `vteps[]` の各要素に `overlay_domain`
- `type: l2vni` に `tunnel_pairs: [{endpoints: [<VTEP>, <VTEP>], overlay_domain: <id>}]` (無向の対。ADR-0006 の `endpoints` と同じ形)。ドメインを書かない構成では出さない (今までどおり全 VTEP のフルメッシュと読む)
- `type: l3vni` に `overlay_domains: [<id>]` と `tunnel_pairs` (D4)

ndl-viz は、ドメインを枠で描き、`tunnel_pairs` の対だけトンネルの線を引ける。

### D8. `labels.site` との関係

ドメインとサイトは別の軸で、互いに代わりにならない。

| | 何を表すか | 多重性 |
|---|---|---|
| `labels.site` (ADR-0017) | 機器が置かれた拠点。注釈 | 1 つの機器に 1 つ |
| `overlay_domain` | VTEP がフルメッシュでトンネルを張る範囲。構造 | 1 つの VTEP に 1 つ |

1 つのサイトが 1 つのドメインのことが多いが、stretched fabric では 2 つのサイトが 1 つのドメインに、Multi-Site の BGW はサイトのドメインと DCI のドメインの両方に面する。

### D9. `role: border-gateway`

`docs/role-vocabulary.md` の informative の節に `border-gateway` を足す。推奨の 9 語 (CANONICAL_ROLES) は変えない (ADR-0003)。mlndl のコアは読まず、BGW かどうかは D4 の構造から導く。人と ndl-viz のための目印。`bgw` は BGP と紛らわしいので値に使わない。

### D10. 用語

- 日本語は「オーバーレイのドメイン」。初出では構文名 `overlay_domains` を添える。ブロードキャストドメインと紛れる段落では「ドメイン」と略さない
- BGW は初出で「境界ゲートウェイ (BGW)」

## 範囲外 (deferred.md に足す)

| 項目 | 始めるきっかけ |
|---|---|
| 1 本のループバックで 2 つのドメインを終端する VTEP (同じ L3 IF を 2 つの VTEP に書くことになり、ADR-0014 の検査に当たる) | そういう機種・構成を書く必要が出たとき |
| hub-and-spoke など、データプレーンがフルメッシュでない DCI | データプレーンまで階層の DCI を書く必要が出たとき |
| VNI stitching (ドメインごとに VNI の番号を付け替える)。今は VNI はトポロジー全体で一意 | 既存の deferred.md の行にドメインとの関係を書き足す |
| BGW での Route Target の付け替え | 既存の行 (L2VNI の RT) に関連づける |
| BUM の配送方式をドメインごとに変えること | 方式の違うドメインを書く必要が出たとき |
| L3VNI の明示の `vteps` (L2VNI を持たない VRF の L3VNI はドメインが空になる) | L2VNI のない L3VNI の範囲を書く必要が出たとき |
| BGW が L2 の中継だけで tenant の VRF を持たない構成 (D4 の導き方では L3VNI に入る) | そういう構成を書き分ける必要が出たとき |
| 1 つの VTEP が 2 つのドメインに属する (多対多) | 実装の例が出たとき |

## Consequences

**良い影響**:

- EVPN Multi-Site・border leaf を兼ねる BGW・stretched fabric のトンネルの範囲を、方式名を使わず構造だけで書ける
- L2VNI の `vteps` を全 VTEP のフルメッシュと読む誤りが、ドメインを書けば消える
- BGW に必ず出ていた ADR-0026 D5 の 10 の warning が消える
- 加算だけで、今の見本・fixture・ndl-viz の読み方は変わらない
- サイトを増やしても、ドメインを 1 つと VTEP を足すだけ (DCI のドメインは 1 つのまま。試し書き [b3](evaluations/adr0029/b3-three-sites.yaml))

**悪い影響・トレードオフ**:

- BGW は VTEP のエントリが 2 つになる (1 台が 2 行に分かれる)。ADR-0014 D6 の書き方そのものだが、読む人には新しい
- ドメインの中身を 1 か所で見渡せない (VTEP の行を縦に読む)。エクスポーターの `overlay_domain` ノードの `vteps` で補う
- 「オーバーレイ」が構文のキーに初めて出る。underlay は `link_role: underlay` (推奨値) だけ。リファレンスで定義する

## 検討した代替案

| 案 | 却下の理由 |
|---|---|
| ドメインが `members` で VTEP を並べる | VTEP が `members` と L2VNI の `vteps` に二重に出る。1 つの VTEP が 2 つのドメインに書けてしまい、検査が要る。記述量も多い (試し書き b2)。Pass B で network-tech-reviewer だけが推した |
| L2VNI の `vteps` を `[{domain, vteps}]` に構造化 | L2VNI ごとに同じ分け方を繰り返す。Union 型になる。ドメインの名前を置く場所がない |
| EVPN のセッションから導く | データプレーンが制御プレーンに依存する。制御プレーンを書かない構成で書けない。RR の配下では leaf どうしのセッションがない |
| `labels.site` から導く | labels は注釈 (ADR-0009)。サイトとドメインは 1 対 1 でない。BGW は 2 つに面する |
| 方式名のフィールド (`tier: multi-site`、`is_bgw`) | ADR-0005 D4 補則の問い 4、ADR-0014 D1 |
| 名前 `fabrics` / `vxlan_domains` / `evpn_domains` | `fabrics` は DCI に合わない。`vxlan_domains` は VXLAN 以外に狭い。`evpn_domains` は静的 VXLAN を除く |
| `role: border-gateway` を推奨の 9 語に足す | 構造から導けるので要らない。informative に留める |

## Pass C の結果

Pass C では、5 つのエージェントが Pass A の報告を読まず、[Pass B のまとめ](evaluations/adr0029/passb/summary.md) とユーザーの判断から設計し直した ([passc/](evaluations/adr0029/passc/))。モデル・構文・L3VNI の導き方は一致した。割れた所は統合で次のように決めた。

| 論点 | 意見 | 決定 |
|---|---|---|
| VTEP のないドメイン | warning (spec・dsl) / error (network) | warning |
| 1 つのドメインに L2VNI の VTEP が 1 つ | warning (spec) / 出さない (dsl・network) | 出さない |
| セッションとドメインの境界 | 出さない (spec・dsl) / info (network) | 出さない |
| `overlay_domain` のノードをエクスポーターに出すか | 出す (dsl) / 1.0 では出さない (spec) | 出す (書いたエンティティなので。ndl-viz の枠の名前に使える) |
| トンネルの対の形 | `{from, to}` (dsl・spec) / spec が `endpoints` を自信がない点に挙げた | `{endpoints: [a, b]}` (無向。ADR-0006) |
| 混在の検査の単位 | トポロジー全体 (spec・dsl・network) / L2VNI ごと (linguist の文案) | トポロジー全体 |

試し書き [passc/p1](evaluations/adr0029/passc/p1-evpn-multisite.yaml) (2 サイトの EVPN Multi-Site) は、`overlay_domains` と `overlay_domain:` を消すと今の validator を通る。残るのは BGW の 4 つの warning (ADR-0026 D5 の 10) だけで、D6 で消える。

## 改訂の注記 (実装で足した)

- ADR-0014 D2 の末尾: 「**改訂 ([ADR-0029](0029-overlay-domains.md))**: VTEP に任意のフィールド `overlay_domain` を足した。EVPN Multi-Site などで、トンネルを張る範囲 (中でフルメッシュに張る VTEP の集合) を書き分けるときに使う。書かなければ全 VTEP が 1 つの暗黙のドメインに属する」
- ADR-0026 D5 の 10 の末尾: 「**改訂 ([ADR-0029](0029-overlay-domains.md) D6)**: 2 つ以上のオーバーレイのドメインに VTEP を持つ機器 (BGW など) は、その L2VNI についてこの warning の対象から外す」

## References

- RFC 9014 (EVPN Overlay の Interconnect)、RFC 9135 (EVPN の IRB)、RFC 8365 (EVPN を使う NVO)、RFC 7432 (EVPN)
- 評価: [Pass A のまとめ](evaluations/adr0029/passa-summary.md)、[Pass B のまとめ](evaluations/adr0029/passb/summary.md)、[Pass C](evaluations/adr0029/passc/)
- 試し書き: a1 (今の構文で書けない所)、b1〜b4 (書く場所の比較・3 サイト・stretched)、passc の p1〜p3
