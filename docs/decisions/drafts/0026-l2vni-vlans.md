# ADR-0026: L2VNI は機器ごとに番号の違う VLAN を束ねる (`vlans`)

- **Status**: Draft
- **Date**: 2026-11-15
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: A (5 エージェントの評価を 1 回取った。4/5 が案 A、example-author は案 C を推した)
- **Amends**: [ADR-0014](../0014-vteps.md) D3 (L2VNI の VLAN の参照)、[ADR-0011](../0011-layer3-data-plane.md) D4 (anycast gateway の一致の単位)
- **関連**: ADR-0005 D4 補則・D6、[ADR-0013](../0013-vlan-ports-on-lag.md)、ADR-0015、ADR-0022、[ADR-0023](../0023-per-device-lag-and-ethernet-segments.md)、[ADR-0025](../0025-end-grace-for-old-forms.md)

## Context

EVPN-VXLAN では、ブロードキャストドメインを識別するのは VNI で、VLAN の番号は機器の中だけの番号である。
leaf1 では VLAN 20、leaf3 では VLAN 30 を同じ L2VNI 10020 に載せる構成は、既存の L2 の番号を残したままファブリックに収容するときに普通に使う。
Cumulus (NVUE)・NX-OS (`vn-segment`)・EOS (`vxlan vlan X vni Y`)・Junos・SONiC のどれでも、機器ごとに別の VLAN を同じ VNI に対応させて書ける。

RFC もこれを妨げない。

- RFC 8365 §5.1: VXLAN の VTEP は、既定では内側の VLAN タグを付けずにカプセル化する。VLAN の番号は VTEP の外に出ない
- RFC 8365 §5.1.3: VLAN-based service (MAC-VRF に VNI が 1 つ) の EVPN ルートの Ethernet Tag は 0。機器間で VID を合わせる要件はない
- RFC 7432 §6.1: VLAN-based service で、PE ごとに VID が違ってよい (RFC はこれを "VID translation" と呼び、受け側の PE で行う)

今の MLNDL ではこれを書けない。

- L2VNI の `vlan` は `layer2.vlans` の id を 1 つだけ指す (`Annotated[str, Ref("layer2.vlans")]`)
- VLAN のエントリは `vlan_id` を 1 つ持ち、ポートで複数の機器にまたがる (機器はポートから導く。ADR-0013)
- 同じ `vni` の L2VNI を 2 つ書くと VNI の重複で error。L2VNI を 1 つにして `vlan: vlan-20` とすると、leaf3 の `vlan-30` は VNI とつながらず、
  「VNI に参加するノード 'leaf3' には VLAN 'vlan-20' のポートがありません」の warning が出る (2026-11-15 に確かめた)

ndl-viz は L2VNI の下に `vlan` を 1 つだけ描くので、番号の違う機器は図から落ちる。ndl-viz は推定で埋めない方針なので、言語の側で書けるようにする。

## Decision

### D1. L2VNI の `vlans` は VLAN のリスト

```yaml
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
  vxlan:
    - id: vni-10020
      type: l2vni
      vni: 10020
      vlans: [vlan-20, vlan-30]            # この VNI に載る、機器ごとの VLAN
      vteps: [vtep-leaf1-leaf2, vtep-leaf3, vtep-leaf4]
```

- 型は `Annotated[list[str], Ref("layer2.vlans")]`、要素は 1 つ以上 (`min_length=1`)。参照の存在の検査は `Ref` の宣言で付く (ADR-0015)
- 全機器で番号が同じ普通の構成は `vlans: [vlan-100]` と 1 要素で書く
- L3VNI は変えない (`vrf` を持ち、VLAN を持たない)

### D2. 旧 `vlan:` は移動先を示す error

`vlan` (単数) は読み替えず、書いたら次の error にする (ADR-0025 D1 と同じ形)。`vlan` と `vlans` の両方を受ける形は採らない。

