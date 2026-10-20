# ADR-0014: VXLAN のトンネル端点 (VTEP)

- **Status**: Draft — 実装済み (2026-10-20)。Pass B / C は未実施
- **Date**: 2026-10-20
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: A (5 エージェントの評価を 2 回取った。1 回目の推奨 `anycast_ip` にユーザーが疑問を出し、方式中立の形に改めた)
- **Amends**: ADR-0005 D4 補則 (問い 4 を追加)、ADR-0002 D7 (推奨プレフィックス `vtep-`)
- **関連**: ADR-0001 D8、ADR-0005 D4 補則・D6、[ADR-0011](../0011-layer3-data-plane.md) (「書けないまま残るもの」1)、[ADR-0013](../0013-vlan-ports-on-lag.md)、drafts/0010 (制御プレーン・保留中)

## Context

L2VNI は `vtep_source` (L3 IF の id、単数) と `members` (ノードの id) を持っていた。VTEP はノード (NVE インターフェース) の
属性で、1 つの VNI には複数のノードが参加するのに、VNI ごとに 1 ノード分の VTEP しか書けなかった。
`valid_full_dc.yaml` は `vtep_source: leaf1-lo, members: [leaf1, leaf2]` で、leaf2 の VTEP を表せていなかった。
MLAG ペアが共有する VTEP のアドレス (anycast VTEP) も書けなかった (ADR-0011 の「書けないまま残るもの」の 1 番)。

1 回目の評価では、VTEP を独立したエンティティにすること (5/5) と、MLAG ペアで 1 つのエンティティにして共有アドレスを
`anycast_ip` に書くこと (3/5) が推された。これにユーザーが「なぜ `anycast_ip` なのか。方式が増えるたびに構文が増えるのか」
と問い、2 回目の評価で 5/5 が `anycast_ip` と `type: anycast` を撤回した。

## Decision

### D1. 方式中立: 構文は関係の形で決め、方式名は構文に入れない

VTEP の冗長化には、MLAG の anycast VTEP (Cumulus)、両ピアのループバックに同じ IP (Arista)、ループバックの secondary IP
(NX-OS vPC)、Multi-Site BGW の anycast など、ベンダーと方式ごとに呼び名がある。しかし関係の形はどれも
**「1 つ以上のノードが、1 つのトンネル端点アドレスを終端する」** で同じである。

そこで、構文は関係の形だけを表し、方式名をフィールド名や型に入れない。方式による設定の違い (NX-OS の advertise-pip、
Cumulus の `clagd-vxlan-anycast-ip` など) は、機器の種類 (`device_type`) から上位ツールが導く。

**型を分ける基準**: 持つフィールドの形が違うときだけ型を分け、方式名では分けない。既存の Tagged Union はこの基準に合う。

| 構成子 | 分けている理由 |
|---|---|
| `lag.type: lacp \| mlag` | `node` (単数) と `nodes` + `peer_link` で、持つフィールドが違う |
| `gateway_redundancy.mode` | VRRP / HSRP は `group_id` / `vip` / `priority`、anycast gateway は `anycast_mac` |
| `vxlan.type: l2vni \| l3vni` | `vlan` を指すか `vrf` を指すか |
| `tunnel_interfaces.type` | カプセル化の種類 (列挙値。フィールドの形は同じなので型は分けていない) |
| VTEP の単独 / 共有 | **形が同じ** (`sources` の数だけが違う) → 型を分けない |

この基準を ADR-0005 D4 補則に問い 4 として加える。

### D2. `layer2.vteps`

```yaml
layer2:
  vteps:
    - id: vtep-leaf1-leaf2                  # 推奨プレフィックス vtep-
      sources: [leaf1-lo1, leaf2-lo1]       # この VTEP を終端するノードの L3 IF (ループバック)
      address: 10.0.100.12/32               # VTEP のアドレス (複数ノードで共有)
    - id: vtep-border1
      sources: [border1-lo1]                # 1 つなら address は省略でき、border1-lo1 の ip になる
```

| フィールド | 内容 |
|---|---|
| `sources` | この VTEP を終端するノードの L3 IF の id (1 つ以上)。ノードは各 L3 IF から決まるので `node` は持たない (ADR-0005 D6) |
| `address` / `address_v6` | VTEP のアドレス (CIDR)。`address` は IPv4、`address_v6` は IPv6 (L3 IF の `ip` / `ipv6` と同じ分け方) |

