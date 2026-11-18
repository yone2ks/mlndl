# ADR-0027: 互換の約束 — 1.0 の後、1.x で許す変更と 2.0 が要る変更

- **Status**: Draft (改訂 1。2026-11-18 の横断評価 [evaluations/adr0027/evaluation.md](../evaluations/adr0027/evaluation.md) を反映)
- **Date**: 2026-11-18
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー (D3・D4・D5 の 4 つの論点)
- **Pass**: A (5 エージェントの評価を 1 回取り、割れた 4 つの論点をユーザーが決めた。改訂 1 は Pass B の指摘の反映)
- **Amends**: ADR-0010 の移行の改訂 (「1.0 の後は破壊的な変更にメジャーバージョンの更新を必須とする」の中身を決める)、ADR-0002 D8 (severity の意味を約束に入れる)、
  ADR-0015 (`Ref` を公開の API に入れる)、ADR-0025 (旧形式の error を 2.0 まで残す)、CLAUDE.md §3 (`ndl_version`)
- **関連**: ADR-0003 (推奨外の `role` に warning を出さない)、[1.0 に向けた棚卸し](../evaluations/release-1.0/inventory.md)

## Context

最初のリリースは 1.0 で、1.0 の後は破壊的な変更にメジャーバージョンの更新が要る (ADR-0010 の移行の改訂)。ところが、何が「破壊的な変更」かは決めていない。
1.0 に向けた棚卸し (2026-11-18) では仮の物差しで項目を振り分けたが、その物差しを約束として書く必要がある。今の実装には次の穴がある (2026-11-18 に確かめた)。

- `ndl_version` は CLAUDE.md §3・`docs/reference/README.ja.md`・`validation.ja.md` で「必須」とあるが、実装は既定値 `"1.0"` を持ち、書かなくても通る (`src/mlndl/schema/topology.py:27`・`:40`。試し書き C1)
- 全モデルが `extra="forbid"` なので、1.1 で足したキーを 1.0 の mlndl は `Extra inputs are not permitted` で拒む。`ndl_version: "1.1"` と書いてもバージョンの違いは知らせず、利用者は書き損じと区別できない (試し書き C2・C3・B2)
- 引用符なしの `ndl_version: 1.10` は、YAML が数値の 1.1 と読み、`Input should be a valid string [input_value=1.1]` という分かりにくい error になる
- パッケージのバージョンは `0.1.0` で、`ndl_version` との関係が決まっていない
- 検査を足すこと・緩めることが互換にどう効くか、`--strict` で CI を回す利用者に何を約束するかが決まっていない

## Decision

この ADR の「規範」は、変えるのにメジャーバージョンの更新 (2.0) が要るもの、「参考」(informative) は 1.x で変えてよいものを指す。

### D1. 約束の範囲

| 対象 | 扱い |
|---|---|
| YAML の書き方 (キー・形・必須 / 任意・値域・既定値・意味) | **規範** |
| 検査の結果 (どの YAML が error になるか) と severity の意味 (ADR-0002 D8) | **規範**。D3 の範囲で 1.x でも変わる |
| Python の公開の API: `parse` / `parse_file` / `validate` / `validate_all` の呼び方・戻り値・例外の型、`ValidationResult` (`errors` / `warnings` / `notes`) と `ValidationError` (`path` / `message` / `severity`)、`MLNDLTopology.index()` / `resolve()`、`IdIndex`、`Ref`、`LANGUAGE_VERSION` | **規範** |
| CLI の `validate` / `export` / `schema`、`--strict` の意味 (D4)、終了コード (error があれば 1、なければ 0) | **規範** |
| エクスポーター (Cytoscape の JSON) の**規範キー**: 要素の `type` の値、種類ごとのキーと埋め込みのリストの中のキー、ルートの `meta` (D6) | **規範**。キー・値を足すのは 1.x でよい。消す・改名する・意味を変えるのは 2.0 |
| 規範キー以外の出力、pydantic のモデルの属性と型・`model_dump()` の形、`derive.py` の関数、メッセージの文面とパスの書き方、`docs/reference/schema.json` (生成物) | **参考** |

