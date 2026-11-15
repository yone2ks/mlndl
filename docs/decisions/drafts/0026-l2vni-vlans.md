# ADR-0026: L2VNI に、機器によって番号の違う VLAN を載せる (`vlans`)

- **Status**: Draft (改訂 1。2026-11-15 の横断評価 [evaluations/adr0026/evaluation.md](../evaluations/adr0026/evaluation.md) を反映)
- **Date**: 2026-11-15
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: A (5 エージェントの評価を 1 回取り、案 A をユーザーが選んだ。改訂 1 は Pass B の指摘の反映)
- **Amends**: [ADR-0014](../0014-vteps.md) D3 (L2VNI の VLAN の参照。参加ノードの導き方は変えない)、[ADR-0011](../0011-layer3-data-plane.md) D4 (anycast gateway の一致の単位)
- **関連**: ADR-0005 D4 補則・D6、[ADR-0013](../0013-vlan-ports-on-lag.md)、ADR-0015、ADR-0022、[ADR-0023](../0023-per-device-lag-and-ethernet-segments.md)、[ADR-0025](../0025-end-grace-for-old-forms.md)

## Context

EVPN-VXLAN では、ブロードキャストドメインを識別するのは VNI で、VLAN の番号は機器の中だけの番号である。
機器によって VLAN の番号が違うことがある構成 (leaf1・leaf2・leaf4 では VLAN 20、leaf3 だけ VLAN 30 を、同じ L2VNI 10020 に載せる) は、
既存の L2 の番号を残したままファブリックに収容するときに普通に使う。
Cumulus (NVUE)・NX-OS (`vn-segment`)・EOS (`vxlan vlan X vni Y`)・Junos・SONiC のどれでも、機器ごとに別の VLAN を同じ VNI に対応させて書ける。

RFC もこれを妨げない (2026-11-15 に本文で確かめた)。

- RFC 8365 §5.1: VXLAN の VNI は通常テナントの VID と 1 対 1 で、入口の VTEP は内側の VLAN タグを付けずにカプセル化する (RFC 7432 の VLAN-based service に当たる)。VLAN の番号は VTEP の外に出ない
- RFC 8365 §5.1.3: VLAN-based service (MAC-VRF に VNI が 1 つ) の EVPN ルートの Ethernet Tag は 0
- RFC 7432 §6.1: VLAN-based service で、PE ごとに VID が違ってよい。そのとき PE は VID を付け替える (RFC はこれを "VID translation" と呼ぶ)

今の MLNDL ではこれを書けない。

- L2VNI の `vlan` は `layer2.vlans` の id を 1 つだけ指す (`Annotated[str, Ref("layer2.vlans")]`)
- VLAN のエントリは `vlan_id` を 1 つ持ち、ポートで複数の機器にまたがる (機器はポートから導く。ADR-0013)
- 同じ `vni` の L2VNI を 2 つ書くと VNI の重複で error。L2VNI を 1 つにして `vlan: vlan-20` とすると、leaf3 の `vlan-30` は VNI とつながらず、
  「VNI に参加するノード 'leaf3' には VLAN 'vlan-20' のポートがありません」の warning が出る (試し書き B1 で確かめた)

ndl-viz は L2VNI の下に `vlan` を 1 つだけ描くので、番号の違う機器は図から落ちる。ndl-viz は推定で埋めない方針なので、言語の側で書けるようにする。

## Decision

### D1. L2VNI の `vlans` は VLAN のリスト

