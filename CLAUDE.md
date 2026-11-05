# mlndl プロジェクト

**設計の根拠**: `docs/decisions/` の ADR を参照（言語の設計決定とその経緯）

**利用者向けの文書**: `docs/README.ja.md`（考え方 `docs/concepts.ja.md`、言語リファレンス `docs/reference/`）。構文や検査を変えたら、この CLAUDE.md の要約とあわせて `docs/reference/` も直すこと

## エージェント運用ルール

**設計判断・仕様議論・ADR 作成・MLNDL の設計に関する質問には、必ず以下の 5 エージェントを並列起動してから統合回答を作ること。**

| エージェント | 役割 |
|---|---|
| `mlndl-spec-architect` | 仕様統合・ADR 判断 |
| `mlndl-linguist` | 命名・意味論評価 |
| `mlndl-dsl-designer` | DSL 構造・直交性 |
| `network-tech-reviewer` | ネットワーク技術的妥当性 |
| `mlndl-example-author` | YAML 試し書きによる実証 |

対象外（単独で回答してよい）: コーディング・ファイル操作・単純な質問・動作確認。

---

## このパッケージの位置づけ

MLNDL 原案 (NAIST, 2011) で提案した**マルチレイヤ NDL（MLNDL）** の現代的再実装。

- 原案での実装: C++ の処理系と、対話型の検索ツール
- 本パッケージ: Python / pydantic v2 で再実装した独立 pip パッケージ

### エコシステム内の役割

```
【ソース層】
  neteye / NetBox / 手書き YAML
       ↓（アダプター経由）
【mlndl】← このパッケージ（スキーマ・パーサー・バリデーター・エクスポーター）
       ↓
【利用層】
  ndl-viz（可視化）/ eve-lab-builder（EVE-NG デプロイ）
```

mlndl は EVE-NG を知らない。ndl-viz も知らない。純粋な中間フォーマットライブラリ。

---

## 重要な設計決定（議論で確定済み）

### 1. `attaches_to` — Supporting Relationship の統一フィールド

> **→ 詳細: [ADR-0001](docs/decisions/0001-attaches-to.md)**

RFC8345 の "supporting" 関係（下位層が上位層の物理基盤となる関係）を **`attaches_to` に統一**。

| レベル | 書き方 | 意味 | RFC8345 対応 |
|--------|--------|------|-------------|
| ノード | `attaches_to: eve-server`（文字列） | この VM はこのホスト上で動く | supporting-node |
| ノード | `attaches_to: {node: eve-server}` | 同上（オブジェクト形式）— プログラム生成時はこちらを推奨 | supporting-node |
| インターフェース | `attaches_to: {interface: leaf1-swp51}` | この論理 IF はこの物理ポート (L1 IF) で実現 | supporting-termination-point |
| LAG | `attaches_to: {lag: lag-border1-po1}` | routed LAG / LAG 上のサブ IF | supporting-termination-point |
| VLAN | `attaches_to: {vlan: vlan-100}` | SVI | supporting-termination-point |
| サブ IF | `attaches_to: {subinterface: subif-br1-eth0-10}` | サブ IF に載る L3 IF | supporting-termination-point |
| リンク（LAG） | `lag.members: [...]` | members が意味的に自然なのでそのまま | supporting-link |

pydantic での型定義: `attaches_to: str | AttachesTo`（文字列ならノードID糖衣構文、オブジェクトは `{node:}` / `{interface:}` / `{lag:}` / `{vlan:}` / `{subinterface:}` のいずれか 1 キー）

**キー名が参照先の種類を示す**（ADR-0001 D8、ラウンド4 Pass C）。`{interface:}` は L1 IF 専用。どのキーを書けるかはエンティティごとにスキーマで制限する:
L1 ノード / L1 IF は `node` / `interface`、`layer2.subinterfaces` は `interface` / `lag`、`layer3.interfaces` は `interface` / `lag` / `vlan` / `subinterface`。
旧形式 `{interface: <LAG / VLAN / サブ IF の id>}` は ndl_version 1.x の間だけ warning 付きで受け付ける。

BGP 等のセッション（`control_plane.routing_neighbors`）は `attaches_to` を持たない。通り道は `update_source` の L3 IF の `attaches_to` から導く
（ADR-0010 D7。`{link:}` キーは ADR-0010 で削除し、書くと移動先を示すエラーになる）。

旧形式（使わない）:
- `{layer: layer1, interface: swp51}` — `layer` フィールドは廃止（グローバル一意 ID なので不要）
- `supporting_interface`、`routing_adjacencies[].supporting`、`{link:}`（ADR-0010）

### 2. `implementation` フィールド

> **→ 詳細: [ADR-0004](docs/decisions/0004-implementation-role-matrix.md)**

`type: virtual` は廃止。Layer1 は物理トポロジーを表すレイヤーなので `virtual` は概念的に矛盾。

```yaml
implementation: vm          # 仮想マシン
implementation: physical    # 物理機器
implementation: container   # コンテナ
```

### 3. `ndl_version` — 必須フィールド

```python
class MLNDLTopology(BaseModel):
    ndl_version: str = "1.0"

    @model_validator(mode="before")
    @classmethod
    def check_version(cls, data: dict) -> dict:
        ver = data.get("ndl_version", "")
        major = int(ver.split(".")[0]) if ver else 0
        if major != 1:
            raise ValueError(f"Unsupported MLNDL version: {ver}. Expected 1.x")
        return data
```

### 4. セキュリティ

