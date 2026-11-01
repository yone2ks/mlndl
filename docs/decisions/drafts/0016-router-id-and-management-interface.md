# ADR-0016: ルーター ID と管理インターフェースを明示する — `router_id` と `management_interface`

- **Status**: Draft — スキーマ・validator・エクスポーターは**未変更**。Pass B / C は未実施
- **Date**: 2026-10-29
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **Pass**: A (初回策定)
- **関連**: [ADR-0011](../0011-layer3-data-plane.md) D9・D11、[ADR-0010](../0010-control-plane-separation.md) D5・D9 (2026-11-01 に Accepted、実装は未着手)、
  ADR-0005 (D3-1 (b)・D4・D4 補則 問い 4)、ADR-0009 (labels は非参照)、[drafts/0015](0015-declarative-references.md) (Ref)、
  [docs/exporter-cytoscape.md](../../exporter-cytoscape.md)

## Context

### 代表アドレスの推定をやめた

Cytoscape エクスポーターは、ノードの「代表アドレス」(`lo_ip` / `lo_ipv6`) を推定していた。`unattached` の L3 IF のうち、
`update_source` に使われているもの → `vtep_source` に使われていないもの → 記述順、の順で 1 つ選ぶ。
この推定は廃止し、ADR-0011 D11 で「言語は代表アドレスを定義しない」とした。ndl-viz は「MLNDL に書かれた情報だけを表示する」。

### 「書かれていない」のではなく「書けない」

前回の評価で network-tech-reviewer は、運用者が図で router-id と管理 IP をひと目で見たい需要は強いと指摘した。
network-tech-reviewer と example-author は、今は「書かれていない」のではなく「書けない」状態だと指摘した。
実機ではどちらも明示的に設定する。

| | 実機での設定 | MLNDL で今書けるか |
|---|---|---|
| router-id | `router bgp <asn>` / `router-id 10.1.0.11` (NX-OS・EOS・FRR)、`routing-options router-id` (Junos) | 書けない (`BGPNode` に欄がない) |
| 管理アドレス | `interface mgmt0` + `vrf management` (NX-OS)、`Management1` (EOS)、`fxp0` (Junos)、`ip ssh source-interface loopback0` (インバンド) | L3 IF としては書けるが、どれが管理用かは書けない |

推定が外れる構成もはっきりしている。

- **BGP unnumbered**: IF に IPv4 がない。router-id はリテラルでしか決まらない
- **管理 IF だけが `unattached`**: L1 を書かずに管理 IF を書くと、ループバックと区別できない
- **IS-IS / OSPF だけの underlay**: `update_source` が書かれないので、推定の手がかりがない
- **router-id が IF の IP と一致しない設計**: RFC 6286 は一致を要求しない

`examples/eveng-evpn-lab.yaml` では、loopback0 を router-id と BGP に、loopback1 を VTEP に、mgmt0 (`vrf-management`) を管理に使う。
この区別はコメントにしか書けていない。

### スコープ

router-id は ADR-0005 D3-1 (b) の「L3 アドレッシング」行と `protocols.ospf` 行で、すでにスコープ内とされている。
ADR-0010 は保留中に D5 で置き場所と形式まで決めていたが、2026-11-01 の Accepted 版 (D9) で router-id の形式と検査は本 ADR に委ね、置き場所を `control_plane` のノードエントリとした。ADR-0010 の実装はまだない。

管理アドレスはこれまでどの ADR にも出てこない。

## Decision

### D1. 足す。ただし 2 つは性質が違う

| | ADR-0005 D4 | D4 補則 | 構成子の種類 |
|---|---|---|---|
| `router_id` | 意味境界 Yes (AS / OSPF ドメイン内で一意)、blast_radius Yes (重複すると iBGP の OPEN が拒否される) | 問い 3: これがないと BGP Identifier が決まらない → 書く | 規範側 (validator が値を検査する) |
| `management_interface` | 4 軸ほぼ No (管理面を失ってもデータプレーンは止まらない) | 問い 1〜3 では決まらない。機器に明示的に設定する事実で、推定ではない | 注釈側 (`role` と同じ)。ただし値は参照なので、参照の存在は検査する (ADR-0015) |

