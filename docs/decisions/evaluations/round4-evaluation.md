# ラウンド4 横断評価メモ (Pass B)

- **Date**: 2026-10-15
- **Evaluators**: mlndl-spec-architect (反論者モード), mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **対象ドラフト**: [drafts/0011](../drafts/0011-layer3-data-plane.md) (layer3 データプレーン)、
  [drafts/0012](../drafts/0012-subinterfaces.md) (802.1Q サブ IF)、[drafts/0013](../drafts/0013-vlan-ports-on-lag.md) (VLAN のポートから LAG を指す)
- **試し書き**: [round4/](round4/README.md) (3 本。実測結果つき)

---

## 評価の前提

ラウンド1/1.5 と違い、3 本とも **Pass A のまま実装・main マージ済み**である (ADR-0011 は 2026-10-04、0012 は 10-05、0013 は 10-11)。
したがって本評価は、通常の観点に加えて「実装の都合で正当化された箇所」と「ADR 本文と実装のずれ」を見る。

もう 1 つの前提として、3 本は**同じ統合者が同じセッションで続けて書いた**。設計ラウンドでは毎回 5 エージェントの評価を取ったが、
統合と判断の流れ (ADR-0011 の表現原理 → ADR-0012 の ID 空間表 → ADR-0013 の表拡張) は一本の思考の軌跡になっている。
これ自体がアンカーになりうる (spec-architect の指摘)。

評価の目的はラウンド1と同じ: (1) アンカー検出、(2) 白紙再設計シミュレーション、(3) 横断矛盾、(4) 見落とした論点、(5) 「結論ありき」感。

## 章構成

1. 事実確認 — エージェントの主張を実装と ADR 本文で確かめた結果
2. アンカー検出
3. 指摘 (テーマ別に統合、優先順)
4. 横断矛盾
5. 白紙再設計シミュレーション
6. ユーザー決定事項への異論 (別枠)
7. Pass C への Input サマリ

指摘の出典は各エージェントの ID で示す: S = spec-architect、L = linguist、D = dsl-designer、N / F / X / V = network-tech-reviewer、Y = example-author。

---

## 1. 事実確認

### 1-1. 試し書き YAML の実測

example-author の環境では検証コマンドを実行できなかったため、統合時に実行した。

| ファイル | `validate --strict` の結果 |
|---|---|
| `a_enterprise_two_sites.yaml` (本社 MLAG + VRRP デュアルスタック + 支社 router-on-a-stick + IPsec VTI) | 通る |
| `b_evpn_dc_external_peer.yaml` (EVPN anycast GW + routed LAG + サブ IF で外部ピア) | parse error 1 件。`ipv6: 2001:db8:ext::1/126` の `ext` が 16 進数でない (書き手の誤記。validator は正しい)。直すと通る |
| `c_common_mistakes.yaml` (誤り 9 件 M1〜M9 を混入) | 下表 |

`c_common_mistakes.yaml` の誤りの検出状況:

| 誤り | 検出 |
|---|---|
| M1 SVI の短縮形と明示した `attaches_to` の食い違い | error |
| M2 VLAN に LAG とそのメンバーの両方 | error |
| M3 VLAN に LAG のメンバーだけ | warning |
| M4 トンネルの `destination_ip` と `destination_interface` の両方 | error (スキーマ段階) |
| M5 VRRP の IPv6 VIP がリンクローカルでない | error (スキーマ段階) |
| M6 IPv4 VIP が IF のサブネット外 | error |
| M7 VLAN ポートの `node` と `interface` の食い違い | error |
| **M8** サブ IF のタグ番号を対向 VLAN と食い違えた | **検出されない** (ADR-0012 D3 の設計どおり) |
| **M9** anycast gateway のペアで片方の IP が食い違う | **検出されない** |

**実測で新たに分かったこと**: M4・M5 はスキーマ (pydantic) 段階の error なので、**それがあるとほかの 7 件は 1 件も報告されない**。
M4・M5 を取り除いて初めて M1〜M3・M6・M7 が出た。書き手は「1 件直すと別の誤りが出てくる」体験をする (→ 3-5 の E7)。

