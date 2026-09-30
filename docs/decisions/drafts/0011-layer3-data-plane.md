# ADR-0011: layer3 データプレーンの確定

- **Status**: Draft — **D3〜D7・D9・D10 実装済み (2026-10-01)**。D8 (ADR-0005 の同期) は未着手
- **Date**: 2026-09-20
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **Pass**: A r2 (初回策定 → 5 エージェントレビュー反映。差分は末尾「r1 からの変更」)
- **関連**: ADR-0001 (attaches_to), ADR-0002 (ID 命名), ADR-0005 (表現スコープ), ADR-0006 (endpoints), ADR-0009 (labels), drafts/0010 (制御プレーン・保留中)

### 位置づけ

本 ADR は **ADR-0005 の部分改訂**であり、置き換えではない。ADR-0005 の三側面・D4 判定フレームワークは維持する。
対象は **データプレーンの layer1 / layer2 / layer3** に限る。制御プレーン (BGP / OSPF / IS-IS / BFD) は
ADR-0010 で保留中であり、本 ADR は触れない。

ユーザー決定 (2026-09-20):

1. **スタティックルートはスコープ外**。「経路情報は含めない」という既存の合意に従う (D1・D2)
2. **トンネルインターフェースはスコープ内** (D6)
3. **デュアルスタックは `ip` = IPv4 / `ipv6` = IPv6。いずれも単数** (D5)

## Terms

| 用語 | 本 ADR での意味 |
|---|---|
| **フィールド** | pydantic モデルの属性 (例: `L3Interface.ip`) |
| **エンティティ** | 独立した ID を持つオブジェクト (`L3Interface` / `TunnelInterface` / `VRF` 等) |
| **データプレーン** | 転送そのものに関わる要素 (IP / VLAN / VNI / VRF / SVI / VIP)。制御プレーン (ADR-0010) の対語 |
| **RIB** | Routing Information Base。個別経路の集合。本 ADR ではスコープ外 (D2) |
| **SVI** | VLAN に対応する L3 インターフェース (Switched Virtual Interface) |
| **VIP** | Virtual IP。VRRP / HSRP / anycast gateway が応答するアドレス |
| **AF (アドレスファミリー)** | IPv4 または IPv6 |
| **anycast gateway** | 全ノードが同一の IP / MAC で同時に応答する分散ゲートウェイ (RFC 9135)。プロトコル交換を伴わない |

## Context

「layer3 までを表現できるのか確定させたい」という問いに対し、5 エージェントで現行スキーマを評価し、
代表的な 5 トポロジー (キャンパス 3-Tier / DC EVPN / 支社 router-on-a-stick / デュアルスタック / vSphere) を
試し書きした。結果は「**条件付きで表現できるが、確定とは言えない**」だった。

### F1. 書けるもの / 書けないもの

5 本とも `validate` は通ったが、これは書けない要素を `# 書けない:` のコメントとして残した結果であり、
コメントは合計 27 箇所あった。

| | 内容 |
|---|---|
| 書ける | L1 全般、VLAN / VxLAN、VRF、SVI、VRRP、EVPN Symmetric IRB のデータプレーン |
| 書けない | トンネル、サブインターフェースの 802.1Q タグ、1 IF への IPv4 + IPv6、anycast gateway の明示 |

実証エージェントの要約が正確である: **「L3 のデータプレーン (ヘッダ空間) は書けるが、L3 の到達性情報 (RIB) は書けない」**。
後者のうちスタティックルートは D1 の原理により**書かない**と確定した (D2)。

### F2. 矛盾が黙って通る (実測)

書けない要素より重い。以下はいずれも `OK — no validation errors` になる。

| 書いた内容 | 結果 |
|---|---|
| `interface: vlan-999` と `vlan: vlan-100` を同時に書く (食い違い) | 通る |
| `ip: not-an-ip-address` / `ip: 10.0.0.1/33` | 通る |
| leaf1 の L3 IF が `attaches_to` で leaf2 の物理 IF を指す | 通る |
| leaf1 の `trunk_ports` が leaf2 の IF を指す | 通る |

ADR-0010 の F2〜F4 で見つけた「二重表現が相互検証されず矛盾が通る」問題が、L3 にもあった。

### F3. ADR-0005 D2-2 の SVI 規範が実装と一致していない

| ADR-0005 D2-2 の規範 | 実装の挙動 |
|---|---|
| B-1 `interface: vlan-100` は `layer2.vlans` を暗黙参照し、存在しなければ error | **参照していない** (`vlan-999` でも通る) |
| B-2 `attaches_to: {interface: vlan-100}` は生成系の**正規形** | **error になる** (`_check_attaches_to` が `layer1.interfaces` の ID しか見ない) |
| (規定なし) | 実装だけに `vlan:` フィールドがあり、fixture は実際にこれを使っている |

**ADR が正規形と定めた書き方が validate を通らない。** NetBox アダプターを書いた時点で破綻する。

### F4. IP アドレスに形式検証がない

`L3Interface.ip: str` は任意の文字列を受ける。`exporter/cytoscape.py` は
`try: ipaddress.ip_interface(...) except ValueError: pass` で握りつぶすため、**エクスポートは成功し、
その VLAN のサブネット情報が警告なく図から消える**（実測。export は exit 0）。落ちるより気づきにくい。

