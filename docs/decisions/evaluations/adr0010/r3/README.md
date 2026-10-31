# ADR-0010 r3 Pass B 試し書き (2026-11-01)

[ADR-0010 r3 (Draft)](../../../drafts/0010-control-plane-separation.md) の Pass B
(5 エージェント再レビュー) のための試し書き。r2 から r3 への変更点
(`process` → `instance`、トポロジー外の端点 `address` + `local_as`、
unnumbered はアドレスを持たない L3 IF を update_source で指す、
`attaches_to` のキーに `{lag:}` が加わる、`router_id` は ADR-0016 に委ねる) を
実例で確かめる。

いずれも `tests/fixtures/` の対象外で、`python -m mlndl validate` はまだ通らない
(スキーマ側に `control_plane` が未実装)。L1 / L2 / L3 は参照整合性だけが保てる
最小構成に留め、焦点は `control_plane.*` の記述。既存の `d8-r3/` は編集しない。

## ファイル一覧

| ファイル | ケース | 検証の焦点 |
|---|---|---|
| `C1_split_underlay_overlay.yaml` | spine1–leaf1 の underlay (/31 single-hop eBGP) と overlay (loopback 間 eBGP multihop) を 2 本に分ける | r2 の `process:` が `instance:` になったこと、同じノード対の 2 本目の ID 接尾辞 (D7) |
| `C2_unnumbered_multi_af.yaml` | FRR 定番 1 本 eBGP unnumbered セッションで `ipv4_unicast` + `l2vpn_evpn` を同時に運ぶ | unnumbered の表現が「アドレスを持たない L3 IF」に変わった (D3)。link-local を形だけ書かなくてよい |
| `C4_vrf_lite_external.yaml` | border leaf6 ↔ wan-rtr の VRF-lite (VRF ごとに 1 インスタンス、2 セッション) | `instance:` が同じ type で複数エントリあるときの必須参照であること (D3・D6) |
| `C5_ibgp_over_svi.yaml` | vPC ペア leaf3/leaf4 間の iBGP を Vlan3999 の SVI 上に張る | `attaches_to: {lag:}` が使えること (r3 で初めて追加された) |
| `C6_external_peer.yaml` | トポロジー外の ISP (IP と AS だけ分かる) との eBGP | 端点に `address` + `local_as` を書く形 (D3・D4)。擬似ノードが不要になった |
| `C6b_external_peer_cable.yaml` | ISP の PE までのケーブルを layer1 に書き、相手の L3 IF を 1 つ書いて `{node, update_source}` で指す | D3 の表「相手の機器はトポロジー内」の派生形。C6 との使い分けを示す |
| `R_extended_control_plane.yaml` | `examples/eveng-evpn-lab-extended.yaml` の `routing_adjacencies` + `protocols` 節を r3 の `control_plane` に書き直した断片 | 元の 159 行 (routing_adjacencies 36 + protocols 123) が r3 でどれだけ減るか |

## 各ケースで分かったこと

### C1 (underlay + overlay を 2 セッションで)

- 「同じノード対の 2 本目」は D7 の推奨どおり `-evpn-` のような意味の分かる語を
  入れるほうが `-2` よりずっと読みやすい。
- `type: bgp` のエントリが 1 つしかなければ `instance:` は省略可だが、Pass B 的に
  読み手が「どのインスタンスか」を即座に判断できるので省略しないほうがよい、と
  感じた。D7 の「省略可」記述は、明示を**推奨**とまで踏み込んでよいかもしれない。
- Consequences の「エクスポーターが辺に載せる値」はすべて参照だけで決まる
  (両端 IP = `update_source` → L3 IF.ip、AS = `bgp-default.nodes[].local_as`、
  eBGP/iBGP は AS 比較、AF はセッション、VRF はインスタンスから。推定なし)。

### C2 (unnumbered)

- r2 で example-author が指摘した「link-local を形だけ書く」が解消。L3 IF に `ip`
  も `ipv6` も書かない状態が自然に通る (= 現行スキーマでも vlan-3001 の transit SVI
  と同じ形)。
- ただし「アドレスを持たない L3 IF」はエクスポーターから見ると
  (ADR-0011 D11 の分類で) `l1_interface` カテゴリの unattached でも unnumbered
  でもなく、「ip も ipv6 も空の普通の L3 IF」になる。unnumbered かどうかは
  **BGP セッション側の文脈**で初めて決まる (= update_source がアドレスなし IF を
  指すこと) ので、ndl-viz 側で L3 IF 単体を見ても unnumbered と分からない。
  r3 Consequences の「IF の名前と unnumbered を出す」はセッション視点では正しい
  が、L3 IF 単体の表示ではこの判定が難しい。

### C4 (VRF-lite)

- 同じノード対で VRF が違うだけの 2 セッションを並べたとき、`instance:` 必須の
  規則 (D3) がとても自然に働く。ID の接尾辞 `-tenant-a` / `-tenant-b` も D7 の
  例と一致。
