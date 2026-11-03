# description-only 試し書き — 5 シナリオ

方針 (ユーザー見解):
- `labels` は図上の可視化軸として使う。provider / circuit-id / 契約種別は
  **`description` の自由記述**で表現する。
- 構文は増やさない。`L1Link.labels` も足さない。
- 事業者網 (IP-VPN / 広域イーサ / インターネット / Direct Connect) は
  `role: provider-network` / `role: internet` / `role: dx-connection` 等
  自由文字列の **箱ノード** で表す。
- 専用線 (点対点のラストマイル / ダークファイバ) は **`L1Link`** で書く。
- サイトは `labels: {site: ...}` (ADR-site-boundary の結論)。
- `implementation` は任意。網ノードでは省略してよい。
- `parent` は未実装のため使わない (S5 でも VPC 配下階層をフラットに書く)。
- S4 の BGP over トンネルは書かない (update_source が tunnel_interfaces を
  指せるかが未確定のため)。

付加検証: 他エージェントの案「種別は `link_role` と箱ノードの `role` で足りる」
について、シナリオごとに `link_role` に何を書けるかを試す。

| # | 概要 | 構文の中心 |
|---|------|-----------|
| S1 | 東京 DC - 大阪 DC を 2 本の専用線で冗長 (事業者別、回線 ID あり) | L1Link のみ |
| S2 | 3 拠点を IP-VPN。CE は PE と eBGP | box node + L1Link |
| S3 | 3 拠点を広域イーサ (VLAN 100 ストレッチ) | box node + L1Link + VLAN |
| S4 | 本社 2 本インターネット + 支社と GRE/IPsec (BGP over tunnel なし) | box node + tunnel_interfaces |
| S5 | オンプレ - AWS 間 Direct Connect | box node + L1Link + L3 |

各ファイルは `python -m mlndl validate <path>` で errors 0 を目指す
(warnings/info は許容)。
