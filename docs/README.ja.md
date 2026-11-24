# MLNDL の文書

MLNDL (Multi-Layer Network Description Language) と、その参照実装 mlndl の文書です。

| 文書 | 読むとき |
|---|---|
| [はじめの一歩](getting-started.ja.md) | 小さなトポロジーを書いて、検査して、図にするまでを試したい |
| [MLNDL の考え方](concepts.ja.md) | MLNDL が何を書く言語で、どういう考え方で作られているかを知りたい |
| [MLNDL 言語リファレンス](reference/README.ja.md) | このキーに何を書けるか、何が誤りになるかを調べたい |
| [ADR (設計決定の記録)](decisions/README.md) | なぜそう決めたか、どんな案を採らなかったかを知りたい |

## 見本

リポジトリの [examples/](../examples/) にある YAML です。どれも `python -m mlndl validate` で error が出ません。

| ファイル | 書いてあるもの |
|---|---|
| [two-sites-ospf.yaml](../examples/two-sites-ospf.yaml) | 2 拠点の小さな企業網。L1〜L3 と OSPF。[はじめの一歩](getting-started.ja.md) で使う |
| [wan-sites.yaml](../examples/wan-sites.yaml) | 4 拠点と AWS をつなぐ WAN。専用線・IP-VPN・広域イーサ・インターネット VPN・Direct Connect、サイト (`labels.site`) と事業者網の箱 |
| [eveng-evpn-lab.yaml](../examples/eveng-evpn-lab.yaml) | 2 spine / 2 leaf の EVPN-VXLAN のラボ。BGP の underlay と overlay、L2VNI・L3VNI、anycast gateway |
| [eveng-evpn-lab-extended.yaml](../examples/eveng-evpn-lab-extended.yaml) | 上のラボを広げた架空の構成。vPC と VTEP の共有、Ethernet Segment、サブ IF、border leaf の VRF-lite |
| [fabrics-chain.yaml](../examples/fabrics-chain.yaml)・[fabrics-mesh.yaml](../examples/fabrics-mesh.yaml)・[fabrics-superspine.yaml](../examples/fabrics-superspine.yaml) | 3 つの DC ファブリックのつなぎ方 (数珠つなぎ・フルメッシュ・super-spine)。L1 だけ |

## 言語リファレンスの付録

- [書き方の推奨](style-guide.ja.md): id の付け方、`name` の書き方、引用符が要る値、書く順番
- [role の推奨語彙](role-vocabulary.md)
- [labels の推奨の軸名](label-vocabulary.md)

## mlndl (参照実装) の文書

- 使い方 (CLI と Python): リポジトリの [README](../README.md)
- [Cytoscape.js 出力](exporter-cytoscape.md): ndl-viz などが読むエクスポーターの出力の形

## これから書くもの

- 目的別の書き方 (how-to): MLAG、VM とホスト、サイトと事業者網、EVPN など
