# ADR-0018: 事業者網やトンネルを越えるセッションの通り道

- **Status**: Accepted (2026-11-03 に実装。スキーマ・derive・validator・エクスポーター・fixture・examples。ndl-viz は 2026-11-04 に対応: セッションの札に bridge の名前・トンネルの種類を添え、bridge は事業者網の箱に載せる)
- **Date**: 2026-11-03
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー (bridges の先取り・トンネルを同じ ADR で・マルチアクセスは次の ADR)
- **Pass**: C (ラウンド7。[評価メモ](evaluations/adr0018/evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0018](drafts/0018-sessions-across-bridges-and-tunnels.md)
- **関連**: ADR-0002 (D5 id の一意性、D7 プレフィックス、D8 severity)、ADR-0003 (role は注釈側)、ADR-0005 (D4 補則 問い 4、D6)、
  [drafts/0007](drafts/0007-vnic-vswitch-bridges.md) (`layer2.bridges` の元の構想)、[ADR-0010](0010-control-plane-separation.md) (D7 通り道、D8、D10)、
  [ADR-0011](0011-layer3-data-plane.md) (D6 トンネル、D11)、[ADR-0013](0013-vlan-ports-on-lag.md) (ポートの形、D7)、
  [drafts/0015](drafts/0015-declarative-references.md) (Ref)、[ADR-0017](0017-sites-and-wan.md) (D3 線と箱、D4 description、D5-2)

## Context

ADR-0017 D5-2 は、事業者網をはさんで自社の機器どうしが張るセッションの構文を決めず、次の 5 つの問いをこの ADR に渡した。

1. 事業者網が L2 を透過するか L3 で終端するかを書くか。書くならどこに書くか。Phase 2 の `layer2.bridges` と書き方が 2 通りにならないか
2. 箱をはさむ通り道を ADR-0010 D7 がどう導くか。BGP にだけ通り道の検査があり、OSPF / IS-IS にはない。この非対称をどう揃えるか
3. マルチアクセスのセグメント (3 拠点以上の広域イーサ) の OSPF / IS-IS をどう書くか
4. トンネル IF を `update_source` にすること (BGP over GRE / IPsec)
5. 両端を `node` で書いて error になったときのメッセージ

今の状態は次のとおりである。

- **BGP**: 通り道は、両端の `update_source` の L3 IF の基盤から導く (ADR-0010 D7、`derive._transport`)。
  - 両端が同じ L1 リンク (または LAG のメンバーどうし) にないと error になる。そのため、広域イーサの箱をはさむと両端を `node` で書けない (`evaluations/adr0017/passc/P2b`)。
  - 今は片側をトポロジー外 `{address, local_as}` にして逃げている (P2a)。
- **OSPF / IS-IS**: 通り道の検査も導出もない。2 拠点なら両端 `node` で書いても通るが、通り道は出力されない。
- **トンネル**: `update_source` は `Ref("layer3.interfaces")` なので、`layer3.tunnel_interfaces` の id を指すと参照の error になる。そのため `examples/wan-sites.yaml` には GRE の上の BGP を書けていない。

どれも「セッションの通り道が L1 リンク 1 本ではない」という同じ問題である。

Pass A の前に、5 エージェントが 5 つの案を評価し、試し書きをした (`evaluations/adr0018/passa/`)。

| 案 | 内容 |
|---|---|
| V | 箱の L1 IF を `layer2.vlans` のポートにする |
| B | `layer2.bridges` を先取りする |
| F | `provider_transport: l2 \| l3` を足す |
| T | `update_source` がトンネル IF を指せる |
| M | マルチアクセスの隣接をセグメント単位で書く |

そのうえでユーザーが次の 3 点を決めた。

- L2 透過は B で書く
- トンネルは同じ ADR で扱う
- マルチアクセスは次の ADR に回す

Pass B は 5 エージェントの横断評価と試し書き B1〜B5 で、割れた論点はなかった。この ADR は、評価メモだけを入力に 5 エージェントが再設計した結果である。試し書きは `evaluations/adr0018/passc/` に置いた。

### 用語

| 語 | この ADR での意味 |
|---|---|
| 通り道 | セッションのパケットが 1 ホップで通るリンク層の実体。L1 リンク・LAG・bridge・トンネルの対のどれか (ADR-0010 D7 の語) |
| bridge | 802.1Q の番号を持たない 1 つの L2 セグメント。`layer2.bridges` の 1 エントリ |
| bridge に届く | L3 IF の基盤の L1 リンクの対向が、その bridge のポートであること (D2) |
| トンネルの対 | 互いに相手の `source` を `destination_interface` に指している 2 本のトンネル IF (D3) |
| 食い違い | 両端から導いた通り道が一致しないこと |

## Decision

### D1. 事業者網の中の L2 の転送は `layer2.bridges` に書く

drafts/0007 で Phase 2 に予定していた `layer2.bridges` のうち、最小の形だけを先に入れる。

```yaml
layer1:
  nodes:
    - {id: net-wideether, name: NTT Com 広域イーサ, role: provider-network}
  interfaces:
    - {id: net-wideether-tokyo, node: net-wideether, name: tokyo}
    - {id: net-wideether-osaka, node: net-wideether, name: osaka}
  links:
    - {id: link-tokyo-wideether, endpoints: [tokyo-rtr-ge0, net-wideether-tokyo]}
    - {id: link-osaka-wideether, endpoints: [osaka-rtr-ge0, net-wideether-osaka]}
layer2:
  bridges:
    - id: bridge-wideether             # 推奨プレフィックス bridge-。回線 ID は id に埋めない
      name: WE-220                     # 任意。人が読む名前
      ports:                           # この bridge でフレームを転送するポート
        - {interface: net-wideether-tokyo}   # 箱のポート
        - {interface: net-wideether-osaka}
        # tokyo-rtr-ge0 / osaka-rtr-ge0 (拠点のルーターのポート) は書かない
      description: 契約 WE-220。ポートベース   # 任意 (ADR-0017 D4)
```

- **フィールド**: `id` / `name` / `ports` / `description` の 4 つ。
  - `ports` のあいだでは、Ethernet フレームが L2 のまま転送される。
  - VLAN と違い、bridge は 802.1Q の番号を持たない。
- **`ports` に書くのは、フレームを転送する側のポート**: 事業者網なら箱の L1 IF を書く。
  - 拠点のルーターのルーテッドポートは書かない。ルーターはフレームを転送せず、箱のポートに L1 リンクでつながって bridge を**使う**側だからである。
  - これは機器の bridge のポート (Linux の `bridge-ports`、IEEE 802.1D) と同じ意味である。
  - RFC 8345 の supporting の向きとも合う。下の層の箱が、上の層のセッションを実現する。
- **ポートの形は VLAN のポートと同じ** (ADR-0013): `{interface: <L1 IF>}` か `{lag: <LAG>}` のちょうど一方を書く。
  - `node` は書かず、参照先から導く (ADR-0005 D6)。
  - bridge のポートは `native` を持たない。
  - [ADR-0023](0023-per-device-lag-and-ethernet-segments.md) D5 (2026-11-08) で `{ethernet_segment:}` も書けるようにした。事業者網を PE ごとのノードで書き、拠点が 2 台の PE に冗長に接続する場合に使う。
- **方式名は書かない** (ADR-0005 D4 補則 問い 4): E-LINE / E-LAN / VPLS / EVPN のどれで実現しているかは構文に出さない。
  - 2 拠点も 3 拠点以上も、違うのは `ports` の数だけである。
  - 方式・契約 ID・EVC ID は `name` や `description` に書く。
- **bridge を書かなければ透過しない**: IP-VPN やインターネットの箱には bridge を書かない。
  - 問い 1 の「L2 透過か L3 終端か」は、フラグではなく bridge の有無で表す。
  - validator は箱の `role` を見ない (ADR-0003)。
- **bridge を書くのは箱をはさむときだけ**:
  - L2 専用線 (EPL)・ダークファイバ・波長は、ADR-0017 D3 のとおり L1Link で拠点どうしを直接つなぐ。bridge は書かない。
  - 自社の L2 スイッチのポートの所属は `layer2.vlans` で書く。bridge は、番号を持たない L2 セグメント (事業者網の中) に使う。
- **id**: 回線 ID は契約で変わるので、id に埋めず `name` / `description` に書く。
  - 同じ種類の事業者網が 2 つあるときは、事業者で分ける (`bridge-wideether-ntt` / `bridge-wideether-kddi`)。
- **drafts/0007 との関係**: 同じ構成子である。
  - drafts/0007 の `members: [{node, interface}]` は、この ADR の `ports` に読み替える。
  - vSwitch のための `type` / `nodes` / `uplinks` と、VLAN との関係 (`vlans[].bridge`) はこの ADR では決めない。後で足すときは任意のフィールドとして加算し、1.x の間は bridges の必須フィールドを増やさない。
  - 名前は linguist の整理に従い、外へ向かう転送ポートを `ports`、中に収容するもの (vNIC) を `members` と呼び分ける余地を残す。

**検査** (error):
- `ports` の参照先が、そのキーの種類 (L1 IF / LAG) で定義されているか。これは汎用の参照検査で、キー付き参照になる。
- 同じポートを 2 つの bridge に書いていないか。
- 同じ bridge に同じポートを 2 回書いていないか。
- 同じ bridge に LAG とそのメンバーを併記していないか (ADR-0013 と同じ)。

**検査** (warning):
- `ports` が 1 つしかない。相手の拠点がトポロジー外のこともあるので error にはしない。
- ポートの L1 リンクの対向が、同じ bridge の別のポートになっている。拠点のルーターのポートを書いた疑いがある。
- 同じ L1 IF / LAG が、VLAN のポートと bridge の `ports` の両方にある。箱のポートを VLAN に書いた疑いがある。vSwitch の uplink では正当になるので、drafts/0007 で見直す。
- LAG のメンバーだけを書いて LAG を書いていない。`{lag:}` を促す (ADR-0013 と同じ)。
- 推奨プレフィックス `bridge-` で始まっていない (ADR-0002 D7 に足す)。

### D2. 通り道を bridge に延ばす (ADR-0010 D7 の拡張)

L3 IF が bridge に**届く**とは、その L3 IF の基盤 (L1 IF か LAG) の L1 リンクの対向のポートが、bridge の `ports` にあることをいう。
- サブ IF のときは、サブ IF の基盤を見る。
- LAG のときは、メンバーの対向のどれかが `ports` にあるか、対向の LAG が `ports` にあれば届く。

たどるのは ADR-0013 D7 と同じく 1 ホップだけである。サブ IF の層はホップに数えない。

| 両端 | 通り道 | |
|---|---|---|
| 同じリンク (または LAG のメンバーどうし) | `{link:}` / `{lag:}` | 今と同じ |
| 両端が同じ bridge に届く | `{bridge: <bridge id>}` | **新規**。single-hop として扱う |
| 片方だけが bridge に届く、別々の bridge に届く、片方だけが直結 | — | 食い違い (BGP は error) |
| どちらかが基盤を持たない (ループバック等) | — | multihop。今と同じ |
| どちらかがトポロジー外の相手 | — | 導かない。今と同じ |

- **1 ホップだけ**: 拠点のルーターと箱のあいだに自社の L2 スイッチがはさまると、ルーターのポートの対向はスイッチになるので bridge に届かない。
  - 2 つの bridge (または VLAN と bridge) が L1 リンクでつながっていても、同じセグメントとはみなさない (D8)。
- **IS-IS**: `interface` は L1 IF を指すので、その L1 IF の対向のポートが `ports` にあるかで判定する。L3 IF から基盤をたどる 1 段を省く。
- **サブ IF のタグは、bridge をはさむときは比べない**: タグ変換のある契約 (EVPL。東京は 100、大阪は 200) では、両拠点のタグが違うのが正しい。
- **3 つ以上の `ports` を持つ bridge の上の BGP**: 組ごとのセッション (フルメッシュや RR) として今の構文で書ける。

```yaml
control_plane:
  routing_neighbors:
    - id: bgp-peer-tokyo-osaka
      type: bgp
      from: {node: tokyo-rtr, update_source: tokyo-rtr-ge0-l3}   # tokyo-rtr-ge0 の対向は net-wideether-tokyo (bridge-wideether のポート)
      to:   {node: osaka-rtr, update_source: osaka-rtr-ge0-l3}   # osaka-rtr-ge0 の対向は net-wideether-osaka (bridge-wideether のポート)
      address_families: [ipv4_unicast]
      # 通り道は {bridge: bridge-wideether} と導かれる
```

### D3. トンネル IF を `update_source` と OSPF の `interface` に書ける

- **書ける場所**: BGP の `update_source` と OSPF の `interface` は、`layer3.interfaces` に加えて `layer3.tunnel_interfaces` の id も指せる。
  - 値は文字列のままで、今の YAML は変わらない。
  - 機器の設定 (`update-source Tunnel0`) でも、ループバックとトンネルは同じ形で指す。
  - どちらを指しても、`update_source` の意味 (このセッションの自分の側の IF) は変わらない。
- **型**: ADR-0015 の `Ref` を、複数のコレクションを指せるように広げる (`Ref("layer3.interfaces", "layer3.tunnel_interfaces")`)。
  - 参照の検査は、各コレクションの id の和集合で引く。
  - エラーメッセージの参照先の呼び名は「L3 インターフェース / トンネル」と連結する。
  - 既存の 1 つのコレクションを指す `Ref` は変わらない。
- **id の一意性**: id はトポロジー全体で一意 (ADR-0002 D5) なので、どちらのコレクションかは id から決まる。
  - ADR-0002 D5 の全レイヤーを横断する一意性の検査はまだ一部しか実装されていない。そのうち、`layer3.interfaces` と `layer3.tunnel_interfaces` のあいだの重複の error を、この ADR で先に実装する。新しい制約ではない。
- **通り道**: 両端がどちらもトンネル IF で、互いに対になっていれば、通り道は `{tunnel: [<from 側のトンネル>, <to 側のトンネル>]}` になる。
  - 対になるとは、from 側のトンネルの `destination_interface` が to 側のトンネルの `source` を指し、to 側の `destination_interface` が from 側の `source` を指すことをいう。
  - 並びは from、to の順にする。今の `{lag: [<この端の LAG>, <相手の LAG>]}` と同じ形である。
  - 次の場合は食い違いになる。
    - 片方だけがトンネル IF
    - 両方ともトンネル IF だが、対になっていない
  - 対の判定は両端が `node` のときだけ行う。相手がトポロジー外 (`{address, local_as}`) なら、`destination_ip` のトンネルでも今のとおり通り道を導かない。
  - 両端が `node` でも、どちらかのトンネルが `destination_ip` なら対を確かめられないので、通り道を導かず食い違いともしない。
- **VRF**: トンネル IF を指したとき、「`update_source` の VRF」はトンネル IF の `vrf` (overlay 側) である。`transport_vrf` ではない。
- **トンネルの下の通り道は導かない**: セッションの通り道はトンネルで止める。外側のパケットの通り道は `source` の L3 IF から別にたどれる。
- **実装**:
  - `derive._l3_basis` は、トンネル IF を 4 つ目の種類 (`tunnel`) として扱う。
  - ADR-0011 D11 の L3 IF の分類 (`l3_attachments`) には入れない。トンネル IF は L3 IF とは別のコレクションで、`attaches_to` を持たない。
- **IS-IS の `interface`**: L1 IF を指すので、この ADR では広げない。IS-IS は IP ではなく L2 (LLC) で IIH を送り、GRE / VTI / WireGuard の上には載らない。

```yaml
layer3:
  tunnel_interfaces:
    - {id: tunnel-tokyo-fukuoka, node: tokyo-rtr, type: gre, source: tokyo-rtr-inet, destination_interface: fukuoka-rtr-inet, ip: 172.31.0.1/30}
    - {id: tunnel-fukuoka-tokyo, node: fukuoka-rtr, type: gre, source: fukuoka-rtr-inet, destination_interface: tokyo-rtr-inet, ip: 172.31.0.2/30}
control_plane:
  routing_neighbors:
    - id: bgp-peer-tokyo-fukuoka-gre
      type: bgp
      from: {node: tokyo-rtr,   update_source: tunnel-tokyo-fukuoka}
      to:   {node: fukuoka-rtr, update_source: tunnel-fukuoka-tokyo}
      address_families: [ipv4_unicast]
      # 通り道は {tunnel: [tunnel-tokyo-fukuoka, tunnel-fukuoka-tokyo]}
```

### D4. OSPF / IS-IS にも通り道を導く

- OSPF と IS-IS の両端からも、D2・D3 と同じ規則で通り道を導き、エクスポーターに出す。これで問い 2 の非対称を解消する。
  - OSPF の `interface` は L3 IF かトンネル IF。
  - IS-IS の `interface` は L1 IF。
- **食い違いの severity**: ndl_version 1.x の間は warning にとどめ、2.0 で error にする。
  - 今まで valid だった OSPF / IS-IS の YAML を、1.x の間に error にしない。
  - BGP の食い違いは今のまま error である。BGP の通り道の検査は ADR-0010 D7 の初めからの約束で、OSPF / IS-IS の検査はこの ADR で新しく足すものだからである。
- **ADR-0010 D8 との関係**: この決定は 2 端点のセッションの通り道を導くだけで、ADR-0010 D8 のポイントツーポイント前提は変えない。
  - 3 つ以上の `ports` を持つ bridge の上の OSPF / IS-IS を、組に展開して書くことは推奨しない。
  - マルチアクセスの隣接の書き方は次の ADR で決める。bridge がセグメントを表すので、その上に加算する。

### D5. エクスポーター

- **`transport_link` の値**: `{"bridge": <bridge id>}` と `{"tunnel": [<from 側>, <to 側>]}` を足す。
  - 今の `{"link":}` / `{"lag":}` は変えない。キー名も変えない。bridge もトンネルも、セッションから見て 1 ホップのリンク層の通り道だからである。
- **OSPF / IS-IS の辺**: `transport_link` を出す (D4)。
- **bridge の要素**: bridge を Cytoscape の要素として出す。持たせるのは `id` / `name` / `description` / `ports` と、ポートから導いたノード。
  - ndl-viz での描き方 (箱の中に描くか、出さないか) は ndl-viz の側で決める。
  - mlndl は、書かれた情報を落とさずに出す。
- **RFC 8345 エクスポーター** (`exporter/rfc8345.py`): bridge をどう出すかは Phase 2 の L2 ネットワークと合わせて決める。当面は出さない。

### D6. 通り道の食い違いのメッセージ

今のメッセージは「直結のインターフェースどうしで張るなら、同じリンクの両端を指してください」である。これを次の形に改める。
- 両端の通り道を言葉で示す (矢印は使わない)。
- そのうえで、書き手の意図ごとに次の手を示す。
- 並べる順は、よくある順 (直結、事業者網、トンネル) にする。

```
両端の update_source から導いた通り道が食い違います。
  from: tokyo-rtr-ge0-l3 の通り道は link-tokyo-wideether
  to:   osaka-rtr-ge0-l3 の通り道は link-osaka-wideether
次のどれかで直してください (ADR-0018):
  (a) 直結のリンクの上で張るなら、両端の L3 IF を同じ L1 リンクの両端に載せる
  (b) 事業者網をはさむなら、両端のポートの対向 (箱のポート) を同じ layer2.bridges[].ports に書く
  (c) トンネルの上で張るなら、両端の update_source を対になるトンネル IF にする
```

片方だけがトンネル IF のときは、(a)〜(c) の前に次の 1 文を出す。

```
from 側はトンネル IF ですが、to 側はトンネル IF ではありません。相手の機器のトンネル IF (destination_interface が from 側の source を指すもの) を書いてください。
```

OSPF / IS-IS では、1 行目の `update_source` を `interface` と書く。

### D7. ADR-0017 D5-2 の書き方を置き換える

| プロトコル | 書き方 | 残る限界 |
|---|---|---|
| BGP (広域イーサの 2 拠点) | bridge を書き、両端を `node` で書く。通り道は `{bridge:}` | なし |
| BGP (広域イーサの 3 拠点以上) | 同上。組ごとのセッション (フルメッシュか RR) | — |
| BGP / OSPF (GRE・IPsec VTI・WireGuard の上) | トンネル IF を `update_source` / `interface` に書く。通り道は `{tunnel:}` | 1 対 1 のトンネルだけ (D8) |
| OSPF / IS-IS (広域イーサの 2 拠点) | bridge を書き、両端を `node` で書く。通り道が導かれる | IS-IS はトンネルの上に書けない |
| OSPF / IS-IS (広域イーサの 3 拠点以上) | **範囲外** | 次の ADR (マルチアクセス) |

- 片側をトポロジー外の相手として書く書き方 (ADR-0017 P2a) は、valid のままだが推奨しない。
  - validator は、トポロジー外の相手が自社の機器かどうかを知りえない。そのため warning は出さず、文書で推奨しないとだけ書く。
- ADR-0017 D5-2 には、この ADR を指す注記を足す。

### D8. 扱わないもの

- **マルチアクセスの隣接** (3 拠点以上の OSPF / IS-IS、DR / DIS): 次の ADR で扱う。
- **拠点の L2 スイッチをはさむ構成** (ルーター → 自社スイッチ → 箱): 1 ホップでは届かず、食い違いになる。多段のたどり方は後の論点とする。
  - 自社のスイッチのポートを事業者網の bridge の `ports` に混ぜることは推奨しない。
- **1 つのポートに複数の EVC を載せる契約** (EVPL のサービス多重。タグ 100 は大阪へ、タグ 200 は名古屋へ): `ports` はポート単位なので区別できない。必要になったら、`ports` の要素にタグを足す (加算)。
- **1 対 1 でないトンネル**: WireGuard のマルチピアや、DMVPN (mGRE) の hub (`destination` を持たない)。`tunnel_interfaces` の多対多は別の ADR で扱う。
- **IP-VPN の上で CE どうしが直接張るセッション**: 実在しない。CE は PE とだけ張り、CE どうしで張りたいならトンネルを載せる (D3)。
- 次のものはこの ADR では扱わない。
  - **自社が PE を持つ VPLS / MPLS-EVPN**
  - **Q-in-Q のトンネルポート**
  - **E-TREE の root / leaf**
  - **事業者網の QoS クラス**: `description` に書く (ADR-0017 D4)
- 次のものもこの ADR では扱わない。
  - **IS-IS over GRE**
  - **トンネルの下の通り道**
  - **トンネルの `transport_vrf` と `source` の L3 IF の `vrf` の照合**
  - **vSwitch としての bridge**: `type` / `uplinks` / VLAN との関係。drafts/0007 で扱う
- **VLAN の端点の導出 (ADR-0013 D7) を、bridge をはさんで広げること**
- **事業者網の MTU** (最大フレーム長): `L1Link.mtu` の意味 (Ethernet ヘッダーを含むか) が決まっていないので、別に扱う。トンネルの PMTU / MSS も同じく扱わない。
  → `L1Link.mtu` は [ADR-0020](0020-remove-l1-link-mtu.md) でなくした (2026-11-07)。インターフェース単位の MTU は [先送りした項目](deferred.md)。
- **IPsec / WireGuard の鍵や暗号のパラメーター**: 秘匿情報は書かない (ADR-0017 D4)。

## Consequences

**良い影響:**

- 広域イーサ越しの BGP を、両端とも `node` で書ける。セッションが 1 エントリになり、ndl-viz でも線として描ける。
- GRE / IPsec の上の BGP / OSPF が書ける。`examples/wan-sites.yaml` の穴が埋まる。
- 「L2 で透過するか」をフラグにしないので、validator が箱の `role` を見ずに済む (ADR-0003 を保つ)。
- 2 拠点と 3 拠点以上、ポートベースとタグ変換ありを、同じ構文で書ける (試し書き B1 / B2 / P1)。
- OSPF / IS-IS にも通り道が出て、BGP との非対称がなくなる。
- 既存の YAML は変わらない。spec-architect が fixtures / examples を確認した。既存のセッションは直結かループバックの上にあり、通り道が変わるものはない。

**悪い影響 / トレードオフ:**

- Phase 2 の `layer2.bridges` を一部前倒しする。vSwitch の設計 (drafts/0007) は、この ADR の `id` / `ports` の形に合わせる制約を受ける。
- 箱の L1 IF を、`layer1.interfaces` と bridge の `ports` の 2 か所に書く。
- bridge をはさむとサブ IF のタグを比べないので、タグの書き間違いは検出できない。
- 拠点の L2 スイッチをはさむ構成は、まだ書けない (D8)。
- OSPF / IS-IS と BGP で、食い違いの severity が 1.x の間だけ違う。
- bridge を書かない事業者網が「書き忘れ」なのか「透過しない」なのかは、構文からは区別できない。文書で補う (試し書き P1)。

**影響を受けるコンポーネント:**

- **スキーマ**:
  - `schema/layer2.py`: `Bridge` と `L2Layer.bridges` を足す。VLAN のポートの型から、`{interface:}` / `{lag:}` のちょうど一方を書く基底を抜き出して共有する。bridge のポートは `native` も旧形式の `node` も持たない。
  - `schema/refs.py`: `Ref` で複数のコレクションを指せるようにする。
  - `schema/control_plane.py`: `update_source` と OSPF の `interface` の Ref を変える。
- **index**: `index.py` で、Ref の複数のコレクションを和集合で引く。
- **derive** (`derive.py`):
  - `_l3_basis` にトンネルを足す。
  - `_transport` に bridge とトンネルを足す。
  - `TransportLink` に `bridge` / `tunnel` を足す。
  - OSPF / IS-IS の通り道を導く。
  - `vlan_endpoints` は bridge をはさんで広げないことを、docstring に書く。
- **バリデーター**:
  - bridge の検査
  - L3 IF とトンネルの id の重複の検査 (`_check_interface_id_spaces`)
  - 食い違いの severity とメッセージ
  - 推奨プレフィックス `bridge-`
  - 参照の検査と未定義参照のメッセージを、複数のコレクションに対応させる
- **テスト**:
  - `tests/test_refs.py`: `KEYED_REFERENCES` に `layer2.bridges[].ports[].interface` / `.lag` を足し、Ref の複数パスに対応させる。
  - fixtures に、bridge・トンネルの valid / invalid を足す。
- **エクスポーター**:
  - `exporter/cytoscape.py`: `transport_link` と bridge の要素を出す。
  - `docs/exporter-cytoscape.md` を改める。
- **サンプル**: `examples/wan-sites.yaml` に、広域イーサの bridge と GRE の上の BGP を足す。
- **文書**:
  - CLAUDE.md: YAML 例の `layer2.bridges`、バリデーション項目の表、ADR の表を改める。
  - ADR-0002 D7: プレフィックス `bridge-` を足す。
  - ADR-0010 D7: 通り道の表に bridge とトンネルを足す。
  - ADR-0010 D10: OSPF / IS-IS の食い違いの行を足す。
  - ADR-0011 D6 / D11: トンネル IF を `update_source` に書けること、`l3_attachments` には入れないことを書く。
  - ADR-0013 D7: bridge をはさんで広げないことを書く。
  - ADR-0015: `Ref` の複数のコレクションを書く。
  - ADR-0017 D5-2: この ADR を指す注記を足す。
  - drafts/0007: `members` を `ports` に読み替える。
- **ndl-viz**: `transport_link` の新しい形と、bridge の表示を扱う。

## Alternatives Considered

- **`layer2.bridges` を最小の形で先取りする** *(採用案)*
- **案 V** (箱の L1 IF を `layer2.vlans` のポートにする): 却下した。
  - `vlan_id` に書く値がない。事業者網の中の番号は書き手に見えず、試し書き Q1_V / Q2_V は `vlan_id: 999` と嘘を書いた。
  - ポートベースの契約や、タグ変換のある契約を 1 つの番号にできない。
  - VLAN を「番号を持つブロードキャストドメイン」と読む既存の意味が 2 つに割れる。
- **案 F** (箱か L1Link に `provider_transport: l2 | l3` を足す): 却下した。
  - どの IF が同じセグメントかを示せない。
  - 1 つの箱の中に複数のセグメントを持てない。
  - 方式を構文に入れることになる (ADR-0005 D4 補則 問い 4)。
- **`ports` ではなく `members`** (drafts/0007 の語): 却下した。
  - 「所属」と読まれ、拠点のルーターのポートまで書かれる (Pass A 前の試し書き Q1_B がそうだった)。
  - 機器の語 (Linux の `bridge-ports`) は ports で、VLAN の `trunk_ports` / `access_ports` とも並ぶ。
- **`update_source` をキー付きにする** (`{interface:}` / `{tunnel:}`): 却下した。
  - すべての BGP セッションの書き方が変わる。
  - id から種類が決まる参照に、キーは要らない。ADR-0001 D8 のキーは、`attaches_to` のように参照先の種類で意味が変わる参照のためのものである。
- **トンネル IF を `layer3.interfaces` に統合する**: 却下した。ADR-0011 D6 の分離 (トンネルは source / destination を持つ) が崩れる。
- **トンネルを別の ADR にする**: 採らなかった。`transport_link` の形の改訂を 1 回で済ませるためである (ユーザーの判断)。
- **`transport_link` の値を `{tunnel: {from: a, to: b}}` にする** (linguist): 採らなかった。
  - 有向であることは構造から読める。
  - しかし今の `{lag: [<この端>, <相手>]}` がすでに from、to の順のリストなので、形を揃える方を優先した。
- **`ports` が 1 つなら error** (dsl-designer): 採らなかった。相手の拠点がトポロジー外のとき、1 つしか書けないのは正当である。
- **同じポートを 2 つの bridge に書いても warning** (dsl-designer): 採らなかった。
  - 事業者網のポートは 1 つのセグメントにしか属さない。
  - サービス多重 (D8) は、ポートにタグを足して表す。
- **bridge をエクスポーターの要素として出さない** (dsl-designer): 採らなかった。
  - 箱と重なって描かれる心配は、ndl-viz の描き方で決めることである。
  - mlndl は書かれた情報を落とさない。
- **片側をトポロジー外にする書き方に warning を出す**: 採らなかった。validator は、トポロジー外の相手が自社の機器かどうかを知りえない。
- **bridge をはさむ両端のサブ IF のタグが違うときに info を出す** (network-tech、Pass B): 採らなかった。タグ変換の契約では違うのが正しく、ノイズになる。

## References

- ADR-0017 D5-2 (この ADR に渡した問い)
- ADR-0010 D7 / D8 / D10
- ADR-0013 D7
- ADR-0011 D6 / D11
- ADR-0015
- ADR-0002 D5 / D7 / D8
- ADR-0003
- ADR-0005 D4 補則・D6
- drafts/0007 (vNIC と仮想スイッチ。`layer2.bridges` の元の構想)
- 評価メモ: `evaluations/adr0018/evaluation.md`
- 試し書き:
  - `evaluations/adr0018/passa/` (Q1〜Q4)
  - `evaluations/adr0018/passb/` (B1〜B5)
  - `evaluations/adr0018/passc/` (P1〜P5)
  - `evaluations/adr0017/passc/` (P1 / P2a / P2b)
- MEF 6.x (EPL / EVPL / EP-LAN / EVP-LAN)、IEEE 802.1D
