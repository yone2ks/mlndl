# はじめの一歩

小さなトポロジーを書き、mlndl で検査して、図にするまでの流れです。[文書の目次](README.ja.md)

MLNDL が何を書く言語かは [MLNDL の考え方](concepts.ja.md)、キーの正確な定義は [言語リファレンス](reference/README.ja.md) にあります。

## 準備

mlndl をインストールします (リポジトリの [README](../README.md))。

```bash
pip install -e ".[dev]"
```

## 1. 機器とケーブルを書く

2 台のルーターを 1 本のケーブルでつなぎます。`first.yaml` に書きます。

```yaml
ndl_version: "1.0"

layer1:
  nodes:
    - {id: rtr-a, role: border, implementation: physical}
    - {id: rtr-b, role: border, implementation: physical}
  interfaces:
    - {id: rtr-a-ge0-0, node: rtr-a, name: Ge0/0}
    - {id: rtr-b-ge0-0, node: rtr-b, name: Ge0/0}
  links:
    - {id: link-rtr-a-rtr-b, endpoints: [rtr-a-ge0-0, rtr-b-ge0-0], link_speed: 100M}
```

- `ndl_version` は必須です。引用符で囲んで書きます
- どのエントリにも `id` を付けます。ほかのエントリは `id` で指します (ケーブルの `endpoints` はインターフェースの `id`)。`id` はファイル全体で一意です
- `name` には機器の上での名前 (`Ge0/0`) をそのまま書きます。`name` は参照には使いません

検査します。

```bash
python -m mlndl validate first.yaml
```

```
OK — no validation errors
```

## 2. 誤りを見る

ケーブルの端に、ないインターフェースを書いてみます (`rtr-b-ge0-0` を `rtr-b-ge0-9` に)。

```
ERROR    layer1.links[0].endpoints[1]: 未定義の L1 インターフェース 'rtr-b-ge0-9' を参照しています
```

行の先頭は重さ (`ERROR` / `WARNING` / `NOTE`)、次がファイルの中の場所です。error が 1 つでもあると終了コードは 1 になります。
どんな検査があるかは [検査の一覧](reference/validation.ja.md) にあります。

## 3. warning と `--strict`

書けるけれど推奨と違う書き方は warning です。たとえばケーブルの `id` を `link-` で始めず、速度を `1000M` と書くと:

```
WARNING  layer1.links[0].id: L1 リンク の ID 'rtr-a-to-rtr-b' は推奨プレフィックス 'link-' で始まっていません (ADR-0002 D7)
WARNING  layer1.links[0].link_speed: link_speed '1000M' は '1G' と書くとそろいます。数値が 1 以上 1000 未満になる単位で書きます (ADR-0021 D3)
OK — no validation errors (2 warnings)
```

warning だけなら終了コードは 0 です。CI で warning も止めたいときは `--strict` を付けます (warning が error になります)。

## 4. IP アドレスとルーティングを書き足す

ケーブルの上に IP アドレスを載せ、2 台のあいだに OSPF の隣接を書きます。`first.yaml` の後ろに足します。

```yaml
layer3:
  interfaces:
    - {id: rtr-a-ge0-0-l3, node: rtr-a, name: Ge0/0, ip: 10.0.0.1/30, attaches_to: {interface: rtr-a-ge0-0}}
    - {id: rtr-b-ge0-0-l3, node: rtr-b, name: Ge0/0, ip: 10.0.0.2/30, attaches_to: {interface: rtr-b-ge0-0}}

control_plane:
  ospf:
    - {id: ospf-wan, nodes: [{node: rtr-a}, {node: rtr-b}]}
  routing_neighbors:
    - id: ospf-adj-rtr-a-rtr-b
      type: ospf
      from: {node: rtr-a, interface: rtr-a-ge0-0-l3}
      to:   {node: rtr-b, interface: rtr-b-ge0-0-l3}
      area: "0.0.0.0"
```

- MLNDL は層ごとに書きます。L1 のインターフェース (ポート) と、その上の L3 のインターフェース (IP アドレス) は別のエントリで、L3 の側から `attaches_to` で L1 を指します
- OSPF の隣接は L3 のインターフェースを指します。隣接がどのケーブルを通るかは書きません。両端の L3 インターフェースの `attaches_to` から mlndl が導きます

L3 のインターフェースではなく L1 のインターフェースを書くと、何を指したかを添えて教えてくれます。

```
ERROR    control_plane.routing_neighbors[0].to.interface: 未定義の L3 インターフェース / トンネル 'rtr-b-ge0-0' を参照しています。'rtr-b-ge0-0' は L1 インターフェース です
```

## 5. 図にする

Cytoscape.js の JSON に書き出すと、[ndl-viz](https://github.com/yone2ks/ndl-viz) で図にできます。

```bash
python -m mlndl export --format cytoscape first.yaml > topology.json
```

出力の形は [Cytoscape.js 出力](exporter-cytoscape.md) にあります。

## 6. もう少し大きな例

VLAN とそのゲートウェイ、サーバーまで書いた 2 拠点の例が [examples/two-sites-ospf.yaml](../examples/two-sites-ospf.yaml) にあります。上の 2 台に、次を書き足したものです。

| 書き足したもの | 区画 | リファレンス |
|---|---|---|
| スイッチとサーバー、拠点 (`labels: {site: tokyo}`) | `layer1` | [layer1](reference/layer1.ja.md) |
| 拠点ごとのユーザー VLAN と、そのポート | `layer2.vlans` | [layer2](reference/layer2.ja.md#vlans) |
| VLAN のゲートウェイ (SVI。`attaches_to: {vlan:}`)、ループバック、サーバーの IP | `layer3.interfaces` | [layer3](reference/layer3.ja.md#interfaces) |

ほかの例は [見本の一覧](README.ja.md#見本) を、id の付け方などは [書き方の推奨](style-guide.ja.md) を見てください。
