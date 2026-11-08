# ADR-0010: control plane と data plane の分離 — `control_plane` と `routing_neighbors`

- **Status**: Accepted (2026-11-01 に実装。スキーマ・validator・derive・エクスポーター・fixture・examples。ndl-viz の表示は未対応)
- **Date**: 2026-11-01
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー
- **Pass**: C (ラウンド3。[評価メモ](evaluations/round3-evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0010](drafts/0010-control-plane-separation.md)
- **関連**: ADR-0001 (D8 参照キー。本 ADR で改訂)、ADR-0002 (ID)、ADR-0005 (D1・D3-1・D3-2・D3-3・D4 補則・D6。本 ADR で改訂)、ADR-0006 (endpoints)、
  ADR-0009 (labels)、ADR-0011 (L3 IF・D6 トンネル・D11)、[ADR-0014](0014-vteps.md) (VTEP)、[ADR-0015](0015-declarative-references.md) (Ref)、
  [drafts/0016](drafts/0016-router-id-and-management-interface.md) (router_id。本 ADR で置き場所を改訂)

## Context

### 発端と経緯

「BGP は Layer 的にどこに入るのか」という問いから、NDL YAML が BGP を 2 か所に持つことが分かった (2026-09-18)。

```yaml
layer3:
  routing_adjacencies: [...]   # BGP / OSPF / IS-IS の隣接 (type で区別)
protocols:
  bgp: [{nodes: [{neighbors: [...]}]}]   # BGP のプロセス設定と neighbor
```

2026-09-19 に `control_plane` の新設と `routing_neighbors` への改名を決め、BGP エントリの単位を決めないまま、
layer3 までのデータプレーン (ADR-0011〜0013) を先に確定させるため保留した。

2026-11-01 に ndl-viz の表示がきっかけで再開した。同じ機器の組に `protocols.bgp` の neighbor (両側から向き違いで 1 本ずつ・プロセスごと) と
routing_adjacencies が重なり、1 組に最大 6 本の線が出た (`examples/eveng-evpn-lab-extended.yaml` で 14 組・79 本)。
組ごとに 1 本へまとめると、別々のセッション (underlay の eBGP と EVPN の iBGP) が 1 本の線に混ざった。
ユーザーの要件は「**線 1 本 = セッション 1 本で、両端の IP と AS、eBGP / iBGP、運ぶ AF が分かる**」こと
(ndl-viz は MLNDL に書かれた情報だけを表示し、推定で埋めない)。この要件は RFC 4271 のセッション (2 つのアドレスの間の 1 本の TCP 接続) そのものである。

### 実測で分かった事実

| | 事実 |
|---|---|
| F1 | `protocols` と `routing_adjacencies` を削除してもデータプレーンの記述は壊れない (VRF・VNI・VLAN・VTEP・SVI の IP は残る)。「論理構成図にプロトコル情報を書かない」実務慣行と一致する |
| F2 | 隣接側の機器の組は 3 fixture すべてでプロセス側と 100% 重複し、相互に検証されていない |
| F3 | 同じ機器の組の複数セッション (underlay と overlay) を書き分ける規約がない |
| F4 | `valid_multi_vlan.yaml` で leaf1 が underlay では AS65001、EVPN では AS65000。1 台の BGP スピーカーは (VRF ごとに) 1 つの AS しか持たないのに valid になる |
| F5 | IS-IS は IP を使わない (802.2 LLC に直接載る) のに `layer3` に置かれ、`update_source` を書いてもエラーにならない |
| F6 | OSPF / IS-IS はプロセスを書く場所がない |
| F7 | VRF-lite で VRF ごとに 2 本張るセッションが、`protocols.bgp` では neighbor 1 つにしかならない (VRF を書く場所がない) |
| F8 | fixture に、ループバックを `update_source` にしながら `attaches_to: {link:}` で直結のリンクを指したセッションがある (multihop なのにリンクを指す) |

### 業界モデル

IETF RFC 8349 (`control-plane-protocols` を routing instance の中に置く)、OpenConfig `network-instance` (BGP neighbor は BGP ブロックの中)、
Batfish (`vrfs[] → bgpProcess`、隣接は導出) はいずれも、制御プロトコルを独立したコンテナにまとめ、**インスタンスの単位を VRF とする**。
主要実装も同じで、FRR / Arista EOS / Cisco NX-OS は VRF ごとの `router bgp`、Junos は routing-instances ごとである。

## Terms

| 用語 | 本 ADR での意味 |
|---|---|
| **セッション** | 2 台のスピーカー間の 1 本の関係。BGP では 2 つのアドレスの間の 1 本の TCP 接続 (RFC 4271)。`routing_neighbors` の 1 エントリ = エクスポーターの辺 1 本 |
| **隣接 (adjacency)** | OSPF / IS-IS の正式用語 (RFC 2328、ISO/IEC 10589)。BGP には使わない |
| **ピア / neighbor** | セッションの相手方の 1 台 (RFC 4271 で同義)。構文ではセッションの「端点」と呼ぶ |
| **インスタンス** | 1 つのノードが 1 つの VRF で動かす 1 つのルーティングプロトコルの実体 (RFC 8349)。`control_plane.<proto>[]` の 1 エントリは、ある 1 つの VRF のインスタンスを全ノード分まとめたもの。会話で「BGP プロセス」と呼ぶものと同じ |
| **single-hop / multihop** | セッションの相手が直結したリンクの上にいるか、ルーティングを経由しないと届かないか。構文には書かず、両端の `update_source` の L3 IF から導く (D7) |
| **underlay / overlay** | ファブリックの IP 網と、その上に VXLAN で作る網。BGP セッションの性質ではない。セッションについて言うときは AF と VRF から導く informative な呼び名 (D6) |
| **トランスポートのアドレスファミリー** | セッションを張る IP (TCP の両端) が IPv4 か IPv6 か。セッションが運ぶ経路の種類 (`address_families`、NLRI の AFI/SAFI) とは独立である (RFC 8950 では IPv6 のセッションで IPv4 経路を運ぶ) |

## Decision

### D1. `layer1` / `layer2` / `layer3` はデータプレーンのネットワーク層である

`layerN` は RFC 8345 のネットワーク層 (データプレーン・トポロジー) に番号を振ったもので、OSI 参照モデルの層番号ではない。
制御プロトコルはトランスポートが不揃い (BGP は TCP、OSPF は IP、IS-IS は L2) で、どの `layerN` にも属さない。

| セクション | RFC 8345 の network-type | 表すもの | ADR-0005 D1 の側面 |
|---|---|---|---|
| `layer1` | physical-network | 機器・ポート・ケーブル・LAG | (a) 物理構成図 |
| `layer2` | l2-network (RFC 8944) | ブロードキャストドメイン・VNI・VTEP | (b) 論理構成図 — データプレーン |
| `layer3` | l3-unicast-topology (RFC 8346) | VRF・IP アドレッシング・ゲートウェイ・トンネル | (b) 論理構成図 — データプレーン |
| `control_plane` | (RFC 8349 の control-plane-protocols) | セッションとプロトコルのノードごとの設定 | (b) 論理構成図 — 制御プレーン |

`control_plane` は注釈ではなく規範側の構成子である (BGP セッションを失えば EVPN の到達性が消える。ADR-0005 D4 の軸 4)。
論理構成図に描かないことがあるのは表示の選択である。`control_plane` は任意で、書かない YAML も valid である (F1)。

### D2. トップレベル `control_plane:` を新設し、`protocols:` と `layer3.routing_adjacencies` を廃止する

```yaml
layer1: {nodes, interfaces, links, lag}
layer2: {vlans, vteps, vxlan, subinterfaces}
layer3: {vrfs, interfaces, tunnel_interfaces}
control_plane: {bgp, ospf, isis, bfd, routing_neighbors}   # インスタンスごとの設定 → セッション の順を推奨
```

**配置基準**: 誰と誰が経路・到達性情報を交換するか (セッション) と、そのプロトコルのノードごとの設定は `control_plane` に置く。
データプレーンの要素に帰属する値は、それを配布・交渉するのが制御プロトコルであっても、その要素の属性として置く
(LACP の mode → `layer1.lag`、ゲートウェイの VIP → `layer3.interfaces`、RD / RT → `layer3.vrfs`、VNI の参加 → `layer2.vxlan[].vteps`)。

### D3. セッションは `control_plane.routing_neighbors` に 1 エントリ 1 本で書く

セッションを書ける場所は `routing_neighbors` だけにする (`protocols.bgp[].nodes[].neighbors[]` は廃止)。
名前は、BGP・OSPF・IS-IS のすべてで使われる語 neighbor による (`routing_` は IPv6 ND・LLDP の neighbor と区別するため)。
プロトコルごとに端点の意味が違うので `type` を discriminator とする Tagged Union にし、型名は正式用語に従う (BGP は session、OSPF / IS-IS は adjacency)。
別のエンティティを指すフィールドには ADR-0015 の `Ref` を付ける。

```python
class BgpInsideEndpoint(BaseModel):          # トポロジー内の機器
    model_config = ConfigDict(extra="forbid")
    node: Annotated[str, Ref("layer1.nodes")]
    update_source: Annotated[str, Ref("layer3.interfaces")]   # この側のセッションのアドレスを持つ L3 IF (必須)
    route_reflector_client: bool = False                       # この端が RR クライアント (RFC 4456。neighbor 単位)

class BgpOutsideEndpoint(BaseModel):         # トポロジー外の相手 (IP と AS しか分からない)
    model_config = ConfigDict(extra="forbid")
    address: IPv4Address | IPv6Address       # 相手のホストアドレス (プレフィックス長なし)
    local_as: int                            # 相手自身の AS

BgpEndpoint = Annotated[
    BgpInsideEndpoint | BgpOutsideEndpoint,
    Discriminator(lambda v: "inside" if "node" in v else "outside"),   # node の有無で型を選ぶ
]

class OspfEndpoint(BaseModel):
    node: Annotated[str, Ref("layer1.nodes")]
    interface: Annotated[str, Ref("layer3.interfaces")]     # OSPF は IP 上で hello を送る

class IsisEndpoint(BaseModel):
    node: Annotated[str, Ref("layer1.nodes")]
    interface: Annotated[str, Ref("layer1.interfaces")]     # IS-IS は L2 上で IIH を送る

class BgpSession(BaseModel):
    id: str
    type: Literal["bgp"]
    instance: Annotated[str | None, Ref("control_plane.bgp")] = None
    from_: BgpEndpoint = Field(alias="from")
    to: BgpEndpoint
    address_families: list[AddressFamily] = []
    bfd: bool = False

class OspfAdjacency(BaseModel):
    id: str
    type: Literal["ospf"]
    instance: Annotated[str | None, Ref("control_plane.ospf")] = None
    from_: OspfEndpoint = Field(alias="from")
    to: OspfEndpoint
    area: str                                 # ドット区切り 4 オクテット。`0` は `0.0.0.0` に正規化
    bfd: bool = False

class IsisAdjacency(BaseModel):
    id: str
    type: Literal["isis"]
    instance: Annotated[str | None, Ref("control_plane.isis")] = None
    from_: IsisEndpoint = Field(alias="from")
    to: IsisEndpoint
    level: Literal["level-1", "level-2", "level-all"]   # RFC 9130
    bfd: bool = False

RoutingNeighbor = Annotated[BgpSession | OspfAdjacency | IsisAdjacency, Field(discriminator="type")]
```

- **1 エントリ = 1 セッション**。同じ機器の組に 2 本あれば 2 エントリ書く。セッションには `attaches_to` を書かない (D7)
- **BGP の端点は 2 つの型**で、`node` の有無で決まる型を選ぶ。選び方が決まっているので、どちらの型の誤りか (「`update_source` がない」「`address` と `node` は同時に書けない」) がそのまま返る
- **トポロジー内の端点の `update_source` は必須**。BGP のセッションを書く以上、そのアドレス (または unnumbered) と通り道が必ず決まる。
  `control_plane` を書かない・BGP のセッションを書かない YAML には何も要求しない
- **トポロジー外の端点** (`address` + `local_as`) は、ADR-0011 D6 のトンネルの `destination_ip` と同じく「相手をトポロジーに書いたか」で使い分ける。
  ISP の PE までのケーブルを `layer1` に書くなら相手はトポロジー内であり、相手の L3 IF を 1 つ書いて `{node, update_source}` で指す。
  両端ともトポロジー外にはできない (型ではなく D10 の検査)
- **`local_as` は常に「その端自身の AS」**である。インスタンスの `nodes[].local_as` も、トポロジー外の端点の `local_as` も、書いている対象自身が名乗る AS であり、
  `remote_as` (記述する側から見た相手の AS) のような相対的な値はこのモデルにない。`from` / `to` に優劣はない (eBGP / iBGP は両端の AS の比較で決まる)
- **端点の `address`** は相手のホストアドレスで、`layer2.vteps[].address` (VTEP のアドレス) とは別物
- **`from` / `to` は有向のまま**とする (ADR-0006「L3 との非対称性について」。端ごとに `update_source` 等の非対称な属性を持つ)
- **`instance`** はセッションが属するインスタンスエントリ (D5) を指す。同じ type のエントリが 2 つ以上なら必須、1 つなら省略できるが明示を推奨する
- **`update_source`** は L3 IF の `id` を指す (機器上の `name` では引かない。ADR-0011)。ループバックかどうかは問わない
- **RR** はクライアント側の端点に `route_reflector_client: true` を立てる。RFC 4456 のクライアントの定義も、Cisco / Arista / Juniper / FRR / OpenConfig の設定も
  neighbor 単位である。ノードの属性 (`role: route_reflector`) にすると、RR と non-client の iBGP の相手、階層 RR、同じクラスタの RR どうしを書き分けられない。
  あるノードが RR であることは「クライアントを持つこと」から導く。クラスタ ID が要るときは D5 のノードエントリに加算的に足す
- **OSPF / IS-IS の `interface`** は参照先が違う (OSPF は `layer3.interfaces`、IS-IS は `layer1.interfaces`)。型を分けて `Ref` の ID 空間を取り違えない (F5 の解消)
- OSPF / IS-IS はポイントツーポイント前提である (D12)

### D4. BGP unnumbered

**`update_source` が `ip` も `ipv6` も持たない L3 IF を指す端は unnumbered** である (FRR の `neighbor swp51 interface`。相手の IPv6 リンクローカルは実行時に決まる)。
リンクローカルアドレスを形だけ書く必要はない。L3 IF に `ipv6: fe80::...` を明示すれば、それはそのアドレスで張る numbered のセッションとして扱う。
IPv6 のグローバルアドレスで張るセッションも unnumbered ではない。

アドレスのない L3 IF そのものは unnumbered 用とは限らない (書きかけ・未使用もありうる)。unnumbered とみなすのは、セッションの `update_source` がそれを指すときだけである。
ビューアーは IPv4 を推定せず、IF の名前と「unnumbered」を出す。

ADR-0005 D3-1 の「`update_source` が loopback でない物理 IF を指せば unnumbered」は、IPv6 だけのループバックや SVI 上のセッションで誤判定するため、本 D4 に置き換える。

### D5. BGP のエントリは VRF ごとのインスタンスであり、ノードの設定だけを持つ

`control_plane.bgp[]` の 1 エントリは **1 つの VRF の BGP インスタンス**である (評価メモの D8-a)。エントリはセッションを持たず、ノードごとの設定だけを持つ。

```yaml
control_plane:
  bgp:
    - id: bgp-default                  # vrf 省略 = default VRF
      nodes:
        - {node: spine1, local_as: 65000}
        - {node: leaf1,  local_as: 65001}
    - id: bgp-tenant-a
      vrf: vrf-tenant-a                # Ref("layer3.vrfs")
      nodes:
        - {node: leaf6, local_as: 65006}
  ospf:
    - id: ospf-underlay                # 1 エントリ = 1 OSPF ルーティングドメイン
      nodes: [{node: spine1}]
  isis:
    - id: isis-underlay
      nodes: [{node: spine1, net: 49.0001.0100.0000.0001.00}]
  bfd:
    - {id: bfd-global, min_tx: 300, min_rx: 300, multiplier: 3, nodes: [spine1, leaf1]}
```

- ノードエントリは固有の型 (`BgpInstanceNode` 等) にし、`node` と `bfd[].nodes` に `Ref("layer1.nodes")` を付ける
- 同じ機器が複数の VRF のインスタンスに出るときは、VRF ごとに `local_as` を書く (同じ値でも省略しない。VRF ごとに AS を変える構成もある)
- **AF はセッションにだけ書く**。同じ機器・同じ VRF でも相手ごとに運ぶ AF は違う (spine は leaf とは EVPN、WAN とは IPv4 だけ)。
  ノードにも書けると、どちらが正しいかが決まらない (F4 と同型)。ピアグループのような既定値は持ち込まない
- **eBGP / iBGP は両端の AS から導く**。`BGPNeighbor.type` と `remote_as` は廃止する (F4 の温床。ADR-0005 D3-1 P6 の `remote_as: external | internal` も廃止)。
  両端の AS は、トポロジー内の端は `instance` のエントリの `nodes[]` の `local_as`、トポロジー外の端は端点の `local_as`
- **`BGPProcess.role` (underlay / overlay) は廃止**する (D6)
- 1 VRF に複数の BGP インスタンスを持てる実装 (Junos の logical-systems、IOS-XR の multi-instance) は表現しない

単位を役割 (underlay / overlay) にする案は却下した。1 本の eBGP unnumbered セッションで `ipv4_unicast` と `l2vpn_evpn` を同時に運ぶ構成 (FRR で一般的) を
どのエントリにも入れられず、underlay と overlay が同じ default VRF のエントリ 2 つになって「同一 VRF に 1 エントリ」「同一ノード・同一 VRF で AS は 1 つ」と衝突する
(`evaluations/adr0010/d8-r3/` の C1・C2)。

### D6. underlay / overlay は構文に入れず、AF と VRF から導く

overlay の BGP セッションも overlay (VXLAN トンネル) の中に張るのではなく、**underlay の IP 網の上でループバックどうしに張る TCP 接続**である。
overlay と呼ぶのは運ぶ中身が overlay を作る情報 (EVPN 経路) だからである。セッションには独立した 3 つの性質があり、どれも構文の別の場所で決まる。

| 性質 | 例 | 決まる場所 |
|---|---|---|
| 何を運ぶか | `ipv4_unicast` / `l2vpn_evpn` | セッションの `address_families` |
| どこを通って張るか | single-hop / multihop | 両端の `update_source` の L3 IF から導く (D7) |
| AS の関係 | eBGP / iBGP | 両端の AS (D5) |

「underlay / overlay」は前の 2 つを束ねた呼び名であり、方式名を構文に入れない ADR-0005 D4 補則 問い 4 に従って構文に持ち込まない。
人やツールが知りたいときは次のように導く (informative。導き方は `docs/exporter-cytoscape.md` に書く)。

| セッション | 呼び名 |
|---|---|
| `l2vpn_evpn` / `vpnv4` / `vpnv6` を運ぶ | overlay の情報を運ぶ |
| default VRF のインスタンスで `ipv4_unicast` / `ipv6_unicast` だけを運ぶ | underlay の経路を運ぶ |
| 上の両方を運ぶ (1 本で ipv4 と evpn) | 両方 |
| default 以外の VRF のインスタンスで `ipv4_unicast` / `ipv6_unicast` を運ぶ (VRF-lite の外部接続等) | どちらでもない (テナントの経路) |

`labels: {fabric_role: underlay}` のような分類は採らない。AF から導ける事実の二重表現になり、食い違いが検査されない。labels (ADR-0009) はノードの構成子でもある。

### D7. セッションの通り道は書かず、`update_source` の L3 IF から導く

セッションに `attaches_to` を書く形 (旧 routing_adjacencies の `{link:}`) は廃止する。single-hop の通り道は、`update_source` の L3 IF にすでに書かれた
`attaches_to` (ADR-0011) から導ける。セッションにも書くと同じ事実を 2 か所に書くことになり、F8 の食い違いが検査なしに通る。
また LACP の LAG は機器ごとに 1 つなので、2 台の間の port-channel を `{lag:}` で指すとどちらの LAG か決まらない。
これは ADR-0005 D6 (`node` は基盤から導き、書かない) と同じ考え方である。

| 両端の `update_source` の L3 IF | その `attaches_to` | 通り道 (`transport_link`) |
|---|---|---|
| 物理 IF の L3 IF (/31・unnumbered) | `{interface: <L1 IF>}` | 両端の L1 IF を結ぶリンク。single-hop |
| port-channel の L3 IF | `{lag: <LAG>}` | 両端の LAG (メンバーどうしがリンクでつながる)。single-hop |
| サブ IF の L3 IF | `{subinterface: <サブ IF>}` | サブ IF の基盤 (L1 IF / LAG) について上と同じ |
| SVI | `{vlan: <VLAN>}` | 決めない (VLAN は複数のリンク・LAG にまたがりうる)。multihop と同じ扱い |
| ループバック・dummy 等 | なし (`unattached`) | なし。multihop |
| トポロジー外の端がある | — | なし |

- single-hop / multihop は構文に出さない。`ebgp-multihop` の設定は書かない (ADR-0005 D3-2。下流ツールが導出結果から判断する)
- 導出は `derive.py` の 1 つの関数で行い、validator (D10 の通り道の検査) とエクスポーター (D11) が共有する
- SVI 上のセッション (vPC ペア間の iBGP 等) が peer-link の LAG の上を流れることは、VLAN のポートからたどれば分かる (ADR-0013 D7) が、セッションの通り道としては出さない

> **ADR-0018 で拡張** (2026-11-03): 両端が同じ `layer2.bridges` に届けば `{bridge:}`、両端が対になるトンネル IF なら `{tunnel: [<from>, <to>]}` を通り道とする。
> OSPF / IS-IS にも同じ規則で通り道を導く (食い違いは 1.x の間 warning。[ADR-0025](0025-end-grace-for-old-forms.md) D2 で error に繰り上げた)。食い違いのメッセージも改める (2026-11-03 実装)。

### D8. OSPF / IS-IS

- OSPF / IS-IS も D5 と同じくインスタンスのエントリ (`control_plane.ospf` / `isis`) とセッション (`routing_neighbors` の `ospf` / `isis`) に分ける
- **ポイントツーポイント前提**とする。マルチアクセスのセグメント (OSPF の DR / BDR、IS-IS の DIS) では DROther どうしが 2-Way 止まりで Full にならず (RFC 2328 §10.4)、
  N 台を 2 端点の組に展開すると意味が壊れる。DC ファブリックでは Ethernet 上でも point-to-point で運用するのが一般的で (RFC 7938)、当面の実害は小さい
- OSPF の `area` はドット区切り 4 オクテットとし、`0` は `0.0.0.0` に正規化する
- `router_id` は D9 のとおり ADR-0016 に委ねる。IS-IS の主識別子は NET の system-id である

### D9. `router_id` は ADR-0016 に委ね、置き場所は `control_plane` のノードエントリとする

`router_id` の形式 (ドット区切り 4 オクテット・非ゼロ)、L3 IF の IP との一致を要求しないこと (RFC 6286)、一意性の検査は ADR-0016 で決める。
置き場所は `control_plane.bgp[].nodes[].router_id` と `control_plane.ospf[].nodes[].router_id` である。D5 で BGP のエントリが VRF ごとのインスタンスになるので、
VRF ごとの router-id はエントリごとに書ける。ADR-0016 が `protocols.bgp[]` に先行して置く場合は、本 ADR の実装時に `control_plane` へ移す。

### D10. 検査

参照先の存在 (`instance` / `node` / `update_source` / `interface` / `vrf` / `bfd[].nodes`) は `Ref` の汎用検査で付く (ADR-0015)。
端点の形 (D3 の 2 つの型) は型で弾く。手で書くのはネットワークとしての意味の検査だけである。

| チェック | Severity | 根拠 |
|---|---|---|
| `instance` の省略時、同じ type のエントリがちょうど 1 つか | error | D3 |
| トポロジー内の端の `node` が、`instance` のエントリの `nodes` にあるか | error | D5 (AS を引く先) |
| BGP の `update_source`、OSPF / IS-IS の `interface` の参照先の `node` が、その端の `node` と一致するか | error | D3 (ADR-0011 D9 と同じ形) |
| `update_source` の L3 IF の `vrf` が、`instance` のエントリの `vrf` と一致するか (省略はどちらも default) | error | VRF-lite の書き間違いを防ぐ |
| 両端ともトポロジー外でないか | error | D3 |
| 両端から導いた通り道が食い違わないか (片方が直結の L1 IF / LAG を指すのに、もう片方がその対向でない。SVI は両端が同じ VLAN か) | error | D7。食い違えば TCP が成立しない |
| 両端の**トランスポートのアドレスファミリー** (IPv4 / IPv6) が一致するか (トポロジー外の端は `address`。unnumbered の端は検査しない) | error | 異なる AF の TCP は成立しない |
| 同じインスタンスで、`update_source` の L3 IF の id の組 (順序を問わない) が同じセッションが 2 つないか | error | 二重定義 |
| `route_reflector_client: true` のセッションの両端の AS が同じか | error | RR は iBGP の仕組み (RFC 4456) |
| 同一ノード・同一 VRF で、BGP エントリの `local_as` が一意か | error | F4 |
| 同一 VRF に BGP エントリが 2 つ以上ないか | error | D5 |
| default 以外の VRF のインスタンスのセッションに `l2vpn_evpn` / `vpnv4` / `vpnv6` を書いていないか | warning (`--strict` で error) | これらの経路は default VRF のセッションで運ぶのが通常 (RFC 4364 / RFC 7432)。例外の構成を言い切れない |
| `bfd: true` のセッションの両端ノードが、いずれかの `control_plane.bfd[].nodes` に含まれるか | error | 矛盾が黙って通るのを防ぐ |
| `routing_neighbors[].id` の推奨プレフィックス (`bgp-peer-` / `ospf-adj-` / `isis-adj-`) | warning | ADR-0002 D7 |
| 旧キー (`protocols`、`layer3.routing_adjacencies`、`BGPProcess.role`、`neighbors[].type` / `remote_as`) | error | D12 (移動先・代わりの書き方を示す) |

`router_id` の検査は ADR-0016 で定義する。

### D11. エクスポーターの出力

ndl-viz は推定しないので、エクスポーターが参照をたどって値を決めてから出す。値は `derive.py` の 1 つの関数 (例: `routing_session_views(topology)`) で求め、
validator と共有する。validator が見ている値と ndl-viz に渡る値が一致する。

**機器のデータの `bgp_sessions`**: その機器の BGP セッションをすべて入れる (トンネルの `tunnels` と同じ形)。相手はトポロジー内なら `node`、外なら `address` で表す。

**セッションの辺**: 両端がトポロジー内のセッションは、機器どうしの辺としても出す (1 セッション = 1 辺)。

```json
{"id": "bgp-peer-spine1-leaf1", "type": "routing_neighbor", "protocol": "bgp",
 "source": "spine1", "target": "leaf1",
 "instance": "bgp-default", "vrf": "vrf-default",
 "from": {"node": "spine1", "l3_interface": "spine1-e1-1-l3", "interface_name": "Ethernet1/1", "ip": "10.0.0.0/31", "local_as": 65000},
 "to":   {"node": "leaf1",  "l3_interface": "leaf1-e1-1-l3",  "interface_name": "Ethernet1/1", "ip": "10.0.0.1/31", "local_as": 65001},
 "bgp_type": "ebgp",
 "address_families": ["ipv4_unicast"],
 "transport_link": {"link": "link-spine1-leaf1"},
 "bfd": false}
```

| 値 | 決まり方 |
|---|---|
| 両端の IP | `update_source` の L3 IF の `ip` / `ipv6`。アドレスがなければ出さず `unnumbered: true` (D4) |
| 両端の AS | D5 |
| `bgp_type` (ebgp / ibgp) | 両端の AS が同じかどうか (RFC 4271 の定義)。現行の `bgp_session` 辺と同じフィールド名を引き継ぐ |
| `interface_name` | `update_source` の L3 IF の機器上の名前 (`name`) |
| `transport_link` | D7 の通り道。`{link:}` か `{lag:}`。multihop・SVI では出さない。導いた値であり、YAML の `attaches_to` ではない |
| `vrf` | `instance` のエントリの `vrf` (省略なら default) |

現行の `routing_adjacency` 辺と `bgp_session` 辺 (1 組に最大 6 本) は、この 1 種類に置き換わる。OSPF / IS-IS も同じ形で、端点は `interface` を出す。
形の詳細は実装時に `docs/exporter-cytoscape.md` に書く。運用者が線で見たい情報の順 (両端 IP → AS と eBGP / iBGP → AF → router-id → BFD → RR 関係) をビューアーの表示の目安にする。

### D12. ID 命名・移行・範囲外

**ID**: ADR-0002 D7 の推奨プレフィックス `bgp-peer-` / `ospf-adj-` / `isis-adj-` は変えない。プレフィックス以外は自由で、次を推奨する。
区別の語はノード対の後ろ (末尾) に付ける (`bgp-peer-<A>-<B>` の形を崩さない)。

| 状況 | 例 |
|---|---|
| 1 本のセッション (複数 AF を運ぶものも) | `bgp-peer-spine1-leaf1` |
| default 以外の VRF のセッション | `bgp-peer-leaf6-wan-rtr-tenant-a` (VRF ID から `vrf-` を除いた部分) |
| 同じインスタンスで同じ組の 2 本目 | 用途の語を付ける: `-overlay` / `-backup` / `-mgmt` 等 (`bgp-peer-spine1-leaf1-overlay`)。運ぶ AF の名前は、1 本で複数を運ぶセッションと紛れるので推奨しない |

ID は人が読むための名前であり、両端の機器は `from` / `to` から引く (ノード ID がハイフンを含むと、ID からはノード対と接尾辞の境目が読めない)。

**移行**: `mlndl` は未リリース (0.1.0) で外部利用者はいないため、移行期間を設けず置き換える。`ndl_version` は `1.0` のまま (1.0 は Phase 1〜2 の間は策定中であり、
外部利用者がいない限り 1.0 の範囲内で破壊的変更を許容する。Phase 3 以降はメジャーバージョンの更新を必須とする)。

> **改訂 (2026-11-07)**: Phase の札をやめた ([ADR-0005](0005-mlndl-expressive-scope.md) D5 の改訂) ので、上の「Phase 3 以降」を次のように置き換える。
> 最初のリリースは 1.0 (`ndl_version: "1.0"`) とし、今進めている整理が終わってから出す。それまでは 1.0 の範囲内で破壊的な変更を許す。
> 1.0 をリリースした後は、破壊的な変更にメジャーバージョンの更新を必須とする。

旧キーは読み替えず、移動先・代わりの書き方を示す **error** をまとめて返す (1 件目で打ち切らない)。セッションの通り道は旧 `attaches_to` から機械的に移せない (F8) ためである。

```
protocols は control_plane に移動しました (ADR-0010)
layer3.routing_adjacencies は control_plane.routing_neighbors に移動しました。attaches_to は書かず、update_source から導きます (ADR-0010)
protocols.bgp[].role は廃止しました。underlay / overlay はセッションの address_families から導きます (ADR-0010)
neighbors[].remote_as / type は廃止しました。各機器の AS をインスタンスの nodes[].local_as に書きます (ADR-0010)
```

**範囲外** (書く場所を作らない。必要になれば ADR で線引きしてから加算する):

- per-neighbor の `local-as` / `replace-as`、BGP Confederation (RFC 5065)、`allowas-in` を前提とする AS 設計
- BGP ポリシー (route-map / prefix-list / community)、ピアグループ・テンプレート、graceful restart、TCP MD5 / TCP-AO (RFC 5925)、add-path (RFC 7911)、BGP role (RFC 9234)、
  `next-hop-unchanged`・route server (RFC 7947) などの振る舞いの設定 (ADR-0005 D3-2)。人向けの注記は L1 ノードの `role` に書ける
- multihop のセッションが通る underlay の経路 (ECMP で複数のリンク)。Phase 3 で `carried_by` 等を検討
- OSPF / IS-IS のマルチアクセスのセグメント (D8)、micro-BFD (RFC 7130)
- FRR の unnumbered の `v6only` とそうでないモードの区別 (D4)
- セッションの状態 (Established 等)。記述ではなく実データであり、ビューアーが外部のデータを重ねる

## Consequences

### 良い影響

- 二重表現 (F2) が構造的に解消する。セッションを書ける場所は 1 か所で、通り道も `update_source` からしか決まらない (F8 が起きない)
- F4 のような AS の矛盾が検査で見つかる。F5 (IS-IS に `update_source`)・F6・F7 も解消する
- 「プロトコル抜きの論理構成図」が `control_plane` を 1 キー落とすだけで得られる (F1)
- ビューアーがセッションを 1 本ずつ描ける。両端の IP・AS、eBGP / iBGP、AF、VRF、通り道がどれも参照をたどるだけで決まる
  (試し書き 7 ケースと移行 4 本で確認。決まらないのは unnumbered の両端 IP だけで、出さないのが正しい)
- 記述が短くなる。`examples/eveng-evpn-lab-extended.yaml` の制御プレーン部分は 159 行が約 55 行、`examples/eveng-evpn-lab.yaml` は 92 行が約 45 行

### 悪い影響 / トレードオフ

- **破壊的変更**。3 fixture (`valid_full_dc` / `valid_multi_vlan` / `valid_multisite_wan`)、2 examples、`tests/test_phase2.py` などの書き換えが要る
- **fixture は単純な移植では直らない**。`valid_multi_vlan.yaml` は F4 を直すため AS 設計を決め直す。`valid_full_dc.yaml` と `valid_multi_vlan.yaml` は underlay を
  ループバックどうしで張りながらリンクを指していた (F8) ので、underlay を single-hop にするなら /31 の L3 IF を足す (`evaluations/adr0010/passc/`)
- EVPN の制御プレーンは次の 3 通りに書け、本 ADR は推奨順を決めない。RFC 7432 / 8365 は BGP の運び方 (iBGP / eBGP、1 本か複数か) を規定していない
  - 1 本で複数 AF を運ぶ: アドレスのない L3 IF を `update_source` にし、`[ipv4_unicast, l2vpn_evpn]` を 1 本に書く (FRR の `neighbor swp1 interface` 系)
  - underlay と overlay を分ける: /31 の L3 IF どうしで `[ipv4_unicast]`、ループバックどうしの eBGP multihop で `[l2vpn_evpn]`
    (Arista EOS や Cisco NX-OS の設計ガイドが紹介する構成。`examples/eveng-evpn-lab.yaml` もこの形)
  - IGP + iBGP RR: OSPF / IS-IS を `control_plane` に書き、EVPN は iBGP の RR とクライアントで (Cisco NX-OS の構成ガイドなどで広く使われる)
- 管理外のピアの書き方が 2 通りある (相手の機器をトポロジーに書くか、`address` + `local_as` か)。トンネルと同じ使い分けである
- SVI 上のセッションは通り道が出ない (D7)。multihop のセッションが通る経路も表現できない
- `update_source` を必須にしたので、「セッションがあることだけ」を先に書く書きかけの状態は表せない

### 影響を受けるコンポーネント

- スキーマ: `src/mlndl/schema/control_plane.py` を新設、`protocols.py` を廃止、`layer3.py` から `RoutingAdjacency` を削除、`topology.py`。
  `BgpSession` / `OspfAdjacency` / `IsisAdjacency` は `isinstance` 分岐用に公開する
- 参照の宣言: `refs.py` の `COLLECTION_LABELS` に `control_plane.bgp` / `ospf` / `isis` / `routing_neighbors`。`tests/test_refs.py` の `SCHEMA_MODULES` に `control_plane`、
  `KEYED_REFERENCES` から routing_adjacencies の行を外す
- 導出: `src/mlndl/derive.py` にセッションの値 (両端の IP・AS・eBGP / iBGP・VRF・通り道) を求める関数
- バリデーター: `src/mlndl/validator.py` (routing_adjacencies の検証と `_validate_protocols` を D10 に置き換え)
- エクスポーター: `src/mlndl/exporter/cytoscape.py` (D11)、`docs/exporter-cytoscape.md`
- ndl-viz: BGP の線をセッションごとにし、中央に eBGP / iBGP と AF、両端に IP と AS を出す。絞り込みは AF (と VRF) で行う。トポロジー外の相手は機器カードの中に出す
- サンプル: `tests/fixtures/valid_full_dc.yaml` / `valid_multi_vlan.yaml` / `valid_multisite_wan.yaml`、`examples/eveng-evpn-lab.yaml` / `eveng-evpn-lab-extended.yaml`
  (`role: route_server` 等は L1 ノードの `role` の注記に移す)
- テスト: `tests/test_phase2.py`、`tests/test_validation_severity.py`
- 文書: `CLAUDE.md` (YAML 例・バリデーション表・attaches_to の表)、ADR-0001 (D8)、ADR-0005 (D1・D3-1)、drafts/0016 (D2)。いずれも本 ADR の確定と同時に改訂した

## Alternatives Considered

- **現状維持** (routing_adjacencies + protocols): 却下 — F2〜F8 がすべて残り、ndl-viz の重複描画 (最大 6 本) の原因そのもの
- **セッションを `protocols` 配下へ移すだけ**: `protocols` という補集合的な名前 (LACP も 802.1Q もプロトコルなのに入らない) が残る
- **RFC 8345 の `networks:` リストに一般化**: 却下 — 型が退化する。RFC 8345 との対応はエクスポーターで担保する (ADR-0005 Alt-4)
- **OpenConfig 方式 (`layer3.vrfs[].protocols[]`) / インスタンスの中にセッション (`control_plane.bgp[].sessions[]`)**: 却下 — 所属が構造で決まる利点はあるが、
  プロトコル横断でセッションを列挙する用途 (1 セッション = 1 辺) で全エントリを巡回することになる。フラット + `instance` 参照で同じ区別が得られる
- **セッションを書かず各機器の neighbor 設定から導く (Batfish 方式)**: 却下 — 記述言語として「意図したセッション」を書けない。
  unnumbered・multihop・SVI 上のセッションは neighbor 設定だけでは両端の組が決まらない
- **BGP エントリを役割 (`role: underlay | overlay`) 単位にする**: 却下 — D5
- **underlay / overlay を `labels: {fabric_role}` で書く**: 却下 — D6
- **セッションに `attaches_to: {link:} | {lag:}` を書く**: 却下 — D7
- **端点を 1 つの型にまとめ `model_validator` で 2 つの形を区別する**: Pass B 時点の案。`node` の有無で型を選ぶ Union にすれば、選び方が決まったうえで型ごとのエラーが返るので、そちらを採った
- **`update_source` を任意にする**: 却下 — 両端の IP と通り道が決まらない線ができる。BGP のセッションを書く以上、必須にしてもユーザーの負担は小さい
- **RR をノードの `role: route_reflector` で書く**: 却下 — D3 (neighbor 単位でしか書き分けられない構成がある)
- **管理外のピアは必ず `layer1` に機器を置き L3 IF を書く**: 却下 — IP と AS しか分からない相手のために形だけの機器・IF・リンクを作ることになる (`evaluations/adr0010/d8-r3/C6`)
- **トポロジー外の相手の AS を `peer_as` / `remote_as` と呼ぶ**: 却下 — 「その端自身の AS」なので `local_as` にそろえる (D3)
- **インスタンスを指すフィールドを `process`**: 却下 — OS のプロセスと紛れる。RFC 8349 は routing instance
- **`update_source` を `local_address` (OpenConfig) / `source` に**: 却下 — `local_address` はアドレス前提で unnumbered と合わない。`source` はトンネルの `source` と紛れる
- **unnumbered を端点の `unnumbered: true` か、L1 IF を指す `update_source` で表す**: 却下 — `update_source` の参照先が 2 種類になる
- **single-hop / multihop、`ebgp-multihop` をセッションのフィールドにする**: 却下 — ADR-0005 問い 4。D7 で導ける
- **AF をインスタンスのノードにも書く (ピアグループ的な既定値)**: 却下 — D5
- **エクスポーターのフィールド名**: 通り道の `path` は AS_PATH と紛れる。トポロジー外のセッションを `external_bgp_sessions` / `off_topology_bgp_sessions` という
  別のキーにする案は、external が eBGP と紛れる・意味が伝わりにくい。トンネルと同じく機器の `bgp_sessions` にすべて入れる形にした
- **`bgp_type` を `session_type` に改名**: 却下 — 値域 (ebgp / ibgp) は BGP 固有で、現行出力との連続性もある
- **命名 `layer4` / `plane`**: 却下 — トランスポートが不揃い。RFC 7426 の plane と underlay / overlay は別の概念

## 未解決事項

1. `bfd: bool` を BFD プロファイルの参照 (`bfd: <id>`) に変えるか (RFC 9127)。micro-BFD とあわせて別 ADR で扱う
2. `AddressFamily` の値域 (`ipv4_unicast | ipv6_unicast | l2vpn_evpn | vpnv4 | vpnv6`)。RFC 8950 (IPv6 ネクストホップで IPv4 経路) は別 AF にせず付記で足りる見込み。
   `ipv4_labeled_unicast` (RFC 8277) 等も合わせて扱う。表示名 (`L2VPN EVPN` 等) との対応はエクスポーター側に置く
3. OSPF の `area` をセッション側に置くか、インスタンスのノード側に置くか (同じ area を共有するセッションが多いと冗長)
4. `address_families` の省略 (未指定) と空リスト (何も運ばない) を区別するか

## References

- 評価メモ: [evaluations/round3-evaluation.md](evaluations/round3-evaluation.md) (Pass B と Pass C の結果)
- 試し書き: [evaluations/adr0010/](evaluations/adr0010/README.md) — `layering/`・`draft-r1-syntax/` (保留前)、`d8-r3/` (D8 の比較)、`r3/` (r3 の構文)、`passc/` (fixture と examples の移行・誤りの検出)
- RFC 4271 (BGP-4) / RFC 6286 (BGP Identifier) / RFC 4760 (MP-BGP) / RFC 4456 (Route Reflection) / RFC 5065 (Confederation) / RFC 7947 (Route Server) / RFC 8950
- RFC 2328 (OSPFv2) §10.4 / RFC 5340 (OSPFv3) / ISO/IEC 10589 (IS-IS) / RFC 1195 / RFC 9130 (`ietf-isis`)
- RFC 5881 / RFC 5883 / RFC 7130 / RFC 9127 (BFD)
- RFC 4364 / RFC 7432 / RFC 8365 (EVPN) / RFC 7938 (BGP in Large-Scale Data Centers)
- RFC 7426 / RFC 8345・8346・8944 / RFC 8349 (`ietf-routing`) / OpenConfig `openconfig-network-instance`
