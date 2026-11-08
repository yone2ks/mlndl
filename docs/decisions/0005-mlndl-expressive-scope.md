# ADR-0005: mlndl の表現スコープ定義

- **Status**: Accepted
- **Date**: 2026-05-29
- **Deciders**: mlndl-spec-architect (Pass C), mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, ecosystem-reviewer
- **Pass**: C (再設計後の最終版)
- **Supersedes**: drafts/0005-mlndl-expressive-scope.md
- **Amended by**: [ADR-0011](0011-layer3-data-plane.md) (2026-10-04、Pass C で確定 2026-10-15)、[ADR-0012](0012-subinterfaces.md) (2026-10-05)、
  [ADR-0013](0013-vlan-ports-on-lag.md)、ラウンド4 Pass C (2026-10-15) — 表現の指針 (D4 補則)、`node` の持ち方 (D6)、
  SVI 規範の改訂、スコープ表の実装同期。[drafts/0014](drafts/0014-vteps.md) (2026-10-20) — D4 補則に問い 4 (方式中立) を追加。
  [ADR-0010](0010-control-plane-separation.md) (2026-11-01) — 制御プレーンを `control_plane` に分離 (D1・D3-1 の制御プレーンの行、P6、BGP unnumbered の規則)。
  2026-11-07 — D5 の Phase の札をやめ、先送りした項目を [deferred.md](deferred.md) にまとめた。
  改訂箇所には注記を入れ、元の記述は履歴として残す。一覧は末尾の「実装同期メモ」を参照

## Context

ラウンド1 (ADR-0001〜0004) で `attaches_to` / ID 命名 / `role` 語彙 / `implementation × role` の各論点を確定した結果、「これらは何のために設計されたか」という上位命題 — **mlndl が何を表現する言語か** — が ADR として未明文化のまま残っていた。CLAUDE.md には散発的な記述 (「mlndl は EVE-NG を知らない」「Phase 1 は L1 のみ」「中間フォーマットライブラリ」) があるものの、新概念 (例: `service-mesh`, `dpu-offload`, `EVPN ESI-LAG`) を「スコープ内/外」に振り分けるための判定基準が欠落していた。

### ユーザー発話 (引用)

ラウンド1.5 着手時のユーザー方針:

> mlndl は **「物理構成図、論理構成図、物理と論理の間の連携」** を表現する言語

この三区分を ADR-0005 として明文化することが本 ADR の出発点である。

### ADR 策定の経緯

- **Pass A** (`drafts/0005-mlndl-expressive-scope.md`): spec-architect 単独で初期ドラフトを起草。三区分を「三軸 (a/b/c)」として導入し、D3 で「含む」「含めない」リストを確定
- **Pass B**: linguist / dsl-designer / network-tech-reviewer / ecosystem-reviewer の 4 並列レビュー。15 件の指摘 (P1〜P15) を `evaluations/round1.5-evaluation.md` 段階1 章に集約
- **Pass C** (本 ADR): spec-architect が Pass A ドラフトを参照禁止とし、評価メモのみを入力としてゼロから再設計

Pass B で確定した主要論点:

1. 「三軸」は (a)(b) の直交性は成立するが、(c) は (a)(b) を結ぶ**関係**であり独立軸ではない (P2, P10)
2. D3「含む (Phase 1 + Phase 2)」は Phase 2 未実装を「含む」と書く時制矛盾 (P1)
3. routed 物理 IF の二段表現は D2 で規定済みだが、SVI の二段表現規則が未定義 (P3)
4. EVPN advertise フラグ群を「含めない」とすると MLAG+Symmetric IRB が事実上記述不能になる (P7)
5. `tunnel_interfaces` と `tunnel_links` の関係性 (entity / relation の対) が未注釈 (P8)
6. NetBox Interface type → mlndl 層の振り分けマトリクスが欠落 (P9)
7. BGP unnumbered の `remote_as` 値域 (`external` / `internal` キーワード) が未明示 (P6)

### 前提 (Pass C 確定事項)

- **ADR-0001 (Pass C)**: `attaches_to` は supporting 関係の単一フィールド。`{node:}` / `{interface:}` / `{link:}` のタグ付き Union
- **ADR-0002 (Pass C)**: 全エンティティはグローバル一意 ID 空間を共有。severity 定義は D8 (ADR-0002)
- **ADR-0003 (Pass C)**: `role` は optional な意味論的ラベル。canonical 9 語彙。本 ADR の D3 によりラウンド1.5 段階2 で再評価対象
- **ADR-0004 (Pass C)**: コアバリデーターが拒否するのは `container × hypervisor` の 1 件のみ。慣行チェックは外部プラグイン
- **Phase 1 = L1 のみ実装**。Phase 2 以降で L2/L3/protocols を順次実装

## Decision

### D1. mlndl は「三側面」を表現する言語である

mlndl の表現対象を、ユーザー発話に基づき以下の **三側面 (three aspects)** として定義する。

| 記号 | 側面 | 内容 | RFC 8345 対応 |
|------|------|------|--------------|
| (a) | **物理構成図** | ノード (箱) と物理ケーブル (線) で構成される下位レイヤー | physical-network-topology, supporting-node/link の被支持側 |
| (b) | **論理構成図** | VLAN / VRF / VxLAN / 隣接関係など、上位プロトコルの存在と形 | l3-unicast-topology, l2-network-topology |
| (c) | **物理-論理連携** | (a) と (b) を結ぶ supporting 関係。`attaches_to` 単一フィールドで表現 | supporting-* (node / termination-point / link) |

**呼称について — なぜ「三側面」か (Pass B P10 採用)**:

「軸 (axis)」は数学的な直交性を含意するが、(c) は (a) と (b) を**結ぶ関係**であり、(a)(b) と独立した軸ではない。port_channel / MLAG / SVI / トンネル IF など、(a) と (b) の境界をまたぐエンティティが本質的に存在する以上、(a)(b)(c) を厳密な MECE 直交分類とする主張は内部矛盾を招く。

