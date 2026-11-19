# ADR-0028: 1.0 の前の名前と型の直し

- **Status**: Superseded by [0028](../0028-names-and-types.md) (2026-11-20 に Pass C で確定。この版は改訂 1)
- **Date**: 2026-11-19
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー (D2・D4・D5 の 3 つの論点と、Pass B の `lacp.mode` の `static`)
- **Pass**: A (5 エージェントの評価を 1 回取り、割れた 3 つの論点をユーザーが決めた。改訂 1 は Pass B の指摘の反映)
- **Amends**: ADR-0001 D8 (表の `layer1.lag`)、ADR-0010 (`address_families` の既定値)、ADR-0014 D3 (`vteps` を型で 1 つ以上に)、
  ADR-0018 D1 (`bridges[].ports` を 1 つ以上に)、ADR-0023 D1 (`layer1.lag` の名前、`lacp` の既定値と `on`)、ADR-0025 D1 (移動先を示す error の一覧)、
  ADR-0026 (`layer2.vxlan` の名前)、ADR-0027 (「1.0 の前に必須になるもの」の表をこの ADR で決める)
- **関連**: [1.0 に向けた棚卸し](../evaluations/release-1.0/inventory.md) §2〜§4、[Pass A の検討](../evaluations/adr0028/recommendation.md)、[Pass B の評価](../evaluations/adr0028/evaluation.md)

## Context

ADR-0027 で、1.0 の後に名前・既定値・意味を変える、型を狭める、検査を強めるのは 2.0 が要ると決めた。型を広げる・必須を任意にする・既定値のない任意のキーを足すのは 1.x でできる。
だから 1.0 は**狭く始める**のがよい。1.0 の前の今しか直せないものが、今の実装に次のとおりある (2026-11-19 に確かめた)。

- id を持つエントリの一覧で `layer1.lag` (`src/mlndl/schema/layer1.py:439`) と `layer2.vxlan` (`layer2.py:256`) だけが単数形。ほかの一覧はすべて複数形 (`control_plane` の `bgp` / `ospf` / `isis` / `bfd` はプロトコルの名前)
- 列挙の値で IS-IS の `level` (`control_plane.py:212`) だけがハイフン区切り (`level-1` / `level-2` / `level-all`)。ほかの値はすべて下線区切り (`all_active` / `ipsec_vti` / `l2vpn_evpn` / `anycast_gateway`)
- LAG の `lacp.mode` の `on` (static の LAG) は、引用符なしで書くと YAML が真偽値の `true` と読み、error になる (試し書き B1)。`lacp` の下に「LACP を使わない」値があるのも読み手を惑わせる
- `L2VxLAN.vteps` は既定値 `[]` で、空を後から validator で error にしている (`layer2.py:157`・`:188-190`)。`BgpSession.address_families` は既定値 `[]` で、空が「書いていない」か「何も運ばない」か決まっていない (`control_plane.py:161`)。
  `Lag.members` (`layer1.py:325`) と `Bridge.ports` (`layer2.py:103`) は空でも通る (bridge はポートが 1 つなら warning なのに、0 個なら何も出ない)
- 既定値で埋めると「書いていない」と区別がつかなくなるものがある。`LacpConfig.mode = "active"`・`min_links = 1` (`layer1.py:304-305`)、BFD の `min_tx = 300`・`min_rx = 300`・`multiplier = 3` (`control_plane.py:91-93`)。
  エクスポーターは LACP を書かれた値だけ出していて (`exporter/cytoscape.py:146`)、モデルの既定値と食い違っている
- 値域のない整数がある。`local_as` (`control_plane.py:39`・`:117`)、`vni` (`layer2.py:155`・`:201`)、BFD のタイマー、`min_links`。トンネルの `mtu` には上限がない (`layer3.py:251`)

## Decision

### D1. id を持つエントリの一覧の名前を複数形にそろえる

| 今 | 1.0 |
|---|---|
| `layer1.lag` | `layer1.lags` |
| `layer2.vxlan` | `layer2.vxlans` |

- 中身 (エントリのキー) は変えない
- 規則は「**id を持つエントリの一覧は複数形、1 つを指す参照キーは単数形**」。`interfaces` と `{interface:}` の関係と同じで、`attaches_to: {lag: <id>}`、VLAN / bridge のポートと ES の脚の `{lag:}`、VRF の `l3vni:` は単数のまま
- ID のリスト (`members` / `sources` / `vlans` / `vteps` / `address_families`) はすでに複数形
- **例外**: `layer3.interfaces[].gateway_redundancy` はリストだが単数のまま (ADR-0011 D4 で決めた名前)。エントリは id を持たない、1 つの IF の「冗長の設定」で、`gateway_redundancies` は不自然
- `Ref` のパス (`Ref("layer1.lags")`・`Ref("layer2.vxlans", where=...)`) と、参照先の種類を示すメッセージの語 (`refs.py` の `COLLECTION_LABELS`) も直す
- `vnis` は採らない。番号のリストに見え、エントリの `vni:` と語が重なる

