# ADR-0014 設計比較 — VXLAN VTEP の表現、特に MLAG ペアの anycast VTEP

現状の `layer2.vxlan[l2vni].vtep_source: str` (単数) + `members: [node...]` は
VNI ごとに 1 ノード分の VTEP ソースしか書けず、MLAG ペアの anycast VTEP IP も
書けない。`tests/fixtures/valid_full_dc.yaml` が `vtep_source: leaf1-lo` で leaf2 の
VTEP を表せていないのが実例。

本評価は 4 案 (A/B/C/D) の試し書き。トポロジーは共通で spine 2 + leaf 4
(MLAG ペア A = leaf1/leaf2、ペア B = leaf3/leaf4) + border 1 (単独 VTEP)、
L2VNI 2 本 (10100 は全体、10200 はペア A のみ)、L3VNI 1 本。L1 のケーブリング
と BGP 設定は本論ではないので省略した。

## 4 案

| 案 | 新規エンティティ | VTEP IP の在りか | MLAG anycast の書き方 | 行数 (本評価) |
|---|---|---|---|---|
| A | なし | L3 IF (`ip:`) | 2 ノードの lo1 に同じ IP を書く + VNI は `vtep_sources: [...]` 列挙 | ~75 |
| B | `layer2.vteps` (1 ノード = 1 VTEP) | L3 IF (`ip:`) | 案 A と同じ (L3 IF 側で同じ IP) | ~80 |
| C | `layer2.vteps` (MLAG は `nodes:` 2 ノード) | VTEP エンティティ (`anycast_ip:`) か L3 IF | VTEP エンティティに `anycast_ip` を 1 箇所書くだけ | ~70 |
| D | なし (`vtep_source` を list に広げる最小改変) | L3 IF (`ip:`) | 案 A と実質同じ | ~75 |

## 書きやすさ・読みやすさ

- **案 A / D**: `vtep_source` を単純に複数化するだけで、既存の読者 (VNI = 一枚の
  論理セグメント、vtep ソースはその L3 側実体) の直観に揃う。追加の抽象が
  不要。ただし「どの 2 つが MLAG ペアの anycast か」が暗黙 (= L3 IF の IP
  被り) で、読んだだけでは MLAG 関係が見えない。
- **案 B**: VTEP に ID が付くことで VNI 側がすっきりする (`vteps:
  [vtep-leaf1, ...]` は VNI 参加者が 1 行で分かる)。しかし「VTEP」という
  抽象を 1 ノードごとに 1 つ作るだけだと、`node` と `source` の 2 フィールド
  しかない薄いエンティティになり、`members` を `vteps` に置き換えただけに
  見える。利得が小さい。
- **案 C**: MLAG が 1 エンティティ・anycast IP が 1 箇所、という読み味は
  今回の 4 案で一番良い (`lag: {type: mlag, nodes: [a,b]}` と並ぶ)。
  solo と MLAG が同一コレクションに同居するため Discriminated Union
  (`node` 単数 vs `nodes` 複数、§6 の `lag` と同じ型分岐) が必要。

## 二重表現 (同じ事実を 2 か所に書くこと)

| 事実 | A | B | C | D |
|---|---|---|---|---|
| anycast IP = 10.0.1.12/32 | lo1 2 箇所に同一値 | lo1 2 箇所に同一値 | **1 箇所 (vtep)** | lo1 2 箇所に同一値 |
| ノード = {leaf1,leaf2,...} | `vtep_sources` + `members` | `vteps` のみ (members 省略推奨) | `vteps` の `nodes` のみ | `vtep_source` + `members` |
| MLAG ペア関係 | 書かれない (lo1 の IP 一致で暗黙) | 書かれない | **明示 (vtep.nodes)** | 書かれない |

案 C が最も二重表現が少ない。案 A/D は anycast IP を 2 回書き、しかも
「2 ノードの lo1 の IP が偶然一致している」ことが MLAG を意味するという、
解釈のための約束事を validator に埋め込む必要がある。

## 書き手がやりがちな誤りと検出可能性

