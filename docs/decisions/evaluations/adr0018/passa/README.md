# ADR-0018 Pass A の前の論点整理 試し書き

ADR-0017 D5-2「箱 (事業者網) をはさむルーティングのセッション」を、`drafts` にする前の
候補案で試し書きし、各案の書きにくさを集める。構文は変えない (ADR-0017 Pass C で確定した
`labels.site` / `role: provider-network` / 箱の L1 IF の `name` は拠点名 / `description`) 。

## ファイル

| ID | 問 | 案 | 構成 | 期待される validator 出力 |
|---|---|---|---|---|
| `Q1_V.yaml` | Q1 | 案 V (layer2.vlans) | 2 拠点の広域イーサ上の eBGP | 現状: ERROR (transport_mismatch)。案 V 採用時: OK を期待。嘘: vlan_id ダミー |
| `Q1_B.yaml` | Q1 | 案 B (layer2.bridges) | 同上 | 現状: ERROR (未実装の `layer2.bridges` + transport_mismatch)。案 B 採用時: OK を期待 |
| `Q1_F.yaml` | Q1 | 案 F (provider_transport) | 同上 | 現状: ERROR (未実装の `provider_transport` + transport_mismatch)。案 F 採用時: OK を期待 |
| `Q2_V.yaml` | Q2 | 案 V | 3 拠点 E-LAN の OSPF | **OK** (OSPF には transport_mismatch 検査がない。P1 と同じ)。拡張は 1 エントリにまとめること |
| `Q2_M.yaml` | Q2 | 案 M (ospf-segment) | 同上 | 現状: ERROR (type: ospf-segment が discriminated union に無い)。案 M 採用時: OK を期待 |
| `Q3_T.yaml` | Q3 | 案 T (update_source が tunnel) | 2 本のインターネット + GRE + eBGP | 現状: ERROR (update_source が tunnel-* を指せない: Ref の対象外)。案 T 採用時: OK を期待 |
| `Q4_F.yaml` | Q4 | 案 F (一番よさそう) | LAG + subif + 2 回線冗長 | 現状: ERROR (未実装 + transport_mismatch)。案 F 採用時: OK を期待 |

## 検証コマンド (統合担当向け)

```sh
cd mlndl
for f in docs/decisions/evaluations/adr0018/passa/Q*.yaml; do
  echo "── $f ──"
  python -m mlndl validate "$f"
done
```

## 各案で書いた分量 (meta 以降の実行可能 YAML、空行とコメント除く概算)

| ファイル | 行数 | 繰り返し書いた事実 | 嘘 (推測で書いた箇所) |
|---|---|---|---|
| Q1_V | ~45 | 箱の 2 側の L1 IF を 2 回 (interfaces + access_ports) | `vlan_id: 999` (事業者側の内部タグは見えない) |
| Q1_B | ~45 | 箱の 2 側の L1 IF を 2 回 (interfaces + bridge.members) | なし |
| Q1_F | ~35 | — | なし |
| Q2_V | ~65 | 箱の 3 側の L1 IF を 2 回 + OSPF フルメッシュ 3 本に area 情報 3 回 | `vlan_id: 999` |
| Q2_M | ~45 | OSPF の members に 3 L3 IF (1 エントリで済む) | なし |
| Q3_T | ~75 | トンネル IF が双方向で 2 本 (tokyo→fukuoka と逆向き)、ISP ごとに 2 セット | なし |
| Q4_F | ~55 | 箱側の L1 IF 2 本 (interfaces)、LAG の members で L1 IF 2 本の重複 | なし |

## 書きにくかった点

### 案 V の最大の問題: 知らない vlan_id を書かされる

事業者網 (広域イーサ) の中で使われる 802.1Q タグは契約側 (ユーザー) に見えない
ことが多く、`vlan_id` を書き手が決めなければならない。`vlan_id: 999` のような
推測値を書くことになり、構文の意味 (「このポートはこの vlan_id を運ぶ」) と
実運用がずれる。ADR-0005 D4 補則「表現の指針」の「推測で書かざるを得ない構文」
に該当する。

### 案 B の未決事項: bridge の node / プレフィックス / vlans との関係

`layer2.bridges` を先取りすると、以下を同時に決める必要がある。

- bridge の id プレフィックス (`bridge-*`? ADR-0002 D7 への加筆)
- bridge は特定のノードに属するか、浮いているか (ここでは node を書かない方針で書いた)
- `layer2.vlans` との関係 (bridge と VLAN は同じことを別の切り口で言う構文に
  なりかねない。重複構文を 1.x で許すか)

### 案 F の限界: 1 つの箱 = 1 セグメント

`provider_transport: l2` を箱に書くと、その箱に接続するすべての拠点が同じ
セグメントに属する扱いになる。これは E-LAN には合うが、E-Line (2 拠点だけが
対になる) や、1 本の広域イーサ契約の中で複数の EVC を持つ構成を書けない。
Q4 の「同じ箱に 2 本の L1 IF を束ねて 1 EVC」を書くには、箱の中で L1 IF を
グルーピングする構文がもう 1 つ要る (結局 案 V か 案 B に戻る)。