### D2. IS-IS の `level` の値を下線区切りにする (ユーザー決定)

`level-1` / `level-2` / `level-all` を `level_1` / `level_2` / `level_all` にする。

- 列挙の値の書き方を「下線区切り」の 1 つの規則にする。IS-IS だけを例外にしない
- RFC 9130 の YANG の `level-type` と各社の CLI (`is-type level-1-2` など) からは区切りだけが離れる。ほかの値 (`l2vpn_evpn` など) も RFC や CLI の綴りそのままではなく、mlndl で下線にそろえている
- `level_1_2` は採らない。3 つの値のうち 1 つだけが合成の名前になる

### D3. 空に意味のないリストは型で 1 つ以上にする

基準: **そのエントリがリストの要素なしでは成り立たない** (何も束ねない LAG、何も転送しない bridge、どこにも載らない VNI、何も運ばないセッション) なら 1 つ以上にする。
空がそれだけで意味を持つ (`trunk_ports` / `access_ports` が空 = SVI だけの VLAN、`gateway_redundancy` が空 = 冗長なし)、またはエントリを先に宣言してあとから足す (`BgpInstance.nodes` / `BFDConfig.nodes`、各コレクション) なら空を許す。

| フィールド | 今 | 1.0 |
|---|---|---|
| `L2VxLAN.vteps` | 既定値 `[]`、空を validator で error | 必須、1 つ以上 (ADR-0014 D3 の改訂) |
| `BgpSession.address_families` | 既定値 `[]` | 必須、1 つ以上 (ADR-0010 の改訂) |
| `Lag.members` | 必須、空でも通る | 必須、1 つ以上 (1 つの LAG は ES の脚で使う) |
| `Bridge.ports` | 既定値 `[]` | 必須、1 つ以上 (ADR-0018 D1 の改訂。ポートが 1 つの warning は残す) |
| `EthernetSegment.members` | 2 つ以上を `field_validator` で | 2 つ以上を型にも書く (結果は変わらない) |

- `address_families` の既定値を `[ipv4_unicast]` にしない。1.0 で固まり、EVPN のセッションで `l2vpn_evpn` を書き忘れたのと区別できない
- **メッセージ**: 型 (`Field(min_length=...)`) にも書いて `schema.json` に `minItems` を出し、文はバリデーターで「何を書けばよいか」を示す文にする。pydantic の既定の文 (`List should have at least 1 item`・`Field required`) にしない。
  今の親切な文は保つ (`vteps` の「L2VNI が載る VTEP を vteps: [<layer2.vteps の id>] で書いてください」、ES の `members` の「1 台の機器だけの LAG は ... に書けば足ります」。後者の `layer1.lag` は `layer1.lags` に直す)。
  `address_families` には例を添える (「`[ipv4_unicast]`、EVPN なら `[l2vpn_evpn]`」)。文面は参考 (ADR-0027 D1)

### D4. 既定値で「書いていない」を埋めない。static の LAG は `static` と書く (ユーザー決定)

既定値は 1.0 で意味として固まる。機器ごとに既定値が違うもの、値から関係を読むもの (ADR-0022) は既定値を持たず、書かなければ「書いていない」(ADR-0023 D4 の `redundancy_mode` と同じ)。

| フィールド | 今 | 1.0 |
|---|---|---|
| `LacpConfig.mode` | `"active"` / `"passive"` / `"on"`、既定値 `"active"` | `active` / `passive` / **`static`**、任意、既定値なし |
| `LacpConfig.min_links` | `1` | 任意、既定値なし |
| BFD の `min_tx` / `min_rx` / `multiplier` | `300` / `300` / `3` | 任意、既定値なし |

- **`static`**: LACP を使わずに束ねる LAG (Cisco / Arista の `channel-group N mode on`、Linux bonding の `balance-xor` など、Junos の LACP を書かない AE)。
  `on` をやめる理由は 2 つ。引用符なしの `on` を YAML が `true` と読むこと、`lacp` の下で「LACP が on」と読めて意味が逆になること。`static` は各社で呼び方の違う static の LAG を中立に書ける
