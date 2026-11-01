# ADR-0010 実証 YAML

[ADR-0010](../../0010-control-plane-separation.md) (Accepted、Pass A は [drafts/0010](../../drafts/0010-control-plane-separation.md)) の検討で作成した試し書き。
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

## `d8-r3/` — D8 の比較と r3 の論点 (2026-11-01)

D8 (BGP エントリの単位) を再開したときの試し書き。**ADR-0010 r2 の構文** (`process:`、管理外ピアは `layer1` ノードのみ等) で書かれている。
r3 で `process` → `instance`、トポロジー外の端点 (`address` + `local_as`)、unnumbered の判定などが変わったため、そのままでは r3 に一致しない。
ケースの一覧は [`d8-r3/README.md`](d8-r3/README.md)。

## `r3/` — r3 の構文による書き直し (2026-11-01、Pass B)

**ADR-0010 r3 の構文** (`instance:`、トポロジー外の端点 `address` + `local_as`、unnumbered はアドレスのない L3 IF) で書いた。
r4 でセッションの `attaches_to` を廃止した (通り道は `update_source` の L3 IF から導く) ため、`attaches_to` を書いたケース (C1・C5 等) はその部分だけ r4 に一致しない。
`R_extended_control_plane.yaml` は `examples/eveng-evpn-lab-extended.yaml` の制御プレーン部分の書き直し (159 行 → 約 55 行)。
ケースの一覧は [`r3/README.md`](r3/README.md)。

## `passc/` — Pass C の試し書き (2026-11-01)

Pass C の構文で、fixture 3 本 (`valid_full_dc` / `valid_multi_vlan` / `valid_multisite_wan`) と `examples/eveng-evpn-lab.yaml` の制御プレーン部分を移行し、
検査で見つかるべき誤りを混ぜた例 (`mistakes.yaml`) を書いた。確定版 (ADR-0010) と違う点: route server を端点の `role` で書いているが、確定版は振る舞いの設定として範囲外にした。
ID の接尾辞は `-evpn` で書いているが、確定版の推奨は用途の語 (`-overlay` 等)。ケースの一覧は [`passc/README.md`](passc/README.md)。
