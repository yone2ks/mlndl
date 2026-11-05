# layer1

物理の構成: 機器・L1 IF・リンク・LAG。[リファレンスの目次](README.ja.md)

```yaml
layer1:
  nodes:
    - {id: spine1, role: spine, implementation: vm, device_type: cumulus_linux}
    - {id: leaf1,  role: leaf,  implementation: vm, attaches_to: esxi-01, labels: {site: tokyo}}
  interfaces:
    - {id: spine1-swp1, node: spine1, name: swp1}
    - {id: leaf1-swp51, node: leaf1,  name: swp51}
  links:
    - {id: link-spine1-leaf1, endpoints: [spine1-swp1, leaf1-swp51], link_speed: 10G, mtu: 9216}
  lag:
    - {id: lag-leaf1-bond0, type: lacp, node: leaf1, members: [leaf1-swp1, leaf1-swp2]}
```

| キー | 型 | 説明 |
|---|---|---|
| `nodes` | [[機器](#nodes)] | |
| `interfaces` | [[L1 IF](#interfaces)] | |
| `links` | [[リンク](#links)] | |
| `lag` | [[LAG](#lag)] | LACP (1 台) と MLAG (2 台) |

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
| `overrides` | マッピング | | | 上位のツールの既定値の上書き (`{eve_ng: {cpu: 4}}` など)。mlndl は中を見ない |
| `description` | 文字列 | | | |

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
| `link_speed` | 文字列 | | | `10G`、`100G` など |
| `mtu` | 整数 | | | VXLAN の underlay は 1550 以上 (推奨 9216) |
| `link_role` | 文字列 | | | 自由な文字列。推奨値は `underlay` / `access` / `trunk` / `peer-link` / `management` / `uplink` |
| `description` | 文字列 | | | 回線 ID・契約帯域・事業者名など ([ADR-0017](../decisions/0017-sites-and-wan.md) D4) |

## lag

LAG。`type` で LACP (1 台の bond) と MLAG (2 台にまたがる bond) を分けます。

### type: lacp

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | 推奨プレフィックス `lag-` |
| `type` | `lacp` | ○ | | |
| `node` | id | ○ | `layer1.nodes` | bond を持つ機器 (単数) |
| `members` | [id] | ○ | `layer1.interfaces` | メンバーの L1 IF |
| `lacp` | [LACP の設定](#lacp-の設定) | | | |
| `description` | 文字列 | | | |

### type: mlag

| キー | 型 | 必須 | 参照先 | 説明 |
|---|---|---|---|---|
| `id` | id | ○ | | |
| `type` | `mlag` | ○ | | |
| `nodes` | [id] | ○ | `layer1.nodes` | ちょうど 2 台 (複数形) |
| `members` | [id] | ○ | `layer1.interfaces` | 両方の機器のメンバー |
| `lacp` | [LACP の設定](#lacp-の設定) | | | |
| `peer_link` | id | ○ | `layer1.lag` | 2 台を結ぶピアリンクの LAG (同じ `lag` の一覧の LACP) |
| `peer_link_interface` | 文字列 | ○ | | ピアリンクの機器上の名前 (`peerlink.4094`) |
| `domain_id` | 整数 | | | MLAG のドメイン ID |
| `system_mac` | 文字列 | | | 2 台で共通の system MAC |
| `client_lag` | id | | `layer1.lag` | 対向の機器 (サーバーなど) 側の LACP の LAG |
| `description` | 文字列 | | | |

```yaml
lag:
  - {id: lag-peer-link, type: lacp, node: leaf1, members: [leaf1-swp49, leaf1-swp50]}
  - id: lag-mlag-server1
    type: mlag
    nodes: [leaf1, leaf2]
    members: [leaf1-swp3, leaf2-swp3]
    lacp: {mode: active, min_links: 1}
    peer_link: lag-peer-link
    peer_link_interface: peerlink.4094
    domain_id: 10
```

### LACP の設定

| キー | 型 | 必須 | 説明 |
|---|---|---|---|
| `mode` | `active` / `passive` / `on` | (`active`) | |
| `min_links` | 整数 | (`1`) | |
