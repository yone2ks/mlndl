# MLNDL の考え方

MLNDL (Multi-Layer Network Description Language) が何を書く言語で、どういう考え方で作られているかを説明します。
書き方の規則は [言語リファレンス](reference/README.ja.md) に、個々の決定の経緯は [ADR](decisions/README.md) にあります。

## MLNDL が書くもの

MLNDL は、ネットワークのトポロジーを 1 つの YAML のファイルに書く言語です。書くものは三つの側面に分けられます ([ADR-0005](decisions/0005-mlndl-expressive-scope.md) D1)。

| 側面 | 中身 | 書く場所 |
|---|---|---|
| 物理の構成 | 機器 (箱) と、それをつなぐケーブル・回線 (線) | `layer1` |
| 論理の構成 | VLAN・VXLAN・VRF・IP アドレス、BGP や OSPF のセッション | `layer2`・`layer3`・`control_plane` |
| 物理と論理のつながり | 論理のものが、どの物理のものの上で実現されているか | `attaches_to` |

たとえば「leaf1 の swp51 というポートに 10.1.0.1/31 がある」は、物理のポート (L1 IF)、論理の IF (L3 IF)、その 2 つのつながりの 3 つに分けて書きます。

```yaml
layer1:
  interfaces:
    - {id: leaf1-swp51, node: leaf1, name: swp51}           # 物理のポート
layer3:
  interfaces:
    - id: leaf1-swp51-l3                                     # 論理の IF
      node: leaf1
      name: swp51
      ip: 10.1.0.1/31
      attaches_to: {interface: leaf1-swp51}                  # つながり
```

1 つの事実を分けて書くのは、層ごとに別の問いに答えられるようにするためです。
「このケーブルが切れたら、どの BGP セッションが落ちるか」は、セッション → L3 IF → L1 IF → リンクと、つながりをたどって答えます。

MLNDL の源流は MLNDL 原案 (NAIST, 2011) です。
原案の三層モデル、`attachesTo` (今の `attaches_to`)、ブロードキャストドメインの検索の考え方を受け継ぎ、RFC 8345 (ネットワークトポロジーの YANG モデル) の supporting 関係を下敷きにして作り直しました。

## 層

`layer1` / `layer2` / `layer3` の番号は、RFC 8345 のネットワーク層に振ったもので、OSI の層番号とは一致しません。

- `layer1`: 機器・L1 IF・リンク・LAG。物理の構成
- `layer2`: VLAN・bridge・VXLAN・サブ IF。L2 のセグメントと、その上のトンネル
- `layer3`: VRF・L3 IF・トンネル IF。IP の到達性の起点
- `control_plane`: BGP・OSPF・IS-IS のセッション。どの `layerN` にも属さない ([ADR-0010](decisions/0010-control-plane-separation.md))

## 4 つの関係

MLNDL のエンティティどうしの関係は、次の 4 つに分かれます。それぞれ別のキーで書き、混ぜません ([ADR-0009](decisions/0009-membership-orthogonality.md))。

| 関係 | キー | 意味 | 例 | 見分け方 |
|---|---|---|---|---|
| 実現 (supporting) | `attaches_to` | 下の層のものが上の層のものを支える | L3 IF はポートの上にある、VM はホストの上で動く | それを外すと動かなくなる |
| 所属 | `node` | どの機器のものか | swp51 は leaf1 のポート | それを外すと存在できなくなる |
| 包含 | `parent` | 論理的な箱に入っている (Phase 3 以降) | サブネットは VPC に属する | 外しても動くが、分類から外れる |
| 分類 | `labels` | 参照ではない属性 | サイトは東京、テナントは acme | 参照ではない (値が id を指さない) |

## フラットな一覧と id の参照

MLNDL は、エンティティを種類ごとのフラットな一覧に書き、別のエンティティは `id` で指します。機器の中にポートを、ポートの中に IP を、と入れ子にはしません ([ADR-0005](decisions/0005-mlndl-expressive-scope.md) D2-1)。

