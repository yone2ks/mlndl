# ADR-0010: control plane と data plane の分離 — `control_plane` と `routing_neighbors`

- **Status**: Superseded by [0010](../0010-control-plane-separation.md) (ラウンド3 Pass C, 2026-11-01)。以下は Pass A (r1〜r4) の記録として残す。 元の Status: Draft — r4。D8 はユーザー決定済み (2026-11-01)。r3 の Pass B を反映済み
- **Date**: 2026-09-19 (r1・r2) / 2026-11-01 (r3・r4)
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **Pass**: B 済み r4 (r3 = D8 の決定と、保留中に Accepted になった ADR との整合を反映。r4 = r3 の Pass B を反映。差分は末尾「r3 からの変更」「r2 からの変更」)
- **関連**: ADR-0001 (attaches_to。D8 のキー規則), ADR-0002 (ID 命名 D2・D6・D7), ADR-0005 (表現スコープ D1・D3-1・D3-3・D4 補則), ADR-0006 (endpoints), ADR-0009 (labels),
  ADR-0011 (L3 IF・トンネルの `destination_ip`), [drafts/0014](0014-vteps.md) (VTEP), [drafts/0015](0015-declarative-references.md) (Ref), [drafts/0016](0016-router-id-and-management-interface.md) (router_id)
- **吸収する課題**: 「案P」(BGP 隣接の二重表現)

## 経緯と現在の状態

- **2026-09-19**: r2 まで策定。D2・D3 をユーザーが決定
- **2026-09-20**: layer3 までのデータプレーンを先に確定させるため保留 (ADR-0011〜0013 は 2026-10-15 に Accepted)
- **2026-11-01**: 再開。ndl-viz で BGP を表示すると、同じ機器の組に `protocols.bgp` の neighbor (両側から向き違いで 1 本ずつ・
  プロセスごと) と `layer3.routing_adjacencies` が重なり、1 組に最大 6 本の線が出た。組ごとに 1 本へまとめると
  別々のセッション (underlay の eBGP と EVPN の iBGP など) が 1 本の線に混ざり、意味が通らなくなった。
  ユーザーの要件は「**線 1 本 = セッション 1 本で、両端の IP と AS、eBGP / iBGP、運ぶ AF が分かる**」こと
  (ndl-viz は MLNDL に書かれた情報だけを表示し、推定で埋めない)。今の構造ではセッションを完全に表す場所がなく、
  この要件を満たせないことが D8 の再開理由になった。5 エージェントで検討し、r3 として反映した
  (試し書き: [`evaluations/adr0010/d8-r3/`](../evaluations/adr0010/d8-r3/README.md))
- **2026-11-01**: r3 を 5 エージェントで横断評価 (Pass B) し、r4 として反映した
  (試し書き: [`evaluations/adr0010/r3/`](../evaluations/adr0010/r3/README.md))

**ユーザー決定済み**:

| 日付 | 決定 |
|---|---|
| 2026-09-19 | トップレベル `protocols:` を廃止し `control_plane:` を新設する (D2) |
| 2026-09-19 | `layer3.routing_adjacencies` を `control_plane.routing_neighbors` に移動・改名する (D3) |
| 2026-11-01 | BGP エントリの単位は **VRF ごとのインスタンス** (D8)。underlay / overlay は構文に入れず AF から導く |
| 2026-11-01 | トポロジー外の相手は `address` と `local_as` だけで書ける (D3・D4。トンネルの `destination_ip` と同じ形) |
| 2026-11-01 | unnumbered は「update_source がアドレスを持たない L3 IF を指す」で表す (D3) |
| 2026-11-01 | セッションには `attaches_to` を書かない。通り道は `update_source` の L3 IF から導く (D3。r3 の `{link:}` / `{lag:}` 案を Pass B 後に変更) |
| 2026-11-01 | インスタンスを指すフィールドは `instance` (`process` から改名。D3) |
| 2026-11-01 | `router_id` は ADR-0016 に委ねる (D5) |

**次の手順**: Pass C (評価メモから再構築して確定。ADR-0001・ADR-0005・ADR-0016 の改訂を同時に行う) → 実装。

**実装への影響**: スキーマ・validator・fixture は**まだ変更していない**。現行の `layer3.routing_adjacencies` と
`protocols` はそのまま動作し、F2〜F6 の問題も残っている。

### 位置づけ

本 ADR は **ADR-0005 の部分改訂**であり、置き換え (supersede) ではない。ADR-0005 の三側面・D4 判定フレームワーク・スコープ確定は維持する。
改訂するのは以下に限る。

| 改訂対象 | 内容 |
|---|---|
| ADR-0005 D1 | 「(b) 論理構成図」の内部を、データプレーン (`layer2` / `layer3`) と制御プレーン (`control_plane`) に分けて位置づける |
| ADR-0005 D3-1 (b) | `layer3.routing_adjacencies` 行と `protocols.*` 行を `control_plane.*` に置き換える |
| ADR-0005 D3-1 (c) | `routing_adjacencies[].attaches_to` 行を削除する。セッションの通り道は `update_source` の L3 IF から導く (D3) |
| ADR-0005 D3-1 (P6) | `remote_as: <ASN> \| external \| internal` を廃止する (D4) |
| ADR-0005 D3-1 (unnumbered) | 「`update_source` が loopback でない IF を指せば unnumbered」を、「`update_source` が `ip` も `ipv6` も持たない L3 IF を指せば unnumbered」に置き換える (D3) |
| ADR-0001 D2 の例・D8 の表 | セッション (routing_adjacencies) の `attaches_to: {link:}` の例と、routing_adjacencies に書けるキー (`node` / `interface` / `link`) の記述を削除する。`{link:}` キーは今セッションでしか使われていないので、L1 ノード・L1 IF に残すか (L1 の何かがリンク上で実現される場面があるか) は ADR-0001 の改訂で決める。CLAUDE.md の同じ表 (「リンク (BGP 等)」の行) も |
| ADR-0016 | `router_id` の置き場所を `control_plane.bgp[].nodes[]` / `control_plane.ospf[].nodes[]` に移す (D5) |
| ADR-0002 D7 | 備考のみ (プレフィックスは変更しない。D7 参照) |

**ADR-0006 は改訂しない。** ADR-0006「L3 との非対称性について」の判断 (L3 の隣接は `from`/`to` の有向を維持する) をそのまま引き継ぐ。

前回ラウンドで構想した ADR-0005 の再設計 (redistribute / EVPN advertise フラグを D3-2 へ移す、スコープの原理文の追加) は**本 ADR の範囲外**であり、別途 `drafts/0005v2-*` で扱う。

## Terms

