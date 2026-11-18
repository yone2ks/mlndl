# ADR-0027 初版の横断評価 (2026-11-18)

対象: `drafts/0027-compatibility-promise.md` の初版 (コミット `5ab3c57`、改訂 1 の前)。5 エージェントが並列に評価し、試し書き担当が `passb/` の B1〜B6 を書いた。
network-tech-reviewer は、ndl-viz のソース (`ndl-viz/src/`) を読んでエクスポーターの規範キーの一覧を作った。

前提 (ユーザー決定。蒸し返さない): `ndl_version` は必須。YAML より古い mlndl はバージョンの違いを知らせて止まる (未知のキーを warning にして読み進めない)。
1.x で新しい error を足すのは 1.x で足したキー・値に付くものだけ。`--strict` は「そのバージョンの warning を error にする」だけを約束し、warning のコードは 1.x で足す。

## 試し書きの検証

統合担当が今の validator で流した。B5a・B6 は名前の直しの後の書き方 (`lags` / `vxlans` / `level_2`) なので、旧名に戻した写しでも流した。

| ファイル | 今の validator | ドラフトどおり実装したら |
|---|---|---|
| B1 (1.0 の YAML を 1.1 の mlndl で読む) | valid | valid |
| B2 (`ndl_version: "1.1"` + `mtu`) | `mtu` の未知のキーの error × 2 | 1.0 の mlndl: バージョンの違いの error 1 本。1.1 の mlndl: valid |
| B3a (1.1 の `mtu` の検査、`mtu` を書かない 1.0 の YAML) | valid | valid (検査はそのキーを書いたエントリにだけ効く) |
| B3b (IPv6 の IF に `mtu: 1000`) | `mtu` の未知のキーの error | 1.1 の mlndl: 新しいキーに付く error (D3 の範囲内) |
| B4 (1.1 で足した warning で `--strict` だけ止まる) | valid | 既定では valid、`--strict` で止まる |
| B5a (名前の直しの後) | `lags` / `vxlans` の未知のキー、`level_2` の値域の error。旧名に戻すと valid | valid |
| B5b (旧名) | valid | 移動先を示す error |
| B6 (L3 IF の `node` と `{lag:}` の機器の食い違いを 1.0 が見逃した想定) | 旧名に戻すと **error** (ADR-0011 D9 の検査が既にある) | — |

B6 は、試し書き担当が「1.0 の実装が見逃している」と想定した誤りだが、今の validator は既に error にしている。想定の例としては成り立たないが、
「文書に error と書いてあるのに実装が見逃していた誤りを 1.x で直す」という論点そのものは残る (下の「バグの修正」)。

`ndl_version: 1.10` (引用符なし) は、今も error になる。YAML が数値の 1.1 と読むので、メッセージは `Input should be a valid string [input_value=1.1]` で分かりにくい (統合担当が確かめた)。

## 一致した点

- D1〜D8 の方向とユーザー決定の 4 点に矛盾はない: 5/5
- エクスポーターの出力にバージョンを入れる (ルートの `meta`): network-tech・spec-architect
- 文書に error と書いてあったのに実装が見逃した誤りは、1.x でバグの修正として直せる (D3 の「新しい error」に当たらない): spec-architect・network-tech・example-author
- 名前の直しは、旧名を移動先を示す error にする形 (ADR-0025 と同じ) でよい: dsl-designer・spec-architect
- 1.x で足したキーの検査は、そのキーを書いたエントリにだけ効かせる: dsl-designer・example-author (B3a / B3b)

## 改訂 1 で反映した指摘

