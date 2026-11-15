# ADR-0026: L2VNI に、機器によって番号の違う VLAN を載せる (`vlans`)

- **Status**: Accepted (2026-11-15 に Pass C で確定。実装はまだ)
- **Date**: 2026-11-15
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author (Pass C)、ユーザー (案 A で確定、「VLAN translation」の語を使わない、範囲外の 2 点)
- **Pass**: C ([評価メモ](evaluations/adr0026/evaluation.md) を入力に再設計)
- **Supersedes**: [drafts/0026](drafts/0026-l2vni-vlans.md)
- **Amends**: [ADR-0014](0014-vteps.md) D3 (L2VNI の VLAN の参照)、[ADR-0011](0011-layer3-data-plane.md) D4 (anycast gateway の一致の単位)、
  CLAUDE.md のバリデーション項目「VLAN ID」(同じ機器での `vlan_id` の重複に SVI も数える)
- **関連**: ADR-0005 D4 補則・D6、[ADR-0013](0013-vlan-ports-on-lag.md) D7 (本文は変えない)、ADR-0015、ADR-0018 D4 (重ねて出さない考え)、ADR-0022、
  [ADR-0023](0023-per-device-lag-and-ethernet-segments.md) D7、[ADR-0025](0025-end-grace-for-old-forms.md)

## Context

EVPN-VXLAN では、ブロードキャストドメインを識別するのは VNI で、VLAN の番号は機器の中だけの番号である。
機器によって VLAN の番号が違うことがある構成 (leaf1・leaf2・leaf4 では VLAN 20、leaf3 だけ VLAN 30 を、同じ L2VNI 10020 に載せる) は、
既存の L2 の番号を残したままファブリックに収容するときに普通に使う。
Cumulus (NVUE)・NX-OS (`vn-segment`)・EOS (`vxlan vlan X vni Y`)・Junos・SONiC のどれでも、機器ごとに別の VLAN を同じ VNI に対応させて書ける。

RFC もこれを妨げない (2026-11-15 に本文で確かめた)。

- RFC 8365 §5.1: VXLAN の VNI は通常テナントの VID と 1 対 1 で、入口の VTEP は内側の VLAN タグを付けずにカプセル化する (RFC 7432 の VLAN-based service に当たる)。VLAN の番号は VTEP の外に出ない
- RFC 8365 §5.1.3: VLAN-based service (MAC-VRF に VNI が 1 つ) の EVPN ルートの Ethernet Tag は 0
- RFC 7432 §6.1: VLAN-based service で、PE ごとに VID が違ってよい。そのとき PE は VID を付け替える (RFC はこれを "VID translation" と呼ぶ)

今の MLNDL ではこれを書けない。L2VNI の `vlan` は `layer2.vlans` の id を 1 つだけ指し、VLAN のエントリは `vlan_id` を 1 つ持つ。
同じ `vni` の L2VNI を 2 つ書くと VNI の重複で error になり、L2VNI を 1 つにすると番号の違う機器の VLAN は VNI とつながらない (試し書き B1・P1)。
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

- 型は `Annotated[list[str], Ref("layer2.vlans")]`。要素は 1 つ以上 (`min_length=1`)、同じ id を 2 回書かない (スキーマの `model_validator`)。
  参照の存在の検査は `Ref` の宣言で付く (ADR-0015)。`tests/test_refs.py` の `NOT_REFERENCES` / `KEYED_REFERENCES` は変えない
- 全機器で番号が同じ普通の構成は `vlans: [vlan-100]` と 1 要素で書く (試し書き B4)
- 参照は L2VNI から VLAN への片方向だけ。VLAN のエントリには L2VNI への参照を持たせない
- L3VNI は変えない (`vrf` を持ち、VLAN を持たない)

### D2. 旧 `vlan:` は移動先を示す error