| 用語 | 本 ADR での意味 |
|---|---|
| **セッション** | 2 台のスピーカー間の 1 本の関係。プロトコルを問わない抽象概念 (BGP の Established、OSPF の Full、IS-IS の Up) |
| **隣接 (adjacency)** | OSPF / IS-IS の正式用語 (RFC 2328 §1.2 / §10、ISO/IEC 10589)。BGP には使わない |
| **ピア / neighbor** | 相手方の 1 台。RFC 4271 §1.1 で peer と neighbor は同義。2 台の関係そのものは「セッション」と呼ぶ |
| **インスタンス** | 1 台のノード上の、1 つの VRF における 1 つのルーティングプロトコルの実行単位 (RFC 8349 の routing instance 内の control-plane-protocol)。YAML の `control_plane.<proto>[]` の 1 エントリは、**ある 1 つの VRF の、そのプロトコルのインスタンスを全ノード分まとめたもの**であり、セッションは `instance:` でそれを指す。会話や CLI で「BGP プロセス」と呼ぶものと同じ |
| **single-hop / multihop** | セッションの相手が直結したリンクの上にいるか (single-hop)、ルーティングを経由しないと届かないか (multihop)。構文には出さず、`update_source` の L3 IF から導く (D3) |
| **トランスポートのアドレスファミリー** | セッションを張る IP (TCP の両端) が IPv4 か IPv6 か。セッションが運ぶ経路の種類 (`address_families`。NLRI の AFI/SAFI) とは独立である (RFC 8950 では IPv6 のセッションで IPv4 経路を運ぶ) |
| **underlay / overlay** | ファブリックの IP 網 (underlay) と、その上に VXLAN で作る網 (overlay)。BGP セッションの性質ではない。セッションについて言うときは AF から導く呼び名として使う (D8) |

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

キーの推奨記述順は `bgp`, `ospf`, `isis`, `bfd`, `routing_neighbors` (インスタンスごとの設定 → セッション)。

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
| VTEP と VNI の参加 (`layer2.vteps` / `layer2.vxlan[].vteps`) | `layer2` (現状維持。drafts/0014 の決定を前提とする) | VNI の参加集合。EVPN では Type-3 route で自動配布されるが、mlndl が記述するのは意図した参加集合であり、VNI の属性 |

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
**1 エントリ = 1 セッション**である。同じ機器の組に 2 本のセッションがあれば 2 エントリ書く。

別のエンティティの id を指すフィールドには ADR-0015 の `Ref` を付ける。参照先の存在の検査はこれで付き、D6 に手で書かない。

```python
class BgpEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # トポロジー内の機器: node (+ update_source)。トポロジー外の相手: address + local_as (下の表)
    node: Annotated[str | None, Ref("layer1.nodes")] = None
    update_source: Annotated[str | None, Ref("layer3.interfaces")] = None   # この側のセッションのアドレスを持つ L3 IF
    address: IPv4Address | IPv6Address | None = None                       # トポロジー外の相手のホストアドレス (プレフィックス長なし)
    local_as: int | None = None                                            # トポロジー外の相手自身の AS
    route_reflector_client: bool = False                                   # この端が RR クライアント (RFC 4456)

    @model_validator(mode="after")
    def _shape(self) -> "BgpEndpoint":
        # 2 つの形のどちらかであること (下の表)。エラーは「何が足りない / 書けない」を具体的に返す
        ...

class OspfEndpoint(BaseModel):
    node: Annotated[str, Ref("layer1.nodes")]
    interface: Annotated[str, Ref("layer3.interfaces")]     # OSPF は IP 上で hello を送る

class IsisEndpoint(BaseModel):
    node: Annotated[str, Ref("layer1.nodes")]
    interface: Annotated[str, Ref("layer1.interfaces")]     # IS-IS は L2 上で IIH を送る (参照先が OSPF と違う理由は Alternatives)

class RoutingNeighborBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str
    bfd: bool = False                                       # セッション単位の BFD opt-in

class BgpSession(RoutingNeighborBase):
    type: Literal["bgp"]
    instance: Annotated[str | None, Ref("control_plane.bgp")] = None
    from_: BgpEndpoint = Field(alias="from")
    to: BgpEndpoint
    address_families: list[AddressFamily] = []

class OspfAdjacency(RoutingNeighborBase):
    type: Literal["ospf"]
    instance: Annotated[str | None, Ref("control_plane.ospf")] = None
    from_: OspfEndpoint = Field(alias="from")
    to: OspfEndpoint
    area: str                                               # ドット区切り 4 オクテット (RFC 2328。`0` は `0.0.0.0` に正規化)

class IsisAdjacency(RoutingNeighborBase):
    type: Literal["isis"]
    instance: Annotated[str | None, Ref("control_plane.isis")] = None
    from_: IsisEndpoint = Field(alias="from")
    to: IsisEndpoint
    level: Literal["level-1", "level-2", "level-all"]       # RFC 9130 (ietf-isis) の level-type

RoutingNeighbor = Annotated[BgpSession | OspfAdjacency | IsisAdjacency, Field(discriminator="type")]
```

- **IS-IS に `update_source` を書くと型エラーになる** (F5 の解消)
- **OSPF の `interface` は `layer3.interfaces`、IS-IS の `interface` は `layer1.interfaces` を参照する**。
  端点の型を分けることで、`Ref` の参照先の ID 空間を取り違えない
- **`from` / `to` は有向のまま**とする (ADR-0006「L3 との非対称性について」を引き継ぐ)。BGP の `update_source` のように
  端ごとに非対称な属性を持つため、`endpoints: [a, b]` の無向リストにはしない
- **`instance`** は、そのセッションがどのインスタンスエントリ (D4) に属するかを指す。同じ type のエントリが
  2 つ以上ある場合 (例: default VRF と tenant VRF の BGP) は必須。これがないと両端の AS をどのエントリから引くか決まらない。
  エントリが 1 つでも、明示しておくと読みやすい (推奨)。
  r2 の `process` から改名した (Terms の「インスタンス」と字面を一致させ、RFC 8349 に合わせ、OS のプロセスと紛れないようにする)。
  `instance` は type ごとに別のコレクションを指すので、Tagged Union の各型に置く
- **`update_source`** は L3 IF の `id` を指す。機器上の名前 (`name`) では引かない (ADR-0011)。
  ループバックかどうかは問わない (ADR-0011 D11 は `unattached` をループバックとみなさない)
- **BGP の端点は 1 つの型にまとめ、2 つの形を `model_validator` で区別する。** トポロジー内 / 外の端点を 2 つのクラスの Union に
  すると、pydantic v2 の discriminator なしの Union は先に当てはまった型を選び、どちらにも当てはまらないときのエラーも
  「どの型にも合わない」としか言えない。1 つの型にしておけば「`node` のない端は `address` と `local_as` が必須です」のように具体的に返せる
- **RR 関係**は、クライアント側の端点に `route_reflector_client: true` を立てる。主要ベンダー (Cisco / Arista / FRR の
  `neighbor X route-reflector-client`) と OpenConfig (`route-reflector-client`) は、いずれも RR 側から見た neighbor に
  フラグを立てるモデルである。あるノードが RR であることは「クライアントを持つこと」から導出する。
  クラスタ ID が必要な場合は D4 のノードエントリに `route_reflector_cluster_id` を置く

#### セッションの通り道は書かず、`update_source` から導く

セッションには `attaches_to` を**書かない**。r2 までの routing_adjacencies が持っていた `attaches_to: {link:}` (このセッションが流れる物理リンク) は、
`update_source` の L3 IF にすでに書かれている事実から導ける。セッションにも書くと同じ事実を 2 か所に書くことになり、食い違い
(例: 現行 fixture の、ループバックを `update_source` にしながら `attaches_to: {link:}` を書いたセッション) が検査なしに通る。
これは ADR-0005 D6 の「`node` は基盤から導き、書かない」、ADR-0012 / 0013 の「参照先から導出する」と同じ考え方である。

両端の `update_source` の L3 IF の `attaches_to` (ADR-0011) から、通り道を次のように導く (導出は `derive.py` に置き、validator・エクスポーター・ndl-viz で共有する)。

