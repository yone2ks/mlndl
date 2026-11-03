# ADR-0018 Pass B — ドラフトでの試し書き

Pass A の 5 エージェント評価と試し書き (`../passa/`) のあとに確定した
[drafts/0018](../../../drafts/0018-sessions-across-bridges-and-tunnels.md) で、
典型的な構成と嫌なケースを書き直す。構文の変更はドラフトどおり:

- `layer2.bridges` を最小の形で先取り (D1)
- `update_source` と OSPF の `interface` に `layer3.tunnel_interfaces` を書ける (D3)
- マルチアクセスの隣接は次の ADR に回す (ユーザーの判断 / D8)

## ファイル

| ID | 構成 | 使う D | 現状の mlndl での予想 | ドラフト実装後の予想 |
|---|---|---|---|---|
| `B1_wideether-portbased-ebgp.yaml` | 2 拠点 EPL (ポートベース) + eBGP | D1, D2 | schema error (bridges 未定義) + transport_mismatch | errors 0。通り道 `{bridge: bridge-we220}` |
| `B2_wideether-tagswap-ibgp-fullmesh.yaml` | 3 拠点 EVP-LAN (タグ変換 100/200/300) + iBGP フルメッシュ | D1, D2 | schema error + transport_mismatch | errors 0。通り道 `{bridge: bridge-we300}` × 3 本。問 3 の info 候補 |
| `B3_internet-gre-ebgp-ospf.yaml` | ISP 2 社 + GRE 2 対 + eBGP 2 本 + OSPF 1 本 | D3, D4 | Ref error (update_source が tunnel-* を指せない) | errors 0。通り道 `{tunnel: [...]}` |
| `B4a_two-hop-via-own-switch.yaml` | 自社 L2 SW をはさむ (2 ホップ) | D2 (負のケース) | schema error + transport_mismatch | **error** (D6 の新しいメッセージ) |
| `B4b_site-lag-to-provider-box.yaml` | 拠点側 LAG → 箱 | D1, D2 (LAG) | schema error + transport_mismatch | errors 0。通り道 `{bridge: bridge-we220}` |
| `B4c_tunnel-one-side-only.yaml` | GRE の片側だけ書く | D3 (負のケース) | Ref error | **error** (「片方だけトンネル IF」) |
| `B4d_same-l1if-in-vlan-and-bridge.yaml` | 同じ L1 IF が VLAN と bridge の両方に出る | D1 の未決 / D8 の境界 | schema error | **未決** (ドラフトからは決まらない) |
| `B5_wan-sites-adr0018.yaml` | `examples/wan-sites.yaml` に bridge と GRE の上の BGP を足した版 | D1, D2, D3 | schema error 複数 | errors 0 |

(`B5` は `examples/wan-sites.yaml` 本体を変更していない。差分は本ファイル中の `+ ADR-0018` マーカーを参照)

## 書いた行数と、同じ事実を書いた回数

各ファイル、meta 以降の空行とコメントを除いた概算。「同じ事実」は、同じ参照先 (ノード・L1 IF・LAG など) を
別の構文で 2 回以上書いた箇所を指す。

| ファイル | 行数 | 同じ事実を書いた箇所 | 嘘 (推測) |
|---|---|---|---|
| B1 | ~55 | 箱の L1 IF 2 本 (`layer1.interfaces` と `bridges.members`) | なし |
| B2 | ~75 | 箱の L1 IF 3 本 (interfaces と members)、サブ IF 3 本 (interfaces + L3 IF の attach) | なし |
| B3 | ~80 | トンネル IF 4 本 (双方向で 2 対) + ソース/デスティネーションの L3 IF | なし |
| B4a | ~55 | 箱の L1 IF 2 本 | なし |
| B4b | ~60 | 箱の L1 IF 3 本 + LAG メンバー 2 本 (interfaces と lag.members) | なし |
| B4c | ~45 | 箱の L1 IF 2 本 | なし |
| B4d | ~30 | L1 IF (`access-sw-ge48`) を vlans と bridges の両方に | — (問いそのものが「同じ事実の二重書き」) |
| B5 | ~160 | `wan-sites.yaml` と同じ全ノード + 広域イーサの箱の L1 IF 2 本を bridges に二重に | 技術疑問: core SW が BGP を話す構成を取ってしまった (下記) |

## 書きにくかった点 (Pass B 評価の問 1〜8 に沿って)

