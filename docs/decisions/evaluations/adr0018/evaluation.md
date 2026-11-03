# ADR-0018 初版の横断評価 (2026-11-03)

対象: `drafts/0018-sessions-across-bridges-and-tunnels.md` の初版 (改訂 1 の前)。5 エージェントが並列に評価し、試し書き担当が `passb/` の B1〜B5 を書いた。

前提 (ユーザー決定。蒸し返さない): L2 透過は `layer2.bridges` を先取りして書く (案 V / F は却下)、トンネルは同じ ADR で扱う、マルチアクセスの隣接は次の ADR。

## 試し書きの検証

`layer2.bridges` は未実装なので、各ファイルから `bridges` を外して `python -m mlndl validate` を流した。試し書き担当が flow 形式の `description` に `,` を含めて
後ろがキーとして読まれていた誤り (B1 / B2 / B5) と、OSPF インスタンスの `nodes` を文字列で書いた誤り (B3) は統合担当が直した。直したあとの error は、ドラフトを実装すれば消えるものだけ:

| ファイル | 今の validator の error | ドラフトどおり実装したら |
|---|---|---|
| B1 (ポートベース 2 拠点 eBGP) | 通り道の食い違い | `{bridge:}` で valid |
| B2 (タグ変換 3 拠点 iBGP フルメッシュ) | 通り道の食い違い × 3 | `{bridge:}` で valid (タグは比べない) |
| B3 (GRE 2 対 + eBGP 2 本 + OSPF 1 本) | トンネルへの参照 × 6、同じ両端 × 1 (参照が解決できないことによる) | `{tunnel:}` で valid |
| B4a (自社 L2 スイッチをはさむ 2 ホップ) | 通り道の食い違い | 食い違いのまま (1 ホップ) |
| B4b (拠点側 LAG で箱へ) | 通り道の食い違い | `{bridge:}` で valid |
| B4c (トンネルを片側だけ書く) | トンネルへの参照 | 食い違い (片方だけトンネル IF) |
| B4d (同じ L1 IF を VLAN と bridge に) | なし | 改訂 1 で warning |
| B5 (wan-sites の書き直し) | トンネルへの参照 × 2 | valid |

## 一致した点

- D1 の方向 (方式名を書かない、bridge の有無で透過を表す、`role` を見ない、ポートの形は VLAN と同じ、`node` を書かない): 5/5
- `members` に拠点のルーターのポートを入れない線引き: 5/5 (network-tech は「入れると『ここで転送する』の意味が壊れる」、spec-architect は原案の supporting の向きと合うとした)
- 1 ホップのまま: spec-architect・network-tech。自社の L2 スイッチをはさむ構成は D8 に書く
- D3 のトンネル IF を `update_source` に: 5/5。linguist は Pass A 前に推したキー付き化を撤回 (機器の `update-source Tunnel0` と同じ)
- `transport_link` のキー名を変えない: 5/5 (linguist も改名を撤回)
- 推奨プレフィックス `bridge-`: linguist・example-author
- 後方互換: spec-architect が fixtures / examples を確認。既存の BGP / OSPF は直結かループバックで、通り道が変わるものはない。`valid_multisite_wan.yaml` の OSPF 8 本は同じリンクの両端で、warning は出ない

## 改訂 1 で反映した指摘

