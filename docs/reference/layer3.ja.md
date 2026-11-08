# layer3

L3 の構成 (データプレーン): VRF・L3 IF・トンネル IF。[リファレンスの目次](README.ja.md)

スタティックルート、ポリシールーティング、VRF 間のリークなどは MLNDL の範囲外です ([ADR-0011](../decisions/0011-layer3-data-plane.md) D2)。ルーティングのセッションは [control_plane](control-plane.ja.md) に書きます。

| キー | 型 | 説明 |
|---|---|---|
| `vrfs` | [[VRF](#vrfs)] | |
| `interfaces` | [[L3 IF](#interfaces)] | IP を持つ IF |
| `tunnel_interfaces` | [[トンネル IF](#tunnel_interfaces)] | GRE・IPsec VTI など |

## vrfs

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `vrf-` |
| `rd` | 文字列 | | | Route Distinguisher ([書き方](types.ja.md#route-target-と-route-distinguisher)) |
| `l3vni` | id | | `layer2.vxlan` | この VRF の L3VNI。L3VNI の `vrf` と互いに一致させる |
| `route_targets` | `{import, export}` | | | Route Target。`import` と `export` に、それぞれ文字列の列を書く ([書き方](types.ja.md#route-target-と-route-distinguisher)) |
| `description` | 文字列 | | | |

L3 IF やインスタンスで `vrf` を書かなければ default VRF です。`vrf: vrf-default` のように default VRF に名前を付けて書く場合は、その VRF も `vrfs` に定義します。

## interfaces

L3 IF。IP を持つ IF です。何の上にあるかを `attaches_to` で書き、その種類で分類します ([ADR-0011](../decisions/0011-layer3-data-plane.md) D11)。

```yaml
interfaces:
  - id: leaf1-swp51-l3                      # routed ポート
    node: leaf1
    name: swp51
    ip: 10.1.0.1/31
    attaches_to: {interface: leaf1-swp51}
  - id: leaf1-vlan-100                      # SVI
    node: leaf1
    name: Vlan100
    ip: 192.168.100.1/24
    vrf: vrf-tenant-a
    attaches_to: {vlan: vlan-100}
    gateway_redundancy:
      - {mode: anycast_gateway}             # 全ノードで同じ ip。MAC アドレスは書かない
  - {id: leaf1-lo, node: leaf1, name: lo, ip: 10.0.0.1/32}   # attaches_to なし (ループバックなど)
```

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | `<機器の id>-<名前>` が慣例 |
| `node` | id | ○ | `layer1.nodes` | この IF を持つ機器。`attaches_to` の参照先の機器 (群) に含まれること |
| `name` | 文字列 | ○ | | 機器上の名前 (`swp51`、`Vlan100`、`lo`)。参照ではない。同じ機器で重複できない |
| `ip` | IPv4 プレフィックス付きアドレス | | | |
| `ipv6` | IPv6 プレフィックス付きアドレス | | | |
| `vrf` | id | | `layer3.vrfs` | 省略すると default VRF |
| `attaches_to` | `{interface:}` / `{lag:}` / `{vlan:}` / `{subinterface:}` | | 下の表 | この IF の基盤。オブジェクトの形だけ (文字列では書けない) |
| `gateway_redundancy` | [[ゲートウェイ冗長](#gateway_redundancy)] | | | |
| `description` | 文字列 | | | |

| `attaches_to` のキー | 参照先 | 分類 | 例 |
|---|---|---|---|
| `interface` | `layer1.interfaces` | L1 IF の上 | routed ポート |
| `lag` | `layer1.lag` | LAG の上 | routed LAG。MLAG / ESI-LAG の上なら機器ごとの LAG を指す |
| `vlan` | `layer2.vlans` | VLAN の上 | SVI |
| `subinterface` | `layer2.subinterfaces` | サブ IF の上 | router-on-a-stick |
| (書かない) | | どれにも載らない | ループバックなど。ループバックとみなすわけではない |

`attaches_to` に `{ethernet_segment:}` は書けません。L3 IF は機器ごとに IP を持つので、機器ごとの LAG を `{lag:}` で指します ([ADR-0023](../decisions/0023-per-device-lag-and-ethernet-segments.md) D5)。

分類は `attaches_to` のキーで決まり、`name` では決めません。`ip` も `ipv6` も持たない L3 IF を BGP の `update_source` にすると unnumbered になります ([control-plane.md](control-plane.ja.md))。

### gateway_redundancy

VRRP・HSRP・anycast gateway。`mode` で書くキーが変わります ([ADR-0011](../decisions/0011-layer3-data-plane.md) D4)。IPv4 と IPv6 は別のエントリに書きます。

```yaml
gateway_redundancy:
  - {mode: vrrp, group_id: 100, vip: 192.168.100.254, priority: 110}
  - {mode: vrrp, group_id: 100, vip: "fe80::1", priority: 110}     # IPv6 の VIP はリンクローカル
```

| mode | キー | 型 | 必須 | 説明 |
|---|---|---|---|---|
| `vrrp` / `hsrp` | `group_id` | 整数 | ○ | 同じ IF・同じ mode・同じアドレスファミリーで重複できない |
| | `vip` | IP アドレス | ○ | IPv4 は IF のサブネットの中。IPv6 はリンクローカル (RFC 5798) |
| | `priority` | 整数 | | |
| | `preempt` | 真偽値 | | |
| `anycast_gateway` | (なし) | | | 同じ VLAN の anycast gateway の群で `ip` / `ipv6` が一致すること |

どの mode も `description` を書けます。
anycast の MAC アドレス (`anycast_mac`) は書きません。MAC アドレスは構成図の粒度ではないためです。書くと error になります ([ADR-0022](../decisions/0022-diagram-granularity.md) D2)。

## tunnel_interfaces

トンネル IF ([ADR-0011](../decisions/0011-layer3-data-plane.md) D6)。外側のパケットの送り元と宛先を自分で持ちます (トンネルのリンクは書かない)。

```yaml
tunnel_interfaces:
  - id: tunnel-border1-dc2
    node: border1
    type: gre
    source: border1-wan                     # 同じ機器の L3 IF
    destination_interface: dc2-border1-wan  # トポロジー外なら destination_ip
    ip: 172.31.0.1/30
    vrf: vrf-tenant-a                       # トンネル IF が属する VRF (内側)
    transport_vrf: vrf-default              # 外側のパケットが流れる VRF
    mtu: 1476
```

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `tunnel-`。L3 IF の id とも重複できない |
| `node` | id | ○ | `layer1.nodes` | |
| `type` | `gre` / `ipip` / `ipsec_vti` / `wireguard` | ○ | | |
| `source` | id | ○ | `layer3.interfaces` | 外側の送り元。同じ機器の L3 IF |
| `destination_interface` | id | (どちらか一方) | `layer3.interfaces` | 外側の宛先。別の機器の L3 IF |
| `destination_ip` | IP アドレス | (どちらか一方) | | 外側の宛先がトポロジー外のとき |
| `ip` | IPv4 プレフィックス付きアドレス | | | トンネル IF のアドレス |
| `ipv6` | IPv6 プレフィックス付きアドレス | | | |
| `vrf` | id | | `layer3.vrfs` | トンネル IF が属する VRF |
| `transport_vrf` | id | | `layer3.vrfs` | 外側のパケットが流れる VRF |
| `mtu` | 整数 | | | トンネル IF の MTU。68 以上 |
| `description` | 文字列 | | | |

外側のアドレスファミリーは、`source` と宛先で一致させます。両端をトポロジーの中に書くときは、逆向きのトンネルも書きます (ないと info)。
2 本のトンネルが互いの `source` を宛先にしていれば対になり、その上のセッションの通り道は `{tunnel: [...]}` になります ([control-plane.md](control-plane.ja.md#通り道))。
