# ADR-0028 横断評価メモ (Pass B, 2026-11-19)

[Pass A のドラフト](../../drafts/0028-names-and-types.md) を 5 エージェントが並列に評価した。統合担当は報告をコード・RFC の本文・試し書きの結果と照らして確かめ、割れた 1 点 (`lacp.mode` の `on`) をユーザーが決めた。
ユーザーが Pass A で決めた 3 点 (IS-IS の `level` を下線に、LACP の既定値を両方なくす、値域を狭める直しを入れる) は前提とした。

## 判定

| エージェント | 判定 | いちばんの指摘 |
|---|---|---|
| spec-architect | Pass C に進めてよい (加筆 3 点) | D7 の実装の位置 (`L1Layer` / `L2Layer` の `model_validator(mode="before")`) が書いていない。影響を受けるコンポーネントの漏れ。Amends に ADR-0001・0026 |
| linguist | 方向は妥当 | **高**: `lacp` の下に「LACP を使わない」値 `on` があるのは矛盾。`gateway_redundancy` はリストなのに単数で、D1 の規則に但し書きが要る |
| dsl-designer | 方向は妥当 | **高**: `Bridge.ports` が D3 の表から漏れている。メッセージの実装の形を 1 つに。Pass A の 2 案 (エクスポーターの `vlans`、OSPF の `update_source`) は取り下げ |
| network-tech-reviewer | 承認 (加筆 3 点) | RFC の節番号を確かめた。BFD のタイマーの単位 (言語は ms、RFC 5880 は μs) の注記。IS-IS の機器ごとの is-type は 1.x で足せる |
| example-author | — | 試し書き B1〜B6。`lacp` の 4 通りの書き方の意味を表にしてほしい |

## 試し書き (`passb/`)

改名した所を今の形に戻したコピーを、今の validator で `--strict` で検証した (2026-11-19)。

| ファイル | ドラフトのとおりなら | 今の validator |
|---|---|---|
| `b1-static-and-unwritten-lacp.yaml` | valid | **error**: `lacp: { mode: on }` の `on` を YAML が真偽値 `true` と読み、`mode` の値域の外になる |
| `b2-empty-lacp.yaml` | error (`lacp: {}`) | 通る |
| `b3-ranges.yaml` | error 9 本 (値域の外の端) | 通る (値域がない) |
| `b4-ranges-ok.yaml` | valid (値域の内の端) | 通る |
| `b5-single-member-lag-es.yaml` | valid (メンバー 1 つの LAG を ES で束ねる) | 通る |
| `b5b-empty-lag.yaml` | error (`members: []`) | 通る |
| `b6-plural-collection-singular-ref.yaml` | valid (`lags` と `{lag:}` を並べる) | 通る |

統合担当が足した確認: ポートが空の bridge (`ports: []`) と、中身のない `route_targets: {}` は、今は `--strict` でも何も出ずに通る。

## 確かめたこと

- **`mode: on` は YAML で `true` になる** (統合担当が `yaml.safe_load("a: {mode: on}")` で確かめた。`{'mode': True}`)。ドラフトの「static の LAG は `lacp: {mode: on}`」は、そのままでは書けない。
  今の文書・examples・fixtures に `mode: on` の例はない (`schema.json` の列挙だけ)。linguist の意味の矛盾の指摘と合わせて、ユーザーが **`static` に改名** と決めた
- **`gateway_redundancy` (`layer3.py:160`) だけがリストで単数**。ほかの id を持つエントリの一覧はみな複数形、ID のリスト (`members` / `sources` / `vteps` / `address_families`) もみな複数形。
  `gateway_redundancy` のエントリは id を持たない。D1 の規則を「id を持つエントリの一覧」と書き、`gateway_redundancy` は ADR-0011 D4 の名前のまま残すと注記する
