# ラウンド3 横断評価メモ (Pass B) — 制御プレーン (ADR-0010)

- **Date**: 2026-11-01
- **Evaluators**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **対象ドラフト**: [drafts/0010](../drafts/0010-control-plane-separation.md) (control plane と data plane の分離)。
  評価は 2 回行った: (1) D8 の再開時に r2 を対象に、(2) r3 を対象に横断評価。r4 は (2) の反映版
- **試し書き**: [adr0010/d8-r3/](adr0010/d8-r3/README.md) (r2 の構文。D8-a と D8-b の書き比べ 7 ケース)、
  [adr0010/r3/](adr0010/r3/README.md) (r3 の構文。6 ケースと eveng-evpn-lab-extended の制御プレーン部分)

---

## 評価の前提

ADR-0010 は 2026-09-20 に保留し、layer3 までのデータプレーン (ADR-0011〜0013、ラウンド4) を先に確定させた。
**Pass A は実装していない** (スキーマ・validator・fixture は旧構造のまま)。

2026-11-01 に再開したきっかけは ndl-viz の表示である。同じ機器の組に `protocols.bgp` の neighbor (両側から向き違いで 1 本ずつ・プロセスごと) と
`layer3.routing_adjacencies` が重なり、1 組に最大 6 本の線が出た。組ごとに 1 本へまとめると、別々のセッション (underlay の eBGP と EVPN の iBGP など) が
1 本の線に混ざって意味が通らなくなった。ユーザーの要件は「**線 1 本 = セッション 1 本で、両端の IP と AS、eBGP / iBGP、運ぶ AF が分かる**」こと
(ndl-viz は MLNDL に書かれた情報だけを表示し、推定で埋めない)。

評価の途中でユーザーが決めた事項がある。Pass C ではこれを前提とし、異論は §6 に別枠で置く。

| 日付 | 決定 |
|---|---|
| 2026-09-19 | トップレベル `protocols:` を廃止し `control_plane:` を新設する |
| 2026-09-19 | `layer3.routing_adjacencies` を `control_plane.routing_neighbors` に移動・改名する |
| 2026-11-01 | BGP エントリの単位は VRF ごとのインスタンス。underlay / overlay は構文に入れず AF から導く |
| 2026-11-01 | トポロジー外の相手は端点に `address` と `local_as` だけで書ける |
| 2026-11-01 | unnumbered は「update_source がアドレスを持たない L3 IF を指す」で表す |
| 2026-11-01 | インスタンスを指すフィールドは `instance` |
| 2026-11-01 | `router_id` は ADR-0016 に委ねる |
| 2026-11-01 | セッションには `attaches_to` を書かず、通り道は `update_source` の L3 IF から導く (r3 の `{link:}` / `{lag:}` から変更) |

## 章構成

1. 事実確認
2. アンカー検出
3. 指摘 (テーマ別)
4. 横断矛盾
5. 白紙再設計シミュレーション
6. ユーザー決定事項への異論 (別枠)
7. Pass C への Input サマリ

指摘の出典: S = spec-architect、L = linguist、D = dsl-designer、N = network-tech-reviewer、Y = example-author。

---

## 1. 事実確認

### 1-1. 二重表現と矛盾の実測

| 対象 | 事実 |
|---|---|
| `examples/eveng-evpn-lab-extended.yaml` を Cytoscape に export | 機器の組は 14 組。`routing_adjacency` 辺 27 本 + `bgp_session` 辺 52 本 = 79 本。spine–leaf の組は routing_adjacency 2 本 (underlay・EVPN) + bgp_session 4 本 (2 プロセス × 両側) で 6 本 |
| 同 leaf6–wan-rtr | routing_adjacencies は VRF ごとに 2 本、`protocols.bgp` の neighbor は 1 つ (VRF を書く場所がない) |
| `tests/fixtures/valid_multi_vlan.yaml` | leaf1 が underlay で AS65001、EVPN で AS65000 (F4)。この組の routing_adjacencies は 1 本で、`protocols.bgp` は 2 プロセス。セッションの本数がデータから決まらない |
| `tests/fixtures/valid_full_dc.yaml` / `valid_multisite_wan.yaml` | ループバックを `update_source` にしながら `attaches_to: {link:}` を書いたセッションがある (multihop なのに直結のリンクを指す) |
| 現行エクスポーター | `bgp_session` 辺に `bgp_type` (ebgp / ibgp) を出している (`docs/exporter-cytoscape.md` には未記載) |

