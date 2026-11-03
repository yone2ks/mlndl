# ADR-0017: サイト・事業者網・回線情報の書き分け

- **Status**: Superseded by [0017](../0017-sites-and-wan.md) (2026-11-03 に Pass C で確定)
- **Date**: 2026-11-03
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author, ecosystem-reviewer、ユーザー
- **Pass**: A (改訂 1。初版に 5 エージェントの横断評価を反映した。評価メモは `evaluations/adr0017/evaluation.md`)
- **関連**: ADR-0002 D7、ADR-0003 (role は注釈側)、ADR-0005 (D2-1 箱と線、D4 補則)、ADR-0006 (endpoints)、
  [drafts/0008](0008-cloud-networks-scope-location.md) (箱もノード)、[ADR-0009](../0009-membership-orthogonality.md) (labels)、
  [ADR-0010](../0010-control-plane-separation.md) (D7 通り道、D10)、[ADR-0011](../0011-layer3-data-plane.md) D7 (description)、
  [ADR-0012](../0012-subinterfaces.md)、`docs/label-vocabulary.md`、`docs/role-vocabulary.md`

## Context

ndl-viz は、`link_role: wan` のリンクを除いた L1 リンクの連結成分を「サイト」とみなして枠と名前を描いていた。
しかし `wan` は `link_role` の推奨値ではなく、サイトの名前も MLNDL のどこにも書かれていない。
「MLNDL に書かれた情報だけを出し、推定で埋めない」という ndl-viz の方針にも合わない。

ここから 2 つの問いが出た。

1. **サイト**をどう書くか
2. **WAN 回線**をどう書くか。NetBox は Circuit (A/Z の終端、事業者、回線 ID、種別) を管理している。
   専用線と事業者網 (IP-VPN・広域イーサ・インターネット・閉域接続) をどう書き分け、図にどう出すか

1 回目の評価 (サイト) は 5/5 が `link_role: wan` を推奨値にすることを退け、`labels: {site: ...}` を推した。
2 回目の評価 (WAN 回線) では、`L1Link` に `provider` / `circuit_id` を足す案、独立エンティティ `layer1.circuits` を作る案、
事業者網を箱ノードにする案、その使い分けを試し書きで比べた (`evaluations/adr-wan-circuits/`)。

ここでユーザーが次の見解を出した。

> labels は図上で可視化するために使う認識。provider とか circuit-id を記載したいなら description の中に表現すればいいレベル。

`description` はすべてのエンティティにある (ADR-0011 D7)。3 回目の評価はこの見解を受けて行い、4/5 がスキーマを変えない形に同意した
(試し書きは `evaluations/adr-wan-circuits/description-only/`)。初版のドラフトを 5 エージェントで評価し、試し書きを
`evaluations/adr0017/` に置いた (S1〜S6a は valid、S6b は D5-2 のとおりエラー)。

### 用語

| 語 | この ADR での意味 |
|---|---|
| 事業者網 | 自社の外にある通信事業者・クラウド事業者の網。`role: provider-network` の箱ノードで書く |
| 箱 | 箱ノードの略。事業者網を表すノード |
| 回線 | 事業者と契約する 1 本の通信路 (NetBox の Circuit)。書くときは `L1Link` になる |
| サイト | 拠点。`labels.site` の値 |

## Decision

### D1. サイトは `labels.site` で書く

```yaml
layer1:
  nodes:
    - {id: tokyo-rtr, role: border, labels: {site: tokyo}}
    - {id: osaka-rtr, role: border, labels: {site: osaka}}
```

- 新しい構成子は作らない。`site` は `docs/label-vocabulary.md` に障害軸として既にある。サイトは障害の単位であり、
  同時に図でまとめる単位でもあるので、1 つのキーで両方に使う
- 値は自由文字列で、参照ではない (ADR-0009 D2)。図に出す名前になるので、プレフィックスは付けなくてよい
- **`labels.site` は規約で、書かなくても valid**。ツールは、あれば使い、なければ何もしない (ADR-0009 D3「下流ツールは特定の
  キーの存在を前提にできない」)。ndl-viz は `labels.site` のないノードにサイトの枠も名前も出さない
- **サイト間のリンクは書かずに取り出せる**: 両端のノードの `labels.site` が違うリンクが、サイト間のリンクである。
  これは値を比べて取り出すだけで、サイトという箱を作るのではない。`link_role` に `wan` と書いて二重に表す必要はない
