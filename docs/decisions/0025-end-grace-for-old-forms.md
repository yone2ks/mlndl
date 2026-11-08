# ADR-0025: 1.0 の前に旧形式の猶予 (warning) をやめる

- **Status**: Accepted (2026-11-09 に実装)
- **Date**: 2026-11-09
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: C (5 エージェントの検討を 1 回で行った。下書きはない)
- **Amends**: ADR-0001 D8 (旧形式の扱い)、ADR-0011 D10・D11 (エクスポーターの旧キー)、ADR-0013 D2、[ADR-0014](0014-vteps.md) D4、
  ADR-0018 D4、ADR-0010 (移行の改訂)
- **関連**: ADR-0020 / ADR-0022 / ADR-0024 (同じ形で書き方をなくした)、ADR-0011 D11 (ノードの代表アドレスを定義しない)

## Context

最初のリリースは 1.0 で、それまでは破壊的な変更を許し、旧形式は猶予を置かずに移動先を示す error にする (ADR-0010 の移行の改訂)。
1.0 の後は、破壊的な変更にメジャーバージョンの更新が要る。

この方針を決める前に、いくつかの旧形式を「ndl_version 1.x の間は読み替えて受け付け、warning を出す。2.0 で受け付けをやめる」と決めていた。
このまま 1.0 を出すと、読み替えのコード (スキーマ・validator・derive・エクスポーター) と旧形式を受ける余地が 2.0 まで残る。

| 対象 | 決めた場所 | 今まで |
|---|---|---|
| L3 IF の `interface` キー (→ `name`) | ADR-0011 D10 | スキーマで読み替え、warning |
| L3 IF の短縮形 `interface: vlan-N` (→ `name` + `attaches_to: {vlan:}`) | ADR-0011 D3・D10 | 同上 |
| `{interface: <LAG / VLAN / サブ IF の id>}` (→ `{lag:}` / `{vlan:}` / `{subinterface:}`) | ADR-0001 D8、ADR-0011 D10 | validator が参照先の種類で読み、warning |
| VLAN のポートの `node` | ADR-0013 D2 | validator が照合し、warning |
| L2VNI の `vtep_source` / `members` (→ `layer2.vteps` と `vteps`) | ADR-0014 D4 | validator が warning |
| OSPF / IS-IS の通り道の食い違い | ADR-0018 D4 | warning (2.0 で error と予告) |
| エクスポーターの旧キー (L3 IF の `interface` / `kind` / `vlan` / `subinterface` + `vlan_id` / `lag`、ノードの `lo_ip` / `lo_ipv6`) | ADR-0011 D11、`docs/exporter-cytoscape.md` | 1.x の間だけ併記 |

examples/ と tests/fixtures/ には、これらの旧形式を使ったものはない。まだ外部の利用者もいない。

また、ADR-0014 (VTEP) と ADR-0015 (参照先の宣言) は実装済みなのに Draft のままで、Accepted の ADR-0018・ADR-0023 がこの 2 つに頼っている。

## Decision

### D1. 入力の旧形式を、移動先を示す error にする

読み替えをやめ、書いたら移動先を示す error にする (ADR-0020 / ADR-0024 と同じ形)。読み替えのコードも消す。

| 旧形式 | メッセージ (要旨) |
|---|---|
| L3 IF の `interface: swp51` | `L3 IF の interface はなくしました。機器上の名前は name に書き、L1 IF などへの参照は attaches_to: {interface: <L1 IF の id>} のように書きます` |
| L3 IF の `interface: vlan-100` (`attaches_to` なし) | `L3 IF の短縮形 interface: vlan-100 はなくしました。name: <機器上の名前> と attaches_to: {vlan: vlan-100} に書き換えてください` |
| `attaches_to: {interface: lag-leaf1-po1}` | `{interface:} は L1 インターフェース専用です。'lag-leaf1-po1' は LAG なので {lag: lag-leaf1-po1} と書いてください。機器上の名前は name に書き、参照先の種類は attaches_to のキーで示します` |
| VLAN のポートの `node` | `VLAN のポートの node はなくしました。ノードは参照先の interface / lag / ethernet_segment から導くので、node の行を消してください` |
| L2VNI の `vtep_source` / `members` | `L2VNI の vtep_source / members はなくしました。layer2.vteps に VTEP を書き (sources: [<ループバックの L3 IF の id>])、L2VNI では vteps: [<VTEP の id>] で参照してください` |

- `{interface: X}` の誤りはスキーマでは分からない (X の種類を知るにはトポロジー全体が要る)。validator の参照の解決で、X がその場所に書ける別のキーの種類なら、正しいキーを示す error にする。
  VLAN / bridge のポート、Ethernet Segment の脚、サブ IF の基盤、L3 IF の `attaches_to` のどれでも同じ形で示す。
  これは `{lag: <L1 IF の id>}` のような逆向きの取り違えにも効く
- `name` と `attaches_to` の取り違えは、IOS の `interface Port-channel1` の感覚で起きやすい (試し書き)。L3 IF の `attaches_to` の誤りには、
  「機器上の名前は `name`、参照先の種類は `attaches_to` のキー」の一文を添える

### D2. OSPF / IS-IS の通り道の食い違いを error にする

BGP と同じく error にする。ADR-0018 D4 の「1.x の間は warning、2.0 で error」を繰り上げる。

network-tech-reviewer が、正しい構成が error にならないことを確かめた。確かめた構成は次のとおり:

- unnumbered (アドレスのない L3 IF。基盤の L1 IF で通り道を導く)
- GRE / IPsec の上の OSPF (対になるトンネル IF)
- 片側が `destination_ip` のトンネル (食い違いにしない)
- 事業者網の bridge
- routed LAG、サブ IF
- 同じ VLAN の SVI どうし
- ループバックどうし

