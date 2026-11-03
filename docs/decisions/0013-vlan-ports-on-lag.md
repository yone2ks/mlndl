# ADR-0013: VLAN のポート (trunk_ports / access_ports)

- **Status**: Accepted
- **Date**: 2026-10-15 (D7 を 2026-10-23 に追記)
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー
- **Pass**: C (ラウンド4。[評価メモ](evaluations/round4-evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0013](drafts/0013-vlan-ports-on-lag.md)
- **関連**: ADR-0001 (D8 参照キー)、ADR-0002 (D5)、ADR-0005 (D4・D6 `node`)、ADR-0006 (`endpoints`)、ADR-0009 (三構成子)、[ADR-0011](0011-layer3-data-plane.md)、[ADR-0012](0012-subinterfaces.md)

## Context

VLAN が載るポートは `layer2.vlans[].trunk_ports` / `access_ports` に書く。Pass A (drafts/0013) で LAG を指せるようにした。
実機では、VLAN の設定はどのベンダーでも LAG (port-channel / bond / ae) の側にあり、メンバーはそれを継承する。

ラウンド4 Pass C で、参照先の種類をキーで示すこと (ADR-0001 D8) と、`node` を書かないこと (ADR-0005 D6) を決めたので、
本 ADR もそれに合わせて確定する。

## Decision

### D1. ポートは `{interface:}` か `{lag:}` で指す

```yaml
layer2:
  vlans:
    - id: vlan-100
      vlan_id: 100
      trunk_ports:
        - {lag: lag-mlag-server1}      # MLAG: 1 エントリで両ノード
        - {lag: lag-peer-link}         # peer-link も書ける
        - {interface: leaf3-swp5}      # L1 IF
      access_ports:
        - {lag: lag-leaf4-server3}     # サーバー向け bond の access
```

どちらか一方だけを書く。VLAN やサブ IF は指せない。"port" は、ここでは「L2 の設定が載る端点 (L1 IF または LAG)」の意味である。
改名 (`tagged_members` / `untagged_members` 等) は、`layer2.bridges` (drafts/0007) で参照先がさらに広がるときに再検討する。

### D2. `node` を書かない

ノードは `interface` / `lag` から決まる (ADR-0005 D6)。MLAG を指すエントリは両ノードに効く。

Pass A では「任意 (書けば照合)」だったが、サブ IF (ADR-0012 D2) と揃えて書かない形に改めた (ユーザー判断)。
ndl_version 1.x の間は旧形式として受け付け、warning を出したうえで照合する (食い違えば error。MLAG に `node` を書くのも error)。

### D3. LAG のメンバーを VLAN に書かない

| 書き方 | Severity |
|---|---|
| 同じ VLAN に LAG とそのメンバーの両方を書く | error (二重表現) |
| LAG があるのに、メンバーだけを書く | warning (`{lag:}` で書くよう促す) |

### D4. 同じ VLAN に同じ端点を 2 回書かない

`trunk_ports` と `access_ports` の両方、または同じリストに同じ端点が 2 回出たら error。

### D5. VLAN ID の重複検査は LAG のノードに展開する

「同じノードの上で別の VLAN エントリが同じ `vlan_id` を使っていないか」は、MLAG を指すエントリを両ノードに展開してから検査する。
エクスポーター (cytoscape) も、VLAN の所属を両ノードに出す。

### D6. 書けるが、検査しないもの

- **peer-link**: 実機では全 VLAN を暗黙に通すことが多い。書いても書かなくてもよい
- **サーバー側の bond**: `access_ports` に書くかどうかは書き手に任せる (VM の vNIC を書く近似との整合。drafts/0007)
- **native VLAN の一致**: MLAG は 1 エントリなので両ノードで食い違いようがない。LACP の両端の一致は検査しない

### D7. 補則: VLAN の端点の導出 (2026-10-23 追記)

> ADR-0018 (2026-11-03): 事業者網の箱の中の転送は `layer2.bridges` に書く。VLAN の端点の導出は bridge をはさんで広げない (1 ホップのまま)。

VLAN のポート (D1) はスイッチ側の端点である。その対向で VLAN のフレームを受ける機器の IF と IP は、
**構文を足さず、既存の参照 (id) をたどって導ける**。ツール (エクスポーター・validator 等) はこの手順に従い、
IF の `name` の一致では引かない (`name` は参照ではない。ADR-0011 D3)。

ndl-viz に入れた表示を 5 エージェントで評価した際、「`name` の一致で引いているので裏付けがない」と判定したが、
ユーザーの指摘 (スイッチの IF とその対向がわかれば確定できる) を受けて再評価し、参照の連鎖で確定できる範囲を定めた。

#### 手順 (1 ホップ)

1. **ポートの L1 IF**: `{interface: X}` なら X。`{lag: L}` なら L のメンバー (MLAG は両ノードのメンバー)
2. **対向**: X を `endpoints` に含む L1 リンクのもう一方の端点 Y と、そのノード H (ADR-0006)。リンクがなければ端点はない
3. **ポートを持つノード同士のリンクは除く**: Y、または Y をメンバーに持つ LAG が、同じ VLAN のポートでもあれば数えない
   (スイッチ間の trunk、D6 によりポートとして書いたサーバーの bond)
4. **端点の L3 IF** (H の L3 IF)。Lh は Y をメンバーに持つ H の LAG (bond)
   - フレームが untagged (`access_ports`、または `native: true` の `trunk_ports`): `attaches_to` が `{interface: Y}` か `{lag: Lh}` のもの
   - フレームが tagged (native でない `trunk_ports`): `attaches_to` が `{subinterface: S}` で、S が Y か Lh の上にあり、
     S の `vlan_id` が VLAN の `vlan_id` と等しいもの
5. **H の先はたどらない**: L2 スイッチの先のホスト、ハイパーバイザの上の VM は端点にならない

同じポートのノードから同じ H に複数の脚で届き、H 側で 1 つの LAG にまとまるもの (MLAG の両脚の片側、bond のメンバー) は 1 つの端点にまとめる。

#### 確かさ (`resolution`)

| 値 | 条件 | 確かさ |
|---|---|---|
| `direct` | untagged で、L3 IF がちょうど 1 つ | 参照で確定 |
| `tag_match` | tagged で、タグの一致するサブ IF の L3 IF がちょうど 1 つ | 推定。ADR-0012 D3 はタグと VLAN を照合しない (VLAN translation / QinQ で番号が同じでも別の VLAN になりうる) |
| `ambiguous` | 候補が 2 つ以上 | 決まらない。候補をすべて示す |
| `no_l3` | 端点の L1 IF は確定、L3 IF がない | IF まで確定。H が L2 スイッチ・ハイパーバイザ・IP のないホストのどれかは区別しない |

#### 意味と範囲

- **呼び方**: 端点の機器は VLAN の「メンバー」ではなく「**VLAN の端点**」(endpoint on VLAN) と呼ぶ。VLAN のポートは D1 のスイッチ側の端点だけで、
  端点との関係は `attaches_to` / `parent` / `labels` (ADR-0009) のどれでもない、参照から求める関係である (broadcast_domain クエリと同じ種類)
- **確定するのは宣言上の構成**: 802.1X / MAB / MAC ベースの動的 VLAN、voice VLAN、private VLAN、shutdown・err-disable、STP blocking などの
  運用中の状態は表さない (ADR-0005 D4)
- **端点はポートのノードにローカル**: EVPN で VLAN を VNI でストレッチしても、ほかの VTEP のノードの端点にはならない
- **1 ホップで止める**: 途中のスイッチの VLAN 設定が書かれていない区間を「すべて通す」とみなすと、暗黙の前提が増える。多段の到達はクエリ層 (Phase 3+) で扱う
- **ハイパーバイザ上の VM**: 親のポートの VLAN を引き継ぐとはみなさない。`layer2.bridges` (drafts/0007、Phase 2) で決める

#### 検査

| チェック | Severity |
|---|---|
| `direct` / `tag_match` の端点の `ip` / `ipv6` が、その VLAN の SVI (`attaches_to: {vlan:}`) のどのサブネットにも入らない (同じアドレスファミリーの SVI がない VLAN は検査しない) | info |

L2 だけのセグメントや設計途中の構成がラボでは普通にあるので、warning にはしない。

#### 実装

- 導出: `src/mlndl/derive.py` の `vlan_endpoints()`。エクスポーターと validator が同じ関数を使う
- エクスポーター (`cytoscape.py`): `vlan_member` エッジに `endpoints` を出す (ポートのノードごと)。ビューワは参照をたどり直さず、これを表示する

#### 見送った案

- **IF の `name` の一致で L3 IF を引く** (最初の ndl-viz の実装): ADR-0011 D3 に反する。L1 と L3 で名前が違う (`eth0` / `ens3`、bond) と誤る
- **「L3 IF が 1 つならそれ」の予備ルール**: trunk の先のハイパーバイザで、別の VLAN の IP をこの VLAN のものとして示す
- **VLAN の設定のない透過スイッチを素通りして多段をたどる** (example-author): 本文「1 ホップで止める」
- **SVI のサブネットで表示を絞る / warning** (network-tech-reviewer): 端点は参照で確定するので絞らない。サブネット外は info に留める
- **「VLAN のメンバー」と呼ぶ**: 本文「呼び方」

## Pass A との差分

| 項目 | Pass A (drafts/0013) | Pass C |
|---|---|---|
| LAG の指し方 | `{interface: <LAG id>}` (新キーは作らない) | `{lag: <LAG id>}` (ADR-0001 D8) |
| `node` | 任意 (書けば照合) | 書かない (1.x の間は warning で受け付け、照合する) |
| 受付の表 | ADR-0012 D5 の表に行を追加 | スキーマ (`interface` / `lag` のどちらか一方) |

## References

- [ラウンド4 横断評価メモ](evaluations/round4-evaluation.md)、設計比較 `evaluations/adr0013/`、`evaluations/round4/passc/`
- IEEE 802.1AX (Link Aggregation)