- **`Bridge.ports` (`layer2.py:103`) は既定値 `[]` で、空でも warning すら出ない**。ポートが 1 つのときの warning (ADR-0018 D1) はあるが 0 個にはない。D3 に足す
- **RFC の節番号** (network-tech が本文で確かめた): RFC 5880 §4.1 (Detect Mult は 8 ビット、Desired Min TX / Required Min RX は 32 ビットの μs)、§6.8.6 (Detect Mult が 0 の packet は捨てる)。RFC 7348 §5 (VNI は 24 ビット)。
  RFC 6793 (4 バイトの AS)、RFC 7607 (AS 0)。RFC 791 §3.1 (Total Length は 16 ビット)。68 は §3.2 の「分割せずに転送できる最小の大きさ」で、Total Length の最小値ではない。65535 / 4294967295 の予約は RFC 7300
- 旧名の error と `extra="forbid"` の `Extra inputs are not permitted` は、`model_validator(mode="before")` が先に例外を出せば重ならない。既存の `L2VxLAN.reject_old_forms` (`layer2.py:160-177`) と `MLNDLTopology.reject_legacy_control_plane` (`topology.py:43`) が同じ形
- ndl-viz の IS-IS の札は `level` の値をそのまま出す (`src/flow/session.ts:42`、コメントの例は `:39`)

## 採った指摘 (改訂 1)

| 指摘 | 誰 | 改訂 |
|---|---|---|
| `lacp.mode` の `on` を `static` に (YAML の真偽値の罠と、意味の矛盾) | linguist・統合担当 (試し書き B1)。決定はユーザー | D4・D7 |
| `lacp` の書き方 4 通りの意味 (書かない / `mode` だけ / `min_links` だけ / 両方)。`min_links` は LACP を張るかと独立 (static でも効く) | example-author・network-tech | D4 |
| BFD・LACP は言語として既定値を定義しない (機器任せ) と文書に書く | spec-architect | D4 |
| `Bridge.ports` を 1 つ以上に | dsl-designer | D3 |
| D1 の規則の範囲 (id を持つエントリの一覧) と `gateway_redundancy` の例外 | linguist | D1 |
| メッセージの実装の形: `Field(min_length=...)` を残して `schema.json` に `minItems` を出し、文はバリデーターで案内の文に。ES の `members` の今の文 (「1 台の機器だけの LAG は ...」) も保つ | dsl-designer・spec-architect | D3 |
| `route_targets: {}` などの中身のない任意のオブジェクトは扱わない、と書く | dsl-designer | D4 |
| 値域の決め方の原則 (幅の狭いフィールドは上下限、幅が広く実装の上限がまちまちなものは下限だけ)。値域の error の文は pydantic の既定でよい。HSRP の `group_id` は今のまま | dsl-designer・example-author | D5 |
| BFD のタイマーの単位の注記、RFC の節番号、RFC 7300 | network-tech | D5・References |
| D6 の OSPF / IS-IS の `interface` に「validator がどちらの id かを見て誤りを指す」 | linguist | D6 |
| D7 に実装の位置。最後の段落を分けて書く。IS-IS のメッセージは「ハイフンではなく下線」 | spec-architect・linguist | D7 |
| Amends に ADR-0001 (D8 の表の `layer1.lag`)・ADR-0026 (CLAUDE.md の `layer2.vxlan`) | spec-architect | 冒頭 |
| 影響を受けるコンポーネントの漏れ (tests のパスの文字列、fixtures・examples の一覧、docstring、`docs/reference/` の各ファイル、ndl-viz の `session.ts`) | spec-architect | Consequences |
| IS-IS の機器ごとの is-type は 1.x で任意のキーとして足せる | network-tech | Alternatives |
| `level_all` の `all` と `all_active` の `all` は意味が違う | linguist | Consequences |

## 採らなかった指摘