```yaml
layer1:
  ethernet_segments:
    - {id: es-server1, members: [{lag: lag-leaf1-server1}, {lag: lag-leaf2-server1}]}
layer2:
  vlans:
    - id: vlan-20                          # leaf1 / leaf2 (ES 経由) と leaf4 の VLAN 20 は 1 エントリ
      vlan_id: 20
      trunk_ports:
        - {ethernet_segment: es-server1}
        - {interface: leaf4-swp3}
    - id: vlan-30                          # leaf3 だけ番号が違う
      vlan_id: 30
      access_ports: [{interface: leaf3-swp1}]
  vteps:
    - {id: vtep-leaf1-leaf2, sources: [leaf1-lo, leaf2-lo], address: 10.0.100.12/32}
    - {id: vtep-leaf3, sources: [leaf3-lo]}
    - {id: vtep-leaf4, sources: [leaf4-lo]}
  vxlan:
    - id: vni-10020
      type: l2vni
      vni: 10020
      vlans: [vlan-20, vlan-30]            # この VNI に載る VLAN
      vteps: [vtep-leaf1-leaf2, vtep-leaf3, vtep-leaf4]
layer3:
  interfaces:                              # SVI は機器ごと。番号が違っても anycast のアドレスは同じ (D6)
    - {id: leaf1-vlan-20, node: leaf1, name: vlan20, attaches_to: {vlan: vlan-20}, ip: 10.20.0.1/24, vrf: vrf-tenant-a, gateway_redundancy: [{mode: anycast_gateway}]}
    - {id: leaf2-vlan-20, node: leaf2, name: vlan20, attaches_to: {vlan: vlan-20}, ip: 10.20.0.1/24, vrf: vrf-tenant-a, gateway_redundancy: [{mode: anycast_gateway}]}
    - {id: leaf3-vlan-30, node: leaf3, name: vlan30, attaches_to: {vlan: vlan-30}, ip: 10.20.0.1/24, vrf: vrf-tenant-a, gateway_redundancy: [{mode: anycast_gateway}]}
    - {id: leaf4-vlan-20, node: leaf4, name: vlan20, attaches_to: {vlan: vlan-20}, ip: 10.20.0.1/24, vrf: vrf-tenant-a, gateway_redundancy: [{mode: anycast_gateway}]}
```

完全な形 (L3VNI・VRF・BGP を含む) は試し書き `evaluations/adr0026/passb/B1_mixed_vlans_canonical.yaml`。

- 型は `Annotated[list[str], Ref("layer2.vlans")]`、要素は 1 つ以上 (`min_length=1`)、同じ id を 2 回書かない (スキーマの `model_validator`)。
  参照の存在の検査は `Ref` の宣言で付く (ADR-0015)
- 全機器で番号が同じ普通の構成は `vlans: [vlan-100]` と 1 要素で書く
- L3VNI は変えない (`vrf` を持ち、VLAN を持たない)

### D2. 旧 `vlan:` は移動先を示す error

`vlan` (単数) は読み替えず、書いたら次の error にする (ADR-0025 D1 と同じ形・同じ言い回し)。`vlan` と `vlans` の両方を受ける形は採らない。

> L2VNI の vlan はなくしました。vlans: [vlan-100] のようにリストで書いてください。機器によって VLAN の番号が違うときは、番号ごとの VLAN のエントリを並べます (ADR-0026)

### D3. VLAN のエントリと L2VNI の意味

- **L2VNI に入る VLAN**: ブロードキャストドメインを表すのは L2VNI。VLAN のエントリは「そのドメインに、ある 802.1Q の番号でつながるポート」を表す
- **L2VNI に入らない VLAN** (VXLAN を使わない VLAN): 今までどおり、VLAN のエントリ 1 つが 1 つのブロードキャストドメインを表す
- VLAN のエントリを分けるのは**番号が違うときだけ**。同じ番号なら、何台の機器にまたがっても 1 エントリに書く (今と同じ)。
  そのため id は `vlan-<N>` のままで足り、`vlan-leaf1-20` のような機器名入りの id の規約は足さない
- Ethernet Segment は相手から 1 本の LAG に見えるので、脚の機器の番号は 1 つ。`{ethernet_segment:}` で書けば自然にそうなる。
  脚を機器ごとの `{lag:}` で書いて別の番号の VLAN に分けた場合だけ、D5 の error になる
- `vlans` は「1 つの VNI に載る、機器によって番号の違う VLAN」で、VLAN-aware bundle (1 つの MAC-VRF に入る、VNI の違う VLAN の集まり) ではない
- 別の機器で同じ番号を別のブロードキャストドメインに使う (今も許している) ときの id の付け方は、この ADR では決めない