### 1-2. 試し書きの実測

- **D8-a**: 7 ケース (2 セッション分離・unnumbered で 1 本に 2 AF・IGP + iBGP RR・VRF-lite・SVI 上の iBGP・管理外ピア・EVPN マルチサイト) すべて書けた (Y)
- **D8-b**: C1 で「同一 VRF に 1 エントリ」「同一ノード・同一 VRF で AS は 1 つ」と衝突。C2 (1 本で ipv4 と evpn) はどのエントリにも入れられない (Y)
- **r3 の構文**: eveng-evpn-lab-extended の制御プレーン部分が 159 行 → 約 55 行 (Y)
- **エクスポーターに出す値**: 6 ケースとも、両端の IP・AS・eBGP / iBGP・AF・VRF が参照をたどるだけで決まった。決まらないのは unnumbered の両端 IP だけで、出さないのが正しい (Y)
- **管理外ピアを r2 の構文で書くと**、相手側に形だけの L1 IF・L3 IF・リンクを作ることになった (Y、d8-r3/C6)
- **r3 の `attaches_to: {lag:}`**: 2 台の間の port-channel は LAG が機器ごとに 2 つあり、どちらを指すか決まらなかった (Y、r3/C5)

## 2. アンカー検出

- **ビューアーの要件が設計を駆動した。** 再開の理由は表示の都合である。ただし要件 (線 1 本 = セッション 1 本) は RFC 4271 のセッションの概念そのものであり、
  表示の都合を言語に持ち込んだものではない、と全員が判断した。Pass C でも「表示のための構文」が紛れていないかを確かめる
- **r2 の骨格は再検証されていない。** `routing_neighbors` をフラットに置き、インスタンスのエントリを別に持つ構造は 2026-09-19 の決定で、今回は D8 だけを問うた。
  OpenConfig / Batfish のようにセッションをインスタンスの中に置く案、Batfish のようにセッションを書かずに導く案は、r2 の Alternatives で退けたままである (§5)
- **r3 / r4 は同じ統合者が同じセッションで書いた。** とくに「セッションの通り道を導く (attaches_to を廃止)」は統合時の発見であり、5 エージェントの独立評価を経ずにユーザーが決めた。
  エクスポーターのフィールド名 (`path`・`external_bgp_sessions`・`interface_name`) も統合者が決めた
- **ndl-viz の暫定実装** (機器の組ごとに 1 本、役割での絞り込み) が先にあり、それが失敗した経験から要件が出た。暫定実装の形に引きずられていないかを確かめる

## 3. 指摘 (テーマ別)

### A. BGP エントリの単位 — 合意 (5/5)

VRF ごとのインスタンス (D8-a)。FRR / EOS / NX-OS / Junos の構造 (VRF ごとの `router bgp`、Junos は routing-instances) と RFC 8349・OpenConfig・Batfish に一致する (N, D)。
役割単位 (D8-b) は 1 本で複数 AF を運ぶ構成を書けず、D6 とも衝突する (Y)。`BGPProcess.role` は廃止 (S, N)。

### B. セッションの通り道 — 変遷あり (統合者の発見 → ユーザー決定)

- r2: `attaches_to: {node:} | {interface:} | {link:}`。r3: `{link:} | {lag:}` (D, Y)
- r3 の Pass B で 2 つの問題: LAG を指すとき機器ごとの 2 つのどちらか決まらない (Y)、SVI 上のセッションは VLAN が複数のリンクにまたがりうるので通り道を 1 本に決められず multihop と同じ扱いが実用的 (N)
- 統合時の発見: single-hop の通り道は `update_source` の L3 IF の `attaches_to` (L1 IF → リンク、LAG、サブ IF → その基盤) から導ける。セッションに書くと二重表現 (§1-1 の fixture の食い違いがその実例)。
  ADR-0005 D6 (`node` は基盤から導く)、ADR-0012 / 0013 と同じ考え方
- 残る論点: ADR-0001 D8 の表で routing_adjacencies に許していたキーを外すと、`{link:}` キーの使い道がなくなる。L1 ノード・L1 IF に残すかを決める (S)
- `update_source` を書かないセッションは通り道も IP も分からない。書くことを推奨にとどめるか、必須にするか

### C. BGP の端点 — 2 つの形

