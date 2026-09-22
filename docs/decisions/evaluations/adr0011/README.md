# ADR-0011 実測資料

[ADR-0011](../../drafts/0011-layer3-data-plane.md) の根拠となった試し書きと実測。
**`tests/fixtures/` の対象外**であり、pytest からは読まれない。

## `topologies/` — 現行スキーマでどこまで書けるか (2026-09-20)

制御プレーン (BGP / OSPF) は書かず、L1 / L2 / L3 のデータプレーンだけで代表トポロジーを書いた。
**5 本とも `python -m mlndl validate` を通る**が、書けない要素を `# 書けない:` のコメントで
残した結果であり、コメントは合計 27 箇所ある (ADR-0011 F1)。

| ファイル | トポロジー | 主に書けなかったもの |
|---|---|---|
| `T1_campus_3tier.yaml` | キャンパス 3-Tier + VRRP | デフォルトルート、クライアントの GW |
| `T2_spine_leaf_evpn_dataplane.yaml` | DC Spine-Leaf EVPN のデータプレーン | anycast gateway の明示、MLAG の anycast VTEP |
| `T3_branch_router_on_a_stick.yaml` | 支社ルーター | 802.1Q サブ IF、トンネル、静的経路 (13 箇所) |
| `T4_dual_stack.yaml` | デュアルスタック | 1 IF に v4 + v6 (3 エントリに分割) |
| `T5_vsphere_dvswitch_fixed.yaml` | vSphere | dvSwitch / PortGroup / VMkernel |

`T5` は壊れている `tests/fixtures/valid_vsphere_dvswitch.yaml` (IF 名を参照している) を
ID 参照に直した版で、validate を通る。

## `contradictions/` — 矛盾が黙って通る例 (ADR-0011 F2・F4)

| ファイル | 内容 | 現行の結果 |
|---|---|---|
| `l3_contradiction.yaml` | `interface` / `vlan` / `attaches_to` が三者三様 + 不正な IP | `attaches_to` の VLAN 参照だけが error (ADR-0005 D2-2 の正規形が通らない = F3) |
| `l3_contradiction2.yaml` | 食い違う `interface` / `vlan`、不正な IP、`/33`、別ノードの IF 参照 | **すべて通る** |
| `bad_ip_export.yaml` | 不正な IP を持つ SVI | validate も **cytoscape export も通り**、VLAN のサブネットが警告なく消える |

## `dualstack/` — デュアルスタック表現の案比較 (ADR-0011 D5)

`T4_dual_stack.yaml` を 3 案で書き直したもの。案 U (`ip` = IPv4 単数 + `ipv6` 単数) が採用案。

| ファイル | 案 | 既存 fixture の変更行数 |
|---|---|---|
| `T4_variant_U.yaml` | `ip` (IPv4 単数) + `ipv6` (単数) — **採用** | 0 行 |
| `T4_variant_Uplus.yaml` | `ip` 単数 + `ipv6` リスト | 0 行 |
| `T4_variant_L.yaml` | `ipv4` リスト + `ipv6` リスト (`ip` 廃止) | 9 行 |

いずれも新構文のため現行スキーマでは parse できない。
