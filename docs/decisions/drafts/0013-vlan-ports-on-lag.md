# ADR-0013: VLAN の trunk_ports / access_ports から LAG を指す

- **Status**: Superseded by [0013](../0013-vlan-ports-on-lag.md) (ラウンド4 Pass C, 2026-10-15)。以下は Pass A の記録として残す。 元の Status: Draft — 実装済み (2026-10-11)。Pass B 実施済み ([round4-evaluation](../evaluations/round4-evaluation.md))、Pass C は未実施
- **Date**: 2026-10-11
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **Pass**: A (設計ラウンドで 5 エージェントの評価を取り、割れた 1 点をユーザーが判断した上で策定)
- **Amends**: drafts/0012 D5 (`{interface:}` が指せる ID 空間の表に `PortRef` の行を足す)
- **関連**: ADR-0002 (D5 グローバル一意), drafts/0011 (D1 表現原理・D9 ノード所属), drafts/0012 (D2 導出・D5 ID 空間)

## Context

`layer2.vlans[].trunk_ports` / `access_ports` の要素 `PortRef {node, interface, native}` は、`interface` で
L1 IF しか指せなかった。そのため port-channel / bond / MLAG をトランクにする構成は、メンバーの物理ポートを
並べて近似するしかなかった (例: `valid_full_dc.yaml` の vlan-100 は MLAG `lag-mlag-server1` のメンバー
`leaf1-swp1` / `leaf2-swp1` を並べていた)。

実機では、VLAN の設定はどのベンダーでも LAG 側にある (network-tech-reviewer、確信度 高):

| 実装 | VLAN 設定の場所 |
|---|---|
| Cisco NX-OS (vPC) / IOS-XE | `interface port-channel N` の `switchport`。メンバーに食い違う設定を書くと suspend |
| Arista EOS (MLAG) | `interface Port-Channel N`。ピア間で不一致なら MLAG consistency check で止まる |
| Cumulus Linux / SONiC | bond の `bridge-vids` / `bridge-access` |
| Juniper | `interface aeN unit 0 family ethernet-switching vlan members` |
| Linux bond | `bond0` (bridge port) または `bond0.N`。スレーブには書けない |

メンバーを並べる書き方は実機と対応しないうえ、LAG のメンバー構成を変えたときに VLAN 側の列挙が古いまま残る。
ADR-0012 は「影響」節でこの問題を未解決として残していた。

## Decision

### D1. `PortRef.interface` は L1 IF または LAG を指す

```yaml
layer2:
  vlans:
    - id: vlan-100
      vlan_id: 100
      trunk_ports:
        - {interface: lag-mlag-server1}      # MLAG: 1 エントリで leaf1 / leaf2 の両方
        - {interface: lag-leaf3-po1}         # LACP
        - {interface: lag-peer-link}         # peer-link も書ける
        - {node: leaf3, interface: leaf3-swp5}   # 従来の書き方もそのまま有効
      access_ports:
        - {interface: lag-leaf4-server3}     # サーバー向け bond の access も書ける
```

LAG を指すために `lag:` のような新しいキーは足さない。サブ IF (`attaches_to: {interface:}`) と L3 IF はすでに
`interface` で LAG を指しており (ADR-0012 D4)、VLAN だけ別のキーにすると「論理 IF を指す」書き方が 2 系統になる。
`trunk_ports` / `access_ports` の "port" は、ここでは「L2 の設定が載る端点 (L1 IF または LAG)」の意味に広げる。

ADR-0012 D5 の表に次の行を足す:

| 参照元 | X が指せるもの | 根拠 |
|---|---|---|
| `layer2.vlans[].trunk_ports[].interface` / `access_ports[].interface` | L1 IF ∪ LAG | 本 ADR D1 |

VLAN やサブ IF は指せない (未定義の参照として error)。

### D2. `node` は省略できる (L1 IF でも LAG でも)

ID はグローバルに一意なので (ADR-0002 D5)、`node` は `interface` から必ず導出できる。ADR-0012 D2 (親から
導出できるものは持たない) にならい、`PortRef.node` を必須から任意に変えた。

- 書いた場合は、`interface` から導いたノードと照合する (違えば error)
- **MLAG を指すときは `node` を書けない (error)**。1 エントリが両ノードに効くので、`node: leaf1` と書くと
  片方だけに見えてしまう。MLAG / vPC は両ピアの VLAN 設定が一致していないと該当 VLAN が止まる
  (network-tech-reviewer) ため、片方のノードだけに VLAN を載せる書き方を用意する必要もない

設計ラウンドでは意見が割れた。「`node` 必須・MLAG は 2 エントリ」(linguist・dsl-designer)、
「LAG のときだけ省略可」(spec-architect・example-author)、「1 エントリで両ノード」(network-tech-reviewer)。
ユーザーが「常に省略可」を選んだ。「LAG のときだけ」という例外を作らず、2 エントリ案の「LAG の `nodes` と
同じ情報を VLAN 側にも書く」重複も避けられるためである。