- トポロジー内 `{node, update_source}` / トポロジー外 `{address, local_as}`。トンネル (ADR-0011 D6) の `destination_interface` / `destination_ip` と同じ「相手をトポロジーに書いたか」での使い分け
- **型**: 1 つのクラス + `model_validator`。2 つのクラスの Union は、pydantic v2 の discriminator なし Union が先に合った型を選び、エラーも「どれにも合わない」になる (D)
- **注記**: 端点の `local_as` は「その端の相手自身の AS」で、インスタンスの `nodes[].local_as` と同じ視点。`remote_as` (廃止) のような相対値ではない。端点の `address` は相手のホストアドレスで、VTEP の `address` (CIDR) とは別物 (L)
- ISP の PE までのケーブルを書いた場合はトポロジー内として L3 IF を 1 つ書く (Y、r3/C6b)。トポロジー外の相手とだけ張るとこちらの L1 IF は対向なしで残る (Y)
- 「機器は書いたが L3 IF は書かない」中間の形 (`{node, address}`) は採っていない

### D. unnumbered

- 判定: `update_source` が `ip` も `ipv6` も持たない L3 IF を指す (N)。ADR-0005 D3-1 の「loopback でない IF」は IPv6 だけのループバックや SVI で誤判定する
- IPv6 のグローバルアドレスで張るセッションは unnumbered ではない (N)
- 表示: アドレスのない L3 IF は unnumbered 用とは限らない (書きかけ・未使用)。「unnumbered」と出すのはセッションが指すときだけ (Y)
- FRR の `v6only` とそうでないモードは区別できない (N。未解決へ)

### E. underlay / overlay

- セッションの性質ではない。overlay の BGP も underlay の上でループバックどうしに張る TCP 接続で、「何を運ぶか (AF)」と「どこを通るか」を束ねた呼び名 (統合・全員同意)
- 導き方は AF と VRF で 4 分類: EVPN / VPN を運ぶ → overlay、default VRF で ipv4 / ipv6 だけ → underlay、両方 → 両方、default 以外の VRF の ipv4 / ipv6 → どちらでもない (N)
- `labels: {fabric_role}` は却下: AF と同じ事実の二重表現 (S)、labels はノードの構成子でセッションには付けられない (S)、食い違いが検査されない (L)

### F. 検査 (D6)

- 参照先の存在は `Ref` の汎用検査 (ADR-0015) に任せ、手書きは意味の検査だけ (S, D)
- 追加: `update_source` の機器と端の機器の一致 (BGP)、OSPF / IS-IS の端点の IF の機器の一致 (S)、`update_source` の VRF とインスタンスの VRF の一致 (Y)、
  両端から導いた通り道の食い違い (統合)、トポロジー外の端と反対側のトランスポートのアドレスファミリーの一致 (N: 「トランスポートの」と明記)、
  RR クライアントは iBGP (D)、セッションの重複を L3 IF の id の組で判定 (D)
- default 以外の VRF に `l2vpn_evpn` / `vpnv4` / `vpnv6`: 例外 (Inter-AS 等) を言い切れないので warning、`--strict` で error (N)
- router_id の検査は ADR-0016 (S)

### G. 命名

- `process` → `instance` (L, S)。Terms・RFC 8349 と一致、OS のプロセスと紛れない
- `update_source` は維持 (L): IF を指す語で unnumbered でも崩れない。`local_address` はアドレス前提、`source` はトンネルと衝突
- D7: 区別の語はノード対の末尾 (`bgp-peer-spine1-leaf1-evpn`)。間に挟むと `bgp-peer-<A>-<B>` の形が崩れる (L)。「AF 名を入れない」と例の `-evpn` が矛盾していた (S)
- エクスポーターの `bgp_type`: L は `session_type` を提案。現行の `bgp_session` 辺が既に `bgp_type` を出しているため r4 は維持
- `from.name` → `interface_name` (L)
- 文中の揺れ: 「プロセス → 隣接」(D2)、「ピア関係」(L)

### H. エクスポーターと ndl-viz

- 1 セッション = 1 辺。両端の機器・L3 IF・IP・AS、eBGP / iBGP、AF、VRF、導いた通り道を載せる (D, S)
- 導出は `derive.py` の 1 つの関数で行い、validator とエクスポーターが共有する (D)
- トポロジー外の相手とのセッションは辺にせずノードのデータに (トンネルと同じ) (D)
- 運用者が線で見たい情報の優先順位: 両端 IP (unnumbered は IF 名) → AS と eBGP / iBGP → AF → router-id → BFD → RR 関係 (N)。状態 (Established 等) はスコープ外

