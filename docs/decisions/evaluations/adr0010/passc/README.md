# ADR-0010 Pass C 試し書き (2026-11-01)

[round3-evaluation.md](../../round3-evaluation.md) の「ユーザー決定事項」(§評価の前提の表) を
前提に、ドラフト (`drafts/0010-control-plane-separation.md`) を**読まずに**組み立てた
制御プレーンの構文で書いた。Pass B の `r3/` との最大の違い:

- **routing_neighbors に `attaches_to` を書かない**。通り道は `update_source` の L3 IF
  (→ `attaches_to` → L1 IF / LAG / subinterface) からたどる (§3-B)
- `router_id` は書かない (ADR-0016 に委ねる)
- `role: underlay/overlay` は書かない (AF から導く)
- トップレベル `protocols:` を使わない (`control_plane:` に移動)

## ファイル一覧

| ファイル | 元ファイル | 焦点 |
|---|---|---|
| `fixture_full_dc.yaml`   | `tests/fixtures/valid_full_dc.yaml`      | F4 (leaf1 の AS 65001 / 65000) を Full eBGP に揃えて解消 |
| `fixture_multi_vlan.yaml`| `tests/fixtures/valid_multi_vlan.yaml`   | 同、leaf1/2/3 の AS 二重宣言を解消。route_server/client を endpoint の `role:` で書く |
| `fixture_multisite_wan.yaml`| `tests/fixtures/valid_multisite_wan.yaml`| DC Full eBGP + WAN eBGP (cm-core はトポロジー内)。トポロジー外ピアの書き方を補足で示す |
| `eveng_evpn_lab.yaml`    | `examples/eveng-evpn-lab.yaml`           | `role: route_server` / `route_server_client` を endpoint の role に移植 |
| `mistakes.yaml`          | — (新規)                                 | §3-F の検査を網羅する 9 件の誤り (M1〜M9)。各エントリに期待 Severity をコメント |

いずれも `tests/fixtures/` には置かず、`python -m mlndl validate` は通らない
(スキーマ側に `control_plane` が未実装)。制御プレーン節だけを示し、L1/L2/L3 は
参照整合性のため元ファイルの id をそのまま使う前提。

## 検証したこと

### 1. 通り道の導出 (§3-B)

全セッションで、`from.update_source` / `to.update_source` の L3 IF からたどって
通り道が一意に決まるか (または決まらないことが「multihop」として自然か) を確認:

| 例 | from の update_source | to の update_source | 導いた path |
|---|---|---|---|
| full_dc の underlay | spine1-swp1-l3 (→ spine1-swp1 → link-spine1-leaf1) | leaf1-swp51-l3 (→ leaf1-swp51 → link-spine1-leaf1) | **link-spine1-leaf1** (両端一致) |
| full_dc の overlay  | spine1-lo (attaches_to 無し) | leaf1-lo (attaches_to 無し) | **なし** (= multihop。辺の attaches_to は空) |
| multisite WAN       | dc-border1-swp1-l3 → link-wan-border1-core1 | cm-core1-te1-1-l3 → link-wan-border1-core1 | **link-wan-border1-core1** |
| mistakes.M6         | spine1-e1-1-l3 → link-spine1-leaf1 | leaf2-e1-1-l3 (孤立) | **mismatch → error** |

すべてのケースで path は参照だけで決まり、セッションに `attaches_to` を書く
必要が無いことを確認した。

### 2. エクスポーターに出す値がすべて参照で決まるか

| 項目 | 元 | 導出 |
|---|---|---|
| 両端 IP | — | `update_source` → L3 IF.ip |
| 両端 AS | — | `instance` → BGP entry → nodes[].local_as |
| eBGP/iBGP | — | 両端 AS の比較 |
| AF | — | session.address_families |
| VRF | — | `instance` → BGP entry.vrf (省略 = default) |
| path | — | 上記 §3-B の導出 |
| RR/RS 関係 | — | endpoint.role |

いずれも推定なしで決まる (unnumbered セッションの両端 IP だけは「出さない」が正しい)。

### 3. F4 の構造的な排除

