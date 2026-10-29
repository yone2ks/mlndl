# Cytoscape エクスポーターの出力 (informative)

`python -m mlndl export --format cytoscape` が出す JSON (`{"nodes": [...], "edges": [...]}`) の語彙。
主な消費者は ndl-viz。言語 (NDL YAML) の仕様ではなく、mlndl と表示ツールの間の取り決めである。

方針:

- **エクスポーターは参照を解決し、ビューワは集合演算をする**。参照 (id) をたどる導出はエクスポーター (`src/mlndl/derive.py`) で行い、
  ビューワに機器上の名前 (`name`) を照合させない (`name` は参照ではない。ADR-0011 D3)
- 導出した値は、何から導いたかを ADR で決めたものに限る。推測は出さない
- 旧キーは ndl_version 1.x の間だけ併記し、2.0 で外す

## ノード

### `type: node` (L1 ノード)

| キー | 内容 |
|---|---|
| `id` / `label` / `role` / `implementation` / `device_type` / `labels` | L1 ノードの値 (`label` は `name`、なければ `id`) |
| `l3_interfaces` | このノードの L3 IF (IP を持つもの)。下の「L3 IF」 |
| `vrfs` | このノードの L3 IF が属する VRF の id |
| `vlans` | このノードにポートがある VLAN の id (MLAG は両ノード。ADR-0013 D5) |
| `vteps` | このノードが終端する VTEP: `{id, source, address?, address_v6?, shared_with?}`。`source` は L3 IF の name、`shared_with` は共有相手のノード (ADR-0014) |
| `subinterfaces` | このノードのサブ IF: `{id, parent, vlan_id, name?}` (MLAG 上は両ノード。ADR-0012) |
| `tunnels` | このノードのトンネル IF (ADR-0011 D6) |
| `local_as` | BGP の AS 番号 |
| `lo_ip` / `lo_ipv6` | **旧キー (推定)**。下の「旧キー `lo_ip` / `lo_ipv6`」 |

#### L3 IF (`l3_interfaces[]`)

| キー | 内容 |
|---|---|
| `id` | L3 IF の id |
| `name` | 機器上の名前 (参照ではない) |
| `attachment` | 何の上に載るか (ADR-0011 D11): `l1_interface` / `lag` / `vlan` / `subinterface` / `unattached` |
| `attaches_to` | YAML と同じ形 (`{"interface": "<L1 IF の id>"}` 等)。`unattached` なら省略 |
| `roles` | ほかのエンティティから参照されている役割: `update_source` (routing_adjacencies) / `vtep_source` (layer2.vteps)。なければ省略。参照の逆引きで、YAML 全体をたどらずに「どの L3 IF が update-source か」を引くためのもの (ndl-viz の表示では使っていない) |
| `ip` / `ipv6` / `vrf` / `gateway_redundancy` | L3 IF の値 |
| `interface` / `kind` | **旧キー**。`interface` は `name` と同じ。`kind` は `attachment` から写したもの (`vlan` → `svi`、`subinterface` → `subinterface`、`unattached` → `loopback`、`l1_interface` / `lag` → `routed`) |
| `vlan` / `subinterface` + `vlan_id` / `lag` | **旧キー**。`attaches_to` の参照先 (サブ IF はそのタグ番号も) |

`unattached` はループバックとは限らない (dummy IF、L1 を書かずに書いた管理 IF、`attaches_to` の書き忘れもありうる)。
表示で「ループバック」と決めつけず、`name` をそのまま見せる。

#### 旧キー `lo_ip` / `lo_ipv6`

MLNDL はノードの代表アドレスを定義しない (ADR-0011 D11)。ndl-viz はカードに代表アドレスを出さず、L3 IF ごとに `name` とアドレスを見せる
(L3 IF が 1 つだけのノードは、そのアドレスを出す)。

`lo_ip` / `lo_ipv6` は、旧 ndl-viz がノードごとに 1 つのアドレスを受け取るためのキーで、ループバックの IP が入ると想定していた。
D11 で `unattached` をループバックとみなさないと決めたので、キー名と中身は一致しない。
既存のビューワを壊さないため ndl_version 1.x の間だけ出し、2.0 で外す。冒頭の方針「推測は出さない」の、1.x 限定の例外である。
新しい表示は使わず、`l3_interfaces[].ip` / `ipv6` を見る。

選び方 (IPv4 / IPv6 で別々に。名前は見ない):

1. `attachment: unattached` で、そのアドレスファミリーのアドレスを持つ L3 IF のうち、`roles` に `update_source` があるもの
2. 1 がなければ、そのうち `roles` に `vtep_source` がないもの
3. 2 もなければ、そのうち YAML で先に書かれたもの
4. 該当する L3 IF がなければキーを出さない

各段で候補が複数あれば、YAML で先に書かれたものを選ぶ (出力は記述順で決まる)。
管理 IF だけが `unattached` の構成では管理アドレスが、BGP unnumbered では記述順で先のアドレスが入る。代表としては当てにならない。

### `type: vlan`

`id` / `label` / `vlan_id` / `name`、SVI から求めた `subnet` / `subnet_v6` / `vrf_name`。

### `type: l2vni` / `type: l3vni`

`id` / `label` / `vni`。L2VNI は `vlan` と `vteps` (書かれたもの)、L3VNI は `vrf` と `vteps`
(VRF に L3 IF を持つノードが終端する VTEP から導いたもの。ADR-0014 D3)。

## エッジ

| `type` | 内容 |
|---|---|
| `link` | L1 リンク。`source` / `target` は L1 ノード、`source_if` / `target_if` は L1 IF の name。`link_speed` / `mtu` / `link_role` / `lag_id` / `lag_type` |
| `lag_bundle` | LAG のメンバーリンクを束ねたもの |
| `attaches_to` | L1 ノードの `attaches_to` (ノードがどこで動くか。ADR-0001) |
| `vlan_member` | VLAN → ポートのあるノード。`tagged_on` / `untagged_on` はポートの name か LAG の id。`endpoints` は下の「VLAN の端点」 |
| `routing_adjacency` | `layer3.routing_adjacencies`。`adj_type` |
| `bgp_session` | `protocols.bgp` の隣接。`process_role` (underlay / overlay)、`local_as` / `remote_as`、`address_families` |
| `tunnel` | 対向がトポロジー内のトンネル IF (A→B と B→A は 1 本) |

### VLAN の端点 (`vlan_member.endpoints[]`)

VLAN のポートの対向で、その VLAN のフレームを受ける機器の IF (ADR-0013 D7)。ポートのノードごとに出す。

| キー | 内容 |
|---|---|
| `node` | 端点の機器 |
| `interfaces` / `interface_names` | 端点の L1 IF の id と name |
| `lag` | 端点側の LAG (bond) |
| `tagged` | ポートがフレームにタグを付けるか |
| `resolution` | `direct` (参照で確定) / `tag_match` (タグの一致から推定) / `ambiguous` (候補が複数) / `no_l3` (L3 IF なし) |
| `l3_interface` / `name` / `ip` / `ipv6` | `direct` / `tag_match` のときの L3 IF |
| `candidates` | `ambiguous` のときの候補 |
| `outside_svi_subnet` | 端点の IP のうち、その VLAN の SVI のサブネットに入らないもの |