| ミス | A | B | C | D |
|---|---|---|---|---|
| **共有 IP の不一致** (lo1 の IP が片方だけ違う) | lo1 の IP を見比べて検出。anycast 意図は宣言されていないので「同じ MLAG ペア」の括りを `layer1.lag[type:mlag].nodes` から拾う必要がある | 同左 | **構造上あり得ない** (IP は VTEP に 1 回しか書かない) | 同左 (案 A と同じ) |
| **片方のピアだけ書く** (vtep_sources に leaf1 だけ) | validator が「MLAG ペアに属するノードは両方書くべき」ルールを別途持たないと検出不可 | 同左 | **vtep.nodes を 2 ノードに縛れば自然に強制** できる (list の長さが 2 でない MLAG は error) | 同左 |
| **VNI の members と VTEP の不整合** | members と vtep_sources の node 集合が食い違う → error 出せる (が、両方書かせているので起こる) | members を省略すれば発生しない (vteps のみが権威) | 発生しない (`vteps` のみ) | 同 A |
| **VTEP の source が自ノードの L3 IF ではない** | 単純な参照整合性で検出 | 同左 | 単独 VTEP は検出可。MLAG VTEP は L3 IF を参照しないので「どの L3 IF から送出するか」の情報が消える → 下記「技術的疑問」参照 | 同 A |

案 C が最もミスに強いが、「VTEP の送信元 IF をどう特定するか」を失う
副作用がある (下記)。

## 現行スキーマで通るか

4 案とも仮構文 (現行は `vtep_source: str` 単数)。手元に Python 実行環境が
ないため `python -m mlndl validate` の実行結果は推測だが:

- 案 A / B / C: 新規フィールド (`vtep_sources`, `layer2.vteps`) は現行モデルの
  `extra="forbid"` に引っかかり ValidationError になるはず。
- 案 D: `vtep_source` に list を渡すと型エラー (str 期待)。やはり error。

いずれも「スキーマ変更が必要」であることは一致している。

## NX-OS 式「1 つの loopback に primary(ユニーク) + secondary(共有)」

| 案 | 書けるか | 備考 |
|---|---|---|
| A | **書けない** | `L3Interface.ip` が単数。別 loopback (lo0 / lo1) に分けるしかない。NX-OS 実機の「同一 lo に 2 IP」は再現不可 |
| B | 書けない (A と同じ) | VTEP エンティティに `primary_source` / `secondary_source` の 2 フィールドを足せば表現可。ただし L3 IF 側は従来通り単数 IP のまま |
| C | **書ける** (エンティティ側で解決) | 例: `{nodes: [leaf1, leaf2], primary_sources: {leaf1: leaf1-lo0, leaf2: leaf2-lo0}, anycast_ip: 10.0.1.12/32}`。primary と anycast を 1 VTEP に同居させられるのは案 C だけ |
| D | 書けない (A と同じ) | — |

NX-OS 構成を素直に書けるのは案 C のみ。

## 推奨

**案 C を推す。** 根拠:

1. **二重表現が消える**: anycast IP が VTEP エンティティに 1 箇所。
   「2 ノードの lo1 の IP 偶然一致」で anycast を推論しない。
2. **MLAG ペア関係が明示される**: `nodes: [leaf1, leaf2]` は `layer1.lag[type:mlag].nodes`
   と文法的に揃い (§6 の `lag` の形)、読者が既に知っている構文の再利用。
3. **ミスに強い**: 「片方のピアだけ」「共有 IP 不一致」が構造上発生し得ない。
4. **NX-OS 構成の primary + secondary を素直に書ける** のは案 C のみ。
5. **ADR-0005 D6 の「ノードごとの設定値を持つものだけ `node` を書く」原則に揃う**:
   anycast は本質的にペアで 1 つの IP = 1 エンティティ、固有 primary はノード
   ごと = ノード軸のサブフィールド、と分離できる。

案 C の欠点として「`vteps` と `lag[type:mlag]` で `nodes: [a,b]` を 2 回書く」
二重表現が残る。これは `vtep.peer_mlag: lag-mlag-a` と `lag` を参照する形で
片方に寄せれば解消できる (follow-up として検討)。

案 A / D は最小改変で済むが、anycast を暗黙に残す設計は validator の責務を
重くし、将来 primary + secondary を扱えない袋小路に向かう。案 B は
抽象の割に得が小さい (= C に発展させる価値あり)。

## 技術的疑問 (network-tech-reviewer へ)

- **案 C で MLAG VTEP の「送信元 L3 IF」をどう示すか**。EVPN では
  NVE source-interface として実 loopback IF を指定するのが実装の常識。
  anycast_ip を VTEP に書くだけでは、どの L3 IF 名 (lo1 など) にその IP が
  貼られているかが mlndl から消える。eve-lab-builder が Cumulus/EOS/NX-OS
  の config を書き出すとき、`primary_sources: {leaf1: leaf1-lo-nve, ...}` を
  必須にする運用で妥当か?
