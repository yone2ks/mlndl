# ADR-0010: control plane と data plane の分離 — `control_plane` と `routing_neighbors`

- **Status**: Draft — **保留中 (2026-09-20)**。再開時は下の「保留時点の状態」から読むこと
- **Date**: 2026-09-19
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **Pass**: A r2 (初回策定 → 5 エージェントレビュー反映。差分は末尾「r1 からの変更」)
- **関連**: ADR-0001 (attaches_to), ADR-0002 (ID 命名 D2・D7), ADR-0005 (表現スコープ D1・D3-1・D3-3), ADR-0006 (endpoints), ADR-0009 (labels)
- **吸収する課題**: 「案P」(BGP 隣接の二重表現)

## 保留時点の状態 (2026-09-20)

layer3 までのデータプレーンの表現力を先に確定させるため、制御プレーンの検討はここで中断した。

**ユーザー決定済み** (2026-09-19):

1. トップレベル `protocols:` を廃止し `control_plane:` を新設する (D2)
2. `layer3.routing_adjacencies` を `control_plane.routing_neighbors` に移動・改名する (D3)

**未決 (再開時にまずユーザー判断を仰ぐ)**:

- **D8**: BGP エントリの単位を VRF ごとのインスタンス (D8-a、推奨) にするか、underlay / overlay の役割 (D8-b) にするか。
  前ラウンドで保留した「address-family と role のどちらを正規にするか」と同じ問い

**r2 の状態**: 5 エージェントのレビュー (spec-architect / linguist / dsl-designer / network-tech-reviewer / example-author) を
反映済み。r2 自体はまだレビューを通していない。再開時は D8 の決定後、r2 を 5 エージェントで再レビューしてから Pass C に進む。

**実装への影響**: スキーマ・validator・fixture は**一切変更していない**。現行の `layer3.routing_adjacencies` と
`protocols` はそのまま動作し、F2〜F6 の問題も残っている。

### 位置づけ

本 ADR は **ADR-0005 の部分改訂**であり、置き換え (supersede) ではない。ADR-0005 の三側面・D4 判定フレームワーク・スコープ確定は維持する。
改訂するのは以下に限る。

| 改訂対象 | 内容 |
|---|---|
| ADR-0005 D1 | 「(b) 論理構成図」の内部を、データプレーン (`layer2` / `layer3`) と制御プレーン (`control_plane`) に分けて位置づける |
| ADR-0005 D3-1 (b) | `layer3.routing_adjacencies` 行と `protocols.*` 行を `control_plane.*` に置き換える |
| ADR-0005 D3-1 (c) | `routing_adjacencies[].attaches_to` 行を `routing_neighbors[].attaches_to` に置き換える |
| ADR-0005 D3-1 (P6) | `remote_as: <ASN> \| external \| internal` を廃止する (D4) |
| ADR-0002 D7 | 備考のみ (プレフィックスは変更しない。D7 参照) |

**ADR-0006 は改訂しない。** ADR-0006「L3 との非対称性について」の判断 (L3 の隣接は `from`/`to` の有向を維持する) をそのまま引き継ぐ。

前回ラウンドで構想した ADR-0005 の再設計 (redistribute / EVPN advertise フラグを D3-2 へ移す、スコープの原理文の追加) は**本 ADR の範囲外**であり、別途 `drafts/0005v2-*` で扱う。

## Terms

| 用語 | 本 ADR での意味 |
|---|---|
| **セッション** | 2 台のスピーカー間の 1 本の関係。プロトコルを問わない抽象概念 (BGP の Established、OSPF の Full、IS-IS の Up) |
| **隣接 (adjacency)** | OSPF / IS-IS の正式用語 (RFC 2328 §1.2 / §10、ISO/IEC 10589)。BGP には使わない |
| **ピア / neighbor** | 相手方の 1 台。RFC 4271 §1.1 で peer と neighbor は同義 |
| **インスタンス** | 1 台のノード上の、1 つの VRF における 1 つのルーティングプロトコルの実行単位 (RFC 8349 の routing instance 内の control-plane-protocol)。YAML では `control_plane.<proto>[]` の 1 エントリがノード群のインスタンスをまとめる |

## Context

### 発端

> 多くの論理構成図ではプロトコル情報までは含んでないんだよね。bgp とかは Layer 的にはどこに入るのかね?

現行の NDL YAML は BGP 情報を 2 箇所に持つ。

```yaml
layer3:
  routing_adjacencies: [...]   # BGP / OSPF / IS-IS の隣接 (type で区別)
protocols:
  bgp: [{nodes: [{neighbors: [...]}]}]   # BGP のプロセス設定と neighbor
```

### 実測で判明した事実 (2026-09-18〜19)

**F1. プロトコル情報を削除しても、データプレーンの記述は壊れない。**
`valid_full_dc.yaml` から `protocols:` と `layer3.routing_adjacencies` を丸ごと削除した YAML は
`python -m mlndl validate` をエラーなしで通過した。VRF / L2VNI / L3VNI / VLAN / VTEP source / SVI の IP は
すべて残る。消えるのは AS 番号・RR 階層・address-family・BFD 適用範囲・overlay セッション。
「論理構成図にはプロトコル情報を書かない」という実務慣行は、mlndl の構造でもそのまま成立する。

> この結果は現行 validator の検査範囲にも依存する (削除側への逆参照を検査していない)。
> 構造上の根拠は下記「業界モデル」の IETF / OpenConfig / Batfish の一致にある。