- **規範キー**の一覧は、ndl-viz が読むキーと、eve-lab-builder が機器と配線を作るのに要るキーから決めた (network-tech-reviewer が ndl-viz のソースから洗い出した。評価メモ)。
  `docs/exporter-cytoscape.md` の表に「規範」の列を足して示す。印は「そのキーが同じ条件で出続ける」ことを約束し、値の書式 (`description` の中身など) までは約束しない
  - 要素の `type`: ノードは `node` / `vlan` / `l2vni` / `l3vni` / `bridge` / `ethernet_segment`、エッジは `link` / `attaches_to` / `vlan_member` / `routing_neighbor` / `tunnel` / `lag_bundle`
  - 参考のままのキーの例: `l3_interfaces[].roles` (ndl-viz は読まない)、`vlan_member` の端点の `candidates` / `outside_svi_subnet`、機器ノードの `vrfs[]` (ほかのキーから導ける)
- 下流のツール (ndl-viz・eve-lab-builder) は、エクスポーターの出力の**未知のキー・未知の値 (`type` など)** を無視する。1.x でキー・値が足されても止まらないため
- Python の利用者は、モデルの属性ではなく公開の関数とエクスポーターの出力に頼る。モデルを比べるなら `model_dump(exclude_unset=True)` を勧める (1.x でフィールドが足されるため)。
  `match` で分岐するなら `case _:` を置く (1.x で値・分岐が足されるため)
- `derive.py` の関数は 1.0 では公開の API に入れない。下流のツールはエクスポーターの出力を読み、derive を直接呼ばない。必要になれば 1.x で加算する (一度入れると減らせない)
- エクスポーターの出力のキーを改名したいときは、新しいキーを足し、古いキーは 2.0 まで残す。入力 (YAML) では同じことをしない (同じ意味を 2 つの名前で書ける形は作らない。ADR-0025)

### D2. 1.x で許す変更と、2.0 が要る変更

この約束は 1.0 のリリースから効く。1.0 を出す前の破壊的な変更 (下の「1.0 の前に必須になるもの」) は、この約束の対象外である。

| 変更 | 1.x |
|---|---|
| 任意のキー・コレクション・Literal の値・Tagged Union の分岐を足す | 許す |
| 受け付ける型を広げる (`X` → `X \| list[X]`)、値域を広げる | 許す (*) |
| 必須のキーを任意にする | 許す (*) |
| 検査を緩める (error を warning に、warning を info に、検査をやめる) | 許す (D4) |
| warning・info を足す | 許す (D4) |
| メッセージの文面を変える | 許す |
| エクスポーターの出力にキー・値を足す | 許す |
| キー・値・コレクションを改名する、消す | **2.0** |
| 任意のキーを必須にする、既定値を変える、意味を変える | **2.0** |
| 型・値域を狭める | **2.0** |
| 検査を強める (warning を error に)、1.0 で書けた YAML を落とす新しい error | **2.0** (D3) |
| 糖衣構文・`meta` の受け付け (D7) をやめる | **2.0** |

(*) YAML の書き手にとっては破壊的でない。ただし pydantic のモデルの属性の型は変わりうる (`str` → `str | None` など。モデルは参考)。
エクスポーターの規範キーは、同じ条件で同じ形のまま出し続ける (省けるようになったキーも、出力では今までどおり出す)。

ほかの ADR が「〜には warning を出さない」と決めているもの (例: ADR-0003 の推奨外の `role`) に warning を足すときは、互換の約束とは別に、その ADR の改訂が要る。

### D3. 新しい error を足してよいのは、1.x で足したキー・値に付くものだけ (ユーザー決定)

- 1.x で足したキーや値の検査は、error にしてよい (そのキーを書いた YAML は、それまで存在しなかった)。キーを足したのと別のマイナーバージョン (1.1 で足したキーに 1.2 で検査を足す) でもよい
- 1.0 で書けた YAML を落とす新しい error は 2.0 まで待つ。それまでは warning として足す (D2)
- **バグの修正**: `docs/reference/validation.ja.md` の表や ADR の本文に error と書いてあったのに、実装が見逃していた誤りを error にするのは、新しい error に当たらない。
  約束どおりに実装を直すだけである。リリースノートでは「バグの修正」として、新しい warning とは別の節に書く。書いていなかった検査は、新しい error として扱う