| `update_source` の L3 IF | その L3 IF の `attaches_to` | セッションの通り道 |
|---|---|---|
| 物理 IF の L3 IF (/31 や unnumbered) | `{interface: <L1 IF>}` | その L1 IF のリンク。両端の L1 IF が同じリンクの両端なら single-hop |
| port-channel の L3 IF | `{lag: <LAG>}` | その LAG。両端の LAG のメンバーどうしがリンクでつながっていれば single-hop |
| サブ IF の L3 IF | `{subinterface: <サブ IF>}` | サブ IF の基盤 (L1 IF / LAG) について上と同じ |
| SVI | `{vlan: <VLAN>}` | 1 本に決まらない (VLAN は複数のリンク・LAG にまたがりうる)。multihop と同じ扱い |
| ループバック・dummy 等 | なし (`unattached`) | multihop |
| `update_source` を書いていない | — | 分からない |

- **single-hop / multihop は構文に出さない** (ADR-0005 D4 補則 問い 4)。上の表から導く。`ebgp-multihop` 等の設定は書かない
  (ADR-0005 D3-2。下流ツールが導出結果から判断する)
- 両端の L3 IF が別々のリンク上にある (隣接していない) のに直結の IF どうしを指している、といった食い違いは D6 で検査する

#### BGP unnumbered

**`update_source` が `ip` も `ipv6` も持たない L3 IF を指すとき、その端は unnumbered** である。リンクローカルアドレスを形だけ書く必要はない
(FRR の `neighbor swp51 interface` 構成。相手のリンクローカルアドレスは実行時に決まる)。
r2 (ADR-0005 D3-1 から引き継いだ「loopback でない IF を指す」) の規則は、IPv6 だけのループバックや SVI 上のセッションで誤判定するため置き換える。
IPv6 のグローバルアドレスを持つ IF で張るセッションは unnumbered ではなく、IPv6 アドレスで張るセッションである。

アドレスのない L3 IF そのものは unnumbered 用とは限らない (書きかけ・未使用もありうる)。unnumbered と表示するのは、
セッションの `update_source` がその L3 IF を指しているときだけである。ビューアーは IPv4 を推定せず、IF の名前と「unnumbered」を出す。

#### BGP の端点の 2 つの形

| 相手 | 書き方 | AS の出どころ |
|---|---|---|
| トポロジー内の機器 (`layer1.nodes` にある) | `{node, update_source}` | `instance` のエントリの `nodes[].local_as` (D4) |
| トポロジー外の相手 (IP と AS しか分からない) | `{address, local_as}` | 端点の `local_as` |

- `node` を書いた端に `address` / `local_as` は書かない。`node` のない端には `address` と `local_as` が必須で、`update_source` は書けない
- 両端ともトポロジー外にはできない
- **端点の `local_as` は「その端の相手自身の AS」**である。インスタンスの `nodes[].local_as` (そのノード自身の AS) と同じ視点であり、
  廃止した `remote_as` (記述する側から見た相手の AS) のような相対的な値ではない
- **端点の `address` は相手のホストアドレス** (プレフィックス長なし) である。`layer2.vteps[].address` (VTEP のアドレス) とは別物
- ADR-0011 D6 のトンネル (`destination_interface` か `destination_ip` のどちらか一方) と同じく、「相手をトポロジーに書いたか」で
  2 つの書き方を使い分ける (フィールド名は揃っていない)。トポロジー外の相手とのセッションは、トンネルと同じくノードのデータとして出し、
  ビューアーは機器どうしの線にしない
- ISP の PE までのケーブルを `layer1` に書いている場合は、相手の機器はトポロジー内である。相手の L3 IF を 1 つ書き、
  `{node, update_source}` で指す (L1 の IF はケーブルのために既にある)
- トポロジー外の相手とだけセッションを張り、ケーブルを書かない場合、こちら側の L1 IF は対向のない IF として残る。これは L1 の記述の粒度の問題であり、本 ADR では制約しない

### D4. インスタンスエントリはノード設定だけを持つ

`control_plane.bgp` / `ospf` / `isis` の各エントリは**セッションを持たず**、各ノードの設定だけを持つ。
BGP のエントリは **VRF ごとのインスタンス**である (D8)。

```yaml
control_plane:
  bgp:
    - id: bgp-default                  # vrf 省略 = default VRF
      nodes:
        - {node: spine1, local_as: 65000}
        - {node: leaf1,  local_as: 65001}
        - {node: isp-pe1, local_as: 64999}    # ケーブルを layer1 に書いた管理外の機器 (role: isp。推奨語彙の外でも valid)
    - id: bgp-tenant-a
      vrf: vrf-tenant-a                # layer3.vrfs[].id を参照 (Ref)
      nodes: [...]
  ospf:
    - id: ospf-underlay                # 1 エントリ = 1 OSPF ルーティングドメイン
      nodes:
        - {node: spine1}
  isis:
    - id: isis-underlay
      nodes:
        - {node: spine1, net: 49.0001.0100.0000.0001.00}
  bfd:
    - {id: bfd-global, min_tx: 300, min_rx: 300, multiplier: 3, nodes: [spine1, leaf1]}
```

`nodes[].node` と `vrf`、`bfd[].nodes` には `Ref` を付ける (ADR-0015)。ノードエントリは固有の型 (`BgpInstanceNode` 等。
`local_as` / `router_id` / `route_reflector_cluster_id` を持つ) にし、validator から参照しやすくする。

同じ機器が複数の VRF のインスタンスに出てくるときは、VRF ごとに `local_as` を書く (同じ値でも省略しない)。
実機も VRF ごとの BGP インスタンスが AS を持つモデルであり、VRF によって AS を変える構成もある。

**AF はセッションにだけ書く。** インスタンスのノードには置かない。同じ機器・同じ VRF でも、相手ごとに運ぶ AF が違うのが実機の普通である
(spine は leaf とは EVPN、WAN ルーターとは IPv4 だけ)。ノードにも書けると、どちらが正しいかが決まらなくなる (F4 と同型)。
ピアグループのような既定値は持ち込まない (設定を生成するための構造であり、構成の記述ではない。ADR-0005 D3-2)。

**eBGP / iBGP は両端の AS から導出する。** `BGPNeighbor.type: ebgp | ibgp` と `remote_as` は廃止する
(同じ事実の二重表現であり、F4 の矛盾の温床)。ADR-0005 D3-1 の P6 (`remote_as: <ASN> | external | internal`) もあわせて廃止する。
FRR の `remote-as external` は設定生成時の記法であり、トポロジーの記述としては両端の AS が決まっていれば足りる。
eve-lab-builder 等の下流ツールが必要に応じて `external` 記法で出力すればよい。

両端の AS は次のように決まる。

- トポロジー内の端: セッションの `instance` が指すエントリの `nodes[]` のうち、その端の `node` のもの (`local_as`)
- トポロジー外の端: 端点の `local_as` (D3。その端の相手自身の AS)

**管理外のピア** (ISP / IX / 他社) は 2 通りに書ける (D3 の表)。ケーブルまで書くなら `layer1` に機器を置き、
BGP エントリの `nodes` に `local_as` を書く (ISP の PE は物理ケーブルの向こう側に実在する機器であり、ADR-0005 D1 (a) と矛盾しない。
`role` (open-form) で `isp` 等と注釈する)。IP と AS しか分からないなら、端点に `address` と `local_as` を書く。