### 1-2. 主張の確認

| 主張 | 出典 | 確認結果 |
|---|---|---|
| `anycast_mac: str` に形式検証がない。ADR-0011 F4 で非難した欠陥を同じ ADR で再発している | S4 | **誤り**。`AnycastGateway.mac_format` が `:` / `-` / `.` 区切りの 3 形式を検証している (`schema/layer3.py`)。退ける |
| ADR-0013 が PortRef の `node` を任意にした理由は、既存 fixture との後方互換である | S5 | **一部誤り**。ADR-0013 D2 の理由は「ID から導出できる」「LAG のときだけという例外を作らない」で、ユーザー判断。ただし、サブ IF (node を持たない) との非対称という指摘の本体は正しい |
| L3 IF が MLAG を指して `node: leaf1` と書くと通ってしまい、ADR-0013 D2 の規則を L3 側で塞いでいない | D2 | **設計どおり**。L3 IF はノードごとに 1 つ (各ノードが自分の IP を持つ) なので `node` は必要。テスト `test_subif_on_mlag_belongs_to_both_nodes` もこの前提。ADR-0013 D2 は VLAN 所属の話で、L3 IF には当てはまらない。ただし、この違いは ADR に書かれていない (→ B) |
| 短縮形 `interface: vlan-100` に `attaches_to: {interface: <L1 IF>}` を併記すると食い違いを検出しない | V2 | **正しい**。食い違い検査は明示側が VLAN のときだけ動く (`validator.py` の `explicit in vlan_ids`) |
| トンネルの `destination_interface` が自分と同じノードの L3 IF でも通る | S8 | **正しい**。validator は参照の存在だけを見る。cytoscape は同じノードなら辺を出さず、黙って捨てる |
| トンネルの外側の AF (source と destination の IPv4 / IPv6) の整合を検査しない | N2 / F8 | **正しい** |
| IF に `ip` がないと IPv4 VIP の検査が飛ばされる | F2 | **正しいが、設計どおり**。ADR-0011 D9 に「`ip` / `ipv6` が未指定の IF は対象外」と明記されている。warning にするかが論点 |
| anycast gateway の全ノード一致を検査しない | N11 / Y6 | **正しい** (M9 で実測) |
| ADR-0011 のヘッダに ADR-0012 / 0013 による改訂の記載がない。D9 の「L1 IF に解決された場合に限り node 照合」は ADR-0012 で LAG / サブ IF に広がった | S7 / V1 | **正しい**。ADR-0005 と ADR-0012 には `Amended by` があるが、ADR-0011 にはない |
| ADR-0011 の Alternatives に「5 エージェント中 4 つがスタティックルートを入れると判定」とある | S1 | **正しい** (L121・L432) |
| ADR-0011 D6 は、IKE / PSK の線引きを「D1 の原理だけでは説明しきれない」と自ら認めている | S1 / S9 | **正しい** (L248〜250) |
| L1 リンクの `endpoints` は要素ちょうど 2 つで、片端がトポロジー外のリンクを書けない | Y8 | **正しい** (`Field(min_length=2, max_length=2)`) |

---

## 2. アンカー検出

| ADR | アンカー強度 | 主なアンカー |
|---|---|---|
| 0011 | **高** | (a) ユーザー決定「スタティックルートはスコープ外」を、D1「表現原理」として一般化し ADR-0005 の補則に置いた (後付けの一般化の疑い。S1)。(b) 既存 fixture の `ip:` が全部 IPv4 だった事実が「書き換え 0 行」として D5 の決定根拠になった。(c) 既存ヘルパー `_check_attaches_to` の形 (`extra_interface_ids` 引数) が D3 の記述にそのまま出ている |
| 0012 | **中〜高** | (a) ADR-0001 の `{interface:}` 1 キー形式を変えないために、参照元ごとに指せる ID 空間を変える表 (D5) を発明した。以後「表に 1 行足す」拡張が型になった (S2・D1)。(b) ADR-0011 D8 の `parent → attaches_to` |
| 0013 | **中** | (a) ADR-0012 D5 の表に 1 行足すだけで済む設計を選んだ。(b) 既存 fixture のメンバー列挙を壊さないため warning にとどめた。(c) ADR-0012 D2 の「親から導出できるものは持たない」を流用したが、結論はサブ IF (持たない) と違う (任意) |