### F5. ADR-0005 D3-1 の表が実装と乖離している

`port_channels` / `mlag` → 実装は `lag` (統合済み)、`links.from/to` → `endpoints` (ADR-0006)、
`gateway_redundancy` → 実装は `fhrp`、`description` は Phase 1 表にあるのに未実装、
`MlagLag.system_mac` は D3-2 で「Phase 2 に再判断」とされたまま実装済み。

## Decision

### D1. 表現原理 — 関係の成立に必要な情報は書き、関係を流れる個別経路は書かない

mlndl は「VRF が存在する」「この SVI がゲートウェイである」「このセッションが張れる」といった
**関係の成立条件**を記述する。その関係を通じて運ばれる**個別の経路情報 (route entries)** は記述しない。

| 書く | 書かない |
|---|---|
| `layer3.interfaces` の IP (到達性の起点) | スタティックルートの宛先とネクストホップ |
| `layer3.vrfs.route_targets` (VPN 境界の定義、RFC 4364) | per-VRF の redistribute ポリシー |
| `gateway_redundancy` の VIP (ゲートウェイの所在) | ホストのルーティングテーブル |

この原理は ADR-0005 D4 を置き換えない。**D4 が「混在」を返したときの解決指針**として働く。
D4 が 4 軸すべて Yes を返す概念は引き続きスコープ内である。

混在時の判定手順:

1. それを削除すると、その関係自体が存在できなくなるか (Route Target は Yes、スタティックルートは No)
2. 数が構造的に上限を持つか (Route Target は数個、経路は数万本)
3. データプレーンの構造そのものが変わるか

### D2. スタティックルートはスコープ外

`layer3.static_routes` に相当する構成子は作らない。ADR-0005 D3-2 のスコープ外表に追加する。

| 概念 | 行き先 |
|---|---|
| スタティックルート / デフォルトルート / redistribute / network 文 / prefix-list | 上位ツール (Ansible / NetBox config context) |

**ホストのデフォルトゲートウェイ**は、同一サブネットの SVI の `ip` または `gateway_redundancy.vip` から
導出できるため、表現力の欠落にはならない。

> 5 エージェントのうち 4 つは「スタティックルートを入れる」と判定した (到達性が書けなくなるという理由)。
> ユーザーは D1 の原理との整合を優先し、スコープ外と決定した。本 ADR はその判断を採る。

### D3. SVI の表現を 1 つに統一する

`L3Interface` の 3 つの参照手段を整理する。

| フィールド | 変更後の位置づけ |
|---|---|
| `interface` | **機器上の名前** (`swp51` / `Vlan100` / `lo`)。設定生成と表示に使う。**参照解決には使わない** |
| `vlan` | **廃止** |
| `attaches_to` | **唯一の参照手段**。`{interface: <L1 IF id>}` または `{interface: <VLAN id>}` |

- **`_check_attaches_to` の参照先を広げるのは `L3Interface.attaches_to` に限定する。**
  このヘルパーは `L1Node` / `L1Interface` / `L3Interface` / `RoutingAdjacency` の 4 箇所から呼ばれており、
  無条件に `layer2.vlans` を足すと「物理ポートが VLAN の上で実現される」といった無意味な参照が通ってしまう。
  呼び出し側から許可する ID 空間を渡す形にする
- **B-1 短縮形は維持するが、正規化して格納はしない。** `attaches_to` が未指定で `interface` が `^vlan-\d+$` に
  マッチする場合、**validator の内部でだけ** `{interface: <その値>}` として参照解決する。
  モデルに書き戻すと、入力になかった `attaches_to` がエクスポート出力に現れ、YAML の往復が壊れる
  (`exporter/yaml.py` は `model_dump(mode="json", exclude_none=True)` で全フィールドを出力するため)
- 明示された `attaches_to` と、`interface` から解決した参照が**食い違う場合は error**
- **短縮形が使えるのは `^vlan-\d+$` だけ**とする。`Vlan100` や `br0` のような機器上の名前は参照解決しない。
  この場合は `interface: Vlan100` と `attaches_to: {interface: vlan-100}` を併記する
  (機器上の名前を保ったまま参照も書ける)
- `interface` が VLAN を示すらしい名前 (大小文字を無視して `vlan` を含む) なのに `attaches_to` が未指定の場合は
  **warning**。SVI のつもりで書いて VLAN に紐づいていない書き方を拾う

> **ADR-0005 D2-2 の改訂**: 同 ADR は「B-1 を推奨し、バリデーターは内部表現を B-2 に正規化する」としていたが、
> 正規化してモデルに格納すると往復が壊れる。「B-1 は validator 内でのみ解決し、格納しない」に改める。
> B-1 の位置づけも「暗黙参照」から「参照を省略できる短縮形」に変わる。

### D4. `fhrp` を `gateway_redundancy` に改め、anycast gateway を表現する

`mode` を discriminator とする Tagged Union にする (`lag` の `LacpLag | MlagLag` と同じ形)。
単一モデルで optional にすると「anycast なのに `group_id` を書いた」が黙って通るため。