どちらも、今書けないものを書けるようにする**加算**である。省略でき、既存の YAML はそのまま valid。`ndl_version` は 1.0 のまま。

### D2. `router_id` は BGP のノードエントリに、リテラルで置く

```yaml
protocols:
  bgp:
    - id: bgp-underlay
      role: underlay
      nodes:
        - node: leaf1
          local_as: 65001
          router_id: 10.1.0.11       # ドット区切り 4 オクテット。L3 IF の id ではない
          neighbors: [...]
```

- **置き場所**: `protocols.bgp[].nodes[].router_id` (`BGPNode`)。ADR-0010 の**先行実装**とする。
  **ADR-0010 (Accepted, 2026-11-01) D9 により、ADR-0010 の実装時に `control_plane.bgp[].nodes[].router_id` へ移る** (意味は変えない。
  OSPF は `control_plane.ospf[].nodes[].router_id`)。ADR-0010 の実装が本 ADR より先なら、最初から `control_plane` に置く
- **形式**: ドット区切り 4 オクテット、非ゼロ。IPv6 アドレスは不可 (RFC 6286 §2.1。OSPFv3 も 32 bit。RFC 5340 §2.2)
- **リテラルであり、参照ではない**。L3 IF の IP との一致も要求しない (RFC 6286 §2.1)。理由:
  - BGP unnumbered や IPv6 だけのファブリックには、参照できる IPv4 の L3 IF がない
  - router-id を固定したまま IF をリナンバリングする運用がある
  - OpenConfig / RFC 8349 も全ベンダーの CLI も、router-id を 32 bit の値として持つ。MLNDL と機器の設定が同じ字面になる
- **OSPF / IS-IS には今は置かない**。OSPF のスキーマがまだない (ADR-0010 の範囲)。IS-IS の識別子は NET の system-id で、
  router-id とは別の語彙 (ADR-0010 D5)
- **VRF ごとの router-id**: ADR-0010 D5 で BGP のエントリが VRF ごとのインスタンスになったので、`control_plane` に移った後はエントリごとに書ける (未決 3 は解消)

### D3. `management_interface` は L1 ノードから L3 IF を 1 つ指す

```yaml
layer1:
  nodes:
    - id: leaf1
      role: leaf
      management_interface: leaf1-mgmt0-l3   # layer3.interfaces[].id。同じノードの L3 IF

layer3:
  interfaces:
    - { id: leaf1-mgmt0-l3, node: leaf1, name: mgmt0, ip: 192.168.0.242/24, vrf: vrf-management,
        attaches_to: {interface: leaf1-mgmt0} }
```

- **意味**: 運用者がこのノードに管理アクセス (CLI / SNMP / NETCONF / gNMI) するときの宛先になる L3 IF。
  アドレスは参照先の `ip` / `ipv6` から取る。IPv4 と IPv6 の両方を持つなら、両方が管理アドレスになる
- **型**: `Annotated[str | None, Ref("layer3.interfaces")] = None`。単数、省略可
- **参照先の種類を問わない**。専用の管理ポート (`{interface:}`)、インバンド管理のループバック (`unattached`)、
  管理 VLAN の SVI (`{vlan:}`)、Linux ホストのデータ兼用の eth0 のどれも指せる。`attaches_to` のキーによる制約は付けない
- **参照先に `ip` / `ipv6` がなくてもよい** (DHCP で取る管理 IF など)。そのときアドレスは表示しない
- 管理 IF を持たないノード (管理しない機器、別系統で管理する機器) は書かなくてよく、warning も出さない

### D4. 参照の向き: 選ぶ側から、選ばれる側を 1 本で指す

1 ノードにつき 1 つに決まるべき値は、**選ぶ側 (ノード / BGP のノードエントリ) に 1 本だけ置く**。
選ばれる側 (L3 IF) に「自分が管理用だ」「自分の IP を router-id に使う」と名乗らせる形は採らない。

- 名乗らせる形では、同じノードの 2 つの L3 IF が名乗ったときに決まらず、validator が「ちょうど 1 つ」を検査することになる。
  廃止した代表アドレスの推定と同じ問題になる
