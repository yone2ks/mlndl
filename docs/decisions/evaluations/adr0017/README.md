# ADR-0017 試し書き (Pass B)

`drafts/0017-sites-and-wan.md` の D1〜D5 に合わせて、`description-only/` の S1〜S5 を書き直し、
D5-2 を試す S6 を 2 本 (候補 a / 候補 b) 追加したもの。元ファイルは変更していない。

## 書き直しの方針 (ドラフトに合わせたもの)

- 事業者網の箱ノードの `role` は **`provider-network` の 1 語**に揃える
  (`role: internet` / `dx-connection` は使わない。網の種類とサービス名は `name` で読む。D3)
- `link_role` は書かないか、既存の推奨語彙 (`underlay` / `access` / `trunk` / `peer-link` / `management` / `uplink`) だけ。
  `wan-l2` / `wan-l3` / `wan-internet` は使わない (D2)
- `description` は人が読む文にする。`key=value` 書式はやめる (D4)
- `labels` には **サイトしか書かない** (`labels: {site: ...}`)。provider / circuit-id / cidr / vpc などの
  識別子・参照めいた値は書かない (D1、D4)
- S5 の BGP は AWS 側をトポロジー外の相手 `{address, local_as}` にする (D5-1)
- S6 は広域イーサの上で 2 拠点の router が直接 BGP / OSPF を張る構成 (D5-2 の未決点)。
  候補 (a) は相手をトポロジー外として書く。候補 (b) は箱 IF を VLAN の trunk_ports に書いて
  derive がどうなるかを試す

## シナリオ一覧

| # | 概要 | 構文の中心 | 期待 |
|---|------|-----------|------|
| S1 | 東京 DC - 大阪 DC を 2 本の専用線で冗長 | L1Link のみ | valid |
| S2 | 3 拠点を IP-VPN。CE は PE と eBGP | 箱ノード + L1Link + BGP (D5-1) | valid |
| S3 | 3 拠点を広域イーサで接続。VLAN 100 ストレッチ | 箱ノード + L1Link + VLAN | valid |
| S4 | 本社 2 本インターネット + 支社と GRE/IPsec | 箱ノード × 2 + tunnel_interfaces + BGP (D5-1) | valid |
| S5 | オンプレ - AWS 間 Direct Connect | 箱ノード + L1Link + BGP (D5-1) | valid |
| S6a | 2 拠点が広域イーサ越しに直接 BGP (相手を外として書く) | 箱ノード + 外部 BGP | valid (ドラフト D5-2 候補 a) |
| S6b | 同上。箱 IF を VLAN の trunk_ports に書き、derive の結果を見る | 箱ノード + VLAN trunk_ports + 内部 BGP | error (ドラフト D5-2 候補 b。期待: 通り道の食い違い) |

## 検証

```
cd mlndl
python -m mlndl validate docs/decisions/evaluations/adr0017/S1_leased_lines.yaml
# ...
```

S6b は mismatch の error を 1 件出す想定 (本文参照)。他は errors 0。