`vlan` (単数) は読み替えず、書いたら次の error にする (ADR-0025 D1 と同じ形)。`vlan` と `vlans` の両方を受ける形は採らない。

> L2VNI の vlan はなくしました。vlans: [vlan-100] のようにリストで書いてください。機器によって VLAN の番号が違うときは、番号ごとの VLAN のエントリを並べます (ADR-0026)

### D3. VLAN のエントリと L2VNI の意味

`docs/concepts.ja.md` には次の趣旨で書く。

> VLAN のエントリは、ある 802.1Q の番号と、その番号でつながるポートの組です。L2VNI に入らない VLAN では、VLAN のエントリ 1 つが 1 つのブロードキャストドメインです。
> L2VNI に入る VLAN では、ブロードキャストドメインを表すのは L2VNI で、その `vlans` に並んだ VLAN のエントリが合わさって 1 つのドメインになります。
> 機器によって番号が違う VLAN は、番号ごとに別のエントリにして、同じ L2VNI の `vlans` に並べます。

- VLAN のエントリを分けるのは**番号が違うときと、同じ番号を別のブロードキャストドメインに使うとき**だけ。同じドメインの同じ番号は、何台の機器にまたがっても 1 エントリに書く。
  そのため L2VNI のためだけに `vlan-leaf1-20` のような機器名入りの id は要らない。同じ番号を別のドメインに使うときの id の付け方は、この ADR では決めない
- Ethernet Segment は相手から 1 本の LAG に見えるので、脚の機器の番号は 1 つ。`{ethernet_segment:}` で書けば自然にそうなる。
  脚を機器ごとの `{lag:}` で書いて別の番号の VLAN に分けた場合だけ、D5 の error になる
- `vlans` は「1 つの VNI に載る、機器によって番号の違う VLAN」で、VLAN-aware bundle (1 つの MAC-VRF に入る、VNI の違う VLAN の集まり) ではない
- 用語: 番号 (`vlan_id` の値。本文で「VID」は RFC の引用でだけ使う)、VLAN のエントリ (`layer2.vlans[]` の 1 要素)、ブロードキャストドメイン。「VLAN translation」は使わない

### D4. 機器と VLAN の導き方

`derive.py` に 2 つの関数を置く。合わせ方は使う側が決める (1 つの関数にはまとめない)。

- `vlan_port_nodes(topology)`: VLAN の id → ポートを持つ機器。ポートは `{interface:}` / `{lag:}` / `{ethernet_segment:}` (ES は脚の全機器)。今の validator の `_port_nodes` を関数にしたもの
- `vlan_svi_nodes(topology)`: VLAN の id → その VLAN を `attaches_to: {vlan:}` で指す SVI の `node`

| 使う場所 | 数える機器 | 理由 |
|---|---|---|
| L2VNI の、機器とその機器の VLAN (D5・D7) | ポート ∪ SVI | SVI だけを持つ機器 (centralized gateway・border leaf) の VLAN を決める (試し書き B2・P4) |
| 同じ機器での `vlan_id` の重複の検査 (今ある検査) | **ポート ∪ SVI** (変更) | SVI もその機器の番号を使う。ポートで `vlan-100` (番号 100) を持つ機器が、SVI で別のエントリ `vlan-100b` (番号 100) を指す矛盾は、ほかの検査では拾えない |
| anycast gateway の一致 (D6) | SVI | 比べるのは SVI の値 |
| VLAN の端点 (ADR-0013 D7) | ポートだけ (変えない) | 端点はセグメントの外側の L3。SVI を入れると全 leaf の同じ anycast の IP が端点に並ぶ |
| エクスポーターの機器ノードの `vlans` と `vlan_member` エッジ | ポートだけ (変えない) | 「その機器にポートがある」の意味を保つ |

L2VNI について、機器の集まりは次の 2 つを区別する。