- **`lacp` の書き方と意味**:

  | 書き方 | 意味 |
  |---|---|
  | `lacp` を書かない | 束ね方を書いていない (LACP を使うか使わないか分からない) |
  | `lacp: {mode: active}` (`passive` も同じ) | LACP で束ねる |
  | `lacp: {mode: static}` | LACP を使わずに束ねる |
  | `lacp: {min_links: 2}` | 束ね方は書いていない。最低 2 本が上がっていれば LAG が上がる (`min_links` は LACP を使うかと関係なく効く) |
  | `lacp: {mode: active, min_links: 2}` | 両方 |
  | `lacp: {}` | **error**。書くなら `mode` か `min_links` を書く |

  `min_links` が `lacp` の下にあるのは名前の上では収まりが悪いが、キーの改名と構造の分割はしない (Alternatives)
- 次は既定値のまま 1.0 で固める。「書いていない = 使わない」が実機の挙動と一致する:
  VLAN のポートの `native = False` (`PortRef`)、`BgpInsideEndpoint.route_reflector_client = False`、セッションの `bfd = False` (BGP / OSPF / IS-IS)
- `vrf` を書かない L3 IF・BGP インスタンスは default VRF (今の意味のまま。言語として決まっている既定値)
- `docs/reference/` に「書かなかったときの意味」の一覧を載せる。LACP と BFD のタイマーは「言語として既定値を定めない (どの値になるかは機器の既定値)」と書く
- `lacp: {}` 以外の、中身のない任意のオブジェクト (`route_targets: {}`) はこの ADR では扱わない。`meta` は未知のキーの入れ物なので空でよい

### D5. 値域を狭める (ユーザー決定)

原則: **プロトコルのフィールドの幅が狭い (8 / 16 / 24 ビット) ものは上限と下限を置く。幅が広く、機器の上限がまちまちなものは下限だけを置く。**
意味のない値 (0、負の値) は下限で外す。予約の値・文書用の値は error にしない (warning なら 1.x で足せる)。

| フィールド | 今 | 1.0 | 根拠 |
|---|---|---|---|
| `local_as` (インスタンスの機器・トポロジー外の相手) | `int` | 1〜4294967295 | 4 バイトの AS (RFC 6793)。0 は AS として使えない (RFC 7607) |
| `vni` (L2VNI・L3VNI) | `int` | 1〜16777215 | VNI は 24 ビット (RFC 7348 §5)。0 は多くの機器が受け付けない |
| BFD の `min_tx` / `min_rx` | `int` | 1 以上 | 単位は ms (各社の CLI と同じ。RFC 5880 §4.1 の packet の上では μs)。上限は機器ごとに違う |
| BFD の `multiplier` | `int` | 1〜255 | Detect Mult は 8 ビットで、0 は不正 (RFC 5880 §4.1・§6.8.6) |
| `LacpConfig.min_links` | `int` | 1 以上 | 0 以下は意味がない。機器の上限はまちまち |
| トンネルの `mtu` | 68 以上 | 68〜65535 | IPv4 の Total Length は 16 ビット (RFC 791 §3.1)。68 は分割せずに転送できる最小の大きさ (§3.2) |

- 予約の AS (65535・4294967295 は RFC 7300、23456 は AS_TRANS) と、VNI の 16777215 は通す
- 値域の外の error の文は pydantic の既定 (`Input should be greater than or equal to 1`) でよい
- HSRP の `group_id` (0〜4095) と VRRP / HSRP の `priority` は今の値域のまま。広げる方向 (VRRP の `priority` を 255 まで、など) は 1.x でできる
- BFD のタイマーを ms の整数で持つので、3.3 ms のような値は書けない。要るなら小数を許す (型を広げる) のは 1.x でできる

### D6. 名前を変えないものと、その約束

棚卸し §4 の 4 点は名前を変えず、`docs/reference/` に約束を書く。

- **種類を見分けるキー**: `type` はエンティティやカプセル化の種類 (`vxlans[].type`・`tunnel_interfaces[].type`・`routing_neighbors[].type`)、`mode` は動作の選び方 (`gateway_redundancy[].mode`・`lacp.mode`)。これから足す種類分けもこの区別に従う
- **2 つの `members`**: `lags[].members` は L1 IF の id のリスト、`ethernet_segments[].members` は `{lag:}` / `{interface:}` のリスト。どちらも「束ねる要素」で、形の違いは参照先が 1 種類か 2 種類かから来る
- **エクスポーターの 2 つの `vlans`**: 機器ノードの `vlans` (ポートがある VLAN) と L2VNI の `vlans` (載る VLAN)。どちらも規範キーで、`docs/exporter-cytoscape.md` の注記を残す
- **OSPF の `interface` は L3 IF、IS-IS の `interface` は L1 IF**: OSPF は IP の上で、IS-IS は L2 の上で hello を送るという違いから来る。同じ `interface` でも書く id の種類が違い、別の種類の id を書くと validator が何の id かを添えて誤りを指す (ADR-0015)。
  `update_source` は BGP の用語 (TCP のセッションの送信元) で、OSPF の隣接とは意味が違うので使わない