```python
class VrrpGateway(BaseModel):
    mode: Literal["vrrp"]
    group_id: int                                  # 1..255 (RFC 5798)
    vip: IPv4Address | IPv6Address                 # IPv6 はリンクローカル必須 (後述)
    priority: int | None = None
    preempt: bool | None = None

class HsrpGateway(BaseModel):
    mode: Literal["hsrp"]
    group_id: int                                  # HSRPv1 0..255 / HSRPv2 0..4095
    vip: IPv4Address | IPv6Address
    priority: int | None = None
    preempt: bool | None = None

class AnycastGateway(BaseModel):
    mode: Literal["anycast_gateway"]
    anycast_mac: str | None = None                 # Cisco の anycast-gateway-mac 等。設定生成に必要
    # vip / group_id は持たない。SVI の ip / ipv6 自体が anycast アドレス

GatewayRedundancy = Annotated[VrrpGateway | HsrpGateway | AnycastGateway, Field(discriminator="mode")]
```

`L3Interface.gateway_redundancy: list[GatewayRedundancy] = []` (現行の `fhrp` と同じ多重性)。

- **`fhrp` という名前をやめる理由**: FHRP は First Hop Redundancy **Protocol** の略で、VRRP / HSRP のように
  プロトコル交換で active を選ぶ方式を指す。EVPN の distributed anycast gateway (RFC 9135) はプロトコルを持たず、
  全ノードが同時に active である。`fhrp.protocol: anycast` はカテゴリの誤りになる
- **値は `anycast_gateway`** とする (`anycast` だと DNS anycast や anycast ルーティング一般と紛れる)。
  ADR-0005 D3-1 の元の記述とも一致する
- **アドレスファミリーのフィールドは作らない**。RFC 5798 §5.2.9 / §6.1 により 1 つの VRRP インスタンスが持つのは
  IPv4 か IPv6 のどちらか一方なので、AF は `vip` の型から判別できる。デュアルスタックの SVI では
  `gateway_redundancy` が IPv4 用と IPv6 用の 2 エントリになる
- **IPv6 の VRRP / HSRP では `vip` はリンクローカルでなければならない**。RFC 5798 §5.2.9 と §6.1 が
  "the first address must be the IPv6 link-local address" と規定している
  (RFC 2119 の大文字 MUST ではなく小文字の must だが、主要ベンダーはいずれも強制する)。
  HSRPv2 for IPv6 にも同じ要件がある。追加のグローバル VIP は本 ADR では扱わない
- **anycast MAC を持てるようにする**。ADR-0005 D3-2 が「Phase 2 で再判断」としていた項目で、
  これがないと下流ツールが設定を生成できない (Cisco `fabric forwarding anycast-gateway-mac`、
  Arista `ip virtual-router mac-address`、Cumulus `address-virtual`)
- **GLBP は対象外**。Cisco 独自で、active/active かつゲートウェイごとに異なる仮想 MAC を配る方式であり、
  3 つの mode のいずれにも写せない

### D5. デュアルスタック — `ip` は IPv4、`ipv6` は IPv6、いずれも単数

```python
class L3Interface(BaseModel):
    ip: IPv4Interface | None = None      # IPv4 (CIDR)。意味論を IPv4 専用に確定する
    ipv6: IPv6Interface | None = None    # IPv6 (CIDR)
```

- 既存 fixture の `ip:` は 23 個すべて IPv4 であり、**この変更で書き換えが必要な行は 0 行**
- 型を `IPv4Interface` / `IPv6Interface` にすることで、F4 の形式検証と、`ip` に IPv6 を書く誤りが
  **parse 時に弾かれる**。`10.0.0.1/33` も弾かれる
- **`ip` と `ipv6` の両方が未指定でも valid** とする。unnumbered や、IP を持たない L2 専用の IF があるため
- **単数で始める**。設計として 1 IF に複数アドレスを割り当てるケース (セカンダリ IPv4、GUA + ULA 併用、
  リナンバリング中の同居、リンクローカルの手動固定) は稀か一時的であり、論理構成図の対象ではない。
  必要になった時点で `ip_secondary` 等の**別フィールドを加算する**。
  `str | list[str]` の Union にはしない (同じ事実を 2 通りに書けるため)

### D6. トンネル — 自己完結した 1 つのエンティティで表現する

```python
class TunnelInterface(BaseModel):
    id: str                                        # 推奨プレフィックス tunnel- (ADR-0002 D7)
    node: str
    type: Literal["gre", "ipip", "ipsec_vti", "wireguard"]
    source: str                                    # layer3.interfaces[].id (トンネルの起点)
    destination_ip: IPv4Address | IPv6Address | None = None    # トポロジー外の対向
    destination_interface: str | None = None                   # layer3.interfaces[].id (トポロジー内の対向)
    ip: IPv4Interface | None = None                # トンネル IF 自体のアドレス
    ipv6: IPv6Interface | None = None
    vrf: str | None = None                         # トンネル IF が属する VRF (overlay 側)
    transport_vrf: str | None = None               # 外側パケットが流れる VRF (Cisco の tunnel vrf)
    mtu: int | None = None
    description: str | None = None
```

