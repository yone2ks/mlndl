# 1.0 に向けた棚卸し (2026-11-18)

最初のリリースは 1.0 で、1.0 の後は破壊的な変更にメジャーバージョンの更新が要る ([ADR-0010](../../0010-control-plane-separation.md) の移行の改訂)。
1.0 の前に何を片付けるかを決めるため、5 エージェント (spec-architect・linguist・dsl-designer・network-tech-reviewer・example-author) が並列に洗い出し、
統合担当が実装と照らして振り分けた。

「破壊的かどうか」の物差しはまだ決まっていないので、この棚卸しは仮の物差し (任意のキー・値を足す、値域を広げる、検査を緩めるのは破壊的でない。
名前・形・必須かどうか・既定値・意味を変える、検査を強めるのは破壊的) で振り分けた。物差しそのものは「互換の約束」の ADR (ADR-0027) で決める。

## 1.0 の前に決めること (後で変えると破壊的)

### 1. 互換の約束 (ADR-0027)

→ [ADR-0027](../../0027-compatibility-promise.md) で決めた (2026-11-18)。2・3 は ADR-0028 で決める。


- `ndl_version` を必須にするか。CLAUDE.md §3・`docs/reference/README.ja.md`・`validation.ja.md` は「必須」と書くが、実装は既定値 `"1.0"` を持ち、書かなくても通る (`src/mlndl/schema/topology.py:27`・`:40`)
- 新しいマイナーバージョンの YAML の扱い。全モデルが `extra="forbid"` なので、1.1 で足したキーを 1.0 の mlndl は `Extra inputs are not permitted` で拒む。`ndl_version: "1.9"` と書いても版の違いは知らせない (2026-11-18 に確かめた)
- 1.x の間に許す変更: キー・値の追加、値域を広げる、検査を緩める、検査を強める、warning を足す (`--strict` で止まる)
- 約束の範囲: YAML の書き方、エクスポーターの JSON の形 (ndl-viz・eve-lab-builder が頼る)、CLI (`validate` / `export` / `--strict`)、Python の API (`parse` / `validate` / `validate_all` / derive)
- `ndl_version` (言語) とパッケージのバージョン (今は `0.1.0`、タグなし) の関係
- 残す形を約束として明記するもの: `attaches_to: <node id>` の文字列の糖衣構文 (`src/mlndl/schema/layer1.py:84`)、`meta` だけが未知のキーを受け付けること (`topology.py:16`)
- 旧形式を「移動先を示す error」にしたもの (ADR-0010・0020・0023〜0026) を、いつまで残すか

### 2. 名前の直し

- `layer1.lag` と `layer2.vxlan` だけが単数形 (`layer1.py:439`・`layer2.py:256`)。ほかのコレクション (`nodes` / `interfaces` / `links` / `ethernet_segments` / `vlans` / `bridges` / `vteps` / `subinterfaces` / `vrfs` / `tunnel_interfaces` / `routing_neighbors`) はすべて複数形
- IS-IS の `level` の値だけがハイフン区切り (`level-1` / `level-2` / `level-all`。`control_plane.py:212`)。ほかの値は下線区切り (`all_active` / `ipsec_vti` / `l2vpn_evpn`)

### 3. 型の細部

- `L2VxLAN.vteps` は既定値 `[]` なのに、空は validator で error (`layer2.py`)。`min_length=1` で型に寄せる
- `BgpSession.address_families: []` が「指定なし」か「何も運ばない」か決まっていない (`control_plane.py:161`)
- 既定値は 1.0 で固まる: `LacpConfig.mode = "active"`・`min_links = 1` (`layer1.py:304-305`)、`route_reflector_client = False` (`control_plane.py:108`) など

### 4. 名前は変えず、約束を書くだけでよいもの

- 種類を見分けるキーが `type` (`vxlan` / `tunnel_interfaces` / `routing_neighbors`) と `mode` (`gateway_redundancy`) で混ざる
- LAG の `members` (L1 IF の id) と Ethernet Segment の `members` (`{lag:}` / `{interface:}`) の形が違う
- エクスポーターの機器ノードの `vlans` (ポートがある VLAN) と L2VNI の `vlans` (載る VLAN) が同じ名前で意味が違う
- OSPF の `interface` だけが L3 IF を指す (ほかの `interface` は L1 IF)

