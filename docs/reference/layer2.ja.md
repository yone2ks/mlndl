# layer2

L2 の構成: VLAN・bridge・VTEP・VXLAN・サブ IF。[リファレンスの目次](README.ja.md)

| キー | 型 | 説明 |
|---|---|---|
| `vlans` | [[VLAN](#vlans)] | 番号を持つ L2 セグメント |
| `bridges` | [[bridge](#bridges)] | 番号を持たない L2 セグメント (事業者網の箱の中の転送) |
| `vteps` | [[VTEP](#vteps)] | VXLAN のトンネル端点 |
| `vxlan` | [[VNI](#vxlan)] | L2VNI と L3VNI |
| `subinterfaces` | [[サブ IF](#subinterfaces)] | 802.1Q の routed サブ IF |

## vlans

VLAN と、それが載るポート。

```yaml
vlans:
  - id: vlan-100
    vlan_id: 100
    trunk_ports:
      - {lag: lag-mlag-server1}     # LAG はメンバーではなく LAG を指す。MLAG は 1 行で両方の機器
      - {interface: leaf1-swp4}
    access_ports:
      - {interface: server1-eth0}
```

| キー | 型 | 必須 | 説明 |
|---|---|---|---|
| `id` | id | ○ | `vlan-<番号>` が慣例 |
| `vlan_id` | 整数 | ○ | 802.1Q の VLAN ID (1〜4094。範囲外は error)。別の機器なら同じ番号を別の VLAN に使ってよい |
| `name` | 文字列 | | 機器上の VLAN 名 |
| `trunk_ports` | [[ポート](#ポート)] | | タグ付きで流すポート |
| `access_ports` | [[ポート](#ポート)] | | タグなしで流すポート |
| `description` | 文字列 | | |

### ポート

`{interface:}` か `{lag:}` のどちらか一方を書きます ([ADR-0013](../decisions/0013-vlan-ports-on-lag.md))。

| キー | 型 | 参照先 | 説明 |
|---|---|---|---|
| `interface` | id | `layer1.interfaces` | L1 IF |
| `lag` | id | `layer1.lag` | LAG。MLAG を指せば 2 台のポートを 1 行で書ける |
| `native` | 真偽値 (`false`) | | trunk でこの VLAN をタグなし (native VLAN) で流すなら `true` |

`node` は書きません (参照先から導く。1.x の間は書いても warning で受け付ける)。
同じ VLAN に LAG とそのメンバーを併記すると error、メンバーだけを書くと `{lag:}` を促す warning です。

VLAN のポートの対向にある L3 IF (サーバーの IP など) は、mlndl がリンクをたどって導きます (VLAN の端点。[ADR-0013](../decisions/0013-vlan-ports-on-lag.md) D7)。

## bridges

番号を持たない L2 セグメント。事業者網の箱の中で、拠点のあいだのフレームを転送することを表します ([ADR-0018](../decisions/0018-sessions-across-bridges-and-tunnels.md) D1)。
bridge を書かない箱は L2 で透過しません。

```yaml
bridges:
  - id: bridge-wideether
    name: WE-220                            # 回線 ID などは id に埋めず name / description に
    ports:                                  # 箱のポートだけ。拠点のルーターのポートは書かない
      - {interface: net-wideether-tokyo}
      - {interface: net-wideether-osaka}
```

| キー | 型 | 必須 | 説明 |
|---|---|---|---|
| `id` | id | ○ | 推奨プレフィックス `bridge-` |
| `name` | 文字列 | | |
| `ports` | [`{interface:}` / `{lag:}`] | | 転送する側 (箱) のポート。`node` と `native` は持たない |
| `description` | 文字列 | | |

方式名 (E-LINE、VPLS など) は書きません。両端のルーターの L1 リンクの対向が同じ bridge のポートなら、そのあいだのセッションの通り道は `{bridge: <id>}` になります ([control-plane.md](control-plane.ja.md#通り道))。

## vteps

VXLAN のトンネル端点 ([ADR-0014](../decisions/drafts/0014-vteps.md))。方式名 (anycast VTEP、vPC など) は書きません。

```yaml
vteps:
  - id: vtep-leaf1-leaf2
    sources: [leaf1-lo, leaf2-lo]   # この VTEP を終端する機器の L3 IF (ループバック)
    address: 10.0.100.12/32         # 複数の機器で共有するときは必須
  - id: vtep-border1
    sources: [border1-lo]           # 1 つならアドレスは省略でき、その L3 IF の ip になる
```

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `vtep-` |
| `sources` | [id] | ○ | `layer3.interfaces` | この VTEP を終端する機器の L3 IF。1 台につき 1 つ。`node` は書かない |
| `address` | IPv4 プレフィックス付きアドレス | | | VTEP のアドレス。`sources` が複数なら必須 |
| `address_v6` | IPv6 プレフィックス付きアドレス | | | |
| `description` | 文字列 | | | |

## vxlan

VNI。`type` で L2VNI と L3VNI を分けます。L2VNI と L3VNI を通して `vni` は重複できません。

### type: l2vni

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | `vni-<番号>` が慣例 |
| `type` | `l2vni` | ○ | | |
| `vni` | 整数 | ○ | | |
| `vlan` | id | ○ | `layer2.vlans` | この VNI に対応する VLAN |
| `vteps` | [id] | | `layer2.vteps` | この VNI に参加する VTEP。参加する機器は VTEP から導く |
| `description` | 文字列 | | | |

旧形式の `vtep_source` / `members` は、1.x の間は warning で受け付けます。

### type: l3vni

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | |
| `type` | `l3vni` | ○ | | |
| `vni` | 整数 | ○ | | |
| `vrf` | id | ○ | `layer3.vrfs` | この VNI に対応する VRF。VRF の `l3vni` と互いに一致させる |
| `irb_mode` | `symmetric` / `asymmetric` | | | |
| `description` | 文字列 | | | |

## subinterfaces

L1 IF や LAG の上の 802.1Q の routed サブ IF (router-on-a-stick など。[ADR-0012](../decisions/0012-subinterfaces.md))。IP と VRF は、このサブ IF に載る [L3 IF](layer3.ja.md#interfaces) に書きます。

```yaml
subinterfaces:
  - id: subif-border1-swp5-200
    attaches_to: {interface: border1-swp5}
    vlan_id: 200
    name: swp5.200
```

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `subif-` |
| `attaches_to` | `{interface:}` / `{lag:}` | ○ | `layer1.interfaces` / `layer1.lag` | このサブ IF の基盤 |
| `vlan_id` | 整数 | ○ | | このリンクの上の 802.1Q のタグ番号 (1〜4094)。`layer2.vlans` への参照ではなく、照合もしない |
| `name` | 文字列 | | | 機器上の名前 (`swp5.200`) |
| `description` | 文字列 | | | |

`node` は持ちません。基盤の L1 IF・LAG から機器を導きます。