- **`tunnel_links` は作らない。** r1 では `layer1.interfaces` + `layer1.links` と同型にしようとしたが、
  これは誤りだった。**L1 のインターフェースは自分の対向を知らない**ので `links` が必要なのに対し、
  **トンネル IF は `source` と `destination` を自分で持つ**ので、リンクを別に書くと同じ事実を 2 箇所に書くことになる。
  ADR-0010 と本 ADR の F2 で問題にした二重表現を、新たに作り込むところだった。
  可視化に必要な「両端を結ぶ辺」は、対になる 2 つのトンネル IF からエクスポーターが導出する
- **`destination` を 2 つのフィールドに分ける**。r1 は `destination: str` に「IP または L3 IF の id」の
  両方を持たせていたが、これは validator が文字列を見て推測することになり、F4 (不正な IP が通る) と同型の問題を生む。
  `destination_ip` と `destination_interface` の**排他**にする (両方指定・両方未指定はいずれも error)
- **`transport_vrf` と `mtu` を持たせる**。前者は overlay の VRF と外側の VRF が別になる構成
  (Cisco の `tunnel vrf`) で必要。後者は GRE で 24 バイト、IPsec ESP で最大 70 バイト強のオーバーヘッドが乗るため、
  設定しないと DF ビット付きの TCP が黙って落ちる。MTU は「関係の成立に必要」(D1) と読める
- **`wireguard` を type に加える**。Linux カーネル標準搭載で、管理プレーンや小規模 overlay での利用が増えている
- **IPsec の暗号化パラメータ (IKE / ESP / PSK) はスコープ外**。ADR-0005 D3-2 の「BGP 認証等の秘匿情報は上位ツール」
  という既存の線引きに従う。D1 の原理だけでは説明しきれない (パラメータは関係の成立条件でもある) ため、
  D3-2 の規範に接続する
- **MSS clamping、mGRE / DMVPN (点-多点)、GRE over IPsec (2 段構成) はスコープ外**
- VxLAN は `layer2.vxlan` のままとし、`tunnel_interfaces` には含めない

### D7. `description` を全構成要素に追加する

ADR-0005 D3-1 の Phase 1 表にありながら未実装だった。全モデルに `description: str | None = None` を足す。
共通基底クラスは作らず、各モデルに個別に定義する (モデルごとに制約を変える余地を残すため)。

`labels` (ADR-0009) との棲み分け: `description` は人間向けの自由記述、`labels` は機械可読の多軸分類。
ADR-0005 D3-1 の「`description` / `comment`」の併記は `description` の 1 語に絞る
(YANG / OpenConfig / RFC 8345 / NetBox / 主要ベンダーがすべて `description`)。

### D8. ADR-0005 D3-1 / D3-2 を実装に同期する

判断の変更ではなく、表と実装のずれ (F5) の解消。ADR-0005 に「実装同期メモ」節を追記する。

| ADR-0005 の記述 | 同期後 |
|---|---|
| `layer1.port_channels` / `layer1.mlag` | `layer1.lag` (type: lacp \| mlag) |
| `layer1.links`: id, from, to | `endpoints` (ADR-0006) |
| `layer3.interfaces[].gateway_redundancy: protocol (anycast_gateway\|vrrp), vip` | `gateway_redundancy: mode (vrrp\|hsrp\|anycast_gateway)` の Tagged Union (D4) |
| `layer3.interfaces`: ip (IPv4/IPv6) | `ip` (IPv4) / `ipv6` (IPv6) (D5) |
| `layer2.subinterfaces`: parent (L1 IF) | `attaches_to: {interface: <L1 IF>}` (下記) |
| `MlagLag.system_mac` は「Phase 2 で再判断」 | 実装済みとして D3-2 から外し、スコープ内に確定 |
| `layer2.vxlan.vtep_source: {layer: layer3, interface_id: ...}` | `vtep_source: str` (L3 IF の ID を直接参照)。`layer` キーは ADR-0001 D2 で廃止済み |
| (なし) | `MlagLag.client_lag` を D3-1 に追記 (実装済みだが ADR に記載がない) |
| `link_role` の推奨語彙 | `trunk` を追加 (`link_role` は既に自由文字列なので、語彙表への追記のみ) |
| `layer3.tunnel_links`: id, from, to (entity/relation の対、P8) | **廃止**。トンネル IF が自己完結するため (D6) |
| (なし) | **ADR-0005 D3-2** にスタティックルート / redistribute / prefix-list をスコープ外として追加 (D2) |

**サブインターフェースの親参照**: ADR-0005 D2-2 ケース C は `parent: <L1 IF>` としていたが、
`parent` は ADR-0009 D1 で Containment (論理階層) に予約された語である。親の物理 IF が落ちればサブ IF も
動作しないので、この関係は Realization であり `attaches_to` が正しい。
加えて ADR-0009 D1 は `parent` の値域を **node の ID** に限定しており、L1 インターフェースを指すのは型としても不適合である。
ADR-0005 D2-2 の記述を修正する。
サブインターフェース自体の実装は本 ADR の範囲外 (Phase 2 の別作業) だが、ADR の文言は今のうちに直す。

### D9. バリデーション規則

F2 で実測した「黙って通る」ものを塞ぐ。