| 指摘 | 誰 | 反映 |
|---|---|---|
| エクスポーターの規範キーの一覧 (`type` の値、ノード・エッジの種類ごとのキー、埋め込みのリストの中のキー)。参考のままでよいキー (`l3_interfaces[].roles`、`vlan_member` の端点の `candidates` / `outside_svi_subnet`、機器ノードの `vrfs[]` など) | network-tech | D1 に一覧の要点、全体は `docs/exporter-cytoscape.md` に「規範」の列を足して示す (実装のとき) |
| エクスポーターの出力のルートに `meta: {ndl_version, mlndl_version}`。今のルートは `nodes` / `edges` だけで、ndl-viz はその 2 つしか読まない (統合担当が確かめた) | network-tech・spec-architect | D1・D6 に。規範キー |
| 入力の `meta.<ツール名>` はエクスポーターの出力に流れない | network-tech | D7 に明記 |
| 「必須のキーを任意にする」「受け付ける型を広げる」は、YAML の書き手には破壊的でないが、Python のモデルの型 (`str` → `str \| None`) とエクスポーターの出力を読む側には破壊的になりうる | spec-architect | D1 で pydantic のモデルの属性と型を参考と明記し、D2 に但し書き (規範キーは同じ条件で出し続ける) |
| `MLNDLTopology` を規範にすると、`model_dump()` の形も規範に見える | dsl-designer・spec-architect | D1: 規範なのは公開の関数と `ValidationResult`。モデルの中身と `model_dump()` は参考。比べるなら `exclude_unset=True` を勧める |
| 文書に error と書いてあったのに実装が見逃した誤りは、バグの修正として 1.x で直す。リリースノートでは新しい warning と別の節 | spec-architect・network-tech・example-author | D3 に |
| 1.x で足したキーの検査を既存の YAML に効かせない実装の指針 (型・`field_validator` はそのキーを書いたときだけ。validator の横断の検査は新しいキーを含むエンティティだけ) | dsl-designer・example-author | D3 に |
| 1.1 で足したキーに 1.2 で error を足すのも D3 の範囲内 | example-author | D3 に |
| 下流のツールは、未知のキーだけでなく未知の値 (`type` など) と分岐も無視する | dsl-designer・network-tech | D1 に |
| warning を info に下げるのもリリースノートに書く | spec-architect | D4 に |
| マイナーが mlndl の知るもの以下なら読む、を明記 | spec-architect | D5 に |
| バージョンの比較は parser で pydantic に渡す前に行い、専用の例外にする。CLI は「スキーマの段階で」の注記を付けない | dsl-designer | D5 に (実装の指針) |
| `ndl_version` は文字列。書式 `^\d+\.\d+$`。数値で書いたら「引用符で囲む」専用の error。比較は数値の組で (`"1.10"` > `"1.9"`) | dsl-designer | D5 に |
| `ndl_version` の定義「この YAML が使う最も新しいバージョン」は「書いたときのバージョン」と誤読される | linguist | D5: 「この YAML を読むのに要る、最も古い mlndl のバージョン」を主にし、error の文面を「1.1 以上を必要とします」に |
| `ndl_version` を書かないときの error に、必須の理由を添える | linguist | D5 に |
| 1.0 を出す前の破壊的な変更 (名前の直しなど) は、この約束の対象外 | dsl-designer | D2 の前に明記 |
| `derive.py` の関数は 1.0 では公開の API に入れない (後から加算で足せる。一度入れると減らせない) | spec-architect | D1 に。dsl-designer はエクスポーターが使う 6 関数を入れる案 (下の「採らなかった指摘」) |
| `BgpSession.address_families` は `min_length=1` (空を許さない。既定値は持たない) | spec-architect | Consequences の「1.0 の前に必須になるもの」に。既定値 `["ipv4_unicast"]` は、1.0 で固まり EVPN の書き忘れと区別できないので採らない |
| 呼び名「約束するキー」は D1 の「規範 / 参考」と別の語 | linguist | **規範キー**に。D1 の前に「規範」「参考」の定義を 1 行 |
| 「版」と「バージョン」、「未知のキー」と「知らないキー」の揺れ | linguist | 「バージョン」「未知のキー」にそろえた |
| D7 の見出しが「入れる / 残す」のどちらとも読める | linguist | 「1.0 の後も残す形」に |
| D8 の 1 行目を「同じメジャーバージョンの」に | linguist | 反映 |
| Amends の漏れ: ADR-0002 D8・ADR-0015・ADR-0025 | spec-architect | Amends / 関連に足した。ADR-0010 (`address_families`)・ADR-0014 (`vteps`) の改訂は、1.0 の前の型の直しを決める ADR で行う |
| `schema.json`・Python / pydantic の下限・CLI の終了コードの扱い | spec-architect | `schema.json` は参考 (生成物) と D1 に。終了コードは「error があれば 1、なければ 0」を規範に。下限は 1.0 の作業で決める |

## 採らなかった指摘

- **`derive.py` のうち、エクスポーターが使う 6 関数を 1.0 の公開の API に入れる** (dsl-designer): 採らない — ndl-viz も eve-lab-builder も derive を直接呼ばない (spec-architect が確かめた)。
  公開の API は後から足せるが、入れると減らせない。必要になったら 1.x で加算する