| 指摘 | 誰 | 反映 |
|---|---|---|
| `members` は所属と読まれ、ルーターのポートまで入れてしまう (Pass A 前の Q1_B がそうだった)。Linux の `bridge-ports` など業界の語は ports で、VLAN の `*_ports` とも並ぶ | linguist | **`members` を `ports` に改名**。例を 1 つ付けた。ポートの対向が同じ bridge のポートなら warning (ルーターのポートを書いた疑い。spec-architect の案) |
| bridge を書くのは箱をはさむときだけ。L2 専用線 (EPL) は L1Link のままで bridge は書かない | network-tech | D1 に追記 |
| 自社の L2 スイッチは VLAN で書く。bridge は番号を持たない L2 セグメント用 | network-tech | D1 に追記 |
| 拠点の L2 スイッチをはさむ構成は 1 ホップで届かない。2 つの bridge / VLAN を L1 でつないでも同じセグメントとはみなさない | network-tech・spec-architect・example-author (B4a) | D2・D8 に明記 |
| IS-IS は `interface` が L1 IF なので、その対向を見る (基盤の 1 層を省く) | network-tech | D2 に追記 |
| トンネルの対の判定 (source と destination_interface をたどる) と `{tunnel: [a, b]}` の順 (from, to) を明示 | example-author・linguist | D3 に追記 |
| `Ref` の複数コレクション化の形 (`paths`、label の連結、和集合で引く)。ADR-0002 D5 の未実装分の先取りであって新しい制約ではない | dsl-designer・spec-architect | D3 に追記 |
| `_l3_basis` にトンネルを 4 つ目の種類として足し、ADR-0011 D11 の分類 (`l3_attachments`) には入れない | dsl-designer・spec-architect | D3 に追記 |
| WireGuard のマルチピア、DMVPN (mGRE) の hub は 1 対 1 でないので扱わない | network-tech | D8 |
| OSPF / IS-IS の warning は ndl_version 1.x の間だけ。2.0 で error | dsl-designer・spec-architect・example-author | D4 |
| D4 は ADR-0010 D8 のポイントツーポイント前提を変えない | spec-architect | D4 |
| 同じ L1 IF を VLAN のポートと bridge の `ports` の両方に書いたら warning (drafts/0007 の vSwitch で再定義) | dsl-designer (warning)・spec-architect (info) | **warning**。今は箱のポートを VLAN に書く誤りの検出として役に立ち、vSwitch の uplink で正当になる時点で見直す |
| D6 のメッセージ: 矢印をやめる、選び方を (a)(b)(c) で、片方だけトンネル IF の分岐 | linguist・example-author | D6 |
| 自社が PE を持つ VPLS / EVPN、Q-in-Q、E-TREE の root / leaf、QoS は扱わない | network-tech | D8 |
| 影響範囲: `tests/test_refs.py` の `KEYED_REFERENCES`、CLAUDE.md の YAML 例とバリデーション表、ADR-0002 D7 の表、ADR-0010 D10 の表、ADR-0015、`vlan_endpoints` は bridge をはさんで広げないこと、`exporter/rfc8345.py` | spec-architect | Consequences |
| VLAN のポートの型から共通の基底 (`{interface:}` か `{lag:}` のちょうど一方) を抜き出し、bridge は `native` を持たない | dsl-designer | Consequences (実装の指針) |
| id に回線名を埋めない例に | linguist | 例の id を `bridge-wideether` に、回線名は `name` / `description` に |

## 採らなかった指摘

- **bridge をはさむ両端のサブ IF のタグが違うときに info** (network-tech): 採らない。タグ変換の契約では違うのが正しく、毎回出るとノイズになる (example-author・dsl-designer)
- **`members` を基底から外し、事業者網の LAG (`{lag:}`) を削る** (example-author): 採らない。形を VLAN のポートとそろえる方を優先する。書けても困らない

## 残る論点 (Pass C 向け)

- 改訂 1 で割れた論点はない。Pass C でゼロから再設計して同じ結論になるかを確かめる

## Pass C への Input サマリ

**Pass C で参照するもの**: 本評価メモ、Accepted の ADR (0001〜0006・0009〜0013・0017)、drafts/0007・0008・0014・0015、CLAUDE.md、`docs/exporter-cytoscape.md`、
`docs/role-vocabulary.md`、試し書き (`evaluations/adr0017/passc/`、`evaluations/adr0018/passa/`、`evaluations/adr0018/passb/`。passa の Q1_B と passb は改名前の `members` で書いている)、
`examples/wan-sites.yaml`、実装 (`src/mlndl/derive.py`・`schema/control_plane.py`・`schema/refs.py`・`schema/layer2.py`・`schema/layer3.py`・`validator.py`・`exporter/cytoscape.py`)。
**drafts/0018 は参照しない** (Pass C の原則)。

### 前提 (ユーザー決定。蒸し返さない)

- 事業者網の中の L2 の転送は `layer2.bridges` を先取りして書く (案 V: VLAN のポートにする、案 F: `provider_transport` のフラグ は却下)
- トンネル IF を `update_source` にすることは同じ ADR で扱う
- マルチアクセスの隣接 (3 拠点以上の OSPF / IS-IS、DR / DIS) は次の ADR

### 確定すべき論点 (優先順)

1. **bridge の最小の形**: フィールド (`id` / `name` / ポートの一覧 / `description`)、ポートの一覧の名前 (`ports` か `members` か)、そこに書くもの (箱のポートだけか、拠点のルーターのポートも書くか)、
   ポートの形 (VLAN のポートと同じ `{interface:}` / `{lag:}` か)、`node` を書かないこと、方式名 (E-LINE / E-LAN / VPLS) を書かないこと、bridge がないことを「透過しない」と読むこと、
   bridge を書く範囲 (箱をはさむときだけか。L2 専用線・自社 L2 スイッチとの使い分け)、drafts/0007 (vSwitch) との関係、検査 (error / warning)、推奨プレフィックス