### D4. L2VNI ごとに、機器とその機器の VLAN を導く

L2VNI の `vlans` の各 VLAN が、どの機器の VLAN かは参照をたどって導く。新しいフィールドは足さない。

1. VLAN のポート (`{interface:}` / `{lag:}` / `{ethernet_segment:}`) の機器 (ADR-0013 と同じ。ES は脚の全機器)
2. その VLAN を `attaches_to: {vlan:}` で指す SVI の `node`

- 見るのは、その L2VNI の `vlans` に書いた VLAN だけ。SVI の VLAN を `vlans` に書き忘れると、その機器の VLAN は決まらない (D5 の warning)
- 2 を足すのは、ポートを持たず SVI だけを持つ機器 (centralized gateway・border leaf など) の VLAN を決めるため
- **この導き方は L2VNI のためだけに使う**。「VLAN の機器」のほかの使い道 (同じ機器での `vlan_id` の重複の検査、VLAN の端点 (ADR-0013 D7)、エクスポーターの機器ノードの `vlans` と `vlan_member` エッジ) は、今までどおりポートだけから導く
- **L2VNI に参加する機器** (VTEP の `sources` から導く。ADR-0014 D3) の定義は変えない。D4 は参加機器ごとに「どの VLAN か」を決めるもので、参加するかどうかは決めない
- ポートも SVI もない参加機器 (Multi-Site の BGW のように VNI を中継するだけの機器など) は、VLAN が決まらない。図ではその機器を「VNI に参加し、VLAN は書かれていない」として出し、推定で埋めない

`derive.py` に「L2VNI ごとに、機器と VLAN の id の組」を返す関数を足し、validator (D5) とエクスポーター (D7) で共用する。

### D5. 検証規則

| チェック | Severity |
|---|---|
| `vlans` が 1 つ以上、同じ id を 2 回書いていない (型) | error |
| `vlans` が `layer2.vlans` に定義されているか (`Ref`) | error |
| 旧 `vlan` (D2) | error |
| 1 つの VLAN が 2 つの L2VNI の `vlans` に入っている | error |
| 1 台の機器で、1 つの L2VNI の `vlans` の VLAN が 2 つ以上ある (D4 で導く) | error |
| 同じ Ethernet Segment の脚 (LAG / L1 IF) が、同じ L2VNI の番号の違う VLAN に分かれている | error |
| 1 つの L2VNI の `vlans` の VLAN を指す SVI の `vrf` が食い違う | error |
| 1 つの L2VNI の `vlans` に同じ `vlan_id` の VLAN が 2 つある (1 エントリにまとめる) | warning |
| VNI に参加する機器 (VTEP から導く) に、`vlans` のどの VLAN もない (D4 の 1・2 で数える。今の warning を広げる) | warning |

- **1 台で 2 つの VLAN が同じ VNI に**: 1 つのブロードキャストドメインを、1 台の機器の中で 2 つの番号で定義することになる。ベンダーによらず誤り
  (どの機器も VLAN と VNI を 1 対 1 で対応させる)
- **1 つの VLAN が 2 つの L2VNI に**: 案 C (VLAN 側に `vni`) なら型で防げたものを validator で補う
- **ES の脚が別の番号に**: 相手 (サーバー) からは 1 本の LAG なのに、脚ごとに別のタグを求められる。
  この error を出した VLAN には、ADR-0023 D7 の「ES の脚の一部だけ」の warning を重ねない
- **SVI の VRF の食い違い**: 同じブロードキャストドメインのゲートウェイが別の VRF にあると、着いた機器によってトラフィックが別の VRF に入る
- **参加機器に VLAN がない warning の境界**: `vlans` のどの VLAN にもポートと SVI が 1 つもないときは、判断できないので出さない (今の「VLAN にポートが書かれていない場合は見ない」と同じ)。
  BGW のような正しい構成でもこの warning が出る (Consequences)
- 番号が違うこと自体は warning にしない
- 1 つの L2VNI に D5 の error があるときは、その L2VNI について D6 の検査を重ねない (同じ原因で error が増えるのを避ける。ADR-0018 D4 の「端の機器の誤りがあるセッションには重ねて出さない」と同じ考え)