そのため本 ADR は「**三側面**」(three aspects) を採用する。(a)(b) は記述対象の二つの層、(c) は両者を結ぶ**操作的分類** (operational classification) として定義する。`attaches_to` を独立した一級概念として議論できるよう (c) を独立側面に立てるが、純粋 MECE ではないことを明示する。

略号 (a)/(b)/(c) は本 ADR 全体で参照のために維持する。

> **改訂 (ADR-0010 D1, 2026-11-01)**: (b) 論理構成図の内部を、データプレーン (`layer2` / `layer3`) と制御プレーン (`control_plane`) に分ける。
> `layerN` は RFC 8345 のデータプレーンのネットワーク層に番号を振ったもので、OSI の層番号ではない。BGP / OSPF / IS-IS / BFD はどの `layerN` にも属さず、`control_plane` に置く。

### D2. 三側面の境界規則

#### D2-1. 「箱」と「線」の表現原則

| 表現 | 用途 |
|------|------|
| **ノード (箱)** | エンティティとして自律的に存在し、ID で参照される対象 (物理機器、論理デバイス、VRF、VLAN、VNI など) |
| **リンク (線)** | 両端を持つ二項関係 (物理ケーブル、BGP セッション、トンネル両端、L1Link、tunnel_links) |
| **参照フィールド** | エンティティ間の所属/包含関係 (`attaches_to`、`vrf`、`vlan`、`members` など) |

RFC 8345 の「ネスト構造で supporting を表現する」アプローチは採用しない。mlndl は **層を独立コレクションで保持し、`attaches_to` で結ぶ「圧縮表現」** を取る (ADR-0001 D1)。

OpenConfig の `/interfaces/interface/subinterfaces/subinterface` 等のネスト構造とは設計思想が異なる。mlndl → OpenConfig の変換は片方向エクスポートとして実装する (往復変換は保証しない)。

#### D2-2. 物理 IF と論理 IF の二段表現規則

物理ポート (L1) と、その上に終端する L2/L3 機能 (VLAN tag、IP アドレス、サブインターフェース、SVI 等) は、**別エンティティとして二段に書き、`attaches_to` で結ぶ**ことを規範とする。

**ケース A: routed 物理 IF (例: leaf1-swp51 に IP を直接付与)**

```yaml
layer1:
  interfaces:
    - id: leaf1-swp51        # 物理ポート (側面 a)
      node: leaf1
      name: swp51
layer3:
  interfaces:
    - id: leaf1-swp51-l3     # L3 終端 (側面 b)
      node: leaf1
      ip: 10.1.0.1/31
      attaches_to:           # 側面 c
        interface: leaf1-swp51
```

**ケース B: SVI (`interface vlan-100` に IP を付与)** — Pass C で新規追加 (P3)

> **ラウンド4 Pass C で改訂 (2026-10-15)**: 以下の B-1 (短縮形 `interface: vlan-N`) は廃止し、B-2 に一本化した。
> 書き方は `name: <機器上の名前>` + `attaches_to: {vlan: <VLAN id>}` である (ADR-0001 D8、ADR-0011 D3)。
> 短縮形と旧キー `interface` は ndl_version 1.x の間だけ受け付け、warning を出す。以下は履歴として残す。

SVI は VLAN を上位 supporting 対象として持つ L3 entity である。次の 2 種類の表現を許容する:

```yaml
# パターン B-1: VLAN 暗黙参照 (推奨・短縮形)
layer3:
  interfaces:
    - id: leaf1-vlan-100
      node: leaf1
      interface: vlan-100     # layer2.vlans[id=vlan-100] を暗黙参照
      ip: 192.168.100.1/24
      vrf: vrf-tenant-a
```

```yaml
# パターン B-2: attaches_to で明示 (生成系・エクスポーターの正規形)
layer3:
  interfaces:
    - id: leaf1-vlan-100
      node: leaf1
      ip: 192.168.100.1/24
      vrf: vrf-tenant-a
      attaches_to:
        interface: vlan-100   # ADR-0001 のタグ付き Union (interface キーで VLAN ID を指す)
```

**規範**:
- パターン B-1 (`interface: vlan-N` フィールド) を**推奨**する。手書き YAML での記述量が最小
- パターン B-2 (`attaches_to: {interface: vlan-N}`) は**生成系 (アダプター・エクスポーター) の正規形**とする
- バリデーターは両形式を受理し、内部表現としては B-2 に正規化する
- `vlan-N` という ID が `layer2.vlans` に存在しない場合は `error` (ADR-0002 D8)

> **ADR-0011 D3 で改訂 (2026-10-04)**: 「内部表現を B-2 に正規化する」は採らない。正規化してモデルに格納すると、
> 入力になかった `attaches_to` が YAML エクスポートに現れ、往復が壊れるため。
> B-1 は **validator の内部でだけ** `{interface: vlan-N}` として解決し、モデルには書き戻さない。
> あわせて以下を定める。
>
> - `interface` は**機器上の名前** (`swp51` / `Vlan100` / `lo`) であり、参照解決には使わない。
>   短縮形として解決するのは `^vlan-\d+$` に一致する場合だけ
> - 機器上の名前を残したい場合は `interface: Vlan100` と `attaches_to: {interface: vlan-100}` を併記する
> - 短縮形と明示した `attaches_to` が食い違えば `error`。VLAN らしき名前で `attaches_to` がなければ `warning`
> - 実装時点で B-2 は「未定義のインターフェース」として **error になっていた** (validator が `layer1.interfaces` しか
>   見ていなかった)。ADR-0011 で `L3Interface` に限り VLAN を参照先として許すよう修正した

**ケース C: サブインターフェース (例: swp1.100)** — Phase 2 実装、本 ADR で予告のみ

```yaml
layer2:
  subinterfaces:
    - id: leaf1-swp1-100
      parent: leaf1-swp1     # L1 物理 IF への参照
      vlan_id: 100
layer3:
  interfaces:
    - id: leaf1-swp1-100-l3
      attaches_to:
        interface: leaf1-swp1-100
      ip: 10.2.0.1/30
```

