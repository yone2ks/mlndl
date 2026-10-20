# ADR-0015: 参照先をスキーマに宣言する (Ref)

- **Status**: Draft — 実装済み (2026-10-21)。Pass B / C は未実施
- **Date**: 2026-10-21
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: A
- **関連**: ADR-0001 D8 (キーで参照先を選ぶ参照)、ADR-0002 D1・D5、ADR-0005 D4 補則、drafts/0014

## Context

ユーザーの問い: 「構文を追加してもライブラリ側をいじらなくてよくて、コード内で参照するときには layer2.vxlan.id とかで
参照できるのが良いように思う」。

調べると、参照の情報が 3 か所にばらばらに書かれていた。

1. スキーマのコメント: `vlan: str  # layer2.vlans[].id を参照` (機械は読まない)
2. validator 冒頭の説明: `vxlan[l2vni].vlan → layer2.vlans` (古くなった記述も残っていた)
3. validator の手書きの検査: 「未定義の X を参照しています」が 29 か所

構文を足すたびに 3 か所を手で揃える必要があり、検査を書き忘れても気づく手段がなかった。
example-author の試算では、MLAG の peer-keepalive (L3 IF を指す `source` を持つ) を足すだけで、
validator に参照の検査と関数の引数の変更が要った。

## Decision

### D1. 検査を 3 種類に分ける

| 種類 | 例 | 仕組み |
|---|---|---|
| 参照先が 1 つに決まっている参照 | `vlan` → `layer2.vlans`、`node` → `layer1.nodes`、`vteps` → `layer2.vteps` | **スキーマに `Ref` で宣言し、汎用の検査が全部を検査する** (D2・D3) |
| 参照先の種類をキーで選ぶ参照 | `attaches_to: {lag: ...}`、VLAN のポートの `{interface:}` / `{lag:}` | 既存の `_resolve_ref` (ADR-0001 D8)。旧形式 `{interface: <LAG>}` の読み替えもここ |
| ネットワークとしての意味の検査 | L3 IF のノード所属、anycast gateway の一致、MLAG、AS 番号、MTU、トンネルの AF | 手書きで残す。各検査に根拠の ADR を書く |

意味の検査を宣言にするかどうかの境目は、**規則を説明するのに RFC やベンダーのマニュアルを引く必要があるか**で決める
(network-tech-reviewer)。引く必要があるものは手書きに残す。汎用の形に押し込むと、MLAG の片側だけといった現場の障害に
つながる誤りを見逃しやすくなるため。

### D2. `Ref` の書き方

```python
vlan: Annotated[str, Ref("layer2.vlans")]
vteps: Annotated[list[str], Ref("layer2.vteps")] = []
client_lag: Annotated[str | None, Ref("layer1.lag")] = None
l3vni: Annotated[str | None, Ref("layer2.vxlan", where=("type", "l3vni"))] = None
```

- **名前は `Ref`** (linguist)。「この値は別のエンティティの id」という事実だけを表す。`RefTo` は `attaches_to`
  (実現の関係という意味を持つ構成子) と紛れるので避けた
- **パスは YAML の構造どおりのコレクション** (`"layer2.vlans"`)。ユーザーの言う `layer2.vxlan.id` は、`.id` がコレクション全体の id か
  要素の id かで迷うので、`.id` は書かない (要素の `id` を指すのは暗黙)
- **`where`** で、コレクションのうち条件に合うものだけを参照先にできる (L3VNI だけ、など)
- **参照先が 1 つに決まる参照には、例外なく `Ref` を付ける**。「フィールド名から参照先が分かるものは省略してよい」という案
  (linguist) は採らなかった。省略すると機械に読めない参照が残り、書き忘れ防止にならない
- 参照先の呼び名 (エラーメッセージ用) は `schema/refs.py` の `COLLECTION_LABELS` に置く

### D3. 汎用の参照検査

validator の `_check_refs` が、スキーマを辿って `Ref` の付いたフィールドを見つけ、値 (リストなら各要素) が参照先にあるかを検査する。

- エラーの場所は YAML のパスで示す (`layer2.vxlan[0].vteps[1]`。`from_` のような別名は `from` で示す)
- 指した id が別の種類のコレクションにあれば、何であるかを添える
  (例: 「未定義の VLAN 'vrf-a' を参照しています。'vrf-a' は VRF です」)
