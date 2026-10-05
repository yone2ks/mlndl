# ADR-0012 設計比較 YAML

[ADR-0012](../../drafts/0012-subinterfaces.md) の設計ラウンド (2026-10-04) で、サブインターフェースの表現案を比べるために書いたもの。
**いずれも ADR-0012 確定前の仮構文**で書かれており、採用案と一致しないものを含む。`tests/fixtures/` の対象外。

| ファイル | 比べた案 | 採否 |
|---|---|---|
| `T1_variant_A_minimal.yaml` | node なし、VLAN 参照なし (`vlan_id` のみ) | **採用** (ただし ID の書き方は `subif-` 形式に変更) |
| `T1_variant_B_with_node.yaml` | A + `node` | 却下 (親 IF からの導出と二重表現) |
| `T1_variant_C_with_vlan_ref.yaml` | `vlan` (VLAN エンティティ参照) のみ、`vlan_id` なし | 却下 (タグ書き換えを表現できない。VLAN を書かない支社構成で書けない) |
| `T2_variant_A_lag_attaches_interface.yaml` | LAG を `attaches_to: {interface: <LAG id>}` で指す | **採用** |
| `T2_variant_A_lag_attaches_lag.yaml` | LAG を `attaches_to: {lag: <LAG id>}` で指す | 却下 (ADR-0001 の改訂が必要) |
| `T3_qinq_vlan_inner.yaml` / `T3_qinq_stag_ctag.yaml` | Q-in-Q の 2 通りの書き方 | Q-in-Q 自体を範囲外とした。将来入れる場合は `stag_vlan_id` / `ctag_vlan_id` が明確 |

実証エージェントは ID に `br1-eth0.10` のようなドット入りの形を使っているが、ADR-0002 D1 の正規表現はドットを許さない。
採用案では `subif-br1-eth0-10` とし、機器上の名前 `eth0.10` は `name` に書く。