error になるのは、ADR-0018 で範囲外とした構成 (拠点のルーターと箱のあいだに自社の L2 スイッチが 1 段はさまる、3 拠点以上のマルチアクセス) だけで、これは BGP でも同じく error になる。

あわせて次の 2 つを直す:

- IS-IS の食い違いのメッセージには、トンネルで直す案 (c) を出さない (IS-IS の `interface` はトンネル IF を指せない。ADR-0018 D3)
- 端の機器と `update_source` / `interface` の機器が食い違うセッションには、通り道の食い違いを重ねて出さない (原因は 1 つなので)

### D3. エクスポーターの旧キーを外す

Cytoscape の JSON から、次のキーを外す。

| キー | 代わり |
|---|---|
| L3 IF の `interface` | `name` |
| L3 IF の `kind` | `attachment` (ADR-0011 D11) |
| L3 IF の `vlan` / `subinterface` + `vlan_id` / `lag` | `attaches_to` (サブ IF のタグはノードの `subinterfaces[].vlan_id`) |
| ノードの `lo_ip` / `lo_ipv6` | なし |

`lo_ip` / `lo_ipv6` は、エクスポーターが推定で選んだノードの代表アドレスで、言語として定義しない値である (ADR-0011 D11)。
名前の `lo_` はループバックを含意するのに、中身はループバックとは限らない (mlndl-linguist)。
今の DC は VTEP 用と BGP 用でループバックを使い分けるので、ノードに代表アドレスが 1 つという前提も成り立たない (network-tech-reviewer)。
「推測は出さない」の例外として残す理由がないので、代わりは置かない。
L3 IF ごとの `name` とアドレス、参照の役割 `roles` (`update_source` / `vtep_source`) は今までどおり出す。

ndl-viz はこの旧キーを使っていたので、同じ時期に直す (`lo_ip` を使っていた旧 topology ビューは、L3 IF が 1 つだけのノードでそのアドレスを出す)。

### D4. ADR-0014 と ADR-0015 を Accepted にする

どちらも実装済みで、Accepted の ADR (ADR-0010 D7・ADR-0018 D3・ADR-0023 D5 / D7) が本文で頼っている。
Pass B / C は改めて行わず、Status を Accepted にして `docs/decisions/drafts/` から `docs/decisions/` に移す。
ADR-0014 D4 (移行) はこの ADR の D1 で置き換える。

### D5. 1.0 の後の方針

1.0 の後に書き方を変えるときも、「読み替えて warning で受け付ける」は既定にしない。
読み替えが要るなら、その ADR で理由を書いて決める。旧形式を受けると、新旧の書き方が同居し、ツールもそれに頼るようになる。

## Consequences

**良い影響:**

- 同じ参照を 2 通りに書ける箇所がなくなり、キーが参照先の種類を示す原則 (ADR-0001 D8) に例外がなくなった
- 読み替えのコードが消えた (スキーマの `migrate_legacy` と deprecations、validator の旧形式の照合と `_check_legacy_vtep_source`、derive の旧形式の LAG の読み替え、エクスポーターの代表アドレスの推定)
- 同じ「通り道の食い違い」が、BGP と OSPF / IS-IS で同じ重さになった
- エクスポーターの出力が、MLNDL に書かれた情報と参照から導いた値だけになった

**悪い影響 / トレードオフ:**

- 旧形式で書いた YAML は読めなくなる。YAML エクスポーターで新形式に書き出す移行の道もなくなる (読めないので)。
  メッセージの移動先に従って手で直す。利用者はまだいない
- `lo_ip` を使って 1 台に 1 つのアドレスを出していた表示は、どの L3 IF を出すかをビューワが自分で決める必要がある (推定はしない)

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer3.py` (`L3Interface`)、`src/mlndl/schema/layer2.py` (`PortRef`・`L2VxLAN`)
- バリデーター: `src/mlndl/validator.py` (`_resolve_ref`、VLAN のポートのノード、VTEP、OSPF / IS-IS の通り道)
- 導出: `src/mlndl/derive.py` (`port_legs`・`l3_attachments`)
- エクスポーター: `src/mlndl/exporter/cytoscape.py`、`docs/exporter-cytoscape.md`
- 文書: ADR-0001・0005・0010・0011・0013・0014・0015・0018、`docs/reference/`、`CLAUDE.md`
- ndl-viz: `lo_ip` と L3 IF の旧キーへの依存を外す

## Alternatives Considered

- **新しい ADR 1 本で扱う** *(採用案)*: 5 エージェントとも推した。どれも「1.0 の前に 1.x の猶予をやめる」という 1 つの判断で、各 ADR に散らすといつ外したかを追いにくい
- **各 ADR (0011 D10 / 0013 D2 / 0014 D4 / 0018 D4) を個別に改訂する**: 履歴が 4 か所に分かれる。各 ADR には改訂の注記だけを残した
- **読み替えを残す (2.0 まで)**: Kubernetes の非推奨 API のように変換の層が長く残る。1.0 の前で利用者がいないので、残す理由がない (mlndl-dsl-designer)
- **OSPF / IS-IS の食い違いだけ warning のまま残す**: 同じ「食い違い」の語が BGP と OSPF で別の重さになる (mlndl-linguist)。誤検知もない (D2)
- **`lo_ip` を役割から選び直して残す** (VTEP の source → update_source の順など): 推定であることは変わらない。選び方はビューワの表示の判断で、言語の出力にしない

## References

- 試し書き: 旧形式と新形式の対 5 組と、OSPF の通り道が食い違う例 (mlndl-example-author。今の挙動で旧形式は warning、新形式は通ることを確かめた)
- ADR-0010 の「移行の改訂」(最初のリリースは 1.0)