- **「secondary IP」は本当にベンダ別の実装詳細か、それとも mlndl の表現対象か**。
  Cumulus/FRR の `vxlan-local-tunnelip` と NX-OS の `ip address A secondary` は
  機能等価だが、構文が違う。mlndl 側は「VTEP の送信元 IP」として単一の抽象
  にすべき (= 案 C の方向) で、実機設定への写像は eve-lab-builder に任せる、
  で問題ないか?
- **border1 のような単独ノードが MLAG VTEP に成長したときの移行性**。
  単独 VTEP (`node:` 単数) から MLAG VTEP (`nodes:` 複数) への書き換えは
  差分が大きい (ID 名も変わる)。この書き換えが頻発するなら、常に
  `nodes: [a]` / `nodes: [a,b]` の 1 構文に統一する方が穏当かもしれない。

## 提案 (mlndl-spec-architect へ)

- **ADR-0014 を起草**: 「VTEP を独立エンティティ化する」で ADR-0012/0013
  と並ぶ L2 設計決定にする。
- **構文スケッチ**:
  ```python
  class VtepSolo(BaseModel):
      type: Literal["solo"] = "solo"      # 省略可
      id: str
      node: str
      source: str              # layer3.interfaces[].id
  class VtepMlag(BaseModel):
      type: Literal["mlag"] = "mlag"
      id: str
      nodes: list[str]         # 固定長 2
      anycast_ip: IPv4Interface
      primary_sources: dict[str, str] | None = None   # node → L3 IF id
      peer_mlag: str | None = None   # layer1.lag[].id (type: mlag) への参照
  Vtep = Annotated[VtepSolo | VtepMlag, Field(discriminator="type")]
  ```
- **L2VxLAN**: `vtep_source: str` → `vteps: list[str]` (vtep id 参照) に変更。
  `members` は廃止 (vtep.nodes から導出)。1.x の後方互換で旧 `vtep_source` /
  `members` は warning 付きで読み替え。
- **validator 追加項目**:
  - MLAG VTEP の `nodes` 長が 2 であること
  - `peer_mlag` を書いた場合、`layer1.lag` の `type: mlag` 側の `nodes` と
    集合一致すること
  - `primary_sources` のキー集合が `nodes` と一致すること
  - 単独 VTEP の `source` の node が `node` と一致すること

## 採否 (2026-10-20、[drafts/0014](../../drafts/0014-vteps.md))

本 README の 4 案 (1 回目の評価) のうち、推奨した案 C (`type: anycast` + `anycast_ip`、MLAG ペアで 1 エンティティ) は**採用しなかった**。
ユーザーが「なぜ `anycast_ip` なのか。方式が増えるたびに構文が増えるのか」と問い、2 回目の評価で
方式中立のモデル (`sources` + `address`) に改めた。試し書きは `neutral/` の 7 本 (Cumulus / Arista / NX-OS vPC / ESI-LAG /
Multi-Site BGW / 単独 / やりがちな誤り) で、方式名を構文に出さずに書けることを確かめた。

採用した形との違い:

- 共有アドレスの名前は `anycast_ip` ではなく `address` (IPv6 は `address_v6`)
- `type` で型を分けない。単独と共有は `sources` の数だけが違う
- アドレスを省略できるのは `sources` が 1 つのときだけ (`neutral/02_arista_mlag.yaml` の省略版は採用形では error)

実装後の `python -m mlndl validate` の結果 (`neutral/`):

| ファイル | 結果 |
|---|---|
| `01` Cumulus / `03` NX-OS vPC / `05` Multi-Site BGW / `06` 単独 | 通る |
| `02` Arista | error (`address` を省略した版。共有するときは `address` が必須) |
| `04` ESI-LAG | error (MLAG のエントリに `labels` を書いている。ESI の書き場所がないための仮置きで、Ethernet Segment は別 ADR) |
| `07` やりがちな誤り | 誤り 3 (同じループバックを 2 つの VTEP で使う) は error、さらにアドレスの重複も error。誤り 1 (ピアの書き忘れ) は MLAG が定義されていれば warning になるが、このファイルには MLAG がないので出ない。誤り 2 (共有 VTEP の `address` とループバックの ip の食い違い) は、NX-OS 式と区別できないので検査しない |

