# ADR-0018: 事業者網やトンネルを越えるセッションの通り道

- **Status**: Superseded by [0018](../0018-sessions-across-bridges-and-tunnels.md) (2026-11-03 に Pass C で確定)
- **Date**: 2026-11-03
- **Deciders**: spec-architect, linguist, dsl-designer, network-tech-reviewer, example-author (Pass A の前に論点を並列で検討、Pass B で横断評価) / ユーザー (D1・D3・D8 の方針)
- **Pass**: A (初回策定、改訂 1)

## Context

ADR-0017 D5-2 は、事業者網をはさんで自社の機器どうしが張るセッションの構文を決めず、問いを 5 つこの ADR に渡した。

1. 事業者網が L2 を透過するか L3 で終端するかを書くか、どこに書くか。Phase 2 の `layer2.bridges` と書き方が 2 通りにならないか
2. 箱をはさむ通り道を ADR-0010 D7 がどう導くか。BGP にだけ通り道の検査があり OSPF / IS-IS にはない非対称をどう揃えるか
3. マルチアクセスのセグメント (3 拠点以上の広域イーサ) の OSPF / IS-IS をどう書くか
4. トンネル IF を `update_source` にすること (BGP over GRE / IPsec)
5. 両端を `node` で書いて error になったときのメッセージ

今の状態:

- **BGP**: 通り道は両端の `update_source` の L3 IF の基盤から導く (ADR-0010 D7、`derive._transport`)。両端が同じ L1 リンク (または LAG のメンバーどうし) でないと error になるので、
  広域イーサの箱をはさむと両端 `node` で書けない (`evaluations/adr0017/passc/P2b`)。片側をトポロジー外 `{address, local_as}` にして逃げている (P2a)
- **OSPF / IS-IS**: 通り道の検査も導出もない。2 拠点なら両端 `node` で通るが、通り道は出力されない
- **トンネル**: `update_source` は `Ref("layer3.interfaces")` で、`layer3.tunnel_interfaces` の id を指すと参照の error になる。
  `examples/wan-sites.yaml` は GRE の上の BGP を書けていない

どれも「セッションの通り道が L1 リンク 1 本ではない」という同じ問題である。

### Pass A の前の検討とユーザーの判断

5 エージェントが案 V (箱の L1 IF を `layer2.vlans` のポートにする)・B (`layer2.bridges` を先取りする)・F (箱か L1Link に `provider_transport: l2 | l3` を足す)・
T (`update_source` がトンネル IF を指せる)・M (マルチアクセスの隣接をセグメント単位で書く) を評価し、example-author が試し書きした (`evaluations/adr0018/passa/`)。

| 論点 | 割れ方 | ユーザーの判断 |
|---|---|---|
| L2 透過をどこに書くか | B: network-tech・linguist・example-author。V: spec-architect。dsl-designer は V と B を同時に設計せよ | **B (bridges を先取り)** |
| トンネルを同じ ADR で扱うか | 同じ: network-tech・example-author。分ける: spec-architect | **同じ ADR** |
| マルチアクセスの隣接 | 今: network-tech・example-author。後: dsl-designer。却下: spec-architect | **次の ADR に回す** |

V を採らない理由は試し書きで具体的になった。`vlan_id` が必須なのに事業者網の中の番号は書き手に見えず、Q1_V / Q2_V は `vlan_id: 999` と嘘を書いた。
ポートベースの広域イーサ (EPL) は拠点がタグなしで、タグ変換のある契約 (EVPL。東京は 100、大阪は 200) は 1 つの番号にできない (network-tech)。
F は 5 人中 4 人が却下した (方式名を構文に入れる。どの IF が同じセグメントかを示せない。1 つの箱の中の複数の EVC を表せない)。

## Decision

### D1. 事業者網の中の L2 の転送は `layer2.bridges` に書く

drafts/0007 で Phase 2 に予定していた `layer2.bridges` を、この ADR で最小の形だけ先に入れる。bridge は 1 つの L2 セグメントを表す。

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
    - id: bridge-wideether             # 推奨プレフィックス bridge-。回線名は id に埋めず name / description に
      name: WE-220                     # 任意。人が読む名前
      ports:                           # この bridge でフレームを転送するポート。{interface:} か {lag:}
        - {interface: net-wideether-tokyo}   # 箱のポートを書く
        - {interface: net-wideether-osaka}
        # tokyo-rtr-ge0 / osaka-rtr-ge0 (拠点のルーターのポート) は書かない
      description: 契約 WE-220。ポートベース   # 任意 (ADR-0017 D4)