> **ADR-0011 D8 で改訂 (2026-10-04)**: 親の物理 IF は `parent:` ではなく `attaches_to: {interface: <L1 IF>}` で指す。
> 親 IF が落ちればサブ IF も動作しないので、この関係は Realization (ADR-0009 D1) である。
> `parent` は ADR-0009 D1 で Containment に予約されており、値域も node の ID に限られる。
> サブインターフェースは ADR-0012 で実装した。上の例の ID `leaf1-swp1-100` は L1 IF の ID と区別できないため、
> `subif-leaf1-swp1-100` とする (ADR-0002 D7)。`vlan_id` はリンク上のタグ番号であり、`layer2.vlans` への参照ではない。

#### D2-3. `attaches_to: {interface: X}` が指せる層

`attaches_to: {interface: X}` の X はグローバル一意 ID (ADR-0002 D5) で解決される:

| X が指す層 | 例 | 用途 |
|-----------|-----|------|
| L1 物理 IF | `interface: leaf1-swp51` | L3 routed 物理 IF (ケース A) |
| L2 VLAN (SVI 経由) | `interface: vlan-100` | SVI (ケース B) |
| L2 サブインターフェース (Phase 2) | `interface: leaf1-swp1-100` | L3 over sub-IF (ケース C) |

> **ADR-0012 D5 で改訂 (2026-10-05)**: X が指せるものを `attaches_to` を持つエンティティごとに固定した。
> `layer3.interfaces` は L1 IF / LAG / VLAN / サブ IF、`layer2.subinterfaces` は L1 IF / LAG、それ以外は L1 IF のみ。
> LAG を加えたことで、LAG 上のサブ IF と routed LAG が書ける。前提となる ID のグローバル一意性 (ADR-0002 D5) は
> validator の error として検証する。

`layer` フィールドなしで層が一意に決定する (ADR-0001 D2)。

#### D2-4. `attaches_to` 単一手段方針 (ADR-0001 再確認)

(c) を表現する手段は `attaches_to` のみとする。`supporting_interface` 等の別フィールドは新設しない。

以下は (c) ではなく entity 内の意味論的フィールドであり `attaches_to` ではない:

- `port_channels.members: [id, ...]` — LAG メンバの集合定義
- `mlag.peer_link: id` — MLAG ドメインの意味論的役割
- `vrf` / `vlan` / `parent` フィールド — 包含関係の宣言

> **ADR-0011 D3 で改訂 (2026-10-04)**: `layer3.interfaces[].vlan` は廃止した。SVI の VLAN は `attaches_to` で指す
> (`vrf` は引き続き包含関係の宣言)。

### D3. スコープの確定

本 ADR は **mlndl が記述可能とする概念集合 (= スコープ内)** と、**意図的に扱わない概念 (= スコープ外)** を明示する。

「**スコープ内**」と「**Phase 1 実装**」は分離する (P1 採用)。スコープ内の概念は将来 Phase で実装されることを保証するが、必ずしも Phase 1 で実装されるわけではない。

#### D3-1. スコープ内

##### Phase 1 実装 (L1 のみ)

| 側面 | 概念 |
|------|------|
| (a) | `layer1.nodes`: id, name, role, implementation (vm\|physical\|container), device_type, overrides, description |
| (a) | `layer1.interfaces`: id, node, name, description |
| (a) | `layer1.links`: id, from, to, link_speed, mtu, link_role (underlay\|access\|peer-link\|management\|uplink) |
| (a) | `layer1.port_channels`: id, node, members, lacp {mode, min_links} — **リンクアグリゲーション (LAG, single-chassis)** |
| (a) | `layer1.mlag`: id, nodes, peer_link, peer_link_interface, domain_id — **リンクアグリゲーション (LAG, multi-chassis)** |
| (c) | `nodes[].attaches_to: <node-id> \| {node: id}` — VM ↔ hypervisor supporting |
| (c) | `interfaces[].attaches_to: {interface: id}` — 論理 IF ↔ 物理 IF supporting |
| 共通 | `description` / `comment`: 全構成要素に optional |
| メタ | `ndl_version` / `meta.name` / `meta.network_types` |

> **実装同期 (ADR-0011 D8, 2026-10-04)**: 上表の `layer1.links: from, to` は ADR-0006 で `endpoints` に、
> `layer1.port_channels` / `layer1.mlag` は §6 設計決定で `layer1.lag` (type: lacp | mlag) に統合済み。
> `description` は `comment` を併記せず `description` の 1 語に絞り、ADR-0011 で全エンティティに実装した。
> `link_role` は自由文字列であり、推奨語彙に `trunk` を加えた。実装済みの `MlagLag.system_mac` / `client_lag` は上表にない。
>
> **改訂 ([ADR-0024](0024-remove-node-overrides.md), 2026-11-09)**: 上表の `layer1.nodes` の `overrides` はなくした。下流のツールの値は下流のツールの設定で機器の id を引いて持つ。

##### スコープ内 (Phase 2 以降で実装予定)

