# ADR-0012: 802.1Q サブインターフェース

- **Status**: Draft — 実装済み (2026-10-05)。Pass B / C は未実施
- **Date**: 2026-10-05
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **Pass**: A (設計ラウンドで 5 エージェントの評価を取り、割れた 2 点をユーザーが判断した上で策定)
- **関連**: ADR-0001 (attaches_to), ADR-0002 (ID 命名 D1・D5・D7), ADR-0005 (D2-2 ケース C・D2-3), ADR-0009 (parent), drafts/0011 (layer3 データプレーン)

## Context

ADR-0011 で layer3 データプレーンの中核を実装したが、サブインターフェースは Known Gap として残った。
支社の router-on-a-stick (ルーターの物理ポート 1 本に 802.1Q タグ付きのサブ IF `eth0.10` / `.20` を作り、
それぞれに IP を振る構成) が書けない。実測は `evaluations/adr0011/topologies/T3_branch_router_on_a_stick.yaml`。

ADR-0005 D2-2 ケース C は `layer2.subinterfaces: id, parent (L1 IF), vlan_id` を予告しており、
ADR-0011 D8 で親の参照を `parent` から `attaches_to` に改めた。それ以外の細部は決まっていなかった。

## Decision

### D1. `layer2.subinterfaces` に置く

```yaml
layer2:
  subinterfaces:
    - id: subif-br1-eth0-10
      attaches_to: {interface: br1-eth0}        # 親: L1 IF または LAG
      vlan_id: 10                               # このリンク上の 802.1Q タグ番号
      name: eth0.10                             # 機器上の名前
      description: users
layer3:
  interfaces:
    - id: br1-eth0-10
      node: br1
      interface: eth0.10
      attaches_to: {interface: subif-br1-eth0-10}
      ip: 192.168.10.1/24
```

- ADR-0005 D2-2 の「物理と、その上に終端する機能を別エンティティにして `attaches_to` で結ぶ」規範に沿う。
  L1 は物理トポロジー (ADR-0005 D1) なので `layer1.interfaces` には置かない。`L3Interface` に `vlan_id` を持たせる案は、
  タグによる多重化という L2 の操作を L3 のエンティティに混ぜることになる
- **今回扱うのは L3 の routed サブ IF のみ**。L2 のサブ IF (Cisco EVC の service instance、bridge-domain への接続) は
  ベンダー横断で別物として扱われており (技術レビュー)、L2 拡張と合わせて別途設計する
- `subinterfaces` には `ip` / `vrf` を書かない。L3 の情報は必ず `layer3.interfaces` から `attaches_to` で載せる

### D2. `node` は持たない

ノードは親 (L1 IF / LAG) から必ず導出できる。持たせると「`node: r1` なのに親 IF は r2 のもの」が書けてしまう。
ADR-0010 / ADR-0011 で繰り返し問題にした二重表現を作らない。

`L3Interface` は `node` と `attaches_to` を両方持つが、これはループバックのように親を持たない L3 IF があり、
`attaches_to` が任意だからである。サブ IF は親が必須なので、事情が違う。

### D3. `vlan_id` はタグ番号であり、VLAN エンティティへの参照ではない

`vlan_id` は IEEE 802.1Q の VID (1..4094。0 と 4095 は予約) で、**このリンク上でフレームに付くタグ番号**を表す。
`layer2.vlans` のエンティティは参照しない。`vlan: vlan-10` のような参照フィールドは持たない。

| 案 | 支持 | 採否 |
|---|---|---|
| `vlan_id` (タグ番号) のみ | spec-architect / dsl-designer / network-tech-reviewer | **採用** (ユーザー判断) |
| `vlan` (VLAN 参照) のみ | example-author | 却下 |
| 両方 (`vlan` は任意、両方あれば一致を検証) | linguist | 却下 |

理由:

- タグはリンク上だけの番号であり、VLAN エンティティと一致しない実務ケースがある: VLAN の書き換え
  (Cisco `switchport vlan mapping`、Juniper `vlan-map`)、Q-in-Q、拠点ごとの番号の再利用
- ルーター側 (routed サブ IF の終端) は VLAN オブジェクトを持たない。`encapsulation dot1Q 10` は
  「タグ 10 のフレームをこのサブ IF に対応付ける」規則である (IEEE 802.1Q §6.9 / 各ベンダー文書)
- VLAN 参照を必須にすると、スイッチを書かない支社ルーター単体の構成でサブ IF が書けない
- 両方を持たせる案は、ADR-0011 で塞いだ SVI の三重表現 (`interface` / `vlan` / `attaches_to`) と同じ構図になる
- 参照のみの案は、実証エージェント自身が「タグの書き換えは書けない」と報告している

