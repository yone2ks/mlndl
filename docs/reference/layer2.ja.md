# layer2

L2 の構成: VLAN・bridge・VTEP・VXLAN・サブ IF。[リファレンスの目次](README.ja.md)

| キー | 型 | 説明 |
|---|---|---|
| `vlans` | [[VLAN](#vlans)] | 番号を持つ L2 セグメント |
| `bridges` | [[bridge](#bridges)] | 番号を持たない L2 セグメント (事業者網の箱の中の転送) |
| `vteps` | [[VTEP](#vteps)] | VXLAN のトンネル端点 |
| `vxlans` | [[VNI](#vxlans)] | L2VNI と L3VNI |
| `subinterfaces` | [[サブ IF](#subinterfaces)] | 802.1Q の routed サブ IF |

id を持つエントリの一覧は複数形です。以前の `vxlan` は `vxlans` に改名しました。書くと移動先を示す error です ([ADR-0028](../decisions/0028-names-and-types.md) D1)。
`vxlans` のエントリは VXLAN のトンネルの 1 本ずつではなく VNI です。`vnis` としなかったのは、番号のリストに見え、エントリの `vni:` と語が重なるためです。

## vlans

VLAN と、それが載るポート。

```yaml
vlans:
  - id: vlan-100
    vlan_id: 100
    trunk_ports:
      - {ethernet_segment: es-server1}   # Ethernet Segment は 1 行で脚の全機器 (MLAG / vPC / ESI-LAG)
      - {lag: lag-leaf3-po1}             # LAG はメンバーではなく LAG を指す
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

`{interface:}`・`{lag:}`・`{ethernet_segment:}` のどれか 1 つを書きます ([ADR-0013](../decisions/0013-vlan-ports-on-lag.md)、[ADR-0023](../decisions/0023-per-device-lag-and-ethernet-segments.md) D5)。

| キー | 型 | 参照先 | 説明 |
|---|---|---|---|
| `interface` | id | `layer1.interfaces` | L1 IF |
| `lag` | id | `layer1.lags` | 機器 1 台の LAG |
| `ethernet_segment` | id | `layer1.ethernet_segments` | Ethernet Segment。脚の全機器のポートを 1 行で書ける |
| `native` | 真偽値 (`false`) | | trunk でこの VLAN をタグなし (native VLAN) で流すなら `true` |

`node` は書きません。ノードは参照先から導きます。書くと error です ([ADR-0025](../decisions/0025-end-grace-for-old-forms.md))。
同じ VLAN に LAG とそのメンバーを併記すると error、メンバーだけを書くと `{lag:}` を促す warning です。
同じように、Ethernet Segment とその脚 (脚の LAG のメンバーを含む) を併記すると error、脚の一部だけを書くと `{ethernet_segment:}` を促す warning です
(MLAG の片側にだけ VLAN を載せる誤りを拾う)。脚をすべて機器ごとに書くのは `{ethernet_segment:}` と同じ意味なので warning にしません。

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
| `ports` | [`{interface:}` / `{lag:}` / `{ethernet_segment:}`] (1 つ以上) | ○ | 転送する側 (箱) のポート。`node` と `native` は持たない。事業者網を PE ごとに書き、拠点が 2 台の PE に冗長に接続するなら `{ethernet_segment:}` |
| `description` | 文字列 | | |

方式名 (E-LINE、VPLS など) は書きません。両端のルーターの L1 リンクの対向が同じ bridge のポートなら、そのあいだのセッションの通り道は `{bridge: <id>}` になります ([control-plane.md](control-plane.ja.md#通り道))。

## vteps

VXLAN のトンネル端点 ([ADR-0014](../decisions/0014-vteps.md))。方式名 (anycast VTEP、vPC など) は書きません。

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

複数の機器で共有する VTEP (MLAG / vPC のペアなど) の `address` は、たいてい各機器のループバックの `ip` とは別の値です
(Cumulus の `clagd-vxlan-anycast-ip`、NX-OS の NVE の secondary IP など)。`sources` の L3 IF の `ip` から決まるわけではないので、共有するときは必ず書きます。
同じ値を 2 つの VTEP に書くと error です。

## vxlans

VNI。`type` で L2VNI と L3VNI を分けます。L2VNI と L3VNI を通して `vni` は重複できません。

### type: l2vni

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | `vni-<番号>` が慣例 |
| `type` | `l2vni` | ○ | | |
| `vni` | 整数 (1〜16777215) | ○ | | |
| `vlans` | [id] (1 つ以上) | ○ | `layer2.vlans` | この VNI に載る VLAN。機器によって番号が違うときは、番号ごとの VLAN のエントリを並べる。同じ id を 2 回書くと error |
| `vteps` | [id] (1 つ以上) | ○ | `layer2.vteps` | この VNI に参加する VTEP。参加する機器は VTEP から導く |
| `description` | 文字列 | | | |

L2VNI に入る VLAN では、ブロードキャストドメインを表すのは L2VNI です。VLAN のエントリは「ある番号と、その番号でつながるポート」で、
`vlans` に並んだエントリが合わさって 1 つのドメインになります ([ADR-0026](../decisions/0026-l2vni-vlans.md))。

```yaml
vlans:
  - {id: vlan-20, vlan_id: 20, trunk_ports: [{ethernet_segment: es-server1}, {interface: leaf4-swp3}]}   # leaf1 / leaf2 / leaf4
  - {id: vlan-30, vlan_id: 30, access_ports: [{interface: leaf3-swp1}]}                                  # leaf3 だけ番号が違う
vxlans:
  - {id: vni-10020, type: l2vni, vni: 10020, vlans: [vlan-20, vlan-30], vteps: [vtep-leaf1-leaf2, vtep-leaf3, vtep-leaf4]}
```

- 全機器で番号が同じなら `vlans: [vlan-100]` と 1 つだけ書きます
- 同じ番号は、何台の機器にまたがっても 1 つのエントリに書きます。エントリを分けるのは番号が違うときだけです
- 参加機器 (VTEP から導く) ごとに、その機器の VLAN は VLAN のポートか、その VLAN を指す SVI (`attaches_to: {vlan:}`) の機器から導きます。
  SVI だけを持つ機器 (border leaf など) の VLAN も決まります
- 1 台の機器に同じ VNI の VLAN が 2 つあるのは error です。Ethernet Segment の脚の機器で番号が違うのも error です
- `vlans` は VLAN-aware bundle (1 つの MAC-VRF に入る、VNI の違う VLAN の集まり) ではありません

旧形式の `vlan` (単数) は、書くと `vlans` への移動先を示す error です ([ADR-0026](../decisions/0026-l2vni-vlans.md))。
旧形式の `vtep_source` / `members` は、書くと `vteps` への移動先を示す error です ([ADR-0025](../decisions/0025-end-grace-for-old-forms.md))。

### type: l3vni

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | |
| `type` | `l3vni` | ○ | | |
| `vni` | 整数 (1〜16777215) | ○ | | |
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
| `attaches_to` | `{interface:}` / `{lag:}` | ○ | `layer1.interfaces` / `layer1.lags` | このサブ IF の基盤 |
| `vlan_id` | 整数 | ○ | | このリンクの上の 802.1Q のタグ番号 (1〜4094)。`layer2.vlans` への参照ではなく、照合もしない |
| `name` | 文字列 | | | 機器上の名前 (`swp5.200`) |
| `description` | 文字列 | | | |

`node` は持ちません。基盤の L1 IF・LAG から機器を導きます。
MLAG / ESI-LAG の上のサブ IF も、機器ごとの LAG を `{lag:}` で指して機器ごとに書きます。`{ethernet_segment:}` は指せません ([ADR-0023](../decisions/0023-per-device-lag-and-ethernet-segments.md) D5)。
