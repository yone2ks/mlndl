# mlndl プロジェクト

**詳細設計**: 初期の設計プラン (リポジトリ外。現在は ADR が正) を参照（全体アーキテクチャ・NDL YAML フォーマット・実装フェーズ）

## エージェント運用ルール

**設計判断・仕様議論・ADR 作成・NDL YAML の設計に関する質問には、必ず以下の 5 エージェントを並列起動してから統合回答を作ること。**

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
| インターフェース | `attaches_to: {interface: swp51}` | この論理 IF はこの物理ポートで実現 | supporting-termination-point |
| リンク（BGP等） | `attaches_to: {link: link-xxx}` | このセッションはこの物理リンク上を流れる | supporting-link |
| リンク（LAG） | `lag.members: [...]` | members が意味的に自然なのでそのまま | supporting-link |

pydantic での型定義: `attaches_to: str | AttachesTo`（文字列ならノードID糖衣構文、オブジェクトは `{node:}` / `{interface:}` / `{link:}` のいずれか 1 キー）

旧形式（使わない）:
- `{layer: layer1, interface: swp51}` — `layer` フィールドは廃止（グローバル一意 ID なので不要）
- `supporting_interface`、`routing_adjacencies[].supporting`

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

- `yaml.safe_load()` 必須（`yaml.load()` は使わない）
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

---

## NDL YAML フォーマット概要

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
      link_role: underlay        # underlay/access/peer-link/management/uplink

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
      trunk_ports:
        - {node: leaf1, interface: swp3}   # node/interface ペア形式（曖昧さなし）
      access_ports:
        - {node: server1, interface: eth0}

  vxlan:
    - id: vni-10100             # ADR-0002: vni-<N> 形式
      type: l2vni                # l2vni / l3vni を明示
      vni: 10100
      vlan: vlan-100
      vtep_source: {layer: layer3, interface_id: leaf1-lo}
      members: [leaf1, leaf2]
    - id: vni-10900
      type: l3vni                # Symmetric IRB 用 L3VNI（必須）
      vni: 10900
      vrf: vrf-tenant-a
      irb_mode: symmetric

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
      node: leaf1
      interface: swp51
      ip: 10.1.0.1/31
      vrf: vrf-default
      attaches_to:               # オブジェクト形式 = {interface: id} / {link: id} / {node: id}
        interface: leaf1-swp51  # layer フィールドは不要（グローバル一意 ID）

    - id: leaf1-vlan-100
      node: leaf1
      interface: vlan-100
      ip: 192.168.100.1/24      # anycast 構成では全 leaf で同一 IP
      vrf: vrf-tenant-a
      # VRRP/HSRP が必要な場合のみ fhrp を追加:
      # fhrp:
      #   - protocol: vrrp
      #     group_id: 100
      #     vip: 192.168.100.254
      #     priority: 110

  routing_adjacencies:
    - id: bgp-peer-spine1-leaf1  # ADR-0002: bgp-peer-* 形式（bgp-adj-* は廃止）
      type: bgp
      from: {node: spine1, update_source: spine1-lo}
      to: {node: leaf1, update_source: leaf1-lo}
      attaches_to:               # このBGPセッションが使う物理リンク
        link: link-spine1-leaf1 # layer フィールドは不要

protocols:
  bfd:
    - id: bfd-global
      min_tx: 300
      min_rx: 300
      multiplier: 3
      nodes: [spine1, leaf1, leaf2]

  bgp:
    - id: bgp-underlay
      role: underlay             # underlay/overlay を明示
      nodes:
        - node: spine1
          local_as: 65000
          neighbors:
            - node: leaf1
              remote_as: 65001
              type: ebgp
              bfd: true
    - id: bgp-evpn
      role: overlay
      nodes:
        - node: spine1
          role: route_reflector
          neighbors:
            - node: leaf1
              type: ibgp
              role: route_reflector_client
              address_families: [l2vpn_evpn]
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
│       │   ├── layer2.py       # VLAN, VxLAN (l2vni/l3vni)
│       │   ├── layer3.py       # VRF, L3Interface, FhrpInstance, RoutingAdjacency
│       │   ├── protocols.py    # BFD, OSPF, BGP
│       │   └── topology.py     # MLNDLTopology（ルートモデル）
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

Severity は ADR-0002 D8 に従う。`validate()` は **error のみ**を返す（後方互換）。
warning / info も含めて受け取るには `validate_all(topology, strict=False)` → `ValidationResult(errors, warnings, notes)`。
`strict=True`（CLI は `python -m mlndl validate --strict`）で warning を error に昇格する。

