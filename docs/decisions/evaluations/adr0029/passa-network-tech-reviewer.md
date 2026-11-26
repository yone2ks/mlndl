# ADR-0029 Pass A — network-tech-reviewer

議題: EVPN Multi-Site (VXLAN EVPN の BGW によるファブリック間接続) を MLNDL でどう書くか。
(この評価のとき、`valid_dc_campus_wan.yaml` はまだ `valid_multisite_wan.yaml` という名前だった)

## 1. EVPN Multi-Site の構成要素と動作

**Border Gateway (BGW)**。サイトの境界で L2/L3 ともに EVPN を中継する装置。実装形態:

- **Anycast BGW** (NX-OS 標準・RFC 9014)。同じサイトの 2〜6 台で共通の Multi-Site VIP を共有。サイト間トンネルはこの VIP 宛てに張る
- **vPC BGW** (NX-OS)。2 台の vPC ペアで 1 つの BGW として動く
- **位置**: 独立の BGW、border leaf 兼任、spine 兼任 (ベンダーごとに呼び名は違うが構造は同じ)

**BGW が持つ 2 つの VTEP**:

| 役割 | 例 | アドレス | 相手 |
|---|---|---|---|
| サイト内 VTEP | `loopback1` | 各 BGW 固有 | サイト内の leaf |
| サイト間 VTEP (Multi-Site VIP) | `loopback100` (anycast) | 同じサイトの BGW で共有 | 他サイトの BGW |

同じ BGW が 2 つの別のループバックを別の VTEP として終端する。サイト間は Multi-Site VIP どうしのフルメッシュ (または route server) のトンネルで、サイト内の leaf からサイト間へ直接トンネルは張らない (**2 段構造**)。

**EVPN セッション**:

- サイト内: leaf ↔ spine (RR)、update_source はループバック
- サイト間: BGW ↔ BGW の eBGP EVPN (直結かフルメッシュ)、または route server 経由。update_source は DCI underlay で届く BGW のループバック
- BGW は受けた Type-2/5 を **re-originate** する (RT の付け替え、next-hop を自分の Multi-Site VIP に、ESI をリセット)。Type-3 がサイト境界をまたがないので BUM が制御される

**DCI underlay**: サイト間の IP 到達性。BGW の Multi-Site VIP に全サイトから届く必要がある。普通は WAN 越しの eBGP (IPv4 unicast) と、その上に EVPN の AF を重ねる。

**L2 の BUM**: サイト内もサイト間も ingress replication が標準。DF election は BGW のあいだで動き、1 サイトの 1 台だけが BUM を外へ流す。

**L3VNI**: Type-5 を BGW が re-originate してサイト間に流す。VNI stitching を使うとサイト A の L3VNI 50001 をサイト B の 60001 に対応させられる (ベンダーごとに機能差あり)。

**Split horizon**: サイト間から受けた BUM をサイト内のほかの BGW に配らない。装置の設定で、構成図には出ない。

## 2. ADR-0022 の粒度

| 項目 | 載せるか | 理由 |
|---|---|---|
| どの機器が BGW か | 載せる | 読む人が「サイトの境界」を値から読む |
| サイト内 VTEP と Multi-Site VIP の区別 | 載せる | アドレスも相手も違う。ADR-0014 D5 の「1 ノードが複数の VTEP を終端する」場合 |
| BGW の所属サイト (EVPN ドメイン) | 載せる | どのサイト間トンネルが張られるかが決まる |
| VNI stitching の対応 | 載せる | 値から関係を読む情報 (deferred.md 50 行目) |
| サイト間 EVPN セッション | 載せる | routing_neighbors で書ける |
| DF election | 載せない | 装置に設定するだけ (問い 5) |
| split horizon / allowed-vni / re-origination のポリシー | 載せない | 同上 |
| Site ID (RFC 9014 の 16 bit) | 載せない | ドメインの id で代わる |
| advertise-pip / virtual-rmac | 載せない | ADR-0014 で範囲外 |

## 3. 今の MLNDL で書けること / 書けないこと

**書けること**:

- 各 BGW のサイト内 VTEP と Multi-Site VIP を `layer2.vteps` の別エントリ 2 つで書ける (ADR-0014 D5)
- サイト間 EVPN セッションは `routing_neighbors` の eBGP `[l2vpn_evpn]` で書ける
- サイトは `labels.site` (ADR-0017)

**書けない所 / 誤読される所**:

