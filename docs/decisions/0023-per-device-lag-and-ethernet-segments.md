# ADR-0023: 機器ごとの LAG と `ethernet_segments` — MLAG / vPC / MC-LAG / ESI-LAG を 1 つの形で書く

- **Status**: Accepted (2026-11-08 に実装)
- **Date**: 2026-11-08
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: C (5 エージェントの検討を 5 回行った。下書きはない。最初の案は廃棄した。下の「経緯」)
- **関連**: [ADR-0022](0022-diagram-granularity.md) (記載の粒度)、ADR-0001 D8 (キーが参照先の種類を示す)、ADR-0005 D4 補則 問い 4 (方式名を構文に入れない)・D6 (`node` の持ち方)、
  ADR-0012 (サブ IF)、ADR-0013 (VLAN のポート)、[drafts/0014](drafts/0014-vteps.md) (VTEP)、ADR-0018 D1 (bridge のポート)、ADR-0020 (注釈の綴りに頼る検査をやめた)

## Context

`layer1.lag` は `type: lacp` (1 台の bond) と `type: mlag` (2 台にまたがる 1 つの bond) の Discriminated Union だった。

```yaml
lag:
  - {id: lag-peer-link, type: lacp, node: leaf1, members: [leaf1-swp49, leaf1-swp50]}
  - id: lag-mlag-server1
    type: mlag
    nodes: [leaf1, leaf2]               # ちょうど 2 台
    members: [leaf1-swp3, leaf2-swp3]
    peer_link: lag-peer-link            # 片側の LAG しか指せない
    peer_link_interface: peerlink.4094  # 誰も読まない必須の文字列
    domain_id: 10
    system_mac: "44:38:39:ff:00:0a"
    client_lag: lag-server1-bond0       # 根拠のない片方向の参照
```

問題:

- ペアの属性 (`peer_link` / `domain_id` / `system_mac`) を bond ごとに繰り返し、食い違っても検査しない
- EVPN multihoming (ESI-LAG) を書けない。ESI は 2 台以上でもよく、固定のペアがなく (server1 は leaf1 + leaf2、server2 は leaf2 + leaf3)、ピアリンクもない
- 実機では、MLAG / vPC / MC-LAG / ESI-LAG のどれでも **LAG の IF は機器ごとにある** (leaf1 の Port-Channel10 と leaf2 の Port-Channel10 を vPC 10 / clag-id で結ぶ。
  ESI-LAG は機器ごとに名前が違ってもよく、Juniper なら ae0 と ae5)。2 台にまたがる 1 つの bond は実機にない
- スタック / VSS / Virtual Chassis / IRF は逆に、複数の筐体が 1 台の論理機器になり、筐体をまたぐ LAG も 1 つの port-channel である

### 経緯

最初の案 (旧 ADR-0022 の案。コミットしていない) は、MLAG の bond を `type: multi_chassis` にし、ペアの属性を 2 台のノードの `multi_chassis_domain` に置いた。
ユーザーの意図は「MLAG と ESI-LAG を統合的に扱う前提で言語を設計する」だったが、この案は MLAG の形 (ちょうど 2 台の固定ペアとペアの属性) に寄っていたので廃棄した。
やり直しの検討で、ユーザーが 2 点を指摘した。

1. 構成図の粒度として、MAC アドレス相当は書かない (→ ADR-0022)
2. 同じ LACP でも、MLAG かスタックかで LAG の IF が出てくるかどうかが変わる

2 から、LAG の表し方を (i) 2 台にまたがる 1 つの bond (今のまま) と (ii) 機器ごとの LAG + 束ねる関係で比べ、ユーザーが (ii) を選んだ。

## Decision

### D1. `layer1.lag` は機器 1 台の LAG。`type` をなくし、`name` を足す

```yaml
lag:
  - {id: lag-leaf1-server1, node: leaf1, name: bond1, members: [leaf1-swp1], lacp: {mode: active}}
  - {id: lag-leaf2-server1, node: leaf2, name: bond1, members: [leaf2-swp1], lacp: {mode: active}}
```

