# ADR-0007（ドラフト）: vNIC と仮想スイッチ（vSwitch/dvSwitch）の表現

- **Status**: Draft（議論メモ — 確定前）
- **Date**: 2026-06-17
- **Pass**: C（5エージェント並列レビュー複数ラウンドの統合メモ）

> このファイルは確定 ADR ではなく、議論の散逸を防ぐための**整理メモ**である。
> 確定事項・未確定論点・却下案・将来への申し送りを記録する。実装（pydantic/validator/exporter）は未着手。
>
> **ADR-0018 (2026-11-03) で `layer2.bridges` の最小の形 (`id` / `name` / `ports` / `description`) を先に確定した。** このメモの `members: [{node, interface}]` は
> `ports: [{interface:} | {lag:}]` (node は書かない) に読み替える。vSwitch のための `type` / `nodes` / `uplinks` と VLAN との関係は、任意のフィールドとして加算する。

---

## 背景・問い

仮想化環境（VMware vSphere / KVM / Hyper-V）の **VM の vNIC** と **仮想スイッチ（vSwitch / dvSwitch / Linux bridge / OVS）** を MLNDL でどう表現するか。

関連する確定事項:
- VM ノード = `layer1.nodes`（`implementation: vm`、`attaches_to: <hypervisor>`）
- ハイパーバイザ = `layer1.nodes`（`role: hypervisor`、`implementation: physical`）
- vSwitch/dvSwitch は **L1 canonical role ではない**（[ADR-0003](../0003-role-vocabulary.md) D1/D6、CLAUDE.md §9）→ L2 で扱う

---

## 確定事項

### A. interface まわり（vNIC）

| 項目 | 決定 | 根拠 |
|------|------|------|
| `interface.type` の導入 | **しない**（不採用） | 物理 NIC と vNIC の区別は `node.implementation` から導出できるため冗長。値域を増やすと L1=物理（ADR-0005 D1）を緩める |
| 物理/vNIC の判別 | `interface.node` → 親ノードの `implementation` を参照 | `implementation: vm` のノードの IF＝vNIC、`physical`＝物理 NIC |
| ndl-viz の描画 | interface → 親ノード → `implementation` を辿る。**未指定は physical にフォールバック** | スキーマ変更ゼロ。`implementation: vm` のノードの IF だけ vNIC スタイルにできる |
| `link.type` の追加 | **しない** | L1 = 物理ケーブルの意味論（ADR-0005 D1）を壊すため。仮想接続は L2 bridge で表現 |

> ✅ 値域問題は「L1.interfaces を物理ケーブル端点に限定する」ことで消滅した（後述）。

### B. 仮想スイッチ（layer2.bridges）

| 項目 | 決定 | 根拠 |
|------|------|------|
| 置き場所 | `layer2.bridges`（新設） | L1 nodes には置かない。ADR-0003 §9 維持 |
| マルチホスト性 | `nodes: [...]`（MLAG パターン） | dvSwitch は「データプレーンは各ホストの host-proxy switch に分散、管理面のみ単一」。各分散実体を1エンティティに束ねるのは MLAG（各スイッチの bond を1論理 LAG に束ねる）と同型 |
| 型の区別 | **統一型**（Discriminated Union 不要） | lag と違いフィールド名が `node`/`nodes` で変わらず、両形態とも「ホスト集合」で意味論が同一。`nodes` 1要素＝single vSwitch、複数＝distributed |
| `type` 値域 | `vswitch` / `dvswitch` / `linux-bridge` / `ovs` | normative discriminator（lag.type/vxlan.type と同じ扱い、Literal） |
| アップリンク | `uplinks: [{node, interface}]` | 物理 NIC（vmnic）を参照。per-host マッピングを表現 |
| vNIC 所属 | `bridges.members: [{node, interface}]`（主） | vNIC 側に逆参照は書かない（DRY） |
| VLAN 連携 | `vlans[].bridge: <bridge-id>` | VLAN が bridge を参照。`vxlan.vlan` 参照と同型 |
| `peer_link` | **不要** | MLAG と違い dvSwitch のホスト間は直結せず ToR 経由のため |

### C. フィールド名の決定理由（linguist）