**同一統合者アンカー**: 3 本の判断は「原理を立てる → 表で例外を管理する → 表を拡張する」という一続きの流れになっている。
白紙再設計 (§5) で、この流れのうち「表で管理する」部分は選ばれない可能性が高い。

---

## 3. 指摘 (テーマ別)

テーマの見出しに、指摘したエージェントの数を書く。複数のエージェントが独立に同じ問題に行き着いたものほど重い。

### A. `{interface: X}` の多態参照 — 優先度 **高** (3/5 が問題視: S2, D1, Y4。linguist は現状維持を支持)

**問題**: `attaches_to: {interface: X}` の X は、L1 IF / LAG / VLAN / サブ IF のどれでもありうる。どれを受け付けるかは、それを書いたエンティティで変わる
(ADR-0012 D5 の表。ADR-0013 で 1 行増えた)。

- ADR-0001 は「キー名が discriminator」と定めたが、`interface` キーは実質的に「参照元の文脈で意味が変わる」discriminator になった (S2)
- 受付の集合は ADR の表と validator 内の引数 (`extra_interface_ids`) と別経路 (`_port_nodes`) に散っており、型 (pydantic) にはない (D1)
- 書く側も読む側も、`{interface: lag-border1-po1}` が LAG を指すことを YAML の表面から読み取れない。試し書きで実際に迷った (Y4)
- `layer2.bridges` (drafts/0007) を入れると、表は 3 回目の拡張を受ける見込み (D1・D6)

**選択肢** (Pass C で正面から比較する):

| 案 | 内容 | 得るもの | 失うもの |
|---|---|---|---|
| a. 現状維持 + 正準化 | 表を validator の定数 1 か所に集め、ADR-0001 に「`interface` は多態参照」と明記して表を移す | 変更が最小。YAML は変わらない | 読みにくさ (Y4) は残る |
| b. キー分割 | `{interface:}` (L1 IF) / `{lag:}` / `{vlan:}` / `{subinterface:}` | 参照先の種類が YAML から読める。受付表が型で書ける (discriminated union) | ADR-0012 D4・ADR-0013 D1 の判断を覆す。既存 YAML の書き換え。ADR-0001 の改訂 |
| c. 種別タグ | `{interface: X, kind: lag}` | 明示的 | 冗長。ID はグローバル一意なので kind は導出可能な二重表現になる |

linguist は「論理 IF を指す統一キー」の直交性から現状維持を支持し、ADR-0013 の設計ラウンドでは 5 エージェント全員が `lag:` キーを却下した。
今回、試し書き (Y4) と反論者 (S2) が逆の結論を出した。**これは設計ラウンドの結論が Pass B で割れた唯一の論点である**。

### B. `node` を「持たない / 任意 / 必須」の規則 — 優先度 **高** (5/5: S5, D2, L6, Y5, Y12)

| エンティティ | `node` | 根拠 |
|---|---|---|
| `layer2.subinterfaces` | 持たない (書くと error) | ADR-0012 D2「親から導出できるものは持たない」 |
| VLAN の `trunk_ports` / `access_ports` | 任意 (書けば照合)。MLAG では書けない | ADR-0013 D2 |
| `layer3.interfaces` | 必須 | ループバックのように親を持たない L3 IF があるため (ADR-0012 D2 で言及) |
| `layer3.tunnel_interfaces` | 必須 | 明記なし |
| `layer1.interfaces` | 必須 | 物理の起点 |

同じ「導出できるか」という基準から、3 通りの結論が出ている。5 エージェント全員が、規則を 1 か所にまとめるよう求めた。

- **整合する説明は可能**: 「そのエンティティがノードごとに 1 つか」で分けると揃う。L3 IF とトンネルはノードごとに別の実体 (IP が違う) なので必須。
  サブ IF と VLAN のポートは、親や LAG と 1 対 1 で決まり、MLAG では 2 ノードにまたがる 1 つの実体なので導出する。
  ただし、この基準はどの ADR にも書かれていない (1-2 の D2 の項)