- エクスポーターの `l3_interfaces[].roles` (`update_source` / `vtep_source`) は「ほかから参照されている」ことから**導いた**値である。
  L3 IF に書く役割の欄を足すと、書いた値と導いた値が同じ場所に並び、読み分けられない
- NetBox (`Device.primary_ip4` / `oob_ip`) と Terraform も、ノードから代表の IF / IP を 1 本で指す

`management_interface` は ADR-0009 の 3 構成子 (Realization / Containment / Classification) のどれでもない。
「ノードが単数で持つ、別のエンティティへの参照」である。同じ種類の需要 (コンソール、主ループバックなど) が増えたら、
まとめ方をそのとき判断する (先回りしない)。

### D5. 名前

| フィールド | 採用理由 | 却下した名前 |
|---|---|---|
| `router_id` | RFC 6286 / RFC 8349 / 全ベンダーの `router-id` の snake_case。ADR-0010 D5 と同じ | `router_id_source` (`update_source` と紛れる)、値の形で参照とリテラルを切り替える同名フィールド (多義) |
| `management_interface` | `_interface` で参照先が L3 IF だと読める。in-band / OOB を問わない | `management` (役割か IF かアドレスか読めない)、`mgmt` (略語。ADR-0002)、`oob` (in-band 管理を排除する。方式名なので ADR-0005 D4 補則 問い 4 にも当たる)、`role` / `roles` / `purpose` / `usage` (L3 IF 側に書く案。D4 で却下) |

`mgmt0` / `fxp0` / `Management1` / `loopback0` / `system` は機種の語で、構文には出さない (ADR-0005 D4 補則 問い 4)。
これらは L3 IF の `name` に書く。

`labels` には入れない。`labels` の値は参照ではない (ADR-0009)。`labels: {management: leaf1-mgmt0-l3}` と書いても、
L3 IF を指したことにはならない。

### D6. 検査

| 検査 | Severity | 根拠 |
|---|---|---|
| `management_interface` が `layer3.interfaces` に実在する id か | error | ADR-0015 (`Ref` を付ければ汎用の検査で付く) |
| `management_interface` の参照先 L3 IF の `node` が、そのノード自身か | error | ADR-0011 D9 と同じ形 |
| `router_id` がドット区切り 4 オクテットで、`0.0.0.0` でないか | error | RFC 6286 §2.1 (型で検査する) |
| 同じ `local_as` を持つ別々のノードが、同じ `router_id` を使っていないか (全 BGP エントリを横断する) | error | RFC 6286 §2.2 (iBGP では OPEN が拒否される)。ADR-0010 D6 |
| `router_id` と L3 IF の IP の一致 | **検査しない** | RFC 6286 は要求しない。unnumbered を妨げる |

一意性の検査を「BGP エントリごと」でなく「同じ `local_as` で全エントリ横断」にするのは、D8 (エントリの単位) が未決でも
同じ結果になるようにするため。同じノードが underlay と overlay の 2 エントリに出るのは今の書き方では普通なので、
**同じノードどうし**の重複は数えない。同じノードが 2 つのエントリで別の `router_id` を書いたときの扱いは未決 4。

### D7. エクスポーター (informative。`docs/exporter-cytoscape.md` に足す)

`type: node` に次を足す。どちらも書かれたものをそのまま出し、推定はしない。

| キー | 内容 |
|---|---|
| `router_ids` | `[{process, router_id}]`。このノードが出る BGP エントリごとの `router_id` (書かれたものだけ)。同じ値をまとめて 1 つに見せるのはビューワ (「エクスポーターは参照を解決し、ビューワは集合演算をする」) |
| `management_interface` | `{id, name, ip?, ipv6?, vrf?}`。参照先 L3 IF の値 |

旧キー `lo_ip` / `lo_ipv6` は今の扱い (1.x の間は互換のため出し、2.0 で外す) を変えない。

### D8. ADR-0011 D11 は改訂しない