- `node` は 1 台。`name` は機器上の名前 (`Port-Channel10` / `bond0` / `ae0`)。参照ではない (ADR-0011 D3 と同じ)
- スタック / VSS / Virtual Chassis / IRF は 1 つの L1 ノードで、筐体をまたぐ LAG もここに 1 つ書く。どの IF がどの筐体にあるかは書かない (`parent` は先送り)
- drafts/0014 は `lag.type: lacp | mlag` を「持つフィールドの形が違うので型を分ける」例に挙げていた。
  LAG を機器ごとにすると、MLAG の LAG も LACP の LAG も形が同じになり、型を分ける理由がなくなった

### D2. 複数の機器の LAG を相手から 1 本に見せる関係は `layer1.ethernet_segments`

```yaml
ethernet_segments:
  - id: es-server1                                        # 推奨プレフィックス es-
    members: [{lag: lag-leaf1-server1}, {lag: lag-leaf2-server1}]
```

- 名前は RFC 7432 の Ethernet Segment (「お客さまのサイトを 1 台以上の PE につなぐイーサネットのリンクの集まり」)。
  MLAG / vPC / MC-LAG もこの一般化として読める。方式名は構文に入れない (ADR-0005 D4 補則 問い 4。VTEP と同じ)。
  どの方式で実現するかは `device_type` から上位のツールが決める
- 置き場所は `layer1`。中身は L1 の LAG / L1 IF を束ねることだけで、VLAN / VNI などの L2 の転送の属性を持たない。
  VLAN と bridge は ES を参照する側 (L2 → L1)。`layer1.lag` が L1 IF を束ねるのと同じ構図である。
  `layer2.vteps` は L2 の転送の端点なので L2 にあり、置き場所が違っても矛盾しない
- キー: `id`、`name` (任意)、`members`、`redundancy_mode` (任意。D4)、`description`。
  ESI の値・LACP system-id・domain_id・vPC 番号 / clag-id は書かない (ADR-0022)
- `members` は 2 つ以上で、機器はすべて別。1 台だけの LAG は `layer1.lag` に書けば足りる
- 名前について: `ethernet_segment` は EVPN の語で、MLAG / vPC だけの現場ではなじみが薄い (ユーザー)。
  4 人が `ethernet_segments` を、ネットワーク技術の担当が `multihoming_groups` を推し、ユーザーが `ethernet_segments` を選んだ。
  `multihoming` は同じトポロジーにある BGP のマルチホーミング (複数 ISP) と取り違えるおそれがある。なじみの薄さは、言語リファレンスに方式との対応表を置いて補う

### D3. 脚は `{lag:}` か `{interface:}`

```yaml
ethernet_segments:
  - id: es-fw1
    members: [{interface: leaf3-xe-0-0-4}, {interface: leaf4-xe-0-0-4}]
    redundancy_mode: single_active
```

- EVPN multihoming の single-active では、CE が LAG を組まず (2 本の独立したリンク、active-standby の NIC チーミング)、
  PE も port-channel / ae を作らずに物理 IF に直接 ESI を設定するのが普通である (Juniper・Arista・SR Linux)。
  LAG しか指せないと、実機にない「中身 1 本の LAG」を書かせることになる
- 形は VLAN のポート (ADR-0013) と同じキー付きの形。参照先の種類をキーで示す (ADR-0001 D8)。
  1.0 の後に「文字列の並び」から「キー付き」に変えると破壊的な変更になるので、今キー付きにする。後からキー (`{subinterface:}` など) を足すのは加算的である
- LAG のメンバーの IF を脚にすると、LAG を指すよう warning を出す

### D4. `redundancy_mode` は任意で、既定値を持たない

- 値は `all_active` (脚がそろって転送する) と `single_active` (同時に転送するのは 1 本)
- 構成図の粒度に入る (ADR-0022 D1)。single-active なら使える帯域が 1 本分になり、運用の図でも active-active と active-standby を描き分ける。
  VRRP の `priority`・LACP の `mode` と同じ粒度である