- `where` に合わない場合はその旨を添える (「'vni-10100' は type: l3vni ではありません」)

**構文を足すとき、参照の検査のために validator に手を入れる必要はない。** `Ref` を書けば検査が付く。

### D4. 分類の網羅をテストで保証する

`tests/test_refs.py` が、スキーマのすべての文字列フィールドについて、次のどれかであることを確かめる。

- `Ref` が付いている
- キーで参照先を選ぶ参照 (`attaches_to`、VLAN のポートの `interface` / `lag`)
- 参照ではない値 (`id`, `name`, `description`, `role` など。テストの一覧に登録)

新しい文字列フィールドを足して、`Ref` も一覧への登録もしなければテストが落ちる。あわせて、`Ref` のパスがスキーマに実在すること、
呼び名が登録されていること、スキーマに「を参照」のコメントだけの参照が残っていないことも確かめる。

### D5. id からエンティティを引く (`resolve`)

```python
topology.resolve("vtep-leaf1-leaf2")            # → Vtep
topology.resolve("vni-10100", "layer2.vxlan")   # パスを指定して引く
index = topology.index()                        # 何度も引くときは索引を使い回す
index.ids("layer2.vxlan", ("type", "l3vni"))    # → {"vni-10900"}
```

- 索引 (`IdIndex`) は、スキーマの id 付きのリストを列挙して作る (エンティティを足しても漏れない)
- 同じ id が複数のコレクションにあると (ADR-0002 D5 違反)、どれを返すか決められないので `LookupError` を出す。そのときはパスを指定する
- 参照先の実体を属性としてスキーマに埋め込む形 (`vni.vlan_obj` など) は採らない。循環や YAML への書き出しが壊れる (dsl-designer)
- 逆引き (この VLAN を参照しているもの) と経路の探索は、Phase 3 の broadcast_domain / blast_radius クエリと一緒に設計する

### 範囲外

- **参照以外の汎用の制約** (双方向参照の一致、(基盤, 値) の一意性、グループ内の値の一致。network-tech-reviewer の提案): 今回は入れない。
  `Ref` を使ってみて、同じ形の検査がさらに増えてから考える
- **スキーマを YAML / JSON Schema などの外部定義にする**: 採らない (5/5)。今の規模では過剰で、pydantic で宣言と検査が完結している方が保守しやすい
- **エクスポーターの索引の置き換え**: cytoscape エクスポーターは今も自前で id → ノードの辞書を組んでいる。`IdIndex` への置き換えは別の作業とする

## Consequences

- 構文を足すとき、参照の存在の検査は `Ref` を書くだけで付く。書き忘れは D4 のテストが検出する
- validator は 1,193 行から 1,052 行になり、冒頭の説明から参照の一覧を外した (スキーマを見ればよい)
- 置き換え前後で、全 fixture の参照を 1 つずつ存在しない id に書き換えた 849 通りについて、error の場所が完全に一致することを確かめた
- 手書きの意味の検査は残る。構文を足すとき、意味の検査が要るかは ADR で判断する

### 影響を受けるコンポーネント

- スキーマ: `schema/refs.py` (新設)、`layer1.py` / `layer2.py` / `layer3.py` / `protocols.py` の参照フィールドに `Ref`、`topology.py` に `index()` / `resolve()`
- 索引: `index.py` (新設。`IdIndex`)
- バリデーター: `_check_refs` / `_walk_refs` を追加し、手書きの存在検査 29 か所を削除
- テスト: `tests/test_refs.py` (15 件)

## Alternatives Considered

- **今のまま (コメント + 手書き)**: 却下 — 構文を足すたびに検査を書き足す必要があり、書き忘れに気づけない
- **新しい構文から少しずつ `Ref` を使う** (example-author): 却下 — しばらく 2 つの方式が並ぶ。既存の検査は差分テストで安全に置き換えられた
- **`Ref` を付けるのはフィールド名から参照先が分からないものだけ** (linguist): 却下 — D2
- **参照以外の制約も宣言にする** (network-tech-reviewer): 見送り — 範囲外
- **スキーマの外部定義**: 却下 — 範囲外

## References

- 試し書き: `evaluations/declarative-refs/comparison.md` (MLAG の peer-keepalive と BUM 配送方式を足す作業の比較)
- YANG の `leafref` (RFC 7950)。参照を型で宣言し、条件付きの参照には `when` / `must` を別に要した教訓 (dsl-designer)