D11 が定義しないとしたのは「ノードの代表アドレス」(図に 1 つだけ出すアドレスを、L3 IF の中から選ぶこと) である。
`router_id` は BGP Identifier という 32 bit の値で、L3 IF のアドレスではない。`management_interface` は管理の宛先を
書き手が宣言したもので、ツールが選んだものではない。どちらも代表アドレスではない。

Accepted にするとき、D11 に次の後注だけを足す: 「router-id と管理の宛先は ADR-0016 で書けるようにした。これらは代表アドレスではない」。

## Consequences

**良い影響:**

- 運用者が見たい router-id と管理アドレスを、推定せずに図に出せる
- BGP unnumbered、IPv6 だけのファブリック、管理 IF だけが `unattached` の構成でも正しく書ける
- 誤って router-id を重複させた構成 (実機では iBGP の OPEN が拒否される) を validator が止める
- ADR-0010 D5・D6 の一部が、D8 の未決と無関係に先に使えるようになる

**悪い影響 / トレードオフ:**

- **同じ値を 2 か所に書く**。loopback0 の IP を router-id にするとき、`router_id: 10.1.0.11` と L3 IF の `ip: 10.1.0.11/32` を
  両方書く。underlay と overlay にエントリを分けていれば、`router_id` も 2 回書く (example-author の試し書き)。
  機器の設定も同じ字面を 2 か所に持つので、実機と同じ形ではある
- 管理アドレスはノードあたり 1 つの L3 IF に限る。OOB とインバンドの併用、mgmt0 / mgmt1 の冗長は、片方しか書けない (未決 1)
- VRF ごとの router-id は書けない (未決 3)
- `protocols` 側の `router_id` は、ADR-0010 の実装時に `control_plane` へ移す作業が増える (機械的な改名)

**影響を受けるコンポーネント (Accepted 後):**

- スキーマ: `src/mlndl/schema/layer1.py` (`L1Node.management_interface`)、`src/mlndl/schema/protocols.py` (`BGPNode.router_id`)
- バリデーター: `src/mlndl/validator.py` (D6 の node 一致と router_id の一意性)
- エクスポーター: `src/mlndl/exporter/cytoscape.py`、`src/mlndl/derive.py`、`docs/exporter-cytoscape.md`
- サンプル: `examples/eveng-evpn-lab.yaml`、`tests/fixtures/` (有効 / 無効のペア)
- 文書: CLAUDE.md (NDL YAML 概要、バリデーション表の「ルーター ID」行を「実装しない」から D6 に置き換える)、
  ADR-0011 D11 (後注)、drafts/0010 D5 (先行実装の注記)

## Alternatives Considered

### router-id

- **R1. BGP のノードエントリにリテラル** *(採用)*: 5/5
- **R1'. BGP のノードエントリに、リテラルか L3 IF の id かを選べる形** (example-author): 却下 (4/5)。
  同じキーに別の種類の値を書けると YAML から読めない (ADR-0001 D8 で `{interface:}` を分けたのと同じ理由)。
  参照で書けるのは IF の IP と router-id が一致するときだけで、一致しない設計 (構成 f) と unnumbered (構成 b) では
  結局リテラルが要る。二重記述の解消は、実機の設定も二重であることから、言語の欠陥とまでは言えない
- **R2. L1 ノードにノード共通の router-id** : 却下 (5/5)。`layer1` はデータプレーンの物理構成 (ADR-0005 D1 (a)、ADR-0010 D1) で、
  制御プレーンの値を置くと層が混ざる。ノード共通の既定値を持たない機種 (NX-OS・EOS) もある。Junos / FRR / SR OS の
  グローバル設定へは、全エントリが同じ値なら上位ツールがまとめればよい
- **R3. L3 IF に「この IP を router-id に使う」と書く**: 却下 (5/5)。router-id が IF の IP と一致しない構成を書けない。D4 の「名乗らせる形」

### 管理アドレス