**F2. 二重表現は全 fixture に実在し、相互検証されていない。**
`routing_adjacencies` を持つ 3 fixture すべてで、隣接側のノード対はプロセス側にも 100% 重複して現れる。
`validator.py` の `_validate_protocols` と routing_adjacencies 検証は独立しており、相互チェックはない。

| fixture | 隣接側の対 | BGP 側の対 | 重複 |
|---|---|---|---|
| `valid_full_dc.yaml` | 4 | 4 | 4 |
| `valid_multi_vlan.yaml` | 6 | 6 | 6 |
| `valid_multisite_wan.yaml` | 10 | 10 | 10 |

**F3. 同一ノード対の複数セッションを書き分ける規約がない。**
`valid_full_dc.yaml` には BGP セッションが実際には 8 本ある (eBGP underlay 4 + iBGP EVPN overlay 4) が、
`routing_adjacencies` は 4 件しかない。命名規約 `bgp-peer-<A>-<B>` (ADR-0002 D2) はノード対だけから ID を作るため、
同じノード対の 2 本目のセッションは同じ ID になってしまう。`bgp-peer-spine1-leaf1` が underlay と overlay の
どちらを指すのかは仕様に定義がない。

**F4. 現行 fixture が AS の矛盾を含んだまま valid になっている。**

```
bgp-underlay (eBGP): spine1(65000) -> leaf1  remote_as=65001
bgp-evpn     (iBGP): spine1(65000) -> leaf1  remote_as=65000   ← leaf1 が 65000 と 65001 の両方
```

1 台の BGP スピーカーは (VRF ごとに) 1 つの AS しか持たない。`local-as` 等の例外設定なしにこの構成は成立しない。
プロセスごとに独立に検証しているため `validate` は通る。

**F5. IS-IS を `layer3` に置くのは技術的に誤りである。**
IS-IS は IP を一切使わない。IEEE 802 LAN 上では 802.2 LLC (DSAP = SSAP = 0xFE) に直接載り、
PDU の先頭オクテットは Intradomain Routeing Protocol Discriminator 0x83 である (ISO/IEC 10589)。
RFC 1195 で IP 経路を運ぶようになってもトランスポートは L2 のまま。
現行スキーマでは `type: isis` の隣接に BGP 概念の `update_source` を書いてもエラーにならず
(`../evaluations/adr0010/layering/R3_isis_attempt.yaml` で実測)、IS-IS に必須の NET と level はどこにも書けない。
**構文的には通るが意味論的に空**である。

**F6. OSPF / IS-IS はプロセスを書く場所がない。**
`RoutingAdjacency.type` は `bgp | ospf | isis` を受けるが、`Protocols` は `bfd` / `bgp` しか持たない。

### `layer1/2/3` は OSI の層番号ではない

RFC 8345 は supporting-network による積み重ねを "layer" と呼ぶ (§1 / §4.1) が、番号は振らない。
network-types は `physical-network` / `l2-network` (RFC 8944) / `l3-unicast-topology` (RFC 8346) のような種別名である。
mlndl の `layerN` は RFC 8345 のネットワーク層に番号を振ったものであり、OSI 参照モデルの層番号ではない。
この定義がどこにも書かれていないことが、「BGP は何層か」という問いを生む直接の原因になっている。

各プロトコルの実際のスタック位置 (RFC は原文照合済み):

| プロトコル | 直接載る層 | 出典 |
|---|---|---|
| BGP-4 | TCP/179 (IPv4 / IPv6 どちらでも) | RFC 4271 §3 |
| OSPFv2 | IP protocol 89 | RFC 2328 §4.3 / App. A.1 |
| OSPFv3 | IPv6 Next Header 89 | RFC 5340 App. A.1 |
| IS-IS | 802.2 LLC 直載り。IP を使わない | ISO/IEC 10589 (有償規格のため節番号は未照合) / RFC 1195 |
| BFD | UDP/3784 (single-hop) / 4784 (multi-hop) / 6784 (micro-BFD, LAG メンバー) | RFC 5881 §4 / RFC 5883 §5 / RFC 7130 §2.2 |
| VRRPv3 | IP protocol 112 / IPv6 Next Header 112 | RFC 5798 §5.1.1.4 / §5.1.2.4 |
| LACP | Slow Protocols (EtherType 0x8809) | IEEE Std 802.3 Annex 57A / IEEE 802.1AX (未照合) |

「ルーティングプロトコル = L3」という対応は、OSPF 以外では成立しない。

### 業界モデル

- **IETF RFC 8349 (`ietf-routing`)**: `control-plane-protocols/control-plane-protocol[type, name]` の 1 コンテナにまとめる。レイヤー概念はない
- **OpenConfig `openconfig-network-instance`**: `network-instances/network-instance/protocols/protocol[identifier, name]`。BGP neighbor は BGP ブロックの中にしかない
- **Batfish**: `vrfs[] → bgpProcess / ospfProcesses / isisProcess`。隣接は宣言ではなく導出値
- **RFC 7426**: control plane / data plane / management plane の三分を定義

3 者は独立に「制御プロトコルは独立したコンテナにまとめ、隣接はその中にだけ書く」に到達している。
mlndl はこの**独立コンテナ化の原則**を採る。一方、VRF の中へのネストは採らず、グローバル一意 ID による
フラット参照を維持する (ADR-0005 Alt-4、および Alternatives の案E)。

## Decision

### D1. `layer1` / `layer2` / `layer3` はデータプレーンのネットワーク層である

`layerN` は **RFC 8345 のネットワーク層 (データプレーン・トポロジー)** を指し、OSI 参照モデルの層番号ではない。

