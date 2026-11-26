# ADR-0029 Pass A — mlndl-example-author

議題: EVPN Multi-Site を MLNDL でどう書くか。試し書きで確かめる。

## 作ったファイル

- `a1-current-syntax.yaml` — 2 サイトの EVPN Multi-Site を今の構文だけで書いたもの。問題点を `# FEEDBACK (N):` で残した
- `a2-fabric-grouping.yaml` — 新しい一覧 `layer2.vxlan_fabrics` と、L2VNI の `fabrics` / `stitching` を足す案。layer1 / layer3 は a1 と同じで省略
- `a3-vtep-scope-and-stitching.yaml` — VTEP に `scope`、L2VNI に `stitching` を足す案 (加算が小さい案)

a2・a3 は仮の構文なので、今の mlndl では通らない。

## トポロジー

各サイトに spine 2・leaf 2・BGW 2 (anycast BGW)・サーバー 1。DCI は bgw1 どうし・bgw2 どうしの /31 の直結 2 本。L2VNI 10100 (`vlan-100`)、L3VNI 10900 (`vrf-tenant-a`、Symmetric IRB)。underlay は各サイトで OSPF、overlay は iBGP EVPN (spine が RR)、サイト間は eBGP multihop。BGW は lo0 (PIP)・lo1 (サイトの VIP)・lo2 (Multi-Site の VIP) の 3 つのループバックを持ち、VTEP は 8 個 (leaf 4・BGW のサイトの VIP 2・Multi-Site の VIP 2)。

## 今の構文で書けた所 / 書けない所 / 誤読される所

**書けた** (ADR-0014 D1 の方式中立は Multi-Site でも働いた):

- 1 台に複数のループバックを L3 IF として持つ
- anycast の VIP と Multi-Site の VIP を `sources` + `address` で書く
- サイト内の iBGP EVPN とサイト間の eBGP multihop EVPN をどちらも `update_source` で書く
- サイトは `labels.site`

**書けない / 誤読される** (a1 の FEEDBACK の番号):

- **(5) 本質**: `L2VNI.vteps` が平らなリストなので、サイト A の leaf とサイト B の leaf が並ぶと any-to-any のトンネルに読める。実際は leaf は自サイトの BGW の VIP とだけ、サイト間は Multi-Site の VIP どうしだけ
- **(11)**: サイト間の EVPN セッション (BGW ↔ BGW) と「このセッションが使う VTEP は Multi-Site の VIP の対」の対応が構文に出ない。update_source は lo0 なので、VTEP との結び付きは id の慣習頼り
- **(4)**: サイトの VIP と Multi-Site の VIP を区別する手段が VTEP の id の付け方 (`-vip` / `-msvip`) しかない
- **(6)**: L3VNI は `vteps` を持たないので (ADR-0014 D3)、L3VNI のサイト間の扱いを書く場所がない
- **(7)**: `VRF.route_targets` が 1 組なので、BGW での RT の付け替えを書けない
- **(9)**: BGW は VLAN のポートも SVI も持たないので ADR-0026 D5 の 10 の warning が出る (deferred.md の既知の論点)
- **(1)(2)(3)(10)**: role に BGW、link_role に DCI の推奨値がない。サイトをまたぐ VLAN を 1 エントリにまとめるか、など

## VNI stitching (サイト B で VNI 20100 に付け替え)

今の構文では書けない (VNI はトポロジー全体で一意。deferred.md 50 行目)。a2 も a3 も、同じブロードキャストドメインに L2VNI を 2 つ以上許す緩和 (ADR-0026 D5 の 4) が要る。a2 は fabric ごとに別の L2VNI エントリを許して `stitching.between_vnis` で対応づける形、a3 は `vni_stitching` の別の一覧にする形を、各ファイルの末尾にコメントで示した。

## 案の比較

| 観点 | a1 (今) | a2 (fabric) | a3 (scope + stitching) |
|---|---|---|---|
| 構文の追加量 | なし | 大 (新しい一覧 + L2VNI の `fabrics` / `stitching`) | 小 (VTEP に `scope`、L2VNI に `stitching`) |
| 段の表現 | × | ◎ fabric が実体 | △ scope から導く |
| ndl-viz との相性 | 誤読を招く | fabric を枠で描ける | 同じ scope を既定の線で |
| ADR-0022 の粒度 | OK | OK | △ 役割を書く境界 |
| VNI stitching への拡張 | 無理 | `between_vnis` で自然 | 別の一覧か拡張 |

## 推奨

**a2 (fabric のグループ) を Pass B の主案に**。(i)「fabric = フルメッシュの集合」は EVPN-VXLAN の運用者の概念と一致し、サイトや AS の境界に縛られない (DCI だけの fabric も書ける)。(ii) FEEDBACK の (4)(5)(11) に同時に効く。(iii) VNI stitching への拡張が構造的に自然で、ADR-0026 D5 の 4 の緩和も fabric の単位に閉じ込められる。a3 は加算が小さいが、scope の値域 (閉じるか開くか) が別の決定を呼び、L2VNI の stitching が役割寄りになって ADR-0022 の問い 5 に触れるおそれがある。

## network-tech-reviewer への技術的な疑問

1. anycast BGW の lo1 / lo2 の分け方は Arista / Cumulus でも同じ形か。1 本にまとめる機種では「2 つの VTEP を 2 つの scope で持つ」モデルがずれるかもしれない
2. L3VNI も BGW で付け替えが起こる。L3VNI には `vteps` がないので、L2VNI とそろえるか、L3VNI 専用にするか
3. BUM を ingress replication で運ぶとき、Multi-Site の VIP を共有する 2 台のどちらが受けるかを構文で区別できない (BUM の配送方式の先送りと重なる)
4. サイトごとに OSPF が分かれるなら、BGW の lo0 の到達性は DCI の eBGP で広告する必要がある (見本の underlay の設計)
5. 同じ ESI をサイトをまたいで使う構成は今回は扱わず、サイトごとの ES で書いた

## spec-architect への提案

1. 主案は a2 (`layer2.vxlan_fabrics`、L2VNI の `fabrics` / `stitching`)
2. L3VNI の stitching を Pass B の決め所に
3. VNI stitching のときだけ「1 つの VLAN が複数の L2VNI に入る」を許す (ADR-0026 D5 の 4 の緩和)
4. fabric が実体になれば、BGW の warning (ADR-0026 D5 の 10) を抑える規則が書けそう
5. role / link_role に BGW / DCI の推奨値を足すかは別の小さな決定