- `router_id` を省いても何も失われない (ADR-0016 に委ねる、D5)。r2 の試し書きで
  router_id を全ノードに書いていたのが Pass B で冗長に感じた理由はこれだと確認
  できた。

### C5 (vPC iBGP + attaches_to: {lag:})

- r3 で `{lag:}` が加わり、d8-r3 の C5 で feedback していた「指す先がない」が
  解消した。これは明確な改善。
- 一方 **1 つの悩み**: MLNDL の LACP LAG は「1 ノード 1 LAG」なので、peer-link の
  LAG は `lag-leaf3-po1` と `lag-leaf4-po1` の 2 つになる。`attaches_to: {lag:}`
  にはどちらを書いても等価のはずだが、仕様に明文化がない。
  → 「ノード側は問わない。両端のどちらかの LAG を指せばよい」を D3 に 1 行
  足すと迷いが減る (後述の feedback)。

### C6 / C6b (トポロジー外ピア)

- **C6 (address + local_as)**: 擬似ノード・擬似 IF が消え、記述が短くなった。
  ISP の `role: isp`、`implementation: physical` といった推測で書くしかなかった
  行がすっきり消える。
- **C6b (ケーブルを書く)**: 相手の L3 IF 1 つで足りることが D3 の表に明記
  されたので迷いが少ない。r2 の試し書きでは「どこまで書くべきか」が分からず
  冗長になりがちだった。
- 使い分けは「ケーブルの物理経路まで記述に含めたいか」で明快に分かれる。
  **ただし C6 で `border1-e1-1` の L1 IF だけがあり、対向を書かない (link が
  生成できない)** 状態は少し不自然。「対向のない L1 IF」が許されるかは、現行
  スキーマだと許容されているが、将来 L1 の整合性検査を厳しくすると詰まる
  可能性がある (後述 feedback)。

### R_extended_control_plane (元ファイル書き直し)

- 元の `routing_adjacencies` 36 行 + `protocols` 123 行 = **159 行**が、
  r3 の `control_plane` では **約 55 行** (本ファイル中の `control_plane:` 配下
  の中身) に収まった。約 65% の削減。
- 元ファイルの F4 (vPC ペアでの AS 矛盾) は、r3 では bgp-default.nodes に
  `leaf3: 65034` と `leaf4: 65034` を 1 回ずつ書くだけになり、矛盾の表現自体が
  不可能になった (= 構造的に F4 を排除できている)。
- 元の `protocols.bgp` 配下に書かれていた `allowas-in なしでは受けない` ような
  実装上の注意書きは、r3 では AS 設計に移管され、1 ノードが複数の AS を持たない
  構造によって自然に表現できる。

## エクスポーターの辺の値がすべて参照で決まるかの確認

r3 Consequences の表の値を、各ケースで参照だけでたどれるか確認した
(推定なしで決まるか)。

| ケース | 両端 IP | 両端 AS | eBGP/iBGP | AF | VRF | attaches_to |
|---|---|---|---|---|---|---|
| C1 (underlay) | ○ update_source → ip | ○ bgp-default.nodes | ○ AS 比較 | ○ セッション | ○ default | ○ {link:} |
| C1 (overlay)  | ○ update_source → ip | ○ bgp-default.nodes | ○ AS 比較 | ○ セッション | ○ default | — multihop は書かない |
| C2 (unnumbered) | ✗ ip/ipv6 なし → 出さない | ○ | ○ | ○ | ○ | ○ |
| C4 | ○ | ○ インスタンスごと | ○ | ○ | ○ テナント | ○ |
| C5 | ○ SVI の ip | ○ | ○ (65034=65034→iBGP) | ○ | ○ | ○ {lag:} |
| C6 | 片側 update_source → ip、相手は address | 片側 nodes、相手は端点の local_as | ○ | ○ | ○ | — ケーブルなし |
| C6b | ○ | ○ 両端とも nodes | ○ | ○ | ○ | ○ {link:} |

すべて推定なしで決まる (C2 の両端 IP は原理的に書かれないので「出さない」が
正しい挙動)。r3 の記述モデルは Consequences の約束を果たしている、と判断できる。

## 行数・書きやすさの比較

| 項目 | 元 (extended) | r3 書き直し | 変化 |
|---|---|---|---|
| 制御プレーンの行数 (control plane section) | 159 行 | 約 55 行 | **-65%** |
| セッションを書く場所 | 2 箇所 (routing_adjacencies + protocols) | 1 箇所 (routing_neighbors) | 一元化 |
| F4 を書けてしまうか | 書ける (= 矛盾を温存) | 書けない (構造的に排除) | 改善 |
| vPC 間 iBGP の attaches_to | 書けない (peer-link は 2 本) | `{lag:}` で書ける | 改善 |
| ISP など外部ピア | 擬似ノード + 擬似 IF 必須 | `address` + `local_as` で可 | 改善 |
| router_id の書き場所 | 各ノードに毎回 | ADR-0016 に委ねて省略可 | 簡潔化 |

## 書きにくかった点・r3 の記述との食い違い

(詳細は親エージェントへの最終報告側に書く)