- **残る非対称**: サブ IF は「持たない」、VLAN のポートは「任意」。同じ基準なら、どちらかに揃えられる (S5)

**修正案**: (1) 上の基準を Pass C で規範として書き、表を 1 つ置く (ADR-0005 か CLAUDE.md)。
(2) サブ IF と VLAN のポートを「持たない」と「任意」のどちらに揃えるかを決める。

### C. `interface` の 2 つの意味と SVI の短縮形 — 優先度 **中〜高** (4/5: L1, L2, D4, D5, Y1, Y3, V2)

- `L3Interface.interface` は機器上の名前 (参照ではない) だが、`attaches_to.interface` / `PortRef.interface` / `TunnelInterface.destination_interface` は ID 参照である。
  同じ L3 IF の中に両方の意味の `interface` が並ぶ。ADR-0012 D6 自身が、サブ IF ではこの衝突を避けるために `name` を選んでいる (L1・L2・D5)
- SVI の短縮形 `interface: vlan-N` は、「参照解決には使わない」はずの `interface` を参照として解決する唯一の例外である。
  「二重表現を避ける」という 3 本共通の方針に対する例外として残っている (D4)。試し書きでも、短縮形と正規形のどちらで書くか迷った (Y1・Y3)。
  さらに、短縮形と L1 IF への `attaches_to` の食い違いを検出しない (V2、実装で確認)

**修正案**: Pass C で「`L3Interface.interface` → `name` の改名」と「短縮形の廃止」を一緒に検討する。どちらも破壊的なので、
同時に行えば破壊的変更は 1 回で済む (D5)。すぐに実施しない場合でも、V2 の検出漏れは直す。

### D. ADR-0011 D1「表現原理」の格付け — 優先度 **高** (1/5: S1, S9。ただし N8 は原理で範囲判定ができると評価)

- 原理は、ユーザー決定「スタティックルートはスコープ外」を後から一般化したものに見える。設計ラウンドでは 5 エージェント中 4 つがスタティックルートを入れると判定しており、原理には到達していなかった (S1)
- ADR-0011 D6 は、トンネルの `mtu` は原理で範囲内、IKE / PSK は「原理だけでは説明しきれない」として ADR-0005 D3-2 (秘匿情報) に接続している。原理単独では判定しきれないことを ADR が認めている (S1・S9)
- 一方、network-tech-reviewer は DHCP relay / NAT / ACL / QoS / ポリシールーティングを「個別パケットの処理であり関係の成立条件ではない」と、原理を使って範囲外と判定できた (N8)。原理に判定能力がまったくないわけではない

**修正案**: 原理を維持するなら、判定軸を 2 本にして順序を決める (1. 秘匿情報か → 上位ツール、2. 関係の成立に必要か → 書く)。
格下げするなら「スコープ境界の覚え書き」とし、ADR-0005 D4 の補則から外す。

### E. validator の検出漏れ (偽陰性) — 優先度 **中〜高**