> L2VNI の vlan はなくしました。vlans: [vlan-100] のようにリストで書いてください。機器ごとに VLAN の番号が違うときは、番号ごとの VLAN を並べます (ADR-0026)

### D3. VLAN のエントリと L2VNI の意味

- **ブロードキャストドメインを表すのは L2VNI**。VLAN のエントリは「1 つの 802.1Q の番号と、その番号でつながるポート」を表す
- VLAN のエントリを分けるのは**番号が違うときだけ**。同じ番号なら、何台の機器にまたがっても 1 エントリに書く (今と同じ)。
  そのため id は `vlan-<N>` のままで足り、`vlan-leaf1-20` のような機器名入りの id の規約は足さない
- 別の機器で同じ番号を別のドメインに使う (今も許している) ときの id の付け方は、この ADR では決めない

### D4. 機器とその機器の VLAN を導く

L2VNI の各 VLAN が、どの機器の VLAN かは参照をたどって導く。新しいフィールドは足さない。

1. VLAN のポート (`{interface:}` / `{lag:}` / `{ethernet_segment:}`) の機器 (ADR-0013 と同じ。ES は脚の全機器)
2. その VLAN を `attaches_to: {vlan:}` で指す SVI の `node`

2 を足すのは、ポートを持たず SVI だけを持つ機器 (border leaf など) の VLAN を決めるため。今の「VNI に参加するノードに VLAN のポートがない」の warning も、
2 を数えるように変える。ポートも SVI もない参加機器は、どの VLAN かが決まらない。図ではその機器を「VNI に参加し、VLAN は書かれていない」として出し、推定で埋めない。

`derive.py` に「L2VNI ごとに、機器 → VLAN の id」を返す関数を足し、validator とエクスポーターで共用する。

### D5. 検証規則

| チェック | Severity |
|---|---|
| `vlans` が 1 つ以上 (型) | error |
| `vlans` が `layer2.vlans` に定義されているか (`Ref`) | error |
| 旧 `vlan` (D2) | error |
| 同じ VLAN を 1 つの L2VNI の `vlans` に 2 回書いた | error |
| 1 つの VLAN が 2 つの L2VNI の `vlans` に入っている | error |
| 1 台の機器で、1 つの L2VNI の `vlans` のうち 2 つ以上がその機器の VLAN になる (D4 で導く) | error |
| 同じ Ethernet Segment の脚 (LAG / L1 IF) が、同じ L2VNI の番号の違う VLAN に分かれている | error |
| 1 つの L2VNI の `vlans` に同じ `vlan_id` の VLAN が 2 つある (1 エントリにまとめる) | warning |
| VNI に参加するノード (VTEP から導く) に、`vlans` のどの VLAN もない (D4 の 1・2 で数える。今の warning を広げる) | warning |

- 1 台の機器で 2 つの VLAN を同じ VNI に載せる設定は、NX-OS などが受け付けない。1 つの VNI のブリッジドメインを 2 つの番号で定義することになるため
- ES の脚の機器で番号が違うと、相手 (サーバー) からは 1 本の LAG なのに、脚ごとに別のタグを求められる。
  ES を `{ethernet_segment:}` で 1 行で書けば番号は 1 つに決まるので、この error は脚を機器ごとの `{lag:}` で書いた場合にだけ出る
- 「機器ごとの VLAN が同じ L2VNI に載る」ことの検査は、ここに挙げたものだけ。番号が違うこと自体は warning にしない

### D6. anycast gateway の一致は VNI 単位

ADR-0011 D4 の「同じ VLAN の anycast gateway 群で `ip` / `ipv6` が一致する」を、次のように変える。

- SVI の VLAN が L2VNI の `vlans` に入っていれば、**その L2VNI の SVI 全体**で一致を検査する
- どの L2VNI にも入っていない VLAN の SVI は、今までどおり VLAN ごとに検査する

