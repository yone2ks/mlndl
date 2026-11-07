# ADR-0020: L1 リンクの `mtu` をなくす

- **Status**: Accepted (2026-11-07 に実装)
- **Date**: 2026-11-07
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: C (5 エージェントの検討を 1 回で行った。下書きはない)
- **関連**: ADR-0003 / ADR-0009 (注釈側の構成子)、ADR-0005 (D4 補則)、ADR-0006 (無向のリンク)、ADR-0011 (L3 IF の MTU は先送り)、
  ADR-0017 (D4)、ADR-0018 (事業者網の MTU)、[先送りした項目](deferred.md)

## Context

L1 の整理を、1.0 をリリースした後では直せないもの (既にあるフィールドの意味) から始めた。
先送りの一覧に「`L1Link.mtu` の意味 (Ethernet ヘッダーを含むか)」が残っていた (ADR-0018)。
ユーザーから「リンクの速度は意識するが、MTU は意識しなくてよいのではないか」という問いが出た。

調べて分かったこと:

- `layer1.links[].mtu` は制約のない整数で、L2 のフレーム長なのか IP の MTU なのかが決まっていない。Ethernet ヘッダーを数えるかはベンダーで違う (9216 / 9000 など)
- examples と fixtures の値は 9216 と 1500 の 2 種類だけで、`link_role` からそのまま決まっていた。リンクごとに意味のある違いはなかった
- MTU を使う検査は 1 つだけだった。VXLAN の underlay の MTU が 1550 以上かを見る検査で、`link_role` が `"underlay"` と綴られたリンクだけを対象にし、`mtu` を書かなければ何も見ない。
  `link_role` は注釈側の自由文字列 (コアは値を見ない。ADR-0003 / ADR-0009) なのに、その綴りが error を出すかを決めていた。注釈の値を見る検査はこれだけだった
- 実機では、MTU はケーブルではなくインターフェース (あるいはシステム全体) の設定である。両端で値が違ってもリンクはつながる。
  データセンターではシステム全体で 9216 などに揃え、リンクごとには決めないのが普通である

`link_speed` は両端の交渉で同じ値に決まる媒体の性質なので、無向のリンク (ADR-0006) に置いてよい。MTU は片側ずつの設定なので、無向のリンクに 1 つだけ置く形と合わない。

## Decision

### D1. `layer1.links[].mtu` をなくす

L1 リンクには MTU を書かない。1.0 のリリース前なので、猶予期間 (warning) は設けない。
書いた場合は、なくしたことを示す error にする (ADR-0010 D12 と同じく、一般の「余分なキー」ではなく理由を示す)。

```
layer1.links の mtu はなくしました。MTU はインターフェースの設定で、リンク (ケーブル) の性質ではないためです (ADR-0020)
```

### D2. VXLAN の underlay の MTU 検査をなくす

`link_role: underlay` のリンクの MTU が 1550 以上かを見る検査をやめる。書かなければ通り、書く人はほぼ 9216 と書くので、検査として働いていなかった。
注釈の値で検査が変わる箇所もこれでなくなる。

### D3. トンネル IF の `mtu` は残す

`layer3.tunnel_interfaces[].mtu` は残す。カプセル化のオーバーヘッドから決まるトンネル IF 自身の値で、ADR-0005 D4 補則の問い 3 の例 (「トンネルの MTU」) のとおり書く側に入る。

### D4. インターフェース単位の MTU は先送りする

MTU を書く必要が出たら、L3 IF (または L1 IF) の属性として足す。後から足しても既存の YAML は壊れない (加算的変更)。
そのときに、何の MTU か (L2 のフレーム長か IP の MTU か)、名前 (`mtu` / `ip_mtu` / `l2_mtu`)、両端の食い違いの検査を決める。
きっかけと一緒に [先送りした項目](deferred.md) に載せる。

## Consequences

**良い影響:**

- 意味の決まらないフィールドが 1 つ減り、ADR-0018 の宿題 (Ethernet ヘッダーを含むか) が消えた
- 注釈側の自由文字列の値を見る検査がなくなり、ADR-0003 / ADR-0009 の原則と食い違う箇所がなくなった
- MTU を書く場所を将来作るとき、実機の単位 (インターフェース) に合わせて作れる

**悪い影響 / トレードオフ:**

- 図 (ndl-viz) の物理リンクに MTU を出せなくなる
- VXLAN の underlay の MTU 不足は検査しない。今も `mtu` を書かなければ検査されていなかったので、実質の差は小さい
- 事業者網の契約上の MTU などは、当面リンクや箱の `description` に書く (ADR-0017 D4)

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer1.py` (`L1Link.mtu` を削り、書いたら error)
- バリデーター: `src/mlndl/validator.py` (`_validate_mtu` を削る)
- エクスポーター: `src/mlndl/exporter/cytoscape.py` (リンクの `mtu` を出さない)
- サンプル: `examples/`、`tests/fixtures/` (`invalid_mtu_vxlan.yaml` を削る)
- 文書: `docs/reference/`、`docs/exporter-cytoscape.md`、`CLAUDE.md`
- ndl-viz: 物理リンクの MTU の表示をやめる

## Alternatives Considered

- **案 B: リンクから消す** *(採用案)*: 5 エージェントとも推奨した。
- **案 A: 残して意味を決める**: L2 のフレーム長・IP の MTU・最大フレーム長の 3 つを 1 つのフィールドで受ける決め方が見つからない。
  片側の設定を無向のリンクに 1 つだけ書く形も残る。検査の対象を `link_role` 以外から導くことはできるが、そこまでして守る値がない。
- **案 C: L1 IF か L3 IF に移す**: 実機の単位には合う。ただし両端に同じ値を 2 回書くことになり (試し書きで L1 の記述が倍になった)、
  今の YAML はどれも IF ごとの違いを書いていない。使われない表現力を先に抱えるより、必要になったときに足す (D4)。
- **段階的に廃止する (1.x の間は warning、2.0 で削除)**: 1.0 のリリース前は破壊的な変更を許す方針 (ADR-0010 の移行の改訂) なので取らない。

## References

- 試し書き: [evaluations/adr0020/](evaluations/adr0020/) (`case_a_current.yaml` / `case_b_no_l1mtu.yaml` / `case_c_on_if.yaml`)
- RFC 8344 (ietf-ip) — IP の MTU はインターフェースの IPv4 / IPv6 ごとの属性 (RFC 8343 の ietf-interfaces の `speed` とは別のモジュール)
- RFC 7348 (VXLAN) — カプセル化のオーバーヘッド