- **参加機器**: `vteps` の各 VTEP の `sources` の L3 IF の `node` (ADR-0014 D3。定義は変えない)
- **参加機器の VLAN**: その L2VNI の `vlans` に書いた VLAN のうち、ポートか SVI がその機器にあるもの。`vlans` に書いていない VLAN は見ない
  (SVI の VLAN を `vlans` に書き忘れると、その機器の VLAN は決まらない)

ポートも SVI もない参加機器 (Multi-Site の BGW のように VNI を中継するだけの機器など) は、VLAN が決まらない。図ではその機器を「VNI に参加し、VLAN は書かれていない」として出し、推定で埋めない。

### D5. 検証規則

| # | チェック | Severity |
|---|---|---|
| 1 | `vlans` が 1 つ以上、同じ id を 2 回書いていない (型) | error |
| 2 | `vlans` が `layer2.vlans` に定義されているか (`Ref`) | error |
| 3 | 旧 `vlan` (D2) | error |
| 4 | 1 つの VLAN が 2 つ以上の L2VNI の `vlans` に入っている | error |
| 5 | 1 台の機器で、1 つの L2VNI の `vlans` の VLAN が 2 つ以上ある (D4) | error |
| 6 | 同じ Ethernet Segment の脚 (LAG / L1 IF) の機器で、同じ L2VNI の VLAN の番号が違う | error |
| 7 | 1 つの L2VNI の `vlans` の VLAN を指す SVI の `vrf` が食い違う | error |
| 8 | 同じ機器で、別の VLAN のエントリが同じ `vlan_id` を使う (今ある検査。SVI の機器も数える。D4) | error |
| 9 | 1 つの L2VNI の `vlans` に同じ `vlan_id` の VLAN が 2 つある (1 エントリにまとめる) | warning |
| 10 | L2VNI の参加機器に、`vlans` のどの VLAN のポートも SVI もない (今の warning を広げる) | warning |

- **4**: 案 C (VLAN 側に L2VNI への参照) なら型で防げたものを validator で補う
- **5**: 1 つのブロードキャストドメインを、1 台の機器の中で 2 つの番号で定義することになる。どの機器も VLAN と VNI を 1 対 1 で対応させる
- **6**: 相手 (サーバー) からは 1 本の LAG なのに、脚ごとに別のタグを求められる。実機にもない構成
- **7**: 同じブロードキャストドメインのゲートウェイが別の VRF にあると、着いた機器によってトラフィックが別の VRF に入る
- **10**: `vlans` のどの VLAN にもポートと SVI が 1 つもないときは、判断できないので出さない (今の「VLAN にポートが書かれていない場合は見ない」と同じ)。
  BGW のような正しい構成でも出ることは受け入れ、抑える構文は足さない (装置の役割を書くことになり、ADR-0022 の粒度を越える)。
  メッセージは誤りと決めつけず、「VTEP で参加しているが、`vlans` のどの VLAN のポートも SVI もない。VNI を中継するだけの機器なら、このままでよい」の形にする
- 番号が違うこと自体は warning にしない

**重ねて出さない規則** (ADR-0018 D4 の「端の機器の誤りがあるセッションには重ねて出さない」と同じ考え):

- 4 の error がある VLAN は、どの L2VNI の側でも 5・6・7 と D6 の対象に入れない (参照の矛盾を直してから意味を比べる)
- 5 の error がある機器は、その L2VNI の 7 と D6 の対象に入れない
- 6 の error を出した VLAN には、ADR-0023 D7 の「ES の脚の一部だけ」の warning を重ねない
- warning どうし、warning と別の原因の error は重ねてよい

### D6. anycast gateway の一致は VNI 単位

ADR-0011 D4 の「同じ VLAN の anycast gateway 群で `ip` / `ipv6` が一致する」を、次のように変える。

