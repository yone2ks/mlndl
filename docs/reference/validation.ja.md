# 検査

MLNDL のファイルが正しいかどうかの検査と、その重さ (severity) です。[リファレンスの目次](README.ja.md)

## 重さ

| 重さ | 意味 | 例 |
|---|---|---|
| **error** | 正しい MLNDL ではない。上位のツールは読み込みを止めてよい | 参照先がない、id の文法違反、IP の形式違反 |
| **warning** | 正しいが、誤りの疑いがあるか、推奨から外れている | 推奨プレフィックスに従わない id、旧形式の書き方 |
| **info** | 正しく、知らせておくだけのこと | 対向がトポロジー内にあるのに逆向きのトンネルがない |

`python -m mlndl validate --strict` は warning を error として扱います。決め方は [ADR-0002](../decisions/0002-id-naming-convention.md) D8 にあります。

検査は 2 段階で行います。

1. **スキーマ**: キーの名前と値の型、必須のキー、列挙の値、1 つのエンティティの中で決まる規則 (`container` × `hypervisor` など)。ここで誤りがあると次の段階に進めません
2. **意味の検査**: 参照の存在と、エンティティをまたぐ規則 (重複、ネットワークとしての整合)

## 読み込み

| 検査 | 重さ |
|---|---|
| ファイルが 1MB を超えない | error |
| YAML として読める。同じマッピングに同じキーを 2 回書いていない | error |
| `ndl_version` の主番号が 1 | error |
| 決められたキーしか書いていない (`meta` を除く) | error |

## すべての区画に共通

