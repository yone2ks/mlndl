# ラウンド4 Pass B 試し書き YAML

[ラウンド4 横断評価](../round4-evaluation.md) (ADR-0011〜0013) で、3 本の機能を組み合わせて書いたトポロジー。
`tests/fixtures/` の対象外。

| ファイル | 内容 | `validate --strict` (2026-10-15 実測) |
|---|---|---|
| `a_enterprise_two_sites.yaml` | 本社 MLAG + VRRP デュアルスタック SVI + anycast GW、支社 router-on-a-stick、拠点間 IPsec VTI | 通る |
| `b_evpn_dc_external_peer.yaml` | EVPN Symmetric IRB (anycast GW)、border に routed LAG、その上のサブ IF で外部ピア | parse error 1 件 (`2001:db8:ext::1/126` の `ext` は 16 進数でない。書き手の誤記)。直すと通る |
| `c_common_mistakes.yaml` | 書き手がやりがちな誤り M1〜M9 を混入 | 下表 |

`c_common_mistakes.yaml` は、スキーマ段階の誤り (M4・M5) があるとそこで止まる。M4・M5 を取り除いてから validator 段階を実測した。

| 誤り | 検出 |
|---|---|
| M1 SVI の短縮形と `attaches_to` の食い違い | error |
| M2 VLAN に LAG とメンバーを併記 | error |
| M3 VLAN に LAG のメンバーだけ | warning |
| M4 トンネルの destination を両方指定 | error (スキーマ段階) |
| M5 VRRP の IPv6 VIP がリンクローカルでない | error (スキーマ段階) |
| M6 IPv4 VIP がサブネット外 | error |
| M7 VLAN ポートの node の食い違い | error |
| M8 サブ IF のタグと対向 VLAN の食い違い | 検出されない (ADR-0012 D3 の設計どおり) |
| M9 anycast gateway の IP の食い違い | 検出されない → **2026-10-15 に検出規則を追加** (round4 E1)。現在は error |

`a_` / `b_` / `c_` の 3 本は Pass C より前の形式 (`{interface: <LAG id>}`、L3 IF の `interface`、VLAN のポートの `node`) で書かれている。
Pass C 後は旧形式として warning が出る (`--strict` では error)。評価時点の記録なので書き換えていない。
`passc/` は Pass C の案比較で、仮構文を含む (採用した形は `03_c_no_shortform.yaml` に近い)。