### D7. 旧名・旧値は移動先を示す error

ADR-0025 D1 と同じく、読み替えはしない。2.0 まで残す (ADR-0027 D7)。

- **実装の位置**: `L1Layer` / `L2Layer` に `model_validator(mode="before")` を足し、`extra="forbid"` の `Extra inputs are not permitted` より先に旧名を捕まえる (既存の `MLNDLTopology.reject_legacy_control_plane`・`L2VxLAN.reject_old_forms` と同じ形)。
  `lacp.mode` と IS-IS の `level` の旧値は `field_validator(mode="before")` で捕まえる。2 つの error が重ならないことをテストで確かめる
- `layer1.lag`: 「`layer1.lag` は `layer1.lags` に改名しました。中身は変わりません。ほかの一覧 (`nodes` / `interfaces` / `links` / `ethernet_segments`) にそろえました (ADR-0028)」
- `layer2.vxlan`: 「`layer2.vxlan` は `layer2.vxlans` に改名しました。中身 (`type` / `vni` / `vlans` / `vteps`) は変わりません (ADR-0028)」
- IS-IS の `level: level-2` など: 「IS-IS の `level` はハイフンではなく下線で書きます (`level_1` / `level_2` / `level_all`) (ADR-0028)」
- `lacp.mode: on` と、YAML が `on` から読む `true`: 「LACP を使わない LAG は `mode: static` と書きます。`on` は YAML で真偽値の `true` と読まれるので、名前を変えました (ADR-0028)」
- `address_families` を書かない・空、`vteps` を書かない・空、`members: []`・`ports: []`、`lacp: {}`: 何を書けばよいかを例で示す (D3・D4)
- 移動先の案内が要らないもの: (1) 既定値をなくした `lacp` と BFD のタイマーは、書いてあった値がそのまま残るので意味が変わらない (書いていなかった YAML は「書いていない」になる)。(2) 値域を狭めたフィールドは、範囲外の値だけが error になる

## Consequences

**良くなること:**
- id を持つエントリの一覧は複数形、1 つを指すキーは単数形、列挙の値は下線区切り、という 3 つの規則に、`gateway_redundancy` の 1 つを除いて例外がなくなる
- 「書いていない」と「既定値と同じ値を書いた」が LACP と BFD で区別できる。エクスポーターの出力とモデルが一致する
- static の LAG を引用符なしで書ける
- 空のリストと範囲外の数を、1.0 から error で止められる。1.0 の後に狭めると 2.0 が要った

**悪くなること・注意:**
- 今の YAML は書き換えが要る: `lag:` → `lags:`、`vxlan:` → `vxlans:`、IS-IS の `level`、`address_families` を書いていないセッション。`lacp: {mode: "on"}` を書いていたら `static` に (今の文書・examples・fixtures にはない)。
  examples・fixtures・`docs/reference/`・CLAUDE.md の例を直す (`docs/decisions/evaluations/` の過去の試し書きは履歴として旧名のまま残す)
- `address_families` を毎回書くので、セッションの行が長くなる (試し書き a1)
- Python の利用者は `layer1.lag` / `layer2.vxlan` の属性名と、`lacp.mode` が `None` になりうることに合わせて直す (モデルは参考。ADR-0027 D1)
- `level_all` の `all` (すべてのレベル) と `all_active` の `all` (すべての脚が転送) は意味が違う。どちらも値の中で読めば紛れない
- IS-IS の `level` はエクスポーターが値をそのまま出す (`cytoscape.py:664`)。ndl-viz の線の札が「IS-IS level_2」になる。ndl-viz で表示を整えるかを決める
- RFC 9130 の YANG に書き出すとき、`level` の値の区切りを変換する (RFC 8345 のエクスポーターは未実装。deferred.md)

**影響を受けるコンポーネント:**
- スキーマ: `layer1.py` (`L1Layer.lags` と旧名の検査、`Lag.members`、`LacpConfig`、ES の `members` とその文)、`layer2.py` (`L2Layer.vxlans` と旧名の検査、`vteps`、`vni`、`Bridge.ports`)、
  `layer3.py` (`Ref("layer2.vxlans")`、トンネルの `mtu`)、`control_plane.py` (`level`、`address_families`、`local_as`、BFD)、`refs.py` (`COLLECTION_LABELS`)、`topology.py` と `index.py` の docstring
