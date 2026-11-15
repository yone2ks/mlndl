# ADR-0026 Pass C の試し書き

参照の向き (案 A: L2VNI に `vlans`、案 C: VLAN に `l2vni`) をゼロから比べるために、example-author が書いた。案 C は採らなかった。

| ファイル | 内容 | 案 |
|---|---|---|
| P1_caseC_mixed_vlans.yaml | Pass B の B1 (ES + leaf3 だけ別番号 + leaf4) を案 C で | C |
| P2_caseA_three_l2vnis.yaml / P2_caseC_three_l2vnis.yaml | L2VNI 3 つ、VLAN 6 つ (うち 1 つは VXLAN を使わない) | A / C |
| P3_caseA_nxos_adapter.yaml / P3_caseC_nxos_adapter.yaml | NX-OS 2 台 (vlan 20 / vn-segment 10020、vlan 30 / vn-segment 10020) の設定を写したもの | A / C |
| P4_borderleaf_and_bgw.yaml | SVI だけを持つ border leaf と、ポートも SVI もない Multi-Site BGW | A |

`vlans` / `l2vni` は未実装なので、単数の `vlan` に置き換えた写しで検証した。結果は [../evaluation.md](../evaluation.md) の「Pass C の結果」。
