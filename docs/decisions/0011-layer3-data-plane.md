# ADR-0011: layer3 データプレーン

- **Status**: Accepted
- **Date**: 2026-10-15 (D11 を 2026-10-24 に追記)
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー (論点 A〜D の判断)
- **Pass**: C (ラウンド4。[評価メモ](evaluations/round4-evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0011](drafts/0011-layer3-data-plane.md)
- **関連**: ADR-0001 (D8 参照キー)、ADR-0002 (ID)、ADR-0005 (D3-2 スコープ外・D4 補則・D6 `node`)、[ADR-0012](0012-subinterfaces.md)、[ADR-0013](0013-vlan-ports-on-lag.md)、drafts/0010 (制御プレーン・保留中)

## Context

Pass A (drafts/0011) は layer3 のデータプレーンを実装まで進めた (2026-10-01)。ラウンド4 Pass B は、ADR-0012 / 0013 と合わせた
3 本を横断評価し、次の問題を挙げた。

- `{interface: X}` が参照元によって L1 IF / LAG / VLAN / サブ IF のどれも指す (ADR-0001 D2 に反し、YAML から読めない)
- `L3Interface.interface` は機器上の名前なのに、同じ語が `attaches_to.interface` では ID 参照になる。SVI の短縮形
  `interface: vlan-N` だけが「名前を参照として解決する」例外になっている
- 「表現原理」は一文だけでは判定しきれない (IKE / PSK、DHCP relay、VRF 間リーク)
- validator の検出漏れ (anycast gateway の不一致、自己トンネル、トンネルの AF など)

Pass C ではこれらを 5 エージェントで再評価し、割れた論点をユーザーが判断した。
なお Pass C の統合者は Pass A を書いた者と同じであり、Pass A の内容を知った上で評価メモを入力にしている。

## Decision

### D1. 表現の指針

> **関係の成立に必要な情報は書き、関係を流れる個別の経路や処理は書かない。**

これは判定の方向を示す**指針**であり、単独で判定する原理ではない。迷ったときは次の順に問い、個々の項目の最終判断は
ADR-0005 D3-2 の表に書く (ADR-0005 D4 補則)。

1. 秘匿情報か → 書かない
2. 転送テーブルの個別エントリ、または個々のパケットへの処理か → 書かない
3. それを削除すると、その関係自体が存在できなくなるか → 書く

### D2. スコープ外

次は書かない。行き先は ADR-0005 D3-2。

| 概念 | 問い |
|---|---|
| スタティックルート / デフォルトルート / redistribute / network 文 / prefix-list | 2 |
| ポリシールーティング / VRF 間のスタティックリーク | 2 |
| ACL / NAT / QoS | 2 |
| DHCP relay (helper-address) | 表で明示 (問いだけでは決まらない) |
| IPsec の暗号化パラメータ (IKE / ESP / PSK) | 1 |
| MSS clamping、mGRE / DMVPN、GRE over IPsec | 表で明示 |

スタティックルートを外すことはユーザーが決めた (設計ラウンドでは 5 エージェント中 4 つが入れると判定した)。
ホストのデフォルトゲートウェイは、同じサブネットの SVI の `ip` か `gateway_redundancy` の `vip` から導出できる。

### D3. `name` と `attaches_to`

```yaml
layer3:
  interfaces:
    - id: leaf1-swp51-l3
      node: leaf1
      name: swp51                       # 機器上の名前。参照ではない
      attaches_to: {interface: leaf1-swp51}
      ip: 10.1.0.1/31
    - id: leaf1-vlan-100                # SVI
      node: leaf1
      name: Vlan100
      attaches_to: {vlan: vlan-100}
    - id: border1-po1                   # routed LAG
      node: border1
      name: Port-channel1
      attaches_to: {lag: lag-border1-po1}
    - id: border1-po1-3001              # サブ IF に載る L3
      node: border1
      name: Port-channel1.3001
      attaches_to: {subinterface: subif-border1-po1-3001}
    - id: leaf1-lo                      # ループバックは attaches_to を持たない
      node: leaf1
      name: lo
      ip: 10.0.0.1/32
```

- **`name`** は機器上の名前で、参照解決には使わない
- **`attaches_to`** が参照の唯一の手段である。キーは `interface` (L1 IF) / `lag` / `vlan` / `subinterface` のいずれか
  (ADR-0001 D8)。ほかのキーと文字列形式はスキーマで弾く
- **`node`** は必須 (ノードごとに別の IP を持つため。ADR-0005 D6)。MLAG を基盤にする L3 IF も、ノードごとに 1 つずつ書く
- SVI の短縮形 `interface: vlan-N` は廃止した。「名前を参照として解決する」唯一の例外だったため (D10 で移行)

### D4. `gateway_redundancy`

`mode` で分岐する Tagged Union。

| mode | フィールド | 制約 |
|---|---|---|
| `vrrp` | `group_id` (1..255), `vip`, `priority` (1..254), `preempt` | 1 エントリは単一 AF (RFC 5798)。デュアルスタックは 2 エントリ |
| `hsrp` | `group_id` (0..4095), `vip`, `priority` (0..255), `preempt` | 同上 |
| `anycast_gateway` | `anycast_mac` | VIP と group_id を持たない (L3 IF の `ip` / `ipv6` 自体が anycast アドレス) |

- IPv6 の VIP はリンクローカル (fe80::/10) でなければならない (RFC 5798 §5.2.9 / §6.1。HSRP も同じ扱い)
- `anycast_mac` は `:` / `-` / `.` 区切りの 3 表記を受け付ける
- 同じ VLAN に載る anycast gateway の SVI 群は、`ip` / `ipv6` / `anycast_mac` が一致しなければならない
  (全ノードが同じアドレスで応答するため)

旧名 `fhrp` と `protocol` は廃止し、移動先を示す error にする。

### D5. `ip` と `ipv6`

`ip` は IPv4、`ipv6` は IPv6 の CIDR で、いずれも単数 (ユーザー判断)。型 (`IPv4Interface` / `IPv6Interface`) で検証し、
`ip` に IPv6 を書くと移動先を示す error にする。同じループバックに複数の IP を積む構成は、用途ごとにループバックを分けて書く
(`ip_secondary` は将来の加算候補)。

### D6. トンネル

`layer3.tunnel_interfaces` に、source と destination を自分で持つ自己完結のエントリとして書く。両端を結ぶ辺は
エクスポーターが導出する (`tunnel_links` は二重表現になるので作らない)。

| フィールド | 内容 |
|---|---|
| `node` | 必須 |
| `type` | `gre` / `ipip` / `ipsec_vti` / `wireguard` |
| `source` | 同じノードの L3 IF の id |
| `destination_interface` / `destination_ip` | どちらか一方。対向がトポロジー内なら前者 (別ノードの L3 IF)、外なら後者 |
| `ip` / `ipv6` | トンネル IF 自身のアドレス |
| `vrf` / `transport_vrf` | トンネル IF が属する VRF (overlay) / 外側パケットが流れる VRF (underlay) |
| `mtu` | 68 以上 |

対向がトポロジー内なら、**両ノードに 1 本ずつ (計 2 本) 書く**。片側しかなければ info で知らせる。

### D7. `description`

すべてのエンティティに任意の自由記述 `description` を置く。`labels` (ADR-0009) と違い、分類には使わない。

### D8. ADR-0005 との関係

本 ADR は ADR-0005 の部分改訂であり、置き換えではない。改訂した箇所は ADR-0005 の本文に注記し、末尾の「実装同期メモ」に一覧を置いた
(D4 補則、D6、D2-2 ケース B、D3-1・D3-2)。

### D9. 検証規則

| チェック | Severity |
|---|---|
| `ip` / `ipv6` の形式と AF (型) | error |
| `attaches_to` のキーが L3 IF に書けるものか (型。ADR-0001 D8) | error |
| `attaches_to` の参照先がそのキーの種類で定義されているか。キーの取り違えには正しいキーを示す | error |
| `attaches_to` が L1 IF / LAG / サブ IF を指すとき、`node` がその所属ノード (群) に含まれるか | error |
| 同一 `(node, name)` の L3 IF が重複していないか | error |
| `name` が VLAN らしい (`Vlan100` 等) のに `attaches_to` がない | warning |
| `VRF.l3vni` と `L3VxLAN.vrf` の双方向一致 | error |
| `L2VxLAN.vtep_source` の L3 IF のノードが `members` に含まれるか | error |
| `L2VxLAN.members` のノードに、その VLAN のポートがあるか (VLAN にポートが 1 つもなければ判断しない) | warning |
| VRRP / HSRP の IPv6 VIP がリンクローカルか | error |
| IPv4 VIP が IF のサブネット内か | error |
| IPv4 VIP があるのに IF に `ip` がない | warning |
| 同じ IF・同じ mode・同じ AF で `group_id` が重複していないか | error |
| 同じ VLAN の anycast gateway 群で `ip` / `ipv6` / `anycast_mac` が一致するか | error |
| トンネル: `source` が同じノードの L3 IF か、`destination_interface` が別ノードの L3 IF か、destination がちょうど一方か | error |
| トンネル: 外側のアドレスファミリーが source と destination で一致するか (両側にアドレスがある場合) | error |
| トンネル: 対向がトポロジー内なのに逆向きのトンネルがない | info |
| 推奨プレフィックス `tunnel-` (ADR-0002 D7) | warning |
| 旧形式 (D10) | warning |

Pass A にあった「短縮形と `attaches_to` の食い違い」の検査は、短縮形の廃止で不要になった。

### D10. 移行

ndl_version は 1.x のまま上げない。旧形式は **1.x の間だけ受け付け**、新形式に読み替えて warning を出す
(`--strict` では error)。2.0 で受け付けをやめる。

| 旧形式 | 新形式 | 読み替え |
|---|---|---|
| `interface: swp1` (L3 IF の機器上の名前) | `name: swp1` | スキーマ |
| `interface: vlan-100` (短縮形、`attaches_to` なし) | `name: vlan-100` + `attaches_to: {vlan: vlan-100}` | スキーマ |
| `attaches_to: {interface: <LAG / VLAN / サブ IF の id>}` | `{lag:}` / `{vlan:}` / `{subinterface:}` | validator (ID の種類で判断) |
| VLAN のポートの `node` | 書かない | validator (ADR-0013 D2) |

`interface` と `name` を両方書いた場合は error。廃止済みのキー (`vlan` / `fhrp` / `gateway_redundancy[].protocol`) は従来どおり
移動先を示す error である。

YAML エクスポーター (`python -m mlndl export --format yaml`) は新形式で書き出すので、スキーマで読み替える 2 つの旧形式の移行に使える。
validator で読み替える 2 つ (ID の種類に依存するもの) は、warning のメッセージに従って書き換える。

### D11. 補則: L3 IF の分類 (2026-10-24 追記)

L3 IF が何の上に載るかの分類は、**`attaches_to` のキーで決まる**。`name` では決めない (D3)。
ツールが表示や集計のために L3 IF を分類するときも、これに従う。

Cytoscape エクスポーターは、L3 IF を `name` の正規表現 (`lo` / `loopback0` 等) でループバックと判定し、
`loopback` / `svi` / `subinterface` / `routed` に分けていた。5 エージェントで評価し、次の問題から作り直した。

- 名前による判定は機種に依存する。SR OS の `system`、Linux の `dummy0` を取りこぼす
- `svi` / `routed port` は Cisco 寄りの語 (Junos は IRB、サブ IF は logical unit)。`routed` は多義 (ループバックも SVI もルーティングされる)
- 構文は `vlan` / `subinterface` など機種に依存しない概念のキーで書けているのに、出力でそれを崩していた (ADR-0005 D4 補則 問い 4)

#### 分類

| `attaches_to` | 分類 | 意味 |
|---|---|---|
| `{interface:}` | `l1_interface` | L1 IF の上 (物理ポート・VM の vNIC) |
| `{lag:}` | `lag` | LAG の上 (routed LAG) |
| `{vlan:}` | `vlan` | VLAN の上 (SVI / IRB / VLAN IF) |
| `{subinterface:}` | `subinterface` | サブ IF の上 |
| なし | `unattached` | 下位の IF を持たない |

- 機種ごとの呼び名 (SVI / IRB、routed port、logical unit) は分類名にしない。表示で補うのはよい (`vlan` を「VLAN IF (SVI / IRB)」と見せる等)
- **`unattached` の中身は定義しない**。ループバックのほか、dummy IF、L1 を書かずに書いた管理 IF、`attaches_to` の書き忘れもありうる。
  ループバックとはみなさない。ループバックを言語で明示する必要がはっきりしたら、そのときに判断する (加算で足せる)

#### 役割 (参照から導く)

L3 IF がほかのエンティティから参照されていることから、役割を導ける。名前は使わない。

| 役割 | 導き方 |
|---|---|
| `update_source` | `layer3.routing_adjacencies[].from` / `to` の `update_source` が指している |
| `vtep_source` | `layer2.vteps[].sources` が指している (ADR-0014) |

MLNDL はノードの代表アドレス (図に 1 つだけ出すアドレス) を言語として定義しない。どの L3 IF のアドレスがノードの代表かは
YAML に書かれず、役割から選べばそれは推定になる。見せ方は表示ツールが決める (ndl-viz の扱いと旧キー `lo_ip` は
`docs/exporter-cytoscape.md`)。当初は推奨手順を置いたが、管理 IF だけが `unattached` の構成、BGP unnumbered、
IS-IS / OSPF だけの underlay などで外れるため外した。

#### 見送った案

- **名前の正規表現でループバックを判定する** (現状): 機種に依存する。D3 とも緊張する
- **`attaches_to` がなければループバックとみなす** (dsl-designer): L1 を書かずに書いた管理 IF をループバックと誤る (example-author の試し書き)
- **名前で絞り、合わなければ unknown として warning** (network-tech-reviewer・linguist): 名前への依存、つまり機種への依存が残る
- **L3 IF に `loopback: true` を足す** (example-author): 言語の変更になる。必要がはっきりするまで見送る
- **分類名を `attaches_to` のキーそのもの (`interface` 等) にする** (spec-architect): `interface` が `attaches_to.interface` (L1 IF の id) と、
  旧出力の `interface` キー (L3 IF の名前) の両方とぶつかる
- **`physical`** (linguist): `implementation: physical` とぶつかる。L1 IF は VM の vNIC でもありうる
- **`svi` / `routed` を値に残す** (dsl-designer・network-tech-reviewer): 上の問題のとおり

#### 実装と移行

- エクスポーター (`cytoscape.py`) は機器ノードの `l3_interfaces[]` に `id` / `name` / `attaches_to` (YAML と同じ形) / `attachment` (上の分類) / `roles` を出す
- 旧キー (`interface`、`kind`、`lo_ip` / `lo_ipv6`、`vlan` / `subinterface` / `lag` の別キー) は ndl_version 1.x の間だけ併記する。
  旧 `kind` は分類から写す (`vlan` → `svi`、`unattached` → `loopback`、`l1_interface` / `lag` → `routed`)。名前による判定はしない。
  旧 `lo_ip` / `lo_ipv6` は旧ビューワのための互換値で、`unattached` の L3 IF から名前によらず 1 つ選ぶ推定である。
  「推測は出さない」(`docs/exporter-cytoscape.md` の方針) の 1.x 限定の例外とし、選び方は同文書に書く。2.0 で外す
- 出力の語彙は `docs/exporter-cytoscape.md` (informative) にまとめる

## Consequences

### 良くなること

- 参照の種類が YAML から読める。受付の範囲がスキーマで決まり、validator の受付表がなくなった
- `interface` という語は L1 IF への参照だけを意味するようになった
- 既存の YAML は壊れない (warning が出る)

### 書けないまま残るもの (別 ADR で扱う。network-tech-reviewer の優先順)

1. ~~VXLAN の anycast VTEP (MLAG ペアで共有する VTEP の IP)。`vtep_source` が単数~~ → [drafts/0014](drafts/0014-vteps.md) で解決 (2026-10-20)
2. MLAG の peer-keepalive
3. L3 IF 単位の MTU
4. VXLAN の BUM 配送方式 (ingress replication / multicast)
5. EVPN multihoming (ESI-LAG)
6. Q-in-Q / ネイティブ (タグなし) サブ IF (ADR-0012)

BGP unnumbered は制御プレーン (drafts/0010) の再開時に扱う。

### 影響を受けるコンポーネント

- スキーマ: `layer1.py` (`AttachesToObj` のキー、`restrict_attach_keys`)、`layer3.py` (`L3Interface.name`、旧形式の読み替え)
- バリデーター: `validator.py` (`_resolve_ref`、D9 の規則)
- エクスポーター: `cytoscape.py` (出力の `l3_interfaces[].interface` キーは ndl-viz との互換のため名前を変えず、中身を `name` にした)
- CLI: スキーマの段階で止まったとき、後段の検査があることを案内する
- fixture: 12 本を新形式に移行 (移行前後でモデルの中身が一致することを全件で確認)

## Alternatives Considered

- **`{interface:}` の多態参照を続け、受付表を 1 か所に集める** (spec-architect): 却下 (ユーザー判断) — YAML から参照先の種類が読めない。
  `layer2.bridges` などを足すたびに表が広がる
- **SVI の短縮形を残す**: 却下 — 「名前を参照として解決する」唯一の例外で、書き方が 2 通りになり、食い違いの検査も要った
- **表現原理を 2 軸 (秘匿情報 → 関係の成立) の原理として維持**: 却下 (ユーザー判断) — DHCP relay・VRF 間リーク・NAT を判定しきれない
  (network-tech-reviewer)
- **すぐに 2.0 として旧形式を error にする**: 却下 — 既存 YAML がすべて無効になる。1.x の間は warning で誘導する

## Pass A との差分

| 項目 | Pass A (drafts/0011) | Pass C |
|---|---|---|
| 表現の根拠 | 「表現原理」(ADR-0005 D4 補則) | 「指針」+ 3 つの問い + D3-2 の明示表 |
| 機器上の名前 | `interface` | `name` |
| SVI | 短縮形 `interface: vlan-N` と `attaches_to: {interface: vlan-N}` | `attaches_to: {vlan:}` のみ |
| `attaches_to` の参照先 | `{interface:}` で L1 IF / LAG / VLAN / サブ IF | キーで種類を示す (ADR-0001 D8) |
| 検証 | — | anycast gateway の一致、自己トンネル、トンネルの AF、片側トンネル (info)、`ip` のない VIP、VNI メンバーの VLAN |
| スコープ外 | スタティックルート等 | + ポリシールーティング、VRF 間のスタティックリーク |

## References

- [ラウンド4 横断評価メモ](evaluations/round4-evaluation.md)、試し書き `evaluations/round4/` (Pass C の比較は `round4/passc/`)
- RFC 5798 (VRRPv3) §5.2.9・§6.1、RFC 9135 (EVPN IRB)、RFC 4364 (BGP/MPLS IP VPN)、RFC 791