**本 ADR の範囲外** (導出が破綻するため Phase 3 以降で再判断):
per-neighbor の `local-as` 上書き・`replace-as`、BGP Confederation (RFC 5065)、`allowas-in` を前提とする AS 設計。
これらを使うトポロジーは現時点では表現できない。

`bfd` の意味: `routing_neighbors[].bfd: true` はセッション単位の opt-in。`control_plane.bfd[]` はノードごとの
timer プロファイルの提供先であり、BFD を張るかどうかは決めない。

### D5. `router_id` は ADR-0016 に委ねる

r2 は D5 で `router_id` の置き場所・形式・一意性を決めていたが、同じ内容を [drafts/0016](0016-router-id-and-management-interface.md)
(ルーター ID と管理インターフェースの明示) が扱っている。二重に決めないよう、**`router_id` は ADR-0016 に委ねる**。

本 ADR が確認するのは置き場所だけである: BGP は `control_plane.bgp[].nodes[].router_id`、OSPF は `control_plane.ospf[].nodes[].router_id`
(D8 で BGP のエントリが VRF ごとのインスタンスになるので、VRF ごとに router-id を持てる)。
ADR-0016 が `protocols.bgp[]` に先行して置く場合は、本 ADR の実装時に `control_plane` へ移す。
形式 (ドット区切り 4 オクテット・非ゼロ)・インターフェース IP との一致を要求しないこと (RFC 6286)・一意性の検査は ADR-0016 で決める。

### D6. バリデーション規則

参照先の存在 (`instance` / `node` / `update_source` / `interface` / `vrf` / `bfd[].nodes`) は `Ref` の汎用検査で付くので、
ここには書かない (ADR-0015)。端点の形 (D3 の 2 つの形) は `BgpEndpoint` の `model_validator` で型の段階で弾く。
手で書くのはネットワークとしての意味の検査だけである。

| チェック | Severity | 根拠 |
|---|---|---|
| `routing_neighbors[].instance` の省略時、同じ type のエントリがちょうど 1 つか | error | D3 |
| トポロジー内の端の `node` が、`instance` のエントリの `nodes` にあるか | error | D4 (AS を引く先) |
| BGP の `update_source`、OSPF / IS-IS の `interface` の参照先の `node` が、その端の `node` と一致するか | error | D3 (ADR-0011 D9 と同じ形) |
| `update_source` の L3 IF の `vrf` が、`instance` のエントリの `vrf` と一致するか (省略はどちらも default) | error | VRF-lite の書き間違いが黙って通るのを防ぐ |
| 両端の `update_source` から導いた通り道が食い違わないか (片方が直結の IF を指すのに、もう片方の L3 IF がそのリンクの対向にない等) | error | D3 (通り道の導出) |
| トポロジー外の端の `address` と、もう一方の端の `update_source` の**トランスポートのアドレスファミリー** (IPv4 / IPv6) が一致するか (unnumbered の端は検査しない) | error | D3。セッションが運ぶ `address_families` とは独立 (Terms) |
| 同じインスタンスで、`update_source` の L3 IF の id の組が同じセッションが 2 つないか (unnumbered も id で比べる) | error | 二重定義 |
| `route_reflector_client: true` のセッションの両端の AS が同じか | error | RR は iBGP の仕組み (RFC 4456) |
| **同一ノード・同一 VRF で、BGP エントリの `local_as` が一意か** | error | F4 の検出 |
| 同一 VRF に BGP エントリが 2 つ以上ないか | error | D8 (VRF ごとに 1 インスタンス) |
| default 以外の VRF のインスタンスのセッションに、`l2vpn_evpn` / `vpnv4` / `vpnv6` を書いていないか | warning | これらの経路は default VRF のセッションで運ぶのが通常 (RFC 4364 §10 / RFC 7432)。例外の構成を言い切れないため error にはしない (`--strict` で error) |
| `bfd: true` のセッションの両端ノードが、いずれかの `control_plane.bfd[].nodes` に含まれるか | error | 現行では矛盾が黙って通る |
| `routing_neighbors[].id` の推奨プレフィックス (`bgp-peer-` / `ospf-adj-` / `isis-adj-`) | warning | ADR-0002 D7 (既存) |

`router_id` の形式と一意性の検査は ADR-0016 で定義する (本 ADR では定義しない。D5)。

### D7. ID 命名

ADR-0002 D7 の推奨プレフィックス `bgp-peer-` / `ospf-adj-` / `isis-adj-` は**変更しない**。
フィールド名は 3 プロトコル共通の語 (`routing_neighbors`)、ID はプロトコル固有の正式用語を使う。
BGP は RFC 4271 に adjacency という語がないため `peer`、OSPF / IS-IS は adjacency が正式用語のため `adj`。

ID の文法は ADR-0002 D1 に従い、プレフィックス以外は自由である。以下は推奨であり、同じ組に複数のセッションがある場合 (F3) の書き分けを示す。
区別の語は**ノード対の後ろ (末尾)** に付ける。ノード対の間に挟むと、`bgp-peer-<A>-<B>` (ADR-0002 D2) の形が崩れる。

| 状況 | ID の例 |
|---|---|
| 1 本のセッションで複数 AF を運ぶ (D8 の典型) | `bgp-peer-spine1-leaf1` (接尾辞なし)。運ぶ AF のうち 1 つだけを ID に入れると、ほかの AF を運ぶことが読めなくなる |
| default 以外の VRF のインスタンスのセッション | `bgp-peer-leaf6-wan-rtr-tenant-a` (VRF ID から `vrf-` を除いた部分を末尾に) |
| 同じインスタンスで同じノード対に 2 本目 (underlay と overlay を別セッションにする構成) | `bgp-peer-spine1-leaf1-evpn` のように、そのセッションだけが運ぶものや用途を末尾に付ける。`-2` (ADR-0002 D6 の衝突回避) も使えるが、何のセッションかが ID から読めない |

ノード ID がハイフンを含む (`wan-rtr`) と、ID だけからはノード対と接尾辞の境目が読めない。ID は人が読むための名前であり、
両端の機器は `from` / `to` から引く (ID を分解して使わない)。

### D8. BGP エントリの単位は VRF ごとのインスタンスとする (2026-11-01 決定)

**決定**: `control_plane.bgp[]` の 1 エントリは **1 つの VRF の BGP インスタンス**である (r2 の D8-a)。
`BGPProcess.role` (underlay / overlay) は**廃止**する。underlay / overlay は構文に入れない。

#### 根拠

F4 の矛盾を正しく直そうとすると、現行の「underlay 用 BGP プロセスと overlay 用 BGP プロセスを分ける」モデル自体が
実機と対応しないことが分かる。FRR・Arista EOS・Cisco NX-OS のいずれでも、default VRF の underlay と overlay は
同じ `router bgp <ASN>` の中の別 neighbor / 別 address-family であり、インスタンスの単位は VRF である
(Junos も `routing-instances` ごと)。RFC 8349 も `control-plane-protocol` を routing instance の中に置き、
OpenConfig (`network-instance`) と Batfish (`vrfs[] → bgpProcess`) も同じ単位である。

さらに Cumulus / FRR で最も一般的な EVPN 構成は、**1 本の eBGP unnumbered セッションで
`ipv4_unicast` と `l2vpn_evpn` を同時に運ぶ**。この構成は「セッションが underlay と overlay のどちらに属するか」が
決められず、役割単位のエントリでは表現できない。

