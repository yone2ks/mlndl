# ADR-0027: 互換の約束 — 1.0 の後、1.x で許す変更と 2.0 が要る変更

- **Status**: Draft
- **Date**: 2026-11-18
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー (D3・D4・D5 の 4 つの論点)
- **Pass**: A (5 エージェントの評価を 1 回取り、割れた 4 つの論点をユーザーが決めた)
- **Amends**: ADR-0010 の移行の改訂 (「1.0 の後は破壊的な変更にメジャーバージョンの更新を必須とする」の中身を決める)、CLAUDE.md §3 (`ndl_version`)
- **関連**: ADR-0002 D8 (severity)、ADR-0025 (「読み替えて warning」を既定にしない)、[1.0 に向けた棚卸し](../evaluations/release-1.0/inventory.md)

## Context

最初のリリースは 1.0 で、1.0 の後は破壊的な変更にメジャーバージョンの更新が要る (ADR-0010 の移行の改訂)。ところが、何が「破壊的な変更」かは決めていない。
1.0 に向けた棚卸し (2026-11-18) では仮の物差しで項目を振り分けたが、その物差しを約束として書く必要がある。今の実装には次の穴がある (2026-11-18 に確かめた)。

- `ndl_version` は CLAUDE.md §3・`docs/reference/README.ja.md`・`validation.ja.md` で「必須」とあるが、実装は既定値 `"1.0"` を持ち、書かなくても通る (`src/mlndl/schema/topology.py:27`・`:40`。試し書き C1)
- 全モデルが `extra="forbid"` なので、1.1 で足したキーを 1.0 の mlndl は `Extra inputs are not permitted` で拒む。`ndl_version: "1.1"` と書いても版の違いは知らせず、利用者は書き損じと区別できない (試し書き C2・C3)
- パッケージのバージョンは `0.1.0` で、`ndl_version` との関係が決まっていない
- 検査を足すこと・緩めることが互換にどう効くか、`--strict` で CI を回す利用者に何を約束するかが決まっていない

## Decision

### D1. 約束の範囲

| 対象 | 扱い |
|---|---|
| YAML の書き方 (キー・形・必須 / 任意・値域・既定値・意味) | **規範**。破るなら 2.0 |
| 検査の結果 (どの YAML が error になるか) と severity の意味 (ADR-0002 D8) | **規範**。D3 の範囲で 1.x でも変わる |
| Python の公開 API: `parse` / `parse_file` / `validate` / `validate_all` / `ValidationResult` / `ValidationError` / `MLNDLTopology` (`index()` / `resolve()`) / `IdIndex` / `Ref` / `LANGUAGE_VERSION` の呼び方・戻り値・例外の型 | **規範** |
| CLI の `validate` / `export` / `schema`、終了コード、`--strict` の意味 (D4) | **規範** |
| エクスポーターの出力 (Cytoscape の JSON) のうち、`docs/exporter-cytoscape.md` の「約束するキー」に挙げたもの | **規範**。キーを足すのは 1.x でよい。挙げたキーを消す・改名する・意味を変えるのは 2.0 |
| 上の「約束するキー」以外の出力、`derive.py` の関数、pydantic のクラス名・モデルの内部、メッセージの文面とパスの書き方 | **参考** (informative)。1.x で変えてよい |

- 下流のツール (ndl-viz・eve-lab-builder) は、エクスポーターの出力の知らないキーを無視する
- エクスポーターの出力のキーを改名したいときは、新しいキーを足し、古いキーは 2.0 まで残す。入力 (YAML) では同じことをしない (同じ意味を 2 つの名前で書ける形は作らない。ADR-0025)

### D2. 1.x で許す変更と、2.0 が要る変更

| 変更 | 1.x |
|---|---|
| 任意のキー・コレクション・Literal の値・Tagged Union の分岐を足す | 許す |
| 受け付ける型を広げる (`X` → `X \| list[X]`)、値域を広げる | 許す |
| 必須のキーを任意にする | 許す |
| 検査を緩める (error を warning に、warning を info に、検査をやめる) | 許す |
| warning・info を足す | 許す (D4) |
| メッセージの文面を変える | 許す |
| エクスポーターの出力にキーを足す | 許す |
| キー・値・コレクションを改名する、消す | **2.0** |
| 任意のキーを必須にする、既定値を変える、意味を変える | **2.0** |
| 型・値域を狭める | **2.0** |
| 検査を強める (warning を error に)、既存の YAML を落とす新しい error | **2.0** (D3) |
| 糖衣構文・`meta` の受け付け (D7) をやめる | **2.0** |

### D3. 新しい error を足してよいのは、1.x で足したキー・値に付くものだけ (ユーザー決定)

