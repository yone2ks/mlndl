# ADR-0010 実証 YAML

[ADR-0010 (Draft・保留)](../../drafts/0010-control-plane-separation.md) の検討で作成した試し書き。
**いずれも `tests/fixtures/` の対象外**であり、pytest からは読まれない。

## `layering/` — 構造案の比較 (2026-09-18)

現行スキーマ上で「BGP をどこに置くか」を比較したもの。

| ファイル | 内容 | 現行スキーマで validate |
|---|---|---|
| `R1_no_protocols.yaml` | `valid_full_dc.yaml` から `protocols` と `layer3.routing_adjacencies` を削除 | 通る (ADR-0010 F1) |
| `R2A_current.yaml` | 案A: 現状構造 | 通る |
| `R2B_adj_in_protocols.yaml` | 案B: 隣接を `protocols` 配下へ | 通らない (未実装構文) |
| `R2C_control_plane.yaml` | 案C: `control_plane` に集約 (採用案の原型) | 通らない (未実装構文) |
| `R2E_vrf_nested.yaml` | 案E: OpenConfig 風に VRF 配下へネスト | 通らない (未実装構文) |
| `R3_isis_attempt.yaml` | 現行スキーマで IS-IS を書く試み | 通る。ただし意味論的に空 (ADR-0010 F5) |

## `draft-r1-syntax/` — ドラフト r1 の構文による書き直し (2026-09-19)

**ADR-0010 r1 の構文** (`BgpNeighborEnd` / `IgpNeighborEnd` / `rr:` 等) で書かれている。
r2 で型名・RR 表現・IGP 端点の分割が変わったため、そのままでは r2 に一致しない。

| ファイル | 内容 |
|---|---|
| `R1_i_single_session_multi_af.yaml` | `valid_full_dc.yaml` を 1 本の eBGP で `[ipv4_unicast, l2vpn_evpn]` を運ぶ形に (制御プレーン部分 92 → 60 行) |
| `R1_ii_multihop_overlay.yaml` | 同、overlay を eBGP multihop に分離 (92 → 83 行) |
| `R2_multisite_wan.yaml` | `valid_multisite_wan.yaml` の書き直し (管理外ピアの表現を検証) |
| `R3_isis_underlay.yaml` | IS-IS underlay + BGP EVPN overlay |
| `R4_ospf_broadcast.yaml` | OSPF マルチアクセスセグメント (2 端点モデルで表現できないことの実証) |