- サイトに属性 (住所・ラック数など) を持たせたくなったら、サイトを箱ノードにして `parent` で指す (drafts/0008、Phase 3+)。
  `labels.site` はそれまでの書き方で、昇格したあとも分類として残せる

### D2. `link_role` に WAN の推奨値を足さない

`wan`、`wan-l2` / `wan-l3`、`dci` などを推奨値にしない。`link_role` は自由文字列のまま (書くのは自由)。

- `wan` は「サイトの間にある」という**位置**で、D1 から取り出せる
- `wan-l2` / `wan-l3` で回線の種類を表そうとすると、専用線・広域イーサ・閉域接続がすべて `wan-l2` になって区別できず
  (試し書き S1 / S3 / S5)、区別しようとすると `wan-leased-l2` / `wan-wide-ether` と語彙が増えていく
- **ツールは `link_role` からサイトの境界を導かない**。ndl-viz の連結成分によるサイト検出はやめる (Consequences)

### D3. 2 点間の回線はリンク、事業者網は箱

回線は、**契約が「2 点間の回線」か「事業者網への接続」か**で 2 つに分ける (ADR-0005 D2-1「箱と線」、D4 補則 問い 4)。

| 契約の形 | 書き方 | サービスの例 |
|---|---|---|
| 2 点間の回線。両端が自分の機器 | **`L1Link`** (`endpoints` は両端の L1 IF) | 専用線、L2 専用線、ダークファイバ、波長 (自社のトランスポンダで終端する DWDM) |
| 事業者網への接続 | **箱** + 各拠点から箱への `L1Link` | IP-VPN、広域イーサ、インターネット、閉域接続 (Direct Connect、ExpressRoute) |

- 2 点間の回線も事業者の中では伝送装置を通るが、契約は 2 点を結ぶものなので中は書かない (ダークファイバと同じ扱い)
- **広域イーサは 2 拠点 (ポイントツーポイント) でも箱にする**。同じサービスに拠点を足したときに書き方が変わらず、
  同じ事業者網に入る拠点が図で並ぶ
- 複数の拠点が同じ事業者網に入るときは 1 つの箱にまとめる。インターネットは ISP ごとに 1 つの箱にし、
  同じ ISP を使う拠点はその箱につなぐ (試し書き S4)
- 迷うサービスの書き方:

| サービス | 書き方 |
|---|---|
| インターネット VPN | ISP の箱 + 両端の機器の `tunnel_interfaces` (ADR-0011 D6) |
| 閉域接続 (Direct Connect の private VIF など) | 事業者の箱 + 箱への `L1Link` + 802.1Q のサブ IF (`layer2.subinterfaces`、ADR-0012) + その上の L3 IF。クラウド側のルーターはトポロジー外の相手 (D5-1) |
| SD-WAN | 下回りは ISP や IP-VPN の箱。上のオーバーレイとコントローラーは扱わない (D6) |

箱の書き方:

```yaml
layer1:
  nodes:
    - id: net-ntt-ipvpn
      name: NTT IP-VPN              # 図に出す名前 (サービス名。事業者名を含めてよい)
      role: provider-network        # 事業者網の箱。ndl-viz は雲で描く
      description: 契約 VPN-01、QoS クラス S
  interfaces:
    - {id: net-ntt-ipvpn-tokyo, node: net-ntt-ipvpn, name: tokyo}   # 事業者側の接続点。name は接続している拠点名
    - {id: tokyo-ce-ge0, node: tokyo-ce, name: Ge0/0}
  links:
    - id: link-tokyo-ipvpn
      endpoints: [tokyo-ce-ge0, net-ntt-ipvpn-tokyo]
      link_speed: 1G
      description: アクセス回線 IPVPN-01-T (メトロイーサ、契約 300M)
```

- `role` は `provider-network` の 1 語にする。インターネット・IP-VPN・広域イーサ・閉域接続を `role` で分けない。
  どれも「自社の外の網に複数の点で接続する」という同じ形で、違いはサービスの名前で、`name` で読める (問い 4: 方式名は構文に入れない)。
  語は NetBox の Provider Network に合わせた
- `implementation` は省略する (事業者網に vm / physical / container の区別は当てはまらない。`L1Node.implementation` は任意)
- 箱に `labels.site` は付けない (事業者網はどのサイトにも属さない)。管理軸 (`tenant` など) は付けてよい
- 箱の IF は事業者側の接続点を表し、`name` には接続している拠点名を書く
- 箱は L3 IF を持たない (事業者の中は書かない)。**これは規約で、validator は検査しない** (検査するには `role` の値を見ることになり、
  ADR-0003 に反する)