- 1.x で足したキーや値の検査は、足したときから error にしてよい (そのキーを書いた YAML は、それまで存在しなかった)
- 1.0 の時点で書けた YAML を落とす新しい error は 2.0 まで待つ。それまでは warning として足す (D2)
- 1 版前に warning で予告して次の版で error にする方式 (network-tech-reviewer の案) は採らない。1.x の中で warning を error に強めることになり、D2 と食い違う

### D4. `--strict` が約束するのは「その版の warning を error にする」ことだけ (ユーザー決定)

- 1.x では warning を足すので、`--strict` で通っていた YAML が新しい版で止まることがある
- `--strict` で CI を回すなら、mlndl のマイナーバージョンを固定して上げるときに見直す運用にする。これを `docs/reference/validation.ja.md` に書く
- 1.x のリリースノートには、足した warning をすべて書く
- warning にコードを付けて個別に抑える仕組み (`--ignore` など) は、1.x で足す (加算)。1.0 の前には作らない

### D5. `ndl_version` は必須。YAML より古い mlndl は版の違いを知らせて止まる (ユーザー決定)

- 1.0 から `ndl_version` を必須にする。書かなければ error (「`ndl_version: "1.0"` を書いてください」)
- 書式は `"<メジャー>.<マイナー>"` (パッチは書かない)。メジャーが 1 でなければ今までどおり error
- YAML の `ndl_version` は「**この YAML が使う最も新しい版**」(この YAML を読むのに要る最低の mlndl の版) を表す。1.1 で足したキーを 1 つでも使ったら `"1.1"` と書く。使わなければ `"1.0"` のままでよい
- YAML のマイナーバージョンが mlndl の知るものより新しければ、未知のキーの error より先に、この 1 本の error を出して止める:
  > この YAML は ndl_version 1.1 で書かれていますが、この mlndl が読めるのは 1.0 までです。mlndl を更新してください (ADR-0027)
- 未知のキーを warning にして読み進める方式は採らない。中間フォーマットとして、下流のツールが情報の欠けたトポロジーのまま気づかずに動くのを避ける
- マイナーバージョンを上げるのは、書けるもの (キー・値・コレクション) を足したとき。検査だけを変えたときは上げない
- `ndl_version: "1.0"` のまま 1.1 のキーを書いた YAML は、書き手の誤りとして今までどおり未知のキーの error になる (試し書き C3)。メッセージに「1.1 のキーなら `ndl_version` を上げる」を添えるかは実装のときに決める

### D6. パッケージのバージョンと言語のバージョン

- パッケージ (pip) のバージョンの `メジャー.マイナー` は、その実装が読める最も新しい `ndl_version` と同じにする。パッチは実装の修正
  - 例: mlndl 1.0.3 は ndl_version 1.0 を読む。mlndl 1.1.0 は 1.0 と 1.1 を読む。mlndl 2.0.0 は 1.x を読まない
- `mlndl.LANGUAGE_VERSION` (例: `"1.0"`) を公開し、下流のツールがこの値で分岐できるようにする
- 1.0 のリリースでパッケージを `1.0.0` にする (今は `0.1.0`)

### D7. 1.0 の約束に入れる形

- **`attaches_to: <node id>` の文字列の糖衣構文** (`layer1.nodes` だけ。`{node: <id>}` と同じ意味)。やめるのは 2.0
- **`meta` は未知のキーを受け付ける**。下流のツールは `meta.<ツール名>:` に自分の設定を置ける。未知のキーを受け付けるのは `meta` だけで、ほかのモデルは 1.x の間 `extra="forbid"` のまま (広げるなら区画ごとに ADR で決める)
- **旧形式の「移動先を示す error」** (ADR-0010・0020・0022〜0026 で入れたもの) は 2.0 まで残す。消すのは 2.0 で、そのときに改めて決める

### D8. 利用者向けの書き方

`docs/reference/README.ja.md` に「互換の約束」の節を足す。「前方互換」「後方互換」の語は、指す向きが読み手によって逆になるので使わず、向きをそのまま書く (linguist)。

> - 新しい mlndl は、古い版の YAML を読めます (1.x の間)
> - 古い mlndl は、新しい版の YAML を読めません。YAML の `ndl_version` が mlndl より新しければ、版の違いを知らせて止まります
> - 1.x で足すのは、任意のキー・値、緩めた検査、warning です。名前・形・必須かどうか・既定値・意味を変えるのは 2.0 です
> - `--strict` は、その版の warning を error にします。1.x で warning が増えることがあるので、CI では mlndl の版を固定してください

## Consequences

**良い影響:**
- 「1.0 の前に直さないと後で直せないもの」を、この表で判定できる
- 古い mlndl で新しい YAML を読んだとき、原因 (版の違い) がすぐ分かる
- 下流のツールは `LANGUAGE_VERSION` と、エクスポーターの「約束するキー」に頼れる

