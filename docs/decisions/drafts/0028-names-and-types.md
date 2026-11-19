# ADR-0028: 1.0 の前の名前と型の直し

- **Status**: Draft
- **Date**: 2026-11-19
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー (D2・D4・D5 の 3 つの論点)
- **Pass**: A (5 エージェントの評価を 1 回取り、割れた 3 つの論点をユーザーが決めた)
- **Amends**: ADR-0010 (`address_families` の既定値)、ADR-0014 D3 (`vteps` を型で 1 つ以上に)、ADR-0023 D1 (`layer1.lag` の名前、`lacp` の既定値)、
  ADR-0025 D1 (移動先を示す error の一覧)、ADR-0027 (「1.0 の前に必須になるもの」の表をこの ADR で決める)
- **関連**: [1.0 に向けた棚卸し](../evaluations/release-1.0/inventory.md) §2〜§4、[検討の記録](../evaluations/adr0028/recommendation.md)

## Context

ADR-0027 で、1.0 の後に名前・既定値・意味を変える、型を狭める、検査を強めるのは 2.0 が要ると決めた。型を広げる・必須を任意にする・既定値のない任意のキーを足すのは 1.x でできる。
だから 1.0 は**狭く始める**のがよい。1.0 の前の今しか直せないものが、今の実装に次のとおりある (2026-11-19 に確かめた)。

- コレクションの名前で `layer1.lag` (`src/mlndl/schema/layer1.py:439`) と `layer2.vxlan` (`layer2.py:256`) だけが単数形。ほかのコレクションはすべて複数形 (`control_plane` の `bgp` / `ospf` / `isis` / `bfd` はプロトコルの名前)
- 列挙の値で IS-IS の `level` (`control_plane.py:212`) だけがハイフン区切り (`level-1` / `level-2` / `level-all`)。ほかの値はすべて下線区切り (`all_active` / `ipsec_vti` / `l2vpn_evpn` / `anycast_gateway`)
- `L2VxLAN.vteps` は既定値 `[]` で、空を後から validator で error にしている (`layer2.py:157`・`:188-190`)。`BgpSession.address_families` は既定値 `[]` で、空が「書いていない」か「何も運ばない」か決まっていない (`control_plane.py:161`)
- 既定値で埋めると「書いていない」と区別がつかなくなるものがある。`LacpConfig.mode = "active"`・`min_links = 1` (`layer1.py:304-305`)、BFD の `min_tx = 300`・`min_rx = 300`・`multiplier = 3` (`control_plane.py:91-93`)。
  エクスポーターは LACP を書かれた値だけ出していて (`exporter/cytoscape.py:146`)、モデルの既定値と食い違っている
- 値域のない整数がある。`local_as` (`control_plane.py:39`・`:117`)、`vni` (`layer2.py:155`・`:201`)、BFD のタイマー、`min_links`。トンネルの `mtu` には上限がない (`layer3.py:251`)。`Lag.members` は空でも型を通る (`layer1.py:325`)

## Decision

### D1. コレクションの名前を複数形にそろえる

| 今 | 1.0 |
|---|---|
| `layer1.lag` | `layer1.lags` |
| `layer2.vxlan` | `layer2.vxlans` |

- 中身 (エントリのキー) は変えない
- **1 つを指す参照キーは単数のまま**: `attaches_to: {lag: <id>}`、VLAN / bridge のポートの `{lag:}`、ES の脚の `{lag:}`、VRF の `l3vni:`。コレクションは複数形、1 つを指すキーは単数形という規則で、`interfaces` と `{interface:}` の関係と同じ
- `Ref` のパス (`Ref("layer1.lags")`・`Ref("layer2.vxlans", where=...)`) と、参照先の種類を示すメッセージの語 (`refs.py` の `COLLECTION_LABELS`) も直す
- `vnis` は採らない。番号のリストに見え、エントリの `vni:` と語が重なる