- 箱の ID にプレフィックスは定めない。ノードの ID にはプレフィックスを付けない (ADR-0002 D7)。試し書きの `net-` は慣例にすぎない

### D4. 回線の情報は `description` に書き、書式は決めない

回線 ID、契約帯域、契約番号、収容局、アクセス回線の種類などは、リンクや箱の `description` に人が読む文で書く。

| 情報 | 書く場所 |
|---|---|
| 2 点間の回線か事業者網か | 構造 (D3。リンクか箱か) |
| 事業者網のサービス名 (事業者名を含めてよい) | 箱の `name` |
| ポートの速度、MTU | `link_speed`、`mtu` (既存。MTU は VTEP の検査にも使う) |
| 回線 ID、契約帯域、契約番号、`name` に書かなかった事業者名 | `description` |
| サイト | 両端のノードの `labels.site` (D1) |

- **`description` の書式は決めない。ツールは `description` をパースせず、一部を取り出しもしない** (そのまま表示するだけ)。
  書式を決めたり先頭の 1 文を使ったりすると、ツールがそれに頼り始め、事実上の構文になる。改行を含めてよい
- 図の線の脇などに機械で特定の情報 (回線 ID など) を出したくなったら、そのとき構文に上げる (加算的変更)
- **`labels` には書かない**。ADR-0009 D1 の Classification は、同じ値で複数のノードやリンクをまとめるための分類である
  (図で枠や色にする、クエリで選ぶ)。回線 ID のように、同じ値を複数の要素が共有しない識別子は分類にならない。
  事業者名は分類にもなりうるが、今はまとめる用途がなく、`L1Link` は `labels` を持たない
- **`L1Link.labels` は足さない**。リンクを分類で選ぶ用途が出たときに加算で足す (`docs/label-vocabulary.md` の
  「適用範囲の拡大」のうちリンクはこの ADR で見送る)
- `link_speed` はポートの速度で、契約帯域 (1G のポートで 100M 契約など) とは違う。契約帯域は `description` に書く
- 認証鍵 (BGP の MD5 鍵など) は `description` にも書かない (ADR-0005 D4 補則 問い 1)

### D5. 箱をはさむルーティングのセッション

ADR-0010 D7 は、両端の `update_source` (直結の IF) が同じリンクの上にあることを求める。箱をはさむと、
両端は箱の両側の別のリンクに載るので、両端ともトポロジー内の機器としてセッションを書くとエラーになる。

```
両端の update_source ('tokyo-rtr-ge0-l3' と 'osaka-rtr-ge0-l3') が同じリンク / LAG / VLAN の上にありません
```

**D5-1. 箱の向こうが事業者の機器のとき** (IP-VPN の PE、ISP のルーター、クラウドのルーター): 相手はトポロジー外の相手
`{address, local_as}` として書く (ADR-0010 D10)。事業者の中は書かないという D3 と合う。

```yaml
layer2:
  subinterfaces:
    - {id: subif-onprem-rtr-ge0-101, attaches_to: {interface: onprem-rtr-ge0}, vlan_id: 101, name: Ge0/0.101}
layer3:
  interfaces:
    - {id: onprem-rtr-vif-prod, node: onprem-rtr, name: Ge0/0.101, ip: 169.254.100.1/30,
       attaches_to: {subinterface: subif-onprem-rtr-ge0-101}}
control_plane:
  routing_neighbors:
    - {id: bgp-peer-onprem-aws, type: bgp,
       from: {node: onprem-rtr, update_source: onprem-rtr-vif-prod},
       to: {address: 169.254.100.2, local_as: 64512}, address_families: [ipv4_unicast]}
```

閉域接続 (試し書き S5) もこの書き方にする。1 本の回線に複数の VIF を載せるときは、サブ IF を VIF ごとに書く。
どの VIF がどの VPC につながるかは書けず、`description` に書く。クラウド側をノードとして書くかは drafts/0008 (Phase 3+) で扱う。

**D5-2. 両端が自分の機器で、事業者網が L2 を透過するとき** (広域イーサの上で拠点のルーターどうしが直接 BGP / OSPF を張る。
金融・自治体の数拠点の構成などで普通にある): **この ADR では構文を変えず、当面は (a) で書く。(d) を別の ADR で検討する。**