| 側面 | 概念 | 備考 |
|------|------|------|
| (b) | `layer2.vlans`: id, vlan_id, trunk_ports [{node, interface}], access_ports [{node, interface}] | |
| (b) | `layer2.subinterfaces`: id, parent (L1 IF), vlan_id | D2-2 ケース C |
| (b) | `layer2.vxlan`: id, type (l2vni\|l3vni), vni, vlan, vtep_source, members, irb_mode | type 明示必須 |
| (b) | `layer3.vrfs`: id, rd, l3vni, route_targets {import, export} | |
| (b) | `layer3.interfaces`: id, node, ip (IPv4/IPv6), vrf, attaches_to または interface フィールド | routed 物理 IF / SVI の二段表現 (D2-2) |
| (b) | `layer3.tunnel_interfaces`: id, node, ip, vrf, type (gre\|ipip\|ipsec-vti) | **entity** (L3Interface の一種) |
| (b) | `layer3.tunnel_links`: id, from, to | **relation** (L1Link 同型の両端関係)。`tunnel_interfaces` と対。P8 採用 |
| (b) | `layer3.routing_adjacencies`: id, type (bgp\|ospf\|isis), from, to, attaches_to | |
| (b) | `layer3.interfaces[].gateway_redundancy`: protocol (anycast_gateway\|vrrp), vip | anycast_mac は D3-3 参照 |
| (b) | `protocols.bgp`: role, address_families [ipv4_unicast \| ipv6_unicast \| l2vpn_evpn \| vpnv4 \| vpnv6] (P5), remote_as: \<ASN\>\|external\|internal (P6), redistribute, route_reflector/route_reflector_client role | |
| (b) | `protocols.ospf`: area, router_id, redistribute | |
| (b) | `protocols.isis`: level, area, system_id | ハイパースケーラー DC / SR underlay |
| (b) | `protocols.bfd`: min_tx, min_rx, multiplier, nodes | **隣接 timer の唯一の例外** D3-3 参照 |
| (b) | EVPN advertise フラグ群 (`advertise-default-gw` / `advertise-svi-ip` / `advertise-pip`) | **Phase 2 で「含む」確定予告** (P7)。Consequences 参照 |
| (b) | L3 アドレッシング: IPv4/IPv6, prefix, loopback IP, anycast VIP, RD/RT, AS 番号, router-id | |
| (c) | `interfaces[].attaches_to: {interface: vlan-N}` | SVI (D2-2 ケース B) |
| (c) | `tunnel_interfaces[].attaches_to: {interface: ...}` | トンネル発信元 IF |
| (c) | `routing_adjacencies[].attaches_to: {link: ...}` | BGP セッションが使う物理リンク |

> **実装同期 (ADR-0011 D8, 2026-10-04)**: 上表のうちデータプレーン部分は ADR-0011 で次のように確定・実装した。
>
> | 上表の記述 | 実装 |
> |---|---|
> | `layer3.interfaces`: ip (IPv4/IPv6) | `ip` (IPv4) / `ipv6` (IPv6)。いずれも単数 (ADR-0011 D5) |
> | `layer3.interfaces[].gateway_redundancy`: protocol (anycast_gateway\|vrrp), vip | `gateway_redundancy`: `mode` (vrrp \| hsrp \| anycast_gateway) の Tagged Union。IPv6 の VIP はリンクローカル (ADR-0011 D4) |
> | `layer3.tunnel_interfaces` + `layer3.tunnel_links` (P8) | `tunnel_interfaces` のみ。トンネル IF は source / destination を自分で持つため、`tunnel_links` は二重表現になる (ADR-0011 D6) |
> | `layer2.vxlan`: vtep_source (旧書式 `{layer: layer3, interface_id: ...}`) | `vtep_source: <L3 IF id>`。`layer` キーは ADR-0001 D2 で廃止済み |
> | `layer2.subinterfaces` | ADR-0012 で実装: id, attaches_to (L1 IF または LAG), vlan_id, name, description。`node` と VLAN 参照は持たない |
>
> **改訂 (ADR-0010, 2026-11-01)**: 上表の制御プレーンの行は次のように置き換える (ADR-0010 は Accepted・実装済み)。
>
> | 上表の記述 | ADR-0010 |
> |---|---|
> | `layer3.routing_adjacencies`: id, type, from, to, attaches_to | `control_plane.routing_neighbors`: 1 エントリ = 1 セッション。BGP の端点は `{node, update_source}` か `{address, local_as}`。`attaches_to` は持たない (D3・D7) |
> | `protocols.bgp`: role, address_families, remote_as (P6), route_reflector role | `control_plane.bgp`: VRF ごとのインスタンス `{id, vrf, nodes: [{node, local_as}]}`。`role` (underlay / overlay) と `remote_as` は廃止。AF はセッションに、RR はセッションの端点の `route_reflector_client` に (D3・D5・D6) |
> | `protocols.ospf` / `protocols.isis` / `protocols.bfd` | `control_plane.ospf` / `isis` / `bfd` (D8) |
> | (c) `routing_adjacencies[].attaches_to: {link: ...}` | 削除。セッションの通り道は `update_source` の L3 IF から導く (D7) |

**BGP unnumbered の表現規則 (P6 採用)** — **ADR-0010 D4・D5 で置き換え (2026-11-01)**: unnumbered は「`update_source` が `ip` も `ipv6` も持たない L3 IF を指す」で表す。`remote_as` は廃止し、eBGP / iBGP は両端の AS から導く。以下は履歴として残す。

`routing_adjacencies` での unnumbered 隣接表現: `mode: unnumbered` フラグを指定するか、または `update_source` が loopback でない物理 IF を指す場合に unnumbered と解釈する。`remote_as` には ASN 番号のほか `external` (Cumulus FRR / FRRouting の `remote-as external` 相当) / `internal` を許容する。

##### NetBox Interface type 振り分けマトリクス (P9 採用)

NetBox → mlndl アダプター実装時の参照表:

| NetBox `type` | mlndl 層 |
|--------------|---------|
| `1000base-t` / `10gbase-x-sfpp` / `25gbase-x-sfp28` / `100gbase-x-qsfp28` 等の物理メディア | `layer1.interfaces` |
| `lag` | `layer1.port_channels` |
| `virtual` (parent あり、vlan あり) | `layer2.subinterfaces` |
| `virtual` (parent なし、IP あり) | `layer3.interfaces` (routed virtual / loopback) |
| `virtual` (SVI: name が `vlan-N` パターン or mode=vlan) | `layer3.interfaces` (D2-2 ケース B) |
| `bridge` | Phase 2 で再判断 (`layer2.bridges` 仮称の設計待ち) |
| その他 / 未知タイプ | アダプターが `warning` を出力し、変換をスキップ (ADR-0002 D6) |

#### D3-2. スコープ外 (含めない概念とその行き先)