| セクション | 対応する RFC 8345 network-type | 表すもの | ADR-0005 D1 の側面 |
|---|---|---|---|
| `layer1` | physical-network | 機器・ポート・ケーブル・LAG | (a) 物理構成図 |
| `layer2` | l2-network (RFC 8944) | ブロードキャストドメイン・VNI | (b) 論理構成図 — データプレーン |
| `layer3` | l3-unicast-topology (RFC 8346) | VRF・IP アドレッシング・ゲートウェイ | (b) 論理構成図 — データプレーン |
| `control_plane` | (RFC 8349 の control-plane-protocols) | ピア関係とプロトコルの設定 | (b) 論理構成図 — 制御プレーン |

この定義を CLAUDE.md・スキーマの docstring・ADR-0005 D1 に明記する。

`control_plane` は注釈ではなく**規範側**の構成子である。ADR-0005 D4 の軸 4 (blast_radius への影響) で明らかに Yes になる
(BGP セッションを失えば EVPN の到達性が消える)。「論理構成図に描かないことがある」のは表示の選択であって、
記述の重要度が低いことを意味しない。

### D2. トップレベル `control_plane:` を新設し、`protocols:` を廃止する

```yaml
layer1: {nodes, interfaces, links, lag}        # data plane
layer2: {vlans, vxlan}                          # data plane
layer3: {vrfs, interfaces}                      # data plane (routing_adjacencies を除去)
control_plane: {bgp, ospf, isis, bfd, routing_neighbors}
```

名前の根拠: RFC 7426 に内包的定義がある。`protocols` は「LACP も 802.1Q も VRRP もプロトコルなのに入っていない」という
補集合的な定義しか持たなかった。`layer4` は BGP (TCP 上) / OSPF (IP 直上) / IS-IS (L2 直上) のトランスポートが
不揃いなため却下。

キーの推奨記述順は `bgp`, `ospf`, `isis`, `bfd`, `routing_neighbors` (プロセス → 隣接)。

#### 配置基準

**`control_plane` に置くもの**: 誰と誰が経路・到達性情報を交換するか (セッション) と、そのプロトコルのノードごとの設定。

**データプレーン側に置くもの**: データプレーン要素に帰属する値。**その値を配布・交渉するのが制御プロトコルであっても**、
値はその要素の属性として置く。

| 情報 | 置き場所 | 理由 |
|---|---|---|
| BGP / OSPF / IS-IS のセッションとノード設定 | `control_plane` | 経路情報を交換するピア関係 |
| BFD | `control_plane` | セッションの生存監視。timer をスコープ内に保持する ADR-0005 D3-3 の例外は維持 |
| LACP の mode / min_links | `layer1.lag[].lacp` (現状維持) | LAG の形成条件。LAG という L1 要素の属性 |
| VRRP / HSRP / anycast gateway | `layer3.interfaces[].fhrp` (現状維持) | ゲートウェイ VIP という L3 要素の属性 |
| Route Target / RD | `layer3.vrfs[]` (現状維持) | VRF の境界 (VPN トポロジー、RFC 4364) を定義する VRF の属性。BGP が extended community として運ぶが、値は VRF に帰属する |
| VxLAN の `members` / `vtep_source` | `layer2.vxlan[]` (現状維持) | VNI の参加ノード集合。EVPN では Type-3 route で自動配布されるが、mlndl が記述するのは意図した参加集合であり、VNI の属性 |

> **r1 からの変更**: r1 は「セクションを削除してデータプレーンの識別子が残るなら control_plane」という判定テストを置いたが、
> このテストでは `vxlan[].members` や `vrfs[].route_targets` まで control_plane 行きになり、現状の配置と矛盾した。
> 削除テストは F1 の観察として残し、判定基準は「セッションか、要素の属性か」に置き換えた。

ndl-viz が「プロトコル抜きの論理構成図」を出すときは、`control_plane` キーを 1 つ落とすだけでよい。

### D3. セッションは `control_plane.routing_neighbors` の 1 箇所にだけ書く

`layer3.routing_adjacencies` を `control_plane.routing_neighbors` に移し、改名する。
`protocols.bgp[].nodes[].neighbors[]` は**廃止**する。セッションを書ける場所は 1 箇所だけになる (案P の解消)。

フィールド名の根拠: RFC 4271 上、BGP は "adjacency" と呼ばない (peer / neighbor / session)。
"adjacency" は OSPF (RFC 2328 §10) と IS-IS の用語である。"neighbor" は BGP・OSPF・IS-IS のすべてで使われ、
全主要ベンダー CLI (`show bgp neighbor` / `show ip ospf neighbor` / `show clns neighbor`) と
OpenConfig が採用している。`routing_` 接頭辞は IPv6 ND (RFC 4861) の neighbor、LLDP neighbor と区別するため。
リストは「近隣関係 (neighbor relationships) の一覧」と読む。

#### type による Discriminated Union

プロトコルごとに端点の意味が違うため、`type` を discriminator とする Tagged Union にする
(`lag` の `LacpLag | MlagLag` と同じ判断)。共通フィールドは基底クラスにまとめる。

エントリの型名はプロトコルごとの正式用語を使う: BGP は session (RFC 4271 §8)、OSPF / IS-IS は adjacency。