- **M2. L1 ノードから L3 IF を 1 本で指す** *(採用)*: 4/5 (spec-architect / linguist / dsl-designer / example-author)
- **M1. L3 IF に `management: true` を書く** (network-tech-reviewer): 却下 (4/5)。
  network-tech-reviewer の論拠は「管理アドレスは IP (L3 IF) の用途であってノードの属性ではない。1 ノードに複数ありうる」。
  複数を書ける点は M2 より優れる。しかし D4 の理由 (複数が名乗ったときに決まらない、書いた役割と導いた `roles` が同じ場所に並ぶ) から、
  複数が要るなら M2 を複数形にする方向で考える (未決 1)
- **M3. 管理 VRF から導く**: 却下 (5/5)。VRF を分けない構成やインバンド管理 (default VRF のループバック) を取りこぼす。
  VRF の中のどれが管理の宛先かは、結局別に決める必要がある
- **M4. `link_role: management` から導く**: 却下 (5/5)。`link_role` は自由文字列の注釈で、そこから意味を導くのは推定になる。
  L1 リンクから L3 IF のアドレスまで参照をたどる必要もある
- **`labels` に書く**: 却下。ADR-0009 (labels の値は参照ではない)

## 未決 (ユーザー判断 / Pass B で確定)

1. **管理 IF を複数書けるようにするか**。OOB (mgmt0) とインバンド (loopback0) の併用、mgmt0 / mgmt1 の冗長がある (network-tech-reviewer)。
   推奨は「今は単数で始める」。複数形にするなら、後から `management_interfaces: [...]` を足すより、最初から決めたほうが
   移行が少ない (linguist は単数 → 複数を破壊的変更と見る)。単数のフィールドは「主たる管理の宛先」と読める
2. **`router_id` をリテラルだけにするか** (R1 と R1' のどちらか)。推奨はリテラルだけ。二重記述を嫌うなら、
   別名のフィールドで参照を足す余地はある (同名で型を切り替えることはしない)
3. ~~VRF ごとの router-id~~ → **解消** (2026-11-01)。ADR-0010 D5 で BGP のエントリが VRF ごとのインスタンスになり、エントリごとに書ける
4. **同じノードが 2 つの BGP エントリで別の `router_id` を書いたとき** → ADR-0010 D5 (VRF ごとのエントリ、同一 VRF に 1 エントリ) により、
   別の VRF なら正当、同じ VRF には 2 エントリ書けない (ADR-0010 D10 の error)。本 ADR の一意性の検査はこの前提で書き直す
5. **フィールド名の確認** (Pass B で linguist に):
   - `management_interface` は L3 IF を指す。`attaches_to` の `{interface:}` は L1 IF 専用 (ADR-0001 D8) なので、
     `_interface` という語尾が参照先を L1 IF と誤読させないか。トンネルの `destination_interface` (L3 IF を指す) という前例はある
   - `layer1.nodes[].role: management` (OOB 管理専用の機器。docs/role-vocabulary.md) と `management_interface` (このノードへの管理の宛先) が
     同じノードに並ぶ。意味の違いを docs/role-vocabulary.md に一言添えるか
6. **OSPF の router-id**。ADR-0010 の実装で OSPF のスキーマを足すときに、D2 と同じ形 (`control_plane.ospf[].nodes[].router_id` にリテラル) で足す。一意性の範囲は OSPF ドメイン

## References

- 関連 ADR: ADR-0001 (D8)、ADR-0002 (D1)、ADR-0005 (D1・D3-1・D4・D4 補則)、ADR-0009、ADR-0011 (D9・D11)、ADR-0010 (D5・D9・D10)、drafts/0015
- 試し書き (5 エージェント評価時、リポジトリ外): BGP unnumbered、OSPF / IS-IS だけの underlay、インバンド管理、Linux ホスト、
  router-id が IF の IP と異なる設計、`examples/eveng-evpn-lab.yaml` の書き直し
- RFC 6286 (BGP Identifier: 4 オクテット・非ゼロ・AS 内で一意。IF の IP との一致は要求しない)
- RFC 2328 / RFC 5340 §2.2 (OSPFv2 / OSPFv3 の Router ID は 32 bit)
- RFC 8349 (`ietf-routing`: router-id はグローバル既定値 + プロトコルごとの上書き)
- NetBox `Device.primary_ip4` / `primary_ip6` / `oob_ip` (ノードから代表の IP を 1 本で指す)