- **実装の指針**: 1.x で足したキーの検査が、そのキーを書いていない YAML に効かないように書く
  - 型 (値域・Literal・Tagged Union) と `field_validator`: そのキーを書いたときだけ効くので、そのままでよい
  - `model_validator` と validator の横断の検査: 新しいキーを含むエンティティだけを対象にする (値が `None` なら見ない)
  - 既存のキーどうしの組み合わせの誤りを 1.x で新しく見つけたときは、warning にとどめる
- 1 つ前のバージョンで warning として予告し、次のバージョンで error にする方式は採らない。1.x の中で warning を error に強めることになり、D2 と食い違う

### D4. `--strict` が約束するのは「そのバージョンの warning を error にする」ことだけ (ユーザー決定)

- 1.x では warning を足すので、`--strict` で通っていた YAML が新しいバージョンで止まることがある。逆に warning を info に下げると、止まっていた YAML が通るようになる
- `--strict` で CI を回すなら、mlndl のマイナーバージョンを固定し、上げるときに見直す運用にする。これを `docs/reference/validation.ja.md` に書く
- 1.x のリリースノートには、足した warning・info に下げた warning・バグの修正 (D3) を、それぞれ節を分けて書く
- warning にコードを付けて個別に抑える仕組み (`--ignore` など) は 1.x で足す (加算)。1.0 の前には作らない

### D5. `ndl_version` は必須。YAML より古い mlndl はバージョンの違いを知らせて止まる (ユーザー決定)

- 1.0 から `ndl_version` を必須にする。書かなければ error:
  > ndl_version は必須です。この YAML がどのバージョンの MLNDL で書かれているかを示すため、先頭に `ndl_version: "1.0"` を書いてください (ADR-0027)
- **書式**: `"<メジャー>.<マイナー>"` の**文字列** (`^\d+\.\d+$`。パッチは書かない)。引用符なしで数値として書いたら、専用の error にする:
  > ndl_version は "1.0" のように引用符で囲んで書いてください。引用符がないと YAML は 1.10 を 1.1 として読みます (ADR-0027)
- メジャーが 1 でなければ、今までどおり error
- **定義**: YAML の `ndl_version` は、**この YAML を読むのに要る、最も古い mlndl のバージョン**を表す。書いたときの mlndl のバージョンではない。
  1.1 で足したキーを 1 つでも使ったら `"1.1"` と書く。使わなければ `"1.0"` のままでよい
- **比べ方**: メジャーとマイナーを数として比べる (`"1.10"` は `"1.9"` より新しい)
  - YAML のマイナーが mlndl の知るもの以下なら、読む
  - YAML のマイナーが mlndl の知るものより新しければ、未知のキーの error より先に、この 1 本の error だけを出して止める:
    > この YAML は ndl_version 1.1 以上を必要としますが、この mlndl (1.0.3) が読めるのは ndl_version 1.0 までです。mlndl を更新してください (ADR-0027)
- **実装の指針**: バージョンの比較は parser で、YAML を辞書にした直後、pydantic のモデルに渡す前に行い、専用の例外にする。CLI は、この例外には「スキーマの段階で見つかった誤り」の注記を付けない
- 未知のキーを warning にして読み進める方式は採らない。中間フォーマットとして、下流のツールが情報の欠けたトポロジーのまま気づかずに動くのを避ける
- マイナーバージョンを上げるのは、書けるものを広げたとき (キー・値・コレクションを足す、必須のキーを任意にする、受け付ける型を広げる)。検査だけを変えたときは上げない
- `ndl_version: "1.0"` のまま 1.1 のキーを書いた YAML は、書き手の誤りとして今までどおり未知のキーの error になる (試し書き C3)。メッセージに「1.1 のキーなら `ndl_version` を上げる」を添えるかは実装のときに決める

### D6. パッケージのバージョンと言語のバージョン

- パッケージ (pip) のバージョンの `メジャー.マイナー` は、その実装が読める最も新しい `ndl_version` と同じにする。パッチは実装の修正
  - 例: mlndl 1.0.3 は ndl_version 1.0 を読む。mlndl 1.1.0 は 1.0 と 1.1 を読む。mlndl 2.0.0 は 1.x を読まない
- `mlndl.LANGUAGE_VERSION` (例: `"1.0"`) と `mlndl.__version__` (例: `"1.0.3"`) を公開する
- エクスポーターの出力のルートに `meta: {ndl_version: <LANGUAGE_VERSION>, mlndl_version: <__version__>}` を置く (規範キー)。
  Python 以外の下流のツールも、出した mlndl のバージョンを読んで「対応していないバージョン」を表示できる