```python
class BgpEndpoint(BaseModel):
    node: str
    update_source: str | None = None           # layer3.interfaces[].id (loopback 等)。unnumbered は D3 末尾
    route_reflector_client: bool = False       # この端が RR クライアントであることを示す (RFC 4456)

class OspfEndpoint(BaseModel):
    node: str
    interface: str                             # layer3.interfaces[].id — OSPF は IP 上で hello を送る

class IsisEndpoint(BaseModel):
    node: str
    interface: str                             # layer1.interfaces[].id — IS-IS は L2 上で IIH を送る

class RoutingNeighborBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str
    process: str | None = None                 # control_plane.<type>[].id。同 type のエントリが 1 つなら省略可
    bfd: bool = False                          # セッション単位の BFD opt-in
    attaches_to: AttachesTo | None = None      # 物理リンク 1 本に対応するセッションのみ。overlay は省略

class BgpSession(RoutingNeighborBase):
    type: Literal["bgp"]
    from_: BgpEndpoint = Field(alias="from")
    to: BgpEndpoint
    address_families: list[AddressFamily] = []

class OspfAdjacency(RoutingNeighborBase):
    type: Literal["ospf"]
    from_: OspfEndpoint = Field(alias="from")
    to: OspfEndpoint
    area: str                                  # ドット区切り 4 オクテット (RFC 2328)

class IsisAdjacency(RoutingNeighborBase):
    type: Literal["isis"]
    from_: IsisEndpoint = Field(alias="from")
    to: IsisEndpoint
    level: Literal["level-1", "level-2", "level-all"]   # RFC 9130 (ietf-isis) の level-type

RoutingNeighbor = Annotated[BgpSession | OspfAdjacency | IsisAdjacency, Field(discriminator="type")]
```

- **IS-IS に `update_source` を書くと型エラーになる** (F5 の解消)
- **OSPF の `interface` は `layer3.interfaces`、IS-IS の `interface` は `layer1.interfaces` を参照する**。
  端点の型を分けることで、validator が参照先の ID 空間を取り違えない
- **`from` / `to` は有向のまま**とする (ADR-0006「L3 との非対称性について」を引き継ぐ)。BGP の `update_source` のように
  端ごとに非対称な属性を持つため、`endpoints: [a, b]` の無向リストにはしない
- **`process`** は、そのセッションがどのインスタンスエントリ (D4) に属するかを指す。同じ type のエントリが
  2 つ以上ある場合 (例: default VRF と tenant VRF の BGP) は必須。これがないと D6 の AS 整合性を
  どのエントリの `local_as` と照合するか決まらない
- **RR 関係**は、クライアント側の端点に `route_reflector_client: true` を立てる。主要ベンダー (Cisco / Arista / FRR の
  `neighbor X route-reflector-client`) と OpenConfig (`route-reflector-client`) は、いずれも RR 側から見た neighbor に
  フラグを立てるモデルである。あるノードが RR であることは「クライアントを持つこと」から導出する。
  クラスタ ID が必要な場合は D4 のノードエントリに `route_reflector_cluster_id` を置く
- **BGP unnumbered** は ADR-0005 D3-1 の既決規則を引き継ぐ: `update_source` が loopback でない IF を指す場合に unnumbered と解釈する

### D4. インスタンスエントリはノード設定だけを持つ

`control_plane.bgp` / `ospf` / `isis` の各エントリは**セッションを持たず**、各ノードの設定だけを持つ。

```yaml
control_plane:
  bgp:
    - id: bgp-default                  # vrf 省略 = default VRF
      nodes:
        - {node: spine1, local_as: 65000, router_id: 10.0.0.1}
        - {node: leaf1,  local_as: 65001, router_id: 10.0.0.11}
        - {node: isp-pe1, local_as: 64999}    # 管理外ピアも AS だけ書く (後述)
    - id: bgp-tenant-a
      vrf: vrf-tenant-a                # layer3.vrfs[].id を参照
      nodes: [...]
  ospf:
    - id: ospf-underlay                # 1 エントリ = 1 OSPF ルーティングドメイン
      nodes:
        - {node: spine1, router_id: 10.0.0.1}
  isis:
    - id: isis-underlay
      nodes:
        - {node: spine1, net: 49.0001.0100.0000.0001.00}
  bfd:
    - {id: bfd-global, min_tx: 300, min_rx: 300, multiplier: 3, nodes: [spine1, leaf1]}
```

**eBGP / iBGP は両端ノードの `local_as` から導出する。** `BGPNeighbor.type: ebgp | ibgp` と `remote_as` は廃止する
(同じ事実の二重表現であり、F4 の矛盾の温床)。ADR-0005 D3-1 の P6 (`remote_as: <ASN> | external | internal`) もあわせて廃止する。
FRR の `remote-as external` は設定生成時の記法であり、トポロジーの記述としては両端の AS が決まっていれば足りる。
eve-lab-builder 等の下流ツールが必要に応じて `external` 記法で出力すればよい。

**管理外のピア** (ISP / IX / 他社) も `layer1.nodes` に置き、BGP エントリの `nodes` に `local_as` だけを書く。
ISP の PE は物理ケーブルの向こう側に実在する機器であり、`layer1` に置くことは ADR-0005 D1 (a) と矛盾しない。
`role` (open-form) で `isp` 等と注釈すればよい。

**本 ADR の範囲外** (導出が破綻するため Phase 3 以降で再判断):
per-neighbor の `local-as` 上書き・`replace-as`、BGP Confederation (RFC 5065)、`allowas-in` を前提とする AS 設計。
これらを使うトポロジーは現時点では表現できない。

`bfd` の意味: `routing_neighbors[].bfd: true` はセッション単位の opt-in。`control_plane.bfd[]` はノードごとの
timer プロファイルの提供先であり、BFD を張るかどうかは決めない。

### D5. `router_id` はインスタンスエントリのノードに置く