| ID | 内容 | 出典 | 確認 | 修正案 |
|---|---|---|---|---|
| E1 | anycast gateway の SVI 群で `ip` / `ipv6` / `anycast_mac` が一致しない | N11, Y6 | 実測 (M9) | 同じ VLAN に載る `mode: anycast_gateway` の L3 IF 群で、同じ AF の IP と MAC の一致を error |
| E2 | トンネルの `destination_interface` が自分と同じノード | S8 | 実装で確認 | error |
| E3 | トンネルの外側の AF が source と destination で食い違う | N2, F8 | 実装で確認 | source の L3 IF と destination (IP または L3 IF) に共通する AF がなければ error |
| E4 | SVI の短縮形と L1 IF への `attaches_to` の食い違い | V2 | 実装で確認 | 短縮形のときは、明示側が VLAN 以外でも食い違いとして error |
| E5 | サブ IF のタグ番号と、対向スイッチの VLAN の食い違い | S3, Y2, Y10 | 実測 (M8)。ADR-0012 D3 の設計どおり | 「対向ポートが同じタグの VLAN を trunk していなければ warning」案 (Y10)。ただし ADR-0012 の設計ラウンドで tech が誤検知を指摘して退けた経緯がある。Pass C で再判断 |
| E6 | 同じ物理 IF が VLAN の trunk にも載り、かつサブ IF の親でもある | F3 | 要確認 (Cumulus / Linux の挙動) | Cisco / Arista では switchport と routed サブ IF は排他。warning 候補 |
| E7 | スキーマ段階の error があると、validator 段階の誤りが 1 件も報告されない | 実測 (§1-1) | 実測 | 構造上の制約 (parse に失敗するとモデルがない)。CLI のメッセージで「parse error を直すと追加の検査が走る」と案内する程度が現実的 |
| E8 | 片側だけのトンネル (対向の TunnelInterface がない) | X4, S 見落とし3 | 未確認 | 対向がトポロジー内なのに逆向きのトンネルがない場合は info |
| E9 | IF に `ip` がないのに IPv4 VIP を書く | F2 | 設計どおり (ADR-0011 D9) | warning に格上げするか判断 |
| E10 | L2VNI の `members` と、その VLAN が載るノード群の食い違い | F9 | 未確認 | warning 候補 (優先度 低) |

> **対応状況 (2026-10-15)**: E1〜E4 は Pass C を待たずに validator に実装した (テストつき)。`c_common_mistakes.yaml` の M9 はこれで検出される。E5〜E10 は Pass C で判断する。

### F. 範囲内なのに書けないもの — 優先度 **中** (network-tech-reviewer 中心)

| 項目 | 出典 | 判定 | 備考 |
|---|---|---|---|
| VXLAN の anycast VTEP (MLAG ペアで共有する VTEP IP) | N3 | 範囲内、優先度 高 | ADR-0011 の未解決 3 と同じ。`vtep_source` が単数 |
| EVPN multihoming (ESI-LAG) | N4 | 範囲内 | `MlagLag` は `peer_link` 必須なので、`type: esi_lag` を足す |
| L3 IF 単位の MTU | N6 | 範囲内 | SVI / routed サブ IF の MTU が書けない |
| VXLAN の BUM 配送方式 (ingress replication / multicast) | N10 | 範囲内 | 原理 D1 では「関係の成立に必要」と読める |
| MLAG の peer-keepalive | N5 | 範囲内 | split-brain 検出の設計要素 |
| Q-in-Q / ネイティブ (タグなし) サブ IF | N9 | 範囲内、優先度 低 | 拡張の形は ADR-0012 に記載済み |
| 片端がトポロジー外の L1 リンク | Y8 | 要判断 | 外部の stub ノードを置く書き方を docs に示すだけでも改善する |
| WAN / インターネット向けの `link_role` 推奨語 | Y9 | 範囲内 (注釈) | 推奨語彙表を作る |
| BGP unnumbered (IPv6 リンクローカルだけの L3 IF) | N1 | ADR-0010 の責務 | 制御プレーンの再開時に扱う |

**範囲外として ADR-0011 D2 の表に追記するもの** (N7・N8): DHCP relay、NAT、ACL、QoS、ポリシールーティング、VRF 間のスタティックリーク。

### G. 文書の整合 — 優先度 **中〜低**