- SVI の VLAN が L2VNI の `vlans` に入っていれば、**その L2VNI の SVI 全体**で `ip`・`ipv6` の一致を検査する
- どの L2VNI にも入っていない VLAN の SVI は、今までどおり VLAN ごとに検査する
- 拾う SVI は、今までどおり `gateway_redundancy` に `mode: anycast_gateway` を持つものだけ。MAC は比べない (ADR-0022)
- error のメッセージは L2VNI の id を主語にし、食い違う 2 つの SVI の id・VLAN・値を添える。例:
  `L2VNI 'vni-10020' の anycast gateway で ip が食い違っています: 'leaf3-vlan-30' (VLAN 'vlan-30') は 10.20.0.2/24、'leaf1-vlan-20' (VLAN 'vlan-20') は 10.20.0.1/24。anycast gateway は VNI のすべての機器で同じアドレスにします (ADR-0026 D6)`
- 同じ単位 (L2VNI か VLAN) の中に `anycast_gateway` の SVI と、`anycast_gateway` を持たない SVI (`vrrp` だけ、または冗長なし) が混ざっていたら **warning**。
  機器によってホストのゲートウェイが変わる。移行の途中などで一時的に混ざることがあるので error にはしない

leaf1 の `vlan20` と leaf3 の `vlan30` は同じブロードキャストドメインのゲートウェイなので、同じアドレスでなければ、着いた機器によってホストのゲートウェイが変わる。
VLAN 単位のままだとこの食い違いを見逃す (試し書き B5)。Symmetric IRB と Asymmetric IRB のどちらでも同じ要件になる。

### D7. エクスポーター

- L2VNI のノードの `vlan` (文字列) を `vlans` (id のリスト。YAML と同じ) に替える。旧キーは併記しない (ADR-0025 D3 と同じ)
- D4 で導いた対応を、L2VNI のノードに `node_vlans: [{node: <機器の id>, vlan: <VLAN の id>}]` として出す。VLAN が決まらない参加機器は出さない
  - リストの形は、Ethernet Segment の `members` や機器の `l3_interfaces[]` / `bgp_sessions[]` にそろえる。1 台の機器が複数の VLAN を持つ拡張にも形を壊さずに足せる
  - キー名を `members` にしないのは、入力の L2VNI で `members` をなくした (ADR-0014 D4・ADR-0025) ため
  - `node_vlans` はエクスポーターが導いた値で、YAML には書けない。`docs/exporter-cytoscape.md` に明記する
- 機器ノードの `vlans` (その機器にポートがある VLAN) と L2VNI のノードの `vlans` (その VNI に載る VLAN) は、同じキー名で意味が違う。`docs/exporter-cytoscape.md` で書き分ける
- 機器ノードの `vlans` と `vlan_member` エッジは変えない (D4)
- ndl-viz は L2VNI から VLAN へ線を複数描き、`node_vlans` で機器ごとの番号を示す。ndl-viz の側では導かない

### 範囲外

- **アクセスポートでの番号の付け替え** (外から来たタグ 100 を機器の中の VLAN 20 として扱う設定): ポートの設定で、構成図の粒度ではない (ADR-0022 の問い 5)。
  この ADR の「機器によって番号が違う」は、RFC 7432 §6.1 の呼び方では VID translation だが、ポートで番号を付け替える機能とは別のものとして扱う
- **VLAN-aware bundle** (1 つの MAC-VRF に複数の VLAN を入れ、VLAN ごとに別の VNI を持つ): MLNDL は今、サービスの種類を書かない。
  書く必要が出たら別の ADR で扱い、L2VNI の `vlans` を流用せず別のキー (例: `layer2.mac_vrfs`) にする