### 1. members は転送する側のポートだけ (D1)
B1 を書くときに「ドラフト本文のかっこ書き (= 拠点のルーター IF は書かない) 」を読み落とすと
Pass A の Q1_B と同じ間違いをする。文章だけで線引きするには読み手に強い。ドラフト本文の
「転送する側」が「意味 (ルーターはフレームを転送しない) から導く定義」になっているが、
初心者には導きが難しい。例を 1 つ付けるのがよさそう。

### 2. 1 ホップ届き判定 (D2)
B4a で意図的に 2 ホップにしたが、「自社の L2 SW をどう扱うか」はドラフトから一意に
決まらない。選択肢は 2 つあり、どちらを書くかで validator の反応が変わる:
- (a) 自社 SW のポートも members に入れて 1 つの bridge で扱う (= 1 ホップに畳む)
- (b) 自社 SW 側に別の bridge を書き、2 つの bridge が L1 リンクでつながる構造にする

(b) を書くと「異なる bridge どうしのあいだで BGP が張れるか」というドラフト未定義の問いに
行き当たる。D2 の表は「別の bridge に届く = 食い違い」としか言わないので、L1 リンクで
つながっていても「同じセグメント」と validator に認識させる書き方がない。
→ 「bridge どうしを L1 リンクでつなぐ」は実在パターン (自社 SW + 事業者網) なので、D2 を
加筆するか、drafts/0007 の vSwitch 設計に預けるかを決める必要がある。

### 3. サブ IF のタグを bridge をはさむと比べない (D2)
B2 で東京=100 / 大阪=200 / 名古屋=300 を書けたのは良い (Pass A の Q1_V の
`vlan_id: 999` 嘘が消える)。ただし「比べない」が本当に info で見せる価値があるかは
微妙。1 セグメントに 3 つの違う vlan_id のサブ IF が並ぶのは EVPL の正しい形であり、
info を出すと「意図的な設計」を毎回ノイズとして見ることになる。
→ 「同じ bridge に異なる vlan_id」の info は、タグがそろう (= EPL) 構成では
出ないので、「複数の vlan_id が同居」のときだけ info でよさそう。でも ndl-viz では
表示したい情報なので、info ではなく「導いた属性」として derive 側で返すのが素直かもしれない。

### 4. トンネルの対の判定 (D3)
B3 で 2 対のトンネルを書いたが、BGP セッションの `from.update_source` と `to.update_source` に
別のトンネル IF (`tunnel-tokyo-fukuoka-isp-a` と `tunnel-fukuoka-tokyo-isp-a`) を書くときの
対応関係が ID の命名規約だけで表現されるのは危うい。validator は `source` / `destination_interface` を
たどって対を確かめるが、書き手が間違えて違う ISP のトンネルを混ぜても (A の from + B の to) 、
`source` の対向で検出できる。これは D3 本文で明示したほうがよい。

B4c (片側だけ) は D3 の負のケース。「片方だけトンネル IF」のエラーメッセージを D6 に
追記する必要がある (D6 の現文は直結/事業者網/トンネルの 3 択を示すだけで、「相手のトンネルを
書き忘れたのでは」の助言はない)。

### 5. OSPF / IS-IS の食い違いを warning に (D4)
B3 で OSPF の `interface` にトンネル IF を書いた。food error ではなく「warning まで緩和する」の
線引きは、既存の YAML を壊さない配慮としては妥当。ただし 1.x の間だけ warning という
緩和は、2.0 に向けて書き手に「将来 error になる」と予告することになる。D4 本文で「2.0 で
error に昇格」を明記するほうがよい。

### 6. `transport_link` のキー名 (D5)
B1 / B2 / B3 を書いた立場からは、`transport_link` のまま `{"bridge": ...}` / `{"tunnel": ...}` が
増えるのが素直。linguist が `transport` を推した意図は分かるが、エクスポーターの出力互換
(ndl-viz) を優先。ドラフトの判断に賛成。

### 7. 推奨プレフィックス `bridge-` (D1 / 検査)
B1〜B5 で `bridge-we220` / `bridge-we300` / `bridge-we100` / `bridge-dvs-prod` と素直に書けた。
ADR-0002 D7 に `bridge-` を足す提案に異論なし。ただし「同じ契約名を bridge の id に入れる」慣例を
作るなら、`bridge-<契約 ID>` の例を docs に 1 行書き足すとよい。

