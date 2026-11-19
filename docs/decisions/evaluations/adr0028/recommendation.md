# ADR-0028 Pass A の検討 (2026-11-19)

5 エージェント (spec-architect・linguist・dsl-designer・network-tech-reviewer・example-author) に、
[1.0 に向けた棚卸し](../release-1.0/inventory.md) の §2〜§4 と、[ADR-0027](../../0027-compatibility-promise.md) の「1.0 の前に必須になるもの」の表を渡して並列に評価してもらった。
統合担当が報告をコードと照らして確かめ、割れた 3 点をユーザーが決めた。

## 試し書き

example-author が書いた。改名した所 (`lags` → `lag`、`vxlans` → `vxlan`、`level_*` → `level-*`) を今の形に戻したコピーを、今の validator で `--strict` で検証した (2026-11-19)。

| ファイル | 内容 | 戻したコピーの結果 |
|---|---|---|
| `a1-evpn-mlag-renamed.yaml` | EVPN-VXLAN + ES + BGP 2 本 + BFD を直した後の形で。LACP を書く LAG と書かない LAG を混ぜた | error も warning もない |
| `a2-isis-levels.yaml` | IS-IS を `level_1` / `level_2` / `level_all` で | error も warning もない |
| `a3-old-names.yaml` | 旧名 (`lag` / `vxlan` / `level-2`)。期待するメッセージの案をコメントに | 今は通る (ADR-0028 の実装後に error) |
| `a4-empty-lists.yaml` | `vteps: []`・`address_families: []`・`address_families` を書かない | 今は `vteps: []` の 1 本だけが error (スキーマの段階で止まる) |
| `a5-defaults-removed.yaml` | LACP と BFD の既定値をなくした形 | error も warning もない |

## 一致した点

- `layer1.lag` → `lags`、`layer2.vxlan` → `vxlans` (全員)。旧名は移動先を示す error
- `L2VxLAN.vteps` と `BgpSession.address_families` は 1 つ以上を必須にし、既定値を持たない (全員)。`address_families` の既定値を `[ipv4_unicast]` にしない (EVPN の書き忘れと区別できない)
- BFD のタイマー (`min_tx` / `min_rx` / `multiplier`) は既定値をなくす (全員。機器ごとに既定値が違い、300 / 300 / 3 で埋めると「書いていない」と区別できない)
- `False` の既定値 (`native` / `route_reflector_client` / セッションの `bfd`) は残す (全員。「書いていない = 使わない」が実機の挙動と一致する)
- 棚卸し §4 の `type` と `mode` の混在、2 つの `members` は名前を変えない (全員)

## 割れた点と決定

| 論点 | 意見 | 決定 |
|---|---|---|
| IS-IS の `level` の値 | linguist・dsl・spec・example: 下線区切り (`level_1` / `level_2` / `level_all`)。network-tech: RFC 9130 の YANG と各社の CLI がハイフンなので残す | **下線にそろえる** (ユーザー) |
| `LacpConfig` の既定値 (`mode = "active"`・`min_links = 1`) | network-tech: 両方なくす。example: `mode` だけなくす。spec・dsl: 残す | **両方なくす** (ユーザー) |
| 棚卸しにない値域を狭める直し (`local_as`・`vni`・BFD・LAG / ES の `members`・トンネルの `mtu` の上限) | network-tech・dsl が提案。spec は触れず | **ADR-0028 に入れる** (ユーザー) |
| エクスポーターの機器ノードの `vlans` を改名 | dsl: `port_vlans` などに。linguist・spec: 変えず文書で明示 | 変えない (多数。ndl-viz が読む規範キーで、`docs/exporter-cytoscape.md` に注記がすでにある) |
| OSPF の `interface` を `update_source` に | dsl: BGP と対称に。linguist・spec: 変えない | 変えない (`update_source` は BGP の用語で、OSPF の隣接は IF の上に張られるので意味が違う。統合担当) |

## 統合担当が確かめたこと

- `local_as` (`control_plane.py:39`・`:117`) と `vni` (`layer2.py:155`・`:201`) は `int` だけで範囲がない。BFD のタイマー (`control_plane.py:91-93`) にも値域がない。`Lag.members` (`layer1.py:325`) は空でも型を通る。ES の `members` の 2 つ以上は `field_validator` (`layer1.py:418`) で見ている
- エクスポーターは LACP を `exclude_unset` で書かれた値だけ出す (`cytoscape.py:146`)。モデルの既定値 `active` とすでに食い違っている。ndl-viz も `lacp?.mode` を任意として扱う (`src/types/topology.ts:91`)。既定値をなくしても下流は変わらない
- エクスポーターは BFD のタイマーを出さない。機器ノードの LAG のキーは `lags` (複数形) で、改名の影響はない (`cytoscape.py:236`)
- IS-IS の `level` はエクスポーターが値をそのまま出す (`cytoscape.py:664`)。ndl-viz は線の札に「IS-IS level-2」と出している (`src/flow/session.ts:39`)。改名すると札が `level_2` になるので、ndl-viz で表示を整えるかを決める
- example-author の「LACP の既定値をなくすと `min_links: 1` を繰り返し書くことになる」は誤り。既定値をなくしても任意のままで、書かなければ「書いていない」になるだけ (a5 も `min_links` を書かずに通る)
- network-tech の「Cumulus の BFD の既定は 300 / 300 / 3」と example-author の「Cumulus は 100 / 100 / 3」は食い違う。どちらにしても既定値を言語で持たない結論は変わらないので、ADR には機器の既定値を書かない