| チェック | Severity |
|---|---|
| `ip` / `ipv6` の形式と AF (型で担保。`ip` に IPv6 を書けば parse エラー) | error |
| `attaches_to: {interface: X}` の X を解決する。**`L3Interface` のみ** `layer1.interfaces` ∪ `layer2.vlans`、他は `layer1.interfaces` のみ (D3) | error |
| `interface` から解決した参照と、明示された `attaches_to` の食い違い (D3) | error |
| 旧 `vlan:` キーが残っている場合、移動先を示すエラー (D10) | error |
| `interface` が VLAN らしき名前なのに `attaches_to` が未指定 (D3) | warning |
| `attaches_to` が **L1 IF に解決された場合に限り**、その L1 IF の `node` が `L3Interface.node` と一致するか (VLAN は node を持たないので対象外) | error |
| `VLAN.trunk_ports[] / access_ports[]` の `interface` が、同じ `node` に属しているか | error |
| 同一 `(node, interface)` の `L3Interface` が重複していないか | error |
| `VRF.l3vni` と `L3VxLAN.vrf` の双方向一致 | error |
| `L2VxLAN.vtep_source` が指す L3 IF の `node` が `members` に含まれているか | error |
| `mode: vrrp` / `hsrp` で `vip` が IPv6 の場合、リンクローカル (fe80::/10) か (RFC 5798 §5.2.9・§6.1) | error |
| `vip` が **IPv4** の場合のみ、同一 IF の `ip` と同じサブネットか。IPv6 のリンクローカル VIP と、`ip` / `ipv6` が未指定の IF は対象外 | error |
| 同一 IF・同一 AF で `group_id` が重複していないか (VRRP / HSRP とも AF ごとに別の名前空間) | error |
| `group_id` の値域 (VRRP は 1..255、HSRPv2 は 0..4095) | error |
| `TunnelInterface.destination_ip` と `destination_interface` が排他か (両方指定・両方未指定は不可) | error |
| `TunnelInterface.source` / `destination_interface` / `vrf` / `transport_vrf` の参照解決 | error |
| ID の推奨プレフィックス `tunnel-` (ADR-0002 D7) | warning |

### D10. 移行

パッケージは 0.1.0 (未リリース) であり、移行期間は設けない。`ndl_version` は `1.0` のまま据え置く
(ADR-0010 D9 と同じ扱い)。

| 変更 | 既存 fixture への影響 |
|---|---|
| `ip` の型を `IPv4Interface` に | **0 行** (23 個すべて IPv4) |
| `ipv6` / `description` / トンネルの追加 | **0 行** (加算) |
| `fhrp` → `gateway_redundancy`、`protocol` → `mode`、値 `anycast_gateway` | **1 fixture** (`valid_multisite_wan.yaml`) の 6 エントリ |
| `L3Interface.vlan` フィールドの廃止 | **0 箇所**。旧キーが残っていれば移動先を示す error を出す |
| `interface: vlan-N` の短縮形の扱い | 3 fixture の 15 箇所。書き方は変わらないが、参照解決の経路が変わる |
| `ip` の型変更に伴う `exporter/cytoscape.py` の修正 | `IPv4Interface` は `json.dumps` で直列化できない (`TypeError`)。`str()` を挟む |
| D9 の新規チェック | 既存 fixture が新たに error になる箇所があれば、fixture 側を直す |

> **r2 の移行見積もりの訂正 (実装時に実測)**: r2 は「`vlan:` が 5 fixture 8 箇所」「`fhrp` は 3 fixture」としていたが、
> fixture の `vlan:` 8 箇所はすべて `layer2.vxlan[].vlan` (VNI → VLAN のマッピング) で、廃止対象の
> `L3Interface.vlan` ではなかった。`fhrp` を使う fixture も 1 本だけだった。YAML のキー名を grep しただけで、
> それがどのモデルのフィールドかを確かめていなかったことによる誤り。

### 実装記録 (2026-10-01)

| 項目 | 内容 |
|---|---|
| スキーマ | `layer3.py`: `L3Interface` (`ip: IPv4Interface` / `ipv6: IPv6Interface` / `gateway_redundancy` / 廃止キーの検出)、`VrrpGateway` / `HsrpGateway` / `AnycastGateway` の Tagged Union、`TunnelInterface`、`L3Layer.tunnel_interfaces`。layer1 / layer2 の全エンティティに `description` |
| validator | D9 の全規則。`_check_attaches_to` に `extra_interface_ids` を追加し、VLAN を許すのは `L3Interface` の呼び出しだけにした |
| エクスポーター | cytoscape: `ip` / `ipv6` の `str()` 化、SVI の VLAN を `attachment_ref()` で解決、`subnet_v6`、`lo_ipv6`、ノードの `tunnels`、トンネル辺の導出 (往復 2 本から 1 本)。不正な IP を握りつぶしていた `try/except ValueError` は型検証に置き換えて削除 |
| CLI | スキーマ違反をトレースバックではなく `ERROR` 行で報告するようにした (廃止キーの移動先メッセージを利用者に届けるため) |
| fixture | `valid_multisite_wan.yaml` の `fhrp` を移行。新規 `valid_dual_stack.yaml` / `valid_tunnel.yaml` |
| テスト | `tests/test_layer3_dataplane.py` (47 件)。新規の検証規則 10 件は、それぞれを無効化すると対応するテストが落ちることを確認済み |

