# ADR-0028: 1.0 の前の名前と型の直し

- **Status**: Accepted (2026-11-20 に Pass C で確定。同日に実装: スキーマ・エクスポーター・テスト・docs・改訂の注記。ndl-viz の対応 (IS-IS の札と `min_links` の読み先) はこれから)
- **Date**: 2026-11-20
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、
  ユーザー (IS-IS の `level` を下線区切りに、LACP の既定値をなくす、値域を狭める直しを入れる、`lacp.mode` の `on` を `static` に、`min_links` を LAG の直下に)
- **Pass**: C ([評価メモ](evaluations/adr0028/evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0028](drafts/0028-names-and-types.md)
- **Amends**: ADR-0001 D8 (表の `layer1.lag`)、ADR-0010 (`address_families` の既定値)、ADR-0014 D3 (`vteps` を型で 1 つ以上に)、ADR-0018 D1 (`bridges[].ports` を 1 つ以上に)、
  ADR-0023 D1 (`layer1.lag` の名前、`lacp` の形と既定値)、ADR-0025 D1 (移動先を示す error の一覧)、ADR-0026 (`layer2.vxlan` の名前)、ADR-0027 (「1.0 の前に必須になるもの」の表)
- **関連**: [1.0 に向けた棚卸し](evaluations/release-1.0/inventory.md) §2〜§4、ADR-0011 D4 (`gateway_redundancy` の名前は変えない)、ADR-0022 (記載の粒度)

## Context

ADR-0027 で、1.0 の後に名前・既定値・意味を変える、型を狭める、検査を強めるのは 2.0 が要ると決めた。型を広げる・必須を任意にする・既定値のない任意のキーを足すのは 1.x でできる。
だから 1.0 は**狭く始める**。1.0 の前の今しか直せないものが、今の実装に次のとおりある (2026-11-19 に確かめた)。

- id を持つエントリの一覧で `layer1.lag` (`src/mlndl/schema/layer1.py:439`) と `layer2.vxlan` (`layer2.py:256`) だけが単数形
- 列挙の値で IS-IS の `level` (`control_plane.py:212`) だけがハイフン区切り (`level-1` / `level-2` / `level-all`)
- LAG の `lacp.mode` の `on` (static の LAG) は、引用符なしで書くと YAML (PyYAML は YAML 1.1) が真偽値の `true` と読み、error になる (試し書き B1)。`lacp` の下に「LACP を使わない」値があるのも読み手を惑わせる
- `lacp.min_links` は LACP を使わない LAG でも効く (Cisco / Arista の `port-channel min-links`、Junos の `minimum-links`。LACP の下にあるのは Linux bonding だけ) のに、`lacp` の下にある
- `L2VxLAN.vteps` と `BgpSession.address_families` は既定値 `[]` で、空の意味が決まっていない (`layer2.py:157`・`control_plane.py:161`)。`Lag.members` (`layer1.py:325`) と `Bridge.ports` (`layer2.py:103`) は空でも通る
- 既定値で埋めると「書いていない」と区別がつかないものがある: `LacpConfig.mode = "active"`・`min_links = 1` (`layer1.py:304-305`)、BFD の `min_tx = 300`・`min_rx = 300`・`multiplier = 3` (`control_plane.py:91-93`)。
  エクスポーターは LACP を書かれた値だけ出していて (`exporter/cytoscape.py:146`)、モデルの既定値と食い違っている
- 値域のない整数がある: `local_as` (`control_plane.py:39`・`:117`)、`vni` (`layer2.py:155`・`:201`)、BFD のタイマー、`min_links`。トンネルの `mtu` には上限がない (`layer3.py:251`)

## Decision

### D1. id を持つエントリの一覧は複数形、1 つを指す参照キーは単数形

| 今 | 1.0 |
|---|---|
| `layer1.lag` | `layer1.lags` |
| `layer2.vxlan` | `layer2.vxlans` |

- 中身 (エントリのキー) は変えない
- 1 つを指す参照キーは単数のまま: `attaches_to: {lag: <id>}`、VLAN / bridge のポートと ES の脚の `{lag:}`、VRF の `l3vni:`。`interfaces` と `{interface:}` の関係と同じで、キーの名前が参照先の種類を示す (ADR-0001 D8)
- ID のリスト (`members` / `sources` / `vlans` / `vteps` / `address_families`) はすでに複数形。`control_plane` の `bgp` / `ospf` / `isis` / `bfd` はプロトコルの名前で、この規則の外
- **例外**: `layer3.interfaces[].gateway_redundancy` はリストだが単数のまま (ADR-0011 D4 の名前)。エントリは id を持たない 1 つの IF の冗長の設定で、規則の範囲 (id を持つエントリの一覧) に入らない
- `Ref` のパス (`Ref("layer1.lags")`・`Ref("layer2.vxlans", where=...)`) と、参照先の種類を示すメッセージの語 (`refs.py` の `COLLECTION_LABELS`) も直す
- `vnis` は採らない。番号のリストに見え、エントリの `vni:` と語が重なる

### D2. 列挙の値は下線区切り。IS-IS の `level` を `level_1` / `level_2` / `level_all` に (ユーザー決定)

- 複数の語からなる列挙の値は下線で区切る (`ipv4_unicast` / `l2vpn_evpn` / `anycast_gateway` / `all_active` / `ipsec_vti`)。IS-IS だけを例外にしない
- RFC 9130 の YANG の `level-type` と各社の CLI (`is-type level-1-2` など) からは区切りだけが離れる。ほかの値も RFC や CLI の綴りそのままではない
- `level_1_2` は採らない。3 つの値のうち 1 つだけが合成の名前になる

### D3. 要素なしでは成り立たないリストは、型で 1 つ以上にする

**基準**: エントリがリストの要素なしでは成り立たない (何も束ねない LAG、何も転送しない bridge、どこにも載らない VNI、何も運ばないセッション) なら、必須・1 つ以上にし、既定値を持たない。
空がそれだけで意味を持つ、またはエントリを先に宣言してあとから足すリストは、空を許す。

| フィールド | 今 | 1.0 |
|---|---|---|
| `L2VxLAN.vteps` | 既定値 `[]`、空を validator で error | 必須、1 つ以上 (ADR-0014 D3 の改訂) |
| `BgpSession.address_families` | 既定値 `[]` | 必須、1 つ以上 (ADR-0010 の改訂) |
| `Lag.members` | 必須、空でも通る | 必須、1 つ以上 (メンバー 1 つの LAG は ES の脚で使う) |
| `Bridge.ports` | 既定値 `[]` | 必須、1 つ以上 (ADR-0018 D1 の改訂。ポートが 1 つの warning は残す) |
| `EthernetSegment.members` | 2 つ以上を `field_validator` で | 2 つ以上を型にも書く (結果は変わらない) |

- **空を許すもの**: 各層の一覧 (`nodes` / `lags` / `vxlans` など)、VLAN の `trunk_ports` / `access_ports` (空 = SVI だけの VLAN)、`gateway_redundancy` (空 = 冗長なし)、
  `route_targets` の `import` / `export` (片方向だけの VRF)、`BgpInstance` / `OspfInstance` / `IsisInstance` / `BFDConfig` の `nodes` (エントリを先に宣言して機器をあとから足す)、`meta.network_types`
- `address_families` の既定値を `[ipv4_unicast]` にしない。1.0 で固まり、EVPN のセッションで `l2vpn_evpn` を書き忘れたのと区別できない
- **メッセージ**: 型 (`Field(min_length=...)`) に書いて `schema.json` に `minItems` を出す。実行時の文は `mode="before"` のバリデーターで、何を書けばよいかを示す文にする (pydantic の既定の `List should have at least 1 item` / `Field required` にしない)。
  今の親切な文は保つ (`vteps` の「L2VNI が載る VTEP を vteps: [<layer2.vteps の id>] で書いてください」、ES の `members` の「1 台の機器だけの LAG は ... に書けば足ります」。後者の `layer1.lag` は `layer1.lags` に直す)。
  `address_families` には例を添える (「`[ipv4_unicast]`、EVPN なら `[l2vpn_evpn]`」)。文面は参考 (ADR-0027 D1)

### D4. LAG の束ね方: `lacp` は `mode` だけ、`static` を足し、`min_links` は LAG の直下に (ユーザー決定)

```yaml
lags:
  - {id: lag-leaf1-bond1, node: leaf1, name: bond1, members: [leaf1-swp1, leaf1-swp2], lacp: {mode: active}, min_links: 2}
  - {id: lag-leaf1-bond2, node: leaf1, name: bond2, members: [leaf1-swp3], lacp: {mode: static}}
  - {id: lag-leaf1-bond3, node: leaf1, name: bond3, members: [leaf1-swp4]}             # 束ね方は書いていない
```

| フィールド | 今 | 1.0 |
|---|---|---|
| `lags[].lacp` | 任意。`{mode, min_links}`、`mode` の既定値 `"active"` | 任意。`{mode}` で、`lacp` を書くなら `mode` は必須 |
| `lacp.mode` | `active` / `passive` / `on` | `active` / `passive` / **`static`** |
| `lags[].min_links` | (`lacp.min_links`、既定値 `1`) | 任意、既定値なし、1 以上 |

- **`static`**: LACP を使わずに束ねる LAG (Cisco / Arista の `channel-group N mode on`、Junos の LACP を書かない AE、Linux bonding の 802.3ad 以外の mode)。
  `on` をやめる理由は 2 つ。引用符なしの `on` を YAML が `true` と読むこと、`lacp` の下で「LACP が on」と読めて意味が逆になること。`static` は各社の文書の「static LAG」「static port-channel」と同じ語で、`active` / `passive` と同じく束ね方の状態を表す
- **`min_links`**: 「最低何本のメンバーが上がっていれば LAG が上がるか」で、LACP を使うかと関係なく効くので LAG の直下に置く。`lacp` は「LACP をどう張るか (張らないか)」だけの欄になる。
  Linux bonding は 802.3ad の mode でしか `min_links` が効かないが、その制約は言語では見ない (下流のツールか、1.x の warning)
- **書き方と意味**:

  | 書き方 | 意味 |
  |---|---|
  | `lacp` を書かない | 束ね方を書いていない (LACP を使うか使わないか分からない) |
  | `lacp: {mode: active}` / `{mode: passive}` | LACP で束ねる |
  | `lacp: {mode: static}` | LACP を使わずに束ねる |
  | `lacp: {}` | **error**。`mode` を書く |
  | `min_links: 2` (LAG の直下) | 最低 2 本のメンバーが上がっていれば LAG が上がる。`lacp` と独立 |

- **言語として既定値を定めないもの** (書かなければ「書いていない」。ADR-0023 D4 の `redundancy_mode` と同じ): `lacp.mode`、`min_links`、BFD の `min_tx` / `min_rx` / `multiplier`。
  どの値になるかは機器の既定値で、`docs/reference/` にそう書く
- **既定値のまま 1.0 で固めるもの** (「書いていない = 使わない」が実機の挙動と一致する): VLAN のポートの `native = False`、`route_reflector_client = False`、セッションの `bfd = False` (BGP / OSPF / IS-IS)。
  `vrf` を書かない L3 IF・トンネル IF・BGP / OSPF のインスタンスは default VRF。`docs/reference/` に「書かなかったときの意味」の一覧を載せる
- `lacp: {}` 以外の中身のない任意のオブジェクト (`route_targets: {}`) はこの ADR では扱わない。`meta` は未知のキーの入れ物なので空でよい
- `passive` どうし、`static` と `active` の組み合わせ (LAG が上がらない) の検査は、1.x で warning として足せる

### D5. 値域を狭める (ユーザー決定)

**原則**: プロトコルのフィールドの幅が狭い (8 / 16 / 24 ビット) ものは上限と下限を置く。幅が広く、機器の上限がまちまちなものは下限だけを置く。意味のない値 (0、負の値) は下限で外す。
予約の値・文書用の値は error にしない (warning なら 1.x で足せる)。値域の外の error の文は pydantic の既定 (`Input should be greater than or equal to 1`) でよい。

| フィールド | 今 | 1.0 | 根拠 |
|---|---|---|---|
| `local_as` (インスタンスの機器・トポロジー外の相手) | `int` | 1〜4294967295 | 4 バイトの AS (RFC 6793)。AS 0 は使えない (RFC 7607) |
| `vni` (L2VNI・L3VNI) | `int` | 1〜16777215 | VNI は 24 ビット (RFC 7348 §5)。0 は多くの機器が受け付けない |
| BFD の `min_tx` / `min_rx` | `int`、既定値 300 | 1 以上、既定値なし | 単位は ms (各社の CLI と同じ。RFC 5880 §4.1 の packet の上では μs)。上限は機器ごとに違う |
| BFD の `multiplier` | `int`、既定値 3 | 1〜255、既定値なし | Detect Mult は 8 ビットで、0 は不正 (RFC 5880 §4.1・§6.8.6) |
| `lags[].min_links` | `int`、既定値 1 | 1 以上、既定値なし | 0 以下は意味がない。機器の上限はまちまち |
| トンネルの `mtu` | 68 以上 | 68〜65535 | IPv4 の Total Length は 16 ビット (RFC 791 §3.1)。68 は分割せずに転送できる最小の大きさ (§3.2) |

- 予約の AS (65535・4294967295 は RFC 7300、23456 は AS_TRANS (RFC 6793)) と VNI の 16777215 は通す
- HSRP の `group_id` (0〜4095) と VRRP / HSRP の `priority` は今の値域のまま。広げる方向 (VRRP の `priority` を 255 まで、など) は 1.x でできる
- BFD のタイマーを ms の整数で持つので、3.3 ms のような値は書けない。要るなら小数を許す (型を広げる) のは 1.x でできる
- `local_as` の asdot 表記 (`65001.100`、RFC 5396) は 1.x で `int | str` に広げられる

### D6. 名前を変えないものと、その約束

次は名前を変えず、2.0 まで動かさない。`docs/reference/` と `docs/exporter-cytoscape.md` に約束として書く。

- **種類を見分けるキー**: `type` はエンティティやカプセル化の種類 (`vxlans[].type`・`tunnel_interfaces[].type`・`routing_neighbors[].type`)、`mode` は動作の選び方 (`gateway_redundancy[].mode`・`lacp.mode`)。これから足す種類分けもこの区別に従う
- **2 つの `members`**: `lags[].members` は L1 IF の id のリスト、`ethernet_segments[].members` は `{lag:}` / `{interface:}` のリスト。どちらも「束ねる要素」で、形の違いは参照先が 1 種類か 2 種類かから来る
- **エクスポーターの 2 つの `vlans`**: 機器ノードの `vlans` (ポートがある VLAN) と L2VNI の `vlans` (載る VLAN)。どちらも規範キーで、`docs/exporter-cytoscape.md` の注記を残す
- **OSPF の `interface` は L3 IF、IS-IS の `interface` は L1 IF**: OSPF は IP の上で、IS-IS は L2 の上で hello を送るという違いから来る。別の種類の id を書くと、validator が何の id かを添えて誤りを指す (ADR-0015)。
  `update_source` は BGP の用語 (TCP のセッションの送信元) で、OSPF の隣接とは意味が違うので使わない
- **`gateway_redundancy`** (D1 の例外) と **`local_as`** (どちらの端も「その端自身の AS」。ADR-0010)

### D7. 旧名・旧値は移動先を示す error

ADR-0025 D1 と同じく読み替えはせず、2.0 まで残す (ADR-0027 D7)。

| 旧名・旧値 | 捕まえる場所 | メッセージ (案) |
|---|---|---|
| `layer1.lag` | `L1Layer` の `model_validator(mode="before")` | 「`layer1.lag` は `layer1.lags` に改名しました。中身は変わりません。id を持つエントリの一覧は複数形にそろえました (ADR-0028)」 |
| `layer2.vxlan` | `L2Layer` の `model_validator(mode="before")` | 「`layer2.vxlan` は `layer2.vxlans` に改名しました。中身 (`type` / `vni` / `vlans` / `vteps`) は変わりません (ADR-0028)」 |
| IS-IS の `level: level-2` など | `IsisAdjacency` の `field_validator("level", mode="before")` | 「IS-IS の `level` はハイフンではなく下線で書きます (`level_1` / `level_2` / `level_all`) (ADR-0028)」 |
| `lacp.mode: "on"` | `LacpConfig` の `field_validator("mode", mode="before")` | 「`on` は `static` に改名しました。LACP を使わずに束ねる LAG は `mode: static` と書きます (ADR-0028)」 |
| `lacp.mode` に真偽値 (引用符なしの `on` / `off` / `yes` / `no` を YAML が読んだもの) | 同上 | 「YAML が引用符なしの `on` などを真偽値として読みました。LACP を使わずに束ねる LAG は `mode: static`、LACP で束ねるなら `active` / `passive` と書きます (ADR-0028)」 |
| `lacp.min_links` | `LacpConfig` の `model_validator(mode="before")` | 「`min_links` は LACP を使うかと関係なく効くので、LAG の直下 (`lags[].min_links`) に移しました (ADR-0028)」 |

- `mode="before"` のバリデーターは型の検査と `extra="forbid"` の `Extra inputs are not permitted` より先に走るので、2 つの error は重ならない (既存の `MLNDLTopology.reject_legacy_control_plane`・`L2VxLAN.reject_old_forms` と同じ形)。
  旧名 1 つだけのとき、旧名と未知のキーを一緒に書いたときに、案内の文が出ることをテストで確かめる
- `address_families` / `vteps` を書かない・空、`members: []`・`ports: []`、`lacp: {}` は D3・D4 の案内の文
- 移動先の案内が要らないもの: (1) 既定値をなくした `lacp.mode`・`min_links`・BFD のタイマーは、書いてあった値がそのまま残るので意味が変わらない (書いていなかった YAML は「書いていない」になる)。
  (2) 値域を狭めたフィールドは、範囲外の値だけが error になる

## Consequences

**良くなること:**
- id を持つエントリの一覧は複数形、1 つを指すキーは単数形、列挙の値は下線区切り、という 3 つの規則に、`gateway_redundancy` の 1 つを除いて例外がなくなる
- 「書いていない」と「既定値と同じ値を書いた」が LACP と BFD で区別できる。エクスポーターの出力とモデルが一致する
- static の LAG を引用符なしで書ける。`lacp` は LACP の欄、`min_links` は LAG の欄になり、置き場所と意味が一致する
- 空のリストと範囲外の数を、1.0 から error で止められる。1.0 の後に狭めると 2.0 が要った

**悪くなること・注意:**
- 今の YAML は書き換えが要る: `lag:` → `lags:`、`vxlan:` → `vxlans:`、IS-IS の `level`、`lacp.min_links` → `min_links`、`address_families` を書いていないセッション。
  examples・fixtures・`docs/reference/`・CLAUDE.md の例を直す (`docs/decisions/evaluations/` の過去の試し書きは履歴として旧名のまま残す)。リリースの前に旧名が残っていないかを grep で確かめる
- `address_families` を毎回書くので、セッションの行が長くなる (試し書き a1)
- `lacp` を書いても書かなくても「LACP を使うか」が分からない LAG が残る (`lacp` を書かない LAG)。「書かなければ書いていない」の原則どおりで、D4 の表で示すだけにする
- Python の利用者は属性名 (`layer1.lags`・`layer2.vxlans`・`Lag.min_links`) と、`lacp.mode` と BFD のタイマーが `None` になりうることに合わせて直す (モデルは参考。ADR-0027 D1)
- `vxlans` は VXLAN のトンネルの 1 本ずつとも読めるが、エントリは VNI (ブロードキャストドメインか、L3VNI)。`vnis` を採らなかった理由 (D1) を `docs/reference/` にも書く
- `level_all` の `all` (すべてのレベル) と `all_active` の `all` (すべての脚が転送) は意味が違う。どちらも値の中で読めば紛れない
- IS-IS の `level` と `lacp.mode` はエクスポーターが値をそのまま出す (`cytoscape.py:664`・`:146`)。ndl-viz の線の札が「IS-IS level_2」になる。整えて出すかは ndl-viz で決める。
  `lacp` の出力から `min_links` が外れ、LAG の `min_links` になる (規範キーの変更。1.0 の前なので約束の対象外)
- 1.0 の後は、ここで決めた名前を 2.0 まで変えられない。旧名の error も 2.0 まで抱える
- RFC 9130 の YANG に書き出すとき、`level` の値の区切りを変換する (RFC 8345 のエクスポーターは未実装。deferred.md)

**影響を受けるコンポーネント:**
- スキーマ: `layer1.py` (`L1Layer.lags` と旧名の検査、`Lag.members`・`Lag.min_links`、`LacpConfig`、ES の `members` とその文)、`layer2.py` (`L2Layer.vxlans` と旧名の検査、`vteps`、`vni`、`Bridge.ports`)、
  `layer3.py` (`Ref("layer2.vxlans")`、トンネルの `mtu` とそのコメント)、`control_plane.py` (`level`、`address_families`、`local_as`、BFD)、`refs.py` (`COLLECTION_LABELS`)、`topology.py` と `index.py` の docstring
- `validator.py`・`derive.py`・`exporter/cytoscape.py`: 属性名の置き換え (`l1.lag` → `l1.lags` など)。エクスポーターの出力のキー `lags` は変わらない。LAG の `lacp` から `min_links` を出し、LAG の直下に `min_links` を出す
- テスト: 改名・旧名と旧値の error (と `extra="forbid"` が重ならないこと)・空のリスト・`lacp: {}`・`static` と `on` と真偽値・`lacp.min_links`・値域の端。既存のテストのパスの文字列 (`layer1.lag[0]...`・`layer2.vxlan[0]...`)
- fixtures と examples: `lag:` / `vxlan:` / IS-IS の `level` / `lacp.min_links` を書いているものすべて
- 文書: `docs/reference/` (layer1・layer2・layer3・types・control-plane・validation、`schema.json` の再生成)、`docs/exporter-cytoscape.md` (LAG の `lacp` と `min_links`、IS-IS の `level` の値)、CLAUDE.md の例と表
- 下流: ndl-viz。`src/flow/session.ts:39`・`:42` の IS-IS の札、`src/types/topology.ts:91` の LAG の `lacp` の型 (`min_links` を LAG の直下に)、`src/components/PropertiesPanel.tsx:93` の `min_links` の表示

## Alternatives Considered

- **名前を直さず 1.0 を出す**: 採らない。単数形の 2 つとハイフンの値、`on` の罠が 2.0 まで残る
- **IS-IS の `level` をハイフンのまま残す** (network-tech-reviewer、Pass A): 採らない。RFC と CLI に近いが、値の書き方に例外が残る (ユーザー決定)
- **`lacp.mode` の `on` を残し、真偽値を読んだら「引用符で囲んでください」と案内する**: 採らない。引用符を忘れやすいことと、`lacp` の下の `on` が逆の意味に読めることは残る (ユーザー決定)
- **`on` を `none` / `manual` に**: 採らない。`none` は「LACP の設定なし」(`lacp` を書かない) と紛れる。`manual` は一部の機器の語で、`static` ほど通じない (linguist)
- **`min_links` を `lacp` の下に残す** (spec-architect・dsl-designer。構造を割るほどではない、`lacp` を束ね方の欄と読めばよい): 採らない。`min_links` は LACP と独立に効き、1.0 の後は動かせない (ユーザー決定。linguist・network-tech-reviewer)
- **`lacp` を `{mode}` のオブジェクトでなく値 (`lacp: active`) にする**: 採らない。LACP の設定 (rate など) を 1.x で任意のキーとして足す余地を残す
- **LACP の既定値を残す** (Pass A の spec-architect・dsl-designer。Linux bonding などの慣用): 採らない。機器ごとに既定値が違い、static の LAG と「書いていない」が見分けられない (ユーザー決定)
- **BFD のタイマーの既定値を 300 / 300 / 3 で固める**: 採らない。機器ごとに既定値が違う
- **インスタンスと BFD の `nodes` を 1 つ以上に** (Pass C の dsl-designer): 採らない。エントリを先に宣言して機器をあとから足す書き方を残す。空のインスタンスの warning は 1.x で足せる
- **エクスポーターの機器ノードの `vlans` を `port_vlans` などに、OSPF の `interface` を `update_source` に** (Pass A の dsl-designer。Pass B で取り下げ): 採らない。D6
- **`ethernet_segments[].members` を `legs` に、`gateway_redundancy` を `gateway_redundancies` に**: 採らない。D6・D1
- **予約の AS・VNI を error に、AS_TRANS を warning に**: 採らない。error にすると実機が受け付ける値まで止めかねない。warning は 1.x で足せる
- **IS-IS の機器ごとの is-type (level-1 だけ / level-2 だけ / 両方) を足す**: 採らない。セッションの `level` で隣接は書ける。機器ごとの値は任意のキーとして 1.x で足せる

## Pass A との差分

Pass C の 5 エージェントは drafts/0028 を読まずに評価メモから再設計し、骨子 (D1〜D7) は改訂 1 と同じ結論になった。変わった点:

- **D4**: `min_links` を `lacp` の下から LAG の直下に移した (ユーザー決定。linguist・network-tech-reviewer が各社の `min-links` が LACP と独立に効くことを確かめた)。`lacp` は `{mode}` だけになり、書くなら `mode` が必須。`lacp: {}` の error の案内は「`mode` を書く」になった
- **D7**: 旧名・旧値を表にした。`lacp.mode` に真偽値が入ったとき (引用符なしの `on` / `off` / `yes` / `no`) と、`lacp.min_links` の移動先を足した
- **D3**: 空を許すリストを列挙した (dsl-designer が全リストを表にして確かめた)。メッセージは `mode="before"` のバリデーターで出す形に決めた
- **D5**: asdot 表記を 1.x で広げられることを足した (network-tech-reviewer)
- **Consequences**: `vxlans` の読まれ方、1.0 の後は 2.0 まで変えられないこと、旧名の grep (spec-architect)。ndl-viz の `lacp` の型と `min_links` の表示を足した

## References

- RFC 5880 §4.1・§6.8.6 (BFD)、RFC 5396 (asdot)、RFC 6793 (4 バイトの AS)、RFC 7300 (予約の AS)、RFC 7348 §5 (VXLAN)、RFC 7607 (AS 0)、RFC 791 §3.1・§3.2 (IPv4)、RFC 9130 (IS-IS の YANG)
- 棚卸し: [evaluations/release-1.0/inventory.md](evaluations/release-1.0/inventory.md)
- Pass A の検討: [evaluations/adr0028/recommendation.md](evaluations/adr0028/recommendation.md)、評価メモ: [evaluations/adr0028/evaluation.md](evaluations/adr0028/evaluation.md)
- 試し書き: `evaluations/adr0028/` (a1〜a5)、`passb/` (b1〜b6)、`passc/` (P1〜P3)
- 関連 ADR: ADR-0001、ADR-0010、ADR-0011、ADR-0014、ADR-0015、ADR-0018、ADR-0022、ADR-0023、ADR-0025、ADR-0026、ADR-0027