- マルチホスト性は **`nodes`**（`hosts`/`spans`/`distributed_over` ではない）。
  `lag.nodes` / `bgp[].nodes` / `bfd.nodes` で「この論理エンティティが乗る複数ノード」の意味が既に確立しており、同語で一貫性最大。

---

## スキーマ案（確定部分のみ）

```yaml
layer1:
  nodes:
    - {id: esxi-01, role: hypervisor, implementation: physical}
    - {id: esxi-02, role: hypervisor, implementation: physical}
    - {id: web-vm1, role: server, implementation: vm, attaches_to: esxi-01}
    - {id: web-vm2, role: server, implementation: vm, attaches_to: esxi-02}

  interfaces:
    - {id: esxi01-vmnic0, node: esxi-01, name: vmnic0}          # 物理NIC（type 既定）
    - {id: web-vm1-eth0,  node: web-vm1, name: eth0, type: vnic}  # 仮想NIC

  links:
    # 物理ケーブルのみ L1 に書く（vmnic ↔ ToR）
    - {id: link-esxi01-tor, endpoints: [esxi01-vmnic0, tor1-swp1], link_role: uplink}

layer2:
  bridges:
    - id: dvs-prod
      type: dvswitch
      nodes: [esxi-01, esxi-02]        # MLAG パターン: 分散実体を1エンティティに束ねる
      uplinks:
        - {node: esxi-01, interface: esxi01-vmnic0}
        - {node: esxi-02, interface: esxi02-vmnic0}
      members:
        - {node: web-vm1, interface: web-vm1-eth0}
        - {node: web-vm2, interface: web-vm2-eth0}

    - id: vsw0
      type: linux-bridge
      nodes: [kvm-host1]               # single host も1要素リストで統一

  vlans:
    - id: vlan-100
      vlan_id: 100
      bridge: dvs-prod                 # VLAN が bridge を参照
      access_ports: [...]
      trunk_ports: [...]
```

---

## 未確定論点（要判断）

### 1. `interface.type` の値域 → ✅ 解決（type 自体を導入しない）

当初 `physical`/`vnic` の2値、または `physical`/`virtual`/`loopback`/`tunnel` 等が検討されたが、
4エージェント（network-tech / linguist / dsl-designer / example-author）の議論で**論点がズレていた**ことが判明した。

**核心（example-author の実証）**: 「値域を媒体軸にするか機能軸にするか」を議論する前に、
「**L1.interfaces に何を書くか（スコープ）**」を決めるべき。スコープを絞れば値域問題は消える。

全エージェントが同じ根本原因を指摘（ADR-0005 D1: L1=物理）:
- **loopback** → L3 構成子（`layer3.interfaces` の `interface: lo`）
- **tunnel / VTEP** → overlay（`layer2.vxlan.vtep_source`）
- **vmkernel (vmk0)** → L3 IP を持つ → L3
- **SVI / subinterface** → L2/L3

→ これらは **そもそも L1.interfaces に来ない**。L1.interfaces ＝「物理ケーブルが刺さる端点」に限定すれば、
中身は physical NIC と vNIC の2種のみ。そしてこの2種の区別は `node.implementation` から導出できる（下表）。

**決定**:
- `interface.type` フィールドは**導入しない**
- 物理/vNIC の区別は `implementation` から導出（`vm`→vNIC、`physical`→物理）
- ndl-viz は interface→親ノード→`implementation` を辿り、**未指定は physical にフォールバック**
- loopback/tunnel/vmk/SVI は L1.interfaces に書かず L2/L3 側で扱う
- スキーマ変更ゼロ

> 補足: 各エージェントの個別推奨は分岐した（linguist=機能軸列挙、network-tech=physical/virtual/loopback の3値、
> dsl-designer=機能軸 ethernet のみ or type 不要）。だが「値域を増やす方向は L1=物理を緩めるので避ける」点は
> 4体中3体が一致。example-author のスコープ論がそれらを統合した。

### 2. `members` と `vlans.access_ports` の二重表現

vNIC が `bridges.members` と `vlans.access_ports` の両方に現れる。
推奨整理（未合意）: **`members` = 物理的所属（どの bridge に刺さるか）、`access_ports` = VLAN タグ付けの宣言**として直交させる。

### 3. タギングモード（VST / EST / VGT）

タグ付与主体（ハイパーバイザ / 物理スイッチ / VM 内）を区別する手段が未定義。
network-tech-reviewer は `tagging: access | trunk | external`（VMware 用語を抽象化）を提案。