元の `valid_full_dc.yaml` と `valid_multi_vlan.yaml` では、1 ノードが同じ default VRF の中で
2 つの AS (underlay 用 / overlay iBGP 用) を宣言していた。Pass C では BGP インスタンスを
VRF ごとに 1 つしか置けないため、同じ `node` に対する `local_as` は 1 つしか書けない。
F4 を書く余地が無くなる (= 構造的排除)。

書き直すためには設計上の選択が必要:

- 選択 A: **Full eBGP** (Dinesh Dutt / Cumulus 推奨。RFC 7432 §15 で許容)。
  underlay も overlay も eBGP、spine を route_server として endpoint role に記す。本 passc/
  の全ファイルで採用。
- 選択 B: **iBGP フル** (全ノード同じ AS)。underlay に OSPF/IS-IS を使う。本 passc/ では
  採用せず。

## 移行で分かった書きにくさ・仕様の穴

### 1. 元ファイルに **spine 側の /31 L3 IF が無い**

`valid_full_dc.yaml` / `valid_multi_vlan.yaml` は underlay BGP を loopback 間で張っており、
spine 側の /31 L3 IF (例: `spine1-swp1-l3`) が存在しない。これは **loopback→loopback の
single-hop BGP** という意味的に成立しない形で、現行 `routing_adjacencies[].attaches_to: {link: ...}`
では見逃されている (「物理リンクを指しただけ」で両端が同じリンクに乗っているとは検査されない)。

Pass C では update_source から path を導くので、`spine1-lo` と `leaf1-lo` が同じ L1 リンクに
乗らず path が決まらない (= multihop 扱い)。元の意図が「P2P /31 の single-hop」なら、
`spine1-swp1-l3` 等を追加しないと記述が破綻する。これは **Pass C が元ファイルの潜在欠陥
を顕在化させた** 例。R_extended_control_plane.yaml はすでに /31 L3 IF があったので同じ
問題は無かった。

→ feedback: Pass C 検査の 1 項目として「update_source が loopback で、同じ組の AF が
   ipv4/ipv6 unicast かつ default VRF、両端ノードが物理的に直結している (L1 リンクが
   1 本ある) 場合、意図は single-hop /31 である可能性が高いが update_source が loopback の
   ため multihop 扱いになる」ような notes/info を出すと親切。これは §3-F の表には無い。

### 2. route_server / route_server_client は RR と同格に扱えるか

eveng-evpn-lab.yaml 元ファイルでは `role: route_server` が BGP ノードの属性として書かれていた。
Pass C でこれを endpoint の `role:` に移すと、意味は「この端点は next-hop unchanged + retain
RT all として振る舞う」になり、eBGP でも iBGP でも書ける (RR と違って eBGP が主用途)。
検査は「route_reflector_client ⇒ iBGP」だけで、route_server_client は検査しない設計で
妥当だと感じたが、「どちらを書くかの判断」は実装/ベンダー依存の情報であり、注釈側 (role は
自由文字列、推奨語彙あり) とすべきかもしれない。

→ feedback: endpoint の `role` の推奨語彙を `docs/role-vocabulary.md` に追加する価値がある
   (`route_reflector`, `route_reflector_client`, `route_server`, `route_server_client`)。
   `role` と重複する名前なので別軸にする (例: `bgp_role:`) のも検討の余地あり。

### 3. 「同じノード対の 2 本目」の ID 衝突回避

D7 の推奨「ノード対の末尾に区別語」で `bgp-peer-spine1-leaf1-evpn` のようにしたが、
multisite_wan ではセッション数が多く、`bgp-peer-dc-spine1-border1-evpn` のように ID が長い。
25 文字を超えるが、ADR-0002 D1 の 63 文字制限内に収まる。読みやすさは `-evpn` が末尾に
くる形で保てた。
一方で「3 本目のセッション」(例えば ipv6_unicast を別セッションに分けた場合) をどう書くかは
曖昧 (`-v6`? `-ipv6`?)。D7 に推奨語彙リストがあると迷いが減る。

→ feedback: D7 に区別語の推奨リスト (`-evpn`, `-v6`, `-vpnv4`, `-admin` 等) を informative
   として追記するとよい。

