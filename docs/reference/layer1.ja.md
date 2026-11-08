# layer1

物理の構成: 機器・L1 IF・リンク・LAG・Ethernet Segment。[リファレンスの目次](README.ja.md)

```yaml
layer1:
  nodes:
    - {id: spine1, role: spine, implementation: vm, device_type: cumulus_linux}
    - {id: leaf1,  role: leaf,  implementation: vm, attaches_to: esxi-01, labels: {site: tokyo}}
  interfaces:
    - {id: spine1-swp1, node: spine1, name: swp1}
    - {id: leaf1-swp51, node: leaf1,  name: swp51}
  links:
    - {id: link-spine1-leaf1, endpoints: [spine1-swp1, leaf1-swp51], link_speed: 10G}
  lag:
    - {id: lag-leaf1-bond0, node: leaf1, name: bond0, members: [leaf1-swp1, leaf1-swp2]}
  ethernet_segments:
    - {id: es-server1, members: [{lag: lag-leaf1-server1}, {lag: lag-leaf2-server1}]}
```

| キー | 型 | 説明 |
|---|---|---|
| `nodes` | [[機器](#nodes)] | |
| `interfaces` | [[L1 IF](#interfaces)] | |
| `links` | [[リンク](#links)] | |
| `lag` | [[LAG](#lag)] | 機器 1 台の LAG |
| `ethernet_segments` | [[Ethernet Segment](#ethernet_segments)] | 複数の機器の脚を相手から 1 本に見せる関係 (MLAG / vPC / MC-LAG / ESI-LAG) |

## nodes

機器。物理機器・VM・コンテナを問わず、ネットワークの「箱」を表します。事業者網 (`role: provider-network`) もここに書きます。

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | |
| `name` | 文字列 | | | 表示名 |
| `implementation` | `vm` / `physical` / `container` | | | 実装の形。Layer 1 なので `virtual` はない ([ADR-0004](../decisions/0004-implementation-role-matrix.md)) |
| `role` | 文字列 | | | 役割。自由な文字列で、推奨値は [role-vocabulary.md](../role-vocabulary.md)。`implementation: container` と `role: hypervisor` の組だけは error |
| `device_type` | 文字列 | | | 機種を表す抽象的なキー (`cumulus_linux` など)。EVE-NG のテンプレートや CPU 数は書かない。上位のツールが変換する |
| `attaches_to` | 文字列 / `{node:}` / `{interface:}` | | `layer1.nodes` / `layer1.interfaces` | この機器が動く基盤。VM ならホスト。文字列で書くと `{node:}` と同じ ([README.md](README.ja.md#attaches_to-実現)) |
| `labels` | 文字列 → 文字列 | | | 多軸の分類 ([ADR-0009](../decisions/0009-membership-orthogonality.md))。値は参照ではない。サイトは `labels: {site: tokyo}` ([ADR-0017](../decisions/0017-sites-and-wan.md)) |
| `description` | 文字列 | | | |

`overrides` はなくしました。書くと error です。EVE-NG の CPU・RAM・イメージなど、下流のツールが機器ごとに変える値は、そのツールの設定で機器の `id` を引いて書きます ([ADR-0024](../decisions/0024-remove-node-overrides.md))。

### 事業者網の箱

IP-VPN・広域イーサ・インターネットなどの事業者網は、`role: provider-network` の機器として書き、拠点からの回線を箱への `links` で書きます。
サービスの種類は `role` で分けず `name` に書きます。箱は L3 IF を持ちません (規約。検査はしない)。箱の中で L2 を転送するなら [`layer2.bridges`](layer2.ja.md#bridges) に書きます。
詳しくは [ADR-0017](../decisions/0017-sites-and-wan.md)。

## interfaces

L1 IF。物理ポート、VM の vNIC、コンテナの veth など。IP は持たず、IP は [L3 IF](layer3.ja.md#interfaces) に書きます。

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | `<機器の id>-<ポート>` が慣例 (`leaf1-swp51`) |
| `node` | id | ○ | `layer1.nodes` | この IF を持つ機器 |
| `name` | 文字列 | | | 機器上の名前 (`swp51`、`Ethernet1/1`) |
| `attaches_to` | `{node:}` / `{interface:}` | | `layer1.nodes` / `layer1.interfaces` | この IF を実現する基盤 (vNIC が載る物理 NIC など) |
| `description` | 文字列 | | | |

## links

2 つの L1 IF をつなぐ物理リンク (ケーブル・回線)。2 点間の専用線やダークファイバもここに書きます。

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `link-` |
| `endpoints` | [id] | ○ | `layer1.interfaces` | ちょうど 2 つ。順序に意味はない (リンクは無向。[ADR-0006](../decisions/0006-endpoints.md)) |
| `link_speed` | 速度 | | | ポートの速度。`10G`、`2.5G`、`1.6T` など ([速度](types.ja.md#速度))。契約帯域ではない (契約帯域は `description`) |
| `link_role` | 文字列 | | | 自由な文字列。推奨値は `underlay` / `access` / `trunk` / `peer-link` / `management` / `uplink` |
| `description` | 文字列 | | | 回線 ID・契約帯域・事業者名など ([ADR-0017](../decisions/0017-sites-and-wan.md) D4) |

MTU はリンクには書きません。MTU はインターフェースの設定で、リンク (ケーブル) の性質ではないためです ([ADR-0020](../decisions/0020-remove-l1-link-mtu.md))。

## lag

LAG。機器 1 台の上の port-channel / bond / ae です ([ADR-0023](../decisions/0023-per-device-lag-and-ethernet-segments.md) D1)。
MLAG / vPC / MC-LAG / ESI-LAG でも、実機の LAG は機器ごとにあるので、機器ごとに 1 つずつ書きます。
それらを相手から 1 本に見せる関係は [`ethernet_segments`](#ethernet_segments) に書きます。
スタック / VSS / Virtual Chassis / IRF は 1 台の論理機器なので、筐体をまたぐ LAG もここに 1 つ書き、`ethernet_segments` は書きません。

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `lag-` |
| `node` | id | ○ | `layer1.nodes` | LAG を持つ機器 (1 台) |
| `name` | 文字列 | | | 機器上の名前 (`Port-Channel10`、`bond0`、`ae0`) |
| `members` | [id] | ○ | `layer1.interfaces` | メンバーの L1 IF |
| `lacp` | [LACP の設定](#lacp-の設定) | | | |
| `description` | 文字列 | | | |

ピアリンク (MLAG / vPC で 2 台をつなぐ LAG) も、機器ごとの普通の LAG として書きます。役割は L1 リンクの `link_role: peer-link` で示せますが、注釈なので検査には使いません ([ADR-0023](../decisions/0023-per-device-lag-and-ethernet-segments.md) D6)。

以前の `type: lacp` / `type: mlag`、`nodes`、`peer_link`、`peer_link_interface`、`domain_id`、`system_mac`、`client_lag` は書けません。書くと移動先を示す error になります。
ドメインの番号や MAC は構成図の粒度ではないので書きません ([ADR-0022](../decisions/0022-diagram-granularity.md))。

### LACP の設定

| キー | 型 | 必須 | 説明 |
|---|---|---|---|
| `mode` | `active` / `passive` / `on` | (`active`) | |
| `min_links` | 整数 | (`1`) | |


## ethernet_segments

複数の機器の脚 (LAG か L1 IF) を、相手 (ホスト / CE) から 1 本に見せる関係です ([ADR-0023](../decisions/0023-per-device-lag-and-ethernet-segments.md))。
名前は RFC 7432 の Ethernet Segment から取りました。MLAG / vPC / MC-LAG / EVPN multihoming (ESI-LAG) をこの 1 つの形で書き、方式名は書きません。どの方式かは上位のツールが `device_type` から判断します。

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `es-` |
| `name` | 文字列 | | | 表示名 |
| `members` | [`{lag:}` / `{interface:}`] | ○ | `layer1.lag` / `layer1.interfaces` | 脚。2 つ以上で、機器はすべて別 |
| `redundancy_mode` | `all_active` / `single_active` | | | 脚がそろって転送するか、同時に転送するのは 1 本か。既定値はなく、書かなければ「書いていない」 |
| `description` | 文字列 | | | |

```yaml
lag:
  - {id: lag-leaf1-peer,    node: leaf1, name: peerlink, members: [leaf1-swp49, leaf1-swp50]}   # ピアリンクは普通の LAG
  - {id: lag-leaf2-peer,    node: leaf2, name: peerlink, members: [leaf2-swp49, leaf2-swp50]}
  - {id: lag-leaf1-server1, node: leaf1, name: bond1, members: [leaf1-swp1]}
  - {id: lag-leaf2-server1, node: leaf2, name: bond1, members: [leaf2-swp1]}
ethernet_segments:
  # MLAG / vPC / ESI-LAG (all-active)。clag-id・vPC 番号・ESI の値・system MAC は書かない
  - id: es-server1
    members: [{lag: lag-leaf1-server1}, {lag: lag-leaf2-server1}]
  # ESI の single-active。CE が LAG を組まず、物理 IF に直接 ESI を設定する構成は {interface:} で書く
  - id: es-fw1
    members: [{interface: leaf3-xe-0-0-4}, {interface: leaf4-xe-0-0-4}]
    redundancy_mode: single_active
```

- 脚が LAG なら `{lag:}`、LAG を作らず物理 IF に直接設定するなら `{interface:}` で指します。LAG のメンバーの IF を書くと、LAG を指すよう warning が出ます
- 同じ機器の脚を 2 つ書く、1 つの脚を 2 つの ES に入れる、LAG とそのメンバーを併記する、脚どうしが L1 リンクでつながっている (ピアリンクを脚にした疑い) は error です
- VLAN のポートと bridge のポートは `{ethernet_segment: <id>}` で ES を指せます ([layer2](layer2.ja.md#vlans))。脚の全機器に効きます
- L3 IF とサブ IF は ES を指せません。機器ごとに IP や設定が違うので、機器ごとの LAG を `{lag:}` で指します
- どの脚が転送するか (single-active の DF) は書きません。DF 選出で決まり、VLAN ごとに変わるためです

### 方式との対応

| 構成 | 書き方 |
|---|---|
| Cumulus clag / Arista MLAG / Cisco vPC / Juniper MC-LAG | 機器ごとの LAG を 2 つ、ES の `members` に `{lag:}` で並べる。ピアリンクは普通の LAG |
| Cisco vPC Fabric Peering (物理のピアリンクなし) | 同上で、ピアリンクの LAG がないだけ |
| EVPN multihoming (ESI-LAG、all-active) | 機器ごとの LAG を 2 つ以上。ES ごとに機器の組み合わせが違ってよい |
| EVPN multihoming (single-active) | `{interface:}` か `{lag:}` で脚を並べ、`redundancy_mode: single_active` |
| スタック / VSS / Virtual Chassis / IRF | 1 台の L1 ノードと 1 つの LAG。ES は書かない |