| 指摘 | 誰 | 理由 |
|---|---|---|
| `lacp` の改名は 2.0 に送る | linguist | 1.0 の後の改名は 2.0 が要る (ADR-0027 D2)。直せるのは今だけ。値の `on` を `static` にすれば、キーの改名なしに引用符の罠と意味の矛盾がほぼ解ける |
| LAG を `mode` (active / passive / static) と `lacp` (`min_links`) に割る | linguist (2.0 の案として) | `static` で足りる。`min_links` は LACP のない LAG でも効くので、`lacp` の下にあるのは名前の問題として残るが、構造を割るほどではない |
| 予約の AS 23456 を warning に | network-tech | warning は 1.x で足せる (ADR-0027 D2)。この ADR では扱わない |
| `local_as` の型を共有の `Annotated` に | example-author | 実装の書き方で、ADR では決めない |
| 「旧名の error と `extra="forbid"` の error は重ならない」をテストで確かめる | dsl-designer | ADR ではなく実装のテストで確かめる (D7 にテストを書くと書く) |

## 残る論点 (Pass C 向け)

1. **`lacp` の下の `min_links`**: `min_links` は LACP を使うかと関係なく効く (static の LAG でも効く)。`lacp` の下に置いたままでよいか。キーの改名と構造の分割は Pass B で採らなかったが、1.0 の後は動かせない
2. **メッセージを型とバリデーターのどちらで出すか**: `Field(min_length=...)` で `schema.json` に `minItems` を出しつつ、文は案内の文にする方法 (Pass B の dsl-designer の案) が、既存のコードの流儀と食い違わないか
3. **D3 の線引きの最終確認**: スキーマのすべてのリストに基準 (要素なしでは成り立たないか) を当てはめ、漏れと行き過ぎがないか

## Pass C への Input サマリ

**Pass C で参照するもの**: 本評価メモ、[Pass A の検討](recommendation.md)、[1.0 に向けた棚卸し](../release-1.0/inventory.md)、[ADR-0027](../../0027-compatibility-promise.md) (とくに D2 と「1.0 の前に必須になるもの」の表)、
Accepted の ADR (0001・0010・0011・0014・0018・0022・0023・0025・0026)、CLAUDE.md、`docs/reference/`、`docs/exporter-cytoscape.md`、
試し書き (`adr0028/` の a1〜a5、`passb/` の b1〜b6)、実装 (`src/mlndl/schema/*.py`、`exporter/cytoscape.py`)、ndl-viz の `src/flow/session.ts`・`src/types/topology.ts`。
**drafts/0028 は参照しない** (Pass C の原則)。

### 前提 (ユーザー決定。蒸し返さない)

- IS-IS の `level` の値は下線区切り (`level_1` / `level_2` / `level_all`)
- `LacpConfig.mode` と `min_links` は既定値をなくす (書かなければ「書いていない」)
- 値域を狭める直し (`local_as`・`vni`・BFD・LAG / ES の `members`・トンネルの `mtu` の上限) を入れる
- `lacp.mode` の `on` を `static` に改名する

### 一致済み (Pass A・B の全員)

- `layer1.lag` → `lags`、`layer2.vxlan` → `vxlans`。旧名は移動先を示す error
- `vteps`・`address_families` は 1 つ以上を必須、既定値なし。`address_families` の既定値を `[ipv4_unicast]` にしない
- BFD のタイマーの既定値をなくす。`False` の既定値 (`native` / `route_reflector_client` / セッションの `bfd`) は残す
- 棚卸し §4 の 4 点 (`type` と `mode`、2 つの `members`、エクスポーターの 2 つの `vlans`、OSPF / IS-IS の `interface`) は名前を変えない

### 確定すべき論点 (優先順)

1. **決定の範囲と並び**: 名前 (一覧・列挙の値)、空のリスト、既定値、値域、名前を変えないものの約束、旧名・旧値の error
2. **規則の言い方**: 一覧の複数形の規則の範囲と例外 (`gateway_redundancy`)、列挙の値の書き方、空を許すリストの基準、値域の決め方の原則
3. **`lacp` の書き方の意味の表** (書かない / `mode` だけ / `min_links` だけ / 両方 / `{}`) と、上の「残る論点」1
4. **旧名・旧値の error の実装の位置とメッセージ**
5. **影響を受けるコンポーネントと、改訂の注記が要る ADR**