### D6. anycast gateway の一致は VNI 単位

ADR-0011 D4 の「同じ VLAN の anycast gateway 群で `ip` / `ipv6` が一致する」を、次のように変える。

- SVI の VLAN が L2VNI の `vlans` に入っていれば、**その L2VNI の SVI 全体**で `ip`・`ipv6` の一致を検査する
- どの L2VNI にも入っていない VLAN の SVI は、今までどおり VLAN ごとに検査する
- 拾う SVI は、今までどおり `gateway_redundancy` に `mode: anycast_gateway` を持つものだけ。MAC は比べない (ADR-0022)
- error のメッセージは L2VNI の id を主語にし、食い違う 2 つの SVI の id・VLAN・値を添える。例:
  `L2VNI 'vni-10020' の anycast gateway で ip が食い違っています: 'leaf3-vlan-30' (VLAN 'vlan-30') は 10.20.0.2/24、'leaf1-vlan-20' (VLAN 'vlan-20') は 10.20.0.1/24。anycast gateway は VNI のすべての機器で同じアドレスにします (ADR-0026 D6)`

leaf1 の `vlan20` と leaf3 の `vlan30` は同じブロードキャストドメインのゲートウェイなので、同じアドレスでなければ、着いた機器によってホストのゲートウェイが変わる。
VLAN 単位のままだとこの食い違いを見逃す (試し書き B5)。Symmetric IRB と Asymmetric IRB のどちらでも同じ要件になる。

### D7. エクスポーター

- L2VNI のノードの `vlan` (文字列) を `vlans` (id のリスト。YAML と同じ) に替える。旧キーは併記しない (ADR-0025 D3 と同じ)
- D4 で導いた対応を、L2VNI のノードに `node_vlans: [{node: <機器の id>, vlan: <VLAN の id>}]` として出す。VLAN が決まらない参加機器は出さない
  - リストの形は、Ethernet Segment の `members` (`[{node, lag}]` など) にそろえる
  - キー名を `members` にしないのは、入力の L2VNI で `members` をなくした (ADR-0014 D4・ADR-0025) ため。同じ名前が出力で別の意味を持つのを避ける
- 機器ノードの `vlans` と `vlan_member` エッジは変えない (ポートから導く。D4)
- `docs/exporter-cytoscape.md` を直す。ndl-viz は L2VNI から VLAN へ線を複数描き、`node_vlans` で機器ごとの番号を示す (ndl-viz 側では導かない)

### 範囲外

- **アクセスポートでの番号の付け替え** (外から来たタグ 100 を機器の中の VLAN 20 として扱う設定): ポートの設定で、構成図の粒度ではない (ADR-0022 の問い 5)。
  この ADR の「機器によって番号が違う」は、RFC 7432 §6.1 の呼び方では VID translation だが、機器のポートで番号を付け替える機能とは別のものとして扱う。
  ADR と docs では「VLAN translation」の語を使わず「機器によって番号が違う」と書く
- **VLAN-aware bundle** (1 つの MAC-VRF に複数の VLAN を入れ、VLAN ごとに別の VNI を持つ。RFC 8365 §5.1.3 では Ethernet Tag が MAC-VRF の中のブリッジテーブルを指し、EVI の全 PE でそろえる):
  MLNDL は今、サービスの種類 (VLAN-based / VLAN-aware bundle) を書かない。書く必要が出たときに別の ADR で扱う。
  そのときは L2VNI の `vlans` を流用せず別のキー (例: `layer2.mac_vrfs`) にし、D5 の検査との関係を見直す
- **Ethernet Tag ID の値**: 書かない (RFC で決まる値、または装置に設定するためだけの値。ADR-0022)
- **VLAN のエントリに `node` を持たせる**: しない (ADR-0005 D6、ADR-0013)。ポートも SVI もない機器の番号は書けないまま残す (D4)
- **ファブリックごとの VNI の番号の使い回し** (RFC 8365 §5.1.1 の、その場所だけの VNI): VNI の番号はトポロジー全体で一意のまま。別の ADR で扱う