| カテゴリ | チェック内容 | Severity |
|---------|------------|---------|
| 参照整合性 | 全レイヤーで未定義 node/interface への参照がないか | error |
| AS 番号 | eBGP ペアで同一 AS / iBGP ペアで異なる AS の矛盾 | error |
| VNI ユニーク性 | L2VNI と L3VNI がグローバルに重複していないか | error |
| VRF ↔ L3VNI | l3vni フィールドが vxlan に定義済みか | error |
| VTEP source | vtep_source.interface_id が layer3.interfaces に存在するか | error |
| MTU 整合性 | VxLAN 使用時に underlay MTU が 1550 以上か | error |
| LAG 整合性 | `type: mlag` のノードが 2 つか、`peer_link` が同じ `lag` リスト内に存在するか | error |
| Route Target | `ASN:NN` または `IP:NN` フォーマットか | error |
| VLAN ID | 同一ノード上で別の VLAN エントリが同じ `vlan_id` を使っていないか（別ノードでの番号再利用は許容） | error |
| 推奨プレフィックス | `link-` / `lag-` / `vlan-` / `vni-` / `vrf-` / `bfd-` / `bgp-peer-` / `ospf-adj-` / `isis-adj-`（ADR-0002 D7） | warning |
| labels キー | ADR-0002 D1 の ID 正規表現に従っているか（ADR-0009 D3）。値は検査しない | warning |
| ルーター ID | ~~bgp/ospf の router_id が layer3.interfaces に定義済みか~~ | **実装しない** — RFC 6286 は BGP Identifier と IF の IP の一致を要求しない。ADR-0010 D5・D6 の一意性チェックに置き換え予定（保留中） |

---

## 実装フェーズ（このリポジトリの範囲）

### Phase 1（最初に着手）
- `MLNDLTopology` pydantic v2 スキーマ（**L1 のみ**）
- `ndl_version` フィールド + バージョン検証
- `yaml.safe_load` + 1MB サイズ制限
- `model_validator` でクロスフィールド参照検証（リンクが未定義インターフェースを参照していないか）
- `exporter/yaml.py` と `exporter/cytoscape.py`（L1 部分のみ）
- pytest fixtures YAML によるユニットテスト
- **成果物: L1 MLNDL YAML を parse・validate・export できる pip パッケージ**

### Phase 2 以降（全体プランを参照）
L2/L3/protocols スキーマ追加 → validator.py 完全実装 → broadcast_domain/blast_radius クエリ対応

---

## 言語設計決定 (ADR)

ラウンド1/1.5 の基礎概念は **2パス方式** (Pass A ドラフト → Pass B 横断評価 → Pass C ゼロから再設計) で確定。詳細は `docs/decisions/` を参照。

| ADR | タイトル | Pass | 主要決定事項 |
|-----|---------|------|------------|
| [ADR-0001](docs/decisions/0001-attaches-to.md) | `attaches_to` の使い分け | C | `layer` フィールド廃止。`{node:}` / `{interface:}` / `{link:}` の 1 キー形式 |
| [ADR-0002](docs/decisions/0002-id-naming-convention.md) | ID 命名規則 | C | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`、`vlan-100`・`vni-10100`・`bgp-peer-*` 形式 |
| [ADR-0003](docs/decisions/0003-role-vocabulary.md) | `role` 語彙 | **C2** | `role` は注釈側構成子。open-form (自由文字列)。推奨 9 語彙は `docs/role-vocabulary.md`。`hypervisor` は normative token |
| [ADR-0004](docs/decisions/0004-implementation-role-matrix.md) | `implementation × role` | C | コアは `container × hypervisor = error` のみ。他は上位ツールに委譲 |
| [ADR-0005](docs/decisions/0005-mlndl-expressive-scope.md) | mlndl の表現スコープ定義 | C | 三側面 (物理構成図/論理構成図/物理-論理連携)。D4 判定フレームワーク |
| [ADR-0006](docs/decisions/0006-endpoints.md) | L1 リンク端点表現 | C | `from`/`to` 廃止 → `endpoints: [a, b]`（無向リスト）。Cytoscape/RFC8345 出力のみ source/target にマップ |
| [ADR-0009](docs/decisions/0009-membership-orthogonality.md) | メンバーシップ構成子の直交性 | C 相当 | `attaches_to`（Realization）/ `parent`（Containment）/ `labels`（Classification）の 3 軸に分離。`scope`・`pod`・`tags` 等 20 語以上を却下 |
| [ADR-0008](docs/decisions/drafts/0008-cloud-networks-scope-location.md) | クラウドネットワークの表現 | C (Draft) | 箱もノード（`role: vpc`）。`location` 軸。所属は `parent` + `labels` |
| [ADR-0010](docs/decisions/drafts/0010-control-plane-separation.md) | control plane と data plane の分離 | A r2 (Draft・**保留**) | `protocols` → `control_plane`、`layer3.routing_adjacencies` → `control_plane.routing_neighbors`（決定済み・**未実装**）。BGP エントリの単位は未決 |
| [ADR-0011](docs/decisions/drafts/0011-layer3-data-plane.md) | layer3 データプレーンの確定 | A r2 (Draft) | 原理「関係の成立に必要な情報は書き、個別経路は書かない」。スタティックルートはスコープ外。SVI は `attaches_to` に一本化。`fhrp` → `gateway_redundancy`。`ip` (IPv4) / `ipv6`。トンネル追加（**未実装**） |
| (§6 設計決定) | `lag` 統合設計 | — | `port_channels` + `mlag` → `lag` (type: lacp \| mlag)。Discriminated Union で `node` (単数) / `nodes` (複数) を区別 |

---

## 参考

- MLNDL 原案 (NAIST, 2011) の論文: 手元の場所は CLAUDE.local.md
- 全体設計プラン: 初期の設計プラン (リポジトリ外。現在は ADR が正)
- RFC 8345（supporting 関係の元概念）
- RFC 8944（L2 拡張）、RFC 8346（L3 拡張）
