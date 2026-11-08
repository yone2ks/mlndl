# ADR-0022: 記載の粒度 — 構成図に書くものと、装置の設定に任せるもの

- **Status**: Accepted (2026-11-08 に実装)
- **Date**: 2026-11-08
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: C (5 エージェントの検討を 4 回行った。下書きはない)
- **関連**: ADR-0005 D3-2 (スコープ外の明示表)・D4 補則 (書くかどうかの問い 1〜4)、ADR-0011 D4 (`gateway_redundancy`)、
  [ADR-0023](0023-per-device-lag-and-ethernet-segments.md) (機器ごとの LAG と `ethernet_segments`)

## Context

MLAG と ESI-LAG を 1 つの構文で書く検討 (ADR-0023) で、最初の案は LACP の system-id (`system_mac`)、ESI の値 (10 バイト)、
MLAG の `domain_id`、bond ごとの番号 (vPC 番号・clag-id・mc-ae-id) を書く方向だった。ユーザーの指摘:

> NW 構成図に記載する情報の粒度として、MAC アドレス相当までは記載しない認識です。

ADR-0005 D4 補則の問い 1〜3 (秘匿情報か / 転送テーブルの個別エントリか / 削除すると関係が成り立たないか) では、これらを判定しきれない。
ESI の値や domain_id は秘匿情報でも経路でもなく、実機では消すと関係が成り立たない (問い 3 では「書く」になる)。
一方、構成図にこれらを書いても、読み手は図から何も読み取れない。読み取れるのは「この 2 台の bond が 1 本に見える」という関係だけである。

既にある構文にも MAC がある: `gateway_redundancy` の `anycast_mac` (ADR-0011 D4。同じ VLAN の SVI 群で一致を検査していた) と、
MLAG の `system_mac`。ADR-0011 D4 / D8 はこれらをスコープ内と確定していた (ADR-0005 D3-2 の注記)。

## Decision

### D1. ADR-0005 D4 補則に問い 5 「構成図の粒度か」を足す

問い 1〜3 で「書く」となったものも、次の問いで「書かない」になりうる。

5. **構成図を読む人が、その値から関係を読み取るか。それとも装置に設定するためだけの値か** →
   装置に設定するためだけの値 (識別子の具体的な値・MAC アドレス・自動で作られる値) は書かない。
   関係は id の参照で書き、その関係を装置の上で成り立たせる番号や MAC は上位のツール (設定の生成) が決める

判断の目安:

| 書く (図から関係や性質が読める) | 書かない (装置の設定の粒度) |
|---|---|
| VLAN ID、VNI (ネットワークをまたいで一致させる番号で、図に書く) | MAC アドレス全般 (anycast MAC、LACP system-id、system MAC) |
| IP アドレス、AS 番号、RD / RT | ESI の値 (多くは LACP や MAC から自動で作る。type 1 / type 3) |
| VRRP / HSRP の `group_id`・`priority` (どちらが master かが図で読める) | MLAG / vPC のドメインの番号 (`domain_id`)、bond ごとの番号 (vPC 番号・clag-id・mc-ae-id) |
| 冗長のモード (all-active / single-active。ADR-0023 D4) | どの脚が転送するか (DF)、DF 選出の preference |
| LACP の `mode` (active / passive) | ピアリンクの機器上の名前 (`peer_link_interface`) |

VLAN ID・VNI は「番号」だが、複数の機器・ネットワークで一致させることで関係が成り立ち、構成図にも書く値である。
domain_id や vPC 番号は、2 台の設定どうしを結び付けるための値で、関係そのものは ADR-0023 の `ethernet_segments` の参照で書ける。

### D2. `gateway_redundancy` の `anycast_mac` をなくす

```yaml
gateway_redundancy:
  - {mode: anycast_gateway}          # anycast_mac は書かない
```

- `anycast_mac` を書くと、書かない理由を示す error にする。読み替えはしない (1.0 のリリース前なので warning の期間を置かない)
- anycast gateway の一致の検査は `ip` / `ipv6` だけになる。MAC の一致は設定の生成が保証する
- ADR-0005 D3-2 の注記 (ADR-0011 D4 / D8 で `anycast_mac` と `system_mac` をスコープ内に確定した) を取り消す。
  `system_mac` は ADR-0023 で `layer1.lag` からなくした

### D3. この粒度の原則で、ADR-0023 の束ねる関係から落とすもの

ESI の値・LACP system-id・domain_id・vPC 番号 / clag-id・ピアリンクの機器上の名前は書かない。
`ethernet_segments` にこれらのキー (`esi` / `system_mac` / `domain_id` / `peer_link(s)`) を書くと、書かない理由を示す error にする。

## Consequences

**良い影響:**

- 構成図に書くかどうかを、問い 5 で決められる。技術が増えても「その番号を書くか」で迷わない
- MLAG と EVPN multihoming で、書くものがそろう (どちらも「どの機器の脚を束ねるか」だけ)
- 設定の生成に要る値は、上位のツールが `device_type` と id から決める。MLNDL の YAML に機器ごとの番号が散らばらない

**悪い影響 / トレードオフ:**

- テナントごとに違う anycast MAC を使う運用 (少ない) は、MLNDL では書けない。上位のツールの設定で機器の id を引いて持つ ([ADR-0024](0024-remove-node-overrides.md) で `overrides` をなくしたときに直した)
- 既存の YAML の `anycast_mac` は error になる。リポジトリの例 (`examples/eveng-evpn-lab*.yaml`) から消した

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer3.py` (`AnycastGateway`)、`src/mlndl/schema/layer1.py` (`Lag` / `EthernetSegment` の旧キー)
- バリデーター: `src/mlndl/validator.py` (anycast の一致検査から MAC を外した)
- 文書: ADR-0005 (D3-2 の注記・D4 補則)、ADR-0011 D4、`docs/reference/`、`CLAUDE.md`

## Alternatives Considered

- **問い 5 を足し、MAC 相当は書かない** *(採用案)*
- **問い 3 の但し書きにする**: 「削除すると関係が成り立たなくても、関係を id で書けるなら値は書かない」。問い 3 の意味が分かりにくくなるので、独立した問いにした (mlndl-spec-architect)
- **`anycast_mac` だけ残す**: 2 回目の検討で 2 人が推した (NX-OS の `fabric forwarding anycast-gateway-mac` は全スイッチで一致が必須で、検査に意味がある)。
  3 回目で、一致は設定の生成が保証すればよく、構成図の読み手は MAC から何も読まないとして 5 人とも外す側に変わった
- **ESI の値を任意で書けるようにする**: 手で書く type 0 の ESI はあるが、値から読める関係はない。関係は `ethernet_segments` の参照で書ける

## References

- ADR-0005 D3-2・D4 補則、ADR-0011 D4
- RFC 7432 §5 (Ethernet Segment Identifier の種類)
- RFC 9135 (EVPN の distributed anycast gateway)