- 1.0 のリリースでパッケージを `1.0.0` にする (今は `0.1.0`)

### D7. 1.0 の後も残す形

- **`attaches_to: <node id>` の文字列の糖衣構文** (`layer1.nodes` だけ。`{node: <id>}` と同じ意味)。やめるのは 2.0
- **`meta` は未知のキーを受け付ける**。下流のツールは `meta.<ツール名>:` に自分の設定を置ける。未知のキーを受け付けるのは `meta` だけで、ほかのモデルは 1.x の間 `extra="forbid"` のまま (広げるなら区画ごとに ADR で決める)。
  入力の `meta` はエクスポーターの出力には流れない (出力の `meta` は D6 のバージョンだけ)。下流のツールが自分の設定を使うなら YAML を読む
- **旧形式の「移動先を示す error」** (ADR-0010・0020・0022〜0026 で入れたもの) は 2.0 まで残す。消すのは 2.0 で、そのときに改めて決める

### D8. 利用者向けの書き方

`docs/reference/README.ja.md` に「互換の約束」の節を足す。「前方互換」「後方互換」の語は、指す向きが読み手によって逆になるので使わず、向きをそのまま書く (linguist)。

> - 新しい mlndl は、同じメジャーバージョンの古い YAML を読めます。2.0 の mlndl は 1.x の YAML を読みません
> - 古い mlndl は、新しいバージョンの YAML を読めません。YAML の `ndl_version` が mlndl より新しければ、バージョンの違いを知らせて止まります
> - 1.x で足すのは、任意のキー・値、緩めた検査、warning です。名前・形・必須かどうか・既定値・意味を変えるのは 2.0 です
> - `--strict` は、そのバージョンの warning を error にします。1.x で warning が増えることがあるので、CI では mlndl のバージョンを固定してください

## Consequences

**良い影響:**
- 「1.0 の前に直さないと後で直せないもの」を、この表で判定できる
- 古い mlndl で新しい YAML を読んだとき、原因 (バージョンの違い) がすぐ分かる
- 下流のツールは、エクスポーターの規範キーと出力の `meta` に頼れる

**悪い影響 / トレードオフ:**
- 1.x で誤りを見つける新しい検査を思いついても、1.0 で書けた YAML を落とすものは 2.0 まで warning にとどまる
- `--strict` の利用者は、マイナーバージョンを上げるたびに新しい warning を見直す
- `ndl_version` を必須にするので、書いていない YAML は 1.0 で error になる (今の examples と fixtures は全部書いている。テストの中の YAML には書いていないものがある)
- Python の利用者がモデルの属性に頼ると、1.x で型が広がることがある (モデルは参考)

**この ADR の結果、1.0 の前に必須になるもの** (改名・既定値・意味の変更は D2 で 2.0 になるため。D2 の前の 1 文のとおり、この約束の対象外として 1.0 の前に行う):
- 名前の直し: `layer1.lag` → `lags`、`layer2.vxlan` → `vxlans` (または `vnis`)、IS-IS の `level-1` / `level-2` / `level-all` → 下線区切り。旧名は移動先を示す error。
  新しい名前は名前の直しの ADR で決める (評価メモの「残る論点」1)
- `L2VxLAN.vteps` を `min_length=1` に (今は既定値 `[]` で、空を validator で error にしている)
- `BgpSession.address_families` を `min_length=1` に (空を許さない。既定値は持たない。既定値 `["ipv4_unicast"]` は 1.0 で固まり、EVPN の書き忘れと区別できなくなるので採らない)
- 既定値 (`LacpConfig.mode = "active"`・`min_links = 1`、`route_reflector_client = False` など) を見直して一覧にする
- ADR-0010 (`address_families`) と ADR-0014 (`vteps`) の改訂は、これらを決める ADR で行う

