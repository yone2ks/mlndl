# Cytoscape エクスポーターの出力

`python -m mlndl export --format cytoscape` が出す JSON (`{"meta": {...}, "nodes": [...], "edges": [...]}`) の語彙。
主な消費者は ndl-viz と eve-lab-builder。言語 (MLNDL の YAML) の仕様ではなく、mlndl と下流のツールの間の取り決めである。

方針:

- **エクスポーターは参照を解決し、ビューワは集合演算をする**。参照 (id) をたどる導出はエクスポーター (`src/mlndl/derive.py`) で行い、
  ビューワに機器上の名前 (`name`) を照合させない (`name` は参照ではない。ADR-0011 D3)
- 導出した値は、何から導いたかを ADR で決めたものに限る。推測は出さない
- 旧キーは出さない (1.x の間だけ併記するとしていた旧キーは、[ADR-0025](decisions/0025-end-grace-for-old-forms.md) D3 で 1.0 の前に外した)

## 互換の約束 (規範キー)

[ADR-0027](decisions/0027-compatibility-promise.md) D1-2 により、下の表の「規範」の列に ○ を付けたキーは**規範キー**である。

- 規範キーは、1.x の間、同じ条件で同じ形のまま出し続ける。消す・改名する・意味を変えるのは 2.0。キー・値 (`type` の値など) を足すのは 1.x でもある
- ○ が約束するのはキーの有無と形まで。値の書式 (`label` の文字列の整形、`description` の中身、リストの並び順) は約束しない
- ○ のないキー (参考) は 1.x で変わることがある
- 下流のツールは、**未知のキー・未知の値・未知の分岐を無視して読み進める**
- eve-lab-builder が読むキーは推定で規範に含めた。eve-lab-builder を確かめられるようになったら、この列を実際のキーで直す (ADR-0027 D1-2)
- 要素の `type` の値はすべて規範: ノードは `node` / `vlan` / `l2vni` / `l3vni` / `bridge` / `ethernet_segment`、エッジは `link` / `attaches_to` / `vlan_member` / `routing_neighbor` / `tunnel` / `lag_bundle`
- すべての要素の `id` / `type` / `label` / `layer` / `description` (あれば) は規範

## ルートの `meta`

| キー | 規範 | 内容 |
|---|---|---|
| `ndl_version` | ○ | 入力の YAML の `ndl_version` そのまま (ADR-0027 D6) |
| `mlndl_version` | ○ | 出力した mlndl のバージョン (`mlndl.__version__`) |

入力の YAML の `meta` (下流のツールの設定など) は出力に流さない (ADR-0027 D7)。下流のツールが自分の設定を使うなら YAML を読む。

## ノード

### `type: node` (L1 ノード)

| キー | 規範 | 内容 |
|---|---|---|
| `id` / `label` / `role` / `implementation` / `device_type` / `labels` | ○ | L1 ノードの値 (`label` は `name`、なければ `id`)。サイトの枠は `labels.site` (ADR-0017) |
| `l3_interfaces` | ○ | このノードの L3 IF (IP を持つもの)。下の「L3 IF」 |
| `vrfs` | ○ | このノードの L3 IF が属する VRF の id (並び順は参考) |
| `vlans` | ○ | このノードにポートがある VLAN の id (Ethernet Segment は脚のすべてのノード。ADR-0013 D5・ADR-0023 D8)。L2VNI の `vlans` とは意味が違う |
| `vteps` | ○ | このノードが終端する VTEP: `{id, source, address?, address_v6?, shared_with?}`。`source` は L3 IF の name、`shared_with` は共有相手のノード (ADR-0014) |
| `lags` | ○ | このノードの LAG: `{id, name?, members, lacp?, ethernet_segment?, description?}`。`members` はメンバーの L1 IF の name (リンクの `source_if` / `target_if` と同じ)。`lacp` は書かれた値だけ。`ethernet_segment` はこの LAG が脚の ES (ADR-0023) |
| `subinterfaces` |  | このノードのサブ IF: `{id, parent, vlan_id, name?}` (ADR-0012) |
| `tunnels` | ○ | このノードのトンネル IF (ADR-0011 D6): `id` / `type` / `source` / `destination_interface` / `destination_ip` / `ip` / `vrf` |
| `local_as` | ○ | BGP の AS 番号 (default VRF のインスタンスのもの。なければ最初に出てくるインスタンス) |
| `bgp_sessions` | ○ | このノードの BGP セッションすべて (相手がトポロジー外のものを含む。トンネルの `tunnels` と同じ形)。下の「BGP セッション」に `local` (この機器の端) と `peer` (相手の端) を足したもの (ADR-0010 D11) |

