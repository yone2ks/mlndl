# ADR-0013: VLAN のポート (trunk_ports / access_ports)

- **Status**: Accepted
- **Date**: 2026-10-15
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー
- **Pass**: C (ラウンド4。[評価メモ](evaluations/round4-evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0013](drafts/0013-vlan-ports-on-lag.md)
- **関連**: ADR-0001 (D8 参照キー)、ADR-0002 (D5)、ADR-0005 (D6 `node`)、[ADR-0011](0011-layer3-data-plane.md)、[ADR-0012](0012-subinterfaces.md)

## Context

VLAN が載るポートは `layer2.vlans[].trunk_ports` / `access_ports` に書く。Pass A (drafts/0013) で LAG を指せるようにした。
実機では、VLAN の設定はどのベンダーでも LAG (port-channel / bond / ae) の側にあり、メンバーはそれを継承する。

ラウンド4 Pass C で、参照先の種類をキーで示すこと (ADR-0001 D8) と、`node` を書かないこと (ADR-0005 D6) を決めたので、
本 ADR もそれに合わせて確定する。

## Decision

### D1. ポートは `{interface:}` か `{lag:}` で指す

```yaml
layer2:
  vlans:
    - id: vlan-100
      vlan_id: 100
      trunk_ports:
        - {lag: lag-mlag-server1}      # MLAG: 1 エントリで両ノード
        - {lag: lag-peer-link}         # peer-link も書ける
        - {interface: leaf3-swp5}      # L1 IF
      access_ports:
        - {lag: lag-leaf4-server3}     # サーバー向け bond の access
```

どちらか一方だけを書く。VLAN やサブ IF は指せない。"port" は、ここでは「L2 の設定が載る端点 (L1 IF または LAG)」の意味である。
改名 (`tagged_members` / `untagged_members` 等) は、`layer2.bridges` (drafts/0007) で参照先がさらに広がるときに再検討する。

### D2. `node` を書かない

ノードは `interface` / `lag` から決まる (ADR-0005 D6)。MLAG を指すエントリは両ノードに効く。

Pass A では「任意 (書けば照合)」だったが、サブ IF (ADR-0012 D2) と揃えて書かない形に改めた (ユーザー判断)。
ndl_version 1.x の間は旧形式として受け付け、warning を出したうえで照合する (食い違えば error。MLAG に `node` を書くのも error)。

### D3. LAG のメンバーを VLAN に書かない

| 書き方 | Severity |
|---|---|
| 同じ VLAN に LAG とそのメンバーの両方を書く | error (二重表現) |
| LAG があるのに、メンバーだけを書く | warning (`{lag:}` で書くよう促す) |

### D4. 同じ VLAN に同じ端点を 2 回書かない

`trunk_ports` と `access_ports` の両方、または同じリストに同じ端点が 2 回出たら error。

### D5. VLAN ID の重複検査は LAG のノードに展開する

「同じノードの上で別の VLAN エントリが同じ `vlan_id` を使っていないか」は、MLAG を指すエントリを両ノードに展開してから検査する。
エクスポーター (cytoscape) も、VLAN の所属を両ノードに出す。

### D6. 書けるが、検査しないもの

- **peer-link**: 実機では全 VLAN を暗黙に通すことが多い。書いても書かなくてもよい
- **サーバー側の bond**: `access_ports` に書くかどうかは書き手に任せる (VM の vNIC を書く近似との整合。drafts/0007)
- **native VLAN の一致**: MLAG は 1 エントリなので両ノードで食い違いようがない。LACP の両端の一致は検査しない

## Pass A との差分

| 項目 | Pass A (drafts/0013) | Pass C |
|---|---|---|
| LAG の指し方 | `{interface: <LAG id>}` (新キーは作らない) | `{lag: <LAG id>}` (ADR-0001 D8) |
| `node` | 任意 (書けば照合) | 書かない (1.x の間は warning で受け付け、照合する) |
| 受付の表 | ADR-0012 D5 の表に行を追加 | スキーマ (`interface` / `lag` のどちらか一方) |

## References

- [ラウンド4 横断評価メモ](evaluations/round4-evaluation.md)、設計比較 `evaluations/adr0013/`、`evaluations/round4/passc/`
- IEEE 802.1AX (Link Aggregation)