- `yaml.SafeLoader` で読む（`safe_load` と同じ。`yaml.load()` に任意のローダーを渡さない）。同じマッピングでのキーの重複は error（PyYAML は黙って後勝ちにするので、ローダーで検出する）
- 入力サイズ上限: `MAX_TOPOLOGY_BYTES = 1 * 1024 * 1024`（1MB）

### 5. `layer1.nodes.role` 語彙

> **→ 詳細: [ADR-0003](docs/decisions/0003-role-vocabulary.md)** (Pass C2 — ラウンド1.5 再設計後)

`role` は **注釈側構成子** (ADR-0005 D4 で 4 軸全 No と判定)。mlndl コアは値域チェックを行わない。

```yaml
role: spine        # 自由文字列。構文制約なし。未指定でも valid
```

**推奨語彙 (informative)**: `docs/role-vocabulary.md` を参照。以下の 9 語が推奨値として定義されており、ndl-viz の既定スタイルが適用される:

```
spine | leaf | core | border | server | firewall | load-balancer | hypervisor | management
```

推奨値以外の `role` 値 (例: `tap-aggregator`, `dpu-offload`) も valid。mlndl は warning を出さない。

**唯一の例外**: `implementation: container` + `role: hypervisor` の組み合わせは **error** (ADR-0004 D-1、normative token)。

ID 命名規則も参照: [ADR-0002](docs/decisions/0002-id-naming-convention.md)

---

### 6. `lag` — LACP と MLAG の統一フィールド

`port_channels`（単一ノード LAG）と `mlag`（マルチシャーシ LAG）を **`lag` フィールドに統合**。`type` で区別する。

```yaml
lag:
  - id: lag-leaf1-bond0           # LACP: 単一ノードの bond
    type: lacp
    node: leaf1                   # 単数形: lacp は 1 ノード
    members: [leaf1-swp1, leaf1-swp2]
    lacp: {mode: active, min_links: 1}

  - id: lag-mlag-server1          # MLAG: 2 ノードにまたがる bond
    type: mlag
    nodes: [leaf1, leaf2]         # 複数形: mlag は 2 ノード
    members: [leaf1-swp3, leaf2-swp3]
    lacp: {mode: active, min_links: 1}
    peer_link: lag-peer-link      # 同じ lag リスト内の別エントリを参照
    peer_link_interface: peerlink.4094
    domain_id: 10
```

pydantic での型定義（Discriminated Union）:

```python
class LacpLag(BaseModel):
    type: Literal["lacp"]
    node: str                          # 単一ノード
    members: list[str]
    lacp: LacpConfig | None = None

class MlagLag(BaseModel):
    type: Literal["mlag"]
    nodes: list[str]                   # 2 ノード固定
    members: list[str]
    lacp: LacpConfig | None = None
    peer_link: str                     # lag.id を参照
    peer_link_interface: str
    domain_id: int | None = None

Lag = Annotated[LacpLag | MlagLag, Field(discriminator="type")]
```

廃止フィールド（使わない）: `port_channels`、`mlag`（トップレベルキー）

### 8. device_type は抽象キー

EVE-NG 固有情報（template/cpu/ram）は mlndl に書かない。

```yaml
# mlndl YAML 内
- id: spine1
  device_type: cumulus_linux   # 抽象キー

# eve-lab-builder/config/device_mapping.yaml で変換
cumulus_linux:
  template: cumulus-vx
  cpu: 2
  ram: 2048
```

### 9. 仮想化環境の L1 表現

> **根拠: [ADR-0003](docs/decisions/0003-role-vocabulary.md) D1・D6 / [ADR-0005](docs/decisions/0005-mlndl-expressive-scope.md) D1**

`vswitch`/`dvswitch` は **L1 canonical roles ではない**。vSwitch はソフトウェア機能であり物理的な「箱」ではないため L1 に属さない。Phase 2 の L2 スキーマで扱う。

**L1 での表現方針**:

```yaml
# ハイパーバイザホスト
- id: esxi-01
  role: hypervisor
  implementation: physical

# ハイパーバイザ上の VM ノード
- id: spine1
  role: spine
  implementation: vm
  attaches_to: esxi-01          # 文字列 = ノードID（糖衣構文）
  # または attaches_to: {node: esxi-01}

# ESXi の物理 NIC → ToR スイッチへの物理ケーブルは L1 links で表現
```

`vswitch`/`dvswitch` の仮想スイッチング機能は Phase 2 L2 スキーマ (`layer2.bridges` 等) で設計予定。

---

### 10. `labels` — 多軸分類（注釈側構成子）

> **→ 詳細: [ADR-0009](docs/decisions/0009-membership-orthogonality.md) / 推奨軸名: [docs/label-vocabulary.md](docs/label-vocabulary.md)**

ノードが**同時に複数の直交した軸に所属する**ことを表す key-value マップ。**Phase 1 実装済み**。

```yaml
- id: leaf1
  role: leaf
  attaches_to: esxi-01       # Realization  — どこで動くか（物理基盤）
  parent: pod-tokyo          # Containment  — どこに属するか（論理階層・Phase 3+）
  labels:                    # Classification — どんな属性か（多軸）
    az: ap-northeast-1a
    tenant: acme
    env: prod
```

**三構成子の直交性**（ADR-0009 D1）:

| 構成子 | 意味論 | 多重性 | 値 | 判定基準 |
|--------|--------|--------|-----|---------|
| `attaches_to` | Realization（RFC8345 supporting） | 単一 | ID 参照 | これを外すと**動作が止まる** |
| `parent` | Containment（論理階層） | 単一、連鎖でネスト | ID 参照 | 外しても動くが**分類から外れる** |
| `labels` | Classification（多軸分類） | 多重（map） | **自由文字列・非参照** | 参照ではない属性 |