#### L3 IF (`l3_interfaces[]`)

| キー | 規範 | 内容 |
|---|---|---|
| `id` | ○ | L3 IF の id |
| `name` | ○ | 機器上の名前 (参照ではない) |
| `attachment` | ○ | 何の上に載るか (ADR-0011 D11): `l1_interface` / `lag` / `vlan` / `subinterface` / `unattached` |
| `attaches_to` | ○ | YAML と同じ形 (`{"interface": "<L1 IF の id>"}` 等)。`unattached` なら省略 |
| `roles` |  | ほかのエンティティから参照されている役割: `update_source` (routing_neighbors) / `vtep_source` (layer2.vteps)。なければ省略。参照の逆引きで、YAML 全体をたどらずに「どの L3 IF が update-source か」を引くためのもの (ndl-viz の表示では使っていない) |
| `ip` / `ipv6` / `vrf` / `gateway_redundancy` | ○ | L3 IF の値 |

`unattached` はループバックとは限らない (dummy IF、L1 を書かずに書いた管理 IF、`attaches_to` の書き忘れもありうる)。
表示で「ループバック」と決めつけず、`name` をそのまま見せる。

#### ノードの代表アドレスは出さない

MLNDL はノードの代表アドレスを定義しない (ADR-0011 D11)。以前は旧ビューワのために `lo_ip` / `lo_ipv6` を推定で 1 つ選んで出していたが、
[ADR-0025](decisions/0025-end-grace-for-old-forms.md) D3 で外した。代わりは置かない。
ビューワは `l3_interfaces[]` の `name` / `ip` / `ipv6` / `roles` を見て、何を見せるかを自分で決める
(ndl-viz は L3 IF ごとに `name` とアドレスを見せ、L3 IF が 1 つだけのノードはそのアドレスを出す)。

### `type: vlan`

`id` / `label` / `vlan_id` / `name`、SVI から求めた `subnet` / `subnet_v6` / `vrf_name`。**すべて規範**。

### `type: bridge`

番号を持たない L2 セグメント (`layer2.bridges`。[ADR-0018](decisions/0018-sessions-across-bridges-and-tunnels.md) D1・D5)。事業者網の箱の中の転送に使う。
`id` / `label` (`name` がなければ id) / `name`、`ports` (`{"interface": <L1 IF>}`・`{"lag": <LAG>}`・`{"ethernet_segment": <ES>}` に、そのポートのノードを `nodes` として添えたもの)、
`nodes` (ポートのノードを重複なく並べたもの。ふつうは事業者網の箱 1 つ)。**すべて規範**。辺は出さない。描き方 (箱の中に描くか、描かないか) はビューワが決める。

### `type: ethernet_segment`

複数の機器の脚を相手から 1 本に見せる関係 (`layer1.ethernet_segments`。[ADR-0023](decisions/0023-per-device-lag-and-ethernet-segments.md) D8)。
`id` / `label` (`name` がなければ id) / `name`、`members` (YAML と同じ形 `{"lag": <LAG>}` / `{"interface": <L1 IF>}` に、脚の機器を `node` として添えたもの)、
`nodes` (脚の機器を重複なく並べたもの)、`redundancy_mode` (書かれていれば。書かれていなければ出さず、`all_active` で埋めない)。**すべて規範**。
辺は出さない。脚のリンクには `ethernet_segment` を載せる (下の「エッジ」)。枠などの描き方はビューワが決める。
MLAG か EVPN multihoming かは出さない (構文に方式名がない。ビューワが区別したければ `device_type` を見る)。