| 検査 | 重さ |
|---|---|
| **参照**: 参照のキー ([各ページの表の「参照先」](README.ja.md#表の読み方)) が、参照先に実在する id を指している。別の種類の id を指したら何であるかを添える | error |
| **参照のキー**: `attaches_to` などのキーが、そのエンティティに書けるものである。参照先がそのキーの種類で定義されている。取り違え (`{lag: vlan-100}`) には正しいキーを示す | error |
| **id の文法**: すべての `id` が [id の文法](types.ja.md#id) に従う | error |
| **id の一意性**: すべての `id` がファイル全体で一意。同じ一覧の中の重複も、別の一覧との重複も誤り | error |
| **推奨プレフィックス** ([types.md](types.ja.md#推奨プレフィックス)) | warning |

## layer1 ([layer1.md](layer1.ja.md))

| 検査 | 重さ |
|---|---|
| `implementation: container` と `role: hypervisor` を一緒に書いていない | error |
| `labels` の値が文字列 | error |
| `labels` のキーが id の文法に従う | warning |
| リンクの `endpoints` がちょうど 2 つ | error |
| MLAG の `nodes` がちょうど 2 つ。`peer_link` が同じ `lag` の一覧にある | error |

## layer2 ([layer2.md](layer2.ja.md))

| 検査 | 重さ |
|---|---|
| **VLAN のポート**: `{interface:}` か `{lag:}` のどちらか一方。同じ VLAN に LAG とそのメンバーを併記していない。同じ VLAN に同じポートを 2 回書いていない | error |
| **VLAN のポート**: LAG のメンバーだけを書いている (`{lag:}` を促す) | warning |
| **VLAN ID**: `vlan_id` が 1〜4094。同じ機器の上で、別の VLAN のエントリが同じ `vlan_id` を使っていない (別の機器での番号の再利用はよい。MLAG に載せた VLAN は両方の機器で数える) | error |
| **bridge**: 同じポートを 2 つの bridge に、同じ bridge に 2 回、LAG とそのメンバーを併記して書いていない | error |
| **bridge**: ポートが 1 つ。ポートの対向も同じ bridge のポート (ルーターのポートを書いた疑い)。ポートが VLAN のポートにもある。LAG のメンバーだけを書いている | warning |
| **VTEP**: 同じ L3 IF を 2 つの VTEP に・1 つの VTEP に 2 回書いていない。1 つの VTEP に同じ機器の L3 IF を 2 つ書いていない。`sources` が複数なら `address` がある。アドレスが決まり、VTEP の間で重複しない | error |
| **VTEP**: `sources` が 1 つで、`address` がその L3 IF の `ip` と食い違う。MLAG のペアの片方だけが VTEP を終端している | warning |
| **VNI**: L2VNI と L3VNI を通して `vni` が重複しない | error |
| **VNI**: L2VNI に参加する機器 (VTEP から導く) に、その VLAN のポートがある | warning |
| **VRF と L3VNI**: VRF の `l3vni` が定義されている。VRF の `l3vni` と L3VNI の `vrf` が互いに一致する | error |
| **サブ IF**: `vlan_id` が 1〜4094。同じ基盤の上でタグが重複しない。`attaches_to` が `{interface:}` か `{lag:}`。タグと `layer2.vlans` の照合は**しない** | error |

## layer3 ([layer3.md](layer3.ja.md))

| 検査 | 重さ |
|---|---|
| **IP アドレス**: `ip` は IPv4、`ipv6` は IPv6 のプレフィックス付きアドレス (`ip` に IPv6 を書くと移動先を示す) | error |
| **所属**: L3 IF の `node` が、`attaches_to` の参照先 (L1 IF・LAG・サブ IF) の機器 (群) に含まれる | error |
| **重複**: 同じ `(node, name)` の L3 IF が 2 つない | error |
| **SVI の紐づけ忘れ**: `name` が VLAN らしい名前 (`Vlan100` など) なのに `attaches_to` がない | warning |
| **ゲートウェイ冗長**: IPv4 の VIP が IF のサブネットに入る (IF に `ip` がなければ warning)。同じ IF・同じ mode・同じアドレスファミリーで `group_id` が重複しない。IPv6 の VIP はリンクローカル。同じ VLAN の anycast gateway の群で `ip` / `ipv6` / `anycast_mac` が一致する | error |
| **トンネル**: `source` が同じ機器の L3 IF。`destination_interface` が別の機器の L3 IF。`destination_ip` と `destination_interface` のちょうど一方がある。外側のアドレスファミリーが `source` と宛先で一致する | error |
| **トンネル**: 対向がトポロジー内なのに、逆向きのトンネルがない | info |
| **Route Target / RD**: [書き方](types.ja.md#route-target-と-route-distinguisher) に従う | error |
| **VLAN の端点**: VLAN のポートの対向の L3 IF の IP が、その VLAN の SVI のサブネットに入る (SVI がなければ検査しない) | info |

## control_plane ([control-plane.md](control-plane.ja.md))

| 検査 | 重さ |
|---|---|
| **端点の形**: トポロジー内の端点は `{node, update_source}` (OSPF / IS-IS は `{node, interface}`)、トポロジー外の相手は `{address, local_as}`。両端ともトポロジー外は書けない | error |
| **インスタンス**: `instance` を省略できるのは、同じ type のインスタンスが 1 つのときだけ。端の機器がインスタンスの `nodes` にある | error |
| **端の機器**: `update_source` / `interface` の機器が端の `node` と一致する。`update_source` の VRF がインスタンスの VRF と一致する | error |
| **通り道 (BGP)**: 両端から導いた通り道が食い違わない。トランスポートのアドレスファミリーが一致する | error |
| **通り道 (OSPF / IS-IS)**: 両端から導いた通り道が食い違わない (ndl_version 2.0 で error にする) | warning |
| **重複**: 同じ両端のセッションが 2 つない | error |
| **AS**: `route_reflector_client` は iBGP のセッションにだけ書ける。同じ機器・同じ VRF で AS は 1 つ。同じ VRF に BGP のインスタンスは 1 つ | error |
| **BFD**: `bfd: true` のセッションの両端が、BFD のタイマーの `nodes` にある | error |
| **AF**: default 以外の VRF のセッションに `l2vpn_evpn` / `vpnv4` / `vpnv6` を書いている | warning |

## 旧構造と廃止キー

読み替えずに、移動先を示す error にするもの。

| 書いたもの | 移動先 |
|---|---|
| `protocols` | `control_plane` ([ADR-0010](../decisions/0010-control-plane-separation.md) D12) |
| `layer3.routing_adjacencies` | `control_plane.routing_neighbors` |
| `protocols.bgp[].role`、`neighbors[].remote_as` / `type` | インスタンスの `nodes[].local_as`。eBGP / iBGP は両端の AS から導く |
| セッションの `attaches_to: {link:}` | 書かない。通り道は `update_source` から導く |
| L3 IF の `vlan` | `attaches_to: {vlan:}` ([ADR-0011](../decisions/0011-layer3-data-plane.md) D10) |
| L3 IF の `fhrp` | `gateway_redundancy` |
| `gateway_redundancy[].protocol` | `gateway_redundancy[].mode` |
| `layer1.links[].mtu` | 書かない。MTU はインターフェースの設定 ([ADR-0020](../decisions/0020-remove-l1-link-mtu.md)) |

## 旧形式

ndl_version 1.x の間は読み替えて受け付け、warning を出すもの。

| 旧形式 | 新しい書き方 |
|---|---|
| L3 IF の `interface: swp51` | `name: swp51` |
| L3 IF の短縮形 `interface: vlan-100` | `name: Vlan100` と `attaches_to: {vlan: vlan-100}` |
| `attaches_to: {interface: <LAG / VLAN / サブ IF の id>}` | `{lag:}` / `{vlan:}` / `{subinterface:}` ([ADR-0001](../decisions/0001-attaches-to.md) D8) |
| VLAN のポートの `node` | 書かない。参照先から導く ([ADR-0013](../decisions/0013-vlan-ports-on-lag.md)) |
| L2VNI の `vtep_source` / `members` | `layer2.vteps` と L2VNI の `vteps` ([ADR-0014](../decisions/drafts/0014-vteps.md)) |