- **アドレスを省略できるのは `sources` が 1 つのときだけ**。そのときは、その L3 IF の `ip` / `ipv6` を使う (ユーザー判断)。
  複数のノードで共有するときは、ループバックの ip が全員同じ (Arista 式) でも `address` を書く。共有の意図が YAML に残り、
  偶然 ip が一致しただけのものを共有と読むことがない
- フィールド名は `address` (ユーザー判断)。`ip` にすると、`sources` が指す L3 IF の `ip` (ノード固有) と同じ語が 2 層に並ぶ

### D3. VNI は `vteps` で VTEP を指す

```yaml
  vxlan:
    - {id: vni-10100, type: l2vni, vni: 10100, vlan: vlan-100, vteps: [vtep-leaf1-leaf2, vtep-border1]}
```

L2VNI に参加するノードは、`vteps` の各 VTEP の `sources` から導く。旧 `members` はこの情報の二重表現だったので廃止する。

L3VNI には今回 `vteps` を持たせない。L3VNI が載るノードは、その VRF に属する L3 IF を持つノードから導けるため
(ユーザーは「どちらでもよい」とした。必要になれば加算で足せる)。

### D4. 移行

`vtep_source` と `members` は ndl_version 1.x の間だけ受け付け、warning を出す (`--strict` では error)。2.0 で廃止する。

- **自動では読み替えない**。旧形式の `members` に複数ノードがあっても、それが VTEP の共有なのか、ノードごとの別の VTEP
  なのかは YAML から分からないため (dsl-designer・spec-architect)。warning に従って `layer2.vteps` を書き起こす
- `vteps` と旧形式の併記はスキーマで error
- 旧形式でも従来の検査 (`vtep_source` の参照、そのノードが `members` に含まれるか、MTU の範囲) は働く

### D5. 検証規則

| チェック | Severity |
|---|---|
| `sources` が 1 つ以上 (型) | error |
| 共有 (`sources` が複数) なのに `address` / `address_v6` がない (型) | error |
| `address` に IPv6 を書いた (型。`address_v6` へ案内) | error |
| `sources` が `layer3.interfaces` に定義されているか | error |
| 同じ L3 IF を 1 つの VTEP に 2 回、または 2 つの VTEP に書いていないか | error |
| 1 つの VTEP に、同じノードの L3 IF を 2 つ書いていないか | error |
| `sources` が 1 つで `address` がなく、その L3 IF にも ip / ipv6 がない (アドレスが決まらない) | error |
| `sources` が 1 つで、`address` とその L3 IF の ip が食い違う | warning |
| 2 つの VTEP のアドレスが重複していないか (共有なら 1 つの VTEP にまとめる) | error |
| MLAG ペアの片方だけが VTEP を終端している (相方の書き忘れの可能性) | warning |
| L2VNI の `vteps` が定義済みの VTEP か、重複していないか | error |
| L2VNI に `vteps` も旧 `vtep_source` もない (型) | error |
| L2VNI に参加するノードに、その VLAN のポートがない (ADR-0011 D9) | warning |
| 旧形式 `vtep_source` / `members` | warning |
| 推奨プレフィックス `vtep-` | warning |
| underlay MTU >= 1550 の対象を、VTEP を終端するノードどうしのリンクにする (既存の検査の範囲を変更) | error |

1 つのノードが複数の VTEP を終端すること (別の L3 IF で) は許す。Multi-Site BGW がサイト内の VTEP と BGW の共有 VTEP を
両方持つ構成を、エントリを 2 つ書いて表すため。

### D6. 方式ごとの書き方

構文を足さずに、次のように書く (試し書きは `evaluations/adr0014/neutral/`)。