### 8. 同じ L1 IF が VLAN のポートと bridge の両方 (B4d)
ドラフトから正否が決まらない。D8 「vSwitch としての bridge は扱わない」で範囲外に逃げている
が、Pass B の問 8 として挙がっているので判断は要る。
→ 「warning (重複宣言、drafts/0007 の vSwitch で統合予定)」が妥当か。
→ あるいは「同じ L1 IF を 2 つの構成子で宣言するのは常に error」として、
vSwitch のアップリンクは drafts/0007 の `vswitch.uplinks` のみで書く、と前倒しで決める。

## 技術的疑問 (network-tech-reviewer へ)

### 1. B5 で core SW が BGP を話す構成を取った
元の `wan-sites.yaml` では `tokyo-core` と `nagoya-sw` は BGP を話さず、拠点ルーター
(`tokyo-rtr*`) のみが話す構成。広域イーサ (`vlan-100`) の両端が `tokyo-core-te3` と
`nagoya-sw-ge48` のため、「広域イーサの上に BGP を張る」を素直に書くには core SW / SW が
BGP を話す構成にせざるを得なかった。実運用では L2 SW が広域イーサを折り返し、拠点
ルーターが SVI 相当の L3 IF を持つのが現実的。L1 を変えずに書き足すのが example-author の
役目だったが、SVI を SW に書くことで「SW が BGP を話す」という違和感が出た。

### 2. B4b の「対向の LAG が members にある」の意味
D2 本文の「対向の LAG」とは、箱側で LACP を終端する LAG を書く構文を想定しているか。
事業者網の内部設定を mlndl で書く意味はほぼないので、この分岐は不要なのではないか
(= 「メンバーの対向のどれかが members にある」だけで十分)。D2 の表現を簡素化できる余地。

### 3. B2 の vlans との関係
`layer2.vlans` と `layer2.bridges` は「802.1Q 番号を持つかどうか」で分かれると読んだが、
現実には同じ L2 セグメントが VLAN のタグ付きで運ばれることも多い (B5 の広域イーサが
vlan-100 を運ぶ)。vlans と bridges を両方書いた B5 のような構成が「ダブル宣言」として
error / warning になるのか、「vlan-100 の運搬を bridge-we100 が担う」の 2 層構造として
valid になるのか、ドラフトは触れていない。

## ドラフトの文だけでは書き方が決まらなかった箇所 (まとめ)

1. 自社 L2 SW が bridge と並ぶときの書き方 (B4a) — 1 つの bridge に畳むか、2 つの bridge を L1 で繋ぐか
2. `layer2.vlans` と `layer2.bridges` の重複宣言 (B5) — どちらも書いてよいのか
3. 同じ L1 IF が VLAN と bridge の両方 (B4d) — error / warning / 許容のどれか
4. タグ変換のある構成で「違う vlan_id が同じ bridge に同居」の見せ方 (B2) — info / 導出属性 / 何もしない
5. トンネル対の片側欠落のエラーメッセージ (B4c) — D6 に追記するか
6. 多数ある「同じ事実の 2 回書き」(箱の L1 IF を interfaces と bridges.members、
   LAG のメンバーを interfaces と lag.members に二度書く) — これは
   ADR-0001 / ADR-0013 の既決事項の帰結で、ドラフトは踏襲しただけ。改善の
   余地はあるが本 ADR の範囲外。

## 推す案

ドラフトのまま採用で問題は少ない。ただし D1 本文に「members は転送する側のポートだけ」の
例を 1 行足すこと、D6 のメッセージに「片方だけトンネル IF」用の分岐を足すこと、D2 の表に
「別の bridge どうしが L1 でつながる (= 自社 SW + 事業者網)」の扱いを 1 行足すこと、を
Pass C に向けての差分として推す。

## 統合担当の実行結果 (2026-11-03)

`layer2.bridges` は未実装なので、`bridges` を外して `python -m mlndl validate` を流した。flow 形式の `description` に `,` と数字が続いてキーとして読まれていた箇所 (B1 / B2 / B5) を
引用符で囲み、B3 の OSPF インスタンスの `nodes` を `[{node: ...}]` の形に直した。直したあとの error は、ドラフトを実装すれば消えるもの
(bridge をはさむ通り道の食い違い、トンネルへの参照) と、B4a / B4c の意図した食い違いだけ。結果の表は [評価メモ](../evaluation.md)。

改訂 1 で bridge の `members` は `ports` に改名した。このディレクトリのファイルは改訂前の `members` のまま残す。