**`labels` の性質**:

- キーもバリューも**自由文字列**。コアは値域・キー域チェックを一切しない（`role` と同じ注釈側）
- 値の型は `str` のみ。`labels: {vlan: 100}` は error
- 未指定（`None`）でも valid
- **値は参照ではない** — `labels: {pod: pod-tokyo}` は `pod-tokyo` というノードを指していない。
  属性を持つ箱に所属させたい場合は `parent:` を使う
- キーは ADR-0002 D1 の ID 正規表現への準拠を推奨（表記揺れ防止）。違反は **warning**
  （`validate_all()` / CLI で表示。`validate()` の戻り値には含まれない）

**予約語**（ADR-0002 追記）: bare `label` / `tag` はフィールド名として使用禁止。
MPLS は `mpls_label` / `label_stack`、802.1Q は `vlan_id`（実装済み）、Q-in-Q は `stag_vlan_id` / `ctag_vlan_id`。

**未解決**: `labels` は障害軸（`az`/`pod`/`rack`）と管理軸（`tenant`/`env`）をフラットに混在させるため、
Phase 3+ の `blast_radius` クエリが軸の性質を区別できない。当面は `docs/label-vocabulary.md` の分類を
informative な指針とし、必要が明確になった時点で構造化構成子に昇格させる（加算的変更）。

### 11. サイト・事業者網・回線情報（構文は足さない）

> **→ 詳細: [ADR-0017](docs/decisions/0017-sites-and-wan.md)**

- **サイト**は `labels: {site: tokyo}`（値はサイトの名前そのまま。`site-tokyo` としない）。規約で、書かなくても valid。サイト間のリンクは両端の `site` の違いから取り出す
- **2 点間の回線**（専用線・L2 専用線・ダークファイバ・波長）は `L1Link`。**事業者網への接続**（IP-VPN・広域イーサ・インターネット・閉域接続）は
  `role: provider-network` の箱ノード + 拠点から箱への `L1Link`。サービスの種類は `role` で分けず箱の `name` に書く。箱は L3 IF を持たない（規約。検査しない）
- **回線 ID・契約帯域・事業者名**は `description` に書く。書式は決めず、ツールはパースしない。`labels` には書かない。`link_role` に `wan` などの推奨値は足さない
- **事業者の機器**（PE・クラウドのルーター）との BGP は、相手をトポロジー外 `{address, local_as}` で書く
- **広域イーサ越しに自社の機器どうしが張る BGP** は、当面は片側をトポロジー外として書く（両端 `node` は ADR-0010 D7 で error）。
  3 拠点以上の広域イーサの OSPF / IS-IS は範囲外。構文は次の ADR で決める
- **→ ADR-0018 で決着**: 箱の中の L2 の転送は `layer2.bridges`（`ports` は箱のポートだけ）に書き、両端 `node` で書く。トンネルの上のセッションは `update_source` / OSPF の `interface` にトンネル IF を書く

---

## MLNDL フォーマット概要

各キーの正確な定義は `docs/reference/` にある。ここは設計の判断に使う要約。