- どの脚が転送するか (DF) は書かない。DF 選出で決まり、VLAN ごとに入れ替わるので、構成図からは決まらない
- 既定値は置かない。書かなければ「書いていない」で、`all_active` で埋めない (ndl-viz の「推定で埋めない」と同じ)。
  MLAG / vPC は常に all-active なので、書く情報がない (書いてもよい)。
  試し書きの担当は「省略が書き忘れか未検討か区別できない」として既定 `all_active` を推したが、ほかの 4 人は「明示した all-active」と「書いていない」の区別を残す側だった
- 値の語は RFC 7432 の all-active / single-active から取った。方式名ではなく振る舞いの種類である。言語学の担当は、値が EVPN を思わせること、
  `mode` という語が `lacp.mode`・`gateway_redundancy[].mode` に続いて 3 つ目になることを懸念として残した

### D5. `{ethernet_segment:}` を受けるのは VLAN のポートと bridge のポートだけ

```yaml
layer2:
  vlans:
    - {id: vlan-100, vlan_id: 100, trunk_ports: [{ethernet_segment: es-server1}]}   # 脚の全機器に効く
layer3:
  interfaces:   # routed / サブ IF / SVI は機器ごとに書き、機器ごとの LAG を指す
    - {id: leaf1-bond5, node: leaf1, name: bond5, attaches_to: {lag: lag-leaf1-fw1}, ip: 10.250.0.1/29}
```

- VLAN のポート (ADR-0013) と bridge のポート (ADR-0018 D1) は `{interface:}` / `{lag:}` / `{ethernet_segment:}` のどれか 1 つ。ES は脚の全機器に効く
- bridge のポートで受けるのは、事業者網を PE ごとのノードで書き、拠点の CE が 2 台の PE に冗長に接続する場合のため。
  ADR-0017 の基本形 (事業者網を箱ノード 1 つで書く) では使わない。DSL 設計の担当は VLAN のポートだけにする案を推した (4 対 1)
- L3 IF とサブ IF の `attaches_to` は ES を指せない。機器ごとに IP や設定が違うので、機器ごとの LAG を `{lag:}` で指す。
  `ATTACH_KEYS` (ADR-0001 D8) は変えない。`attaches_to: {ethernet_segment:}` を書くと、機器ごとの LAG を指すよう示す error にする
- routed だけの構成 (VLAN を載せない MLAG) でも、ES を書けば「この 2 台の LAG が相手から 1 本に見える」ことが YAML に残る

### D6. ピアリンクは構文に書かない

- MLAG / vPC で 2 台をつなぐピアリンクは、機器ごとの普通の LAG と L1 リンクとして書く。L1 リンクに `link_role: peer-link` と注釈を付けてよい
- `link_role` は注釈なので、それを元にした検査はしない (ADR-0020 で `link_role` の綴りに頼る検査をやめたのと同じ理由)
- 2 回目の検討で、ネットワーク技術と仕様統合の担当は `peer_links` を ES に任意で置く案を推したが、試し書きで ES ごとに同じピアリンクを繰り返すことが再発し (20 本の bond で 20 回)、5 人とも書かない側になった
- vPC Fabric Peering (物理のピアリンクなし) は、ピアリンクの LAG を書かないだけで、構文の上では ESI-LAG と同じ形になる。peer-keepalive も専用の構文を持たず、管理ポートの L3 IF として書く
- ES の脚どうしが L1 リンクでつながっていたら、ピアリンクを脚にした疑いとして error にする (D7)。これは `link_role` ではなく参照 (リンクの両端) で決める

### D7. 検査

