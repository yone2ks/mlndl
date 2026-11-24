# 書き方の推奨

MLNDL の YAML を読みやすく、ファイルどうしでそろった形で書くための推奨です。[文書の目次](README.ja.md)

ここに書くのは推奨で、守らなくても valid です (推奨プレフィックスだけは warning になります)。
言語の決まり (何が error か) は [言語リファレンス](reference/README.ja.md) にあります。
推奨は examples と言語リファレンスの例で使っている書き方から取りました。

## id の付け方

`id` は文法 (英小文字・数字・ハイフン、63 文字まで。[型](reference/types.ja.md#id)) に従い、ファイル全体で一意にします。
id は参照に使う名前なので、機器の上での名前とは別に、ファイルの中で引きやすい名前を付けます。

| エンティティ | 形 | 例 |
|---|---|---|
| 機器 | 役割と番号、またはサイトと役割 | `spine1`、`leaf1`、`rtr-a`、`tokyo-core` |
| L1 インターフェース | `<機器の id>-<機器上の名前>` (小文字に、記号はハイフンに) | `leaf1-swp51`、`rtr-a-ge0-0`、`leaf3-xe-0-0-4` |
| L1 リンク | `link-<端の機器>-<端の機器>`。同じ 2 台のあいだに 2 本以上あれば末尾で分ける | `link-spine1-leaf1`、`link-spine1-leaf3-a` |
| LAG | `lag-<機器>-<名前か相手>` | `lag-leaf1-bond0`、`lag-leaf1-server1` |
| Ethernet Segment | `es-<相手>` | `es-server1` |
| VLAN / VNI | `vlan-<番号>` / `vni-<番号>` | `vlan-100`、`vni-10100` |
| L1 IF の上の L3 IF | `<L1 IF の id>-l3` | `leaf1-swp51-l3` |
| ループバック | `<機器の id>-lo` (2 つ以上なら `-lo0`、`-lo1`) | `leaf1-lo` |
| SVI | `<機器の id>-vlan-<番号>` | `leaf1-vlan-100` |
| VRF | `vrf-<名前>` | `vrf-tenant-a` |
| VTEP | `vtep-<終端する機器>` | `vtep-leaf1-leaf2`、`vtep-border1` |
| セッション | `bgp-peer-<機器>-<機器>` / `ospf-adj-…` / `isis-adj-…`。同じ 2 台に 2 本目があれば用途を末尾に | `bgp-peer-spine1-leaf1-overlay` |

推奨プレフィックス (`link-`・`lag-`・`vlan-` など) の一覧と、従わないときの warning は [型](reference/types.ja.md#推奨プレフィックス) にあります。

## name は機器の上での名前

`name` には、その機器の設定や CLI に出てくる名前をそのまま書きます。`name` は参照に使わないので、機器ごとの書き方の違いをそろえる必要はありません。

- インターフェース: `swp51`、`Ge0/0`、`xe-0/0/4`、`eth0`
- LAG: `bond0`、`Port-Channel10`、`ae0`
- SVI: 機器によって `Vlan100` (Cisco / Arista)、`vlan100` (Cumulus)、`irb.100` (Junos) など。examples では `Vlan100` と書いている

機器の表示名 (`layer1.nodes[].name`) は図に出す名前です (`Spine-1`)。

## 引用符が要る値

YAML (mlndl は YAML 1.1 の読み方) は、引用符のない値を数や真偽値として読むことがあります。次は引用符で囲みます。

| 値 | 書き方 | 引用符がないと |
|---|---|---|
| `ndl_version` | `"1.0"` | `1.10` が数の `1.1` になる (error) |
| RD・Route Target | `"65001:10"` | `65001:10` が 60 進数の整数 `3900070` になる (error) |
| OSPF の `area` | `"0.0.0.0"` | `0` も書けるが、ドット区切りにそろえる |

`lacp: {mode: static}` のように、列挙の値は引用符なしで書けるものだけにしてあります (以前の `on` は `true` と読まれるので `static` に改名しました。[ADR-0028](decisions/0028-names-and-types.md))。

## 書く順番

区画は `ndl_version` → `meta` → `layer1` → `layer2` → `layer3` → `control_plane` の順に書きます。区画の中は、参照される側を先に書きます。

- `layer1`: `nodes` → `interfaces` → `links` → `lags` → `ethernet_segments`
- `layer2`: `vlans` → `bridges` → `vteps` → `vxlans` → `subinterfaces`
- `layer3`: `vrfs` → `interfaces` → `tunnel_interfaces`
- `control_plane`: インスタンス (`bgp` / `ospf` / `isis`) と `bfd` → `routing_neighbors`

一覧の中は、サイトや機器ごとにまとめ、コメントの見出し (`# ── tokyo ──`) で区切ると読みやすくなります。

## 1 行で書くか、複数行で書くか

- キーが少なく 1 行に収まるエントリは、フロー形式 (`{id: ..., node: ...}`) で 1 行に書き、列をそろえる
- キーが多いもの、コメントを付けたいものは、ブロック形式で 1 キー 1 行に書く

どちらで書いても意味は同じです。同じ一覧の中では、なるべくどちらかにそろえます。

## 書かなくてよいもの

- `vrf`: default VRF なら書きません。`vrf: vrf-default` のように名前を付けて書くなら、その VRF を `layer3.vrfs` に定義します
- 既定値のないキー (`lacp`、BFD のタイマー、`redundancy_mode` など): 分からないとき、決めていないときは書きません。書かなければ「書いていない」の意味で、値を推測して埋めません

## description と labels

- `description`: 回線 ID・契約帯域・事業者名などの補足を、自由な文で書きます。書式は決めず、ツールは中を読みません ([ADR-0017](decisions/0017-sites-and-wan.md))
- `labels`: 機器の分類 (サイト・テナント・環境など) をキーと値で書きます。サイトは `labels: {site: tokyo}` (値は `site-tokyo` ではなく名前そのまま)。軸の名前は [labels の推奨の軸名](label-vocabulary.md) を使います