- **移動先を示す error の文面を 1.x の間変えない** (example-author): 採らない — メッセージの文面は参考 (D1)。下流のツールにはメッセージを読ませない
- **バージョンの違いの error に、1.1 で足したキーの一覧を添える** (example-author): 実装のときに決める
- **`ndl_version: "1.0"` のまま 1.1 のキーを書いたら、メッセージに「`ndl_version` を上げる」を添える**: 実装のときに決める (初版のまま)

## 残る論点 (Pass C 向け)

1. **名前の直しの新しい名前** (linguist の提案):
   - `layer2.vxlan` → `vxlans` (初版。dsl-designer・spec-architect) か `vnis` (linguist。中身は VNI のエントリで、`vteps` と並ぶ)
   - IS-IS の `level-1` / `level-2` / `level-all` → `level_1` / `level_2` / `level_all` (初版。IS-IS の YANG (RFC 9130) の `level-all` の区切りを変えるだけ) か `level_1_2` (linguist。「Level 1-2」は CLI の慣用)
   - この ADR は名前の直しが 1.0 の前に必須になることを決めるだけで、新しい名前は名前の直しの ADR で決める。Pass C でどこで決めるかを確かめる
2. **ADR-0003 との関係**: 試し書き B4 は「推奨外の `role` の値に warning」を 1.1 の例にしたが、ADR-0003 は「推奨外の `role` に mlndl は warning を出さない」と決めている。
   D2 の「warning を足すのは 1.x で許す」は、ほかの ADR が「warning を出さない」と決めたものを覆すときは、その ADR の改訂が要る (互換の約束とは別に)。Pass C で 1 行足すかを確かめる
3. **規範キーの一覧の最終形**: network-tech の一覧を `docs/exporter-cytoscape.md` に写すとき、eve-lab-builder が読むキーは推定 (手元にソースがない)。ユーザーに確かめる

## Pass C への Input サマリ

**Pass C で参照するもの**: 本評価メモ、[1.0 に向けた棚卸し](../release-1.0/inventory.md)、Accepted の ADR (特に 0002・0003・0010・0015・0025・0026)、CLAUDE.md、
`docs/exporter-cytoscape.md`、`docs/reference/README.ja.md`・`validation.ja.md`、試し書き (`adr0027/` の C1〜C6、`passb/` の B1〜B6)、
実装 (`src/mlndl/schema/topology.py`・`parser.py`・`__init__.py`・`__main__.py`・`exporter/cytoscape.py`)、ndl-viz の `src/types/topology.ts`。
**drafts/0027 は参照しない** (Pass C の原則)。

### 前提 (ユーザー決定。蒸し返さない)

- `ndl_version` は必須
- YAML より古い mlndl は、バージョンの違いを知らせて止まる。未知のキーを warning にして読み進めない
- 1.x で新しい error を足すのは、1.x で足したキー・値に付くものだけ
- `--strict` は「そのバージョンの warning を error にする」だけを約束する。warning のコードと個別の抑止は 1.x で足す

### 確定すべき論点 (優先順)

1. **約束の範囲**: YAML、検査の結果と severity、公開の Python の API (どの関数・クラス)、CLI (サブコマンド・終了コード・`--strict`)、エクスポーターの規範キー (一覧とルートの `meta`)。参考にするもの (モデルの中身、`model_dump()`、`derive.py`、メッセージ、`schema.json`)
2. **1.x で許す変更と 2.0 が要る変更の表**: 「必須を任意に」「型を広げる」の扱い (YAML とモデルと出力で違う)、下流のツールが未知のキー・値・分岐を無視すること
3. **新しい error とバグの修正の線引き**、1.x で足したキーの検査の書き方
4. **`--strict` とリリースノート**
5. **`ndl_version`**: 定義 (読むのに要る最も古いバージョン)、書式 (文字列、`^\d+\.\d+$`)、比べ方、バージョンの違いの error (parser で先に)、マイナーを上げる条件
6. **パッケージのバージョン**と `LANGUAGE_VERSION`、エクスポーターの `meta.mlndl_version`
7. **1.0 の後も残す形** (糖衣構文、`meta` の受け付け、旧形式の error) と、1.0 を出す前の変更は対象外であること
8. **利用者向けの書き方** (向きをそのまま書く、規範キー)
9. **1.0 の前に必須になるもの** (名前の直し、`vteps` の `min_length=1`、`address_families` の `min_length=1`、既定値の一覧) と、それを決める場所
