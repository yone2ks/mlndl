# control_plane

制御プレーン: BGP・OSPF・IS-IS のインスタンス、BFD のタイマー、セッション ([ADR-0010](../decisions/0010-control-plane-separation.md))。[リファレンスの目次](README.ja.md)

`control_plane` は書かなくても構いません (データプレーンだけの記述も正しい MLNDL です)。

| キー | 型 | 説明 |
|---|---|---|
| `bgp` | [[BGP のインスタンス](#bgp)] | 1 エントリ = 1 つの VRF の BGP (全機器分) |
| `ospf` | [[OSPF のインスタンス](#ospf)] | |
| `isis` | [[IS-IS のインスタンス](#isis)] | |
| `bfd` | [[BFD のタイマー](#bfd)] | |
| `routing_neighbors` | [[セッション](#routing_neighbors)] | 1 エントリ = 1 セッション (BGP・OSPF・IS-IS) |

## bgp

BGP のインスタンス。VRF ごとに 1 つ書き、そこに参加する機器と AS を並べます。同じ VRF に 2 つは書けません。

```yaml
bgp:
  - id: bgp-default                     # vrf を書かなければ default VRF
    nodes:
      - {node: spine1, local_as: 65000}
      - {node: leaf1,  local_as: 65001}
  - id: bgp-tenant-a                    # VRF-lite などはテナントの VRF ごとに
    vrf: vrf-tenant-a
    nodes: [{node: border1, local_as: 65021}]
```

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | |
| `vrf` | id | | `layer3.vrfs` | 省略すると default VRF |
| `nodes` | [`{node, local_as}`] | | | 参加する機器と AS。同じ機器・同じ VRF で AS は 1 つ |
| `description` | 文字列 | | | |

`nodes` の要素: `node` (id、必須、参照先 `layer1.nodes`)、`local_as` (整数、必須)。

underlay / overlay の区別は書きません。セッションが運ぶアドレスファミリーと VRF から導きます ([ADR-0010](../decisions/0010-control-plane-separation.md) D6)。

## ospf

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | |
| `vrf` | id | | `layer3.vrfs` | |
| `nodes` | [`{node}`] | | `layer1.nodes` | 参加する機器 |
| `description` | 文字列 | | | |

## isis

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | |
| `nodes` | [`{node, net}`] | | `layer1.nodes` | 参加する機器 (`node`) と、その NET (`net`。`49.0001.0100.0000.0001.00` など。書かなくてもよい) |
| `description` | 文字列 | | | |

## bfd

BFD のタイマー。BFD を張るかどうかはセッションの `bfd` で決め、ここにはタイマーと対象の機器を書きます。

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `bfd-` |
| `min_tx` | 整数 | (`300`) | | ミリ秒 |
| `min_rx` | 整数 | (`300`) | | ミリ秒 |
| `multiplier` | 整数 | (`3`) | | |
| `nodes` | [id] | | `layer1.nodes` | このタイマーを使う機器。`bfd: true` のセッションの両端はここにあること |

## routing_neighbors

セッション。1 エントリが 1 つのセッション (BGP のピア、OSPF / IS-IS の隣接) です。`type` で書くキーが変わります。

### type: bgp

```yaml
routing_neighbors:
  - id: bgp-peer-spine1-leaf1
    type: bgp
    instance: bgp-default                 # BGP のインスタンスが 1 つなら省略できる
    from: {node: spine1, update_source: spine1-swp1-l3}
    to:   {node: leaf1,  update_source: leaf1-swp51-l3}
    address_families: [ipv4_unicast]
    bfd: true
  - id: bgp-peer-border1-isp
    type: bgp
    from: {node: border1, update_source: border1-lo}
    to:   {address: 203.0.113.1, local_as: 64500}   # トポロジー外の相手
```

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `bgp-peer-`。同じ組の 2 本目は用途の語を末尾に (`bgp-peer-spine1-leaf1-overlay`) |
| `type` | `bgp` | ○ | | |
| `instance` | id | | `control_plane.bgp` | このセッションが属するインスタンス。BGP のインスタンスが 1 つなら省略できる |
| `from` | [端点](#bgp-の端点) | ○ | | |
| `to` | [端点](#bgp-の端点) | ○ | | `from` と `to` に向きの意味はない |
| `address_families` | [`ipv4_unicast` / `ipv6_unicast` / `l2vpn_evpn` / `vpnv4` / `vpnv6`] | | | 運ぶアドレスファミリー。1 本で複数運べる |
| `bfd` | 真偽値 | (`false`) | | |
| `description` | 文字列 | | | |

#### BGP の端点

トポロジーの中の機器か、トポロジー外の相手のどちらかです。両端ともトポロジー外にはできません。

| 形 | キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|---|
| トポロジーの中 | `node` | id | ○ | `layer1.nodes` | |
| | `update_source` | id | ○ | `layer3.interfaces` / `layer3.tunnel_interfaces` | セッションを張る IF。同じ機器のもの |
| | `route_reflector_client` | 真偽値 | (`false`) | | この端がルートリフレクタのクライアント。iBGP のときだけ |
| トポロジー外 | `address` | IP アドレス | ○ | | 相手のアドレス |
| | `local_as` | 整数 | ○ | | 相手自身の AS |

mlndl が両端から導くもの (書かない):

- **eBGP / iBGP**: 両端の AS (インスタンスの `local_as`) から
- **unnumbered**: `update_source` が `ip` も `ipv6` も持たない L3 IF なら unnumbered
- **通り道**: 下の [通り道](#通り道)

### type: ospf

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `ospf-adj-` |
| `type` | `ospf` | ○ | | |
| `instance` | id | | `control_plane.ospf` | |
| `from` / `to` | `{node, interface}` | ○ | `interface` は `layer3.interfaces` / `layer3.tunnel_interfaces` | 隣接を張る L3 IF (トンネル IF も書ける) |
| `area` | 文字列 | ○ | | `0.0.0.0` など |
| `bfd` | 真偽値 | (`false`) | | |
| `description` | 文字列 | | | |

### type: isis

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `isis-adj-` |
| `type` | `isis` | ○ | | |
| `instance` | id | | `control_plane.isis` | |
| `from` / `to` | `{node, interface}` | ○ | `interface` は `layer1.interfaces` | IS-IS は L2 の上で張るので L1 IF を指す |
| `level` | `level-1` / `level-2` / `level-all` | ○ | | |
| `bfd` | 真偽値 | (`false`) | | |
| `description` | 文字列 | | | |

## 通り道

セッションのパケットが通るリンクを、mlndl は両端の `update_source` (OSPF・IS-IS は `interface`) から導きます。セッションに `attaches_to` は書きません ([ADR-0010](../decisions/0010-control-plane-separation.md) D7、[ADR-0018](../decisions/0018-sessions-across-bridges-and-tunnels.md))。

| 両端の IF | 通り道 |
|---|---|
| 同じ L1 リンクの両端の上にある | `{link: <リンクの id>}` |
| 同じ LAG (または LAG のメンバーどうし) の上にある | `{lag: [<from の LAG>, <to の LAG>]}` |
| L1 リンクの対向が、どちらも同じ bridge のポート (1 ホップ) | `{bridge: <bridge の id>}` |
| 互いの `source` を宛先にした対のトンネル IF | `{tunnel: [<from のトンネル>, <to のトンネル>]}` |
| ループバックどうしなど、どれにも載らない (multihop) | 導かない |
| SVI・トポロジー外の相手・宛先が `destination_ip` のトンネル | 導かない |

上のどれにも当てはまらず両端の通り道が食い違うと、BGP も OSPF / IS-IS も error になります ([ADR-0025](../decisions/0025-end-grace-for-old-forms.md) D2)。メッセージは両端の通り道と直し方を示します。