| 検査 | 重さ |
|---|---|
| ES の `members` が 2 つ以上 (型)。脚が `{lag:}` か `{interface:}` のどちらか一方 (型) | error |
| 同じ機器の脚が 2 つある | error |
| 1 つの脚 (と、脚の LAG のメンバーの L1 IF) が 2 つの ES に入っている | error |
| 同じ ES に LAG とそのメンバーを併記している | error |
| 脚どうしが L1 リンクでつながっている (ピアリンクを脚にした疑い) | error |
| 脚に LAG のメンバーの IF を書いている (`{lag:}` を促す) | warning |
| 同じ VLAN / bridge に ES とその脚 (脚の LAG のメンバーを含む) を併記している | error |
| VLAN / bridge のポートに ES の脚の一部だけを書いている (`{ethernet_segment:}` を促す。MLAG の片側にだけ VLAN を載せる典型的な誤り) | warning |
| ES の脚の機器の一部だけが VTEP を終端している (どの VTEP も終端していない機器がある。drafts/0014 D5 の「MLAG ペアの片方だけ」を付け替えた) | warning |
| ES の id が `es-` で始まらない (ADR-0002 D7) | warning |

- VLAN ID の同一機器上の重複は、ES に載せた VLAN を脚のすべての機器で数える (ADR-0013 D4 の MLAG の扱いを付け替えた)
- VLAN の端点 (ADR-0013 D7) は、ES のポートを脚の L1 IF に展開してたどる
- VTEP の warning は「同じ VTEP を共有しているか」ではなく「VTEP を終端しているか」で見る。EVPN multihoming では脚の機器がそれぞれ自分の VTEP を終端するので、共有を求めると誤検知になる
- 脚をすべて機器ごとに書く (`{lag: lag-leaf1-a}, {lag: lag-leaf2-a}`) のは `{ethernet_segment:}` と同じ意味なので warning にしない
- **採らなかった検査**:
  - `single_active` の ES の機器の SVI がどれも anycast gateway なら warning (ネットワーク技術の担当の案)。anycast gateway はファブリック全体の SVI に置くのが普通で、
    その VLAN にはほかのホストもいるので、誤検知になる。single-active の DF でない機器も、ほかのホストのゲートウェイとして働く
  - ピアリンクのある MLAG ペアの ES に `single_active` を書いたら warning (vPC / clag に single-active の概念はない)。「ピアリンクがある」をリンクの両端から推定することになるので採らない
  - 機器ごとに書く L3 IF・サブ IF が、ES の脚の一部の機器にしかない (warning)。先送りした ([deferred.md](deferred.md))

### D8. エクスポーター

- リンクの `lag_type` をなくし、端の L1 IF が脚の ES を `ethernet_segment` として載せる。`lag_id` (端の L1 IF がメンバーの LAG) は残す。`lag_bundle` も同じ
- ES を `type: ethernet_segment` の要素として出す: `members` (YAML と同じ形に脚の機器 `node` を添える)・`nodes`・`redundancy_mode` (書かれていれば)・`name`・`description`
- VLAN のノードの `vlans` は ES の脚のすべての機器に載せる。`vlan_member` の `tagged_on` / `untagged_on` は、ES のポートをその機器の脚 (LAG の id か L1 IF の name) に開いて出す
  (ビューワはリンクの `lag_id` と照合できる)
- ndl-viz は、同じ `ethernet_segment` を持つリンクを 1 つの枠で囲む (MLAG の枠を `lag_type` から付け替える)。`redundancy_mode` は書かれていればラベルで示す。
  どの脚が standby かは決まらないので、脚の線の描き方は変えない

### D9. 旧形式は移動先を示す error にする

1.0 のリリース前なので、warning の期間を置かず、読み替えもしない。

| 書いたもの | メッセージで示す移動先 |
|---|---|
| `layer1.lag[].type: lacp` | `type` を消す |
| `layer1.lag[]` の `type: mlag`・`nodes`・`peer_link`・`peer_link_interface`・`domain_id`・`system_mac`・`client_lag` | 機器ごとの LAG を書き、`ethernet_segments` の `members` で束ねる。番号と MAC は書かない (ADR-0022) |
| `ethernet_segments[]` の `esi`・`system_mac`・`domain_id`・`peer_link(s)` | 書かない (ADR-0022) |
| L3 IF・サブ IF の `attaches_to: {ethernet_segment:}` | 機器ごとの LAG を `{lag:}` で指す |

## Consequences

**良い影響:**