**ルーター側のサブ IF とスイッチ側の VLAN が同じブロードキャストドメインにあるか**は、
サブ IF の親 IF から L1 リンクをたどり、対向ポートの `trunk_ports` に同じタグ番号の VLAN があるかで導出する。
物理的にもこれが正確であり、将来の `broadcast_domain` クエリはこの経路で実装する。

**この照合を validator の検証にはしない**。設計ラウンドでは「親ポートが同じ番号の VLAN の trunk に載っているか」を
検証する案 (dsl-designer は warning、example-author は error) が出たが、Cisco / Arista では routed サブ IF の
親ポートは switchport にできない (排他) ため、正しく書いた構成ほど誤検知を出す (network-tech-reviewer)。

### D4. LAG 上のサブ IF は `{interface: <LAG の id>}` で親を指す

`Port-channel1.100` / `bond0.100` / `ae0.100` は全主要ベンダーにあり、DC でも WAN でも頻出である (技術レビュー)。

| 案 | 支持 | 採否 |
|---|---|---|
| `{interface:}` の参照先に LAG を加える | network-tech-reviewer / example-author | **採用** (ユーザー判断) |
| `{lag:}` キーを新設 | dsl-designer | 却下 |
| 範囲外 | spec-architect | 却下 |

- ADR-0005 D2-3 は `{interface: X}` を「X をグローバル一意 ID (ADR-0002 D5) で解決し、層をまたいで指す」と定義している。
  LAG も機器上ではインターフェース (RFC 8345 の termination point) であり、この定義に収まる。ADR-0001 の改訂は不要
- `{lag:}` 新設は、参照先の種類が YAML で見えるという利点があるが、ADR-0001 の 1 キー集合を変え、
  全ての `attaches_to` の検証に影響する
- 範囲外にすると、導入直後に「LAG 上に作れない」と足りなくなる可能性が高い

**同じ機構で、routed LAG (LAG 自体に IP を振る構成) も書けるようにした**: `L3Interface.attaches_to: {interface: <LAG id>}`。

dsl-designer の懸念 (「呼び出し元ごとに `{interface:}` が指せる ID 空間が変わる」手法が ADR-0011 の VLAN に続いて 2 回目になる) は
もっともなので、ID 空間をエンティティごとに 1 つの表に固定する (D5)。

### D5. `attaches_to: {interface: X}` が指せる ID 空間

| `attaches_to` を持つエンティティ | X が指せるもの | 根拠 |
|---|---|---|
| `layer1.nodes` / `layer1.interfaces` | L1 IF | ADR-0001 |
| `layer2.subinterfaces` | L1 IF ∪ LAG | ADR-0012 D4 |
| `layer3.interfaces` | L1 IF ∪ LAG ∪ VLAN ∪ サブ IF | ADR-0011 D3 (VLAN) / ADR-0012 D4 (LAG・サブ IF) |
| `layer3.routing_adjacencies` | L1 IF | 変更なし (ADR-0010 で保留中) |

この表にない組み合わせは error である。新しい組み合わせを足すときは、この表を改訂する ADR を書く。

**前提として、L1 IF / LAG / VLAN / サブ IF の ID は互いに重複してはならない** (ADR-0002 D5)。
`{interface: X}` は X をこれらの空間で引くため、重複すると解決先が曖昧になる。これを validator の error にした
(これまで ADR-0002 D5 は規範としてあったが、検証されていなかった)。

### D6. 命名

| 項目 | 決定 | 根拠 |
|---|---|---|
| セクション名 | `subinterfaces` (1 語) | Cisco / OpenConfig と一致 |
| 機器上の名前 | `name` | `L1Interface` と同じ。`interface` にすると `attaches_to.interface` と同じ語が同一モデルに 2 つ並ぶ |
| タグ | `vlan_id` | `layer2.vlans[].vlan_id` と同名だが、どちらも IEEE 802.1Q の 12 bit VID であり意味は同じ。用法 (宣言か、ポート上のタグか) が違うだけ |
| ID | `subif-<node>-<親 IF>-<タグ>` (例 `subif-br1-eth0-10`) | ADR-0002 D7 の推奨プレフィックス。違反は warning |

ADR-0005 D2-2 ケース C の例 `leaf1-swp1-100` はプレフィックスがなく、L1 IF の ID と区別できないため改める。

### D7. バリデーション規則

| チェック | Severity |
|---|---|
| `vlan_id` が 1..4094 (型で検証) | error |
| `attaches_to` が `{interface:}` 形式か (文字列や `{node:}` / `{link:}` は不可) | error |
| 親が L1 IF または LAG として定義されているか | error |
| 同じ親の上でタグが重複していないか | error |
| L1 IF / LAG / VLAN / サブ IF の ID が互いに重複していないか | error |
| `L3Interface` がサブ IF / LAG を指すとき、そのノード (群) に `L3Interface.node` が含まれるか。MLAG 上のサブ IF は両ノードのもの | error |
| ID の推奨プレフィックス `subif-` | warning |