| ID | 内容 | 出典 |
|---|---|---|
| G1 | **(対応済み 2026-10-15)** ADR-0011 のヘッダに `Amended by: drafts/0012, drafts/0013` を足す。D9 の「L1 IF に解決された場合に限り」と「trunk_ports の node 照合」は改訂済みであることを注記 | S7, V1 |
| G2 | ADR-0005 は 2 本の Draft に部分改訂され、規範の最新形を知るには CLAUDE.md を読むのが早い状態 (ADR が二次情報化)。Pass C で ADR-0011〜0013 を Accepted にする際、ADR-0005 に統合するか、改訂関係の一覧を置く | S (横断矛盾) |
| G3 | validator の規則の採否基準 (error / warning / 検査しない) を ADR-0002 D8 に 1 本化する。候補の 2 軸:「実機で壊れた状態になるか」「書き手が気づかない誤りか」 | S11 |
| G4 | 廃止キーへの案内メッセージをいつまで残すか (ndl_version 1.x の間は残す等) | D3 |
| G5 | ADR-0012 D4 と D5 で routed LAG の規則が重複している。D5 の表に一本化する | S10 |
| G6 | 用語: 本文の「親」は Realization (`attaches_to` 側) で、ADR-0009 の `parent` (Containment) とは別概念と明記する | L8 |
| G7 | 命名の候補: サブ IF の `vlan_id` → `tag` (VLAN の `vlan_id` と意味が違う。L3)、トンネルの `source` → `source_interface` (destination 側との対称。L5)、`vrf` / `transport_vrf` の内外を Terms に (L10)、enum 値の区切り規約 (L11) | L3, L5, L10, L11 |
| G8 | トンネルの両端がトポロジー内なら、各ノードに 1 本ずつ (計 2 本) 書くのが正であることを ADR-0011 D6 に例示する | Y7 |
| G9 | 書かれていない既定の挙動: ループバックが `attaches_to` を持たないこと、MLAG 上の routed サブ IF を検査しないこと、サブ IF の `vlan_id` の値域を型で検証していること | S 見落とし 1・2・5 |

---

## 4. 横断矛盾

| 位置 | 内容 | 評価 |
|---|---|---|
| ADR-0001 D2 vs ADR-0012 D5 | 「キー名が discriminator」vs「同じキーが参照元によって違う ID 空間を引く」 | **矛盾あり** (A) |
| ADR-0012 D2 vs ADR-0013 D2 | 同じ「導出できるものは持たない」から、サブ IF は禁止、VLAN のポートは任意 | **非対称** (B)。基準を書けば説明できるが、書かれていない |
| ADR-0011 D3 vs D3 の短縮形 | 「`interface` は参照解決に使わない」と「`interface: vlan-N` は参照として解決する」 | **意図的な例外**。二重表現の方針に対する例外として扱いを決める (C) |
| ADR-0011 D1 vs D6 | 原理で `mtu` は範囲内、IKE / PSK は原理だけでは判定できず D3-2 に頼る | **原理の判定力の限界** (D) |
| ADR-0011 D9 vs ADR-0012 D7 / ADR-0013 D2 | node 照合の範囲と、PortRef の node 必須 / 任意 | **ADR-0011 本文が古い** (G1) |
| ADR-0011 F4 vs D4 | 「任意の文字列を黙って通す」の非難と `anycast_mac: str` | **矛盾なし** (S4 は誤り。形式は検証している) |
| ADR-0012 D3 vs ADR-0013 D5 | サブ IF のタグは照合しない vs VLAN ID の重複は MLAG を展開して検査 | **矛盾なし**。別の空間。ただし同じ物理 IF 上の両立 (E6) は別の論点 |
| ADR-0012 D5 の表 vs drafts/0010 | 表の `routing_adjacencies` 行は ADR-0010 の再開で変わる | **表の寿命が短い**。A の判断と一緒に扱う |

---

## 5. 白紙再設計シミュレーション

### 同じ結論に到達する点 (独立に支持された)

- IPv4 と IPv6 を別のフィールドにする (`ip` / `ipv6`、単数) — spec-architect・linguist が独立に妥当と判断
- `gateway_redundancy` を `mode` で分岐する Tagged Union にする — spec-architect・dsl-designer・linguist
- サブ IF を独立したフラットなエンティティにし、`node` を持たせない — spec-architect・dsl-designer
- トンネルを自己完結の `TunnelInterface` にし、`tunnel_links` を作らない — spec-architect・dsl-designer
- サブ IF の `vlan_id` を VLAN への参照にしない (タグの書き換えが書けなくなるため) — dsl-designer
- VLAN のポートから LAG を指せるようにする — 全員
- `fhrp` → `gateway_redundancy` の改名は、意味の狭い業界語を正しく捨てた例 — linguist

### 到達しない可能性がある点