## 1.0 の前にやること (破壊的ではないが、利用者が最初に見る見本)

- examples と fixture の不統一
  - ~~anycast gateway なのに `gateway_redundancy` がない: `examples/eveng-evpn-lab.yaml:209-243`、`tests/fixtures/valid_full_dc.yaml:287-293`、`valid_multisite_wan.yaml:338-349`~~ —
    2026-11-18 に確かめたところ誤り。同じ IP を共有する SVI は、examples と valid の fixtures でみな `gateway_redundancy` を書いている (ADR-0027 Pass C で example-author が指摘)
  - SVI の `name` が `Vlan100` (リファレンス) と `vlan-100` (`valid_multi_vlan.yaml`・`valid_full_dc.yaml`・`valid_multisite_wan.yaml`) で混在。SVI の id も `leaf1-vlan100` と `leaf1-vlan-10` で混在
  - `valid_full_dc.yaml` は MLAG なのに leaf2 の SVI がない
  - `valid_twinport_transceiver.yaml:91-97` は LAG を片側しか書かず、ADR-0023 の前の理解のコメントが残る
  - `valid_multisite_wan.yaml:461-468` の OSPF の `area: 0` (整数。受け付けはするが、リファレンスの例は `"0.0.0.0"`)
- 入門の文書: `docs/README.ja.md` から examples への入口がない。小さな完全な例 (試し書きの 2 拠点の企業網が使える)、はじめの一歩のページ、SVI の名前・id の付け方の短いスタイルガイド
- リファレンスの補足: `vrf: vrf-default` を書くなら `vrfs` に定義が要ること、共有 VTEP の `address` は各 `sources` の ip と別の値になりうること、OSPF の `interface` (L3 IF) と IS-IS の `interface` (L1 IF) の違い
- リリースの作業: パッケージを 1.0.0 にしてタグを打つ。drafts/0001〜0005 の Status が「Draft」のまま (README では archived 扱い)

## 1.0 の後でよいもの (加算で足せる)

- Draft の ADR (drafts/0007 vSwitch・0008 クラウド・0016 ルーター ID と管理 IF) と、保留中の ADR-0019
- `docs/decisions/deferred.md` のすべての項目
- VRRP の `priority` を 0〜255 に広げる (`layer3.py:80`。値域を広げるのは破壊的でない)
- `gateway_redundancy[].vip` を複数に (`vip: X | list[X]` に広げる)
- インターフェース単位の MTU、ルーター ID (任意のフィールドの追加)
- Ethernet Segment の脚どうしがつながると出る error を warning に下げる (緩めるのは破壊的でない)
- `L1Node.attaches_to` を複数に (受け付ける型を広げるのは入力にとって破壊的でない。エクスポーターの出力の形を変えるなら別に考える)

## 採らなかった指摘

| 指摘 | 誰 | 理由 |
|---|---|---|
| トポロジー外の相手の AS `local_as` を `remote_as` に改名 | network-tech | ADR-0010 で決めた対称の書き方 (どちらの端も「その端自身の AS」)。旧 `remote_as` は移動先を示す error |
| VTEP の `address` / `address_v6` を `ip` / `ipv6` に改名 | linguist | ADR-0014 D2 でユーザーが選んだ名前 (`sources` の L3 IF の `ip` と同じ語が 2 層に並ぶのを避けた) |
| ADR-0011 D10・0014 D4・0018 D4 の本文が「1.x の間は warning」のまま | spec-architect | 3 つとも直後に ADR-0025 の改訂の注記がある。元の文を残して注記を足すのがこのプロジェクトの書き方 |
| MTU・ルーター ID の欄を 1.0 で予約する | network-tech | 任意のフィールドの追加は加算なので予約は要らない |

## 試し書き

example-author が `docs/reference/` だけを見て書いた 2 つの YAML (`small-2sites-ospf.yaml`・`evpn-4leaf-mlag.yaml`) (2 拠点の企業網と OSPF、4 leaf の EVPN-VXLAN と MLAG) は、どちらも error も warning もなく通った。
書いていて迷った点 (L1 IF と L3 IF を 2 回書く冗長さ、MLAG は 6 か所をそろえて初めて成り立つ、`vrf-default` の定義) は、上の「入門の文書」「リファレンスの補足」に入れた。
