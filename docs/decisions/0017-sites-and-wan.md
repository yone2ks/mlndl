# ADR-0017: サイト・事業者網・回線情報の書き分け

- **Status**: Accepted (2026-11-03。スキーマ・validator は変更しない。文書を改訂し、ndl-viz の表示を実装した)
- **Date**: 2026-11-03
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー
- **Pass**: C (ラウンド6。[評価メモ](evaluations/adr0017/evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0017](drafts/0017-sites-and-wan.md)
- **関連**: ADR-0002 (D7 プレフィックス)、ADR-0003 (role は注釈側)、ADR-0005 (D2-1 箱と線、D4 補則 問い 1・問い 4)、ADR-0006 (endpoints)、
  [drafts/0008](drafts/0008-cloud-networks-scope-location.md) (箱もノード)、[ADR-0009](0009-membership-orthogonality.md) (labels)、
  [ADR-0010](0010-control-plane-separation.md) (D7 通り道、D8 OSPF / IS-IS、D10)、[ADR-0011](0011-layer3-data-plane.md) (D3 `name`、D6 トンネル、D7 description)、
  [ADR-0012](0012-subinterfaces.md)、`docs/label-vocabulary.md`、`docs/role-vocabulary.md`

## Context

ndl-viz は、`link_role: wan` のリンクを除いた L1 リンクの連結成分を「サイト」とみなして枠と名前を描いていた。
しかし `wan` は `link_role` の推奨値ではなく、サイトの名前も MLNDL のどこにも書かれていない。
「MLNDL に書かれた情報だけを出し、推定で埋めない」という ndl-viz の方針にも合わない。

ここから 2 つの問いが出た。

1. **サイト**をどう書くか
2. **WAN の回線**をどう書くか。NetBox は Circuit (A/Z の終端、事業者、回線 ID、種別) を管理している。
   2 点間の回線と事業者網 (IP-VPN・広域イーサ・インターネット・閉域接続) をどう書き分け、図にどう出すか

サイトの評価 (`evaluations/adr-site-boundary/`) は 5/5 が `link_role: wan` を推奨値にすることを退け、`labels: {site: ...}` を推した。
回線の評価 (`evaluations/adr-wan-circuits/`) では、`L1Link` に `provider` / `circuit_id` を足す案、独立エンティティ `layer1.circuits`、
事業者網を箱ノードにする案、その使い分けを試し書きで比べた。その途中でユーザーが次の見解を出した。

> labels は図上で可視化するために使う認識。provider とか circuit-id を記載したいなら description の中に表現すればいいレベル。

これを前提に Pass A のドラフトを書き、5 エージェントで評価した (Pass B、`evaluations/adr0017/evaluation.md`)。
Pass B のあと、ndl-viz に表示を実装して `examples/wan-sites.yaml` で確かめ、OSPF / IS-IS は箱をはさんでも error にならないことが分かった。
この ADR は、評価メモだけを入力に 5 エージェントが再設計した結果である (試し書きは `evaluations/adr0017/passc/`)。

### 用語

| 語 | この ADR での意味 |
|---|---|
| サイト (site) | 拠点。データセンターの建屋や事業所。`labels.site` の値 |
| 事業者網 (provider network) | 自社の外にある通信事業者・クラウド事業者の網。契約して接続するが、中の構成は自社が持たず、見えない |
| 箱 (box node) | 事業者網を 1 つのノードとして書いたもの。`role: provider-network` |
| 回線 (circuit) | 事業者と契約する 1 本の通信路 (NetBox の Circuit)。書くときは `L1Link` になる。2 点間の回線も、事業者網へのアクセス回線も回線である |

「回線」は図の「線」と紛れるので、構文の話をするときは `L1Link` と書く。

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
- **値はサイトの名前をそのまま書く** (`tokyo`、`osaka`、`dc1`)。`site-tokyo` のようにキーと同じ語を前に付けない。
  値は参照ではなく (ADR-0009 D2) ID と見分ける必要がない。図の枠の名前にそのまま出る。`az: ap-northeast-1a`・`tenant: acme` と同じ書き方である。
  `site-tokyo` と書いても valid で、検査はしない
- **`labels.site` は規約で、書かなくても valid**。ツールは、あれば使い、なければ何もしない。これは ADR-0009 D3
  「下流ツールは特定のキーの存在を前提にできない」に沿う (前提にするのではなく、なければ何もしない)。
  ndl-viz は同じ値を持つノードを 1 つの枠にまとめ、`labels.site` のないノードには枠も名前も出さない
- **サイト間のリンクは書かずに取り出せる**: 両端のノードの `labels.site` が違うリンクが、サイト間のリンクである。
  値を比べて取り出すだけで、サイトという箱を作るのではない
- サイトに属性 (住所・ラック数など) を持たせたくなったら、サイトを箱ノードにして `parent` で指す (drafts/0008、Phase 3+)。
  `labels.site` はそれまでの書き方で、昇格したあとも分類として残せる。`labels.site` に構造 (`{name:, address:}` など) を持たせない

### D2. `link_role` に WAN の推奨値を足さない

`wan`、`wan-l2` / `wan-l3`、`dci`、`access-circuit` などを推奨値にしない。`link_role` は自由文字列のまま (書くのは自由)。

- `wan` は「サイトの間にある」という**位置**で、D1 から取り出せる。事業者網へのリンクかどうかは、端が箱かどうかで分かる
- 種類で分けようとすると、2 点間の回線・広域イーサ・閉域接続を区別するために `wan-leased-l2` / `wan-wide-ether` と語が増えていく。
  区別は D3 の構造 (線か箱か) と箱の `name` で足りる
- 事業者網へのリンクを `access` と呼ぶのも推奨しない。`access` は既に推奨値にあり、ホストを収容するリンク (`trunk` と対になる) と読まれる
- **ツールは `link_role` からサイトの境界を導かない**

### D3. 2 点間の回線はリンク、事業者網は箱

回線は、**契約が「2 点間の回線」か「事業者網への接続」か**で 2 つに分ける (ADR-0005 D2-1「箱と線」)。
事業者のサービス仕様は、2 点を結ぶもの (end-to-end) と網への接続 (UNI) にもともと分かれていて、NetBox の Circuit と Provider Network の分け方とも同じである。

| 契約の形 | 書き方 |
|---|---|
| 2 点間の回線。両端が自分の機器 | **`L1Link`** (`endpoints` は両端の L1 IF) |
| 事業者網への接続 | **箱** + 各拠点から箱への `L1Link` |

| サービス | 書き方 |
|---|---|
| 専用線、L2 専用線 (EPL)、ダークファイバ、DWDM の波長 (自社の機器で終端する) | `L1Link`。事業者の中で伝送装置を通っても、契約は 2 点を結ぶものなので中は書かない |
| 広域イーサ。**2 拠点 (E-Line) でも** | 箱。同じサービスに拠点を足したときに書き方が変わらない。契約帯域とポート速度を分けて書ける |
| IP-VPN、モバイル閉域網 | 箱 |
| インターネット | ISP ごとに 1 つの箱。同じ ISP を使う拠点はその箱につなぐ |
| インターネット VPN | ISP の箱 + 両端の機器の `tunnel_interfaces` (ADR-0011 D6) |
| 閉域接続 (Direct Connect、ExpressRoute) | 事業者の箱 + 箱への `L1Link` + VIF ごとの 802.1Q サブ IF (`layer2.subinterfaces`、ADR-0012) + その上の L3 IF。クラウド側のルーターはトポロジー外の相手 (D5-1) |
| SD-WAN | 下回りは実際の契約どおり (ISP や IP-VPN の箱、専用線)。上のオーバーレイとコントローラーは扱わない (D6) |

判定に「事業者の装置が経路の対向になるか」を使わない。広域イーサの上で自社のルーターどうしが張る構成では、
事業者網なのに対向が自社の機器になり、箱か線かが経路の設計で変わってしまう。

箱の書き方:

```yaml
layer1:
  nodes:
    - id: net-ntt-ipvpn
      name: NTT IP-VPN              # 図に出す名前 (サービス名。事業者名を含めてよい)
      role: provider-network
      description: Contract VPN-01, QoS class S
  interfaces:
    - {id: net-ntt-ipvpn-tokyo, node: net-ntt-ipvpn, name: tokyo}   # 事業者側の接続点。name は接続している拠点の名前
    - {id: tokyo-ce-ge0, node: tokyo-ce, name: Ge0/0}
  links:
    - id: link-tokyo-ipvpn
      endpoints: [tokyo-ce-ge0, net-ntt-ipvpn-tokyo]
      link_speed: 1G
      description: Access circuit IPVPN-01-T (metro Ethernet, 300 Mbps contracted)
```

- `role` は `provider-network` の 1 語にする。インターネット・IP-VPN・広域イーサ・閉域接続を `role` で分けない。
  どれも「自社の外の網に複数の点で接続する」という同じ形で、違いはサービスの名前であり、`name` で読める (ADR-0005 D4 補則 問い 4: 方式名は構文に入れない)。
  語は NetBox の Provider Network に合わせた。`CANONICAL_ROLES` には入れず、`docs/role-vocabulary.md` の「グルーピングの箱」の慣用語彙に載せる
- **`name` の読み方**: ADR-0011 D3 の `name` は「機器上の名前で、参照ではない」。箱には機器がないので、箱の `name` はサービスの名前、
  箱の IF の `name` は事業者側の接続点の呼び名 (多くは拠点の名前) と読む。人が読む名前で参照ではない点は同じで、ツールは表示するだけでパースしない
- `implementation` は省略する (事業者網に vm / physical / container の区別は当てはまらない。`L1Node.implementation` は任意)
- 箱に `labels.site` は付けない (事業者網はどのサイトにも属さない)。管理軸 (`tenant` など) は付けてよい
- 箱は L3 IF を持たない (事業者の中は書かない)。**これは規約で、validator は検査しない**。検査するにはコアが `role` の値を見ることになり、
  `hypervisor` に続く 2 つ目の normative token になる (ADR-0003)
- 箱の ID にプレフィックスは定めない。ノードの ID にはプレフィックスを付けない (ADR-0002 D7)。試し書きの `net-` は慣例にすぎない

### D4. 回線の情報は `description` に書き、書式は決めない

| 情報 | 書く場所 |
|---|---|
| 2 点間の回線か事業者網か | 構造 (D3。リンクか箱か) |
| 事業者網のサービス名 (事業者名を含めてよい) | 箱の `name` |
| ポートの速度、MTU | `link_speed` (既存)。MTU はリンクには書かない ([ADR-0020](0020-remove-l1-link-mtu.md) で `mtu` をなくした。契約上の MTU は `description`) |
| 回線 ID、契約帯域、帯域保証の有無、契約番号、QoS クラス、`name` に書かなかった事業者名、クロスコネクトの位置 | リンクや箱の `description` |
| サイト | 両端のノードの `labels.site` (D1) |

- **`description` の書式は決めない。ツールは `description` をパースせず、一部を取り出しもしない** (そのまま表示するだけ)。
  書式を決めたり先頭の 1 文を使ったりすると、ツールがそれに頼り始め、事実上の構文になる。推奨の書き方の例も示さない。改行を含めてよい
- 図の線の脇などに機械で特定の情報 (回線 ID など) を出したくなったら、そのとき構文に上げる (加算的変更)
- **`labels` には書かない**。`labels` は同じ値で複数の要素をまとめる分類である (ADR-0009 D1。図で枠や色にする、クエリで選ぶ)。
  回線 ID のように 1 つの要素だけを識別する値は分類にならない。事業者名は分類にもなりうるが、今はまとめる用途がない
- **`L1Link.labels` は足さない**。リンクを分類で選ぶ用途が出たときに加算で足す
- `link_speed` はポートの速度で、契約帯域とは違う。1G のポートで 300M の契約なら `link_speed: 1G` とし、契約帯域は `description` に書く
- **書かないもの**: 認証鍵 (BGP の MD5 鍵、IPsec の事前共有鍵、SNMP コミュニティなど) と、担当者の名前や連絡先。
  トポロジーの記述は配られ、図にも出る (ADR-0005 D4 補則 問い 1)

### D5. 箱をはさむルーティングのセッション

**D5-1. 箱の向こうが事業者の機器のとき** (IP-VPN の PE、ISP のルーター、クラウドのルーター): 相手はトポロジー外の相手
`{address, local_as}` として書く (ADR-0010 D10)。事業者の中は書かないという D3 と合う。CE の設定も「PE のアドレスと事業者の AS」で済む。

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

1 本の回線に複数の VIF を載せるときは、サブ IF を VIF ごとに書く。どの VIF がどの VPC につながるかは書けず、`description` に書く。
クラウド側をノードとして書くかは drafts/0008 (Phase 3+) で扱う。ndl-viz は、トポロジー外の相手を線にせず機器のカードに出す (箱に向けて線を引かない)。

**D5-2. 両端が自分の機器で、事業者網が L2 を透過するとき** (広域イーサの上で拠点のルーターどうしが直接張る):
**この ADR では構文を変えない。今の書き方と限界を次のとおり定め、構文は次の ADR で決める。**

> **ADR-0018 で決着** (2026-11-03): 広域イーサの箱の中を `layer2.bridges` に書き、両端を `node` で書く。トンネルの上のセッションは `update_source` にトンネル IF を書く。
> 下の表の「片側をトポロジー外にする」書き方は valid のままだが推奨しない。3 拠点以上の OSPF / IS-IS は引き続き範囲外 (マルチアクセスの ADR)。

| プロトコル | 今の書き方 | 限界 |
|---|---|---|
| BGP | 片側をトポロジー外の相手 `{address, local_as}` として書く (`evaluations/adr0017/passc/P2a`) | 自分の機器を外として書くことになる。セッションの線は描かれない。片方の機器の側からしか書けない (逆向きをもう 1 本書くと validator は通るが、1 つのセッションを 2 エントリに書くことになり ADR-0010 の「1 エントリ = 1 セッション」に反する)。両端を `node` で書くと ADR-0010 D7 の通り道の検査で error になる (P2b) |
| OSPF / IS-IS (2 拠点) | 両端を `node` で書く | validator は通る (ADR-0010 D7 の通り道の検査は BGP のセッションだけにかかる)。通り道は導かれない |
| OSPF / IS-IS (3 拠点以上) | **範囲外** | 事業者網がマルチアクセスのセグメントになる。ADR-0010 D8 はポイントツーポイント前提で、N 台を 2 端点の組に展開すると意味が壊れる (DR / BDR)。組に展開すれば validator は通るが (P1)、その書き方は推奨しない |

次の ADR に渡す問い:

1. 事業者網が L2 を透過するか L3 で終端するかを書くか、どこに書くか (広域イーサは透過、IP-VPN は終端)。Phase 2 の `layer2.bridges` と書き方が 2 通りにならないか
2. 箱をはさむ通り道を ADR-0010 D7 がどう導くか。BGP にだけ通り道の検査があり OSPF / IS-IS にはないという非対称をどう揃えるか
3. マルチアクセスのセグメント (3 拠点以上の広域イーサ) の OSPF / IS-IS をどう書くか (ADR-0010 D8 の範囲外の解消)
4. トンネル IF を `update_source` にすること (BGP over GRE / IPsec)。`update_source` は `layer3.interfaces` しか指せず、`examples/wan-sites.yaml` は
   GRE の上の BGP を書けていない。「箱やトンネルを越える通り道」という同じ問題としてまとめて扱う
5. 両端を `node` で書いて error になったときのメッセージ。今は「同じリンクの両端を指してください」で、箱をはさむ書き手には意味が通らない

### D6. 扱わないもの

- **冗長回線の物理的な独立性** (同じ管路・収容局を通らないか): 回線について構造化する価値が最もある情報だが、リンクを束ねる構成子が要るので、必要になったら別の ADR で扱う。
  それまでは `description` に書く
- **事業者網の中の論理トポロジー** (フルメッシュ / ハブアンドスポーク): 経路の配布ポリシーで決まる (ADR-0005 D4 補則 問い 2)
- **SD-WAN のオーバーレイとコントローラー**
- **NetBox の Virtual Circuit** (事業者網の中の論理回線)
- D5-2 の構文 (次の ADR)

### D7. NetBox からの変換 (informative)

片方向の変換で足りる。アダプターは別リポジトリで、このリポジトリの変更対象ではない。

| NetBox | mlndl |
|---|---|
| A / Z の終端がどちらも自社のデバイスの Circuit | `L1Link`。回線 ID・事業者・Commit Rate は `description` |
| Provider Network に終端する Circuit | Provider Network ごとに箱 (`role: provider-network`、`name` はその名前) + 拠点から箱への `L1Link` |
| Circuit Type | 箱の `name` か `description` |
| Site | ノードの `labels.site` (Site の slug ではなく名前に近い値) |

## Consequences

**良い影響:**
- スキーマも validator も変えずに、サイト・2 点間の回線・事業者網を書ける。既存のトポロジーはそのまま valid
- 図に必要な区別 (線か雲か) が構造で決まり、`link_role` の語彙を増やさずに済む
- サイト間のリンクは `labels.site` から取り出せるので、`link_role: wan` と食い違うことがない
- `description` の書式を決めないので、ツールが自由記述をパースする依存が生まれない
- 昇格の道が加算的に残る: `labels.site` → `parent` のサイト箱、`description` の回線情報 → 構文、箱 → D5-2 の次の ADR や `layer2.bridges`

**悪い影響 / トレードオフ:**
- 回線 ID や事業者で検索・集計できない (人が読むだけ)。必要になったら構文に上げる
- 事業者網が L2 で透過するか L3 で終端するかを、機械は区別できない (人は `name` で読む)
- 広域イーサ越しの自社の機器どうしの BGP は、片側からトポロジー外の相手としてしか書けない。3 拠点以上の広域イーサの OSPF / IS-IS は範囲外 (D5-2)
- `labels.site` を書き忘れたノードはどのサイトにも入らない。validator は検出しない
- ndl-viz で、`labels.site` を書いていない既存のトポロジーからサイトの枠と名前 (旧動作の「DC Fabric」など) が消える。
  配置をつながりごとに離すのは続ける

**影響を受けるコンポーネント:**
- スキーマ・validator・`src/mlndl/constants.py`: 変更なし (`provider-network` は `CANONICAL_ROLES` に入れない)
- エクスポーター: `description` をそのまま出す (ADR-0011 D7 の実装)。`role: provider-network` も他の role と同じくそのまま出し、特別扱いしない
- 文書:
  - `docs/role-vocabulary.md` — 「グルーピングの箱」の表に `provider-network` を足す。「推奨しない語彙」に `isp` / `transit` / `carrier-network` / `cloud` を足す
  - `docs/label-vocabulary.md` — 冒頭に「labels は分類。1 つの要素だけを識別する値は `description` に」。`site` の値の例を `tokyo` にし、図の枠とサイト間のリンクを書く。
    「ndl-viz での利用」に `site` を足す。「推奨しない用法」に識別子を足す。「適用範囲の拡大」からリンクを外す
  - `docs/exporter-cytoscape.md` — `description` は表示するだけでパースしないこと
  - `CLAUDE.md`、`docs/decisions/README.md` — ADR の一覧と YAML の例
- examples / fixture: `examples/wan-sites.yaml` (見本) を足し、`tests/fixtures/valid_multisite_wan.yaml` に `labels.site` を足した
- ndl-viz (実装済み):
  - サイトの枠と名前を `labels.site` から描く。`labels.site` のないノードには出さない。複数のサイトにまたがる VLAN の札はどの枠にも入れない
  - `link_role === 'wan'` によるサイト検出と、`wan` の線の見た目をやめた
  - `role: provider-network` を雲で描き、サイトの上の列に並べる。`name` を出す
  - `description` は Properties にそのまま出す。線の上には出さない

## Alternatives Considered

- **サイトは `labels.site`、回線情報は `description`、事業者網は箱** *(採用案)*
- **`link_role: wan` を推奨値にし、サイトはその連結成分** (ndl-viz の旧動作): 却下 — サイトの名前が書けない。`wan` は位置で、
  両端のサイトから取り出せる。DCI のように WAN とも underlay とも言えるリンクで揺れる (サイトの評価で 5/5)
- **自社の 2 点間の回線を `link_role: wan`、事業者網へのリンクを `access` にする** (Pass C のネットワーク担当): 却下 — 前者は位置で D1 から取り出せる。
  後者は既存の推奨値 `access` (ホストを収容するリンク) と意味が衝突する
- **`labels.site` の値を `site-tokyo` にそろえる** (`docs/label-vocabulary.md` の旧例): 却下 — 値は参照ではなく、キーと同じ語を重ねる理由がない。図の枠の名前にもなる (Pass C で 5/5)
- **サイトを `parent` で書く**: 今回は見送り — `parent` は Phase 3+ で未実装。サイトに属性が要るようになったら D1 のとおり昇格する
- **`L1Node.site` を参照フィールドとして足す**: 見送り — サイトの箱が要るなら drafts/0008 の `parent` で書ける
- **`L1Link` に `provider` / `circuit_id` / `service` を足す**: 却下 — 片端が事業者網の回線を書けない。機械で読む用途がまだない (ユーザー判断)
- **独立エンティティ `layer1.circuits`** (NetBox の Circuit に対応): 却下 — 今の範囲では過剰。1 本の回線に複数のリンクが載る構成が必要になったら再検討する
- **`L1Link.labels` を足して `provider` / `circuit-id` を書く**: 却下 — 回線 ID は分類ではない (D4)。今は人が読めれば足りる (ユーザー判断)
- **`description` の書式を決める、推奨の書き方の例を 1 つ示す**: 却下 — ツールがパースし、事実上の構文になる
- **`role: internet` / `dx-connection` などを別に立てる**: 却下 — 形が同じで、違いはサービスの名前 (D3)
- **`role` の語の候補**: `carrier-network` (通信事業者に寄り、クラウドの閉域接続に合わない)、`transit` (BGP の transit と衝突)、`cloud`・`isp` (狭い)
- **箱が L3 IF を持たないことを validator で検査する、`role: provider-network` を通り道の導出で特別扱いする**: 却下 — コアが `role` の値を見ることになる (ADR-0003)
- **D3 の判定を「事業者の装置が経路の対向になるか」にする**: 却下 — 箱か線かが経路の設計で変わる (D3)
- **3 拠点以上の広域イーサの OSPF を 2 端点の組に展開して書くことを推奨する** (Pass C の試し書き担当): 却下 — ADR-0010 D8 が意味が壊れるとした書き方である。範囲外と明記し、次の ADR で扱う
- **箱をはさむセッションの構文 (`provider_transport: l2 | l3` など) をこの ADR で決める**: 見送り — ユーザー判断で次の ADR に分ける (D5-2)

## References

- 評価メモ: `evaluations/adr0017/evaluation.md` (Pass B、Pass B のあとに分かったこと、Pass C の結果)
- 試し書き: `evaluations/adr-site-boundary/` (サイト、T1〜T3 × 4 案)、`evaluations/adr-wan-circuits/` (回線、S1〜S5 × 4 案、`description-only/`)、
  `evaluations/adr0017/` (Pass A に沿った S1〜S6b)、`evaluations/adr0017/passc/` (P1〜P4)
- 見本: `examples/wan-sites.yaml`
- NetBox: Circuits (Provider、Provider Network、Circuit、Circuit Termination、Circuit Type、Virtual Circuit)