- **`{interface:}` の多態参照** — ゼロからなら、参照先の種類をキーで示す設計 (A の案 b) を選ぶ可能性が高い (spec-architect・dsl-designer・example-author)
- **SVI の短縮形** — ゼロからなら作らない (dsl-designer)
- **`L3Interface.interface` という名前** — ゼロからなら `name` にする (linguist・dsl-designer)
- **ADR の分け方** — 0011〜0013 は L2 / L3 のセグメンテーションとして地続きで、1〜2 本にまとまる可能性が高い。3 本に分かれたのは時系列の都合 (spec-architect)

---

## 6. ユーザー決定事項への異論 (別枠)

ユーザーが明示的に決めた事項への異論。覆すよう求めるものではなく、Pass C で判断材料として扱う。

| 決定 | 異論 | 出典 |
|---|---|---|
| スタティックルートはスコープ外 | 到達性が書けず、将来の `blast_radius` で「このリンクが落ちると届かなくなるプレフィックス」を出せない。少なくとも `default_gateway` だけでも再評価の余地がある | S |
| `ip` (IPv4) / `ipv6`、単数 | 英語として `ip` は AF 中立に読める (linguist。ただし異論なし、Terms で強調を推奨)。同じループバックに複数の IP を積む実機構成が書けない (S。`ip_secondary` の加算を申し送りに) | L, S |
| サブ IF は `vlan_id` のみで VLAN 参照なし | 原案の `broadcast_domain` 検索に必要なつながりを、Phase 3 のグラフ探索に先送りしている (S3)。命名として `vlan_id` が VLAN の `vlan_id` と違う意味になる (L3。`tag` への改名で両立) | S, L |
| サブ IF の親 LAG を `interface` キーで指す | A の再掲 | S, D, Y |
| VLAN のポートの `node` は常に省略可 | B の再掲。サブ IF と揃っていない | S, Y |

トンネルを範囲内にした判断には、異論が出なかった。

---

## 7. Pass C への Input サマリ

**Pass C で参照するもの**: 本評価メモ、ADR-0001〜0006・0009 (Accepted 版)、CLAUDE.md、`evaluations/round4/` の試し書き。
**drafts/0011〜0013 は参照しない** (Pass C の原則)。ただし 3 本は実装済みなので、Pass C の結論が実装と違う場合は、移行手順も合わせて決める。

### 確定すべき論点 (優先順)

1. **A. `{interface:}` の多態参照を続けるか、キーを分けるか** — Pass B で唯一、設計ラウンドの結論が割れた。`layer2.bridges` (drafts/0007) や ADR-0010 の再開より前に決める
2. **B. `node` の有無の基準** — 「ノードごとに 1 つの実体か」を規範として書き、サブ IF と VLAN のポートの非対称をどちらに揃えるか決める
3. **D. 表現原理の格付け** — 2 軸 (秘匿情報 → 関係の成立) で維持するか、覚え書きに格下げするか
4. **C. `L3Interface.interface` → `name` と SVI 短縮形の廃止** — 破壊的変更なので同時に。見送る場合も E4 の検出漏れは直す
5. **E. validator の検出漏れ** — E1〜E4 は追加が安く、誤検知の心配も小さい。E5・E6・E9 は Pass C で採否を判断
6. **F. 書けないもの** — anycast VTEP (N3) を最優先に、ESI-LAG・L3 MTU・BUM 配送を別 ADR として起こす
7. **G. 文書の整合** — G1 (ADR-0011 の Amended by) は Pass C を待たずに直してよい

### 独立に同じ結論に到達した点 (Pass A の正当性が高い箇所)

- `gateway_redundancy` の Tagged Union、`ip` / `ipv6` の分離、トンネルの自己完結、サブ IF の独立エンティティ化 (§5)
- VLAN のポートから LAG を指すこと自体 (全員)
- サブ IF の `vlan_id` を VLAN への参照にしないこと (dsl-designer が独立に支持。ただし照合の warning は別論点)

### 退けた指摘

- **S4** (`anycast_mac` に形式検証がない): 実装で誤りを確認した
- **D2 の一部** (L3 IF が MLAG を指すときに `node` を書ける): L3 IF はノードごとの実体なので設計どおり。基準が書かれていない点は B に含めた