```yaml
ndl_version: "1.0"    # 必須

meta:
  name: dc-spine-leaf-lab
  network_types: [l1-physical, l2-network, l3-unicast]

layer1:
  nodes:
    - id: spine1
      name: Spine-1
      implementation: vm
      attaches_to: eve-server    # 文字列 = ノードID（糖衣構文）
      role: spine                # 自由文字列 (推奨値: docs/role-vocabulary.md 参照)
      device_type: cumulus_linux
      labels:                    # 任意: 多軸分類（ADR-0009）。キー・値とも自由文字列
        site: tokyo              # サイト（ADR-0017）。図のサイトの枠になる
        az: ap-northeast-1a
        tenant: acme
      overrides:                 # 任意: eve-lab-builder のデフォルト値を上書き
        eve_ng:
          cpu: 4

  interfaces:
    - id: spine1-swp1
      node: spine1
      name: swp1

  links:
    - id: link-spine1-leaf1
      endpoints: [spine1-swp1, leaf1-swp51]   # 順序非依存（ADR-0006: 物理リンクは無向）
      link_speed: 10G
      mtu: 9216                  # VxLAN 使用時は 1550 以上必須（推奨 9216）
      link_role: underlay        # 自由文字列。推奨: underlay/access/trunk/peer-link/management/uplink

  lag:
    - id: lag-leaf1-bond0           # LACP: 単一ノードの bond
      type: lacp
      node: leaf1
      members: [leaf1-swp1, leaf1-swp2]
      lacp: {mode: active, min_links: 1}

    - id: lag-mlag-server1          # MLAG: 2 ノードにまたがる bond
      type: mlag
      nodes: [leaf1, leaf2]
      members: [leaf1-swp3, leaf2-swp3]
      lacp: {mode: active, min_links: 1}
      peer_link: lag-peer-link
      peer_link_interface: peerlink.4094
      domain_id: 10

layer2:
  vlans:
    - id: vlan-100              # ADR-0002: vlan-<N> 形式
      vlan_id: 100
      trunk_ports:               # {interface: <L1 IF id>} か {lag: <LAG id>}（ADR-0013）。機器上の名前ではない
        - {lag: lag-mlag-server1}          # LAG はメンバーでなく LAG を指す。MLAG は 1 行で両ノード
        - {interface: leaf1-swp4}          # node は書かない（参照先から導出。ADR-0005 D6）
      access_ports:
        - {interface: server1-eth0}

  bridges:                       # ADR-0018。番号を持たない L2 セグメント（事業者網の箱の中の転送）
    - id: bridge-wideether       # 推奨プレフィックス bridge-。回線 ID は id に埋めず name / description に
      name: WE-220
      ports:                     # 転送する側（箱）のポートだけ。{interface:} か {lag:}。拠点のルーターのポートは書かない
        - {interface: net-wideether-tokyo}
        - {interface: net-wideether-osaka}
      # 方式名（E-LINE / VPLS 等）は書かない。bridge を書かない箱は L2 で透過しない

  vteps:                         # ADR-0014。VXLAN のトンネル端点。方式名（anycast 等）は構文に出さない
    - id: vtep-leaf1-leaf2       # 推奨プレフィックス vtep-
      sources: [leaf1-lo, leaf2-lo]   # この VTEP を終端するノードの L3 IF（ループバック）。node は書かない
      address: 10.0.100.12/32    # VTEP のアドレス（IPv6 は address_v6）。複数ノードで共有するときは必須
    - id: vtep-border1
      sources: [border1-lo]      # sources が 1 つなら address は省略でき、その L3 IF の ip になる

  vxlan:
    - id: vni-10100             # ADR-0002: vni-<N> 形式
      type: l2vni                # l2vni / l3vni を明示
      vni: 10100
      vlan: vlan-100
      vteps: [vtep-leaf1-leaf2, vtep-border1]   # 参加ノードは VTEP から導出（旧 vtep_source / members は 1.x の間 warning）
    - id: vni-10900
      type: l3vni                # Symmetric IRB 用 L3VNI（必須）
      vni: 10900
      vrf: vrf-tenant-a
      irb_mode: symmetric

  subinterfaces:                 # ADR-0012。L3 の routed サブ IF（router-on-a-stick 等）
    - id: subif-border1-swp5-200 # 推奨プレフィックス subif-
      attaches_to: {interface: border1-swp5}   # 基盤: {interface: <L1 IF>} か {lag: <LAG>}
      vlan_id: 200               # このリンク上の 802.1Q タグ番号（layer2.vlans への参照ではない）
      name: swp5.200             # 機器上の名前
      # node は持たない（基盤から導出。ADR-0005 D6）。ip / vrf は layer3.interfaces 側に書く

layer3:
  vrfs:
    - id: vrf-tenant-a
      rd: "65001:100"
      l3vni: vni-10900           # VRF ↔ L3VNI バインディング
      route_targets:
        import: ["65001:100"]
        export: ["65001:100"]

  interfaces:
    - id: leaf1-swp51-l3
      node: leaf1                # 必須（ノードごとに別の IP を持つ。ADR-0005 D6）
      name: swp51                # 機器上の名前（参照ではない。ADR-0011 D3）
      ip: 10.1.0.1/31            # IPv4 専用（ADR-0011 D5）
      ipv6: 2001:db8:1::1/127    # IPv6 は別フィールド。いずれも単数
      vrf: vrf-default
      attaches_to:               # 唯一の参照手段。キーが参照先の種類を示す（ADR-0001 D8）
        interface: leaf1-swp51  # {interface:} は L1 IF 専用

    - id: leaf1-vlan-100         # SVI: attaches_to: {vlan: <VLAN id>}（短縮形 interface: vlan-N は廃止）
      node: leaf1
      name: Vlan100
      attaches_to: {vlan: vlan-100}
      ip: 192.168.100.1/24      # anycast 構成では全 leaf で同一 IP（validator が照合する）
      vrf: vrf-tenant-a
      gateway_redundancy:        # ADR-0011 D4（旧 fhrp）。mode で分岐する Tagged Union
        - {mode: anycast_gateway, anycast_mac: "44:38:39:be:ef:aa"}
        # VRRP の場合（IPv4 と IPv6 は別エントリ。IPv6 の VIP はリンクローカル）:
        # - {mode: vrrp, group_id: 100, vip: 192.168.100.254, priority: 110}
        # - {mode: vrrp, group_id: 100, vip: "fe80::1", priority: 110}

    - id: border1-po1            # routed LAG
      node: border1
      name: Port-channel1
      attaches_to: {lag: lag-border1-po1}
      ip: 10.250.0.1/31

    - id: border1-swp5-200       # サブ IF に載る L3
      node: border1
      name: swp5.200
      attaches_to: {subinterface: subif-border1-swp5-200}
      ip: 10.200.0.1/30
      vrf: vrf-default

    - id: leaf1-lo               # ループバックは attaches_to を持たない
      node: leaf1
      name: lo
      ip: 10.0.0.1/32
    - {id: leaf2-lo, node: leaf2, name: lo, ip: 10.0.0.2/32}
    - {id: border1-lo, node: border1, name: lo, ip: 10.0.0.21/32}   # vtep-border1 のアドレスになる

  tunnel_interfaces:             # ADR-0011 D6。source / destination を自分で持つ（tunnel_links はない）
    - id: tunnel-border1-dc2
      node: border1
      type: gre                  # gre / ipip / ipsec_vti / wireguard
      source: border1-wan        # layer3.interfaces[].id（同じ node のもの）
      destination_interface: dc2-border1-wan   # トポロジー外なら destination_ip（どちらか一方）
      ip: 172.31.0.1/30
      vrf: vrf-tenant-a          # トンネル IF が属する VRF（overlay 側）
      transport_vrf: vrf-default # 外側パケットが流れる VRF
      mtu: 1476

control_plane:                   # ADR-0010。書かなくてもよい（データプレーンだけの記述も valid）
  bgp:                           # 1 エントリ = 1 つの VRF の BGP インスタンス（全ノード分）
    - id: bgp-default            # vrf 省略 = default VRF
      nodes:
        - {node: spine1, local_as: 65000}
        - {node: leaf1,  local_as: 65001}
    - id: bgp-tenant-a           # VRF-lite 等はテナントの VRF ごとのインスタンスに
      vrf: vrf-tenant-a
      nodes: [{node: border1, local_as: 65021}]

  bfd:                           # タイマー。BFD を張るかはセッションの bfd で決める
    - {id: bfd-global, min_tx: 300, min_rx: 300, multiplier: 3, nodes: [spine1, leaf1]}

  routing_neighbors:             # 1 エントリ = 1 セッション（BGP / OSPF / IS-IS）
    - id: bgp-peer-spine1-leaf1  # ADR-0002: bgp-peer-* 形式
      type: bgp
      instance: bgp-default      # BGP のエントリが 1 つなら省略できる
      from: {node: spine1, update_source: spine1-swp1-l3}   # update_source は必須（L3 IF の id）
      to:   {node: leaf1,  update_source: leaf1-swp51-l3}
      address_families: [ipv4_unicast]   # 1 本で複数運べる（[ipv4_unicast, l2vpn_evpn]）
      bfd: true
      # attaches_to は書かない。通り道は update_source の L3 IF から導く（直結の /31 → link-spine1-leaf1）
    - id: bgp-peer-spine1-leaf1-overlay   # 同じ組の 2 本目は用途の語を末尾に
      type: bgp
      from: {node: spine1, update_source: spine1-lo}   # ループバックどうし = multihop
      to:   {node: leaf1,  update_source: leaf1-lo}
      address_families: [l2vpn_evpn]
    - id: bgp-peer-border1-isp
      type: bgp
      instance: bgp-default
      from: {node: border1, update_source: border1-lo}
      to: {address: 203.0.113.1, local_as: 64500}       # トポロジー外の相手は address + local_as
    - id: bgp-peer-border1-dc2-gre
      type: bgp
      from: {node: border1, update_source: tunnel-border1-dc2}   # トンネル IF も書ける（ADR-0018 D3。OSPF の interface も同じ）
      to:   {node: dc2-border1, update_source: tunnel-dc2-border1}
      # 通り道は対になるトンネル {tunnel: [from, to]}。箱をはさむ両端が同じ bridge に届けば {bridge: <id>}（ADR-0018 D2）
    # unnumbered: update_source が ip も ipv6 も持たない L3 IF を指す（ADR-0010 D4）
    # RR: クライアント側の端点に route_reflector_client: true（iBGP のみ）
    # eBGP / iBGP は両端の local_as から導く。underlay / overlay は書かず AF と VRF から導く（ADR-0010 D6）
```