### 4. route_server/RR の node 側に `role:` を書くという二重表現の懸念

本 passc では endpoint 側に `role: route_server` を書いたが、「このノードは BGP の RR/RS
として全セッションで振る舞う」という表明は本来**ノード属性**の性格が強い (全セッションで
同じ役割)。endpoint 側に毎回書くのは冗長で、別のセッションで役割を変える人が出た場合に
矛盾が生じうる (= 検査すべきかどうかという論点)。
BGP インスタンスの `nodes[]` に `role:` を書き、endpoint は参照だけに留める案もあったが、
Pass C ではそれを採らず endpoint ごとに書く形にした。これは「セッションごとに RR の
扱いを変える」(たとえばスパインどうしは RR 関係ではなく通常の iBGP フルメッシュ) を書ける
利点があるが、冗長さと trade-off。

→ feedback: Pass C 本決定で endpoint 側に書くとする場合、「同じ `node` が同じ `instance`
   内で role を変えると warning」のような検査を加えると、意図しない揺れを捕まえられる。

### 5. 検査で見つけられない誤り (ユーザー判断が必要)

- **BGP グループ (peer-group) 相当の重複排除**: 現実の設定では複数の neighbor に同じ
  peer-group を適用する。本 Pass C の記述では 1 セッション = 1 行で、peer-group は書けない。
  §7 (範囲外) で明記されているが、ndl-viz では「このセッション群は同じ peer-group」のような
  まとめ表示ができない。
- **`default-originate` / route-map / prefix-list などの政策情報**: Pass C は「意図した
  セッションの実在」までしか書かない。政策は書けない。これは §7 と整合。
- **route_server と iBGP RR を混在させた overlay**: eveng-evpn-lab のように spine が
  AS 65000 一括で、全 leaf が別 AS なら eBGP。だが「spine 間は iBGP (RR 兼用)」のような
  混合は書けるものの、現状の検査では整合性 (RR の反射動作が実装される保証) まで
  踏み込まない。これは Phase 3+ の blast_radius とも連動する。
- **ebgp-multihop の hop 数**: Pass C は multihop/single-hop を構文に出さず (§Independent)、
  update_source の L3 IF から導出する。しかし「3 hop を許す」(= loopback が 3 ホップ先)
  のような設定上の数値は書けない。実際にはベンダー OS に送る必要がある情報だが、意図の
  記述としては不要なので妥当と判断。

### 6. 外部ピアの表現が 2 系統あることの運用負担

`fixture_multisite_wan.yaml` では Campus 側 (cm-core1/2) をトポロジー内として
`{node, update_source}` で書いた。これと `{address, local_as}` のどちらを使うべきかは
「ケーブルまで書くか」で決まるが、サイト境界をどこに引くかは記述者の判断。両方の形が
用意されていること自体は良いが、同じ対象を 2 通りに書けるため、プロジェクトごとの
ガイドライン (「相手の L3 IF を 1 つでも書けるなら in-topo」等) を文書化しないと一貫性が
損なわれやすい。

→ feedback: ADR-0010 の D4 (端点の 2 つの形) に「どちらを選ぶかの指針」を 1 段落足す。
   `docs/style-guide.md` のような外部ガイドの可能性も含めて検討。

## ユーザー判断を仰ぎたい点

1. **endpoint の `role:` に `route_server` / `route_server_client` を加えてよいか**。
   RS は eBGP でも iBGP でも使える点が RR と違うので、同じ `role:` フィールドで表現すべきか
   別フィールドにすべきか (`bgp_role:` 等)。
2. **spine ↔ spine の iBGP フルメッシュ**をどう書くか。本 passc の fixtures では
   spine は AS 65000 を共有するが、spine どうしの iBGP セッションは書いていない (元
   ファイルも書いていない)。実運用では必要な場合があり、「書くとしたら 1 本か 2 本か」
   「update_source は何か」が決まらない。ADR-0010 本文で明示するか、examples で示すかの
   判断。
3. **loopback 間 BGP の attaches_to が無い場合の表示**。ndl-viz でこの辺を「multihop」と
   マークするか、attaches_to を書いていない辺として普通に描くか。本 passc は前者前提で
   書いた。