```

- **意味**: `ports` のあいだで、Ethernet フレームが L2 のまま転送される。VLAN と違い 802.1Q の番号を持たない
- **`ports` に書くのは転送する側のポート**: 事業者網なら箱の L1 IF。拠点のルーターのルーテッドポートは書かない。ルーターはフレームを転送せず、箱のポートに L1 リンクでつながって bridge を**使う**側である
  (RFC 8345 の supporting の向きとも合う。下の層の箱が、上の層のセッションを実現する)
- **形は VLAN のポートと同じ** (ADR-0013): `{interface: <L1 IF>}` か `{lag: <LAG>}` のちょうど一方。`node` は書かず、参照先から導く (ADR-0005 D6)
- **方式名は書かない** (ADR-0005 D4 補則 問い 4): E-LINE / E-LAN / VPLS / EVPN のどれで実現しているかは構文に出さない。2 拠点も 3 拠点以上も `ports` の数が違うだけ。
  方式・契約 ID・EVC ID は `description` に書く
- **書かなければ透過しない**: IP-VPN やインターネットの箱には bridge を書かない。問い 1 の「L2 透過か L3 終端か」は、フラグではなく bridge の有無で表す。
  validator は箱の `role` を見ない (ADR-0003)
- **bridge を書くのは箱をはさむときだけ**: L2 専用線 (EPL)・ダークファイバ・波長は ADR-0017 D3 のとおり L1Link で拠点どうしを直接つなぐので、bridge は書かない
- **VLAN との使い分け**: 自社の L2 スイッチのポートの所属は `layer2.vlans` で書く。bridge は、番号を持たない L2 セグメント (事業者網の中) に使う
- **drafts/0007 との関係**: 同じ構成子である。drafts/0007 の `members: [{node, interface}]` は `ports` (ADR-0013 の形) に読み替える。
  vSwitch のための `type` / `nodes` / `uplinks` と VLAN との関係 (`vlans[].bridge`) はこの ADR では決めず、後で足すときは任意のフィールドとして加算する (1.x の間に bridges の必須フィールドを増やさない)

**検査** (error): `ports` の参照先がそのキーの種類で定義されているか。同じポートを 2 つの bridge に書いていないか。同じ bridge に LAG とそのメンバーを併記していないか (ADR-0013 と同じ)。

**検査** (warning):
- `ports` が 1 つしかない
- ポートの L1 リンクの対向が、同じ bridge の別のポートになっている (拠点のルーターのポートを書いた疑い)
- 同じ L1 IF / LAG が VLAN のポートと bridge の `ports` の両方にある (箱のポートを VLAN に書いた疑い。vSwitch の uplink では正当になるので drafts/0007 で見直す)
- 推奨プレフィックス `bridge-` (ADR-0002 D7 に足す)

### D2. 通り道を bridge に延ばす (ADR-0010 D7 の拡張)

L3 IF が bridge に**届く**とは、その L3 IF の基盤 (L1 IF か LAG。サブ IF ならその基盤) の L1 リンクの対向のポートが、bridge の `ports` にあることをいう
(LAG なら、メンバーの対向のどれかが `ports` にあるか、対向の LAG が `ports` にある)。ADR-0013 D7 と同じく 1 ホップだけたどる。

| 両端 | 通り道 | |
|---|---|---|
| 同じリンク (または LAG のメンバーどうし) | `{link:}` / `{lag:}` | 今と同じ |
| 両端が同じ bridge に届く | `{bridge: <bridge id>}` | **新規**。single-hop として扱う |
| 片方だけが bridge に届く、別の bridge に届く、片方が直結 | — | 食い違い (BGP は error) |
| どちらかが基盤なし (ループバック等) | — | multihop。今と同じ |

- **1 ホップだけ**: 拠点のルーターと箱のあいだに自社の L2 スイッチがはさまると、ルーターのポートの対向はスイッチなので bridge に届かない。
  2 つの bridge (または VLAN と bridge) が L1 リンクでつながっていても、同じセグメントとはみなさない (D8)
- **IS-IS**: `interface` は L1 IF を指すので、その L1 IF の対向のポートが `ports` にあるかで判定する (L3 IF から基盤をたどる 1 段を省く)
- **サブ IF のタグは bridge をはさむと比べない**。タグ変換のある契約 (EVPL) では両拠点のタグが違うのが正しい。直結のリンクのタグの比較は今のまま
- 3 つ以上の `ports` を持つ bridge の上の BGP は、組ごとのセッション (フルメッシュや RR) として今の構文で書ける

```yaml
control_plane:
  routing_neighbors:
    - id: bgp-peer-tokyo-osaka
      type: bgp
      from: {node: tokyo-rtr, update_source: tokyo-rtr-ge0-l3}   # tokyo-rtr-ge0 → 対向 net-wideether-tokyo (bridge-wideether のポート)
      to:   {node: osaka-rtr, update_source: osaka-rtr-ge0-l3}   # osaka-rtr-ge0 → 対向 net-wideether-osaka (bridge-wideether のポート)
      address_families: [ipv4_unicast]
      # 通り道は {bridge: bridge-wideether} と導かれる