RFC 8349 (`ietf-routing`) の router-id はグローバル既定値 + プロトコルごとの上書きである。
mlndl ではインスタンスエントリのノード (`control_plane.bgp[].nodes[].router_id`、`ospf` も同様) に置く。

- **形式**: ドット区切り 4 オクテット (32 bit)。IPv6 アドレスは不可。
  OSPFv3 の Router ID は 32 bit のままで、IPv6 アドレスを割り当てることはできない (RFC 5340 §2.2)
- **インターフェース IP との一致は要求しない**。RFC 6286 §2.1 により BGP Identifier は
  「4 オクテット・符号なし・非ゼロで、AS 内で一意であるべき (should)」値であり、IP アドレスである必要はない。
  IPv6 のみのファブリックや BGP unnumbered では、該当する IPv4 インターフェースが存在しない
- **IS-IS には (現時点では) 置かない**。IS-IS の主識別子は NET の system-id である。
  TE Router ID (RFC 5305 の TLV 134 / RFC 6119 の TLV 140) は MPLS-TE / BGP-LS で使うが、mlndl は TE を扱わない。
  必要になれば `isis[].nodes[].te_router_id` として加算的に追加する

CLAUDE.md のバリデーション表に**未実装**として記載されていた「bgp/ospf の router_id が layer3.interfaces に定義済みか」は、
RFC 6286 が BGP Identifier とインターフェース IP の一致を要求していないため**実装しない**ことを明確にし、表から削除する。
代わりに D6 の一意性チェックを置く。

### D6. バリデーション規則

| チェック | Severity | 根拠 |
|---|---|---|
| `routing_neighbors[].process` が同じ type のエントリ ID か。省略時、同 type のエントリがちょうど 1 つか | error | D3 |
| `from/to.node` が、所属エントリの `nodes` に存在するか | error | 参照整合性 |
| `update_source` が `layer3.interfaces`、OSPF の `interface` が `layer3.interfaces`、IS-IS の `interface` が `layer1.interfaces` に存在するか | error | 参照整合性 (D3) |
| **同一ノード・同一 VRF で、BGP エントリの `local_as` が一意か** | error | F4 の検出 |
| 同一 VRF に BGP エントリが 2 つ以上ないか | error | D8-a (VRF ごとに 1 インスタンス) |
| 同一 AS 内で BGP `router_id` が重複していないか | error | RFC 6286 §2.1 / §2.2 (iBGP では重複で OPEN が拒否される) |
| 同一 OSPF エントリ (= ルーティングドメイン) 内で `router_id` が重複していないか | error | RFC 2328 (AS 内の全ルーターで一意) |
| `router_id` がドット区切り 4 オクテットで非ゼロか | error | RFC 6286 §2.1 / RFC 5340 §2.2 |
| `bfd: true` のセッションの両端ノードが、いずれかの `control_plane.bfd[].nodes` に含まれるか | error | 現行では矛盾が黙って通る |
| `routing_neighbors[].id` の推奨プレフィックス (`bgp-peer-` / `ospf-adj-` / `isis-adj-`) | warning | ADR-0002 D7 (既存) |

### D7. ID 命名

ADR-0002 D7 の推奨プレフィックス `bgp-peer-` / `ospf-adj-` / `isis-adj-` は**変更しない**。
フィールド名は 3 プロトコル共通の語 (`routing_neighbors`)、ID はプロトコル固有の正式用語を使う。
BGP は RFC 4271 に adjacency という語がないため `peer`、OSPF / IS-IS は adjacency が正式用語のため `adj`。

同一ノード対に複数のセッションがある場合 (F3):

| 状況 | ID |
|---|---|
| 1 本のセッションで複数 AF を運ぶ (D8-a の典型) | `bgp-peer-spine1-leaf1` (接尾辞なし)。AF 名は ID に入れない |
| default VRF 以外のインスタンスのセッション | `bgp-peer-spine1-leaf1-tenant-a` (VRF ID から `vrf-` を除いた部分を接尾辞に) |
| 同じインスタンス内で同じノード対に 2 本目 | `bgp-peer-spine1-leaf1-2` (ADR-0002 D6 の衝突回避と同じ形) |

### D8. 【未決・推奨あり】BGP エントリの単位 — VRF ごとのインスタンスか、underlay / overlay の役割か

F4 の矛盾を正しく直そうとすると、現行の「underlay 用 BGP プロセスと overlay 用 BGP プロセスを分ける」モデル自体が
実機と対応しないことが分かる。FRR・Arista EOS・Cisco NX-OS のいずれでも、default VRF の underlay と overlay は
同じ `router bgp <ASN>` の中の別 neighbor / 別 address-family であり、インスタンスの単位は VRF である。
RFC 8349 も `control-plane-protocol` を routing instance の中に置く。

さらに Cumulus / FRR で最も一般的な EVPN 構成は、**1 本の eBGP unnumbered セッションで
`ipv4_unicast` と `l2vpn_evpn` を同時に運ぶ**。この構成は「セッションが underlay と overlay のどちらに属するか」が
決められず、役割単位のプロセス分割では表現できない。

| 案 | BGP エントリの単位 | underlay / overlay の表現 | 単一セッション複数 AF |
|---|---|---|---|
| **D8-a (推奨)** | VRF ごとのインスタンス | セッションの `address_families` から導出。分類が必要なら `labels` (ADR-0009) | 書ける |
| D8-b | 役割 (`role: underlay \| overlay`) | エントリの `role` | 書けない (セッションを 2 つに割る必要がある) |