### D2. IS-IS の `level` の値を下線区切りにする (ユーザー決定)

`level-1` / `level-2` / `level-all` を `level_1` / `level_2` / `level_all` にする。

- 列挙の値の書き方を「下線区切り」の 1 つの規則にする。IS-IS だけを例外にしない
- RFC 9130 の YANG の `level-type` と各社の CLI (`is-type level-1-2` など) からは区切りだけが離れる。ほかの値 (`l2vpn_evpn` など) も RFC や CLI の綴りそのままではなく、mlndl で下線にそろえている
- `level_1_2` は採らない。3 つの値のうち 1 つだけが合成の名前になる

### D3. 空に意味のないリストは型で 1 つ以上にし、既定値を持たない

| フィールド | 今 | 1.0 |
|---|---|---|
| `L2VxLAN.vteps` | 既定値 `[]`、空を validator で error | 必須、1 つ以上 (ADR-0014 D3 の改訂) |
| `BgpSession.address_families` | 既定値 `[]` | 必須、1 つ以上 (ADR-0010 の改訂) |
| `Lag.members` | 必須、空でも通る | 必須、1 つ以上 (1 つの LAG は ES の脚で使う) |
| `EthernetSegment.members` | 2 つ以上を `field_validator` で | 2 つ以上を型で (結果は変わらない) |

- `address_families` の既定値を `[ipv4_unicast]` にしない。1.0 で固まり、EVPN のセッションで `l2vpn_evpn` を書き忘れたのと区別できない
- メッセージは今の親切な文 (`vteps` なら「L2VNI が載る VTEP を vteps: [<layer2.vteps の id>] で書いてください」) を保つ。pydantic の既定の文 (`List should have at least 1 item`) にしない。文面は参考 (ADR-0027 D1) なので、実装の手段は問わない
- コレクション (`nodes: []` など) と、エントリを先に宣言してあとから足す書き方の `BgpInstance.nodes` / `BFDConfig.nodes` は、空を許したままにする

### D4. 既定値で「書いていない」を埋めない (LACP・BFD はユーザー決定)

既定値は 1.0 で意味として固まる。機器ごとに既定値が違うもの、値から関係を読むもの (ADR-0022) は既定値を持たず、書かなければ「書いていない」(ADR-0023 D4 の `redundancy_mode` と同じ)。

| フィールド | 今 | 1.0 |
|---|---|---|
| `LacpConfig.mode` | `"active"` | 任意、既定値なし |
| `LacpConfig.min_links` | `1` | 任意、既定値なし |
| BFD の `min_tx` / `min_rx` / `multiplier` | `300` / `300` / `3` | 任意、既定値なし |

- `lacp` を書かない LAG は「LACP を書いていない」。static の LAG を明示するときは `lacp: {mode: on}` と書く。今は `lacp` を書かなくても `lacp: {}` と書いても見分けがつかないが、エクスポーターと同じ見え方にそろう
- `lacp: {}` (中身のない `lacp`) は error にする。書くなら `mode` か `min_links` を書く
- 次は既定値のまま 1.0 で固める。「書いていない = 使わない」が実機の挙動と一致する:
  VLAN のポートの `native = False` (`PortRef`)、`BgpInsideEndpoint.route_reflector_client = False`、セッションの `bfd = False` (BGP / OSPF / IS-IS)
- `vrf` を書かない L3 IF・BGP インスタンスは default VRF (今の意味のまま。言語として決まっている既定値)
- 1.0 の既定値の一覧は `docs/reference/` に「書かなかったときの意味」として載せる

### D5. 値域を狭める (ユーザー決定)

