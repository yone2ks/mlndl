# 先送りした項目

ADR で「今は決めない」とした項目を、**何が起きたら始めるか** (きっかけ) と一緒にまとめた一覧。

以前は先送りを「Phase 2 で」「Phase 3+ で」と書いていた。Phase 1 (L1) と Phase 2 (L2 / L3 / 制御プレーン) の実装が終わり、
「Phase 3+」は時期の決まらない先送り全般を指す札になっていたので、2026-11-07 に Phase の札をやめた ([ADR-0005](0005-mlndl-expressive-scope.md) D5 の改訂)。
ADR の本文に残る「Phase 2 で」「Phase 3+ で」は、この一覧の該当する行に読み替える。

- 範囲外と決めたもの (スタティックルート・ACL・NAT・BGP ポリシーなど。ADR-0005 D3-2・ADR-0010・ADR-0011) は載せない。範囲外は「書く場所を作らない」という決定であり、先送りではない
- 始めるときは、該当する ADR の Pass から進める (下書きがあるものは Pass B から)
- 項目を片付けたら、この一覧から消し、ADR の一覧 ([README.md](README.md)) に結果を残す

## 言語全体・ツール

| 項目 | 先送りした場所 | 始めるきっかけ |
|---|---|---|
| `broadcast_domain` / `blast_radius` の問い合わせ。参照の逆引き、VLAN の多段の到達もここで扱う | ADR-0005 D5、ADR-0013、drafts/0015 | 利用側のツール (ndl-viz など) が、トポロジーをたどる問い合わせを必要としたとき |
| 検査を外から足す仕組み (ValidationPlugin)。運用慣行の検査や `role` の書き間違いの検出 | ADR-0004 D-4、ADR-0003 | 利用側のツールが、mlndl のコアに入れない検査を足したくなったとき |
| RFC 8345 のエクスポーター | ADR-0001 D7 | RFC 8345 の形で受け取るツールとつなぐとき |
| 元のシステムの主キー (`meta.source_refs`) | ADR-0002 | NetBox などから MLNDL を作るアダプターを書くとき |

## L1

| 項目 | 先送りした場所 | 始めるきっかけ |
|---|---|---|
| `parent` (包含) と、箱ノード (VPC・pod・サイトなど) の置き場所。ADR-0005 D1 の「物理層は任意」への改定もここで決める | ADR-0009 D1、drafts/0008 | クラウド (VPC など) を書く必要が出たとき、またはサイト・pod などの箱に属性 (`cidr` など) を持たせたくなったとき。2026-11-07 の検討の結論は drafts/0008 の末尾 |
| クラウドの表現 (`location` / `provider`、subnet の扱い、VPC ピアリングなど) | drafts/0008 | 同上 |
| 障害軸の構造化 (`fault_domains:` など) | ADR-0009、`docs/label-vocabulary.md` | `blast_radius` の問い合わせを作るとき |
| `labels` を L1 ノード以外 (リンク・LAG・VLAN・VRF など) にも持たせる | drafts/0008 | ノード以外に分類を付けたい例が出たとき |
| `attaches_to` を複数にする (multi-homing) | ADR-0001 D4 | vSwitch / dvSwitch の設計 (drafts/0007) を進めるとき |
| インターフェース単位の MTU (L3 IF または L1 IF。何の MTU か・名前・両端の食い違いの検査)。L1 リンクの `mtu` は ADR-0020 でなくした | ADR-0020 D4、ADR-0011、ADR-0018 | OSPF の MTU 不一致・事業者網の MTU・RoCE などを検査したくなったとき |
| `link_speed` を数値 (bps) に直す関数と、エクスポーターの数値の出力 | ADR-0021 D4 | 速度を比べる検査や、速度で線の太さを変える表示が要るようになったとき |
| LAG のメンバーの速度がそろっているかの検査 | ADR-0021 | 上の数値への変換を足すとき |
| `link_speed` の `P` 以上の単位 | ADR-0021 D1 | 1 本のリンクが 1000T を超える速度が出たとき |
| ブレークアウト (100G → 4×25G の親子関係) | ADR-0005 D3-2 | ブレークアウトのあるトポロジーを書く必要が出たとき |
| 物理配置 (ラックの U 位置・キャビネット) | ADR-0005 D3-2 | ラックの中の位置まで要るとき。サイトとラックの所属は `labels` で書ける (ADR-0017) |
| 機器の中に L1 IF を書く糖衣 (ADR-0019) | 保留 (2026-11-05)。下書きは main にない | 利用者が再開を求めたとき |

## L2

| 項目 | 先送りした場所 | 始めるきっかけ |
|---|---|---|
| vNIC と vSwitch / dvSwitch (`layer2.bridges` の `type` / `nodes` / `uplinks`、VLAN との関係) | drafts/0007、ADR-0018 | ハイパーバイザの中の L2 を書く必要が出たとき |
| EVPN の advertise フラグ (`advertise-default-gw` / `advertise-svi-ip` / `advertise-pip`) | ADR-0005 D3-1 (「含む」と予告済み) | ADR-0005 の再設計 (drafts/0005v2) を始めるとき、または MLAG + Symmetric IRB の例で必要になったとき |
| Ethernet Segment の脚にサブ IF (`{subinterface:}`。論理 IF に直接 ESI を付ける構成) | ADR-0023 D3 | その構成を書く必要が出たとき。`members` はキー付きの形なので加算的に足せる |
| 機器ごとに書く L3 IF・サブ IF が、Ethernet Segment の脚の一部の機器にしかない (warning) | ADR-0023 D7 | routed の MLAG の片側だけに L3 IF を書く誤りを拾いたくなったとき |
| BUM の配送方式 (HER / PIM) | ADR-0005 D3-2 | 今は HER を暗黙に前提している。マルチキャストのアンダーレイを書くとき |
| L2 トンネル (EoGRE / L2TPv3 / OTV) | ADR-0005 D3-2 | その構成を書く必要が出たとき |
| Q-in-Q (`stag_vlan_id` / `ctag_vlan_id`) | ADR-0002 (名前だけ予約) | その構成を書く必要が出たとき |

## L3・制御プレーン

| 項目 | 先送りした場所 | 始めるきっかけ |
|---|---|---|
| ルーター ID と管理インターフェース | drafts/0016 (Pass A) | Pass B から再開する。ルーター ID の一意性の検査はこれを待っている |
| マルチアクセスの隣接 (3 拠点以上の広域イーサの OSPF / IS-IS、DR / DIS) | ADR-0010 D8、ADR-0017 D5-2、ADR-0018 | ADR-0018 の bridge の上に足す形で、次の ADR として始める |
| multihop のセッションが通る underlay の経路 (`carried_by` など) | ADR-0010 | `blast_radius` の問い合わせで、セッションがどのリンクに依存するかが要るとき |
| PIM / MPLS-LDP / Segment Routing | ADR-0005 D3-2 | その構成を書く必要が出たとき |
| QoS (RoCE などの AI 用途) | ADR-0005 D3-2 | 運用設定として範囲外。AI 向けのファブリックで要るときに範囲を見直す |