- **Asymmetric IRB の検査** (全 leaf に全 L2VNI の SVI が要る): 今は L3VNI の `irb_mode: symmetric` しか書かない。Asymmetric を扱うときに別の ADR で
- **VNI stitching** (Multi-Site の BGW で VNI を付け替える) と **ファブリックごとの VNI の番号の使い回し** (RFC 8365 §5.1.1): VNI の番号はトポロジー全体で一意のまま。別の ADR で
- **L2VNI の Route Target**: 今は書かない (VNI から自動で導く前提)。別の ADR で
- **Ethernet Tag ID の値**: 書かない (RFC で決まる値、または装置に設定するためだけの値。ADR-0022)
- **VLAN のエントリに `node` を持たせる**: しない (ADR-0005 D6、ADR-0013)。ポートも SVI もない機器の番号は書けないまま残す (D4)

## Consequences

**良い影響:**
- 機器によって VLAN の番号が違う L2VNI を書け、図に機器ごとの VLAN を出せる
- 1 つの VNI について知りたいこと (載る VLAN と、載る VTEP) が L2VNI のエントリ 1 つで読める (ADR-0014 で VTEP を L2VNI 側に集めたのと同じ向き)
- 今の validator が見逃していた誤り (1 台で 2 VLAN、1 VLAN が 2 VNI、番号の違う VLAN の SVI どうしの anycast の食い違い、ポートと SVI での同じ番号の矛盾) を見つけられる

**悪い影響 / トレードオフ:**
- 全機器で番号が同じ普通の構成でも、`vlan: vlan-100` を `vlans: [vlan-100]` に書き換える (1 要素のリスト)
- 機器の設定の書き方 (NX-OS・IOS-XE・Junos・NVUE は VLAN の下に VNI を書く) とは参照の向きが逆になる。設定から MLNDL を作るアダプターは、全機器を読んでから VNI ごとに VLAN を集める (試し書き P3)
- 「vlan-30 はどの VNI か」は全 L2VNI を探して答える。`derive.py` に逆引きの関数を置けば、ツールの側では困らない
- **L3VNI と参照の向きが違う**: L3VNI と VRF は 1 対 1 で、どちらも相手なしでは意味がないので、双方向に参照し一致を検査している (ADR-0011 D9)。
  VLAN は L2VNI なしでも成り立ち、L2VNI と VLAN は 1 対多なので、L2VNI から VLAN への片方向にし、「1 つの VLAN は 1 つの L2VNI まで」は validator の error で担保する (D5 の 4)。
  VTEP の `sources` や ES の `members` と同じ、束ねる側から指す流儀
- **ポートも SVI もない参加機器に warning が出る** (D5 の 10)
- 「VLAN の機器」を使う場所ごとに、ポートだけかポート ∪ SVI かが違う (D4 の表)。1 つの関数にまとめず、使う側で合わせる
- 同じ機器での `vlan_id` の重複の検査に SVI を数えるので、今は valid な YAML が error になることがある (ポートと SVI で同じ番号の別エントリを指すもの)。今の examples と valid の fixtures にはない (2026-11-15 に確かめた)

**影響を受けるコンポーネント:**
- スキーマ: `src/mlndl/schema/layer2.py` (`L2VxLAN.vlan` → `vlans`、`vlans` の重複、旧 `vlan` の error)
- derive: `src/mlndl/derive.py` (`vlan_port_nodes`・`vlan_svi_nodes`、L2VNI ごとの機器と VLAN、VLAN → L2VNI の逆引き)
- バリデーター: `src/mlndl/validator.py` (D5 の 4〜7・9・10、8 で SVI も数える、`_check_anycast_consistency` を VNI 単位に、モードの混在の warning、重ねて出さない規則)
- エクスポーター: `src/mlndl/exporter/cytoscape.py`、`docs/exporter-cytoscape.md` (D7)
- テスト: `tests/test_refs.py` の `BASE` (`vlan: vlan-100` → `vlans: [vlan-100]`)。新しいテスト (D5 の各検査、D6、D7)
- fixture: L2VNI を持つ 5 本 (`valid_full_dc.yaml`・`valid_dual_stack.yaml`・`valid_multisite_wan.yaml`・`valid_multi_vlan.yaml`・`invalid_vni_duplicate.yaml`) を `vlans: [...]` に。
  足すもの: 機器によって番号が違う構成 (B1)、SVI だけで参加する機器と BGW (B2・P4)、D5 の各 error (B3a〜B3c)、D6 の食い違い (B5)