leaf1 の `Vlan20` と leaf3 の `Vlan30` は同じブロードキャストドメインのゲートウェイなので、同じアドレスでなければ、着いた機器によってホストのゲートウェイが変わる。
VLAN 単位のままだとこの食い違いを見逃す (spec-architect は VLAN 単位のままを推したが、network-tech-reviewer と example-author の指摘を採った)。

### D7. エクスポーター

- L2VNI のノードの `vlan` (文字列) を `vlans` (id のリスト) に替える。旧キーは併記しない (ADR-0025 D3 と同じ)
- 機器ごとの対応 (D4) を L2VNI のノードに `vlan_by_node: {<node>: <vlan の id>}` として出す。決まらない参加機器は出さない
- `docs/exporter-cytoscape.md` を直す。ndl-viz は L2VNI から VLAN へ線を複数描く

### 範囲外

- **アクセスポートでの番号の付け替え** (外から来たタグ 100 を機器の中の VLAN 20 として扱う設定): ポートの設定で、構成図の粒度ではない (ADR-0022 の問い 5)。
  この ADR の「機器ごとに番号が違う」は、RFC 7432 §6.1 の呼び方では VID translation だが、機器のポートで番号を付け替える機能とは別のものとして扱う。
  ADR と docs では「VLAN translation」の語を使わず「機器ごとに番号が違う」と書く
- **VLAN-aware bundle** (1 つの MAC-VRF に複数の VLAN を入れ、VLAN ごとに別の VNI を持つ。RFC 8365 §5.1.3 では Ethernet Tag に VID を使い、番号を EVI 内でそろえる):
  MLNDL は今、サービスの種類 (VLAN-based / VLAN-aware bundle) を書かない。書く必要が出たときに別の ADR で扱い、そのときに D5 の検査との関係を見直す
- **Ethernet Tag ID の値**: 書かない (RFC で決まる値、または装置に設定するためだけの値。ADR-0022)
- **VLAN のエントリに `node` を持たせる**: しない (ADR-0005 D6、ADR-0013)。ポートも SVI もない機器の番号は書けないまま残す (D4)

## Consequences

**良い影響:**
- 機器ごとに VLAN の番号が違う L2VNI を書け、図に機器ごとの VLAN を出せる
- 1 つの VNI について知りたいこと (載る VLAN と、載る VTEP) が L2VNI のエントリ 1 つで読める (ADR-0014 で VTEP を L2VNI 側に集めたのと同じ向き)
- 番号が違う VLAN の SVI どうしでの anycast gateway の食い違いを見つけられる

**悪い影響 / トレードオフ:**
- 全機器で番号が同じ普通の構成でも、`vlan: vlan-100` を `vlans: [vlan-100]` に書き換える (1 要素のリスト)
- 機器の設定の書き方 (NX-OS・IOS-XE・Junos・NVUE は VLAN の下に VNI を書く) とは参照の向きが逆になる。設定から MLNDL を作るアダプターは、VNI ごとに VLAN を集める。
  ただし VLAN のエントリが複数の機器にまたがる今の形でも、機器をまたいで番号ごとにまとめる処理は案 C でも要るので、差は小さい
- 1 つの VLAN が 2 つの L2VNI に入ることは型では防げず、validator で error にする (案 C なら型で防げる)

**影響を受けるコンポーネント:**
- スキーマ: `src/mlndl/schema/layer2.py` (`L2VxLAN.vlan` → `vlans`、旧 `vlan` の error)
- derive: `src/mlndl/derive.py` (L2VNI ごとの機器 → VLAN、D4)
- バリデーター: `src/mlndl/validator.py` (D5 の検査、VNI 参加ノードの warning を SVI も数える形に、`_check_anycast_consistency` を VNI 単位に)
- エクスポーター: `src/mlndl/exporter/cytoscape.py`、`docs/exporter-cytoscape.md` (D7)
- サンプル: `tests/fixtures/` の L2VNI を持つ 4 本 (`valid_full_dc.yaml`・`invalid_vni_duplicate.yaml`・`valid_multisite_wan.yaml`・`valid_multi_vlan.yaml`)、
  `examples/eveng-evpn-lab.yaml`・`examples/eveng-evpn-lab-extended.yaml` を `vlans: [...]` に。機器ごとに番号が違う valid / invalid の fixture を足す