D8-a では現行の `BGPProcess.role` を**廃止**する (informative 降格ではなく削除)。underlay / overlay は
セッションの `address_families` から機械的に導出でき、同じ事実を 2 箇所に書く理由がない。
人間向けの分類として残したい場合は `labels` を使う。推奨キーは `fabric_role: underlay | overlay`
(`docs/label-vocabulary.md` に informative として追記)。`plane` は RFC 7426 の plane と混同するため使わない。

実証: `valid_full_dc.yaml` を D8-a で書き直すと、制御プレーン部分は 92 行 → 60 行 (-35%) になり、
F4 の AS 矛盾は構造上書けなくなる (`../evaluations/adr0010/draft-r1-syntax/R1_i_single_session_multi_af.yaml`)。

**本 ADR の Pass C でユーザー判断を仰ぐ。**

対象外の実装: Junos の logical-systems、IOS-XR の BGP multi-instance (`router bgp N instance X`) のように
1 VRF に複数の BGP インスタンスを持てる実装は、本モデルでは表現しない。

### D9. 移行

`mlndl` は `0.1.0` (未リリース) であり、`protocols:` / `layer3.routing_adjacencies` の外部利用者はいない。
移行期間は設けず直接置き換える。`ndl_version` は `1.0` のまま据え置く。
**`ndl_version: 1.0` は Phase 1〜2 の間は策定中 (drafting) であり、外部利用者がいない限り 1.0 の範囲内で破壊的変更を許容する。**
Phase 3 (安定版) 以降は、破壊的変更にはメジャーバージョンの更新を必須とする。

旧キーを書いた YAML には、**移動先を示す明示的なエラー**を返す。
`MLNDLTopology` に `model_validator(mode="before")` を置き、`protocols` と `layer3.routing_adjacencies` の
両方を検出して**まとめて**報告する (1 件目で打ち切らない)。

```
protocols は control_plane に移動しました (ADR-0010)
layer3.routing_adjacencies は control_plane.routing_neighbors に移動しました (ADR-0010)
```

既存 fixture の書き換えでは、`router_id` は各ノードの loopback IP を流用する (現行 fixture に router_id はない)。

## Consequences

### 良い影響

- **案P が構造的に解消する**: セッションを書ける場所が 1 箇所になり、二重表現も相互検証の必要もなくなる
- 「プロトコル抜きの論理構成図」が `control_plane` を 1 キー落とすだけで得られる
- IS-IS / OSPF が BGP と対称に扱える。IS-IS に `update_source` を書くミス、OSPF と IS-IS の参照先の取り違えが型で弾かれる
- F4 のような AS 矛盾が validator で検出される
- CLAUDE.md の誤った `router_id` 検証規則が解消する
- `valid_full_dc.yaml` の制御プレーン部分が 35% 短くなる (D8-a の場合)

### 悪い影響 / トレードオフ

- **破壊的変更**。3 fixture (`valid_full_dc` / `valid_multi_vlan` / `valid_multisite_wan`) と
  `tests/test_phase2.py` の書き換えが必要
- **`valid_full_dc.yaml` は単純な移植では直らない** (F4)。AS 設計を決め直す必要がある:
  - (i) **第一選択**: 1 本の eBGP セッションで `[ipv4_unicast, l2vpn_evpn]` を運ぶ。Cumulus / FRR の標準構成で、RFC 7938 の方針と整合
  - (iii) **代替**: underlay を IGP (OSPF / IS-IS) にし、全ノード同一 AS で iBGP EVPN overlay (spine を RR)。
    Cisco NX-OS 等の古典的 EVPN 構成で、RFC 8365 の RD / RT モデルに自然に合う
  - (ii) overlay を eBGP multihop にする構成は表現できるが、ベンダー / RFC いずれも推奨していない
- overlay セッションが「どの underlay の上を流れるか」は表現できない (`attaches_to: {link:}` は物理リンク 1 本しか指せない)。
  ndl-viz が overlay セッションを underlay リンクに重ねて描くことはできない。Phase 3 で `carried_by` 等を検討
- per-neighbor の `ebgp-multihop` / `next-hop-unchanged` 等は書く場所がない。ADR-0005 D3-2 のとおり上位ツールに委ねる
  (eBGP で `update_source` が loopback なら multihop が必要なことは導出できる)
- micro-BFD (RFC 7130、LAG メンバー単位) は `bfd[].nodes` の粒度では表現できない。Phase 2 議題に残す
- **OSPF / IS-IS はポイントツーポイント前提**とする。マルチアクセスセグメント (OSPF の DR / BDR、IS-IS の DIS) では
  DROther 同士は 2-Way 止まりで Full にならず (RFC 2328 §10.4)、N 台を 2 端点の組に展開すると意味論が壊れ、
  組数も N(N-1)/2 に膨らむ。セグメントを 1 エンティティとして持つ表現を Phase 3 で設計する。
  DC ファブリックでは Ethernet 上でも point-to-point で運用するのが一般的 (RFC 7938) であり、当面の実害は小さい

### 影響を受けるコンポーネント

- スキーマ: `src/mlndl/schema/protocols.py` → `control_plane.py` に再編、`layer3.py` から `RoutingAdjacency` / `RoutingAdjEndpoint` を削除、`topology.py`
  - `BgpSession` / `OspfAdjacency` / `IsisAdjacency` は `isinstance` 分岐用に公開する (`LacpLag` / `MlagLag` と同じ需要)
  - `__init__.py` の `__all__` は現在スキーマ型を公開していないため、公開 API の破壊はない