## Consequences

**良い影響:**
- 機器によって VLAN の番号が違う L2VNI を書け、図に機器ごとの VLAN を出せる
- 1 つの VNI について知りたいこと (載る VLAN と、載る VTEP) が L2VNI のエントリ 1 つで読める (ADR-0014 で VTEP を L2VNI 側に集めたのと同じ向き)
- 番号が違う VLAN の SVI どうしでの anycast gateway の食い違い・VRF の食い違いを見つけられる

**悪い影響 / トレードオフ:**
- 全機器で番号が同じ普通の構成でも、`vlan: vlan-100` を `vlans: [vlan-100]` に書き換える (1 要素のリスト。試し書き B4)
- 機器の設定の書き方 (NX-OS・IOS-XE・Junos・NVUE は VLAN の下に VNI を書く) とは参照の向きが逆になる。設定から MLNDL を作るアダプターは、VNI ごとに VLAN を集める。
  ただし VLAN のエントリが複数の機器にまたがる今の形では、機器をまたいで番号ごとにまとめる処理は案 C でも要るので、差は小さい
- **L3VNI と参照の向きが違う**: L3VNI は VRF と双方向に参照し合う (`VRF.l3vni` と `L3VxLAN.vrf`。1 対 1 なので一致を検査できる)。
  L2VNI と VLAN は 1 対多なので、L2VNI から VLAN への片方向だけにし、「1 つの VLAN は 1 つの L2VNI まで」は validator の error で担保する (D5)。
  VTEP の `sources` や ES の `members` と同じ、束ねる側から指す流儀
- **ポートも SVI もない参加機器に warning が出る**: Multi-Site の BGW のように VNI を中継するだけの機器は正しい構成だが、D5 の warning が出る。
  抑える方法 (機器の注釈で見分けるなど) は、必要になったときに決める
- SVI から機器を導くのは L2VNI の中だけなので、「VLAN の機器」の導き方が L2VNI とそれ以外で 2 通りになる (D4。Pass C で再確認する)

**影響を受けるコンポーネント:**
- スキーマ: `src/mlndl/schema/layer2.py` (`L2VxLAN.vlan` → `vlans`、`vlans` の重複、旧 `vlan` の error)
- derive: `src/mlndl/derive.py` (L2VNI ごとの機器と VLAN、D4)
- バリデーター: `src/mlndl/validator.py` (D5 の検査、VNI 参加ノードの warning を `vlans` 全体と SVI で数える形に、`_check_anycast_consistency` を VNI 単位に、ES の脚の warning の抑止)
- エクスポーター: `src/mlndl/exporter/cytoscape.py`、`docs/exporter-cytoscape.md` (D7)
- テスト: `tests/test_refs.py` の `BASE` (`vlan: vlan-100` → `vlans: [vlan-100]`)。`Ref` の検査は list も扱うので `NOT_REFERENCES` / `KEYED_REFERENCES` は変えない
- fixture: L2VNI を持つ 5 本 (`valid_full_dc.yaml`・`valid_dual_stack.yaml`・`valid_multisite_wan.yaml`・`valid_multi_vlan.yaml`・`invalid_vni_duplicate.yaml`) を `vlans: [...]` に。
  足すもの: 機器によって番号が違う構成 (B1 相当)、SVI だけで参加する機器 (B2 相当)、D5 の各 error (B3a〜B3c 相当)、D6 の食い違い (B5 相当)
- examples: `examples/eveng-evpn-lab.yaml`・`examples/eveng-evpn-lab-extended.yaml`
- 文書: `docs/reference/layer2.ja.md`、`docs/reference/validation.ja.md` (旧形式の表、VNI の参加機器の行、anycast gateway の行)、`docs/reference/schema.json` (生成物)、
  `docs/concepts.ja.md` (VLAN のエントリと L2VNI の意味、D3)、CLAUDE.md (フォーマット概要の `vxlan` の例、バリデーション項目の VNI の参加ノード・ゲートウェイ冗長・旧形式の行)、
  ADR-0014 D3 と ADR-0011 D4 に改訂の注記