```

### D3. トンネル IF を `update_source` と OSPF の `interface` に書ける

- BGP の `update_source` と OSPF の `interface` は、`layer3.interfaces` に加えて `layer3.tunnel_interfaces` の id も指せる。値は文字列のまま (今の YAML は変わらない)。
  機器の設定でも `update-source` は Loopback と Tunnel を同じように受ける
- **型**: ADR-0015 の `Ref` が複数のコレクションを指せるようにする (`Ref("layer3.interfaces", "layer3.tunnel_interfaces")`)。参照の検査は各コレクションの id の和集合で引き、
  エラーメッセージの参照先の呼び名は「L3 インターフェース / トンネル」と連結する。id はトポロジー全体で一意 (ADR-0002 D5) なので、どちらのコレクションかは id から決まる。
  ADR-0002 D5 の全レイヤー横断の一意性検査は未実装なので、そのうち `layer3.interfaces` と `layer3.tunnel_interfaces` のあいだの重複の error をこの ADR で先に実装する (新しい制約ではない)
- **通り道**: 両端がどちらもトンネル IF で、from 側のトンネルの `destination_interface` が to 側のトンネルの `source` を指し、to 側の `destination_interface` が from 側の `source` を指していれば、
  `{tunnel: [<from 側のトンネル>, <to 側のトンネル>]}` (順は from, to)。
  片方だけトンネル IF、または両方トンネル IF で対になっていなければ食い違い。`destination_ip` (相手がトポロジー外) のトンネルは対を確かめられないので、通り道を出さず食い違いともしない
- **VRF**: トンネル IF を指したときの「`update_source` の VRF」はトンネル IF の `vrf` (overlay 側)。`transport_vrf` ではない
- **トンネルの下の通り道は導かない**: トンネルの外側のパケットがどこを通るかは `source` の L3 IF から別にたどれる。セッションの通り道はトンネルで止める
- **実装**: `derive._l3_basis` はトンネル IF を 4 つ目の種類として扱う。ADR-0011 D11 の L3 IF の分類 (`l3_attachments`) には入れない (トンネル IF は別のコレクション)
- IS-IS の `interface` は L1 IF を指す (IS-IS は IP ではなく L2 で IIH を送る) ので、この ADR では広げない

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

- OSPF (`interface` は L3 IF かトンネル IF) と IS-IS (`interface` は L1 IF) の両端からも、D2・D3 と同じ規則で通り道を導き、エクスポーターに出す。問い 2 の非対称を解消する
- **食い違いは ndl_version 1.x の間は warning、2.0 で error** にする。今まで valid だった OSPF / IS-IS の YAML を 1.x の間に error にしない。BGP の食い違いは今のまま error
- この決定は 2 端点のセッションの通り道を導くだけで、ADR-0010 D8 のポイントツーポイント前提は変えない。3 つ以上の `ports` を持つ bridge の上で OSPF / IS-IS を組に展開して書くことは推奨しない。
  マルチアクセスの隣接の書き方は次の ADR で決める (ユーザーの判断)。bridge がセグメントを表すので、その上に加算する

### D5. エクスポーターの `transport_link` に bridge とトンネルを足す

- `transport_link` の値に `{"bridge": <bridge id>}` と `{"tunnel": [<from 側>, <to 側>]}` を足す。今の `{"link":}` / `{"lag":}` は変えない。キー名も変えない
  (bridge もトンネルも、セッションから見て 1 ホップのリンク層の通り道である)
- OSPF / IS-IS の辺にも `transport_link` を出す (D4)
- bridge を Cytoscape の要素として出す (`ports` と、導いた `nodes`)。ndl-viz での描き方 (箱の中に描くか) は ndl-viz の側で決める

### D6. 通り道の食い違いのメッセージ

今の「直結のインターフェースどうしで張るなら、同じリンクの両端を指してください」を、両端の通り道を示したうえで、書き手の意図ごとに次の手を示す文にする:

> 両端の update_source から導いた通り道が食い違います (from: tokyo-rtr-ge0-l3 の通り道は link-tokyo-wideether、to: osaka-rtr-ge0-l3 の通り道は link-osaka-wideether)。
> 両端を同じリンク / LAG / bridge / トンネルの対でつないでください。(a) 直結なら、両端の L3 IF を同じ L1 リンクの両端に載せる。
> (b) 事業者網をはさむなら、箱のポートを `layer2.bridges[].ports` に書く。(c) トンネルの上なら、`update_source` を対になるトンネル IF にする (ADR-0018 D2 / D3)

片方だけトンネル IF のときは「to 側はトンネル IF ではありません。相手の機器のトンネル IF (`destination_interface` が from 側の source を指すもの) を書いてください」と分岐する。

### D7. ADR-0017 D5-2 の書き方を置き換える

- 広域イーサ越しの自社の機器どうしの BGP は、bridge を書いて両端 `node` で書く (D1・D2)。片側をトポロジー外にする書き方 (ADR-0017 P2a) は valid のままだが推奨しない
- 2 拠点の OSPF / IS-IS も bridge を書けば通り道が出る
- ADR-0017 D5-2 の表を、この ADR を指す 1 文に改める

### D8. 扱わないもの

- **マルチアクセスの隣接** (3 拠点以上の OSPF / IS-IS、DR / DIS): 次の ADR
- **拠点の L2 スイッチをはさむ構成** (ルーター → 自社スイッチ → 箱): 1 ホップで届かず、食い違いになる。多段のたどり方は次の論点
- **1 つのポートに複数の EVC を載せる契約** (EVPL のサービス多重。タグ 100 は大阪へ、タグ 200 は名古屋へ): `ports` はポート単位なので区別できない。必要になったら `ports` の要素にタグを足す (加算)
- **1 対 1 でないトンネル**: WireGuard のマルチピア、DMVPN (mGRE) の hub (`destination` を持たない)。`tunnel_interfaces` の多対多は別の ADR
- **IP-VPN の上で CE どうしが直接張るセッション**: 実在しない (CE は PE とだけ張り、CE どうしが要るならトンネルを載せる = D3)
- **自社が PE を持つ VPLS / MPLS-EVPN** (PE 間の L2VPN / EVPN の AF)、**Q-in-Q のトンネルポート**、**E-TREE の root / leaf**、**事業者網の QoS クラス** (`description` に書く。ADR-0017 D4)
- **IS-IS over GRE**、**トンネルの下の通り道**、**vSwitch としての bridge** (`type` / `uplinks` / VLAN との関係。drafts/0007)
- **VLAN の端点の導出 (ADR-0013 D7) を bridge をはさんで広げること**
- **事業者網の MTU** (最大フレーム長): `L1Link.mtu` の意味 (Ethernet ヘッダーを含むか) が決まっていないので、別に扱う

## Consequences

**良い影響:**

- 広域イーサ越しの BGP を両端 `node` で書ける。セッションが 1 エントリになり、ndl-viz でも線として描ける
- GRE / IPsec の上の BGP / OSPF が書ける (`examples/wan-sites.yaml` の穴が埋まる)
- 「L2 透過か」をフラグにしないので、箱の `role` を validator が見ずに済む (ADR-0003 を保つ)
- 2 拠点と 3 拠点以上、ポートベースとタグ変換ありを同じ構文で書ける (試し書き B1 / B2)
- OSPF / IS-IS にも通り道が出て、BGP との非対称がなくなる
- 既存の YAML は変わらない (spec-architect が fixtures / examples を確認。既存のセッションは直結かループバックで、通り道が変わるものはない)

**悪い影響 / トレードオフ:**

- Phase 2 の `layer2.bridges` を一部前倒しする。vSwitch の設計 (drafts/0007) は、この ADR の `id` / `ports` の形に合わせる制約を受ける
- 箱の L1 IF を `layer1.interfaces` と bridge の `ports` の 2 か所に書く (example-author)
- サブ IF のタグを bridge をはさむと比べないので、タグの書き間違いは検出できない
- 拠点の L2 スイッチをはさむ構成はまだ書けない (D8)
- OSPF / IS-IS と BGP で食い違いの severity が 1.x の間だけ違う

**影響を受けるコンポーネント:**

- スキーマ: `schema/layer2.py` (Bridge。VLAN のポートの型から `{interface:}` / `{lag:}` のちょうど一方の基底を抜き出して共有し、bridge のポートは `native` を持たない)、
  `schema/refs.py` (`Ref` の複数コレクション)、`schema/control_plane.py` (`update_source` / OSPF の `interface` の Ref)
- derive: `derive.py` (`_l3_basis` にトンネル、`_transport` に bridge とトンネル、`TransportLink` に `bridge` / `tunnel`、OSPF / IS-IS の通り道)
- バリデーター: bridge の検査、id の重複 (L3 IF とトンネル)、食い違いの severity とメッセージ、推奨プレフィックス `bridge-`、`_walk_refs` と未定義参照のメッセージの複数コレクション対応
- テスト: `tests/test_refs.py` (`KEYED_REFERENCES` に `layer2.bridges[].ports[].interface` / `.lag`、`Ref` の複数パス)
- エクスポーター: `exporter/cytoscape.py` (`transport_link`、bridge の要素)、`docs/exporter-cytoscape.md`。`exporter/rfc8345.py` で bridge をどう出すかは Phase 2 の課題
- サンプル: `examples/wan-sites.yaml` (広域イーサの bridge、GRE の上の BGP)
- 文書: CLAUDE.md (YAML 例の `layer2.bridges`、バリデーション項目表、ADR 表)、ADR-0010 D7 (表に bridge とトンネル) と D10 (OSPF / IS-IS の食い違いの行)、
  ADR-0017 D5-2、ADR-0002 D7 (プレフィックス `bridge-`)、ADR-0015 (`Ref` の複数コレクション)、drafts/0007 (`members` → `ports`)
- ndl-viz: `transport_link` の新しい形、bridge の表示

## Alternatives Considered

- **案 B** *(採用案)*: `layer2.bridges` を最小の形で先取りする
- **案 V** (箱の L1 IF を `layer2.vlans` のポートにする): 却下 — `vlan_id` に書く値がない (事業者網の中の番号は見えない)。ポートベースやタグ変換のある契約を 1 つの番号にできない。
  VLAN を「番号を持つブロードキャストドメイン」と読む既存の意味が 2 つに割れる (linguist)
- **案 F** (箱か L1Link に `provider_transport: l2 | l3`、linguist の語では `handoff`): 却下 — どの IF が同じセグメントかを示せない。1 つの箱の中に複数のセグメントを持てない。
  方式を構文に入れる (ADR-0005 D4 補則 問い 4)
- **`ports` ではなく `members`** (drafts/0007 の語): 却下 — 「所属」と読まれ、拠点のルーターのポートまで書かれる (Pass A 前の試し書き Q1_B)。
  Linux の `bridge-ports` など機器の語は ports で、VLAN の `trunk_ports` / `access_ports` とも並ぶ (linguist)
- **`update_source` をキー付きにする** (`{interface:}` / `{tunnel:}`): 却下 — すべての BGP セッションの書き方が変わる。
  ADR-0001 D8 の「キーで参照先を選ぶ」は、同じ id 空間の中で種類を選ぶ `attaches_to` のための形で、id から種類が決まる参照には要らない (linguist も Pass B で撤回)
- **トンネル IF を `layer3.interfaces` に統合する**: 却下 — ADR-0011 D6 の分離 (source / destination を持つ) が崩れる
- **トンネルを別の ADR にする** (spec-architect): 採らない — `transport_link` の形の改訂を 1 回で済ませる (ユーザーの判断)
- **bridge をはさむ両端のサブ IF のタグが違うときに info** (network-tech): 採らない — タグ変換の契約では違うのが正しく、ノイズになる

## References

- ADR-0017 D5-2 (この ADR に渡した問い)、ADR-0010 D7 / D8 / D10、ADR-0013 D7、ADR-0011 D6 / D11、ADR-0015、ADR-0002 D5 / D7、ADR-0003、ADR-0005 D4 補則・D6
- drafts/0007 (vNIC と仮想スイッチ。`layer2.bridges` の元の構想)
- 評価メモ: `evaluations/adr0018/evaluation.md`
- 試し書き: `evaluations/adr0018/passa/` (Q1〜Q4)、`evaluations/adr0018/passb/` (B1〜B5)、`evaluations/adr0017/passc/` (P1 / P2a / P2b)
- MEF 6.x (EPL / EVPL / EP-LAN / EVP-LAN)