### 4. アップリンクのチーミング

dvSwitch の uplink teaming（LBT / IP hash / LACP / explicit-failover）の置き場所が未定義。
`bridges.teaming` を足すか、LACP 時は既存 `lag` を参照するか。

### 5. portgroup の表示名

vSphere の PortGroup 名（"PG-Web" 等）を残したい場合の `name` フィールドが `vlans` に必要かも。

---

## 却下案（記録）

| 案 | 却下理由 |
|----|----------|
| vSwitch を `layer1.nodes` の論理ノードにする | ADR-0003 §9 / ADR-0004（implementation 値がない）/ ADR-0005 D1 違反。L1=物理を侵犯 |
| `attaches_to: [esxi-01, esxi-02]`（複数値化） | ADR-0001 の単一値・1:1 supporting 前提を破壊。dvSwitch が「host の上」かつ「vNIC の下」となり方向が反転・意味論崩壊 |
| `layer2.port_groups` 専用エンティティ新設 | VMware 色が強い。VLAN メンバーシップで吸収可能。過剰設計 |
| attaches_to 連鎖で vmnic を直接参照（vSwitch を飛ばす） | 同一 vmnic を複数 vNIC が参照する N:1 が ADR-0001 想定外。タグ付与主体も消える。「嘘」になる |
| 各ホストに別々の vSwitch 実体を書く | 「node が異なる dvSwitch が別物に見える」問題。`nodes: [...]` で束ねることで解決 |

---

## MLAG との対比（設計の核）

| 観点 | MLAG | dvSwitch |
|------|------|----------|
| 分散実体 | 各スイッチの物理 bond | 各 ESXi の host-proxy switch |
| 論理的単一性 | 1つの論理 LAG | 1つの論理 dvSwitch |
| 束ね方 | `lag.nodes: [leaf1, leaf2]` | `bridges.nodes: [esxi-01, esxi-02]` |
| ホスト間接続 | peer-link で直結 | **直結しない**（ToR 経由・VST） |
| → 帰結 | `peer_link` 必須 | `peer_link` 不要 |

---

## 試し書き YAML

`tests/fixtures/` にある 3 本は、本ドラフトの案を比べるための記録である (pytest からは読まれない)。

| ファイル | 案 | 現行スキーマでの validate (2026-10-06) |
|---|---|---|
| `experimental_vswitch_A_chain.yaml` | vSwitch 概念を持たず、vNIC を vmnic に `attaches_to` で連鎖させる | 通る |
| `experimental_vswitch_B_vlanonly.yaml` | vSwitch 概念を持たず、VLAN の `access_ports` / `trunk_ports` だけで表す | 通る |
| `experimental_vswitch_C_bridge.yaml` | `layer2.bridges` を導入する (本ドラフトの方向) | 通らない (`layer2.bridges` が未実装。意図どおり) |

> **2026-10-06 の修正**: A と B はこれまで validate を通らなかったが、原因は案の良し悪しではなく、
> `trunk_ports` / `access_ports` が IF の ID ではなく機器上の名前 (`Ethernet1` / `eth0` / `vmnic0`) を
> 参照していたことだった。ID 参照に直したところ、A と B は現行スキーマでそのまま書けることが分かった。
> あわせて ID `tor-sw1-Eth1` を ADR-0002 D1 に従い `tor-sw1-eth1` に直した。同じ誤りは
> `valid_vsphere_dvswitch.yaml` にもあり、同時に直している。

## 関連 ADR

- [ADR-0001](../0001-attaches-to.md): attaches_to（単一値・supporting 関係）
- [ADR-0003](../0003-role-vocabulary.md): role 語彙・§9 vSwitch は L1 外
- [ADR-0004](../0004-implementation-role-matrix.md): implementation 値域
- [ADR-0005](../0005-mlndl-expressive-scope.md): 表現スコープ（L1=物理）
- §6 lag 統合設計（MLAG の nodes パターン）

## 次のアクション

1. 未確定論点 1〜5 を順に決定（特に 1: interface.type 値域）
2. 確定後に本ドラフトを ADR-0007 として昇格
3. `src/mlndl/schema/layer2.py` に `Bridge` モデル追加・`validator.py` 拡張・exporter 対応
