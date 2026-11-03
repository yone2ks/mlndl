# ADR-0018 Pass C — ゼロから考えた試し書き

Pass B (`../passb/`) で B1〜B5 を書き、改訂 1 で `members` → `ports` の改名が確定した。
Pass C では **drafts/0018 を参照せず**、評価メモ (`../evaluation.md`) の
「Pass C への Input サマリ」と参照物だけからゼロで書き直し、Pass B の結論に収束するか
を確かめる。優先したのは Pass B で書いていない構成:

- 広域イーサと IP-VPN を両方持つ拠点 (bridge を書く箱と書かない箱の混在)
- IPsec VTI の上の OSPF と BGP、VRF (`vrf` と `transport_vrf` が違う) を含む
- IS-IS を bridge をはさんで 2 拠点で (endpoint が L1 IF)
- トンネルの片側が `destination_ip` (相手がトポロジー外)
- invalid 版 3 本 (同じポート×2 bridges、L3 IF と tunnel の id 重複、対になっていないトンネル)

Pass B と違い、本 Pass では **`ports`** (改名後の名前) で書いている。

## ファイル

| ID | 構成 | 使う D | 現状の mlndl での予想 | ドラフト実装後の予想 |
|---|---|---|---|---|
| `P1_mixed-wideether-and-ipvpn.yaml`           | 広域イーサ + IP-VPN の混在 (3 拠点) | D1, D2 (bridge の有無) | schema error (`bridges` 未定義) + 両端 node BGP 1 本が transport_mismatch | errors 0。広域イーサの通り道 `{bridge: bridge-we220}`。IP-VPN 3 本はトポロジー外相手で通り道なし |
| `P2_ipsec-vti-vrf-separated.yaml`             | IPsec VTI + OSPF + BGP。`vrf` ≠ `transport_vrf` | D3, D4 | Ref error (`update_source` / OSPF の `interface` が `tunnel-*` を指せない) | errors 0。BGP / OSPF ともに通り道 `{tunnel: [tunnel-hq-branch, tunnel-branch-hq]}` |
| `P3_isis-over-bridge.yaml`                    | IS-IS を bridge をはさんで 2 拠点 | D1, D2 (IS-IS の 1 段短い判定) | schema error (`bridges` 未定義) | errors 0。IS-IS の通り道 `{bridge: bridge-we220}` |
| `P4_tunnel-destination-ip.yaml`               | GRE の対向が `destination_ip`、BGP の to は outside | D3 (片側 outside の線引き) | Ref error (`update_source: tunnel-*`) | errors 0。outside endpoint なので対の判定はスキップ。通り道は導かれない (ADR-0010 のまま) |
| `P5a_invalid_same-port-in-two-bridges.yaml`   | 同じ L1 IF が 2 bridges の `ports` | D1 (負のケース) | schema error (`bridges` 未定義) | **error** (L1 IF 'net-provider-tokyo' が複数の bridge の ports に) |
| `P5b_invalid_l3if-tunnel-id-collision.yaml`   | L3 IF と tunnel IF で同じ id | D3 の ID 空間 (負のケース) | 一部 schema error (Ref 未拡張) | **error** (ID 'hq-rtr-wan' が L3 インターフェース と トンネルインターフェース の両方で) |
| `P5c_invalid_unpaired-tunnel.yaml`            | from だけ tunnel IF、to はループバック | D3 の対の判定 (負のケース) | Ref error (`update_source: tunnel-*`) | **error** (片方だけ tunnel IF、相手のトンネル IF を書くか他の経路に揃える) |

## Input サマリの論点ごとの結論

Pass B の結論と差がある箇所は「**Pass B との差**」に書く。差がなければ「同じ」。

### 1. bridge の最小の形

- **結論**: フィールドは `id` / `name` / `ports` / `description`。ポートのキー形式は VLAN の trunk_ports / access_ports と同じ `{interface:}` か `{lag:}` のちょうど一方。`node` は書かない (ADR-0005 D6 に沿って参照先から導出)。方式名 (E-LINE / E-LAN / VPLS) は構文に出さない。bridge がないことを「透過しない」と読む。bridge を書くのは L2 透過が必要なときだけ (= 事業者網の L2 契約・自社 vSwitch の将来)。L1Link (L2 専用線) や VLAN (番号を持つ自社 L2 SW のドメイン) は使い分ける。drafts/0007 (vSwitch) は本 ADR の加算で後から統合予定。検査: 同じポートを複数の bridge に書くのは **error** (P5a)。推奨プレフィックス `bridge-`。
- **理由**: VLAN と形をそろえると書き手の負担が増えない (P1 / P3 で確認)。多重所属は L2 透過の意味で成立しない (P5a)。
- **Pass B との差**: 同じ。`ports` の名前も Pass B の改訂 1 と一致 (ゼロから考えても `members` より `ports` が自然 — Linux の `bridge-ports`、VLAN の `*_ports` と並ぶ)。

### 2. bridge に届くことの判定

- **結論**: L3 IF の `attaches_to` の L1 IF の対向が bridge の `ports` にあること。1 ホップ (= L3 IF → L1 IF → 対向)。サブ IF をはさむときは L3 IF → サブ IF → L1 IF → 対向 で、サブ IF は「圧縮して数えない」。LAG のときは LAG のメンバーの対向のどれかが `ports` にあること。**IS-IS の endpoint は L1 IF**なので判定は 1 段短くなる (L1 IF → 対向 → `ports`)。サブ IF のタグ (`vlan_id`) は bridge をはさむと比べない (タグ変換は正当)。
- **理由**: サブ IF を圧縮しない書き方は「`attaches_to` のキーが何種類あるか」で経路の数え方が増えるため、validator の実装も複雑になる (P2 / P3 で確認)。IS-IS が L1 IF 直で張ることと整合。
- **Pass B との差**: 同じ。IS-IS の 1 段短い判定は Pass B の指摘を Pass C でも再確認 (P3)。