- バリデーター: `src/mlndl/validator.py` (routing_adjacencies 検証・`_validate_protocols`・`_check_conventions` のパス)
- エクスポーター: `src/mlndl/exporter/cytoscape.py:308`
- サンプル: `tests/fixtures/valid_full_dc.yaml` / `valid_multi_vlan.yaml` / `valid_multisite_wan.yaml`
- テスト: `tests/test_phase2.py`、`tests/test_validation_severity.py` (隣接プレフィックスのテスト)
- 文書: `CLAUDE.md` (YAML 例・バリデーション表・ディレクトリ構造)、ADR-0005 (D1・D3-1)、ADR-0002 D7 の備考、
  `docs/label-vocabulary.md` (`fabric_role` の追記)、ADR-0003 / drafts 内の `routing_adjacencies` / `protocols` への言及

## Alternatives Considered

- **案C** *(採用案)*: トップレベル `control_plane` にセッションとインスタンス設定を集約
- **案A 現状維持**: 却下 — F2〜F6 がすべて残る。ndl-viz は 2 箇所をフィルタする必要がある
- **案B セッションを `protocols` 配下へ移すだけ**: 構造は案C と同じだが、`protocols` という補集合的な名前が残る
- **案D RFC 8345 の `networks:` リストに一般化**: 却下 — 型が退化し、全 fixture の書き換えになる。
  RFC 8345 との対応はエクスポーターで担保する現行方針 (ADR-0005 Alt-4) を維持
- **案E OpenConfig 方式 (`layer3.vrfs[].protocols[]` にネスト)**: 却下 — IETF / OpenConfig / Batfish の業界モデルだが、
  YAML で書き比べたところ underlay eBGP を「default VRF に属する」と書かされる層の反転が起き、
  手書きの記述言語として読みにくい。BFD の置き場所も定まらない。
  案E が自然に持つ「セッションがどのインスタンスに属するか」の情報は、フラット構造のまま `process:` 参照で得る (D3)
- **`layer3.routing_adjacencies` を RFC 8346 の `l3-link` として正当化し現状維持**: RFC 8346 は `l3-link` を定義しており、
  BGP セッションを L3 トポロジー上のリンクと写像する解釈には根拠がある。しかし F3 (同一ノード対の複数セッション) と
  F5 (IS-IS は IP を使わない) を説明できないため却下
- **インスタンスエントリ内にセッションをネスト (`control_plane.bgp[].sessions[]`)**: 同一ノード対の区別が
  エントリで自然に付く利点はあるが、プロトコル横断でセッションを列挙する (ndl-viz の制御面グラフ描画) には
  全エントリを巡回する必要がある。フラットな `routing_neighbors` + `process:` 参照で同じ区別が得られるため却下
- **`remote_as` を「省略可・明示時は整合検証」として残す**: 管理外ピアを表現できる利点があるが、
  管理外ピアは `layer1` ノード + `local_as` で表現でき (D4)、残すと F4 と同型の二重表現が戻る。却下
- **`OspfEndpoint` と `IsisEndpoint` を 1 つの `IgpEndpoint` にまとめる**: 却下 — OSPF (IP 上) と IS-IS (L2 上) で
  `interface` の参照先が違う。また "IGP" は役割の名前であり、iBGP も IGP 的に使われるため型名として曖昧
- **RR を `rr: server | client` で表す**: 却下 — `rr` は略語規範 (ADR-0002) から外れ、RFC 4456 に "RR server" という語はない。
  `server` は `role: server` (ADR-0003 推奨語彙) とも衝突する
- **IS-IS level の値を `level-1-2` (Cisco 表記) にする**: 却下 — IETF RFC 9130 (`ietf-isis`) の `level-all` に合わせる
- **命名 `layer4`**: 却下 — 制御プロトコルのトランスポートが TCP / IP / L2 と不揃い
- **命名 `plane` を構造語またはラベル軸として使う (`data_plane:` / `labels: {plane: underlay}`)**: 却下 —
  RFC 7426 の plane (control / data / management) と、underlay / overlay (network overlay の階層) は別次元の概念であり、
  混同を招く。過去に提案した `labels: {plane: underlay}` はここで撤回する (`docs/label-vocabulary.md` 未収録のため実装影響なし)
- **命名 `routing_adjacencies` / `routing_sessions` / `routing_peers`**: 却下 — 3 プロトコルすべてで使われる語は neighbor のみ

## 未解決事項 (Pass C で確定)

1. **D8**: BGP エントリの単位 (VRF インスタンス vs 役割)。ユーザー判断
2. `bfd: bool` を `bfd: <bfd プロファイル id>` の参照に変えるか (RFC 9127 は BFD を独立モジュールとし、BGP から augment する)。
   本 ADR では決めない。micro-BFD の対応と合わせて別 ADR で扱う
3. `AddressFamily` の値域 (現行: `ipv4_unicast | ipv6_unicast | l2vpn_evpn | vpnv4 | vpnv6`)。
   RFC 5549 / 8950 (IPv6 ネクストホップで IPv4 NLRI) を区別するか
4. OSPF `area` をセッション側に置くか、インスタンスエントリのノード側に置くか (複数セッションが同じ area を共有すると冗長)

## r1 からの変更 (5 エージェントレビュー反映)