- examples: `examples/eveng-evpn-lab.yaml`・`examples/eveng-evpn-lab-extended.yaml`
- 文書: `docs/reference/layer2.ja.md`、`docs/reference/validation.ja.md` (旧形式の表、VNI の参加機器・VLAN ID・anycast gateway の行)、`docs/reference/schema.json` (生成物)、
  `docs/concepts.ja.md` (D3)、CLAUDE.md (フォーマット概要の `vxlan` の例、バリデーション項目の VNI の参加ノード・VLAN ID・ゲートウェイ冗長・旧形式の行、ADR の表)、
  ADR-0014 D3 と ADR-0011 D4 に改訂の注記 (下の文案)
- 下流: ndl-viz (L2VNI から VLAN へ複数の線、`node_vlans`)

**改訂の注記の文案** (実装のときに各 ADR に足す):

- ADR-0014 D3 の末尾: 「**改訂 ([ADR-0026](0026-l2vni-vlans.md), 2026-11-15)**: L2VNI の `vlan` (単数) は `vlans` (リスト) にした。機器によって番号の違う VLAN を 1 つの L2VNI に載せられる。旧 `vlan` は移動先を示す error。参加ノードを `vteps` から導くことは変えない。」
- ADR-0011 D4 の anycast gateway の説明の末尾: 「**改訂 ([ADR-0026](0026-l2vni-vlans.md) D6, 2026-11-15)**: SVI の VLAN が L2VNI の `vlans` に入っていれば、`ip` / `ipv6` の一致はその L2VNI の SVI 全体で検査する。L2VNI に入らない VLAN は今までどおり VLAN ごと。」

## Alternatives Considered

- **案 A: L2VNI の `vlan` を `vlans` (リスト) にする** *(採用案)*: Pass A・Pass C ともに 4/5 (spec-architect・linguist・dsl-designer・network-tech-reviewer)。
  dsl-designer は Pass C で、Pass B の前の自分の推奨を疑ってゼロから比べ直しても案 A だった。ユーザーが案 A で確定した
- **案 B: `vlan` と `vlans` の両方を受ける**: 却下 — 同じことを 2 通り書け、ADR-0025 の方針に反する (全員一致)
- **案 C: VLAN 側に `l2vni: vni-10020` を持たせ、L2VNI は VLAN を指さない**: 却下 (example-author が Pass A・Pass C の 2 回推した)。
  - 利点: 機器の設定の書き方と向きが一致し、アダプターは設定の行を 1 対 1 に近く写せる (P3)。1 つの VLAN が 2 つの VNI に入ることを型で防げる。
    VRF の `l3vni` と同じ向き。「vlan-30 はどの VNI か」が VLAN のエントリで読める。将来の MAC-VRF と名前が紛れない
  - 却下の理由: VNI に載る VLAN を知るには全 VLAN を逆引きし、1 つの VNI の情報が L2VNI (`vteps`) と VLAN (`l2vni`) の 2 か所に分かれる (P2)。
    VLAN は L2VNI なしでも成り立つ独立したエンティティで、VXLAN を知らないままにしておく。型で防げる利点は D5 の 4 で補える。
    アダプターの変換は 1 回書けば済み、YAML を読む回数のほうが多い。NetBox の L2VPN (1 つの L2VPN が VLAN を複数持つ) も案 A と同じ向き
- **案 D: VLAN のエントリ 1 つの中に機器ごとの番号を持たせる** (`vlan_ids: [{node, vlan_id}]` やポートごとの `vlan_id`): 却下 — VLAN のエントリに `node` を書くことになり、
  ポートから導く機器と二重になる (ADR-0005 D6・ADR-0013)。普通の構成で 2 通りの書き方ができる。ポートごとの番号はポートでの付け替えと混ざる