| 案 | BGP エントリの単位 | underlay / overlay の表現 | 単一セッション複数 AF | D6 との関係 |
|---|---|---|---|---|
| **D8-a (採用)** | VRF ごとのインスタンス | 構文に入れない。AF から導く | 書ける | 矛盾しない |
| D8-b | 役割 (`role: underlay \| overlay`) | エントリの `role` | 書けない | underlay と overlay が同じ default VRF のエントリ 2 つになり、「同一 VRF に 1 エントリ」「同一ノード・同一 VRF で AS は 1 つ」と衝突する |

試し書き (`evaluations/adr0010/d8-r3/`) では、D8-a で C1〜C7 の 7 ケースすべてを書けた。D8-b は C1 (D6 と衝突) と
C2 (1 本で 2 つの AF を運ぶセッションをどのエントリにも入れられない) で破綻した。

#### underlay / overlay は BGP セッションの性質ではない

overlay の BGP セッションも、overlay (VXLAN トンネル) の中に張るのではなく、**underlay の IP 網の上でループバックどうしに張る
TCP 接続**である。overlay と呼ぶのは、運ぶ中身が overlay を作るための情報 (EVPN 経路) だからである。
BGP セッションには互いに独立した 3 つの性質があり、どれも構文の別の場所に書かれる。

| 性質 | 例 | 書く場所 |
|---|---|---|
| 何を運ぶか | `ipv4_unicast` / `l2vpn_evpn` | セッションの `address_families` |
| どこを通って張るか | single-hop (リンク上) / multihop (ループバックどうし) | `update_source` の L3 IF から導く (D3) |
| AS の関係 | eBGP / iBGP | 両端の AS (D4) |

「underlay / overlay」は最初の 2 つをざっくり束ねた呼び名であり、方式名を構文に入れない ADR-0005 問い 4 に従って構文には持ち込まない。
人やツールが知りたいときは、AF と VRF から次のように導く。

| セッション | 呼び名 |
|---|---|
| `l2vpn_evpn` / `vpnv4` / `vpnv6` を運ぶ | overlay の情報を運ぶセッション |
| default VRF のインスタンスで、`ipv4_unicast` / `ipv6_unicast` だけを運ぶ | underlay の経路を運ぶセッション |
| 上の両方を運ぶ (1 本で ipv4 と evpn) | 両方 |
| default 以外の VRF のインスタンスで、`ipv4_unicast` / `ipv6_unicast` を運ぶ (VRF-lite の外部接続等) | どちらでもない (テナントの経路) |

導き方は informative として `docs/exporter-cytoscape.md` に書く。ndl-viz の絞り込みは AF (と VRF) で行う。
`ipv4_labeled_unicast` (RFC 8277) 等は AF の値域とあわせて扱う (未解決事項 3)。

#### 範囲外

Junos の logical-systems、IOS-XR の BGP multi-instance (`router bgp N instance X`) のように
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

`protocols.bgp[].role` (廃止。AF から導く)、`neighbors[].type` / `remote_as` (廃止。両端の AS から導く) にも、
代わりの書き方を示すエラーを返す。`routing_adjacencies[].attaches_to` は移動先に持っていかない (通り道は `update_source` から導く。D3)。

既存 fixture の書き換えで `router_id` を書く場合は、ADR-0016 に従う。

## Consequences

### 良い影響

- **案P が構造的に解消する**: セッションを書ける場所が 1 箇所になり、二重表現も相互検証の必要もなくなる
- 「プロトコル抜きの論理構成図」が `control_plane` を 1 キー落とすだけで得られる
- IS-IS / OSPF が BGP と対称に扱える。IS-IS に `update_source` を書くミス、OSPF と IS-IS の参照先の取り違えが型で弾かれる
- F4 のような AS 矛盾が validator で検出される
- CLAUDE.md の誤った `router_id` 検証規則が解消する (ADR-0016 とあわせて)
- 記述が短くなる。`valid_full_dc.yaml` の制御プレーン部分は 35% 短くなり (1 本で複数 AF を運ぶ形に書き直す場合。D8 の帰結)、
  `examples/eveng-evpn-lab-extended.yaml` は 159 行が約 55 行になる (`evaluations/adr0010/r3/R_extended_control_plane.yaml`)
- **ビューアーがセッションを 1 本ずつ描ける。** エクスポーターは 1 セッションを 1 本の辺として出し、両端の機器・L3 IF・IP・AS、
  eBGP / iBGP、AF、VRF、single-hop なら通るリンク / LAG を載せる。どの値も参照をたどるだけで決まり、推定は要らない (下記)
- セッションの通り道を書かないので、`update_source` と通り道の食い違い (ループバックで張りながらリンクを指す等) が構造上起きない

### 悪い影響 / トレードオフ

- **破壊的変更**。3 fixture (`valid_full_dc` / `valid_multi_vlan` / `valid_multisite_wan`) と
  `tests/test_phase2.py` の書き換えが必要
- **`valid_full_dc.yaml` は単純な移植では直らない** (F4)。AS 設計を決め直す必要がある:
  - (i) 1 本の eBGP セッションで `[ipv4_unicast, l2vpn_evpn]` を運ぶ。Cumulus / FRR で標準的な構成で、RFC 7938 の方針と整合する
  - (ii) underlay は直結の eBGP、overlay はループバックどうしの eBGP multihop と、2 本に分ける (`evaluations/adr0010/r3/C1`)。
    RFC 7432 / RFC 8365 は EVPN のセッションを iBGP に限っておらず、Arista EOS や Cisco NX-OS の設計ガイドが紹介する選択肢の 1 つである。
    `examples/eveng-evpn-lab.yaml` もこの形である。r2 の「ベンダー / RFC いずれも推奨していない」は誤りだったため取り消した
  - (iii) underlay を IGP (OSPF / IS-IS) にし、全ノード同一 AS で iBGP EVPN overlay (spine を RR) にする。
    Cisco の従来の EVPN 構成などで広く使われ、RFC 8365 の RD / RT モデルに自然に合う
  - どれを選ぶかは構成の選択であり、本 ADR は推奨順を決めない
- multihop のセッション (overlay 等) が「どの underlay の経路を通るか」は表現できない (ECMP で複数のリンクを通りうる)。
  ndl-viz が overlay セッションを underlay リンクに重ねて描くことはできない。Phase 3 で `carried_by` 等を検討
- SVI 上のセッション (vPC ペア間の iBGP 等) は、通り道が 1 本に決まらないので multihop と同じ扱いになる (D3)。
  peer-link の LAG の上を流れることは、VLAN のポートからたどれば分かるが、セッションの通り道としては導かない
- `update_source` を書かないセッションは、通り道も両端の IP も分からない。書くことを推奨する
- per-neighbor の `ebgp-multihop` / `next-hop-unchanged` 等は書く場所がない。ADR-0005 D3-2 のとおり上位ツールに委ねる
  (eBGP で通り道が multihop と導かれれば、multihop の設定が要ることは分かる)
- **管理外のピアの書き方が 2 通りある** (機器を `layer1` に置くか、端点に `address` と `local_as` を書くか。D3・D4)。
  トンネルの `destination_interface` / `destination_ip` (ADR-0011 D6) と同じく、「相手の機器をトポロジーに書いたか」で使い分ける