---

## ディレクトリ構造

```
mlndl/
├── src/
│   └── mlndl/
│       ├── __init__.py
│       ├── schema/
│       │   ├── layer1.py       # L1Node, L1Interface, L1Link, LacpLag, MlagLag
│       │   ├── layer2.py       # VLAN, Bridge, VxLAN (l2vni/l3vni), Subinterface
│       │   ├── layer3.py       # VRF, L3Interface, GatewayRedundancy, TunnelInterface
│       │   ├── control_plane.py # BGP / OSPF / IS-IS のインスタンス、BFD、routing_neighbors（ADR-0010）
│       │   ├── refs.py         # Ref（参照先の宣言。ADR-0015）
│       │   └── topology.py     # MLNDLTopology（ルートモデル。index() / resolve()）
│       ├── index.py            # IdIndex（id → エンティティの索引）
│       ├── derive.py           # 参照をたどって求める関係（VLAN の端点 ADR-0013 D7、BGP セッションの両端・AS・通り道 ADR-0010、bridge / トンネル・OSPF / IS-IS の通り道 ADR-0018）
│       ├── parser.py           # yaml.safe_load + 1MB 制限
│       ├── validator.py        # 整合性チェック
│       └── exporter/
│           ├── yaml.py
│           ├── cytoscape.py    # ndl-viz 向け Cytoscape.js JSON
│           └── rfc8345.py
├── tests/
│   └── fixtures/
│       ├── valid_l1_simple.yaml
│       └── invalid_missing_node.yaml
├── pyproject.toml
└── CLAUDE.md                   # このファイル
```

---

## バリデーション項目（validator.py）

**構文を足すとき**（ADR-0015）: 別のエンティティの id を指すフィールドには `Annotated[..., Ref("<コレクションのパス>")]` を付ける。
参照の存在の検査はこれだけで付き、validator を直す必要はない。参照ではない文字列フィールドは `tests/test_refs.py` の
`NOT_REFERENCES` に足す（どちらもしないとテストが落ちる）。ネットワークとしての意味の検査が要るかは ADR で判断し、validator に手で書く。

Severity は ADR-0002 D8 に従う。`validate()` は **error のみ**を返す（後方互換）。
warning / info も含めて受け取るには `validate_all(topology, strict=False)` → `ValidationResult(errors, warnings, notes)`。
`strict=True`（CLI は `python -m mlndl validate --strict`）で warning を error に昇格する。