- 1 つの L1 IF は、リンクの両端、LAG のメンバー、VLAN のポート、L3 IF の基盤と、多くの所から指されます。一覧が 1 つなら、どこからでも同じ id で引けます
- 2 台にまたがるもの (リンク、MLAG、セッション) は、どちらかの機器の中には書けません。フラットにしておけば、置き場所に迷いません
- RFC 8345 の入れ子の形への変換は、エクスポーターが受け持ちます

そのため id はファイル全体で一意で、L1 IF は `leaf1-swp51` のように機器の id を前に付けて書きます。機器上の名前 (`swp51`) は参照には使わず、`name` に書きます。

## 書くものと、導くもの

MLNDL には、ほかの記述から導けることは書きません。mlndl が参照をたどって導きます。

| 書かないもの | 導き方 |
|---|---|
| VLAN のポートやサブ IF がどの機器のものか | 参照先の L1 IF・LAG の `node` から |
| BGP セッションが eBGP か iBGP か | 両端の AS から |
| セッションの通り道 (どのリンク・LAG・bridge・トンネルを通るか) | 両端の `update_source` の基盤から |
| underlay か overlay か | セッションが運ぶアドレスファミリーと VRF から |
| VLAN の端点 (サーバーの IP など) | VLAN のポート → リンクの対向 → 対向の L3 IF |

導けるものを書けるようにすると、書いた値と導いた値が食い違ったときにどちらが正しいかが決まらなくなります。書くのは 1 か所だけにします。

同じように、同じ関係を実現する方式の名前 (anycast VTEP、vPC、VPLS など) も構文には入れません。関係の形が同じなら 1 つの書き方にし、方式による設定の違いは `device_type` から上位のツールが導きます (ADR-0005 D4 補則の問い 4)。

## 書く範囲

MLNDL が書くのは、ネットワークの**関係が成り立つための情報**です。関係を通って流れる個々の経路やパケットへの処理は書きません ([ADR-0005](decisions/0005-mlndl-expressive-scope.md) D4 補則)。

| 書く | 書かない |
|---|---|
| IF の IP アドレス (到達性の起点) | スタティックルート、経路の再配布ポリシー |
| VRF の Route Target | ACL、NAT、QoS、ポリシールーティング |
| ゲートウェイの VIP、トンネルの送り元・宛先・MTU | IPsec の鍵、パスワードなどの秘匿情報 |
| BFD のタイマー (隣接の成立に効く) | BGP / OSPF のタイマー (成立後のチューニング) |

迷ったときは、秘匿情報か、転送の個々のエントリか、それがないと関係自体が成り立たないか、の順に考えます。

## 規範と注釈

キーには、ネットワークの意味を決めるもの (規範) と、人やツールのための補足 (注釈) があります。

- 規範: `id`・参照・`vlan_id`・`ip` など。値が違えばネットワークが違う。mlndl が厳しく検査する
- 注釈: `role`・`labels`・`description`・`name`。値が違ってもネットワークの意味は変わらない。mlndl は値域を検査しない (推奨の語彙はある)

`role: spine` は自由な文字列で、`tap-aggregator` のような語彙にない値も正しい MLNDL です。
例外は `implementation: container` と `role: hypervisor` の組で、技術的に成り立たないので error にします ([ADR-0003](decisions/0003-role-vocabulary.md)・[ADR-0004](decisions/0004-implementation-role-matrix.md))。

## 言語と実装

- **MLNDL**: 言語の名前。MLNDL で書いたファイルを MLNDL ファイルと呼びます
- **mlndl**: Python で書いた参照実装 (パーサー・検査・エクスポーター)。MLNDL ファイルを読み、検査し、ほかの形に書き出します
- **上位のツール**: MLNDL を読んで使う側。ndl-viz (可視化)、eve-lab-builder (EVE-NG へのデプロイ) など

mlndl は上位のツールのことを知りません。EVE-NG のテンプレートや可視化の色のような、特定のツールのための値は MLNDL に書かず、ツールの側で `device_type` や `role` から決めます。