**影響を受けるコンポーネント (この ADR だけの分):**
- パーサー: `src/mlndl/parser.py` (バージョンの比較を pydantic に渡す前に。専用の例外)
- スキーマ: `src/mlndl/schema/topology.py` (`ndl_version` の既定値を外す、書式)
- CLI: `src/mlndl/__main__.py` (バージョンの違いの例外には注記を付けない)
- `src/mlndl/__init__.py` (`LANGUAGE_VERSION`)、`pyproject.toml` (1.0 のリリースで `1.0.0`)
- エクスポーター: `src/mlndl/exporter/cytoscape.py` (ルートの `meta`)
- テスト: `ndl_version` を書いていないテストの中の YAML、バージョンの比較のテスト
- 文書: `docs/reference/README.ja.md` (D8)、`validation.ja.md` (D4)、`docs/exporter-cytoscape.md` (「規範」の列とルートの `meta`)、CLAUDE.md §3
- 下流: ndl-viz (未知のキー・値を無視することの確認、出力の `meta` の表示は任意)

## Alternatives Considered

- **`ndl_version` を書かなければ 1.0 とみなし、warning で促す** (dsl-designer): 却下 (ユーザー決定) — docs と実装の食い違いを残す。必須にしておけば、D5 のバージョンの比較がいつも働く
- **古い mlndl は未知のキーを warning にして読み進める** (network-tech-reviewer): 却下 (ユーザー決定) — 下流のツールが情報の欠けたまま動く。`meta` だけが未知のキーを受け付けるという境界も崩れる
- **今のまま、未知のキーの error に任せる**: 却下 — バージョンの違いか書き損じかを利用者が区別できない
- **新しい error は 1 つ前のバージョンで warning で予告すれば 1.x で足せる** (network-tech-reviewer): 却下 (ユーザー決定) — 1.x の中で warning を error に強めることになる
- **新しい error は 1.x で一切足さない** (dsl-designer・example-author): 採らない — 1.x で足したキーの検査まで warning に縛る理由がない
- **1.0 の前に warning にコードを付け、個別に抑えられるようにする** (network-tech-reviewer): 1.x で足す (ユーザー決定) — 後から足しても破壊的ではない
- **エクスポーターの出力をすべて規範にする**: 却下 — ADR-0023 の `lags[]`、ADR-0026 の `node_vlans` のような追加が 1.x で止まる。規範キーだけを規範にする
- **エクスポーターの出力をすべて参考にする**: 却下 — ndl-viz・eve-lab-builder が頼るキーが 1.x で消えうる
- **`derive.py` のうち、エクスポーターが使う関数を 1.0 の公開の API に入れる** (dsl-designer): 採らない — 下流のツールは derive を呼ばない。公開の API は後から足せるが、入れると減らせない
- **pydantic のモデル (属性と型) を規範にする**: 採らない — 1.x で任意のキーを足すたびに `model_dump()` の形が変わる。規範は公開の関数と `ValidationResult` まで
- **入力の改名を 1.x で、新しい名前を足して古い名前を warning にする**: 却下 — 同じ意味を 2 つの名前で書ける形を作らない (ADR-0025)
- **`address_families` の既定値を `["ipv4_unicast"]` にする** (dsl-designer): 却下 — 既定値は 1.0 で固まり、EVPN のセッションで書き忘れても IPv4 として通る

## Pass B で確かめたこと

評価メモ ([evaluations/adr0027/evaluation.md](../evaluations/adr0027/evaluation.md)) を参照。初版の「Pass B で確かめること」は次のように決めた:
エクスポーターの規範キーの一覧 (D1)、バグの修正の線引き (D3)、出力のバージョン (D6 のルートの `meta`)、`derive.py` は公開しない (D1)、`address_families` は `min_length=1` (Consequences)。

## References

- 棚卸し: [evaluations/release-1.0/inventory.md](../evaluations/release-1.0/inventory.md)
- 評価メモ: [evaluations/adr0027/evaluation.md](../evaluations/adr0027/evaluation.md)
- 試し書き: `evaluations/adr0027/` (C1〜C6) と `recommendation.md`、`evaluations/adr0027/passb/` (B1〜B6)
- 関連 ADR: ADR-0002 D8、ADR-0003、ADR-0010 (移行の改訂)、ADR-0015、ADR-0025
- 比べたもの: Terraform の `required_version`、Kubernetes の未知のフィールドの扱い、protobuf の未知のフィールド、yamllint / ansible-lint / ruff のルールのコードと個別の抑止
- 下流: ndl-viz の `src/types/topology.ts` (エクスポーターの出力を読む型)