| カテゴリ | チェック内容 | Severity |
|---------|------------|---------|
| 参照整合性 | スキーマで `Ref` を宣言したフィールドが、参照先に実在する id を指しているか（汎用の検査。ADR-0015）。別の種類の id を指したら何であるかを添える | error |
| 制御プレーン | `instance` の省略は同じ type のエントリが 1 つのときだけ。端の機器がインスタンスの `nodes` にあるか。`update_source`（OSPF / IS-IS は `interface`）の機器が端の機器と一致するか。`update_source` の VRF がインスタンスの VRF と一致するか。両端から導いた通り道が食い違わないか。トランスポートのアドレスファミリーが一致するか。同じ両端のセッションの重複。`route_reflector_client` は iBGP だけ。同一ノード・同一 VRF で AS は 1 つ、同一 VRF に BGP エントリは 1 つ。`bfd: true` の両端がタイマーの `nodes` にあるか。端点の形・両端ともトポロジー外は型で弾く（ADR-0010 D10）。通り道は同じリンク / LAG、同じ bridge に届く（1 ホップ）、対になるトンネル IF のどれか。食い違いのメッセージは両端の通り道と直し方 (a)(b)(c) を示す（ADR-0018 D2・D3・D6） | error |
| 制御プレーンの通り道（OSPF / IS-IS） | BGP と同じ規則で両端の `interface` から導いた通り道が食い違わないか。ndl_version 1.x の間は warning、2.0 で error（ADR-0018 D4） | warning |
| bridge | `ports` は `{interface:}` か `{lag:}`（型）。参照先がそのキーの種類で定義されているか。同じポートを 2 つの bridge に・同じ bridge に 2 回・LAG とそのメンバーを併記（error）。ポートが 1 つ、ポートの対向も同じ bridge のポート（ルーターのポートを書いた疑い）、VLAN のポートにもある、LAG のメンバーだけ（warning）（ADR-0018 D1） | error / warning |
| 制御プレーンの注意 | default 以外の VRF のセッションに `l2vpn_evpn` / `vpnv4` / `vpnv6` | warning |
| 旧構造 | `protocols`、`layer3.routing_adjacencies`、`protocols.bgp[].role`、`neighbors[].remote_as` / `type`、`attaches_to: {link:}` に移動先を示すエラー。読み替えはしない（ADR-0010 D12） | error |
| VNI ユニーク性 | L2VNI と L3VNI がグローバルに重複していないか | error |
| VRF ↔ L3VNI | l3vni が vxlan に定義済みか。`VRF.l3vni` と `L3VxLAN.vrf` が双方向で一致するか | error |
| VTEP | `sources` が L3 IF に存在するか。同じ L3 IF を 2 つの VTEP / 1 つの VTEP に 2 回書いていないか。1 つの VTEP に同じノードの L3 IF を 2 つ書いていないか。共有（`sources` が複数）なら `address` 必須（型）。アドレスが決まらない / VTEP 間で重複していないか。L2VNI の `vteps` が定義済みか（ADR-0014） | error |
| VTEP の注意 | `sources` が 1 つで `address` が L3 IF の ip と食い違う。MLAG ペアの片方だけが VTEP を終端している。旧形式 `vtep_source` / `members` | warning |
| ノード所属 | L3 IF の `node` が、`attaches_to` の参照先（L1 IF / LAG / サブ IF）のノード（群）に含まれるか（ADR-0011 D9） | error |
| VLAN のポート | `{interface:}` か `{lag:}` のどちらか一方（型）。同じ VLAN に LAG とそのメンバーを併記していないか（error）。同じ VLAN に同じ端点を 2 回書いていないか（error）。LAG のメンバーだけを書いていたら `{lag:}` を促す（warning）（ADR-0013） | error / warning |
| 参照キー | `attaches_to` のキーがそのエンティティに書けるものか（型。ADR-0001 D8）。参照先がそのキーの種類で定義されているか。キーの取り違え（`{lag: vlan-100}` 等）には正しいキーを示す | error |
| ID の文法 | すべてのエンティティの `id` が `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` に従い、63 文字以内か（ADR-0002 D1）。違反理由をまとめて示す | error |
| ID の一意性 | L1 IF / LAG / VLAN / サブ IF の ID が互いに重複していないか。L3 IF とトンネルの ID が重複していないか（ADR-0002 D5・ADR-0018 D3） | error |
| サブ IF | `vlan_id` が 1..4094 か。同じ基盤の上でタグが重複していないか。`attaches_to` が `{interface:}` か `{lag:}` か。タグと `layer2.vlans` の照合は**しない**（ADR-0012 D3） | error |
| L3 IF 重複 | 同一 `(node, name)` の L3Interface が重複していないか | error |
| IP アドレス | `ip` は IPv4、`ipv6` は IPv6 の CIDR（型で検証。`ip` に IPv6 を書くと移動先を示すエラー） | error |
| ゲートウェイ冗長 | IPv4 VIP が IF のサブネット内か（IF に `ip` がなければ warning）。同一 IF・同一 mode・同一 AF で `group_id` が重複していないか。IPv6 VIP はリンクローカルか（RFC 5798）。同じ VLAN の anycast gateway 群で `ip` / `ipv6` / `anycast_mac` が一致するか | error |
| トンネル | `source` が同じ node の L3 IF か。`destination_interface` が別 node の L3 IF か。`destination_ip` / `destination_interface` がちょうど一方か。外側のアドレスファミリーが source と destination で一致するか。VRF 参照。対向がトポロジー内なのに逆向きのトンネルがなければ info | error / info |
| 廃止キー | `vlan` / `fhrp` / `gateway_redundancy[].protocol` に移動先を示すエラー（ADR-0011 D10） | error |
| 旧形式 | L3 IF の `interface`（→ `name`）、短縮形 `interface: vlan-N`、`{interface: <LAG / VLAN / サブ IF>}`、VLAN のポートの `node`。ndl_version 1.x の間は読み替えて受け付ける（ADR-0011 D10） | warning |
| VNI の参加ノード | L2VNI に参加するノード（VTEP から導出）に、その VLAN のポートがあるか | warning |
| VLAN の端点 | ポート → L1 リンクの対向 → 対向の L3 IF を id でたどって求めた端点（1 ホップ。`derive.vlan_endpoints`）の IP が、その VLAN の SVI のサブネットに入っているか。SVI がなければ検査しない（ADR-0013 D7） | info |
| MTU 整合性 | VTEP を終端するノードどうしの underlay MTU が 1550 以上か | error |
| LAG 整合性 | `type: mlag` のノードが 2 つか、`peer_link` が同じ `lag` リスト内に存在するか | error |
| Route Target | `ASN:NN` または `IP:NN` フォーマットか | error |
| VLAN ID | 同一ノード上で別の VLAN エントリが同じ `vlan_id` を使っていないか（別ノードでの番号再利用は許容。MLAG に載せた VLAN は両ノードで数える） | error |
| 推奨プレフィックス | `link-` / `lag-` / `vlan-` / `vni-` / `vrf-` / `tunnel-` / `subif-` / `vtep-` / `bridge-` / `bfd-` / `bgp-peer-` / `ospf-adj-` / `isis-adj-`（ADR-0002 D7。`control_plane.routing_neighbors`） | warning |
| SVI の紐づけ忘れ | `name` が VLAN らしき名前（`Vlan100` 等）なのに `attaches_to` が未指定 | warning |
| labels キー | ADR-0002 D1 の ID 正規表現に従っているか（ADR-0009 D3）。値は検査しない | warning |
| ルーター ID | ~~bgp/ospf の router_id が layer3.interfaces に定義済みか~~ | **実装しない** — RFC 6286 は BGP Identifier と IF の IP の一致を要求しない。ADR-0016 の一意性チェックに置き換え予定（ADR-0010 D9 で委譲。router_id は control_plane.bgp[].nodes[] に置く） |