| 概念 | 行き先 |
|------|--------|
| EVE-NG 固有情報 (template / cpu / ram) | eve-lab-builder/config/device_mapping.yaml |
| ACL / NAT / Firewall policy / route-map / prefix-list | 上位ツール (Ansible / NetBox config context) |
| DHCP relay (helper-address) | 上位ツール |
| BGP community / BGP 認証 / IPv6 RA / SLAAC 詳細 | 上位ツール |
| BGP / OSPF / IS-IS timer (BFD timer を除く) / ECMP max-paths | 上位ツール |
| MAC アドレス全般 (anycast MAC / MLAG system-mac 含む) | 原則扱わない。`gateway_redundancy.anycast_mac` / MLAG system-mac は Phase 2 で「上位ツール導出」vs「L3/MLAG スキーマ例外保持」の二択で再判断 |
| WireGuard トンネル | Phase 2+ (NOS native 非対応) |
| QoS / フロー制御 / PFC / DCB / ETS | 運用設定 (RoCE/AI 用途は Phase 3+) |
| 可視化レイアウト (座標 / 色 / アイコン) | ndl-viz / Cytoscape スタイル |
| Breakout port (100G→4x25G 親子関係) | Phase 2 議題 |
| EVPN Ethernet Segment (ESI/ES-LAG) | Phase 2 議題 (MLAG 代替) |
| BUM 配送方式 (HER vs PIM) | Phase 1 は HER 暗黙前提。Phase 2 で明示判断 |
| 物理配置 (rack U 位置、cabinet ID) | Phase 2 検討 (`meta.site/rack` 任意フィールドとして追加の可否を判断) |
| ベンダー固有 NOS バージョン | アダプター側 |
| sFlow / NetFlow / SNMP 設定 | 運用監視層 |
| L2 トンネル (EoGRE / L2TPv3 / OTV) | Phase 2 で再判断 |
| 別パラダイムプロトコル (PIM / MPLS-LDP / Segment Routing) | Phase 2+ |
| **ポリシールーティング (PBR) / VRF 間のスタティックリーク (route leak / import-map)** (ラウンド4 Pass C で追加) | 上位ツール。D4 補則の問い 2 (転送テーブルの個別エントリ) |
| **スタティックルート / デフォルトルート / redistribute / network 文** (ADR-0011 D2 で追加) | 上位ツール (Ansible / NetBox config context)。ホストのデフォルトゲートウェイは、同一サブネットの SVI の `ip` または `gateway_redundancy.vip` から導出できる |

> **ADR-0011 D4 / D8 で改訂 (2026-10-04)**: 上表の「MAC アドレス全般」のうち、`gateway_redundancy` の
> `anycast_mac` (anycast gateway の MAC) と `MlagLag.system_mac` はスコープ内に確定した。前者は設定生成に必須であり、
> 後者は実装済みだった。それ以外の MAC は引き続きスコープ外。

> **改訂 ([ADR-0022](0022-diagram-granularity.md), 2026-11-08)**: 上の注記を取り消す。`anycast_mac` も `system_mac` も書かない (MAC アドレスは構成図の粒度ではない。D4 補則の問い 5)。
> 上表の「MAC アドレス全般」は例外なくスコープ外に戻る。「EVPN Ethernet Segment (ESI/ES-LAG)」の行は [ADR-0023](0023-per-device-lag-and-ethernet-segments.md) で `layer1.ethernet_segments` として扱った (ESI の値は書かない)。

#### D3-3. 唯一の例外: BFD timer

BFD の `min_tx` / `min_rx` / `multiplier` は、timer の値が隣接形成の可否を直接決めるため**隣接の存在条件**として扱い、スコープ内に保持する。BGP / OSPF / IS-IS の timer (keepalive / hold-time) は隣接確立後のチューニングであり、スコープ外。

### D4. 「構成要素 vs 注釈」の判定フレームワーク

D3 の振り分け判断、および将来の新概念のスコープ内/外判断に使用するフレームワーク (P15 採用)。

| 判定軸 | 構成要素そのもの (スコープ内候補) | 注釈 (スコープ外候補) |
|--------|-------------------------------|----------------------|
| 削除すると参照整合性が崩れるか | Yes | No |
| RFC 8345 ノードグラフから消えるか | Yes | No |
| 値の変更でトポロジーの意味境界が変わるか | Yes | No |
| `broadcast_domain` / `blast_radius` 検索結果に影響するか | Yes | No |

4 軸すべて Yes → スコープ内に含める候補。4 軸すべて No → スコープ外候補。混在する場合は個別判断 (Phase 適切性、ベンダー中立性、上位ツール代替可否を考慮)。

**適用例 — EVPN advertise フラグ群**:
- 削除で参照整合性: No / RFC 8345 グラフ: No / 意味境界: **Yes** (advertise-default-gw の有無で Symmetric IRB の動作が変わる) / blast_radius: **Yes** → 混在 → Phase 2 で「含む」確定予告

**role 等の個別語彙への適用は段階2 (ADR-0003 再設計) で行う**。本 ADR は段階2 の結論を先取りしない。

**段階2 の結論に依存せず確定できる適用例** (P15):
- `description` / `comment`: 4 軸すべて No → 注釈側として全構成要素に optional 許可
- `gateway_redundancy.protocol: anycast_gateway` (enum 値): 値の変更で動作意味が変わる → 注釈ではなく運用パラメータ

#### D4 補則. 表現の指針 (ADR-0011 D1 で追加 2026-10-04、ラウンド4 Pass C で改訂 2026-10-15)

> **関係の成立に必要な情報は書き、関係を流れる個別の経路や処理は書かない。**

mlndl は「VRF が存在する」「この SVI がゲートウェイである」「このトンネルが張れる」といった関係の成立条件を記述し、
その関係を通じて運ばれる個別の経路情報 (route entries) や、個々のパケットへの処理は記述しない。

> **ラウンド4 Pass C で改訂**: 当初は「表現原理」と呼んだが、この一文だけでは判定しきれない項目があった
> (IKE / PSK は関係の成立条件でもある。DHCP relay・NAT・VRF 間のリークは「関係」とも読める)。
> そこで「原理」をやめて**判断の方向を示す指針**とし、次の 3 つの問いと、D3-2 の明示表を合わせて使う。
> 個々の項目の最終判断は D3-2 の表 (と各 ADR) に書く ([round4-evaluation](evaluations/round4-evaluation.md) 論点 D、ユーザー判断)。

