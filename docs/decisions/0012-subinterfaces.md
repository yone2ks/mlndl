# ADR-0012: 802.1Q サブインターフェース

- **Status**: Accepted
- **Date**: 2026-10-15
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー
- **Pass**: C (ラウンド4。[評価メモ](evaluations/round4-evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0012](drafts/0012-subinterfaces.md)
- **関連**: ADR-0001 (D8 参照キー)、ADR-0002 (D1・D5・D7)、ADR-0005 (D2-2 ケース C・D6 `node`)、[ADR-0011](0011-layer3-data-plane.md)

## Context

支社ルーターの router-on-a-stick (物理ポート 1 本を 802.1Q タグで分け、それぞれに IP を振る構成) や、
routed LAG の上のサブ IF を書けるようにする。Pass A (drafts/0012) で実装済み。ラウンド4 Pass B / C で、
参照キー (ADR-0001 D8) と `node` の基準 (ADR-0005 D6) を全体で決め直したので、本 ADR もそれに合わせて確定する。

## Decision

### D1. `layer2.subinterfaces` に置く

```yaml
layer2:
  subinterfaces:
    - id: subif-br1-eth0-10
      attaches_to: {interface: br1-eth0}     # 基盤: L1 IF
      vlan_id: 10                            # このリンク上の 802.1Q タグ番号
      name: eth0.10                          # 機器上の名前
    - id: subif-br1-bond0-100
      attaches_to: {lag: lag-br1-bond0}      # 基盤: LAG
      vlan_id: 100
      name: bond0.100
layer3:
  interfaces:
    - id: br1-eth0-10
      node: br1
      name: eth0.10
      attaches_to: {subinterface: subif-br1-eth0-10}
      ip: 192.168.10.1/24
```

サブ IF はフラットなコレクションの独立エンティティとする (IF の下にネストしない。ADR-0005 D2-1)。
IP と VRF は持たず、L3 は `layer3.interfaces` が `attaches_to: {subinterface:}` で載る。推奨プレフィックスは `subif-`。

### D2. `node` を持たない

サブ IF はタグ番号だけを持ち、ノードは基盤 (L1 IF / LAG) から決まる (ADR-0005 D6)。MLAG を基盤にすれば両ノードに存在する。
`node` を書くとスキーマで error。

### D3. `vlan_id` はタグ番号であり、VLAN への参照ではない

`vlan_id` (1..4094) は、このリンクの上を流れる 802.1Q のタグ番号である。`layer2.vlans` のエンティティは指さない。
タグの書き換えや拠点ごとの番号の再利用で、タグと VLAN エンティティは一致しないことがあるため。

- タグと対向スイッチの VLAN の照合は**しない**。VLAN translation (Arista / Cisco) や対向がトポロジー外の場合に誤検知する
  (ラウンド4 E5、network-tech-reviewer)。ルーター側のサブ IF とスイッチ側の VLAN のつながりは、将来の `broadcast_domain`
  クエリで L1 リンクをたどって導出する
- 同じ物理 IF が VLAN の trunk にも載り、サブ IF の基盤にもなる構成も検査しない。Cumulus / SONiC / Linux では両立し、
  Cisco / Arista では排他で、ベンダーによる (E6)
- 名前を `tag` に変える案 (linguist) は採らなかった (ユーザー判断)

### D4. 基盤は `{interface:}` か `{lag:}`

`attaches_to` には `interface` (L1 IF) か `lag` (LAG) だけを書ける (ADR-0001 D8)。ほかのキーと文字列形式はスキーマで弾く。
L1 IF の `attaches_to` からサブ IF を指すことはできない。

### D5. 検証規則

| チェック | Severity |
|---|---|
| `vlan_id` が 1..4094 か (型) | error |
| `attaches_to` のキーが `interface` / `lag` か (型) | error |
| 基盤がそのキーの種類で定義されているか | error |
| 同じ基盤の上でタグが重複していないか | error |
| L3 IF がサブ IF に載るとき、その `node` が基盤のノード (群) に含まれるか | error |
| L1 IF / LAG / VLAN / サブ IF の ID が互いに重複していないか (ADR-0002 D5) | error |
| 推奨プレフィックス `subif-` | warning |
| `{interface: <LAG の id>}` (旧形式) | warning |

### 範囲外

Q-in-Q (802.1ad)、ネイティブ (タグなし) サブ IF、L2 のサブ IF (service instance / EFP)、VLAN の書き換え。
Q-in-Q を入れる場合は `stag_vlan_id` / `ctag_vlan_id` (ADR-0002 の予約語) を使い、単一タグと Tagged Union にする。
今の `vlan_id` を単一タグの既定として残せば、加算で拡張できる。

## Pass A との差分

| 項目 | Pass A (drafts/0012) | Pass C |
|---|---|---|
| LAG を基盤にする書き方 | `attaches_to: {interface: <LAG id>}` | `attaches_to: {lag: <LAG id>}` |
| L3 がサブ IF に載る書き方 | `attaches_to: {interface: <サブ IF id>}` | `attaches_to: {subinterface: <サブ IF id>}` |
| `{interface:}` が指せる ID 空間の表 (D5) | 本 ADR に置いた | 廃止。キーの種類として ADR-0001 D8 に移した |
| `node` を持たない根拠 | 「親から導出できるものは持たない」 | ADR-0005 D6 の基準 |

## References

- [ラウンド4 横断評価メモ](evaluations/round4-evaluation.md)、設計比較 `evaluations/adr0012/`
- IEEE 802.1Q
