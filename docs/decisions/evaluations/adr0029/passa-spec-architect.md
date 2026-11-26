# ADR-0029 Pass A — mlndl-spec-architect

議題: EVPN Multi-Site を MLNDL でどう書くか。

## 1. スコープの判定 (ADR-0005 D4 と補則の問い)

| 要素 | 判定 | 根拠 |
|---|---|---|
| BGW (ノード) | スコープ内 (今も書ける) | 普通の機器。anycast VTEP は ADR-0014 D6 の Multi-Site BGW の行の書き方。試し書き `evaluations/adr0014/neutral/05_multisite_bgw_anycast.yaml` |
| サイト間の overlay のセッション (BGW どうしの multihop eBGP l2vpn_evpn) | スコープ内 (今も書ける) | `routing_neighbors` の bgp。両端の update_source がループバックなので multihop。試し書き `evaluations/adr0010/d8-r3/C7_multisite_bgw.yaml` |
| **トンネルのドメイン** (leaf はサイト内の VTEP と BGW だけ、BGW どうしがサイト間) | **スコープ内だが今の構文で書けない** (中心の論点) | D4 の軸「意味境界」「blast_radius」が Yes。ADR-0022 の問い 5 も Yes (「leaf は自サイトの BGW 止まり」は構成図が示す関係) |
| VNI stitching | Pass B で結論 | 付け替えの番号は「装置に設定する値」寄り。一方、サイトごとの別の番号空間 (RFC 8365 §5.1.1) は意味境界 |
| DCI underlay | スコープ内 (今も書ける) | 普通の L1 リンク + L3 IF + OSPF / IS-IS / eBGP。ADR-0017 |
| route server | スコープ内 (今も書ける) | `role: route-server` のノード (open-form)。eBGP の RS はクライアントの指定なしで書ける |

## 2. 今の構文で書けるところ / 書けないところ

**書ける**: 各サイトのファブリック (leaf・spine・BGW・anycast VTEP)、BGW どうしの DCI の eBGP、BGW のサイト内 VTEP と対外 anycast VTEP の二枚持ち、DCI underlay。

**書けない**: L2VNI (または L3VNI) について「leaf1 は dc1 の BGW の VTEP とだけトンネルを張り、dc2 の leaf とは張らない」というトンネルの届く範囲。`layer2.vxlans[].vteps` は平らなリスト (`src/mlndl/schema/layer2.py` 173 行)、`derive.l2vni_participants` は全 VTEP の sources の和集合 (`src/mlndl/derive.py` 228-238 行) なので、全 VTEP のフルメッシュと読める。ndl-viz もそう描く。

### 構文案

**案 A: VTEP に `reaches` (届く相手の VTEP)**

```yaml
vteps:
  - {id: vtep-dc1-bgw-dci, sources: [dc1-bgw1-lo2, dc1-bgw2-lo2], address: 10.1.9.2/32, reaches: [vtep-dc2-bgw-dci]}
```

方式名は入らないが、VTEP × VTEP の組を手で書くので記述量が爆発する。ADR-0023 の「関係は id から導く」流儀にも逆行する。

**案 B: L2VNI の `vteps` を構造化する**

```yaml
vteps:
  - {scope: fabric-dc1, members: [vtep-dc1-leaf1, vtep-dc1-leaf2, vtep-dc1-bgw-site]}
  - {scope: fabric-dc2, members: [vtep-dc2-leaf3, vtep-dc2-leaf4, vtep-dc2-bgw-site]}
  - {scope: dci,        members: [vtep-dc1-bgw-dci, vtep-dc2-bgw-dci]}
```

`fabric` / `dci` を値の語にすると事実上の normative token になる。型は `list[str | VtepScope]` の加算。

**案 C: VXLAN のドメインを独立のエンティティに (推奨候補)**