| 候補 | 内容 | 判断 |
|---|---|---|
| (a) 今のまま | 相手をトポロジー外の相手として書く | **当面これで書く**。自分の機器を外として書くことになり、セッションの線も描かれない。片方の機器の側からしか書けない (逆向きをもう 1 本書くと validator は通るが、1 つのセッションを 2 エントリに書くことになり ADR-0010 の「1 エントリ = 1 セッション」に反する) |
| (b) 箱の IF を VLAN のポートに書く | 箱の IF を `layer2.vlans` のポートにし、derive が同じ L2 とみなす | **却下**。拠点がタグなしだと `vlan_id` に書く値がない (事業者の中のタグは分からない)。VLAN が「自社の 802.1Q のセグメント」と「事業者網越しの仮想的なセグメント」の 2 つの意味を持ち、VLAN ID の重複などの検査が誤って働く。拠点のルーターの IF を SVI (`{vlan:}`) として書けば今の derive でも通るが、実際はルーテッドポートなので実物と違う |
| (c) `role: provider-network` を validator が特別扱いする | 箱を透過とみなして通り道を延ばす | **却下**。`role` は注釈側で、コアは値を見ない (ADR-0003)。`hypervisor` に続く 2 つ目の normative token になる |
| (d) 箱に透過を表すフィールドを足す | 例: `L1Node` に任意の `provider_transport: l2 \| l3`。derive は、両端の直結の IF が同じ `l2` の箱につながっていれば箱越しの通り道とする | **別の ADR で検討する**。任意フィールドの追加なので ndl_version 1.x の加算的変更で済む。L2 で透過するか L3 で終端するかを図で区別できる (ネットワーク担当が図に要るとした点)。Phase 2 の `layer2.bridges` の設計と重なるので、そこで合わせて決める |

### D6. 扱わないもの

- **冗長回線の物理的な独立性** (同じ管路・収容局を通らないか): ネットワーク担当は、回線について構造化する価値がある唯一の情報と評価した。
  必要になったら別の ADR で扱う (リンクを束ねる構成子が要る)
- **事業者網の中の論理トポロジー** (フルメッシュ / ハブアンドスポーク): 経路の配布ポリシーで決まる (ADR-0005 D4 補則 問い 2)
- **SD-WAN のオーバーレイとコントローラー**
- **トンネル IF を `update_source` にすること** (BGP over GRE / IPsec): `update_source` は `layer3.interfaces` しか指せない。
  ADR-0010 の課題として別に扱う。D5-2 (d) と同じく「箱やトンネルを越える通り道」の問題なので、まとめて検討してよい
- **NetBox の Virtual Circuit** (事業者網の中の論理回線): 必要になるまで書かない

### D7. NetBox からの変換 (informative)

片方向の変換で足りる (ecosystem-reviewer)。アダプターは別リポジトリで、このリポジトリの変更対象ではない。

| NetBox | mlndl |
|---|---|
| A / Z の終端がどちらも自社のデバイスの Circuit | `L1Link`。回線 ID・事業者・Commit Rate は `description` |
| Provider Network に終端する Circuit | Provider Network ごとに箱 (`role: provider-network`、`name` はその名前) + 拠点から箱への `L1Link` |
| Circuit Type | 箱の `name` か `description` |
| Site | ノードの `labels.site` |

## Consequences

**良い影響:**
- スキーマも validator も変えずに、サイト・2 点間の回線・事業者網を書ける。既存のトポロジーはそのまま valid
- 図に必要な区別 (線か雲か) が構造で決まり、`link_role` の語彙を増やさずに済む
- サイト間のリンクは `labels.site` から取り出せるので、`link_role: wan` と食い違うことがない
- `description` の書式を決めないので、ツールが自由記述をパースする依存が生まれない

**悪い影響 / トレードオフ:**
- 回線 ID や事業者で検索・集計できない (人が読むだけ)。必要になったら構文に上げる
- 事業者網が L2 で透過するか L3 で終端するかを、機械は区別できない (人は `name` で読む)。D5-2 (d) で解消する見込み
- 両端が自分の機器のセッションを、広域イーサ越しには片側からトポロジー外の相手としてしか書けない (D5-2 (a))
- `labels.site` を書き忘れたノードはどのサイトにも入らない。validator は検出しない
- ndl-viz で、`labels.site` を書いていない既存のトポロジーからサイトの枠と名前が消える。`public/` のサンプルに `link_role: wan` を使うものはないので、
  サイトの分かれ方は変わらない (配置を連結成分ごとに離すのは続けてよい)