### 3. トンネル IF を `update_source` / OSPF の `interface` に

- **結論**: `update_source` と OSPF の `interface` の `Ref` を `layer3.interfaces` と `layer3.tunnel_interfaces` の 2 コレクションに広げる。両コレクションの id は衝突してはいけない (ADR-0002 D5 の既存ポリシーをトンネル IF にも広げる / P5b)。
  対の判定 (= 通り道 `{tunnel: [from, to]}` を導く) は**両端 node のときだけ**走る (P4 の outside はスキップ、P5c の片方だけ tunnel IF は error)。対の判定は `source` / `destination_interface` が互いに逆向きかで決める。
  VRF は tunnel IF の `vrf` (overlay) と `transport_vrf` (underlay) が別でよい (P2)。BGP のインスタンスの `vrf` との一致は `vrf` (overlay) 側で見る。`transport_vrf` と underlay 側の L3 IF の `vrf` の一致検査は本 ADR の範囲外。
  `_l3_basis` にトンネルを 4 つ目の種類として足し、ADR-0011 D11 の `l3_attachments` には入れない (= トンネル IF 自身の「attaches_to」はない)。
- **理由**: Ref 拡張の形式は ADR-0015 の加算的拡張 (「複数コレクションを和集合で引く」) で済む (P2 / P4)。ID 空間重複の検査も _check_interface_id_spaces の加算で済む (P5b)。
- **Pass B との差**: 同じ。Pass B で `Ref` を複数コレクションに広げる形は確定済みで、Pass C でも同じ結論。VRF 分離 (`vrf` ≠ `transport_vrf`) は Pass B の B3 では試していなかった軸で、Pass C の P2 で加算で収まることを確認。

### 4. OSPF / IS-IS の通り道

- **結論**: 導く。食い違いの severity は **ndl_version 1.x の間 warning、2.0 で error**。既存の YAML (直結の両端で OSPF / IS-IS を張っているもの) は食い違いが起きないので warning は出ない。ADR-0010 D8 のポイントツーポイント前提は変えない。
- **理由**: 2.0 で error に昇格するが、既存 YAML を 1.x の間に壊さない緩和。P2 / P3 で確認。
- **Pass B との差**: 同じ。

### 5. エクスポーター

- **結論**: `transport_link` のキー名は変えない。値の形は `{bridge: <id>}` と `{tunnel: [<from id>, <to id>]}` を追加。bridge を要素 (= ndl-viz の円 / 枠) として出すかはこの ADR では決めない (= 当面は辺にのみ現れる)。
- **理由**: ndl-viz の既存出力との互換を優先 (Pass B の問 6 と一致)。
- **Pass B との差**: 同じ。

### 6. 食い違いのメッセージ

- **結論**: 「両端の update_source から導いた通り道が食い違います (from: …、to: …)」の後に、
  (a) 直結の候補、(b) 同じ bridge の候補、(c) トンネルの対の候補 の 3 択で助言する。
  片方だけ tunnel IF のときは「相手のトンネル IF (destination_interface が …) も書くか」を加える (P5c)。
  矢印記号 (`→`) は使わず、「from 側」「to 側」で分かる形に。
- **理由**: Pass B の linguist / example-author の指摘のとおり。
- **Pass B との差**: 同じ。

### 7. ADR-0017 D5-2 の置き換え

- **結論**: 広域イーサ越しの自社機器どうしの BGP は、本 ADR で両端 node で書けるようになる (D5-2 の「片側トポロジー外」の回避策は不要になる / P1)。
  クラウドの PE などトポロジー外の相手は、トンネル越しでも「片側 outside」の書き方が引き続き使える (P4)。
  3 拠点以上の広域イーサの OSPF / IS-IS のマルチアクセスは本 ADR では**まだ範囲外**。次の ADR で扱う (ユーザー決定の前提どおり)。
- **理由**: 両端 node + 通り道導出で、D5-2 の限界 (1 セッションを 2 エントリに書く等) が消える。
- **Pass B との差**: 同じ。

### 8. 扱わないもの と 関連文書の改訂

- **結論**:
  - 扱わない: WireGuard のマルチピア、DMVPN (mGRE) の hub、自社が PE を持つ VPLS / EVPN、Q-in-Q、E-TREE の root / leaf、QoS、マルチアクセスの隣接 (次の ADR)、サブ IF のタグが bridge をはさんで違うときの info (タグ変換の契約では違うのが正しい)
  - 加算する関連文書: `tests/test_refs.py` の `KEYED_REFERENCES`、CLAUDE.md の YAML 例とバリデーション表、ADR-0002 D7 の表 (`bridge-` を加算)、ADR-0010 D10 の表、ADR-0015、`derive.vlan_endpoints` は bridge をはさんで広げない、`exporter/rfc8345.py` と `exporter/cytoscape.py` (通り道の値の形を加算)
- **Pass B との差**: 同じ。

## まとめ

Pass B の改訂 1 で確定した設計 (`ports`、D1〜D8) をゼロから書き直しても、同じ結論に収束した。
論点ごとに実装後の予想は上の表の「ドラフト実装後の予想」の列で、Pass C の 7 本すべてで validator の挙動が予測どおりに決まる。

Pass B で書いていなかった軸 (混在拠点 P1、VRF 分離 P2、IS-IS P3、片側 outside P4、ID 衝突 P5b) をゼロから書き足したが、
いずれも Pass B の D1〜D8 の加算的な派生で済み、設計の線引きを変える必要はなかった。