- **案 E: 同じ `vni` の L2VNI エントリを複数許す**: 却下 — 1 つの VNI は 1 つのブロードキャストドメインで、エントリが分かれると誤読を招く
- **フィールド名 `member_vlans` / `vlan_entries`**: 採らない — `vteps` / `sources` / `ports` と同じく、参照先のコレクション名の複数形にそろえる (linguist)
- **「VLAN の機器」を 1 つの関数 (`vlan_members`) にまとめる**: 採らない — 端点・`vlan_member` エッジ (ポートだけ) と L2VNI (ポート ∪ SVI) で意味が違う (dsl-designer が Pass C で撤回)
- **同じ機器での `vlan_id` の重複の検査はポートだけのまま** (spec-architect・network-tech-reviewer): 採らない — ポートと SVI で同じ番号の別エントリを指す矛盾をほかに拾う検査がない
- **`anycast_gateway` と `vrrp` の混在を error** (network-tech-reviewer): warning にした — 移行の途中で一時的に混ざることがある
- **エクスポーターのキー `vlan_by_node` / `vlans_by_node` (辞書) / `members`**: 採らない — 辞書の形は既存の出力になく、`members` は入力でなくした名前と重なる (D7)
- **BGW の warning を抑える構文** (VTEP の役割など): 足さない — 装置の役割を書くことになり ADR-0022 の粒度を越える (network-tech-reviewer)

## Pass A との差分

Pass C の 5 エージェントは drafts/0026 を読まずに評価メモから再設計し、骨子 (案 A、D2・D3・D6・D7 の形) は改訂 1 と同じ結論になった。変わった点:

- **D4**: 改訂 1 は「SVI から機器を導くのは L2VNI の中だけ」としたが、関数を 2 つ (ポート / SVI) にして使う側で合わせる形にし、同じ機器での `vlan_id` の重複の検査にも SVI を数えることにした (dsl-designer)。参加機器と参加機器の VLAN の区別を本文に書いた (example-author)
- **D5**: 番号を振り、重ねて出さない規則に「1 つの VLAN が 2 つの L2VNI に」の error がある VLAN を他の検査から外す規則を足した (spec-architect)。D5 の 10 のメッセージを誤りと決めつけない形にした (example-author)
- **D6**: `anycast_gateway` と、それを持たない SVI の混在の warning を足した (network-tech-reviewer)
- **D7**: `node_vlans` が YAML に書けないこと、機器ノードの `vlans` との書き分けを足した (linguist)
- **範囲外**: Asymmetric IRB、VNI stitching、L2VNI の Route Target を足した (network-tech-reviewer)

## References

- 関連 ADR: ADR-0005 (D4 補則・D6)、ADR-0011 (D4・D9)、ADR-0013 (D7)、ADR-0014 (D3・D4)、ADR-0015、ADR-0018 (D4)、ADR-0022、ADR-0023 (D7)、ADR-0025
- 評価メモ: [evaluations/adr0026/evaluation.md](evaluations/adr0026/evaluation.md)。試し書き `evaluations/adr0026/passb/` (B1〜B5)、`evaluations/adr0026/passc/` (P1〜P4)
- CLAUDE.md: 「MLNDL フォーマット概要」の `layer2.vxlan`、「バリデーション項目」の VNI の参加ノード・VLAN ID・ゲートウェイ冗長
- RFC 7432 §6.1 (VLAN-based service、PE ごとの VID)、§6.3 (VLAN-aware bundle)
- RFC 8365 §5.1 (内側の VLAN タグ)、§5.1.1 (VNI の範囲)、§5.1.3 (Ethernet Tag の値)
- NetBox の L2VPN と L2VPN Termination (1 つの L2VPN に複数の VLAN)
