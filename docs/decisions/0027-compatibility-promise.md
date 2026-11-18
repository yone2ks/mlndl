# ADR-0027: 互換の約束 — 1.0 の後、1.x で許す変更と 2.0 が要る変更

- **Status**: Accepted (2026-11-18 に Pass C で確定。2026-11-19 に実装: `ndl_version` の検査・`LANGUAGE_VERSION`・`UnsupportedVersionError`・出力の `meta`・docs。ndl-viz の対応は要らない (出力のルートの未知のキーを読まない))
- **Date**: 2026-11-18
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、
  ユーザー (`ndl_version` を必須に、古い mlndl はバージョンの違いを知らせて止まる、新しい error は 1.x で足したキー・値だけ、`--strict` はバージョンを固定してもらう、eve-lab-builder のキーは推定で書く、リンクの端は `source` / `target` のまま)
- **Pass**: C ([評価メモ](evaluations/adr0027/evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0027](drafts/0027-compatibility-promise.md)
- **Amends**: ADR-0010 の移行の改訂 (「1.0 の後は破壊的な変更にメジャーバージョンの更新を必須とする」の中身を決める)、ADR-0002 D8 (severity の意味)、
  ADR-0015 (`Ref` の検査)、ADR-0025 (1.0 の後も「読み替えて warning」を既定にしない)、CLAUDE.md §3 (`ndl_version`)
- **関連**: ADR-0003 (推奨外の `role` に warning を出さない。この ADR は上書きしない)、ADR-0006 (リンクの端の向き)、ADR-0028 (1.0 の前の型と名前の直し。これから)、
  [1.0 に向けた棚卸し](evaluations/release-1.0/inventory.md)

## Context

最初のリリースは 1.0 で、1.0 の後は破壊的な変更にメジャーバージョンの更新が要る (ADR-0010 の移行の改訂)。ところが、何が「破壊的な変更」かは決めていない。
1.0 に向けた棚卸し (2026-11-18) では仮の物差しで項目を振り分けたが、その物差しを約束として書く必要がある。今の実装には次の穴がある (2026-11-18 に確かめた)。

- `ndl_version` は CLAUDE.md §3・`docs/reference/README.ja.md`・`validation.ja.md` で「必須」とあるが、実装は既定値 `"1.0"` を持ち、書かなくても通る (`src/mlndl/schema/topology.py:27`・`:40`。試し書き C1)
- 全モデルが `extra="forbid"` なので、1.1 で足したキーを 1.0 の mlndl は `Extra inputs are not permitted` で拒む。`ndl_version: "1.1"` と書いてもバージョンの違いは知らせず、利用者は書き損じと区別できない (試し書き C2・C3・B2)
- 引用符なしの `ndl_version: 1.10` は、YAML が数値の 1.1 と読み、`Input should be a valid string [input_value=1.1]` という分かりにくい error になる (試し書き P1)
- パッケージのバージョンは `0.1.0` で、`ndl_version` との関係が決まっていない
- 検査を足すこと・緩めることが互換にどう効くか、`--strict` で CI を回す利用者に何を約束するかが決まっていない

## Decision

この ADR の**規範**は、変えるのにメジャーバージョンの更新 (2.0) が要るもの、**参考** (informative) は 1.x で変えてよいものを指す。
これは「仕様としての拘束力」の区別で、ADR-0005 D4 の「注釈側の構成子」(`role` / `labels` など、mlndl が値を検査しないもの) とは別の概念である。
注釈側の構成子も、キーとしては規範である (`role` というキーを 1.x で消さない)。

この約束は 1.0 のリリースから効く。1.0 を出す前の破壊的な変更 (ADR-0028 の名前と型の直しなど) は、この約束の対象外である。

### D1. 約束の範囲

| 対象 | 扱い |
|---|---|
| YAML の書き方 (区画・キー・形・必須 / 任意・値域・Literal の値・既定値・意味) | **規範** |
| 検査の結果 (どの YAML が error になるか) と severity の意味 (ADR-0002 D8) | **規範**。D3 の範囲で 1.x でも変わる |
| Python の公開の API (D1-1) | **規範** |
| CLI: サブコマンド (`validate` / `export` / `schema`)、オプション (`--strict` / `--format`)、終了コード (error があれば 1、なければ 0)、出力の行頭 (`ERROR` / `WARNING` / `INFO`) | **規範** |
| エクスポーター (Cytoscape の JSON) の規範キー (D1-2) | **規範**。キー・値を足すのは 1.x でよい。消す・改名する・意味を変えるのは 2.0 |
| 規範キー以外の出力、pydantic のモデルの中身 (属性と型・クラス名)・`model_dump()` の形、`derive.py` の関数、`exporter` のモジュールの内部、メッセージの文面とパスの書き方、`docs/reference/schema.json` (生成物) | **参考** |

#### D1-1. Python の公開の API

- 関数: `parse` / `parse_file` / `validate` / `validate_all` の引数・戻り値の型・例外の型
- `ValidationResult` (`errors` / `warnings` / `notes` / `ok`) と `ValidationError` (`path` / `message` / `severity`、`str()` で 1 行の文字列になること)
- `MLNDLTopology` と、その最上位の属性 (`ndl_version` / `meta` / `layer1` / `layer2` / `layer3` / `control_plane`)、`index()` / `resolve()`。`resolve()` が返すのは「`id` を持つエンティティ」までを約束する
- `IdIndex`、`Ref`、`LANGUAGE_VERSION`、`__version__`、`UnsupportedVersionError` (D5)
- 区画の中のモデル (`L1Node` など) の属性と型は参考。1.x でフィールドが足され、型が広がることがある。モデルを比べるなら `model_dump(exclude_unset=True)` を勧め、`match` で分岐するなら `case _:` を置く
- `derive.py` の関数は 1.0 では公開しない。下流のツールはエクスポーターの出力を読み、derive を直接呼ばない。必要になれば 1.x で加算する (一度公開すると減らせない)

#### D1-2. エクスポーターの規範キー

- ルート: `nodes` / `edges` と、1.0 で足す `meta: {ndl_version, mlndl_version}` (D6)
- 要素の `type` の値: ノードは `node` / `vlan` / `l2vni` / `l3vni` / `bridge` / `ethernet_segment`、エッジは `link` / `attaches_to` / `vlan_member` / `routing_neighbor` / `tunnel` / `lag_bundle`
- 要素の種類ごとのキーと、埋め込みのリスト (`l3_interfaces[]` / `lags[]` / `vteps[]` / `tunnels[]` / `bgp_sessions[]` / `vlan_member` の `endpoints[]` など) の中のキー。
  一覧は network-tech-reviewer が ndl-viz のソースで確かめたもの (評価メモの「Pass C の結果」)。`docs/exporter-cytoscape.md` の表に「規範」の列を足して示す
- 印は「そのキーが同じ条件で同じ形で出続ける」ことを約束する。値の書式 (`label` の文字列の整形、`description` の中身、リストの並び順) までは約束しない
- 参考のままのキー: `l3_interfaces[].roles`、`label` の文字列の書式、機器ノードの `vrfs` の並び順など
- eve-lab-builder が読むキーは、手元にソースがないので推定で規範に含めた (機器の `id` / `device_type` / `implementation` / `labels.site`、`link` の `source` / `target` / `source_if` / `target_if` / `link_speed`、設定を作るための L3 IF・LAG・VTEP・セッション)。
  eve-lab-builder を確かめられるようになったら、`docs/exporter-cytoscape.md` の「規範」の列を実際のキーで直す (ユーザー決定)
- エッジの `source` / `target` は、Cytoscape.js が必須にしているキーで、**向きの意味はない** (ADR-0006。`link` では `endpoints[0]` が `source`、`endpoints[1]` が `target`)。
  `source_if` / `target_if` / `source_lag` / `target_lag` も同じ順で、向きを表さない。名前は変えない (ユーザー決定)
- 下流のツール (ndl-viz・eve-lab-builder) は、出力の**未知のキー・未知の値 (`type` など)・未知の分岐**を無視して読み進める。1.x でキー・値が足されても止まらないため
- 出力のキーを改名したいときは、新しいキーを足し、古いキーは 2.0 まで残す。入力 (YAML) では同じことをしない (同じ意味を 2 つの名前で書ける形は作らない。ADR-0025)

### D2. 1.x で許す変更と、2.0 が要る変更

| 変更 | YAML の書き手 | Python の利用者 | エクスポーターの出力を読む下流のツール |
|---|---|---|---|
| 任意のキー・コレクションを足す | 1.x | 1.x (モデルに属性が増える) | 1.x (出力にキーが増える) |
| Literal の値・Tagged Union の分岐を足す | 1.x | 1.x (`case _:` を置く) | 1.x (未知の値を無視する) |
| 受け付ける型を広げる (`X` → `X \| list[X]`)、値域を広げる | 1.x | 1.x (属性の型が広がりうる。モデルは参考) | 1.x (規範キーは同じ形で出し続ける) |
| 必須のキーを任意にする | 1.x | 1.x (`str` → `str \| None` になりうる。モデルは参考) | 1.x (規範キーは同じ条件で出し続ける) |
| 検査を緩める (error を warning に、warning を info に、検査をやめる) | 1.x (D4) | 1.x | — |
| warning・info を足す | 1.x (D4) | 1.x | — |
| メッセージの文面を変える | 1.x | 1.x | — |
| キー・値・コレクションを改名する、消す | **2.0** | **2.0** | **2.0** (規範キー) |
| 任意のキーを必須にする、既定値を変える、意味を変える | **2.0** | **2.0** | **2.0** |
| 型・値域を狭める | **2.0** | **2.0** | **2.0** |
| 検査を強める (warning を error に)、1.0 で書けた YAML を落とす新しい error | **2.0** (D3) | **2.0** | — |
| 糖衣構文・`meta` の受け付け (D7) をやめる | **2.0** | **2.0** | — |

- マイナーバージョン (1.1 など) で足してよいもの: キー・値・コレクション・warning・info、検査の緩和。パッチバージョン (1.0.1 など) では、バグの修正 (D3) と実装の修正だけを行い、キーと warning は足さない
- この表は、いつ足せるかの決まりである。ほかの ADR が個別に決めたこと (例: ADR-0003 の「推奨外の `role` に warning を出さない」) は上書きしない。
  そうした決定を変えて warning を足すには、その ADR を改訂する ADR が要る

### D3. 新しい error を足してよいのは、1.x で足したキー・値に付くものだけ (ユーザー決定)

- 1.x で足したキーや値の検査は、error にしてよい (そのキーを書いた YAML は、それまで存在しなかった)。キーを足したのと別のマイナーバージョン (1.1 で足したキーに 1.2 で検査を足す) でもよい
- 1.0 で書けた YAML を落とす新しい error は 2.0 まで待つ。それまでは warning として足す (D2)
- 1 つ前のバージョンで warning として予告し、次のバージョンで error にする方式は採らない。1.x の中で warning を error に強めることになる
- **バグの修正**: 「この条件は error」と、Accepted の ADR の本文、CLAUDE.md の「バリデーション項目」の表、`docs/reference/validation.ja.md` のどれかに書いてあったのに、
  実装が見逃していた誤りを error にするのは、新しい error に当たらない。約束どおりに実装を直すだけである。パッチバージョンでも直してよい。
  リリースノートでは「バグの修正」として、直した条件と書いてあった場所 (ADR など) を添える。どこにも書いていなかった検査は、新しい error として扱う
- **1.x で足したキーの検査の書き方** (既存の YAML に効かせない):
  - 新しいフィールドは任意で足す (`T | None = None`)。既定値で今までの意味を変えない
  - 型 (値域・Literal・Tagged Union) と `field_validator`: そのキーを書いたときだけ効くので、そのままでよい。値が `None` なら見ない
  - `model_validator` と validator の横断の検査: 新しいキーを含むエンティティだけを対象にする
  - 既存のキーどうしの組み合わせの誤りを 1.x で新しく見つけたときは、warning にとどめる
  - 1.0 の valid の fixture を、1.x の mlndl で流しても error が増えないことをテストで守る

### D4. `--strict` が約束するのは「そのバージョンの warning を error にする」ことだけ (ユーザー決定)

- 1.x のマイナーバージョンでは warning を足すので、`--strict` で通っていた YAML が新しいバージョンで止まることがある。逆に warning を info に下げると、止まっていた YAML が通るようになる
- `docs/reference/validation.ja.md` に、CI での使い方を書く:
  > `--strict` は、そのバージョンの warning をすべて error にします。1.x のマイナーバージョンで warning が増えることがあるので、CI では `mlndl==1.1.*` のようにマイナーバージョンを固定してください。
  > 上げるときは、まず `--strict` なしで流して新しい warning を確かめ、直してから `--strict` に戻します。パッチバージョンで warning が増えることはありません
- 1.x のリリースノートは次の節に分ける (空の節は書かない)。各マイナーバージョンの先頭に、`--strict` で止まりうる変更の有無を 1 行で書く
  1. **バグの修正**: D3 のバグの修正 (今まで通っていた YAML が error になりうる。直した条件と書いてあった場所を添える)
  2. **追加**: 足したキー・値・コレクション、エクスポーターの出力に足したキー
  3. **検査の追加**: 足した warning・info、1.x で足したキーに付く error
  4. **緩和**: 緩めた検査 (error から warning、warning から info、やめた検査)、必須から任意にしたキー、広げた型 (Python のモデルの型が変わることを添える)
  5. **内部**: `derive.py`・`schema.json` など参考の部分の変更
- warning にコードを付けて個別に抑える仕組み (`--ignore` など) は 1.x で足す (加算)。1.0 の前には作らない

### D5. `ndl_version` は必須。YAML より古い mlndl はバージョンの違いを知らせて止まる (ユーザー決定)

- **定義**: `ndl_version` は、**この YAML を読むのに要る、最も古い mlndl のバージョン**を表す。書いたときの mlndl のバージョンではない。
  1.1 で足したキーを 1 つでも使ったら `"1.1"` と書く。使わなければ `"1.0"` のままでよい
- **必須**: 1.0 から必須にする。書かなければ error:
  > ndl_version は必須です。この YAML を読むのに要る、最も古い mlndl のバージョンを、先頭に ndl_version: "1.0" のように書いてください。書いておくと、古い mlndl で読んだときにバージョンの違いを知らせて止まります (ADR-0027)
- **書式**: `"<メジャー>.<マイナー>"` の**文字列** (`^\d+\.\d+$`。パッチは書かない)。引用符なしで数値として書いたら、専用の error:
  > ndl_version は文字列です。"1.0" のように引用符で囲んで書いてください。引用符がないと、YAML は 1.10 を数の 1.1 と読みます (ADR-0027)
- メジャーが 1 でなければ、今までどおり error
- **比べ方**: メジャーとマイナーを数の組として比べる (`"1.10"` は `"1.9"` より新しい)
  - YAML のマイナーが mlndl の `LANGUAGE_VERSION` 以下なら、読む
  - YAML のマイナーが `LANGUAGE_VERSION` より新しければ、未知のキーの error より先に、この 1 本の error だけを出して止める:
    > この YAML は ndl_version 1.2 以上を必要としますが、この mlndl (1.1.0) が読めるのは ndl_version 1.1 までです。mlndl を更新してください。1.2 で足したキーを使っていないなら、ndl_version を下げても読めます (ADR-0027)
- **例外**: バージョンの違いは `UnsupportedVersionError` (`ValueError` のサブクラス) で知らせ、公開の API に入れる。`except ValueError` で捕まえていた利用者のコードは壊れない
- **実装の指針**: `ndl_version` の検査 (必須・書式・比べる) は parser で、YAML を辞書にした直後、pydantic のモデルに渡す前に行う。
  CLI は、この例外には「スキーマの段階で見つかった誤り」の注記を付けない
- 未知のキーを warning にして読み進める方式は採らない。中間フォーマットとして、下流のツールが情報の欠けたトポロジーのまま気づかずに動くのを避ける
- **マイナーバージョンを上げる条件**: 書けるものを広げたとき (キー・値・コレクションを足す、必須のキーを任意にする、受け付ける型を広げる)。検査だけを変えたときは上げない
- `ndl_version: "1.0"` のまま 1.1 のキーを書いた YAML は、書き手の誤りとして今までどおり未知のキーの error になる (試し書き C3)。メッセージに「1.1 のキーなら ndl_version を上げる」を添えるかは実装のときに決める

### D6. パッケージのバージョンと言語のバージョン

- パッケージ (pip) のバージョンの `メジャー.マイナー` は、その実装が読める最も新しい `ndl_version` と同じにする。パッチは実装の修正
  - 例: mlndl 1.0.3 は ndl_version 1.0 を読む。mlndl 1.1.0 は 1.0 と 1.1 を読む。mlndl 2.0.0 は 1.x を読まない
- `mlndl.LANGUAGE_VERSION` (例: `"1.1"`) と `mlndl.__version__` (例: `"1.1.0"`) を公開する
- エクスポーターの出力のルートに `meta` を置く (規範キー):
  ```json
  {"meta": {"ndl_version": "1.0", "mlndl_version": "1.1.0"}, "nodes": [...], "edges": [...]}
  ```
  - `ndl_version`: 入力の YAML の値そのまま
  - `mlndl_version`: 出力した mlndl の `__version__`
  - Python 以外の下流のツールも、出した mlndl のバージョンを読んで「対応していないバージョン」を表示できる
- 1.0 のリリースでパッケージを `1.0.0` にする (今は `0.1.0`)

### D7. 1.0 の後も残す形

- **`attaches_to: <node id>` の文字列の糖衣構文** (`layer1.nodes` だけ。`{node: <id>}` と同じ意味)。やめるのは 2.0
- **`meta` は未知のキーを受け付ける**。未知のキーを受け付けるのは `meta` だけで、ほかの区画は 1.x の間 `extra="forbid"` のまま (広げるなら区画ごとに ADR で決める)
  - 下流のツールは、自分の名前 (`ndl-viz` など) をキーにして設定を置く (`meta.ndl-viz.layout` など)。mlndl が `meta` に足すキーは下線区切りの名前 (今は `name` / `network_types` など) にし、ハイフンを含む名前は下流のツールに空けておく
  - 入力の `meta` はエクスポーターの出力に流れない (出力の `meta` は D6 のバージョンだけ)。下流のツールが自分の設定を使うなら YAML を読む
- **旧形式の「移動先を示す error」** (ADR-0010・0020・0022〜0026、ADR-0028 で入れるもの) は 2.0 まで残す。消すのは 2.0 で、そのときに改めて決める

### D8. 利用者向けの書き方

`docs/reference/README.ja.md` に「互換の約束」の節を足す。「前方互換」「後方互換」の語は、指す向きが読み手によって逆になるので使わず、向きをそのまま書く。

> - 新しい mlndl は、同じメジャーバージョンの古い YAML を読めます。1.0 で error にならなかった YAML は、1.x のどのバージョンでも error になりません (文書どおりに直したバグの修正を除く)。warning は増えることがあります
> - 古い mlndl は、新しいバージョンの YAML を読めません。YAML の `ndl_version` が mlndl より新しければ、バージョンの違いを知らせて止まります
> - 1.x で足すのは、任意のキー・値、緩めた検査、warning です。名前・形・必須かどうか・既定値・意味を変えるのは 2.0 です
> - `--strict` は、そのバージョンの warning を error にします。CI では mlndl のマイナーバージョンを固定してください
> - **規範** (この約束の対象): YAML の書き方、検査の結果と severity、Python の公開の API、CLI、エクスポーターの規範キー。**参考** (1.x でも変わる): Python のモデルの中身、`derive.py`、メッセージの文面、`schema.json`

用語は次にそろえる: 規範 / 参考 / 規範キー / 未知のキー (その mlndl が知らないキー) / バージョン / メジャー / マイナー / パッチ / 破壊的な変更 (1.0 で正しかった YAML・コード・下流のツールが動かなくなる変更)。「版」は使わない。

## Consequences

**良い影響:**
- 「1.0 の前に直さないと後で直せないもの」を、D2 の表で判定できる
- 古い mlndl で新しい YAML を読んだとき、原因 (バージョンの違い) がすぐ分かる
- 下流のツールは、エクスポーターの規範キーと出力の `meta` に頼れる

**悪い影響 / トレードオフ:**
- 1.x で誤りを見つける新しい検査を思いついても、1.0 で書けた YAML を落とすものは 2.0 まで warning にとどまる
- `--strict` の利用者は、マイナーバージョンを上げるたびに新しい warning を見直す
- `ndl_version` を必須にするので、書いていない YAML は 1.0 で error になる (今の examples と fixtures は全部書いている。テストの中の YAML には書いていないものがある)
- Python の利用者がモデルの属性に頼ると、1.x で型が広がることがある (モデルは参考)
- eve-lab-builder の規範キーは推定で、確かめたあとに直す

**1.0 の前に必須になるもの** (改名・既定値・意味の変更は D2 で 2.0 になるため。この約束の対象外として 1.0 の前に行う)。決めるのは **ADR-0028「1.0 の前の型と名前の直し」** で、ここでは一覧だけを置く:

| 対象 | 今 | 1.0 での形 (Pass C の 5 エージェントの推奨。ADR-0028 で決める) |
|---|---|---|
| `layer1.lag` | 単数 | `lags` (旧名は移動先を示す error) |
| `layer2.vxlan` | 単数 | `vxlans` (Pass C は全員一致。`vnis` は番号のリストに見え、`vnis[].vni` と語が重なる) |
| IS-IS の `level` | `level-1` / `level-2` / `level-all` (RFC 9130 の YANG) | `level_1` / `level_2` / `level_all` (区切りだけを変える。`level_1_2` は合成の値が 1 つだけ混ざる) |
| `L2VxLAN.vteps` | 既定値 `[]`、空を validator で error | `min_length=1` (ADR-0014 の改訂) |
| `BgpSession.address_families` | 既定値 `[]` (空の意味が決まっていない) | `min_length=1`。既定値は持たない (ADR-0010 の改訂。`["ipv4_unicast"]` は 1.0 で固まり、EVPN の書き忘れと区別できない) |
| 既定値の一覧 | `LacpConfig.mode = "active"`・`min_links = 1`、`route_reflector_client = False` など | 見直して一覧にする |

**影響を受けるコンポーネント (この ADR だけの分):**
- パーサー: `src/mlndl/parser.py` (`ndl_version` の検査を pydantic に渡す前に。`UnsupportedVersionError`)
- スキーマ: `src/mlndl/schema/topology.py` (`ndl_version` の既定値を外す)
- CLI: `src/mlndl/__main__.py` (バージョンの違いの例外には注記を付けない)
- `src/mlndl/__init__.py` (`LANGUAGE_VERSION`・`UnsupportedVersionError` を公開)、`pyproject.toml` (1.0 のリリースで `1.0.0`)
- エクスポーター: `src/mlndl/exporter/cytoscape.py` (ルートの `meta`)
- テスト: `ndl_version` を書いていないテストの中の YAML、バージョンの検査のテスト、1.0 の fixture を回帰のために固定すること
- 文書: `docs/reference/README.ja.md` (D8)、`validation.ja.md` (D4)、`docs/exporter-cytoscape.md` (「規範」の列、ルートの `meta`、`source` / `target` に向きがないこと)、CLAUDE.md §3 (サンプルのコードも)
- 下流: ndl-viz (未知のキー・値を無視することの確認。出力の `meta` の表示は任意)

**改訂の注記** (2026-11-19 の実装で各 ADR に足した):
- ADR-0002 の末尾: 「**改訂 ([ADR-0027](0027-compatibility-promise.md), 2026-11-18)**: D8 の severity (error / warning / info) の意味を 1.0 の約束に入れた。severity を上げる・下げるときの条件は ADR-0027 D2・D3 に従う」
- ADR-0015 の末尾: 「**改訂 ([ADR-0027](0027-compatibility-promise.md))**: `Ref` を公開の API に入れた。`Ref` の検査は 1.x の間、同じ条件で同じ結果 (文面は除く) を返す。新しいコレクションへの `Ref` を足すのは加算」
- ADR-0025 の末尾: 「**確認 ([ADR-0027](0027-compatibility-promise.md) D7)**: 1.0 の後も「読み替えて warning」は既定にしない。移動先を示す error は 2.0 まで残す」
- ADR-0010 の移行の改訂の末尾: 「**→ [ADR-0027](0027-compatibility-promise.md)** で、1.x で許す変更と 2.0 が要る変更を決めた」

## Alternatives Considered

- **`ndl_version` を書かなければ 1.0 とみなし、warning で促す** (dsl-designer の Pass A): 却下 (ユーザー決定) — docs と実装の食い違いを残す。必須にしておけば、D5 のバージョンの比較がいつも働く
- **古い mlndl は未知のキーを warning にして読み進める** (network-tech-reviewer の Pass A): 却下 (ユーザー決定) — 下流のツールが情報の欠けたまま動く。`meta` だけが未知のキーを受け付けるという境界も崩れる
- **今のまま、未知のキーの error に任せる**: 却下 — バージョンの違いか書き損じかを利用者が区別できない
- **新しい error は 1 つ前のバージョンで warning で予告すれば 1.x で足せる** (network-tech-reviewer): 却下 (ユーザー決定) — 1.x の中で warning を error に強めることになる
- **新しい error は 1.x で一切足さない** (dsl-designer・example-author の Pass A): 採らない — 1.x で足したキーの検査まで warning に縛る理由がない
- **1.0 の前に warning にコードを付け、個別に抑えられるようにする** (network-tech-reviewer): 1.x で足す (ユーザー決定) — 後から足しても破壊的ではない
- **エクスポーターの出力をすべて規範 / すべて参考にする**: 却下 — 前者は ADR-0023 の `lags[]`・ADR-0026 の `node_vlans` のような追加が 1.x で止まる。後者は ndl-viz・eve-lab-builder が頼るキーが 1.x で消えうる
- **`derive.py` のうち、エクスポーターが使う関数を 1.0 の公開の API に入れる** (dsl-designer の Pass B): 採らない — 下流のツールは derive を呼ばない。公開の API は後から足せるが、入れると減らせない
- **区画の中の pydantic のモデル (属性と型) を規範にする**: 採らない — 1.x でキーを足したり必須を任意にしたりするたびに 2.0 が要ることになり、D2 の加算が封じられる
- **バージョンの違いを pydantic の `ValidationError` で知らせる**: 採らない — スキーマの誤りと混ざり、CLI でも分けにくい。`ValueError` のサブクラスにすれば今のコードも壊れない
- **出力の `meta.ndl_version` に、出した mlndl の `LANGUAGE_VERSION` を入れる** (Pass B の初版): 採らない — `mlndl_version` から分かる。入力の YAML の値のほうが情報が増える (network-tech-reviewer・spec-architect)
- **リンクの端のキーを `a` / `b` にする** (`source_if` → `a_if` など): 採らない (ユーザー決定) — `source` / `target` は Cytoscape.js の必須のキーで、向きの意味がないことは ADR-0006 で決めてある。名前を変えると ndl-viz が直しになる
- **入力の改名を 1.x で、新しい名前を足して古い名前を warning にする**: 却下 — 同じ意味を 2 つの名前で書ける形を作らない (ADR-0025)
- **名前の直しと型の直しをこの ADR で決める**: 採らない — この ADR は「1.x の間、何を変えてよいか」の決まりで、具体的な名前・型の変更は別の ADR (ADR-0028) で決める。混ぜると履歴から「約束を変えたのか、書き方を変えたのか」が読めない (spec-architect・dsl-designer)

## Pass A との差分

Pass C の 5 エージェントは drafts/0027 を読まずに評価メモから再設計し、骨子 (D1〜D8) は改訂 1 と同じ結論になった。変わった点:

- **D1**: 公開の API を具体にした (`MLNDLTopology` の最上位の属性、`resolve()` が返すものの約束、`UnsupportedVersionError`)。CLI の出力の行頭を規範に。
  規範キーの一覧を ndl-viz のソースで確かめ直し、`gateway_redundancy`・VLAN の端点の `resolution` / `candidates` / `outside_svi_subnet`・`lag_bundle` の `member_count` / `label`・VTEP の `shared_with`・`labels.site` を規範に上げた (network-tech-reviewer)。
  eve-lab-builder の分は推定と明記した。エッジの `source` / `target` に向きがないことを明記した (ユーザー)
- **D2**: 3 つの読み手 (YAML の書き手・Python の利用者・下流のツール) ごとの表にした (dsl-designer)。パッチバージョンではキーと warning を足さない (network-tech-reviewer)
- **D3**: バグの修正の判定基準を「Accepted の ADR の本文・CLAUDE.md の表・`validation.ja.md`」にし、パッチでも直せるとした (spec-architect)。1.0 の fixture を回帰のテストで固定する (dsl-designer)
- **D4**: CI での使い方の文案と、リリースノートの 5 つの節 (network-tech-reviewer・spec-architect)
- **D5**: `UnsupportedVersionError` (dsl-designer)。バージョンの違いの error に「キーを使っていないなら下げても読める」を添える (example-author の P2)
- **D6**: 出力の `meta.ndl_version` は入力の YAML の値に (network-tech-reviewer・spec-architect)
- **D7**: `meta` の名前の空け方 (mlndl は下線区切り、下流のツールはハイフンを含む自分の名前。example-author の P3)
- **1.0 の前に必須になるもの**: ADR-0028 で決めることにし、ここは一覧だけに (spec-architect・dsl-designer)。名前の推奨を `vxlans`・`level_all` にした (Pass C の全員。linguist は Pass B の `vnis`・`level_1_2` を撤回)
- **用語**: 「規範」と ADR-0005 の「注釈側の構成子」が別の概念であることを明記した (linguist)

## References

- 棚卸し: [evaluations/release-1.0/inventory.md](evaluations/release-1.0/inventory.md)
- 評価メモ: [evaluations/adr0027/evaluation.md](evaluations/adr0027/evaluation.md)
- 試し書き: `evaluations/adr0027/` (C1〜C6) と `recommendation.md`、`passb/` (B1〜B6)、`passc/` (P1〜P4b)
- 関連 ADR: ADR-0002 D8、ADR-0003、ADR-0005 D4、ADR-0006、ADR-0010 (移行の改訂)、ADR-0015、ADR-0025
- 比べたもの: Terraform の `required_version`、Kubernetes の未知のフィールドの扱い、protobuf の未知のフィールド、yamllint / ansible-lint / ruff のルールのコードと個別の抑止、Keep a Changelog
- 下流: ndl-viz の `src/types/topology.ts` (エクスポーターの出力を読む型)