**D7 の適用範囲**: `description` は layer1 / layer2 / layer3 のエンティティに追加した。`RoutingAdjacency` と
`protocols.*` は ADR-0010 (保留中) で置き換わるため追加していない。`PortRef` / `LacpConfig` / `RouteTargets` /
`AttachesToObj` は独立したエンティティではないため対象外。

**D11 の残件**: ADR-0005 への実装同期メモと原理 (D1) の追記 (D8)。

## Consequences

### 良い影響

- 「layer3 まで表現できる」と言える状態になる。判定基準は D11 (完了条件) に定義する
- F2 の 4 種類の矛盾と、F4 の不正な IP が検出される
- ADR-0005 D2-2 の SVI 規範が初めて実装と一致する。NetBox アダプターが正規形で出力できる
- ADR-0005 D3-1 の表が実装に追いつく
- デュアルスタックが既存データを壊さずに書けるようになる

### 悪い影響 / トレードオフ

- `fhrp` → `gateway_redundancy` と `vlan` 廃止は破壊的変更。3 fixture の書き換えが必要
- **設計として 1 IF に複数アドレスを割り当てる構成は書けない** (D5)。セカンダリ IPv4、GUA + ULA 併用、
  リナンバリング中の同居、リンクローカルの手動固定、**ループバックに用途別の複数 IP** (router-id 用 / VTEP 用 / telemetry 用を
  分ける運用)。加算的に拡張できるが、今は書けない。ループバックについては、用途ごとに別のループバック IF を作れば表現できる
- **IPv6 VRRP の追加グローバル VIP を書けない** (D4)。リンクローカルの VIP のみ
- **IPv6 VIP の scope zone** (`fe80::1%eth0`、RFC 4007) は書けない。`IPv6Address` が zone id を受け付けないため。
  SVI 単位で閉じているので実害は小さい
- **トンネルは点対点のみ**。mGRE / DMVPN のような点-多点、GRE over IPsec の 2 段構成、MSS clamping は書けない (D6)
- **スタティックルートを書けない** (D2)。これは意図的な判断であり、原理 (D1) の帰結
- サブインターフェースは本 ADR では実装しない。802.1Q タグ付き routed subif (router-on-a-stick) は
  引き続き書けない。ADR の文言修正のみ行う (D8)
- `PortRef.native` の命名 (IEEE 802.1Q の用語は untagged) は本 ADR では変更しない (未解決事項)

### 影響を受けるコンポーネント

- スキーマ: `schema/layer3.py` (L3Interface / GatewayRedundancy / TunnelInterface)、全モデルの `description`
- バリデーター: `validator.py` (D9 の規則、`_check_attaches_to` の参照先拡張)
- エクスポーター: `exporter/cytoscape.py` (`lo_ip` の IPv6 対応、VLAN サブネット導出の IPv6 対応、トンネルの edge)
- サンプル: `tests/fixtures/` の 3 fixture の書き換え、新規 `valid_dual_stack.yaml` / `valid_tunnel.yaml`
- 文書: CLAUDE.md、ADR-0005 (D2-2・D3-1・D3-2)、ADR-0002 D7 (相互参照)

### D11. 完了条件 (「layer3 データプレーンの中核が確定した」の定義)

| 観点 | 条件 |
|---|---|
| スキーマ | D3〜D7 のすべてが実装されている |
| バリデーター | D9 のすべての error 規則が実装され、F2 の 4 例がいずれも error になる |
| エクスポーター | yaml が IPv6・トンネルを含めて往復で同値。cytoscape がトンネルの辺を出力する |
| fixture | 既存 5 本 + 新規 2 本 (dual stack / tunnel) が validate を通る |
| ADR | ADR-0005 に実装同期メモ (D8) と原理 (D1) が追記されている |

**「往復で同値」の定義**: `yaml → MLNDLTopology → yaml → MLNDLTopology` として、1 回目と 2 回目の
`model_dump()` が一致すること。**文字列レベルの一致は求めない** (pydantic の型による正規化で
`10.0.0.1` が `10.0.0.1/32` になる等の差分は許容する)。

#### 本 ADR を閉じても書けないもの (Known Gap)

「layer3 まで**すべて**表現できる」とは言わない。以下は残る。

| 項目 | 行き先 |
|---|---|
| **802.1Q サブインターフェース** (router-on-a-stick) | Phase 2 の別作業。本 ADR は ADR-0005 の文言修正のみ (D8)。実測 `T3_branch_router_on_a_stick.yaml` では 13 箇所が書けなかった |
| vSwitch / dvSwitch / PortGroup / VMkernel | drafts/0007 |
| クラウド (VPC 等) | drafts/0008 |
| 制御プレーン (BGP / OSPF / IS-IS / BFD) | drafts/0010 (保留中) |
| D5 / D4 / D6 で書けないもの | 上記 Consequences を参照 |

`tests/fixtures/valid_vsphere_dvswitch.yaml` は drafts/0007 待ちとして対象外とする
(ID 参照に直した版は `evaluations/adr0011/topologies/T5_vsphere_dvswitch_fixed.yaml` にある)。