4 軸判定が「混在」を返したとき、次の順に問う。4 軸すべて Yes の概念は引き続きスコープ内である。

1. **秘匿情報か** (鍵・パスワード・PSK・認証情報) → 書かない。上位ツールへ (D3-2)
2. **転送テーブルの個別エントリ、または個々のパケットへの処理か** (経路、ACL、NAT 変換、QoS、ポリシールーティング) → 書かない
3. **それを削除すると、その関係自体が存在できなくなるか** (Route Target、トンネルの MTU、VTEP) → 書く

書くと決めたものの**書き方**は、次の問いで決める (drafts/0014 D1 で追加, 2026-10-20)。

4. **違いは関係の形 (持つフィールド・参照先・多重度) の違いか、同じ関係を実現する方式の違いか** →
   形が同じなら 1 つの構文で書き、方式名 (anycast / vPC / virtual VTEP など) は構文に入れない。
   型を分けるのは持つフィールドの形が違うときだけ。方式による設定の違いは `device_type` から上位ツールが導く

問い 1〜3 で「書く」となったものも、次の問いで書かないことがある ([ADR-0022](0022-diagram-granularity.md) D1 で追加, 2026-11-08)。

5. **構成図を読む人が、その値から関係を読み取るか。それとも装置に設定するためだけの値か** →
   装置に設定するためだけの値 (識別子の具体的な値・MAC アドレス・自動で作られる値) は書かない。関係は id の参照で書く。
   書く: VLAN ID・VNI・IP・AS・RD / RT・VRRP の `group_id` / `priority`・冗長のモード。
   書かない: MAC アドレス全般・LACP system-id・ESI の値・MLAG のドメインの番号・vPC 番号 / clag-id・DF の preference

| 書く | 書かない |
|---|---|
| `layer3.interfaces` の IP (到達性の起点) | スタティックルートの宛先とネクストホップ |
| `layer3.vrfs.route_targets` (VPN 境界の定義、RFC 4364) | per-VRF の redistribute ポリシー |
| `gateway_redundancy` の VIP (ゲートウェイの所在) | ホストのルーティングテーブル |
| トンネルの source / destination / MTU | IPsec の暗号化パラメータ (問い 1) |

上の「適用例 — EVPN advertise フラグ群」をこの指針で再判定することは本補則の範囲外とし、ADR-0005 の再設計 (drafts/0005v2) で扱う。

### D5. 三側面と Phase の対応

| Phase | 実装範囲 | 三側面のうち |
|-------|---------|------------|
| **Phase 1** | L1 のみ | (a) 物理構成図、および (c) の L1 内部分 (VM↔hypervisor、論理IF↔物理IF) |
| **Phase 2** | L2 / L3 / protocols 追加 | (b) 論理構成図 (VLAN/VRF/VxLAN/BGP/OSPF/IS-IS/BFD)、および (c) の層間部分 (SVI / tunnel / routing_adjacencies の attaches_to) |
| **Phase 3+** | broadcast_domain / blast_radius クエリ、ValidationPlugin 機構 | クエリ層 (側面は変わらず) |

「スコープ内」と「Phase 1 実装」は別概念。Phase 2 以降のスコープ内概念を Phase 1 中に記述した場合、パーサーは `extra="forbid"` で未知フィールドとして `error` にする。

> **改訂 (2026-11-07)**: Phase 1 と Phase 2 の実装は終わった。「Phase 3+」は、時期の決まらない先送り全般を指す札になっていたので、Phase の札をやめる。
> 先送りした項目は、何が起きたら始めるか (きっかけ) と一緒に [先送りした項目](deferred.md) にまとめた。この ADR と他の ADR の本文に残る「Phase 2 で」「Phase 3+ で」は、その一覧の行に読み替える。
> スキーマにないキーを書くと `extra="forbid"` で error になる点は変わらない。

### D6. `node` の持ち方 (ラウンド4 Pass C で追加, 2026-10-15)

エンティティが `node` を持つかどうかは、次の基準で決める ([round4-evaluation](evaluations/round4-evaluation.md) 論点 B)。

> **ノードごとに独立した設定値 (IP・MAC・状態) を持つエンティティは `node` が必須。
> L2 の属性 (タグ番号・VLAN の所属) だけを持ち、参照先 (L1 IF / LAG) からノードが決まるエンティティは `node` を書かない。**

| エンティティ | `node` | 理由 |
|---|---|---|
| `layer1.interfaces` | 必須 | 物理ポートの所属そのもの |
| `layer3.interfaces` | 必須 | ノードごとに別の IP を持つ。MLAG 上の L3 IF もノードごとに 1 つずつ書く |
| `layer3.tunnel_interfaces` | 必須 | source / destination をノードごとに持つ |
| `layer2.subinterfaces` | 書かない | タグ番号だけを持つ。ノードは基盤 (L1 IF / LAG) から決まる。MLAG 上なら両ノード |
| VLAN の `trunk_ports` / `access_ports` | 書かない | VLAN の所属だけを表す。ノードは `interface` / `lag` から決まる。MLAG なら両ノード |

VLAN のポートの `node` は、ADR-0013 (Pass A) では「任意 (書けば照合)」だった。サブ IF と揃えて書かない形に改めた
(ユーザー判断)。ndl_version 1.x の間は旧形式として受け付け、validator が warning を出して照合する。

## Consequences

### 良い影響

