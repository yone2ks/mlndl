# MLNDL 言語リファレンス

MLNDL (Multi-Layer Network Description Language) で書けることと、その規則をまとめた文書です。
「このキーには何を書けるか」「何を書くと誤りになるか」を調べるときに読みます。

- MLNDL を初めて書くなら、先に [MLNDL の考え方](../concepts.ja.md) を読んでください。
- なぜそう決めたかは、各ページから設計決定の記録 ([ADR](../decisions/README.md)) にリンクしています。
- このリファレンスは、できるだけ正確に書いていますが、形式的な仕様ではありません。
  何が正しい MLNDL かは、参照実装 [mlndl](../../README.md) のスキーマ (`src/mlndl/schema/`) と検査 (`src/mlndl/validator.py`) が決めます。
  このリファレンスと実装が食い違っていたら、どちらかの誤りとして直します。

## ページ

| ページ | 中身 |
|---|---|
| このページ | ファイルの全体の形、すべての区画に共通する規則、用語集 |
| [layer1.md](layer1.ja.md) | `layer1`: 機器・L1 IF・リンク・LAG |
| [layer2.md](layer2.ja.md) | `layer2`: VLAN・bridge・VTEP・VXLAN・サブ IF |
| [layer3.md](layer3.ja.md) | `layer3`: VRF・L3 IF・ゲートウェイ冗長・トンネル IF |
| [control-plane.md](control-plane.ja.md) | `control_plane`: BGP・OSPF・IS-IS のインスタンス、BFD、セッション |
| [types.md](types.ja.md) | 値の型: id の文法、IP アドレス、AS 番号、Route Target など |
| [validation.md](validation.ja.md) | 検査の一覧と、error / warning / info の意味 |
| [role-vocabulary.md](../role-vocabulary.md) | `role` の推奨語彙 |
| [label-vocabulary.md](../label-vocabulary.md) | `labels` の推奨の軸名 |
| [schema.json](schema.json) | 機械が読めるスキーマ (JSON Schema)。mlndl のスキーマから生成したもの |

## 表の読み方

各ページのキーの表は、次の列からなります。

| 列 | 意味 |
|---|---|
| キー | YAML に書くキーの名前 |
| 型 | 値の型。[types.md](types.ja.md) の名前を使う。`[T]` は T の列 |
| 必須 | ○ は必ず書く。空欄は書かなくてもよい (括弧内は書かないときの値) |
| 参照先 | 値が別のエンティティの `id` を指すとき、その一覧。そこにない `id` を書くと error になる |

## ファイルの全体の形

MLNDL のファイルは YAML で書きます。いちばん外側は次のキーからなるマッピングです。

```yaml
ndl_version: "1.0"      # 必須。MLNDL の版
meta:                   # ファイルの説明
  name: dc-lab
layer1: {...}           # 物理: 機器・L1 IF・リンク・LAG
layer2: {...}           # L2: VLAN・bridge・VTEP・VXLAN・サブ IF
layer3: {...}           # L3: VRF・L3 IF・トンネル IF
control_plane: {...}    # 制御プレーン: BGP・OSPF・IS-IS・BFD・セッション
```

| キー | 型 | 必須 | 説明 |
|---|---|---|---|
| `ndl_version` | 文字列 | ○ | MLNDL の版。今は `"1.0"`。主番号が 1 でなければ error |
| `meta` | マッピング |  | `name` (文字列)、`network_types` (文字列の列)。ほかのキーを書いてもよい (ここだけは知らないキーを受け付ける) |
| `layer1` | マッピング |  | [layer1.md](layer1.ja.md) |
| `layer2` | マッピング |  | [layer2.md](layer2.ja.md) |
| `layer3` | マッピング |  | [layer3.md](layer3.ja.md) |
| `control_plane` | マッピング |  | [control-plane.md](control-plane.ja.md)。書かなくてもよい (データプレーンだけの記述も正しい) |

`layerN` の番号は RFC 8345 のネットワーク層に振ったもので、OSI の層番号ではありません。BGP などのセッションは、どの `layerN` にも属さず `control_plane` に書きます ([ADR-0010](../decisions/0010-control-plane-separation.md) D1)。

## 共通の規則

### YAML の読み方

- YAML は安全な読み方 (`yaml.SafeLoader`) で読みます。任意のオブジェクトを作るタグは使えません。
- ファイルの大きさは 1MB まで。超えると error です。
- 同じマッピングに同じキーを 2 回書くと error です (`キー 'nodes' が重複しています`)。YAML の仕様でもともと誤りです。
- アンカーとエイリアス (`&leaf` / `*leaf`)、マージキー (`<<`) は使えます。

### 知らないキーは error

`meta` を除き、どのマッピングにも決められたキーしか書けません。綴りを誤ったキーや、廃止したキーは error になります。
廃止したキーのうちいくつかは、移動先を示す error になります ([validation.md](validation.ja.md) の「旧構造」「廃止キー」)。

### id

エンティティ (機器・IF・リンク・VLAN・セッションなど、一覧の要素) は、どれも `id` を持ちます。