1. L2VNI の `vteps` にサイト内とサイト間の VTEP を並べると 2 段構造が消え、全 VTEP のフルメッシュと読める (dc1 の leaf ↔ dc2 の leaf のトンネルは実機では張らない)。ndl-viz も区別できない
2. L2VNI のどの VTEP がサイト内でどれがサイト間かを区別する構造がない。アドレスが anycast かは構文から読めない
3. サイト間 EVPN セッションの両端が BGW であることを検査しない
4. VNI stitching を書けない (VNI はトポロジー全体で一意)
5. BGW は VLAN のポートも SVI も持たないので、ADR-0026 D5 の 10 の warning が出る (deferred.md 54 行目)
6. re-origination での RT の付け替えは、VRF の `route_targets` が 1 組なので書けない (deferred.md 53 行目)
7. 同じ BGW のサイト内 VTEP とサイト間 VTEP の対の関係は暗黙 (`sources` のノードの一致から導けるだけ)

## 4. 最小の追加案と検査

**案 A: EVPN ドメインを 1 つのエンティティに**

```yaml
layer2:
  evpn_domains:                   # サイトや箱ではなく、EVPN の制御プレーンの境界
    - id: evpn-dc1
      bgws: [dc1-bgw1, dc1-bgw2]
    - id: evpn-dc2
      bgws: [dc2-bgw1, dc2-bgw2]
  vteps:
    - {id: vtep-dc1-bgw-msite, sources: [dc1-bgw1-lo100, dc1-bgw2-lo100], address: 10.100.0.1/32, domain: evpn-dc1}
    # domain を付けた VTEP はドメイン間 VTEP。付けない VTEP は従来どおり (サイト内)
  vxlans:
    - id: vni-10100
      type: l2vni
      vni: 10100
      vlans: [vlan-100]
      vteps_by_domain:
        evpn-dc1: [vtep-dc1-leaf1-leaf2, vtep-dc1-bgw-msite]
        evpn-dc2: [vtep-dc2-leaf1-leaf2, vtep-dc2-bgw-msite]
```

書かないもの: site-id、DF、split horizon、allowed-vni、re-origination のポリシー。VNI stitching は別 ADR。

**検査の候補**:

| # | 検査 | Severity |
|---|---|---|
| 1 | `evpn_domains.bgws` がノードに実在 (Ref) | error |
| 2 | 各ドメインに BGW が 1 台以上 | error |
| 3 | 1 ノードが 2 つのドメインの BGW にならない | error |
| 4 | VTEP の `domain` のドメインの BGW と、その VTEP の `sources` のノードが一致 | error |
| 5 | `vteps_by_domain` の各 VTEP の `domain` がキーと一致 | error |
| 6 | サイト間の EVPN セッションの両端が別ドメインの BGW | error |
| 7 | L2VNI が 2 つ以上のドメインに参加するのに、どちらかにドメイン間 VTEP がない | error |
| 8 | ドメイン間 VTEP の `sources` が 1 つ | warning |
| 9 | 全 VTEP が同じドメイン (Multi-Site ではない) | info |
| 10 | L3VNI のドメイン間の表現 | 将来 |

## 5. 推奨と Pass B の論点

**推奨**:

- 少なくとも「ドメイン」と「ドメイン間 VTEP の区別」は要る。平らな `vteps` だけでは 2 段構造を表せず、ndl-viz で誤って描かれる
- `labels.site` とは別の概念にする。サイトは物理の場所 (ADR-0017)、EVPN ドメインは制御プレーンの単位。1 サイトに複数のファブリックもありうる
- VNI stitching、L2VNI の RT、re-origination のポリシーは今回も範囲外
- BGW の `role` は推奨語彙に足すか自由文字列のままか要検討 (ADR-0003)
- 本物の Multi-Site の見本は別の fixture にする

**Pass B の論点**:

1. ドメインの名前: `evpn_domains` / `fabrics` / `evpn_fabrics`。`labels.site` との関係
2. VTEP に `domain` を持たせるか、L2VNI 側で分けるか、両方か (直交性と繰り返し)
3. `vteps` を残して `vteps_by_domain` を加算で足せるか (ADR-0027)
4. ドメイン間 EVPN セッション: `routing_neighbors` + 検査 6 で足りるか、BGW 間フルメッシュの糖衣が要るか (3 サイト以上で本数が増える)
5. anycast BGW・vPC BGW・独立 BGW の 3 つを 1 つの構文で書けるか
6. L3VNI のドメイン間: L2VNI と同じ構造が要るか
7. VNI stitching をどこで線引きして先送りするか
8. BGW の SVI なしの warning をドメインの構造で抑えられるか
9. dc-campus への改名は妥当。Multi-Site は別の fixture
10. ndl-viz: サイト内とサイト間のトンネルを別に描くか、ドメインを枠で描くか