- unnumbered のセッションは、トポロジーの記述からは両端の IP が決まらない (相手の IPv6 リンクローカルは実行時に決まる)。
  ビューアーは IF の名前と「unnumbered」を出す。FRR の `v6only` (IPv4 経路を運ばない) とそうでないモードは区別できない (未解決事項)
- micro-BFD (RFC 7130、LAG メンバー単位) は `bfd[].nodes` の粒度では表現できない。Phase 2 議題に残す
- **OSPF / IS-IS はポイントツーポイント前提**とする。マルチアクセスセグメント (OSPF の DR / BDR、IS-IS の DIS) では
  DROther 同士は 2-Way 止まりで Full にならず (RFC 2328 §10.4)、N 台を 2 端点の組に展開すると意味論が壊れ、
  組数も N(N-1)/2 に膨らむ。セグメントを 1 エンティティとして持つ表現を Phase 3 で設計する。
  DC ファブリックでは Ethernet 上でも point-to-point で運用するのが一般的 (RFC 7938) であり、当面の実害は小さい

### エクスポーターがセッションの辺に載せるもの

ndl-viz は推定しないので、エクスポーターが参照をたどって値を決めてから出す。1 セッション = 1 本の辺である。
現行の `routing_adjacency` と `bgp_session` の 2 種類の辺 (1 組に最大 6 本) は、この 1 種類に置き換わる。

```json
{"id": "bgp-peer-spine1-leaf1", "type": "routing_neighbor", "protocol": "bgp",
 "source": "spine1", "target": "leaf1",
 "instance": "bgp-default", "vrf": "vrf-default",
 "from": {"node": "spine1", "l3_interface": "spine1-e1-1-l3", "interface_name": "Ethernet1/1", "ip": "10.0.0.0/31", "local_as": 65000},
 "to":   {"node": "leaf1",  "l3_interface": "leaf1-e1-1-l3",  "interface_name": "Ethernet1/1", "ip": "10.0.0.1/31", "local_as": 65001},
 "bgp_type": "ebgp",
 "address_families": ["ipv4_unicast"],
 "path": {"link": "link-spine1-leaf1"},
 "bfd": false}
```

| 値 | たどり方 |
|---|---|
| 両端の IP | `from` / `to` の `update_source` → その L3 IF の `ip` / `ipv6`。アドレスがなければ出さない (unnumbered) |
| 両端の AS | `instance` のエントリの `nodes[]` の `local_as`。トポロジー外の端は端点の `local_as` |
| eBGP / iBGP | 両端の AS が同じかどうか (RFC 4271 の定義。推定ではない) |
| AF | セッションの `address_families` |
| VRF | `instance` のエントリの `vrf` (省略なら default) |
| 通り道 (`path`) | 両端の `update_source` の L3 IF から導く (D3 の表)。single-hop ならリンク / LAG、multihop・不明なら出さない |

- `bgp_type` は現行の `bgp_session` 辺と同じフィールド名を引き継ぐ。`interface_name` は L3 IF の機器上の名前 (`name`) で、既存の辺の `source_if` と同じ種類の値
- 通り道は YAML の `attaches_to` ではなく導出した値なので、辺のフィールド名も `path` にして区別する
- これらの値は `derive.py` の 1 つの関数 (例: `routing_session_views(topology)`) で求め、validator (AS・VRF・通り道の検査) と
  エクスポーターが同じ関数を使う。validator が見ている値と ndl-viz に渡る値が一致する
- **トポロジー外の相手とのセッションは辺にせず、ノードのデータに載せる。** トンネル (`cytoscape.py` の tunnels) と同じく、
  両端の `node` が決まるときだけ辺を出し、片方がトポロジー外なら、こちら側のノードの `data["external_bgp_sessions"]` にだけ入れる
- 形の詳細は実装時に `docs/exporter-cytoscape.md` に書く

### 影響を受けるコンポーネント

- スキーマ: `src/mlndl/schema/protocols.py` → `control_plane.py` に再編、`layer3.py` から `RoutingAdjacency` / `RoutingAdjEndpoint` を削除、`topology.py`
  - `BgpSession` / `OspfAdjacency` / `IsisAdjacency` は `isinstance` 分岐用に公開する (`LacpLag` / `MlagLag` と同じ需要)
  - `__init__.py` の `__all__` は現在スキーマ型を公開していないため、公開 API の破壊はない
- バリデーター: `src/mlndl/validator.py` (routing_adjacencies 検証・`_validate_protocols`・`_check_conventions` のパス)
- 参照の宣言: `src/mlndl/schema/refs.py` の `COLLECTION_LABELS` に `control_plane.bgp` / `ospf` / `isis` / `routing_neighbors` を足す。
  `tests/test_refs.py` の `SCHEMA_MODULES` に新しいモジュール (`control_plane`) を足す。セッションに `attaches_to` がなくなるので、
  `KEYED_REFERENCES` から routing_adjacencies の行を外す (ADR-0015。宣言漏れはこのテストが検出する)
- 導出: `src/mlndl/derive.py` にセッションの値 (両端の IP・AS・eBGP / iBGP・VRF・通り道) を求める関数を置く
- エクスポーター: `src/mlndl/exporter/cytoscape.py` の routing_adjacencies / bgp の出力 (上記のセッションの辺に置き換える)、`docs/exporter-cytoscape.md`
- ndl-viz: BGP の線をセッションごとにし、両端に IP と AS、中央に eBGP / iBGP と AF を出す。絞り込みは AF で行う
- サンプル: `tests/fixtures/valid_full_dc.yaml` / `valid_multi_vlan.yaml` / `valid_multisite_wan.yaml`、
  `examples/eveng-evpn-lab.yaml` / `eveng-evpn-lab-extended.yaml`。
  現行 fixture にはループバックを `update_source` にしながら `attaches_to: {link:}` を書いたセッションがあり、移行で `attaches_to` を落とす。
  `examples/eveng-evpn-lab.yaml` の `role: route_server` / `route_server_client` の扱い (RR のフラグに寄せるか、注釈にとどめるか) は移行時に決める
- テスト: `tests/test_phase2.py`、`tests/test_validation_severity.py` (隣接プレフィックスのテスト)
- 文書: `CLAUDE.md` (YAML 例・バリデーション表・attaches_to の表・ディレクトリ構造)、ADR-0005 (D1・D3-1。unnumbered の判定規則の置き換えを含む)、
  ADR-0001 (D2 の例・D8 の表から routing_adjacencies を外す)、ADR-0002 D7 の備考、ADR-0016 (router_id の置き場所を `control_plane` に)、
  ADR-0003 / drafts 内の `routing_adjacencies` / `protocols` への言及。ADR-0001・0005・0016 は本 ADR の Pass C と同時に改訂する

## Alternatives Considered

- **案C** *(採用案)*: トップレベル `control_plane` にセッションとインスタンス設定を集約
- **案A 現状維持**: 却下 — F2〜F6 がすべて残る。ndl-viz は 2 箇所をフィルタする必要がある
- **案B セッションを `protocols` 配下へ移すだけ**: 構造は案C と同じだが、`protocols` という補集合的な名前が残る
- **案D RFC 8345 の `networks:` リストに一般化**: 却下 — 型が退化し、全 fixture の書き換えになる。
  RFC 8345 との対応はエクスポーターで担保する現行方針 (ADR-0005 Alt-4) を維持