| 方式 | 書き方 |
|---|---|
| 単独の VTEP | `sources: [border1-lo1]` (address は省略) |
| Cumulus の MLAG anycast | `sources: [leaf1-lo, leaf2-lo]` (各 lo は固有 IP) + `address: <共有 IP>` |
| Arista の MLAG | `sources: [leaf1-lo1, leaf2-lo1]` (両方の lo1 が同じ ip) + `address: <その ip>`。固有 IP は別の L3 IF (Loopback0) |
| NX-OS vPC (secondary IP) | `sources: [leaf1-lo1, leaf2-lo1]` (ip = 各ノードの primary) + `address: <secondary の共有 IP>` |
| Multi-Site BGW の anycast | `sources: [bgw1-lo2, bgw2-lo2, bgw3-lo2]` + `address`。サイト内の VTEP は別のエントリ |
| EVPN multihoming (ESI-LAG) | VTEP はノードごとの単独エントリ。冗長は Ethernet Segment (LAG 側) の話で、VTEP の構文は変わらない |

NX-OS で `address` が secondary を意味することは構文からは読めない。L3 IF の `ip` は primary、VTEP の `address` は
VTEP として使うアドレス、という役割の違いだけを表し、どう設定に落とすかは `device_type` から上位ツールが決める。

### 範囲外 (別 ADR)

- **BUM 配送方式** (ingress replication / multicast group): ラウンド4 Pass C で決めた順序どおり別 ADR。
  置き場所 (VTEP か VNI か) もそこで決める (dsl-designer は VNI ごとに切り替えるのが実装の常識と指摘)
- **EVPN multihoming の Ethernet Segment** (ESI、DF election): `layer1.lag` の拡張として別 ADR
- **advertise-pip / virtual-rmac**: `device_type` から上位ツールが導く。制御プレーン (drafts/0010) の再開時に再確認
- **VXLAN の UDP ポート** (既定 4789): 必要になるまで足さない
- **EVPN の next-hop、ingress replication のピアリスト**: 個別の経路情報 (ADR-0005 D4 補則の問い 2)

## Consequences

- MLAG ペアの anycast VTEP、ノードごとの VTEP、3 ノード以上で共有する VTEP を、同じ構文で書ける
- 共有アドレスは 1 か所 (`address`) にしか書かないので、ピア間の食い違いが構造上起きない
- 冗長化の方式が増えても、関係の形が同じなら構文は増えない
- fixture 5 本 (VNI 8 件) を新形式に移行した。MLAG ペアの 2 本には、今まで書けなかった共有アドレスを足した

### 影響を受けるコンポーネント

- スキーマ: `layer2.py` (`Vtep`、`L2VxLAN.vteps`、旧 `vtep_source` / `members` を任意に)
- バリデーター: `validator.py` (`_validate_vteps`、`_check_vni_vteps`、`_check_legacy_vtep_source`、MTU の範囲、推奨プレフィックス)
- エクスポーター: `cytoscape.py` (L2VNI のノードに `vteps` を出す)
- テスト: `tests/test_vteps.py` (32 件)

## Alternatives Considered

- **`type: anycast` + `anycast_ip` (MLAG ペアで 1 エンティティ)**: 1 回目の評価で 3/5 が推したが撤回 — 「anycast」は方式の名前で、
  NX-OS の secondary IP を anycast と呼ぶと誤解を招く。方式ごとに型やフィールドが増える (ユーザーの指摘)
- **ノードごとの VTEP + 両ピアのループバックに同じ IP + `anycast_group`** (spec-architect の 1 回目): 却下 — 共有アドレスを 2 か所に書き、
  食い違いを validator で照合することになる。NX-OS の secondary を表すにはループバックを分ける必要がある
- **VNI の `vtep_source` をリストにする**: 却下 — VTEP はノードの属性で、VNI の数だけ同じリストを繰り返す
- **MLAG (`lag`) に共有 VTEP を持たせる**: 却下 — MLAG 以外でも VTEP を共有する (Multi-Site BGW)
- **フィールド名 `ip` / `ipv6`** (linguist): 却下 (ユーザー判断) — 本文 D2
- **ループバックの ip が全員同じなら `address` を省略可** (network-tech-reviewer・dsl-designer): 却下 (ユーザー判断) — 本文 D2
- **L3VNI にも `vteps`** (spec-architect・network-tech-reviewer): 今回は見送り — 本文 D3

## References

- 試し書き: `evaluations/adr0014/` (1 回目の 4 案)、`evaluations/adr0014/neutral/` (方式中立モデルで 7 構成)
- RFC 7348 (VXLAN)、RFC 8365 (EVPN を使う NVO)、RFC 9135 (EVPN IRB)、RFC 7432 (EVPN)