### 案 T の迷いどころ: トンネル 2 本と BGP 1 本の対応

`tunnel_interfaces` は方向を持つ (source + destination_interface で片方向)。
BGP セッションは双方向。`update_source` に `tunnel-*` を書くとき、
`from.update_source` と `to.update_source` に別のトンネル IF を書くことに
なる (`tunnel-tokyo-fukuoka` と `tunnel-fukuoka-tokyo` が対)。
対応関係 (この 2 本が 1 ペア) を validator が導けるかは、`destination_interface`
を逆向きにたどって照合する処理を追加する必要がある。

### 案 M の未解決: segment の整合性をどう検査するか

`type: ospf-segment` の members に挙げた L3 IF が、本当に 1 つの L2 セグメント
上にあるかは、別途「同じ VLAN か同じ bridge か同じ provider_transport: l2
の箱の反対側か」を検査することになる。したがって案 M は **単独では成立せず**、
下に案 V / 案 B / 案 F のいずれかが要る (座組みの問題)。

### 共通の違和感: 「拠点名」の二重書き (ADR-0017 側で既出)

箱の L1 IF の `name` に拠点名を書く慣例 (ADR-0017 D3 例)。拠点側の
`labels.site` と重なるが、相互参照はない (name は参照ではない)。
LAG + 2 回線冗長の Q4 では、箱側の L1 IF が `tokyo-a` / `tokyo-b` と
分岐するので、「拠点名」の意味が揺れる (個の回線名か、拠点名か)。

### Q3 の既知の限界 (ADR-0017 D5-2 問い 4) の再確認

`examples/wan-sites.yaml` の GRE トンネルは双方向 2 本書いてあるが、その上の
BGP は書けていない。案 T で `update_source: tunnel-*` を許すのが素直で、
`layer3.tunnel_interfaces` が `layer3.interfaces` と「L3 の端」として
同じ役割を持つことを言語上明確にする必要がある。

## 試し書き担当が推す案

**Q1 (2 拠点): 案 F が最小**。箱に 1 行足すだけで、拠点側の構文は変えずに通り道が
導けるようになる。ただし E-LAN (Q2) に広げると「1 箱 = 1 セグメント」の
思い込みが露呈するので、案 F 単独では不足。

**Q2 (3 拠点 E-LAN): 案 M + 案 F の併用**。案 M で「どの IF 群が 1 セグメント上に
あるか」を 1 エントリで宣言し、案 F で箱の性質を書く。routing_neighbors の
2 端点制約 (ADR-0010 D8) を超える構文は、問 3 として独立 ADR で扱うのが素直。

**Q3 (GRE の上の BGP): 案 T 一択**。`update_source` の型を広げるだけで、既存の
`tunnel_interfaces` が自然に生きる。ADR-0017 D5-2 の問い 4 が指すとおり。

**Q4 (嫌なケース): 案 V か 案 B**。LAG + subif + 2 回線冗長を 1 箱の中で表すには、
箱の内側に 1 つ以上のセグメント (EVC) を書ける必要がある。案 F では
「同じ箱 = 同じセグメント」の暗黙前提を外せない。案 B の bridge か、
案 V の VLAN (vlan_id ダミー問題は残る) のどちらかで EVC を明示する。

**総合: 案 B + 案 T + 案 M の組み合わせ**を推す。bridge が「箱の中のセグメント」
を宣言し、tunnel_interfaces が update_source になり、ospf-segment が
マルチアクセスの隣接を 1 エントリにする。案 V は vlan_id ダミーが
`description` の自由記述の原則 (ADR-0017 D4) と相性が悪い。案 F は E-LAN と
Q4 で破綻する。

ただし bridge を Phase 2 に先送りすると ADR-0018 自体が待たされる。
Phase 1.x で先行実装する価値があるかは仕様担当の判断。

## 統合担当の実行結果 (2026-11-03)

`python -m mlndl validate` の結果は予想どおり。

| ファイル | 結果 |
|---|---|
| Q1_B / Q1_F / Q4_F | スキーマの段階で error (`layer2.bridges` / `provider_transport` が未定義) |
| Q1_V | 通り道の食い違いで error (ADR-0010 D7) |
| Q2_M | スキーマの段階で error (`type: ospf-segment` が未定義) |
| Q2_V | valid (OSPF には通り道の検査がない) |
| Q3_T | `update_source` がトンネルを指して参照の error。2 本目は参照が解決できないため「同じ両端」の error も出る |

ユーザーの判断で案 B + 案 T を採り、マルチアクセスは次の ADR に回した。ドラフトは [drafts/0018](../../../drafts/0018-sessions-across-bridges-and-tunnels.md)。
Q1_B は拠点のルーターの IF も `members` に入れているが、ドラフトでは `members` は転送する側 (箱) のポートだけとした (D1)。