- **新概念のスコープ判定が機械化される**: D4 フレームワーク (4 軸 Yes/No) により「分からないので議論」から「判定軸を当てて決める」運用に移行できる
- **既存 ADR の根拠が遡及的に強化**: ADR-0003 の `vswitch` 除外、ADR-0004 の「EVE-NG を知らない」原則、ADR-0001 の supporting 単一手段方針 — すべて本 ADR D1/D2 から導出可能
- **SVI 表現規則の明文化**: Phase 2 着手時のスキーマ実装の手戻りが減る
- **tunnel_interfaces と tunnel_links の対称性**: Phase 2 でトンネルを記述する際の構文混乱が予防される
- **NetBox アダプター実装の指針**: D3-1 末尾のマトリクスにより型振り分けが自動判定可能
- **ユーザー発話の保全**: 「物理構成図・論理構成図・物理と論理の連携」という意思決定が ADR として保存される

### 悪い影響 / トレードオフ

- **(c) が独立側面でないことの認知コスト**: D1 で「純粋 MECE ではない」と明示した結果、「三側面の言語」という説明には常に注記が必要
- **EVPN advertise フラグ群の Phase 2 確定予告の重さ**: `advertise-default-gw` / `advertise-pip` は MLAG + Symmetric IRB で事実上必須。Phase 2 で「含む」確定を行わない場合、「mlndl で書けるが実機で動かない」構成が生まれる。**Phase 2 着手時の最優先判断項目**
- **OpenConfig 片方向エクスポートの制限**: mlndl → OpenConfig の片方向エクスポートは実装可能。逆方向 (OpenConfig → mlndl) は仕様として保証しない。Phase 2 直後に PoC を試作して変換複雑度を実測する (ラウンド1.5 プラン申し送り)
- **D4 の段階2 先送り**: 本 ADR の Consequences は段階2 完了後に追記が必要な不完全な状態で Accepted になる

### 影響を受けるコンポーネント

- **スキーマ** (`src/mlndl/schema/`): Phase 1 は影響なし。Phase 2 で `layer2.subinterfaces` / `layer3.tunnel_interfaces` / `layer3.tunnel_links` / SVI 二段表現対応
- **バリデーター** (`src/mlndl/validator.py`): Phase 1 は `extra="forbid"` で Phase 2 概念を拒否。Phase 2 で SVI 参照解決、tunnel entity/relation 対応チェック
- **エクスポーター**: `rfc8345.py` は D2-1 の圧縮表現前提でネスト化復元ロジックを実装 (ADR-0001 D7)。mlndl → OpenConfig は片方向エクスポートとして割り切り
- **ADR-0003 (再設計予定)**: 本 ADR D3 + D4 が段階2 再設計の直接の入力
- **ADR-0004 (条件付き影響)**: 段階2 で `role: hypervisor` 語彙が変わる場合、ADR-0004 D-1 の文言調整が必要 (`evaluations/round1.5-evaluation.md` 既存 ADR 影響評価章で判定)

## Alternatives Considered

### Alt-1. 三層 (L1/L2/L3) を直接 mlndl の表現スコープとして宣言する

- **却下理由**: L1/L2/L3 は OSI レイヤー番号と混同しやすい。ユーザー発話「物理構成図・論理構成図・物理と論理の連携」を直接反映していない。(c) (`attaches_to` による supporting) が各層内の話なのか層間の話なのかが曖昧

### Alt-2. スコープ ADR を作らず、CLAUDE.md の散発記述に留める

- **却下理由**: 新概念のスコープ判定が個別議論になり一貫性がない。ADR-0001〜0004 の上位文書が欠落する。ユーザー方針 (ラウンド1.5 ゴール) と直接矛盾

### Alt-3. 三側面を厳密 MECE として定義し、すべてのエンティティを各側面に振り分ける

- **却下理由**: port_channel / MLAG / SVI / tunnel_interfaces はいずれも (a)(b) 境界をまたぐエンティティ。どちらか一方にしか属さないとする MECE 分類は実装上の表現を歪める。Pass B (P2, P10) で dsl-designer / linguist が独立に同様の指摘 → 本 ADR は D1 で MECE 主張を放棄し「三側面 (操作的分類)」に再定義

### Alt-4. RFC 8345 のネスト構造を mlndl の正規形として採用 (OpenConfig 風)

- **却下理由**: DSL としての記述量が増加 (ADR-0001 D1)。MLNDL 原案 (NAIST, 2011) の MLNDL 設計思想 — 単一フィールド `attaches_to` で supporting を表現する — の継承が失われる。圧縮表現 → RFC 8345 への変換はエクスポーターで担保 (ADR-0001 D7)

### Alt-5. EVPN advertise フラグ群を Phase 2 で「含めない」確定する

- **却下理由**: MLAG + Symmetric IRB は advertise フラグなしでは実機動作しない (network-tech P7 指摘)。D4 フレームワーク適用結果、4 軸中 2 軸が Yes → 混在 → 「含む」方向で Phase 2 確定予告が適切

## Pass A との差分

### 採用した指摘 (Pass A から変更)

| 指摘 | 変更内容 | 重要度 |
|------|---------|--------|
| **P1** 時制矛盾 | D3-1 を「Phase 1 実装」と「スコープ内 (Phase 2 以降)」の 2 ブロックに分離 | 高 |
| **P2** (c) は独立軸でない | D1 で「三側面 (操作的分類)」に再定義。「純粋 MECE ではない」と明記 | 高 |
| **P3** SVI 二段表現規則の欠落 | D2-2 ケース B として SVI 表現を B-1/B-2 で規範化 | 高 |
| **P4** 「アグリゲーション primitive」 | D3-1 で「リンクアグリゲーション (LAG, single-chassis / multi-chassis)」に変更 | 中 |
| **P5** `address_families` 値域 | D3-1 で `[ipv4_unicast \| ipv6_unicast \| l2vpn_evpn \| vpnv4 \| vpnv6]` を明示 | 中 |
| **P6** BGP unnumbered `remote_as` 値域 | `remote_as: <ASN> \| external \| internal` を D3-1 に明示 | 中 |
| **P7** EVPN advertise フラグ群 | Consequences + D3-1 Phase 2 に「含む確定予告」を明記 | 中 |
| **P8** tunnel_interfaces と tunnel_links | D3-1 に entity/relation の対称性を注釈 | 中 |
| **P9** NetBox Interface type マトリクス | D3-1 末尾に振り分け表を追加 | 中 |
| **P10** 「三軸」→「三側面」 | D1 で「三側面 (three aspects)」を採用。略号 (a)/(b)/(c) は維持 | 中 |
| **P14** OpenConfig 往復変換の非対称性 | D2-1 + Consequences に「片方向エクスポート」として明記 | 中 |
| **P15** 「判定枠組」→「判定フレームワーク」 | D4 タイトル変更。表現整理 | 低 |