| フィールド | 今 | 1.0 | 根拠 |
|---|---|---|---|
| `local_as` (インスタンスの機器・トポロジー外の相手) | `int` | 1〜4294967295 | 4 バイトの AS (RFC 6793)。0 は AS として使えない (RFC 7607) |
| `vni` (L2VNI・L3VNI) | `int` | 1〜16777215 | VXLAN の VNI は 24 ビット (RFC 7348 §5)。0 は多くの実装が受け付けない |
| BFD の `min_tx` / `min_rx` (ms) | `int` | 1 以上 | 0 や負の値は意味がない |
| BFD の `multiplier` | `int` | 1〜255 | Detect Mult は 8 ビット (RFC 5880 §4.1) |
| `LacpConfig.min_links` | `int` | 1 以上 | 0 以下は意味がない。機器の上限はまちまちなので上限は置かない |
| トンネルの `mtu` | 68 以上 | 68〜65535 | IPv4 の Total Length は 16 ビット (RFC 791) |

- 予約の AS (23456 の AS_TRANS、65535 など) や文書用の AS・VNI の端の値は error にしない。warning を足すのは 1.x でもできるので、要るときに足す
- 広げる方向 (VRRP の `priority` を 255 まで、など) はこの ADR では扱わない。1.x でできる

### D6. 名前を変えないものと、その約束

棚卸し §4 の 4 点は名前を変えず、`docs/reference/` に約束を書く。

- **種類を見分けるキー**: `type` はエンティティやカプセル化の種類 (`vxlans[].type`・`tunnel_interfaces[].type`・`routing_neighbors[].type`)、`mode` は動作の選び方 (`gateway_redundancy[].mode`・`lacp.mode`)。これから足す種類分けもこの区別に従う
- **2 つの `members`**: `lags[].members` は L1 IF の id のリスト、`ethernet_segments[].members` は `{lag:}` / `{interface:}` のリスト。どちらも「束ねる要素」で、形の違いは参照先が 1 種類か 2 種類かから来る
- **エクスポーターの 2 つの `vlans`**: 機器ノードの `vlans` (ポートがある VLAN) と L2VNI の `vlans` (載る VLAN)。どちらも規範キーで、`docs/exporter-cytoscape.md` の注記を残す
- **OSPF の `interface` は L3 IF、IS-IS の `interface` は L1 IF**: OSPF は IP の上で、IS-IS は L2 の上で hello を送るという違いから来る。`update_source` は BGP の用語 (TCP のセッションの送信元) で、OSPF の隣接とは意味が違うので使わない

### D7. 旧名・旧値は移動先を示す error

ADR-0025 D1 と同じく、読み替えはしない。2.0 まで残す (ADR-0027 D7)。

- `layer1.lag`: 「`layer1.lag` は `layer1.lags` に改名しました。中身は変わりません。ほかのコレクション (`nodes` / `interfaces` / `links` / `ethernet_segments`) にそろえました (ADR-0028)」
- `layer2.vxlan`: 「`layer2.vxlan` は `layer2.vxlans` に改名しました。中身 (`type` / `vni` / `vlans` / `vteps`) は変わりません (ADR-0028)」
- IS-IS の `level: level-2` など: 「IS-IS の `level` は下線で書きます (`level_1` / `level_2` / `level_all`)。ほかの値 (`all_active` / `l2vpn_evpn`) にそろえました (ADR-0028)」
- `address_families` を書かない・空、`vteps` を書かない・空、`lacp: {}`: 何を書けばよいかを例で示す
- 既定値をなくした `lacp` と BFD のタイマー、値域を狭めたフィールドは、書いてあった YAML の意味が変わらないか (既定値) 範囲外の値だけが error になるので (値域)、移動先の案内は要らない

## Consequences

**良くなること:**
- コレクションは複数形、1 つを指すキーは単数形、列挙の値は下線区切り、という 3 つの規則に例外がなくなる
- 「書いていない」と「既定値と同じ値を書いた」が LACP と BFD で区別できる。エクスポーターの出力とモデルが一致する
- 空のリストと範囲外の数を、1.0 から error で止められる。1.0 の後に狭めると 2.0 が要った