### I. 文書と書き方

- EVPN の 3 構成 (1 本で複数 AF / underlay と overlay を分ける eBGP multihop / IGP + iBGP RR) は、推奨順を決めない中立の書き方に。
  r2 の「eBGP multihop の overlay はベンダー / RFC いずれも推奨していない」は誤り: RFC 7432 / 8365 は EVPN を iBGP に限らず、Arista EOS や Cisco NX-OS の設計ガイドが紹介する選択肢 (N)
- OSPF / IS-IS はポイントツーポイント前提 (マルチアクセスは Phase 3)。OSPF の area `0` と `0.0.0.0` の正規化 (N)
- `examples/eveng-evpn-lab.yaml` の `role: route_server` / `route_server_client` の移行方法 (N)
- `role: isp` は推奨語彙の外でも valid と注記 (S)

## 4. 横断矛盾

| 箇所 | 矛盾 | 出典 |
|---|---|---|
| ADR-0001 D2 の例・D8 の表 | routing_adjacencies に `{link:}` (と `node` / `interface`) を許している。通り道を導く決定と矛盾 | S |
| ADR-0005 D3-1 | unnumbered の判定規則 (loopback でない IF)、`routing_adjacencies[].attaches_to` 行、P6 (`remote_as: external`) | S, N |
| drafts/0016 | `router_id` を `protocols.bgp[]` に先行して置く案。`control_plane` へ移す必要 | S, D |
| drafts/0010 r2 の D2 | VTEP を `vtep_source` / `members` で記述 (ADR-0014 以前の構造) | S |
| CLAUDE.md | attaches_to の表 (「リンク (BGP 等)」行)、ADR 表、router_id の検証行 | S |

## 5. 白紙再設計シミュレーション

ドラフトを見ずに要件から組み立てると、次の 3 案が候補になる。

| 案 | セッションの置き場所 | 長所 | 短所 |
|---|---|---|---|
| フラット (r2〜r4) | `control_plane.routing_neighbors[]`、所属は `instance` で参照 | プロトコル横断で列挙しやすい (ndl-viz)。ADR-0005 Alt-4 (フラット + 参照) と整合 | 所属の参照を書く必要がある |
| インスタンスの中 (OpenConfig) | `control_plane.bgp[].sessions[]` | 所属が構造で決まり、`instance` 参照が要らない | プロトコル横断の列挙で全エントリを巡回。r2 で却下 |
| 書かずに導く (Batfish) | なし。各機器の neighbor 設定から導く | 二重表現が原理的にない | 記述言語としては「意図したセッション」が書けない。片側だけの設定の検出が仕事になる |

試し書きは主にフラット案で行った。インスタンスの中に置く案は d8-r3 / r3 では書いていない。

## 6. ユーザー決定事項への異論 (別枠)

覆すよう求めるものではなく、Pass C で判断材料として扱う。

| 決定 | 異論 | 出典 |
|---|---|---|
| トポロジー外の相手は `address` + `local_as` | 同じ値 (相手の IP) を 2 通りに書けるようになる。相手の L3 IF を 1 つ書けば今の参照の仕組みがそのまま使える | D (D8 再開時) |
| 端点の AS も `local_as` | 同じ語が「インスタンスのノード自身の AS」と「トポロジー外の相手の AS」に使われ、記述する側から見た値と誤読されうる。注記で緩和 | L |
| セッションの通り道を導く | SVI 上のセッションが peer-link の LAG の上を流れることは VLAN のポートからたどれば分かるが、セッションの通り道としては出なくなる | N の指摘を統合時に解釈 |
| underlay / overlay を構文に入れない | 人向けの分類を残したい需要はある (`fabric_role` 案)。導き方を informative として書くことで代替 | L |

## 7. Pass C への Input サマリ

**Pass C で参照するもの**: 本評価メモ、Accepted の ADR (0001・0002・0005・0006・0009・0011〜0013)、drafts/0014・0015・0016、CLAUDE.md、
`evaluations/adr0010/` の試し書き。**drafts/0010 は参照しない** (Pass C の原則)。実装はまだないので、移行は旧構造 (`layer3.routing_adjacencies` と `protocols`) から考える。

### 確定すべき論点 (優先順)