2. **bridge に届くことの判定**: L3 IF の基盤の L1 リンクの対向が bridge のポートにあること、たどるホップ数、LAG、サブ IF のタグを比べるか、IS-IS (`interface` が L1 IF)
3. **トンネル IF を `update_source` / OSPF の `interface` に**: 型 (`Ref` を複数のコレクションに広げるか、キー付きにするか)、id の一意性、対の判定と通り道の値の形・順、
   `destination_ip` のとき、VRF (`vrf` か `transport_vrf` か)、トンネルの下の通り道、`_l3_basis` / `l3_attachments` での扱い
4. **OSPF / IS-IS の通り道**: 導くか、食い違いの severity (今まで valid だった YAML を error にするか)、ADR-0010 D8 との関係
5. **エクスポーター**: `transport_link` の値の形 (キー名を変えるか)、bridge を要素として出すか
6. **食い違いのメッセージ**
7. **ADR-0017 D5-2 の置き換え** (片側をトポロジー外にする書き方の扱い)
8. **扱わないもの**と**関連文書の改訂**

---

## Pass C の結果 (2026-11-03)

5 エージェントが drafts/0018 を読まずに本メモから再設計した。論点 1〜8 の大筋は改訂 1 と同じ結論になり、細部で割れた 4 点は統合担当が決めた。ユーザーの判断を待つものはなかった。
確定版は [ADR-0018](../../0018-sessions-across-bridges-and-tunnels.md)。試し書きは [passc/](passc/README.md) (P1〜P5c)。

**試し書きの検証**: `bridges` を外して `python -m mlndl validate` を流した。error はドラフトを実装すれば消えるものと、わざと invalid にしたものだけだった。

| ファイル | 今の validator | この ADR を実装したら |
|---|---|---|
| P1 (広域イーサ + IP-VPN の混在) | 通り道の食い違い | `{bridge:}` で valid |
| P2 (IPsec VTI の上の BGP / OSPF、`vrf` ≠ `transport_vrf`) | トンネルへの参照 × 4 | `{tunnel:}` で valid |
| P3 (bridge をはさむ IS-IS) | valid (通り道の検査がない) | `{bridge:}` で valid |
| P4 (`destination_ip` のトンネル、相手はトポロジー外) | トンネルへの参照 | valid、通り道なし |
| P5a (同じポートを 2 つの bridge に) | (bridges を外すと valid) | error |
| P5b (L3 IF とトンネルの id の重複) | valid | error |
| P5c (片方だけトンネル IF) | トンネルへの参照 | error (食い違い) |

**割れた点と判断**:

| 論点 | 意見 | 判断 |
|---|---|---|
| `ports` が 1 つ | dsl-designer: error。ほか: warning | **warning**。相手の拠点がトポロジー外なら 1 つしか書けないのは正当 |
| 同じポートを 2 つの bridge に | dsl-designer: warning。network-tech・spec-architect・linguist・example-author: error | **error**。サービス多重は D8 (ポートにタグを足して表す) |
| bridge をエクスポーターの要素に出すか | dsl-designer: 出さない (箱と二重に描かれる)。network-tech・spec-architect: 出す | **出す**。描き方は ndl-viz が決める。mlndl は書かれた情報を落とさない |
| `transport_link` のトンネルの形 | linguist: `{tunnel: {from, to}}` (無向の `endpoints` と同じリストの形を避ける)。ほか: `[from, to]` | **`[from, to]`**。今の `{lag: [<この端>, <相手>]}` がすでに from、to の順のリストで、形を揃える |

**改訂 1 に足したもの**:

- LAG のメンバーだけを `ports` に書いたら warning (spec-architect。ADR-0013 と同じ)
- 同じ種類の事業者網が 2 つなら id は事業者で分ける (`bridge-wideether-ntt`) (linguist)
- トンネルの対の判定は両端 `node` のときだけ (example-author の P4)
- 片側をトポロジー外にする書き方は文書で推奨しないだけで、warning は出さない。validator は相手が自社の機器かを知りえない (spec-architect が挙げた問い)
- メッセージは「〜なら、〜する」の形で、直結・事業者網・トンネルの順 (linguist)
- D7 を表にした (network-tech)
- D8 に `transport_vrf` と `source` の L3 IF の `vrf` の照合、PMTU / MSS、IPsec / WireGuard の鍵を足した
- RFC 8345 エクスポーターは bridge を当面出さない