- MLAG / vPC / MC-LAG / ESI-LAG (all-active / single-active) と、その混在を 1 つの形で書ける。技術が増えても `mlag_domains` のようなキーは増えない
- LAG が実機と同じく機器ごとになり、機器上の名前 (`name`) も書ける。routed の MLAG・MLAG の上のサブ IF も、機器ごとの LAG を指すので `node` の検査がそのまま効く
- ペアの属性を bond ごとに繰り返さない (ピアリンクも番号も書かない)
- MLAG の片側にだけ VLAN を載せる誤りを warning で拾える

**悪い影響 / トレードオフ:**

- MLAG の bond 1 本に、LAG 2 つと ES 1 つを書く (以前は LAG 1 つ)。20 本の bond なら LAG 40 と ES 20 になる
- vPC ではピアリンクにも VLAN を通すので、VLAN のポートに `{lag:}` を機器ごとに 2 行書く
- 構文の上では、MLAG と EVPN multihoming (all-active) を区別できない。区別は `device_type` から上位のツールが行う
- `ethernet_segment` は MLAG だけの現場ではなじみの薄い語である。言語リファレンスの対応表で補う

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer1.py` (`Lag`・`SegmentMember`・`EthernetSegment`。`LacpLag` / `MlagLag` はなくした)、`src/mlndl/schema/layer2.py` (`PortTarget` に `ethernet_segment`)、
  `src/mlndl/schema/refs.py` (呼び名)
- バリデーター: `src/mlndl/validator.py` (ES の検査、VLAN / bridge のポート、VTEP の warning の付け替え、`client_lag` の検査をなくした)
- 導出: `src/mlndl/derive.py` (`ethernet_segments`・`port_legs`。VLAN の端点と bridge の脚)
- エクスポーター: `src/mlndl/exporter/cytoscape.py`
- 文書: ADR-0001 D8・ADR-0002 D7・ADR-0012・ADR-0013・drafts/0014・ADR-0018 D1 の注記、`docs/reference/`、`docs/exporter-cytoscape.md`、`CLAUDE.md`
- ndl-viz: MLAG の枠を `ethernet_segment` から描く (別のリポジトリ)

## Alternatives Considered

- **(ii) 機器ごとの LAG + `ethernet_segments`** *(採用案。ユーザーの判断)*
- **(i) 2 台にまたがる 1 つの bond のまま、ESI を属性で足す**: 1 回目の検討の推奨案。LAG の IF が機器ごとにある実機と合わず、routed MLAG の L3 IF・MLAG の上のサブ IF の `node` を片方に決められない
- **`type: multi_chassis` + ノードの `multi_chassis_domain`** (旧 ADR-0022 の案): MLAG の固定ペアに寄り、ESI の 3 台以上・bond ごとの組み合わせと合わない。廃棄した
- **ペアのエンティティ (`mlag_pairs` など) にピアリンクと domain_id を置く**: ESI には要らないエンティティで、技術ごとにキーが増える。粒度の原則 (ADR-0022) で中身もなくなる
- **名前**: `multihoming_groups` (ネットワーク技術の担当。日本の設計書の「マルチホーム構成」に近い。BGP のマルチホーミングと取り違えるおそれ)、
  `multi_chassis_lags` (脚が物理 IF のとき「LAG」が事実と合わない。スタックも連想させる)、`redundant_attachments` (何の冗長か分からず、`redundancy_mode` と言葉が重なる)
- **`members` を LAG の id の文字列だけにする**: single-active の物理 IF の脚を書けない。後からキー付きに変えると破壊的な変更になる
- **`{ethernet_segment:}` をサブ IF / L3 IF の `attaches_to` でも受ける**: サブ IF 1 つで両機器に効いて短くなるが、L3 IF の `node` と IP が機器ごとに違うので、結局機器ごとに書くことになる

## References

- 最終形の記述例 (12 パターン): [evaluations/adr0023/patterns.yaml](evaluations/adr0023/patterns.yaml)。
  案 (i) / (ii) の比較と名前の書き比べは作業メモで、結論だけをこの ADR に書いた
- RFC 7432 §5 (Ethernet Segment)・§8.5 (all-active / single-active)
- RFC 8584 (DF 選出の preference)