```yaml
layer2:
  vxlan_domains:
    - {id: vxd-dc1, members: [vtep-dc1-leaf1, vtep-dc1-leaf2, vtep-dc1-bgw-site]}
    - {id: vxd-dc2, members: [vtep-dc2-leaf3, vtep-dc2-leaf4, vtep-dc2-bgw-site]}
    - {id: vxd-dci, members: [vtep-dc1-bgw-dci, vtep-dc2-bgw-dci]}
  vxlans:
    - {id: vni-10100, type: l2vni, vni: 10100, vlans: [vlan-100], vteps: [...], domains: [vxd-dc1, vxd-dc2, vxd-dci]}
```

- ADR-0005 D2-1 (エンティティは箱、関係は参照)、ADR-0018 の bridges と同じ流儀、ADR-0014 D1 (方式名を書かない) に沿う
- derive: L2VNI の中で同じドメインに入る VTEP どうしだけをトンネルの対にする
- validator: ドメインの members は L2VNI の `vteps` の部分集合、members は 1 つ以上、1 台が同じ L2VNI の 2 つのドメインに出るのは BGW だけ (info)、members が 1 つのドメインは warning
- 互換: 加算。`domains` を書かなければ今までどおり 1 つのドメイン
- VNI stitching を後でドメインに足せる余地が残る

**案 D: セッションから導く**: 構文は増えないが、RR の構成では leaf どうしの直接のセッションがなく、BGP のセッション網からトンネル網を推論するのは図を読む人がしない計算。不採用寄り。

## 3. `labels.site` を意味に使ってよいか

**使うべきでない**。

1. ADR-0009 D1 で labels は Classification。derive の入力にすると、ユーザーが決めるキーを mlndl のコアが前提にすることになる (ADR-0009 D3 に反する)
2. ADR-0017 D1 で `labels.site` は「書かなくても valid」。書き忘れで到達性の意味が変わるのは困る
3. BGW は自サイトのファブリックと DCI の両方に属するが、`labels.site` は 1 つの値

サイト・ファブリック・トンネルのドメインは一致するとは限らない (1 サイトに複数のファブリック、1 ファブリックが複数サイト) ので、別の構成子で書く。

## 4. 推奨と Pass B の論点

**推奨 (第一歩)**:

- 構文: 案 C (`layer2.vxlan_domains`) を推奨候補として Pass B へ
- 見本: 今の fixture を `valid_dc_campus_wan.yaml` に改名し、本物の Multi-Site の見本 `valid_evpn_multisite.yaml` を別に足す (サイトごとに anycast BGW 2 台、サイト間は multihop eBGP l2vpn_evpn、L2VNI 1 + L3VNI 1)
- スコープ: VNI stitching とファブリックごとの VNI の使い回しは今回扱わない (deferred.md 50 行目のまま)。全サイトで同じ VNI 番号の構成だけを対象に

**Pass B の論点**:

1. 案 B と案 C の比較 (L2VNI の中に畳むか、外に出すか。ADR-0014 D4 で L2VNI の `members` を VTEP に外出しした方針との整合)
2. BGW の anycast VTEP を案 C のドメインで指せるか (試し書き)
3. route server 経由の DCI の eBGP を書けるか (RS を端点にして 2 本)
4. 案 C の検査と severity
5. ADR-0026 D4 の `l2vni_participants` の意味: 参加機器は変えず、トンネルの対をドメインごとに分ける。`l2vni_tunnel_pairs` のような関数を新設
6. `labels.site` と `vxlan_domains` の関係を concepts.ja.md に書く
7. `domains` を書かないときの暗黙のドメインの扱い (今の 5 本の fixture は書き換えなし。エクスポーターが暗黙のドメインを出すか)

## 参照したファイル

- src/mlndl/schema/layer2.py 123-203 行、src/mlndl/derive.py 228-264 行
- docs/decisions/0014-vteps.md D1・D3・D6、0026-l2vni-vlans.md D1・D4、0010 D3・D7、0017 D1・D5、0022 D1、0005 D4 補則、deferred.md 50・53・54 行目
- docs/decisions/evaluations/adr0014/neutral/05_multisite_bgw_anycast.yaml
- docs/decisions/evaluations/adr0010/d8-r3/C7_multisite_bgw.yaml