| 指摘 | 出所 | 対応 |
|---|---|---|
| **D3 が ADR-0006 を逆に引用していた** (ADR-0006 は L3 の `from`/`to` 有向維持を明記) | spec-architect | 有向維持に訂正。ADR-0006 は改訂しない |
| **セッションがどのインスタンスに属するかの参照がない** (D8-a と組み合わせると AS 照合先が決まらない) | dsl-designer | `process:` を追加 (D3・D6) |
| **配置基準の削除テストが `vxlan.members` / `vrfs.route_targets` で破綻** | spec-architect | 基準を「セッションか、要素の属性か」に置き換え (D2) |
| **`rr: server` は RFC 4456 にない語で、略語規範・`role: server` と衝突** | linguist | 端点の `route_reflector_client: true` に変更 (D3) |
| `IgpNeighborEnd` は OSPF (L3) と IS-IS (L2) の参照先を混同 | dsl-designer / linguist / example-author | `OspfEndpoint` / `IsisEndpoint` に分割 |
| 型名 `*NeighborEnd` は既存語彙 (`endpoints`, `RoutingAdjEndpoint`) と不一致 / `BgpNeighbor` は片側を指す語 | linguist | `*Endpoint`、`BgpSession` / `OspfAdjacency` / `IsisAdjacency` |
| 管理外ピアを表現できない | example-author / dsl-designer | `layer1` ノード + `local_as` のみで表現 (D4) |
| Confederation / `local-as` 上書きで導出が破綻 | network-tech-reviewer / dsl-designer | 範囲外と明記 (D4) |
| ADR-0005 P6 (`remote_as: external`) を黙って廃止していた | dsl-designer | 明示的に廃止を記載 (位置づけ・D4) |
| IS-IS level `level-1-2` は Cisco 表記 | linguist | RFC 9130 の `level-all` |
| 同一ノード対の ID 接尾辞に AF 名を使うと単一セッション複数 AF と矛盾 | spec-architect / linguist | 接尾辞規則を表に整理 (D7) |
| OSPF の router_id 一意性の範囲が狭すぎた | network-tech-reviewer | 「OSPF エントリ = ルーティングドメイン内」(D6) |
| 「IS-IS には router_id を置かない」は TE Router ID を無視 | network-tech-reviewer | TE は範囲外、加算的に追加可能と明記 (D5) |
| OSPF / IS-IS のマルチアクセスは 2 端点で表現不能 | network-tech-reviewer / example-author | ポイントツーポイント前提を明記 (Consequences) |
| F4 の修正案に iBGP overlay + IGP underlay がない | network-tech-reviewer | (iii) として追加、(ii) を非推奨に |
| CLAUDE.md の router_id 規則は「既存」ではなく「未実装」 | spec-architect | 表現を訂正 (D5) |
| `ndl_version` 据え置きの根拠がない | spec-architect | 1.0 策定中の扱いを明記 (D9) |
| 日本語の用語 (プロセス / インスタンス / セッション / 隣接 / ピア関係) が混在 | linguist | Terms 節を追加 |
| RFC 節番号の誤り: 4271 §4 / 5340 §2.7 / 8345 §3.1 | network-tech-reviewer | 原文照合の上で §3 / App. A.1 / §1・§4.1 に訂正。レビューの修正案 (5340 §4.2) も誤りだったため原文に従った |
| IS-IS を「LLC/SNAP」と記載 | network-tech-reviewer | 802.2 LLC (DSAP=SSAP=0xFE) に訂正。0x83 は PDU 先頭オクテットとして残す |

**採らなかった指摘**:

- `net` を `net_address` に改名 (linguist): `isis[].nodes[]` の中では曖昧さがなく、OpenConfig・RFC 9130・全ベンダー CLI が `net` を使うため据え置く
- IGP 端点の `interface` を `interface_id` に改名 (linguist): mlndl の既存の参照フィールド (`layer3.interfaces[].interface`、`trunk_ports[].interface`) が `interface` で統一されているため据え置く
- `bfd` の型を今のうちに `bool | str` へ緩めておく (dsl-designer): 未解決事項 2 で別 ADR にするため、型の先行変更もそちらで行う
- BGP と OSPF で `router_id` が異なる場合に warning (example-author): 異なる値を意図的に使う設計があり、推奨を強制する根拠がない

## References

- 関連 ADR: ADR-0001, ADR-0002 (D2・D6・D7), ADR-0005 (D1・D3-1・D3-2・D3-3・D4・Alt-4), ADR-0006, ADR-0009
- 実証 YAML: [`evaluations/adr0010/`](../evaluations/adr0010/README.md) — `layering/` (構造案の比較)、`draft-r1-syntax/` (r1 構文による書き直し)
- RFC 4271 (BGP-4) §1.1・§3・§8 / RFC 6286 (BGP Identifier) §2.1・§2.2 / RFC 4760 (MP-BGP) / RFC 4456 (Route Reflection) / RFC 5065 (Confederation)
- RFC 2328 (OSPFv2) §1.2・§4.3・§10・§10.4・App. A.1 / RFC 5340 (OSPFv3) §2.2・App. A.1
- ISO/IEC 10589 (IS-IS) / RFC 1195 / RFC 5305 / RFC 6119 / RFC 9130 (`ietf-isis`)
- RFC 5881 §4 / RFC 5883 §5 / RFC 7130 §2.2 (BFD) / RFC 9127 (BFD YANG)
- RFC 5798 (VRRPv3) §5.1.1.4・§5.1.2.4 / IEEE Std 802.3 Annex 57A / IEEE 802.1AX (LACP)
- RFC 4364 (BGP/MPLS IP VPN) / RFC 7432・RFC 8365 (EVPN) / RFC 7938 (BGP in Large-Scale Data Centers)
- RFC 7426 (SDN Layers and Architecture Terminology)
- RFC 8345 (Network Topologies) §1・§4.1 / RFC 8346 (L3) / RFC 8944 (L2) / RFC 8349 (`ietf-routing`)
- OpenConfig `openconfig-network-instance`