### D3. LAG のメンバーを VLAN に書かない

| 書き方 | severity |
|---|---|
| 同じ VLAN に LAG とそのメンバーの両方を書く | **error** (二重表現。どちらが正か決まらない) |
| LAG があるのに、メンバーだけを書く | **warning** (LAG を指すよう促す。既存の YAML を壊さないため error にはしない) |

### D4. 同じ VLAN に同じ端点を 2 回書かない

`trunk_ports` と `access_ports` の両方、または同じリストに同じ `interface` が 2 回出たら error。
D2 で `node` を省略できるようになり、2 エントリで書いた MLAG がこの形になるので、合わせて検出する。

### D5. VLAN ID 重複検査は LAG のノードに展開して行う

「同一ノード上で別の VLAN エントリが同じ `vlan_id` を使っていないか」の検査は、MLAG を指すエントリを
両ノードに展開してから行う。エクスポーター (cytoscape) も、VLAN の所属を両ノードに出す。

### D6. 書けるが、検査しないもの

- **peer-link**: 実機では全 VLAN を暗黙に通すことが多い (Cisco vPC peer-link、Cumulus `peerlink.4094`)。
  `trunk_ports` に書いてもよく、書かなくてもよい。書かなかったことを warning にはしない
- **サーバー側の bond**: `access_ports` に書くかどうかは書き手に任せる。VM の vNIC を `access_ports` に書く近似
  (drafts/0007、`valid_vsphere_dvswitch.yaml`) との整合のため、禁止も推奨もしない
- **native VLAN の一致**: MLAG は 1 エントリなので両ノードで食い違いようがない。LACP の両端 (スイッチ側と
  サーバー側) の一致は検査しない

## Consequences

### 良くなること

- port-channel / bond / MLAG のトランクが実機どおりに書ける。MLAG は 1 行で済む
- LAG のメンバー構成を変えても VLAN 側を直す必要がない
- 加算的な変更である。`node` 付き・L1 IF 指定の既存 YAML はそのまま通る (メンバーを並べたものは warning)

### 移行

`tests/fixtures/` の 2 本を LAG を指す書き方に移した。

| fixture | 変更 |
|---|---|
| `valid_full_dc.yaml` | vlan-100 の `trunk_ports` 2 行 → `{interface: lag-mlag-server1}` 1 行 |
| `valid_multisite_wan.yaml` | vlan-100 の `trunk_ports` 4 行 → MLAG 2 つを指す 2 行 |

### 書けないまま残るもの

- ESI-LAG (EVPN multihoming)。今の `type: mlag` は `peer_link` 必須で表せない。将来 `type: esi_lag` を足しても、
  VLAN からは同じ `interface: <LAG id>` で指せる (network-tech-reviewer)
- メンバーを VLAN X に、LAG を VLAN Y に書く食い違いは、D3 の warning (メンバー側) としてしか出ない

### 影響を受けるコンポーネント

- スキーマ: `layer2.py` の `PortRef` (`node` を任意に。`interface` の説明)
- バリデーター: `validator.py` の `_validate_l2` と `_port_nodes` (D1〜D5)
- エクスポーター: `exporter/cytoscape.py` (VLAN 所属を LAG のノードに展開)
- テスト: `tests/test_portref_lag.py` (28 件)

## Alternatives Considered

- **新キー `lag:` (`interface` と排他)**: 却下 — `{interface:}` で LAG を指す既存の書き方 (ADR-0012 D4) と 2 系統になる。
  排他を人が覚える必要がある
- **`node` 必須・MLAG は 2 エントリ**: 却下 — LAG の `nodes` と同じ情報を VLAN 側に重ねて書く。片方だけ書いた場合を
  error にするなら、もう片方は書き忘れの指摘のためだけに存在することになる
- **LAG のときだけ `node` を省略可**: 却下 — L1 IF からもノードは導出できるのに、例外規則が 1 つ増える
- **メンバーだけを書く形を error**: 却下 — 既存の YAML がすべて無効になる。warning にとどめ、`--strict` で error にできる
- **`trunk_ports` / `access_ports` を `tagged_members` / `untagged_members` に改名**: 見送り — 改名のコストに見合わない。
  将来 `layer2.bridges` (drafts/0007) などで参照先がさらに広がったときに再検討する (linguist)

## References

- 設計比較 YAML: `evaluations/adr0013/` (3 案 × 3 シナリオ + ありがちなミス 3 件)
- drafts/0012 D2・D4・D5、drafts/0011 D1・D9、ADR-0002 D5
- IEEE 802.1AX (Link Aggregation)