**悪い影響 / トレードオフ:**
- 1.x で誤りを見つける新しい検査を思いついても、既存の YAML を落とすものは 2.0 まで warning にとどまる
- `--strict` の利用者は、マイナーバージョンを上げるたびに新しい warning を見直す
- `ndl_version` を必須にするので、書いていない YAML は 1.0 で error になる (今の examples と fixtures は全部書いている。テストの中の YAML には書いていないものがある)

**この ADR の結果、1.0 の前に必須になるもの** (棚卸しの 2・3。改名・既定値・意味の変更は D2 で 2.0 になるため):
- `layer1.lag` → `lags`、`layer2.vxlan` → `vxlans`、IS-IS の `level-1` / `level-2` / `level-all` → `level_1` / `level_2` / `level_all` (linguist・dsl-designer が推した。旧名は移動先を示す error)
- `L2VxLAN.vteps` を `min_length=1` に (今は既定値 `[]` で、空を validator で error にしている)
- `BgpSession.address_families: []` の意味を決める
- 既定値 (`LacpConfig.mode = "active"`・`min_links = 1`、`route_reflector_client = False` など) を見直して一覧にする

**影響を受けるコンポーネント (この ADR だけの分):**
- スキーマ: `src/mlndl/schema/topology.py` (`ndl_version` の既定値を外す、マイナーバージョンの比較を `extra="forbid"` の検査より前に)
- `src/mlndl/__init__.py` (`LANGUAGE_VERSION`)、`pyproject.toml` (1.0 のリリースで `1.0.0`)
- テスト: `ndl_version` を書いていないテストの中の YAML
- 文書: `docs/reference/README.ja.md` (D8)、`validation.ja.md` (D4)、`docs/exporter-cytoscape.md` (「約束するキー」の節)、CLAUDE.md §3

## Alternatives Considered

- **`ndl_version` を書かなければ 1.0 とみなし、warning で促す** (dsl-designer): 却下 (ユーザー決定) — docs と実装の食い違いを残す。必須にしておけば、D5 の版の比較がいつも働く
- **古い mlndl は未知のキーを warning にして読み進める** (network-tech-reviewer): 却下 (ユーザー決定) — 下流のツールが情報の欠けたまま動く。`meta` だけが未知のキーを受け付けるという境界も崩れる
- **今のまま、未知のキーの error に任せる**: 却下 — 版の違いか書き損じかを利用者が区別できない
- **新しい error は 1 版前に warning で予告すれば 1.x で足せる** (network-tech-reviewer): 却下 (ユーザー決定) — 1.x の中で warning を error に強めることになる
- **新しい error は 1.x で一切足さない** (dsl-designer・example-author): 採らない — 1.x で足したキーの検査まで warning に縛る理由がない
- **1.0 の前に warning にコードを付け、個別に抑えられるようにする** (network-tech-reviewer): 1.x で足す (ユーザー決定) — 後から足しても破壊的ではない。1.0 の前の作業を増やさない
- **エクスポーターの出力をすべて規範にする**: 却下 — ADR-0023 の `lags[]`、ADR-0026 の `node_vlans` のような追加が 1.x で止まる。約束するキーだけを規範にする
- **エクスポーターの出力をすべて参考にする**: 却下 — ndl-viz・eve-lab-builder が頼るキーが 1.x で消えうる
- **入力の改名を 1.x で、新しい名前を足して古い名前を warning にする**: 却下 — 同じ意味を 2 つの名前で書ける形を作らない (ADR-0025)

## Pass B で確かめること

- エクスポーターの「約束するキー」の一覧 (どのキーを規範にするか。ndl-viz・eve-lab-builder が読んでいるキーから決める)
- 文書に error と書いてあるのに実装が見逃していた誤り (バグ) を 1.x で直すのは、D3 の「新しい error」に当たるか
- エクスポーターの出力に、出した mlndl のバージョンと `ndl_version` を入れるか (network-tech-reviewer。下流のツールが「対応していない版」を表示するため。加算)
- 公開 API に `derive.py` の関数のどれを入れるか (今は参考)
- `address_families: []` の扱い (dsl-designer は既定値 `["ipv4_unicast"]` を推したが、既定値は 1.0 で固まるので慎重に)

## References

- 棚卸し: [evaluations/release-1.0/inventory.md](../evaluations/release-1.0/inventory.md)
- 試し書き: `evaluations/adr0027/` (C1〜C6) と `recommendation.md` (example-author)
- 関連 ADR: ADR-0002 D8、ADR-0010 (移行の改訂)、ADR-0025
- 比べたもの: Terraform の `required_version`、Kubernetes の未知のフィールドの扱い、protobuf の未知のフィールド、yamllint / ansible-lint / ruff のルールのコードと個別の抑止