## Alternatives Considered

- **デュアルスタックを `ipv4: list` + `ipv6: list` にする** (命名・実証エージェントの推奨): 却下 —
  既存 23 箇所の書き換えが必要。`ip` を残して `ipv4` を併走させる移行案は、IPv4 を 2 箇所に書ける状態を作る
  (ADR-0010 と L3Interface で問題になった二重表現と同型)。業界も二分しており
  (CLI / Terraform は非対称、YANG / OpenConfig は対称)、YANG に揃える必然性はない
- **`ip` / `ipv6` を `str | list[str]` の Union にする** (技術エージェントの推奨): 却下 —
  同じ事実を 2 通りに書ける。複数アドレスが必要になれば別フィールドを加算する
- **`FhrpInstance.address_family` を追加する** (実証エージェントの提案): 却下 —
  RFC 5798 により 1 インスタンスは単一 AF なので、`vip` の型から判別できる。二重表現になる
- **スタティックルートを入れる** (5 エージェント中 4 つの推奨): 却下 — D1 の原理に反する。ユーザー判断
- **`interface` フィールドを廃止し `attaches_to` だけにする**: 却下 — 機器上の名前 (`swp51`) は
  設定生成に必要であり、参照とは別の情報。ADR-0005 D2-2 の B-1 短縮形も失われる
- **ADR-0005 を Reopen する**: 却下 — ずれているのは D3-1 の実装インベントリであって判断ではない。
  ADR-0010 と同じ「部分改訂」で足りる
- **決定を 3 本の ADR に分ける**: 却下 — 3 決定はいずれも「layer3 データプレーンとして何を書き何を書かないか」
  という同じ軸に属し、原理 (D1) を共有する
- **トンネル (D6) を別 ADR に切り出す** (仕様統合エージェントの推奨): 却下 — r1 では論点が 4 つあったが、
  `tunnel_links` を廃止して自己完結型にしたことで、残る論点は「型の値域」と「どこまでを書くか」の 2 つになった。
  D1 の原理の適用例としても、同じ ADR に置くほうが読みやすい
- **トンネルを `tunnel_interfaces` + `tunnel_links` の対にする** (r1 の案): 却下 —
  トンネル IF は `source` / `destination` を自分で持つため、リンクを別に書くと二重表現になる (D6)
- **`mode` の値を `anycast` にする** (r1 の案): 却下 — DNS anycast や anycast ルーティング一般と紛れる。
  `vrrp` / `hsrp` が固有名詞なのに `anycast` だけ一般名詞になる非対称も避ける
- **`GatewayRedundancy` を単一モデルにして `group_id` / `vip` を optional にする** (r1 の案): 却下 —
  「anycast なのに `group_id` を書いた」が黙って通る。`mode` を discriminator とする Tagged Union にする

## 未解決事項

1. `PortRef.native` を `untagged` に改名するか。
   `native` は Cisco / Aruba / Juniper (`native-vlan-id`) が採用する広く使われる語彙、
   `untagged` は IEEE 802.1Q の標準用語で Arista / NetBox が採用。
   **判断を保留する理由**: 802.1Q の untagged と Cisco の native VLAN は厳密には意味が異なる
   (前者はフレームにタグがないこと、後者はトランク上でタグなしフレームを受ける VLAN)。
   **判断する時期**: サブインターフェース実装時に trunk / access の意味論を確定するのと合わせる
2. enum 値の区切り文字の規約。現状は `l2vni` (連結) / `peer-link` (ハイフン) / `route_reflector` (アンダースコア) が混在する。
   本 ADR では新規の値を snake_case に揃えた (`anycast_gateway` / `ipsec_vti`) が、全体の規約は未確定
3. `L2VxLAN.vtep_source` を MLAG の anycast VTEP に対応させるか (現在は単数参照)
4. `L2VxLAN.vtep_source` を `AttachesTo` 型に揃えるか (他のフィールドは `attaches_to` を使っている)
5. 3 と 4 を本 ADR の範囲に含めるかどうか自体、Pass C でユーザー判断を仰ぐ

## r1 からの変更 (5 エージェントレビュー反映)