**影響を受けるコンポーネント:**
- スキーマ・validator・`src/mlndl/constants.py`: 変更なし (`provider-network` は CANONICAL_ROLES に入れない)
- エクスポーター: `description` をそのまま出す (実装済み、未コミット)。`role: provider-network` も他の role と同じくそのまま出し、特別扱いしない。
  `docs/exporter-cytoscape.md` の `description` の節に「ツールは表示するだけで、パースしない」を書く
- 文書:
  - `docs/role-vocabulary.md` — 「informative 慣用語彙: グルーピングの箱」の表に `provider-network` を足す (`implementation` を書かない点は `vpc` と共通)
  - `docs/label-vocabulary.md` — 冒頭に「labels は同じ値で複数の要素をまとめる分類。回線 ID のような識別子は `description` に」を足す。
    `site` の説明に「図の枠にも使う。サイト間のリンクは両端の site から取り出す」を足す。「適用範囲の拡大」からリンクを外す
  - `CLAUDE.md` — ADR 一覧に追加。「NDL YAML フォーマット概要」の `labels` の例に `site` を足す
- ndl-viz:
  - サイトの枠と名前を `labels.site` から描く。`labels.site` のないノードには出さない
  - `link_role === 'wan'` によるサイト検出をやめる
  - `role: provider-network` を雲で描き、`name` を出す
  - `description` は Properties にそのまま出す (実装済み)。線の上には出さない

## Alternatives Considered

- **案A: サイトは `labels.site`、回線情報は `description`、事業者網は箱** *(採用案)*
- **`link_role: wan` を推奨値にし、サイトはその連結成分** (ndl-viz の旧動作): 却下 — サイトの名前が書けない。`wan` は位置で、
  両端のサイトから取り出せる。DCI のように WAN とも underlay とも言えるリンクで揺れる (1 回目の評価で 5/5)
- **サイトを `parent` で書く**: 今回は見送り — `parent` は Phase 3+ で未実装。サイトに属性が要るようになったら D1 のとおり昇格する
- **`L1Node.site` を参照フィールドとして足す** (DSL 担当が昇格先の一案として挙げた): 見送り — サイトの箱が要るなら drafts/0008 の `parent` で書ける
- **`L1Link` に `provider` / `circuit_id` / `service` を足す** (試し書き A): 却下 — 片端が事業者網の回線を書けない。
  機械で読む用途がまだない (ユーザー判断)
- **独立エンティティ `layer1.circuits`** (試し書き B、NetBox の Circuit に対応): 却下 — 今の範囲では過剰。
  1 本の回線に複数のリンクが載る構成が必要になったら再検討する
- **`L1Link.labels` を足して `provider` / `circuit-id` を書く**: 却下 — 回線 ID は分類ではない (D4)。言語担当は「回線 ID は
  識別子で、K8s の annotations に近い。機械で取り出せる場所がよい」と反対したが、今は人が読めれば足りる (ユーザー判断)
- **`description` の書式を決める** (`key=value` など。試し書き担当): 却下 — 書式を決めるとツールがパースし、事実上の構文になる (DSL 担当)
- **`link_role: wan-l2` / `wan-l3` / `wan-internet`**: 却下 — D2
- **`role: internet` / `dx-connection` を別に立てる** (2 回目の試し書き S4 / S5): 却下 — 形が同じで、違いはサービスの名前 (D3)
- **`role` の語の候補**: `carrier-network` (通信キャリアに寄り、閉域接続に合わない)、`transit` (BGP の transit と衝突)、`cloud`・`isp` (狭い)。
  NetBox の用語に合う `provider-network` を採る (言語担当)
- **D3 の判定を「事業者の装置が経路の対向になるか」にする** (仕様担当): 採らない — 広域イーサの上で自社のルーターどうしが張る構成では、
  事業者網なのに対向が自社の機器になり、箱か線かが経路の設計で変わってしまう。契約の形で分ける

## References

- 試し書き: `evaluations/adr-site-boundary/` (サイト、T1〜T3 × 4 案)、`evaluations/adr-wan-circuits/` (WAN 回線、S1〜S5 × 4 案)、
  `evaluations/adr-wan-circuits/description-only/` (ユーザーの見解に沿った S1〜S5)、
  `evaluations/adr0017/` (初版ドラフトに沿った S1〜S6。S1〜S6a は valid、S6b は D5-2 のエラー)
- 評価メモ: `evaluations/adr0017/evaluation.md`
- NetBox: Circuits (Provider、Provider Network、Circuit、Circuit Termination、Circuit Type、Virtual Circuit)
- ADR-0009 D1 (Classification)、ADR-0011 D7 (description)、ADR-0010 D7・D10