- **案E OpenConfig 方式 (`layer3.vrfs[].protocols[]` にネスト)**: 却下 — IETF / OpenConfig / Batfish の業界モデルだが、
  YAML で書き比べたところ underlay eBGP を「default VRF に属する」と書かされる層の反転が起き、
  手書きの記述言語として読みにくい。BFD の置き場所も定まらない。
  案E が自然に持つ「セッションがどのインスタンスに属するか」の情報は、フラット構造のまま `instance:` 参照で得る (D3)
- **`layer3.routing_adjacencies` を RFC 8346 の `l3-link` として正当化し現状維持**: RFC 8346 は `l3-link` を定義しており、
  BGP セッションを L3 トポロジー上のリンクと写像する解釈には根拠がある。しかし F3 (同一ノード対の複数セッション) と
  F5 (IS-IS は IP を使わない) を説明できないため却下
- **インスタンスエントリ内にセッションをネスト (`control_plane.bgp[].sessions[]`)**: 同一ノード対の区別が
  エントリで自然に付く利点はあるが、プロトコル横断でセッションを列挙する (ndl-viz の制御面グラフ描画) には
  全エントリを巡回する必要がある。フラットな `routing_neighbors` + `instance:` 参照で同じ区別が得られるため却下
- **`remote_as` を「省略可・明示時は整合検証」として残す**: 管理外ピアを表現できる利点があるが、
  管理外ピアは `layer1` ノード + `local_as`、またはトポロジー外の端点の `address` + `local_as` で表現でき (D3・D4)、
  残すと F4 と同型の二重表現が戻る。却下
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
- **D8-b: BGP エントリを役割 (`role: underlay | overlay`) 単位にする**: 却下 — D8
- **underlay / overlay を `labels: {fabric_role: underlay | overlay}` で書く** (r2 の案): 却下 — AF から導ける事実を 2 か所に書くことになり、
  食い違い (「overlay と書いたが EVPN を運んでいない」) が検査されずに通る。また labels (ADR-0009) はノードの構成子で、
  セッションに付けるには ADR-0009 の拡張が要る
- **インスタンスを指すフィールドを `process` のままにする** (r2): 却下 — Terms の「インスタンス」と字面がずれ、OS のプロセスと紛れる。
  RFC 8349 は routing instance と呼ぶ
- **`update_source` を `local_address` (OpenConfig) / `source` に改名**: 却下 — `local_address` はアドレスを前提とする語で unnumbered と合わない。
  `source` はトンネルの `source` と紛れる。`update_source` は IF を指す語で、unnumbered でも意味が崩れない
- **unnumbered を、端点の `unnumbered: true` か、L1 IF を指す `update_source` で表す**: 却下 — `update_source` の参照先が 2 種類になる。
  アドレスを持たない L3 IF を指せば足りる
- **管理外のピアは必ず `layer1` に機器を置き、L3 IF を書く** (r2): 却下 — IP と AS しか分からない相手のために、形だけの機器・IF・リンクを作ることになる
  (`evaluations/adr0010/d8-r3/C6`)
- **single-hop / multihop、`ebgp-multihop` をセッションのフィールドにする**: 却下 — ADR-0005 問い 4 (方式名は構文に入れない)。`update_source` の L3 IF から導ける
- **セッションに `attaches_to: {link:} | {lag:}` を書く** (r2 は `{node:}` / `{interface:}` / `{link:}`、r3 は `{link:}` / `{lag:}`): 却下 —
  `update_source` の L3 IF の `attaches_to` から導ける事実を 2 か所に書くことになる。さらに MLNDL の LACP の LAG は機器ごとに 1 つなので、
  2 台の間の port-channel では LAG が 2 つあり、どちらを指すかが決まらない (`evaluations/adr0010/r3/C5`)。
  SVI 上のセッションはそもそも通り道が 1 本に決まらない
- **端点を `BgpInternalEndpoint | BgpExternalEndpoint` の 2 つの型の Union にする**: 却下 — D3 (エラーが具体的にならない)
- **端点の相手の AS を `peer_as` / `remote_as` と呼ぶ**: 却下 — インスタンスの `nodes[].local_as` と同じく「その機器自身の AS」を表す値なので、
  同じ `local_as` にそろえる。`remote_as` は記述する側から見た相対的な値として廃止した語である (D4)
- **AF をインスタンスのノードにも書けるようにする (ピアグループ的な既定値)**: 却下 — D4

## 未解決事項 (Pass C で確定)

1. ~~D8: BGP エントリの単位~~ → 2026-11-01 にユーザーが決定 (VRF ごとのインスタンス)
2. `bfd: bool` を `bfd: <bfd プロファイル id>` の参照に変えるか (RFC 9127 は BFD を独立モジュールとし、BGP から augment する)。
   本 ADR では決めない。micro-BFD の対応と合わせて別 ADR で扱う
3. `AddressFamily` の値域 (現行: `ipv4_unicast | ipv6_unicast | l2vpn_evpn | vpnv4 | vpnv6`)。
   RFC 5549 / 8950 (IPv6 ネクストホップで IPv4 NLRI) を区別するか (network-tech-reviewer は別 AF にせず `ipv4_unicast` の付記で足りるとする)。
   表示名 (`L2VPN EVPN` 等) との対応はエクスポーター側に置く
4. OSPF `area` をセッション側に置くか、インスタンスエントリのノード側に置くか (複数セッションが同じ area を共有すると冗長)
5. multihop のセッションが通る underlay の経路 (ECMP で複数のリンク) を表す `carried_by` 等 (Phase 3)
6. per-neighbor の `local-as` (AS を統合する移行中の構成) を書けるようにするか。当面は範囲外 (D4)
7. FRR の unnumbered の `v6only` (IPv6 リンクローカルだけで、IPv4 経路を運ばない) とそうでないモードを区別するか。AF の値域 (3) とあわせて扱う
8. `address_families` を省略したとき (未指定) と空リスト (何も運ばない) を区別するか

## r3 からの変更 (2026-11-01。r3 の Pass B を反映)