### `type: l2vni` / `type: l3vni`

`id` / `label` / `vni`。L2VNI は `vlans` と `vteps` (書かれたもの) と `node_vlans` (導いたもの)、L3VNI は `vrf` と `vteps`
(VRF に L3 IF を持つノードが終端する VTEP から導いたもの。ADR-0014 D3)。**すべて規範**。

- `vlans`: この VNI に載る VLAN の id (YAML の `vlans` のまま。ADR-0026)。機器ノードの `vlans` (その機器にポートがある VLAN) とは意味が違う
- `node_vlans`: `[{node, vlan}]`。参加機器 (VTEP から導く) と、その機器の VLAN (VLAN のポートか、VLAN を指す SVI の機器から導く。ADR-0026 D4)。
  VLAN が決まらない参加機器 (VNI を中継するだけの機器など) は出さない。導いた値なので YAML には書けない。
  ビューワは機器ごとの VLAN の番号をこれで示し、自分では導かない

## `description`

YAML に `description` があれば、人が読む補足としてそのまま出す (ADR-0011 D7)。出すのは、対応する要素があるもの:
機器ノード、`vlan`、`bridge`、`ethernet_segment`、`l2vni` / `l3vni`、エッジの `link` / `tunnel` / `routing_neighbor`、ノードに埋め込む `lags[]` / `l3_interfaces[]` / `subinterfaces[]` / `tunnels[]` / `bgp_sessions[]`。
要素を持たないもの (L1 IF、LAG、VRF、VTEP、インスタンス) の `description` は出さない。
受け取るツールは表示するだけで、パースせず、一部を取り出しもしない。回線 ID などを書く場所でもある ([ADR-0017](decisions/0017-sites-and-wan.md) D4)。
`role: provider-network` (事業者網の箱) も、ほかの role と同じくそのまま出す。

## エッジ

エッジの `source` / `target` は Cytoscape.js が必須にしているキーで、**向きの意味はない** ([ADR-0006](decisions/0006-endpoints.md))。
`link` では YAML の `endpoints[0]` が `source`、`endpoints[1]` が `target` で、`source_if` / `target_if` / `source_lag` / `target_lag` も同じ順である。

| `type` | 規範 | 内容 |
|---|---|---|
| `link` | ○ | L1 リンク。`source` / `target` は L1 ノード、`source_if` / `target_if` は L1 IF の name。`link_speed` / `link_role` / `source_lag` / `target_lag` (その端の L1 IF がメンバーの LAG。LAG は機器 1 台なので、両端が別々の LAG のメンバーになりうる) / `lag_id` (どちらかの端の LAG。両端にあれば source 側) / `ethernet_segment` (端の L1 IF が脚の Ethernet Segment)。`lag_type` は ADR-0023 でなくした |
| `lag_bundle` | ○ | LAG のメンバーリンクを束ねたもの。`lag_id`、`member_count`、脚なら `ethernet_segment` |
| `attaches_to` | ○ | L1 ノードの `attaches_to` (ノードがどこで動くか。ADR-0001)。`source` / `target` だけ |
| `vlan_member` | ○ | VLAN → ポートのあるノード。`vlan_id`、`tagged_on` / `untagged_on` はポートの name か LAG の id (Ethernet Segment のポートは、そのノードの脚の LAG の id か L1 IF の name に開く)。`endpoints` は下の「VLAN の端点」 |
| `routing_neighbor` | ○ | `control_plane.routing_neighbors` の 1 セッション = 1 辺。`protocol` (bgp / ospf / isis)。BGP は両端がトポロジー内のものだけ。下の「BGP セッション」 (ADR-0010 D11) |
| `tunnel` | ○ | 対向がトポロジー内のトンネル IF (A→B と B→A は 1 本)。`tunnel_type` / `vrf` |