| 指摘 | 出所 | 対応 |
|---|---|---|
| **D6 のトンネルが二重表現**。トンネル IF は `source` / `destination` を自分で持つので、`tunnel_links` は導出可能な二次情報 | dsl-designer / spec-architect / example-author (独立に 3 者) | `tunnel_links` を廃止し、自己完結型の `TunnelInterface` 1 本に (D6) |
| **`destination: str` が「IP または ID」の 2 形式を受ける**。F4 と同型 | spec-architect / linguist / dsl-designer | `destination_ip` と `destination_interface` の排他に分割 (D6) |
| **`_check_attaches_to` の拡張が広すぎる**。4 箇所から共有されており、L1 の `attaches_to` が VLAN を指せてしまう | dsl-designer / spec-architect | `L3Interface` に限定 (D3・D9) |
| **B-1 の正規化がモデルに書き戻されると YAML の往復が壊れる** | dsl-designer / spec-architect | validator 内でのみ解決し、格納しない。ADR-0005 D2-2 の「内部表現に正規化する」も改訂 (D3) |
| **`ip` の型変更で cytoscape が落ちる**。`IPv4Interface` は `json.dumps` で直列化できない | dsl-designer | D10 に `str()` を挟む修正を明記 (実測で `TypeError` を確認) |
| `GatewayRedundancy` を Tagged Union にすべき。単一モデルだと「anycast なのに group_id」が通る | dsl-designer | `mode` を discriminator とする Union に (D4) |
| 値 `anycast` は一般名詞で多義。ADR-0005 の元記述は `anycast_gateway` | linguist | `anycast_gateway` に戻す (D4) |
| anycast gateway の MAC を書けないと設定生成ができない | network-tech-reviewer | `AnycastGateway.anycast_mac` を追加。ADR-0005 D3-2 の保留項目を解消 (D4) |
| HSRPv2 for IPv6 にもリンクローカル VIP の要件がある | network-tech-reviewer | D9 のチェックを `vrrp` / `hsrp` 両方に (D4・D9) |
| **IPv6 VRRP の VIP はリンクローカルなので、「VIP が IF の IP と同じサブネット」チェックと同時に成立しない** | spec-architect / network-tech-reviewer | サブネット一致は IPv4 のみに限定 (D9) |
| トンネルに `transport_vrf` / `mtu` / `wireguard` が要る | network-tech-reviewer | D6 に追加 |
| `group_id` の値域チェック (VRRP 1..255 / HSRPv2 0..4095) | network-tech-reviewer | D9 に追加 |
| D1 が「D4 より上位」と書くと、D4 が全 Yes を返した概念も外せると誤読される | spec-architect | 「混在時の解決指針」と限定し、判定手順を 3 段で明示 (D1) |
| 移行対象は 3 fixture ではない | dsl-designer | 実測して訂正。`vlan:` が 5 fixture 8 箇所、`interface: vlan-` が 5 fixture 15 箇所 (D10) |
| `MlagLag.client_lag` と `vtep_source` のレガシー書式が同期表にない | spec-architect | D8 に追加 |
| サブ IF 未実装のまま「layer3 まで表現できる」と宣言するのは実測と食い違う | spec-architect / example-author | D11 を「中核が確定した」に改め、Known Gap の表を追加 |
| 「往復で同値」の定義が曖昧 | spec-architect | `model_dump()` の一致と定義し、文字列一致は求めないと明記 (D11) |
| ループバックに用途別の複数 IP を割り当てる運用が書けない | network-tech-reviewer | Consequences に追記 |
| Terms 節がない | linguist / spec-architect | 追加 |
| 未解決事項 1・2 の判断材料が不足 | linguist | 根拠と判断時期を追記 |
| `interface: Vlan100` (機器上の名前) が短縮形にマッチしない | example-author | 短縮形は `^vlan-\d+$` のみと明示し、機器名は `interface` に残して `attaches_to` を併記する形を示した (D3) |
| SVI のつもりで `attaches_to` を書き忘れた場合が検出されない | example-author | warning を追加 (D3・D9) |

**採らなかった指摘**:

- **RFC 5798 の引用を §5.2.7 / §6.4.2 に直し、大文字 MUST とする** (network-tech-reviewer): 原文を照合した結果、
  **指摘の方が誤り**だった。§5.2.7 は "Maximum Advertisement Interval" で VIP とは無関係、§6.4.2 "Backup" に
  リンクローカル VIP の要件はない。リンクローカル要件を述べているのは §5.2.9 と §6.1 の 2 箇所だけで、
  いずれも小文字の "must"。r1 の記述が正しかったため変更しない
- **`link_role` に `trunk` を追加する件を未解決事項に残す** (example-author): `link_role` は既に `str | None`
  (自由文字列) であり、`trunk` は今でも書ける。「詰まる」という報告は誤り。推奨語彙への追記だけなので D8 に移した
- **D6 を別 ADR に切り出す** (spec-architect): `tunnel_links` の廃止で論点が減ったため、1 本に残す
- **`description` を共通基底クラスにまとめる**: dsl-designer が前回に続き個別追加を推奨。変更しない

## References

- 関連 ADR: ADR-0001, ADR-0002 (D6・D7), ADR-0003, ADR-0005 (D2-2・D2-3・D3-1・D3-2・D4), ADR-0006, ADR-0009, drafts/0010
- 実測: [`evaluations/adr0011/`](../evaluations/adr0011/README.md) — topologies / contradictions / dualstack
- RFC 4291 §2.1・§2.5.6 (IPv6 アドレッシング) / RFC 4862 (SLAAC) / RFC 8981 (一時アドレス)
- RFC 3021 (IPv4 /31) / RFC 6164 (IPv6 /127) / RFC 4193 (ULA) / RFC 4192 (リナンバリング)
- RFC 5798 §5.2.9・§6.1 (VRRPv3 — IPv6 の VIP はリンクローカルが先頭) / RFC 9135 (EVPN anycast gateway)
- RFC 4364 (Route Target) / RFC 2784 (GRE) / RFC 2003 (IPIP) / RFC 7296 (IKEv2)
- RFC 8344 (`ietf-ip`) / OpenConfig `openconfig-if-ip` / NetBox IPAddress・Tunnel モデル
- RFC 8345 / 8346 / 8944 (ネットワークトポロジー)
