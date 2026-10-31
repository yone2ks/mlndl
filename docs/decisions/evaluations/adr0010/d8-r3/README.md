# ADR-0010 D8 Pass C3 (再開) — BGP エントリの単位

[ADR-0010 (Draft)](../../../drafts/0010-control-plane-separation.md) の未決 D8 (BGP エントリの単位を VRF ごとのインスタンス D8-a にするか role ごとの D8-b にするか) を 2026-11-01 に再開した際の試し書き。

いずれも `tests/fixtures/` の対象外。スキーマはまだ `control_plane` を知らないため `python -m mlndl validate` は通らない。L1 / L3 は参照整合性だけが保てる最小構成に留め、焦点は `control_plane.*` の記述。構文は ADR-0010 r2 (D3 の `BgpSession` / `OspfAdjacency` / `IsisAdjacency`、D4 のインスタンスエントリ、D5 の router_id、D7 の ID 接尾辞) に合わせた。

## ファイル一覧

| ファイル | ケース | 単位 |
|---|---|---|
| `C1_split_underlay_overlay.yaml` | spine1–leaf1 の underlay (/31 single-hop eBGP) と overlay (loopback 間 eBGP multihop, EVPN) を 2 セッションで書く | D8-a |
| `C1_split_underlay_overlay_d8b.yaml` | 同じ構成を role 単位 (underlay / overlay) で書く | D8-b |
| `C2_unnumbered_multi_af.yaml` | FRR 定番 1 本 eBGP unnumbered セッションで `ipv4_unicast` + `l2vpn_evpn` を同時に運ぶ | D8-a |
| `C2_unnumbered_multi_af_d8b.yaml` | 同じ構成を role 単位で書こうとした (= 書けないことの実証) | D8-b |
| `C3_igp_underlay_ibgp_rr.yaml` | OSPF underlay + 全ノード同一 AS の iBGP EVPN overlay (spine が RR) | D8-a |
| `C4_vrf_lite_external.yaml` | border leaf ↔ WAN ルーターの VRF-lite (VRF ごとに別セッション、サブ IF 上) | D8-a |
| `C5_ibgp_over_svi.yaml` | vPC ペア leaf3–leaf4 間の iBGP を Vlan3999 の SVI 上に張る | D8-a |
| `C6_external_peer.yaml` | ISP など管理外ピア (IP と AS だけ分かる) | D8-a |
| `C7_multisite_bgw.yaml` | EVPN マルチサイトで DC をまたいで BGW 間に overlay EVPN を張る | D8-a |
