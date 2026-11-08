# 値の型

各ページの表の「型」の列で使う名前と、その書き方です。[リファレンスの目次](README.ja.md)

## id

エンティティの `id` と、`id` を指す参照の値。

- 文法: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`。英小文字で始め、英小文字・数字をハイフン 1 つで区切る。末尾や連続のハイフンは書けない
- 長さ: 63 文字まで (DNS ラベルと同じ)
- 違反すると error。理由 (先頭が英小文字でない、大文字がある、など) をまとめて示す
- ファイル全体で一意 ([README.md](README.ja.md#id))

```yaml
id: leaf1-swp51         # 正しい
id: Leaf1_swp51         # error: 大文字と _ は書けない
```

### 推奨プレフィックス

次のエンティティの id は、決まったプレフィックスで始めることを推奨します。従わないと warning です。

| エンティティ | プレフィックス | 例 |
|---|---|---|
| `layer1.links` | `link-` | `link-spine1-leaf1` |
| `layer1.lag` | `lag-` | `lag-leaf1-server1` |
| `layer1.ethernet_segments` | `es-` | `es-server1` |
| `layer2.vlans` | `vlan-` | `vlan-100` |
| `layer2.bridges` | `bridge-` | `bridge-wideether` |
| `layer2.vteps` | `vtep-` | `vtep-leaf1-leaf2` |
| `layer2.vxlan` | `vni-` | `vni-10100` |
| `layer2.subinterfaces` | `subif-` | `subif-border1-swp5-200` |
| `layer3.vrfs` | `vrf-` | `vrf-tenant-a` |
| `layer3.tunnel_interfaces` | `tunnel-` | `tunnel-border1-dc2` |
| `control_plane.bfd` | `bfd-` | `bfd-global` |
| `control_plane.routing_neighbors` (BGP) | `bgp-peer-` | `bgp-peer-spine1-leaf1` |
| `control_plane.routing_neighbors` (OSPF) | `ospf-adj-` | `ospf-adj-tokyo-osaka` |
| `control_plane.routing_neighbors` (IS-IS) | `isis-adj-` | `isis-adj-core1-core2` |

機器・L1 IF・L3 IF にはプレフィックスを決めていません。L1 IF は `<機器の id>-<ポート>` (`leaf1-swp51`)、L3 IF は `<機器の id>-<名前>` (`leaf1-lo`、`leaf1-vlan-100`) と書くのが慣例です。
VLAN は `vlan-<番号>`、VNI は `vni-<番号>` と番号を入れます。

## 文字列

自由な文字列。`name` (機器上の名前)、`description`、`role`、`device_type`、`link_role`、`link_speed` など。
mlndl は値域を検査しません。`role` と `labels` の推奨値は [role-vocabulary.md](../role-vocabulary.md)・[label-vocabulary.md](../label-vocabulary.md) にあります。

`name` は参照ではありません。ほかのエンティティから `name` で引くことはありません。

## 列挙

決まった値だけを書ける文字列。各ページの表に値を並べます。

| キー | 値 |
|---|---|
| `layer1.nodes[].implementation` | `vm` / `physical` / `container` |
| `layer1.ethernet_segments[].redundancy_mode` | `all_active` / `single_active` |
| `layer1.lag[].lacp.mode` | `active` / `passive` / `on` |
| `layer2.vxlan[].type` | `l2vni` / `l3vni` |
| `layer2.vxlan[].irb_mode` | `symmetric` / `asymmetric` |
| `layer3.interfaces[].gateway_redundancy[].mode` | `vrrp` / `hsrp` / `anycast_gateway` |
| `layer3.tunnel_interfaces[].type` | `gre` / `ipip` / `ipsec_vti` / `wireguard` |
| `control_plane.routing_neighbors[].type` | `bgp` / `ospf` / `isis` |
| `control_plane.routing_neighbors[].address_families` | `ipv4_unicast` / `ipv6_unicast` / `l2vpn_evpn` / `vpnv4` / `vpnv6` |
| `control_plane.routing_neighbors[].level` (IS-IS) | `level-1` / `level-2` / `level-all` |

## IP アドレス

| 型の名前 | 書き方 | 使う所 |
|---|---|---|
| IPv4 プレフィックス付きアドレス | `10.1.0.1/31` | `ip` (L3 IF・トンネル IF)、VTEP の `address` |
| IPv6 プレフィックス付きアドレス | `2001:db8:1::1/127` | `ipv6`、VTEP の `address_v6` |
| IP アドレス | `203.0.113.1`、`fe80::1` | トポロジー外の相手の `address`、ゲートウェイの `vip`、トンネルの `destination_ip` |

- `ip` には IPv4 だけ、`ipv6` には IPv6 だけを書きます。`ip` に IPv6 を書くと、`ipv6` に移すよう示す error です
- どちらも単数です。1 つの IF に 2 つ目の IPv4 アドレスを書く構文はありません ([ADR-0011](../decisions/0011-layer3-data-plane.md) D5)
- ホスト部が 0 のアドレス (`10.1.0.0/24` のような網アドレス) も書けますが、IF のアドレスとしては普通書きません

## 数値

| キー | 範囲 | 検査 |
|---|---|---|
| `layer2.vlans[].vlan_id` | 1〜4094 | 範囲外は error。同じ機器の上での重複は error |
| `layer2.subinterfaces[].vlan_id` | 1〜4094 | 範囲外は error |
| `layer2.vxlan[].vni` | 1〜16777215 (24 ビット) | 範囲は検査しない。L2VNI と L3VNI を通して重複すると error |
| `local_as` | 1〜4294967295 (4 バイト AS) | 範囲は検査しない |
| `layer3.tunnel_interfaces[].mtu` | 68 以上 | 範囲外は error |
| `group_id` (VRRP / HSRP) | — | 同じ IF・同じ mode・同じアドレスファミリーで重複すると error |

## 速度

`layer1.links[].link_speed` は `<数値><単位>` の文字列です ([ADR-0021](../decisions/0021-link-speed-format.md))。

- 単位は `K` / `M` / `G` / `T` のどれかで、大文字だけです。`bps` は付けません
- 値は 10 進のビット毎秒です。`K` = 1000 bps、`M` = 10⁶、`G` = 10⁹、`T` = 10¹² bps。1024 倍 (KiB など) ではなく、バイトでもありません
- 数値は整数か小数です。小数の桁数に制限はありません。整数部は省略せず、先頭に余分な `0` を付けません
- `10g`・`10Gbps`・`10 G`・`10GB`・単位のない `10000` は error です。error のメッセージが直し方を示します。単位のない数値は、値を推測しません

| 速度 | 書き方 |
|---|---|
| ISDN の B チャネル、シリアル | `64K`、`9.6K` |
| T1、E1 | `1.544M`、`2.048M` |
| Fast Ethernet | `100M` |
| 1G〜100G | `1G`、`2.5G`、`5G`、`10G`、`25G`、`40G`、`50G`、`100G` |
| 200G 以上 | `200G`、`400G`、`800G`、`1.6T` |

**正規形**: 数値が 1 以上 1000 未満になる単位で書き、余分な `0` を付けません。`1000G` (→ `1T`)・`2500M` (→ `2.5G`)・`0.5G` (→ `500M`)・`10.0G` (→ `10G`) は warning です。
warning は助言で、error ではありません。mlndl は書かれた表記を書き換えず、エクスポーターもそのまま出します。

## Route Target と Route Distinguisher

`layer3.vrfs[].rd` と `route_targets.import` / `export` の各値は、次のどちらかの形の文字列です。違反すると error です。

- `<AS 番号>:<番号>` (例: `"65001:100"`)
- `<IPv4 アドレス>:<番号>` (例: `"10.0.0.1:100"`)

必ず引用符で囲んで書きます。YAML 1.1 では、`:` のあとが 2 桁以下の数字 (`65001:10`) だと 60 進数の数値 (3900070) として読まれ、error になります。

## MAC アドレス

MAC アドレスは書きません。構成図の粒度ではないためです ([ADR-0022](../decisions/0022-diagram-granularity.md))。
以前の `anycast_mac` と MLAG の `system_mac` は、書くと error になります。LACP の system-id、ESI の値、MLAG のドメインの番号、vPC 番号 / clag-id も書きません。

## マッピング

- `labels`: 文字列から文字列へのマッピング。値に数値を書くと error (`labels: {vlan: 100}` は誤り。`"100"` と書く)。キーは id の文法に従うことを推奨し、従わないと warning
- `overrides`: 任意のマッピング。上位のツール (eve-lab-builder など) のための値で、mlndl は中を見ません
- `meta`: 任意のキーを書けるマッピング