旧 `routing_adjacency` (`layer3.routing_adjacencies`) と `bgp_session` (`protocols.bgp`) の辺は、ADR-0010 で `routing_neighbor` に置き換えた
(同じ機器の組に最大 6 本重なっていた)。

### BGP セッション (`routing_neighbor` の `protocol: bgp`、ノードの `bgp_sessions[]`)

どの値も参照をたどって決めた値である (`derive.bgp_session_views`。validator と同じ関数)。

| キー | 規範 | 内容 |
|---|---|---|
| `id` / `instance` / `vrf` | ○ | セッションの id、属するインスタンス、その VRF (default VRF なら `vrf` を出さない) |
| `from` / `to` (辺) ・ `local` / `peer` (ノードの `bgp_sessions`) | ○ | 端: `node`、`l3_interface` (update_source の L3 IF かトンネル IF の id。ADR-0018 D3)、`interface_name` (その L3 IF の `name`。トンネル IF は `name` を持たないので出さない)、`ip` / `ipv6`、`unnumbered: true` (L3 IF にアドレスがない。ADR-0010 D4)、`local_as`、`route_reflector_client`。トポロジー外の相手は `address` と `local_as` だけ |
| `bgp_type` | ○ | `ebgp` / `ibgp`。両端の AS が同じかどうか (AS が決まらなければ出さない) |
| `address_families` | ○ | セッションに書かれた値 |
| `transport_link` | ○ | single-hop の通り道。次のどれか 1 つ: `{"link": <リンク id>}`、`{"lag": [<from 側の LAG>, <to 側の LAG>]}`、`{"bridge": <bridge id>}` (両端が同じ bridge に届く。ADR-0018 D2)、`{"tunnel": [<from 側のトンネル IF>, <to 側のトンネル IF>]}` (対になるトンネル IF。ADR-0018 D3)。ノードの `bgp_sessions[]` でも from / to の順のまま。update_source から導いた値で、YAML の `attaches_to` ではない。multihop (ループバック等)・SVI 上・トポロジー外の相手では出さない (ADR-0010 D7) |
| `bfd` | ○ | セッションに書かれた値 |

underlay / overlay は出さない。知りたいときは次のように導く (informative。ADR-0010 D6):
`l2vpn_evpn` / `vpnv4` / `vpnv6` を運べば overlay の情報を運ぶセッション、default VRF で `ipv4_unicast` / `ipv6_unicast` だけなら underlay の経路を運ぶセッション、
両方なら両方、default 以外の VRF で `ipv4_unicast` / `ipv6_unicast` ならテナントの経路 (どちらでもない)。

OSPF / IS-IS の辺は、`from` / `to` に `node`・`interface` (OSPF は L3 IF かトンネル IF、IS-IS は L1 IF の id)・`interface_name` (トンネル IF なら出さない) を持ち、`area` (OSPF。ドット区切り 4 オクテット) か `level` (IS-IS) を持つ。
`transport_link` は BGP と同じ規則で両端の `interface` から導いた値 (ADR-0018 D4。IS-IS は L1 IF の対向を直接見る)。**すべて規範**。

### VLAN の端点 (`vlan_member.endpoints[]`)

VLAN のポートの対向で、その VLAN のフレームを受ける機器の IF (ADR-0013 D7)。ポートのノードごとに出す。

| キー | 規範 | 内容 |
|---|---|---|
| `node` | ○ | 端点の機器 |
| `interfaces` / `interface_names` | ○ | 端点の L1 IF の id と name |
| `lag` | ○ | 端点側の LAG (bond) |
| `tagged` | ○ | ポートがフレームにタグを付けるか |
| `resolution` | ○ | `direct` (参照で確定) / `tag_match` (タグの一致から推定) / `ambiguous` (候補が複数) / `no_l3` (L3 IF なし) |
| `l3_interface` / `name` / `ip` / `ipv6` | ○ | `direct` / `tag_match` のときの L3 IF |
| `candidates` | ○ | `ambiguous` のときの候補 |
| `outside_svi_subnet` | ○ | 端点の IP のうち、その VLAN の SVI のサブネットに入らないもの |