**検証しないもの**: タグ番号と `layer2.vlans` の照合 (D3)。

## Consequences

### 良い影響

- 支社の router-on-a-stick が書ける (`tests/fixtures/valid_subinterface.yaml`)
- LAG 上のサブ IF と routed LAG が書ける
- 既存 fixture の変更は 0 行 (純粋な加算)
- `{interface:}` が指せる ID 空間が表で固定され、ID のグローバル一意性が初めて検証される

### 悪い影響 / トレードオフ

- **書けないもの**:
  - Q-in-Q (802.1ad)。入れる場合は `stag_vlan_id` / `ctag_vlan_id` (ADR-0002 の予約語) を使い、
    単一タグと Tagged Union にする (`GatewayRedundancy` と同じ形)。今の `vlan_id` を単一タグの既定として残せば非破壊で拡張できる
  - ネイティブ (タグなし) サブ IF (Cisco `encapsulation dot1Q 1 native`)。タグなしの通信は親 IF に載せた `L3Interface` で表す
  - L2 のサブ IF (service instance / EFP)、VLAN の書き換え
- スイッチ側の `trunk_ports` は LAG を指せない (`PortRef.interface` は L1 IF のみ)。LAG の trunk はメンバーの物理ポートを
  列挙するしかない。サブ IF とは独立した問題として残す (設計ラウンドで example-author が発見)
- ルーター側のサブ IF とスイッチ側の VLAN のつながりは、YAML の参照としては書かれない (D3)。導出が必要

### 影響を受けるコンポーネント

- スキーマ: `schema/layer2.py` (`Subinterface`、`L2Layer.subinterfaces`)
- バリデーター: `validator.py` (D7、ID 空間の重複検査、`L3Interface` の参照先と node 所属の拡張)
- エクスポーター: `exporter/cytoscape.py` (ノードの `subinterfaces`、`l3_interfaces[].kind: subinterface`、routed LAG の `lag`)
- fixture: 新規 `tests/fixtures/valid_subinterface.yaml`
- テスト: 新規 `tests/test_subinterfaces.py` (29 件)。新しい検証規則 9 件は、それぞれを無効化すると対応するテストが落ちることを確認した
- 文書: CLAUDE.md、ADR-0005 (D2-2 ケース C・D2-3・D3-1 の実装同期)、ADR-0011 (Known Gap の更新)

## Alternatives Considered

上の D3・D4 の表のほか:

- **`layer1.interfaces` に論理 IF として置く**: 却下 — L1 は物理トポロジー (ADR-0005 D1)
- **`L3Interface` に `vlan_id` を持たせる**: 却下 — L2 の操作を L3 に混ぜる。L3 を持たないサブ IF の拡張余地もなくなる
- **`layer1.interfaces[].subinterfaces` にネスト**: 却下 — フラットなコレクションとグローバル一意 ID の方針 (ADR-0005 D2-1 / ADR-0002 D5) に反する
- **`node` を持たせて `L3Interface` と形を揃える**: 却下 (D2)
- **サブ IF の ID にドットを許す (`br1-eth0.10`)**: 却下 — ADR-0002 D1 の正規表現の変更になる。機器上の名前は `name` に書く
- **Q-in-Q を今回入れる**: 却下 — router-on-a-stick に不要。単一タグとの分岐を持ち込むと型設計の論点が増える

## 申し送り

- `{vlan:}` キーへの移行検討: dsl-designer は、VLAN も `{interface: vlan-100}` ではなく `{vlan: vlan-100}` で指す方が
  明確になると指摘した。今回は D5 の表で ID 空間を固定して対処したが、将来 `attaches_to` のキー体系を見直す際の論点として残す
- MLAG 上の routed サブ IF は実運用では稀 (技術レビュー)。現状は禁止も警告もしない
- LAG のメンバーポート上にサブ IF を作る構成 (多くのプラットフォームで不可) は検出していない
- `PortRef.native` の命名 (ADR-0011 未解決 1) は、L2 のサブ IF を設計する際に合わせて決める

## References

- 関連 ADR: ADR-0001, ADR-0002 (D1・D5・D7), ADR-0005 (D2-1・D2-2・D2-3・D3-1), ADR-0009, drafts/0011
- 設計比較 YAML: [`evaluations/adr0012/`](../evaluations/adr0012/README.md)
- IEEE Std 802.1Q-2022 §6.9 (タグ付け)・§9.6 (VID の値域) / IEEE Std 802.1ad (Q-in-Q)
- RFC 8345 (termination point) / OpenConfig `openconfig-interfaces` (subinterfaces) / `openconfig-vlan`
