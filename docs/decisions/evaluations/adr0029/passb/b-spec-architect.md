# ADR-0029 Pass B — mlndl-spec-architect

## 提案

1. 新しい一覧 `layer2.overlay_domains` (id / name / description / labels) を足す
2. `layer2.vteps[].domain` を任意のフィールドで足す (`Annotated[str | None, Ref("layer2.overlay_domains")]`)
3. L2VNI のスキーマは変えない。トンネルの対は「同じ L2VNI の `vteps` に入り、同じドメインに属する VTEP どうし」で導く
4. L3VNI のトンネルの範囲は、同じ VRF の L2VNI のドメインの和集合で導く
5. BGW・DCI などの方式名は構文に入れない

## 影響の範囲

- **スキーマ**: `OverlayDomain`、`L2Layer.overlay_domains: list[OverlayDomain] = []`、`Vtep.domain`。推奨プレフィックス `od-` を ADR-0002 D7 に足す
- **validator**:
  - `overlay_domains[].id` の文法・一意性・`od-` (warning)
  - `vteps[].domain` の存在は Ref で自動 (error)
  - VTEP が 0 のドメイン (error)、1 のドメイン (warning)
  - **2 つ以上のドメインに参加する L2VNI に、2 つ以上のドメインに VTEP を持つ機器がない** (error)。Multi-Site の核心の検査
  - サイト間の EVPN セッションの両端と、ドメインをまたぐ機器の集合の食い違い (info。制御プレーンを書いたときだけ)
  - ドメインをまたぐ機器では ADR-0026 D5 の 10 の warning を出さない
- **導出** (`derive.py`): `vtep_domain`、`domain_vteps`、`l2vni_tunnel_pairs` (同じドメインの VTEP の対)、`l3vni_tunnel_pairs` (同じ VRF の L2VNI の和集合から)、`cross_domain_nodes` (= BGW らしい機器)。`l2vni_participants` は変えない (ADR-0026 D4 を保つ)
- **エクスポーター**: `type: overlay_domain` のノード、VTEP の `domain`、L2VNI の導出値 `domains`、機器の `is_border_gateway` (導出)。トンネルは L2VNI ごとの VTEP の対の辺で出す (any-to-any の誤読を防ぐ)。加算のキー
- **見本**: 既存の 5 本は書き換えなし。`tests/fixtures/valid_evpn_multisite.yaml` (a1 がもと) を足す
- **文書**: ADR-0029、concepts.ja.md (`labels.site` との違い)、reference の layer2、exporter-cytoscape.md、CLAUDE.md、role-vocabulary.md に `border-gateway` (informative)

## 移行のコスト

**低い**。加算だけで、既存の fixture と ndl-viz の読み方は変わらない (ADR-0027 D2 の「キー・コレクションを足す」)。ドメインを書かないトポロジーは「全 VTEP が暗黙の 1 つのドメイン」として扱い、L2VNI の `vteps` の全部の対がトンネルになる。今の `l2vni_participants` の意味と一致する。

## 代替案

- **A2 (ドメインが `members` で VTEP を並べ、L2VNI が `domains` を指す)**: L2VNI はすでに `vteps` を持つので、所属が 2 か所に重複する。整合の検査が要り、ADR-0005 D2-1 (関係は参照、二重に書かない) に反する。「1 つの VTEP は 1 つのドメイン」も A1 なら型で済むが A2 では検査になる。却下
- **A3 (L2VNI の `vteps` の構造化)**: Pass A で退けた
- **セッションから導く**: データプレーンが制御プレーンに依存する。「書かれた情報だけを使う」に反する
- **`labels.site` から導く**: ADR-0009 D3・ADR-0017 D1・BGW は 2 サイトに面するのに 1 つの値、で破綻

## 推奨

**A1 (`overlay_domains` + VTEP の `domain`) で進める**。ADR-0005・0009・0014・0017・0026・0027 のどれにも加算で入り、fixture の書き換えが要らず、推奨モデルを型で担保できる。ADR-0014 D3 / D4 と ADR-0026 D4 は変わらない (ドメインは VTEP の属性で、参加機器の導き方は同じ)。ADR-0014 D6 の表の「Multi-Site BGW の anycast」の行 (サイト内の VTEP と DCI の VTEP を別エントリ) はそのまま、各エントリに `domain` を足す。

**「DCI も 1 つのドメイン」は妥当**: ドメインを「フルメッシュのトンネルの範囲」の 1 つの定義で扱える。

- route server 経由: RS は VTEP を持たないので DCI のドメインの形は変わらない
- 2 サイトの stretched: 全 VTEP が 1 つのドメイン
- 3 サイト以上のフルメッシュ: DCI のドメイン 1 つに BGW が 3 つ以上
- hub-and-spoke の DCI: 複数の DCI のドメイン (hub の BGW が各 DCI のドメイン向けに VTEP を 1 つずつ持つ)。1 対 1 は崩れない

**L3VNI**: L3VNI には `vteps` を足さず、同じ VRF の L2VNI のドメインの和集合として導く (`l3vni_tunnel_pairs`)。ADR-0014 D3 の「L3VNI の参加ノードは VRF から導く」と同じ流儀。L2VNI のない L3VNI (L3 専用) で VTEP を明示する必要が出たら、`vteps` を加算で足す (先送り)。

**先送り (deferred.md に足す行)**:

- L3VNI の明示の `vteps` (L2VNI のない構成が出てきたとき)
- VNI stitching と「同じ VLAN に複数の L2VNI」の緩和 (50 行目を更新)
- BGW での RT の付け替え (53 行目に関連づけ)
- BUM の配送方式をドメインごとに切り替える書き方

## ユーザーに判断してもらう論点

1. **一覧の名前**: `overlay_domains` / `vxlan_domains` / `fabrics`。推奨は `overlay_domains` (VXLAN にも EVPN にも限定しない、DCI を含むので `fabrics` は不自然)。参照キーは単数の `domain:`、プレフィックス `od-`
2. **`domain` の任意 / 必須**: 任意 (書かなければ暗黙の 1 つのドメイン) を推奨。必須にすると既存の fixture と ADR-0014 D6 の試し書きがすべて書き換えになる
3. **1 つの VTEP が複数のドメインに属せるか**: 1 対 1 を推奨。多対多ではドメインをまたぐ機器の導出が崩れ、エクスポーターで線を引けない
4. **BGW の目印**: `role: border-gateway` を ADR-0003 の推奨語彙 (informative) に足す。validator は読まない

別件: `vrf: vrf-default` を明示したときの EVPN のセッションの warning の文は、この ADR と別に直す。