1. **セッションの記述**: 置き場所 (§5 の 3 案。ユーザー決定はフラット)、端点の 2 つの形と型、`instance`、unnumbered、通り道の導出 (B〜D)
2. **ADR-0001 の `{link:}` キー**の扱い (B)
3. **検査の一覧と Severity** (F)
4. **エクスポーターの出力の形**と `derive.py` の共有関数 (H)
5. **命名**: D7 の ID、`bgp_type` / `session_type`、`interface_name`、`path` (G)
6. **関連文書の同時改訂**: ADR-0001・0005・0016、CLAUDE.md (§4)
7. **範囲外の明記**: per-neighbor local-as、Confederation、multihop の経路 (`carried_by`)、OSPF / IS-IS のマルチアクセス、micro-BFD、`v6only`

### 独立に同じ結論に到達した点

- D8-a (5/5)
- underlay / overlay を構文に入れない (S, L, N, D。`fabric_role` は S が二重表現として退け、L は informative にとどめるなら可とした)
- AF はセッションにだけ書く (D, N)
- single-hop / multihop を構文に出さない (L, N, D)

### 退けた指摘

- `bgp_type` → `session_type` (L): 現行出力との連続性を優先 (Pass C で再判断してよい)
- `BgpEndpoint` に `multihop: bool | int` を任意で許す (N、D8 再開時): 導出できる。方式名を構文に入れない
- `{lag:}` は両端のどちらかの LAG を指せばよい (Y): セッションの `attaches_to` 自体を廃止したため不要

---

## Pass C の結果 (2026-11-01)

5 エージェントが drafts/0010 を読まずに本メモから再設計し、割れた論点をユーザーが判断した。確定版は [ADR-0010](../0010-control-plane-separation.md)。
試し書きは [adr0010/passc/](adr0010/passc/README.md) (fixture 3 本と examples の移行、誤りを混ぜた例)。

| 論点 | 結論 | 経緯 |
|---|---|---|
| 1. セッションの記述 | フラット (`routing_neighbors`)。BGP の端点は `node` の有無で型を選ぶ 2 つの型 (トポロジー内 / 外)。**トポロジー内の端点の `update_source` は必須** | 端点の型は dsl-designer (Pass B の 1 つの型 + `model_validator` から変更)。必須化は dsl-designer、spec-architect は任意を推奨 → ユーザーが必須と判断 (BGP のセッションを書かなければ何も要求しない、を確認のうえ) |
| RR の書き方 | セッションの端点の `route_reflector_client` (neighbor 単位) | dsl-designer はノードの `role: route_reflector` を提案。network-tech-reviewer が、RR と non-client の相手・階層 RR・同じクラスタの RR どうしを書き分けられないと指摘し、端点のフラグを維持 |
| 2. ADR-0001 の `{link:}` キー | 削除 | spec-architect・dsl-designer・network-tech-reviewer が一致 → ユーザー確認 |
| 3. 検査 | 両端から導いた通り道の食い違い・トランスポートの AF・RR は iBGP は error (network-tech-reviewer)。SVI は両端が同じ VLAN かまで | — |
| 4. エクスポーター | 機器のデータに `bgp_sessions` (その機器のセッションすべて。トンネルの `tunnels` と同じ形)、両端がトポロジー内なら辺も。通り道は `transport_link` | `path` は AS_PATH と紛れる (linguist)。`external_bgp_sessions` は eBGP と紛れ、`off_topology_bgp_sessions` は意味が伝わりにくい (ユーザー) → トンネルと同じ形にした |
| 5. 命名 | `instance`・`update_source`・`bgp_type`・`interface_name` を維持。2 本目の ID の接尾辞は用途の語 (`-overlay` 等) | AF 名の接尾辞は 1 本で複数 AF を運ぶセッションと紛れる (linguist) |
| 6. 関連文書 | ADR-0001 (D8)・ADR-0005 (D1・D3-1・P6・unnumbered)・drafts/0016 (D2・未決 3・4・6) を同時に改訂 | — |
| 7. 範囲外 | BGP ポリシー・ピアグループ・graceful restart・TCP MD5 / AO・add-path・BGP role・route server などの振る舞いの設定を追加 | network-tech-reviewer。route server は example-author が端点の `role` に書いたが、振る舞いの設定 (ADR-0005 D3-2) として範囲外にし、注記は L1 ノードの `role` に |

**移行で分かったこと** (example-author): `valid_full_dc.yaml` と `valid_multi_vlan.yaml` は underlay をループバックどうしで張りながらリンクを指していた (F8)。
通り道を導くと multihop になるので、underlay を single-hop にするなら移行時に /31 の L3 IF を足す。