### Phase 2 申し送りに留めた指摘

| 指摘 | 理由 |
|------|------|
| **P11** `meta.site/rack` の Phase 1 追加 | Phase 1 スコープ最小化を優先。Phase 2 で `meta.source_refs` と合わせて設計 |
| **P12** MLAG system-mac の上位ツール導出困難性 | D3-2 で「Phase 2 で再判断」と既記載 |
| **P13** Breakout port / ESI-LAG / Loopback 意図タグ | D3-2 / Phase 2 議題リストに収録 |

### 独立に同じ結論に到達した点 (Pass A の正当性が高い箇所)

- **MAC アドレスは原則扱わない**: 全 4 レビュアーが直接異議なし → D3-2 で維持
- **`attaches_to` 単一手段方針**: ADR-0001 D1 と整合 → D2-4 で再確認
- **RFC 8345 supporting model への準拠**: ecosystem が ◎ と評価 → D1 表で対応関係を維持
- **BFD timer を唯一の例外として保持**: network-tech が構造的正当性を確認 → D3-3 で独立節として定義
- **EVE-NG 固有情報のスコープ外**: ADR-0004 の原則と一貫 → D3-2 で維持
- **D4 を判定基準のみ提示し段階2 の結論を先取りしない**: ラウンド1.5 プランの方針を維持

## 実装同期メモ (2026-10-04)

本 ADR の判断 (三側面・D4 判定フレームワーク・スコープの線引き) は維持したまま、後続 ADR で改訂・実装された箇所の一覧。
各箇所には本文中にも注記を入れている。

| 箇所 | 改訂内容 | 改訂元 |
|---|---|---|
| D2-2 ケース B 規範 | B-1 は validator 内でのみ解決し、B-2 への正規化はモデルに格納しない。`interface` は機器上の名前 | ADR-0011 D3 |
| D2-2 ケース C | サブ IF の親参照は `parent` ではなく `attaches_to` | ADR-0011 D8 |
| D2-4 | `layer3.interfaces[].vlan` を廃止 | ADR-0011 D3 |
| D3-1 Phase 1 表 | `endpoints` / `lag` / `description` の 1 語化 / `link_role` に `trunk` | ADR-0006 / §6 / ADR-0011 D7・D8 |
| D3-1 Phase 2 表 | `ip` / `ipv6`、`gateway_redundancy` の Tagged Union、`tunnel_links` の廃止、`vtep_source` の書式 | ADR-0011 D4〜D6・D8 |
| D2-2 ケース C / D2-3 / D3-1 | サブインターフェースを実装。`{interface:}` が指せる ID 空間をエンティティごとに固定 | ADR-0012 |
| D3-2 | スタティックルート等をスコープ外に追加。`anycast_mac` / `system_mac` をスコープ内に確定 | ADR-0011 D2・D4・D8 |
| D4 | 補則として表現原理を追加 | ADR-0011 D1 |
| D4 補則 | 「原理」を「指針」に改め、3 つの問いと D3-2 の明示表で判断する形にした | ラウンド4 Pass C (論点 D) |
| D6 (新設) | `node` を持つかどうかの基準 | ラウンド4 Pass C (論点 B) |
| D2-2 ケース B / D2-3 | SVI は `attaches_to: {vlan:}`、機器上の名前は `name`。短縮形 `interface: vlan-N` は廃止 (1.x の間は warning で受け付ける)。`{interface:}` は L1 IF 専用 | ADR-0001 D8、ADR-0011 D3 (Pass C) |
| D3-2 | ポリシールーティングと VRF 間のスタティックリークをスコープ外に追加 | ラウンド4 Pass C |
| D4 補則 | 問い 4 (方式中立。型を分けるのはフィールドの形が違うときだけ) を追加 | drafts/0014 D1 |
| D1・D3-1 (制御プレーンの行・(c) の routing_adjacencies 行)・P6・BGP unnumbered の規則 | `control_plane` への分離。VRF ごとの BGP インスタンス、セッションの通り道は導く、unnumbered はアドレスのない L3 IF | ADR-0010 (2026-11-01。Accepted・実装済み) |
| D3-2・D4 補則 | 問い 5 (構成図の粒度) を追加。`anycast_mac` / `system_mac` をスコープ外に戻した | ADR-0022 (2026-11-08) |
| D3-2 | EVPN Ethernet Segment を `layer1.ethernet_segments` として扱った (MLAG / vPC / MC-LAG と同じ形) | ADR-0023 (2026-11-08) |
| D3-1 Phase 1 表 | `layer1.nodes` の `overrides` をなくした | ADR-0024 (2026-11-09) |

## References

- `CLAUDE.md`
- `docs/decisions/evaluations/round1.5-evaluation.md` — Pass B 評価メモ (段階1 章)
- ラウンド1.5 の作業プラン (リポジトリ外) — ラウンド1.5 プラン
- ADR-0001 (Pass C) — `attaches_to` 単一フィールド方針、タグ付き Union
- ADR-0002 (Pass C) — ID グローバル一意性 (D5)、severity 定義 (D8)
- ADR-0003 (Pass C) — `role` canonical 9 語彙。段階2 で本 ADR を入力に Reopen 予定
- ADR-0004 (Pass C) — `implementation × role` の責務分離、「技術的不可能性のみ error」基準
- RFC 8345 — A YANG Data Model for Network Topologies
- RFC 8346 (L3 Topology) / RFC 8944 (L2 Topology) — Phase 2 で参照
- MLNDL 原案 (NAIST, 2011) — MLNDL における三層モデル、`attachesTo` 概念、`broadcast_domain` 検索