- 文書: `docs/reference/layer2.ja.md`・`docs/reference/validation.ja.md`、`docs/concepts.ja.md` (VLAN のエントリと L2VNI の意味、D3)、CLAUDE.md、ADR-0014 D3 と ADR-0011 D4 に改訂の注記
- 下流: ndl-viz (L2VNI から VLAN へ複数の線、`vlan_by_node`)

## Alternatives Considered

- **案 A: L2VNI の `vlan` を `vlans` (リスト) にする** *(採用案)*: 4/5 (spec-architect・linguist・dsl-designer・network-tech-reviewer) が推した
- **案 B: `vlan` と `vlans` の両方を受ける**: 却下 — 同じことを 2 通り書け、ADR-0025 の方針 (旧形式は読み替えずに error) に反する (全員一致)
- **案 C: VLAN 側に `vni: vni-10020` を持たせ、L2VNI は VLAN を指さない**: 却下 (example-author が第一候補とした)。
  - 利点: 機器の設定の書き方と向きが一致する。普通の構成で記述量が変わらない。1 つの VLAN が 2 つの VNI に入ることを型で防げる。
    MLNDL 内にも VRF の `l3vni` という同じ向きの前例がある
  - 却下の理由: VNI に載る VLAN を知るには全 VLAN を逆引きする。VTEP は L2VNI 側 (`vteps`)、VLAN は VLAN 側と、1 つの VNI の情報が 2 か所に分かれる。
    VXLAN を使わない VLAN にも `vni` の欄が並ぶ。NetBox の L2VPN (1 つの L2VPN が VLAN を複数持つ) は案 A と同じ向き。
    型で防げる利点は、D5 の error 1 つで補える
- **案 D: VLAN のエントリ 1 つの中に機器ごとの番号を持たせる** (`vlan_ids: [{node, vlan_id}]` やポートごとの `vlan_id`): 却下 — VLAN のエントリに `node` を書くことになり、
  ポートから導く機器と二重になる (ADR-0005 D6・ADR-0013)。普通の構成で `vlan_id` と `vlan_ids` の 2 通りの書き方ができる。ポートごとの番号はポートでの付け替えと混ざる
- **案 E: 同じ `vni` の L2VNI エントリを複数許す**: 却下 — 1 つの VNI は 1 つのブロードキャストドメインで、エントリが分かれると誤読を招く。VNI の一意性の検査を外すことになる
- **フィールド名 `mapped_vlans` / `member_vlans`**: 採らない — `vteps` / `sources` / `members` / `ports` と同じく、参照先のコレクション名の複数形にそろえる (linguist)
- **機器ごとの VLAN の id 規約 (`vlan-<node>-<N>` / `vlan-<N>-<scope>`)**: 足さない — D3 のとおり番号が同じなら 1 エントリなので、`vlan-<N>` で足りる
  (example-author は ES 側と leaf4 の VLAN 20 を別エントリにして `vlan-20-es` / `vlan-20-leaf4` を考えたが、今の仕様でも 1 エントリで書ける)

## References

- 関連 ADR: ADR-0005 (D4 補則・D6)、ADR-0011 (D4)、ADR-0013、ADR-0014 (D3)、ADR-0015、ADR-0022、ADR-0023、ADR-0025
- CLAUDE.md: 「MLNDL フォーマット概要」の `layer2.vxlan`、「バリデーション項目」の VNI の参加ノード・ゲートウェイ冗長
- RFC 7432 §6.1 (VLAN-based service、PE ごとの VID)、§6.3 (VLAN-aware bundle)
- RFC 8365 §5.1 (内側の VLAN タグ)、§5.1.3 (Ethernet Tag の値)
- NetBox の L2VPN と L2VPN Termination (1 つの L2VPN に複数の VLAN)
