# MLNDL の文書

MLNDL (Multi-Layer Network Description Language) と、その参照実装 mlndl の文書です。

| 文書 | 読むとき |
|---|---|
| [MLNDL の考え方](concepts.ja.md) | MLNDL が何を書く言語で、どういう考え方で作られているかを知りたい |
| [MLNDL 言語リファレンス](reference/README.ja.md) | このキーに何を書けるか、何が誤りになるかを調べたい |
| [ADR (設計決定の記録)](decisions/README.md) | なぜそう決めたか、どんな案を採らなかったかを知りたい |

## 言語リファレンスの付録

- [role の推奨語彙](role-vocabulary.md)
- [labels の推奨の軸名](label-vocabulary.md)

## mlndl (参照実装) の文書

- 使い方 (CLI と Python): リポジトリの [README](../README.md)
- [Cytoscape.js 出力](exporter-cytoscape.md): ndl-viz などが読むエクスポーターの出力の形

## これから書くもの

- チュートリアル: 小さなトポロジーを L1 から順に書き足していく
- 目的別の書き方 (how-to): MLAG、VM とホスト、サイトと事業者網、EVPN など
- 書き方の推奨 (style guide): id の付け方、並べ方、`description` の使い方