- 下流: ndl-viz (L2VNI から VLAN へ複数の線、`node_vlans`)

## Alternatives Considered

- **案 A: L2VNI の `vlan` を `vlans` (リスト) にする** *(採用案)*: 4/5 (spec-architect・linguist・dsl-designer・network-tech-reviewer) が推した
- **案 B: `vlan` と `vlans` の両方を受ける**: 却下 — 同じことを 2 通り書け、ADR-0025 の方針 (旧形式は読み替えずに error) に反する (全員一致)
- **案 C: VLAN 側に `vni: vni-10020` を持たせ、L2VNI は VLAN を指さない**: 却下 (example-author が第一候補とした)。
  - 利点: 機器の設定の書き方と向きが一致する。普通の構成で記述量が変わらない。1 つの VLAN が 2 つの VNI に入ることを型で防げる。
    MLNDL 内にも VRF の `l3vni` という同じ向きの前例がある
  - 却下の理由: VNI に載る VLAN を知るには全 VLAN を逆引きする。VTEP は L2VNI 側 (`vteps`)、VLAN は VLAN 側と、1 つの VNI の情報が 2 か所に分かれる。
    NetBox の L2VPN (1 つの L2VPN が VLAN を複数持つ) は案 A と同じ向き。型で防げる利点は、D5 の error 1 つで補える
- **案 D: VLAN のエントリ 1 つの中に機器ごとの番号を持たせる** (`vlan_ids: [{node, vlan_id}]` やポートごとの `vlan_id`): 却下 — VLAN のエントリに `node` を書くことになり、
  ポートから導く機器と二重になる (ADR-0005 D6・ADR-0013)。普通の構成で `vlan_id` と `vlan_ids` の 2 通りの書き方ができる。ポートごとの番号はポートでの付け替えと混ざる
- **案 E: 同じ `vni` の L2VNI エントリを複数許す**: 却下 — 1 つの VNI は 1 つのブロードキャストドメインで、エントリが分かれると誤読を招く。VNI の一意性の検査を外すことになる
- **フィールド名 `mapped_vlans` / `member_vlans`**: 採らない — `vteps` / `sources` / `members` / `ports` と同じく、参照先のコレクション名の複数形にそろえる (linguist)
- **機器ごとの VLAN の id 規約 (`vlan-<node>-<N>` / `vlan-<N>-<scope>`)**: 足さない — D3 のとおり番号が同じなら 1 エントリなので、`vlan-<N>` で足りる
- **SVI から機器を導くことを全体に広げる** (`derive.vlan_members` に一本化。dsl-designer): 改訂 1 では採らない — 同じ機器での `vlan_id` の重複の検査、VLAN の端点、
  エクスポーターの `vlan_member` エッジの意味が変わる。Pass C で再確認する
- **エクスポーターのキー `vlan_by_node` / `vlans_by_node` (辞書)**: 採らない — 辞書の形は既存の出力にない。`members` は入力でなくした名前と重なる (D7)

## References

- 関連 ADR: ADR-0005 (D4 補則・D6)、ADR-0011 (D4)、ADR-0013、ADR-0014 (D3・D4)、ADR-0015、ADR-0018 (D4)、ADR-0022、ADR-0023 (D7)、ADR-0025
- 横断評価: [evaluations/adr0026/evaluation.md](../evaluations/adr0026/evaluation.md)、試し書き `evaluations/adr0026/passb/` (B1〜B5)
- CLAUDE.md: 「MLNDL フォーマット概要」の `layer2.vxlan`、「バリデーション項目」の VNI の参加ノード・ゲートウェイ冗長
- RFC 7432 §6.1 (VLAN-based service、PE ごとの VID)、§6.3 (VLAN-aware bundle)
- RFC 8365 §5.1 (内側の VLAN タグ)、§5.1.1 (VNI の範囲)、§5.1.3 (Ethernet Tag の値)
- NetBox の L2VPN と L2VPN Termination (1 つの L2VPN に複数の VLAN)