| 変更 | 出所 | 内容 |
|---|---|---|
| **セッションの `attaches_to` を廃止し、通り道を導く** | example-author / network-tech-reviewer の指摘から統合 → ユーザー決定 | `update_source` の L3 IF から導く表を D3 に追加。LAG が 2 つあると決まらない問題・SVI 上のセッションの問題・二重表現が解消 |
| D2 の「プロセス → 隣接」 | linguist | 「インスタンスごとの設定 → セッション」 |
| Terms の「インスタンス」 | spec-architect | 「ある 1 つの VRF の、そのプロトコルのインスタンスを全ノード分まとめた 1 エントリ」と明記。「トランスポートのアドレスファミリー」を追加 |
| 端点の型の設計意図 | dsl-designer | 1 つの型 + `model_validator`。2 つの型の Union にしない理由を D3 に |
| 端点の `local_as` / `address` の注記 | linguist | 「その端の相手自身の AS」「相手のホストアドレス (VTEP の `address` とは別物)」 |
| unnumbered の定義 | network-tech-reviewer / example-author | 「`ip` も `ipv6` もない」と明記。表示はセッションが指すときだけ。IPv6 のグローバルアドレスの IF は unnumbered ではない |
| D6: EVPN / VPN の AF を default 以外の VRF に書く検査 | network-tech-reviewer | error → warning (`--strict` で error) |
| D6: AF の一致の検査 | network-tech-reviewer | 「トランスポートのアドレスファミリー」と明記 |
| D6: 検査を追加 | example-author / spec-architect / dsl-designer | update_source の VRF とインスタンスの VRF の一致、OSPF / IS-IS の端点の機器の一致、通り道の食い違い、RR クライアントは iBGP、重複は L3 IF の id で判定 |
| D6: router_id の行 | spec-architect | ADR-0016 への参照に (二重定義の解消) |
| D7: 区別の語の位置 | linguist / spec-architect | ノード対の後ろ (末尾) に付ける。`bgp-peer-spine1-leaf1-evpn`。「AF 名を入れない」は 1 本で複数 AF を運ぶ場合に限ると書き分け |
| D8: underlay / overlay の導き方 | network-tech-reviewer | VRF の軸を加えて 4 分類 (テナントの経路はどちらでもない) |
| Consequences: EVPN の構成の書き方 | network-tech-reviewer | 推奨順を決めない中立の書き方に。eBGP multihop の overlay は RFC 7432 / 8365 の範囲内で Arista EOS / Cisco NX-OS の設計ガイドが紹介する選択肢 |
| Consequences: 導出の共有と出力の形 | dsl-designer / linguist | `derive.py` の関数を validator とエクスポーターで共有。トポロジー外は `external_bgp_sessions`。`from.name` → `interface_name`、通り道は `path` |
| 位置づけ・影響範囲 | spec-architect | ADR-0001 (D2 の例・D8 の表)・ADR-0005 D3-1 (unnumbered)・ADR-0016 を改訂対象に。Pass C で同時に改訂 |
| 参照の宣言のテスト | dsl-designer | `test_refs.py` の `SCHEMA_MODULES` / `KEYED_REFERENCES` の更新を影響範囲に |
| D4: ノードエントリの型・VRF ごとの `local_as` | dsl-designer / example-author | 固有の型にする。VRF ごとに `local_as` を書く理由を注記 |

**採らなかった指摘**:

- `bgp_type` を `session_type` に改名 (linguist): 現行の `bgp_session` 辺が既に `bgp_type` を出しており、ndl-viz も使っているため引き継ぐ
- `{lag:}` は「両端のどちらかの LAG を指せばよい」と決める (example-author): セッションの `attaches_to` 自体を廃止したため不要になった

## r2 からの変更 (2026-11-01。D8 の決定と 5 エージェントの検討を反映)

| 変更 | 出所 | 内容 |
|---|---|---|
| **D8 を決定** | ユーザー / 5 エージェント一致 | VRF ごとのインスタンス。`BGPProcess.role` を廃止 |
| underlay / overlay の扱い | spec-architect / linguist / ユーザー | 構文に入れず AF から導く。r2 の `labels: {fabric_role}` 案は却下 (Alternatives) |
| `process` → `instance` | linguist / spec-architect | Terms・RFC 8349 と字面をそろえる (D3) |
| トポロジー外の相手 | network-tech-reviewer / example-author | 端点に `address` + `local_as` を書ける (D3・D4)。トンネルの `destination_ip` と同じ形 |
| unnumbered の判定 | network-tech-reviewer | 「loopback でない IF」→「アドレスを持たない L3 IF」(D3) |
| `attaches_to` のキー | dsl-designer / example-author | `{link:}` と `{lag:}`。`{node:}` / `{interface:}` は外す (D3)。**r4 でセッションの `attaches_to` 自体を廃止** |
| 参照の検査 | dsl-designer / spec-architect | ADR-0015 の `Ref` 宣言にし、D6 の表から参照先の存在の検査を外す |
| `router_id` | spec-architect | ADR-0016 に委ねる (D5) |
| D6 に検査を追加 | network-tech-reviewer / dsl-designer | 端点の形、update_source の機器、トポロジー外の端の AF、attaches_to の端 (r4 で通り道の食い違いに置き換え)、セッションの重複、default 以外の VRF での EVPN / VPN の AF |
| 同じ組の 2 本目の ID | example-author | 意味の分かる語を入れる例を推奨に (D7) |
| 単一セッション複数 AF を基本に | — | D8 の典型として記述。underlay と overlay を別セッションにする構成も書ける |
| エクスポーターの出力の形 | dsl-designer / spec-architect | Consequences に追加 (1 セッション = 1 辺) |
| VTEP の記述 | spec-architect | `vtep_source` / `members` から ADR-0014 の `layer2.vteps` に (D2 の表) |
| eBGP multihop の overlay | (統合時) | 「推奨されていない」を取り消し、Pass B で確認 (Consequences) |

## r1 からの変更 (5 エージェントレビュー反映)

| 指摘 | 出所 | 対応 |
|---|---|---|
| **D3 が ADR-0006 を逆に引用していた** (ADR-0006 は L3 の `from`/`to` 有向維持を明記) | spec-architect | 有向維持に訂正。ADR-0006 は改訂しない |
| **セッションがどのインスタンスに属するかの参照がない** (D8-a と組み合わせると AS 照合先が決まらない) | dsl-designer | `process:` を追加 (D3・D6) |
| **配置基準の削除テストが `vxlan.members` / `vrfs.route_targets` で破綻** (当時の構造。`members` は ADR-0014 で `vteps` に置き換わった) | spec-architect | 基準を「セッションか、要素の属性か」に置き換え (D2) |
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

- 関連 ADR: ADR-0001 (D8), ADR-0002 (D2・D6・D7), ADR-0005 (D1・D3-1・D3-2・D3-3・D4・D4 補則・Alt-4), ADR-0006, ADR-0009, ADR-0011 (D6・D11),
  drafts/0014, drafts/0015, drafts/0016
- 実証 YAML: [`evaluations/adr0010/`](../evaluations/adr0010/README.md) — `layering/` (構造案の比較)、`draft-r1-syntax/` (r1 構文による書き直し)、
  `d8-r3/` (D8 の比較と r3 の論点。C1〜C7)、`r3/` (r3 の構文による書き直しと Pass B の実証)
- RFC 4271 (BGP-4) §1.1・§3・§8 / RFC 6286 (BGP Identifier) §2.1・§2.2 / RFC 4760 (MP-BGP) / RFC 4456 (Route Reflection) / RFC 5065 (Confederation)
- RFC 2328 (OSPFv2) §1.2・§4.3・§10・§10.4・App. A.1 / RFC 5340 (OSPFv3) §2.2・App. A.1
- ISO/IEC 10589 (IS-IS) / RFC 1195 / RFC 5305 / RFC 6119 / RFC 9130 (`ietf-isis`)
- RFC 5881 §4 / RFC 5883 §5 / RFC 7130 §2.2 (BFD) / RFC 9127 (BFD YANG)
- RFC 5798 (VRRPv3) §5.1.1.4・§5.1.2.4 / IEEE Std 802.3 Annex 57A / IEEE 802.1AX (LACP)
- RFC 4364 (BGP/MPLS IP VPN) / RFC 7432・RFC 8365 (EVPN) / RFC 7938 (BGP in Large-Scale Data Centers)
- RFC 7426 (SDN Layers and Architecture Terminology)
- RFC 8345 (Network Topologies) §1・§4.1 / RFC 8346 (L3) / RFC 8944 (L2) / RFC 8349 (`ietf-routing`)
- OpenConfig `openconfig-network-instance`