- 文法は `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`、63 文字まで ([types.md](types.ja.md#id))。
- id は**ファイル全体で一意**です。機器の中だけで一意なのではありません。L1 IF の id は `leaf1-swp1` のように機器の id を前に付けて書きます。
  同じ一覧の中で重複しても、別の一覧 (機器と VLAN など) と重複しても error です。
- id は参照のための安定したキーで、機器上の名前 (`swp1`、`Ethernet1/1`) は別に `name` に書きます。
- 種類ごとの推奨プレフィックス (`link-`、`vlan-`、`bgp-peer-` など) があります。従わないと warning です。

詳しくは [ADR-0002](../decisions/0002-id-naming-convention.md)。

### 参照

別のエンティティを指すときは、その `id` を書きます。参照のしかたは 2 通りです。

- **参照先が 1 種類に決まるキー**: 値に id をそのまま書きます (例: L1 IF の `node: leaf1`、リンクの `endpoints: [spine1-swp1, leaf1-swp51]`)。
  各ページの表の「参照先」の列が、どの一覧の id を書けるかを示します。
- **キーで参照先の種類を選ぶもの**: `{種類: id}` の形で書きます (例: `attaches_to: {interface: leaf1-swp51}`、VLAN のポートの `{ethernet_segment: es-server1}`)。
  キーの名前が参照先の種類を示し、どのキーを書けるかはエンティティごとに決まっています ([ADR-0001](../decisions/0001-attaches-to.md) D8)。

参照先にない id を書くと error です。別の種類の id を書いた場合は、それが何であるかを添えて知らせます。
参照は id だけで行い、機器上の名前 (`name`) で引くことはありません。

### `attaches_to` (実現)

あるものが、下の層の何の上で実現されているかを書きます (RFC 8345 の supporting)。値は 1 つです。

| 書く場所 | 書けるキー | 意味 |
|---|---|---|
| `layer1.nodes` | `node` (文字列で `attaches_to: esxi-01` とも書ける) | この VM・コンテナはこのホストの上で動く |
| `layer1.interfaces` | `node` / `interface` | (仮想の IF が) この機器・IF の上にある |
| `layer2.subinterfaces` | `interface` / `lag` | このサブ IF はこの L1 IF・LAG の上にある (必須) |
| `layer3.interfaces` | `interface` / `lag` / `vlan` / `subinterface` | この L3 IF はこの L1 IF・LAG・VLAN (SVI)・サブ IF の上にある |

`{interface:}` は L1 IF だけを指します。LAG・VLAN・サブ IF はそれぞれのキーで指します。
セッションは `attaches_to` を持ちません。通り道は `update_source` から導きます ([control-plane.md](control-plane.ja.md#通り道))。

### `node` (所属)

機器ごとに別の値を持つもの (L1 IF、L3 IF、トンネル IF、LACP の LAG) は、どの機器のものかを `node` で書きます。
機器ごとの値を持たないもの (VLAN、サブ IF、VTEP など) は `node` を持たず、参照先から機器を導きます ([ADR-0005](../decisions/0005-mlndl-expressive-scope.md) D6)。

### `description`

ほとんどのエンティティに `description` (文字列) を書けます。人が読む補足で、mlndl はパースしません。回線 ID・契約帯域・事業者名などもここに書きます ([ADR-0017](../decisions/0017-sites-and-wan.md) D4)。

### 旧形式

ndl_version 1.x の間は、いくつかの古い書き方を読み替えて受け付け、warning を出します (例: L3 IF の `interface` → `name`、VLAN のポートの `node`、L2VNI の `vtep_source` / `members`)。
一覧は [validation.md](validation.ja.md) の「旧形式」にあります。新しく書くときは使わないでください。

## 用語集

| 用語 | 意味 |
|---|---|
| エンティティ | 一覧の要素として `id` を持つもの (機器・IF・リンク・VLAN・セッションなど) |
| 区画 | `layer1` / `layer2` / `layer3` / `control_plane` と、その中の一覧 (`nodes`、`vlans` など) |
| 機器 (ノード) | `layer1.nodes` の要素。物理・VM・コンテナを問わず「箱」 |
| L1 IF | `layer1.interfaces` の要素。物理ポートや vNIC |
| L3 IF | `layer3.interfaces` の要素。IP を持つ IF (routed ポート・SVI・ループバックなど) |
| 実現 (supporting) | 下の層のものが上の層のものを支える関係。`attaches_to` で書く |
| 所属 | あるものがどの機器のものか。`node` で書く |
| 包含 (containment) | 論理的な箱への所属。`parent` で書く予定 (まだ書けない。[先送りした項目](../decisions/deferred.md)) |
| 分類 | 参照ではない属性による分類。`labels` で書く |
| 正規形 | mlndl が読み込んだあとの形。旧形式は正規形に読み替える |
| 通り道 | セッションのパケットが通るリンク・LAG・bridge・トンネル。`update_source` から導く |
| トポロジー外 | このファイルに書かれていない相手 (事業者の機器など)。アドレスと AS だけで書く |