**悪くなること・注意:**
- 今の YAML は書き換えが要る: `lag:` → `lags:`、`vxlan:` → `vxlans:`、IS-IS の `level`、`address_families` を書いていないセッション。examples・fixtures・`docs/reference/`・CLAUDE.md の例を直す (`docs/decisions/evaluations/` の過去の試し書きは履歴として旧名のまま残す)
- `address_families` を毎回書くので、セッションの行が長くなる (試し書き a1)
- Python の利用者は `layer1.lag` / `layer2.vxlan` の属性名と、`lacp.mode` が `None` になりうることに合わせて直す (モデルは参考。ADR-0027 D1)
- IS-IS の `level` はエクスポーターが値をそのまま出す (`cytoscape.py:664`)。ndl-viz の線の札が「IS-IS level_2」になる。ndl-viz で表示を整えるかを決める
- RFC 9130 の YANG に書き出すとき、`level` の値の区切りを変換する (RFC 8345 のエクスポーターは未実装。deferred.md)

**影響を受けるコンポーネント:**
- スキーマ: `layer1.py` (`lags`、`Lag.members`、`LacpConfig`、ES の `members`)、`layer2.py` (`vxlans`、`vteps`、`vni`)、`layer3.py` (`Ref("layer2.vxlans")`、トンネルの `mtu`)、
  `control_plane.py` (`level`、`address_families`、`local_as`、BFD)、`refs.py` (`COLLECTION_LABELS`)
- `validator.py`・`derive.py`・`exporter/cytoscape.py`: 属性名の置き換え (`l1.lag` → `l1.lags` など。エクスポーターの出力のキーは変わらない)
- テスト: 改名・旧名の error・空のリスト・`lacp: {}`・値域の端
- 文書: `docs/reference/` (layer1・layer2・layer3・types・control-plane・validation、`schema.json` の再生成)、`docs/exporter-cytoscape.md` (IS-IS の `level` の値)、CLAUDE.md の例と表
- 下流: ndl-viz (IS-IS の札)。LACP は書かれた値だけを任意で読んでいるので変わらない (`src/types/topology.ts:91`)

## Alternatives Considered

- **名前を直さず 1.0 を出す**: 採らない。単数形の 2 つとハイフンの値が 2.0 まで残る
- **IS-IS の `level` をハイフンのまま残す** (network-tech-reviewer): 採らない。RFC と CLI に近いが、値の書き方に例外が残る。ユーザーが下線を選んだ
- **`LacpConfig.mode = "active"` を残す** (spec-architect・dsl-designer。Linux bonding などの慣用): 採らない。機器ごとに既定値が違い、static の LAG と「書いていない」が見分けられない
- **`mode` だけ既定値をなくし `min_links = 1` を残す** (example-author): 採らない。既定値をなくしても必須にはならず、書かなければ「書いていない」になるだけなので、書く量は増えない
- **BFD のタイマーの既定値を 300 / 300 / 3 で固める**: 採らない。機器ごとに既定値が違う
- **エクスポーターの機器ノードの `vlans` を `port_vlans` などに改名** (dsl-designer): 採らない。ndl-viz が読む規範キーで、意味の違いは文書の注記で足りる
- **OSPF の `interface` を `update_source` に** (dsl-designer): 採らない。D6
- **`ethernet_segments[].members` を `legs` に**: 採らない。「束ねる要素」の語は `members` が自然で、ADR-0023 で決めたばかり
- **予約の AS・VNI を error に**: 採らない。warning なら 1.x で足せる。error にすると、実機が受け付ける値まで止めかねない

## References

- RFC 5880 (BFD)、RFC 6793 (4 バイトの AS)、RFC 7348 (VXLAN)、RFC 7607 (AS 0)、RFC 791 (IPv4)、RFC 9130 (IS-IS の YANG)
- ADR-0010、ADR-0014、ADR-0022、ADR-0023、ADR-0025、ADR-0027
- 試し書き: [evaluations/adr0028/](../evaluations/adr0028/recommendation.md) の a1〜a5