---

## 実装フェーズ（このリポジトリの範囲）

### Phase 1（最初に着手）
- `MLNDLTopology` pydantic v2 スキーマ（**L1 のみ**）
- `ndl_version` フィールド + バージョン検証
- `yaml.safe_load` + 1MB サイズ制限
- `model_validator` でクロスフィールド参照検証（リンクが未定義インターフェースを参照していないか）
- `exporter/yaml.py` と `exporter/cytoscape.py`（L1 部分のみ）
- pytest fixtures YAML によるユニットテスト
- **成果物: L1 MLMLNDL を parse・validate・export できる pip パッケージ**

### Phase 2 以降（全体プランを参照）
L2/L3/protocols スキーマ追加 → validator.py 完全実装 → broadcast_domain/blast_radius クエリ対応

---

## 言語設計決定 (ADR)

ラウンド1/1.5 の基礎概念は **2パス方式** (Pass A ドラフト → Pass B 横断評価 → Pass C ゼロから再設計) で確定。詳細は `docs/decisions/` を参照。

| ADR | タイトル | Pass | 主要決定事項 |
|-----|---------|------|------------|
| [ADR-0001](docs/decisions/0001-attaches-to.md) | `attaches_to` の使い分け | C（D8 をラウンド4 Pass C で追加） | `layer` フィールド廃止。1 キー形式。キー名が参照先の種類を示す（`{interface:}` は L1 IF 専用、`{lag:}` / `{vlan:}` / `{subinterface:}` を追加） |
| [ADR-0002](docs/decisions/0002-id-naming-convention.md) | ID 命名規則 | C | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`、`vlan-100`・`vni-10100`・`bgp-peer-*` 形式 |
| [ADR-0003](docs/decisions/0003-role-vocabulary.md) | `role` 語彙 | **C2** | `role` は注釈側構成子。open-form (自由文字列)。推奨 9 語彙は `docs/role-vocabulary.md`。`hypervisor` は normative token |
| [ADR-0004](docs/decisions/0004-implementation-role-matrix.md) | `implementation × role` | C | コアは `container × hypervisor = error` のみ。他は上位ツールに委譲 |
| [ADR-0005](docs/decisions/0005-mlndl-expressive-scope.md) | mlndl の表現スコープ定義 | C（ADR-0011・ラウンド4 Pass C で部分改訂） | 三側面 (物理構成図/論理構成図/物理-論理連携)。D4 判定フレームワーク。D4 補則「表現の指針」（スコープを決める 3 つの問い + D3-2 の明示表、書き方を決める問い 4「方式名は構文に入れない」）。D6 `node` の持ち方（ノードごとの設定値を持つものだけ必須） |
| [ADR-0006](docs/decisions/0006-endpoints.md) | L1 リンク端点表現 | C | `from`/`to` 廃止 → `endpoints: [a, b]`（無向リスト）。Cytoscape/RFC8345 出力のみ source/target にマップ |
| [ADR-0009](docs/decisions/0009-membership-orthogonality.md) | メンバーシップ構成子の直交性 | C 相当 | `attaches_to`（Realization）/ `parent`（Containment）/ `labels`（Classification）の 3 軸に分離。`scope`・`pod`・`tags` 等 20 語以上を却下 |
| [ADR-0008](docs/decisions/drafts/0008-cloud-networks-scope-location.md) | クラウドネットワークの表現 | C (Draft) | 箱もノード（`role: vpc`）。`location` 軸。所属は `parent` + `labels` |
| [ADR-0010](docs/decisions/0010-control-plane-separation.md) | control plane と data plane の分離 | **C**（2026-11-01 実装） | `protocols` → `control_plane`、`layer3.routing_adjacencies` → `control_plane.routing_neighbors`（1 エントリ = 1 セッション）。BGP エントリは VRF ごとのインスタンス、underlay / overlay は構文に入れず AF と VRF から導く。セッションは `instance` で所属を指し、トポロジー内の端点は `update_source` 必須、トポロジー外の相手は `address` + `local_as`。セッションに `attaches_to` は書かず通り道は `update_source` から導く（ADR-0001 の `{link:}` キーは削除）。RR は端点の `route_reflector_client`。エクスポーターは機器の `bgp_sessions` とセッションの辺 |
| [ADR-0011](docs/decisions/0011-layer3-data-plane.md) | layer3 データプレーン | **C**（D11 を追記） | 表現の指針（スタティックルート等はスコープ外）。L3 IF は `name`（機器上の名前）+ `attaches_to`（`{interface}` / `{lag}` / `{vlan}` / `{subinterface}`）。SVI 短縮形は廃止。`gateway_redundancy`（anycast は全ノード一致を検証）。`ip` / `ipv6`。トンネル。旧形式は 1.x の間 warning（D10）。D11: L3 IF の分類は `attaches_to` のキーで決まり `name` では決めない（`l1_interface` / `lag` / `vlan` / `subinterface` / `unattached`。`unattached` はループバックとみなさない）。ノードの代表アドレスは言語として定義しない。エクスポーター出力の語彙は `docs/exporter-cytoscape.md` |
| [ADR-0012](docs/decisions/0012-subinterfaces.md) | 802.1Q サブインターフェース | **C** | `layer2.subinterfaces`。`node` を持たない。`vlan_id` はリンク上のタグ番号（VLAN への参照ではなく照合もしない）。基盤は `{interface:}` か `{lag:}` |
| [ADR-0013](docs/decisions/0013-vlan-ports-on-lag.md) | VLAN のポート | **C**（D7 を追記） | `trunk_ports` / `access_ports` は `{interface:}` か `{lag:}`。`node` は書かない。MLAG は 1 エントリで両ノード。LAG とメンバーの併記は error、メンバーだけは warning。D7: VLAN の端点（ポートの対向の IF と IP）を参照をたどって導く。1 ホップ、`name` では引かない。tagged trunk のタグ一致は推定 |
| [ADR-0014](docs/decisions/drafts/0014-vteps.md) | VXLAN のトンネル端点 (VTEP) | A (Draft) | `layer2.vteps`（`sources` = 終端するノードの L3 IF、`address` / `address_v6`）。VNI は `vteps` で参照。方式中立（anycast / vPC / BGW を構文に出さない）。アドレス省略は `sources` が 1 つのときだけ。旧 `vtep_source` / `members` は 1.x の間 warning（**実装済み**） |
| [ADR-0015](docs/decisions/drafts/0015-declarative-references.md) | 参照先をスキーマに宣言する | A (Draft) | 参照先が 1 つに決まる参照は `Annotated[str, Ref("layer2.vlans")]` と型に書き、汎用の検査が全参照を検査する。キーで選ぶ参照（attaches_to 等）と意味の検査は別。`topology.resolve(id)` で id から実体を引く（**実装済み**） |
| [ADR-0017](docs/decisions/0017-sites-and-wan.md) | サイト・事業者網・回線情報の書き分け | **C** | スキーマ・validator は変えない。サイトは `labels.site`（値は `tokyo`）。2 点間の回線は `L1Link`、事業者網は `role: provider-network` の箱 + 箱への `L1Link`（契約の形で分ける）。回線 ID 等は `description`（書式なし、パースしない）。`link_role` に WAN の推奨値は足さない。事業者の機器はトポロジー外の相手。広域イーサ越しの自社機器どうしのセッションは次の ADR（D5-2） |
| [ADR-0018](docs/decisions/0018-sessions-across-bridges-and-tunnels.md) | 事業者網やトンネルを越えるセッションの通り道 | **C**（2026-11-03 実装） | `layer2.bridges` を最小の形（`id` / `name` / `ports` / `description`）で先取り。`ports` は転送する側（箱）のポートだけ、`{interface:}` / `{lag:}`、方式名は書かない、書かなければ透過しない。両端が同じ bridge に届けば通り道は `{bridge:}`（1 ホップ）。`update_source` / OSPF の `interface` はトンネル IF も指せ（`Ref` の複数コレクション）、対になれば `{tunnel: [from, to]}`。OSPF / IS-IS も通り道を導き、食い違いは 1.x warning・2.0 error。マルチアクセスは次の ADR |
| (§6 設計決定) | `lag` 統合設計 | — | `port_channels` + `mlag` → `lag` (type: lacp \| mlag)。Discriminated Union で `node` (単数) / `nodes` (複数) を区別 |

---

## 参考

- MLNDL 原案 (NAIST, 2011) の論文: 手元の場所は CLAUDE.local.md
- RFC 8345（supporting 関係の元概念）
- RFC 8944（L2 拡張）、RFC 8346（L3 拡張）