- `validator.py`・`derive.py`・`exporter/cytoscape.py`: 属性名の置き換え (`l1.lag` → `l1.lags` など。エクスポーターの出力のキーは変わらない。IS-IS の `level` の値と `lacp.mode` の値は変わる)
- テスト: 改名・旧名の error (と `extra="forbid"` が重ならないこと)・空のリスト・`lacp: {}`・`static` と `on`・値域の端。既存のテストのパスの文字列 (`layer1.lag[0].id`・`layer2.vxlan[0]...`)
- fixtures と examples: `lag:` / `vxlan:` / IS-IS の `level` を書いているものすべて (`tests/fixtures/` の valid / invalid、`examples/eveng-evpn-lab*.yaml`)
- 文書: `docs/reference/` (layer1・layer2・layer3・types・control-plane・validation、`schema.json` の再生成)、`docs/exporter-cytoscape.md` (IS-IS の `level` と `lacp.mode` の値)、CLAUDE.md の例と表
- 下流: ndl-viz (`src/flow/session.ts:39`・`:42` の IS-IS の札。LACP は書かれた値を任意で読んで `LACP <mode>` と出すので、`static` もそのまま出る)

## Alternatives Considered

- **名前を直さず 1.0 を出す**: 採らない。単数形の 2 つとハイフンの値、`on` の罠が 2.0 まで残る
- **IS-IS の `level` をハイフンのまま残す** (network-tech-reviewer): 採らない。RFC と CLI に近いが、値の書き方に例外が残る。ユーザーが下線を選んだ
- **`lacp.mode` の `on` を残し、`true` を読んだら「引用符で囲んでください」と案内する**: 採らない。引用符を忘れやすいことと、`lacp` の下の `on` が逆の意味に読めることは残る。ユーザーが `static` を選んだ
- **LAG を `mode` (active / passive / static) と `lacp` (`min_links`) に割る、`lacp` を `bundling` などに改名する** (linguist の 2.0 の案): 採らない。`static` で引用符の罠と意味の矛盾はほぼ解ける。構造を割ると ADR-0023 の LAG の形がまた変わる
- **`LacpConfig.mode = "active"` を残す** (Pass A の spec-architect・dsl-designer。Linux bonding などの慣用): 採らない。機器ごとに既定値が違い、static の LAG と「書いていない」が見分けられない
- **`mode` だけ既定値をなくし `min_links = 1` を残す** (Pass A の example-author): 採らない。既定値をなくしても必須にはならず、書かなければ「書いていない」になるだけなので、書く量は増えない
- **BFD のタイマーの既定値を 300 / 300 / 3 で固める**: 採らない。機器ごとに既定値が違う
- **エクスポーターの機器ノードの `vlans` を `port_vlans` などに改名** (Pass A の dsl-designer。Pass B で取り下げ): 採らない。ndl-viz が読む規範キーで、意味の違いは文書の注記で足りる
- **OSPF の `interface` を `update_source` に** (Pass A の dsl-designer。Pass B で取り下げ): 採らない。D6
- **`ethernet_segments[].members` を `legs` に**: 採らない。「束ねる要素」の語は `members` が自然で、ADR-0023 で決めたばかり
- **`gateway_redundancy` を `gateway_redundancies` に**: 採らない。D1 の例外
- **予約の AS・VNI を error に、AS_TRANS を warning に**: 採らない。error にすると実機が受け付ける値まで止めかねない。warning は 1.x で足せる
- **IS-IS の機器ごとの is-type (level-1 だけ / level-2 だけ / 両方) をこの ADR で足す** (network-tech-reviewer の確認): 採らない。セッションの `level` で隣接は書ける。機器ごとの値は任意のキーとして 1.x で足せる

## References

- RFC 5880 §4.1・§6.8.6 (BFD)、RFC 6793 (4 バイトの AS)、RFC 7300 (予約の AS)、RFC 7348 §5 (VXLAN)、RFC 7607 (AS 0)、RFC 791 §3.1・§3.2 (IPv4)、RFC 9130 (IS-IS の YANG)
- ADR-0001、ADR-0010、ADR-0011、ADR-0014、ADR-0015、ADR-0018、ADR-0022、ADR-0023、ADR-0025、ADR-0026、ADR-0027
- 試し書き: [evaluations/adr0028/](../evaluations/adr0028/recommendation.md) の a1〜a5、`passb/` の b1〜b6
