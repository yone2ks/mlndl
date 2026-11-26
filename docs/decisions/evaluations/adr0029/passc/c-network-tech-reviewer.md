# ADR-0029 Pass C — network-tech-reviewer

Pass B のまとめの未決の 2 点 (分かれた所 5・6) と、見本 `valid_evpn_multisite.yaml` の設計、試し書き a1 の直し。

## 技術的な正しさ

- A1 と「ドメイン = フルメッシュ」、1 つの VTEP は 1 つのドメイン: ○。NX-OS の anycast BGW (lo1 = VIP、lo2 = Multi-Site の VIP) を 2 つの VTEP として書くのとかみ合う
- L3VNI のドメインとトンネルの対: 下の推奨で決める
- サイト間の EVPN と DCI の underlay: ○。a1 の DCI の underlay (直結の /31 の eBGP IPv4) と overlay (lo0 どうしの eBGP multihop EVPN) は NX-OS の Multi-Site の素直な最小形

## 業界の実装との対応

- NX-OS の Multi-Site: `evpn multisite border-gateway <id>`、`interface nve1` に `source-interface loopback1` (VIP) と `multisite border-gateway interface loopback2` (Multi-Site の VIP)、`vrf context tenant-a { vni 10900 }` + L3VNI 用の SVI (IP を持たない)。**BGW は tenant の VRF と L3VNI の SVI を設定するのが普通**
- Arista の EVPN Multi-Domain: `evpn multi-domain`、tenant の VRF と L3VNI の SVI も設定
- Cumulus は BGW の対応が薄い

## 分かれた所 6 — L3VNI のドメインとトンネルの対

**推奨: 同じ VRF の L2VNI のドメインの和集合**。

- 実機では L3VNI のトラフィックは「その VRF を扱うすべての VTEP のあいだ」で張られる (Symmetric IRB で送る側の VTEP が L3VNI でカプセル化し、受ける側がデカプセルして L3 で転送)。同じ VRF の L2VNI 群の VTEP の和集合と一致する
- 「VRF の L3 IF を持つ機器」で引く案は、L3VNI の SVI (IP を持たない) を MLNDL に書くかどうかで結果が変わる。書かないのが普通なので、BGW が落ちることがある
- NX-OS の BGW はほぼ必ず L3VNI の設定を持つので、BGW が入るのは正しい
- **どちらの案でも合わない構成**: BGW が L2 の中継だけで tenant の VRF を持たない構成 (まれ)。和集合の案では BGW が L3VNI に入るが、実機ではルーティングしない。書き分けられないので範囲外に記す

導き方: L3VNI のトンネルの対 = 同じ VRF の L2VNI ごとの `l2vni_tunnel_pairs` の和 (重複は畳む)。

## 分かれた所 5 — 検査の severity

| 検査 | 推奨 | 理由 |
|---|---|---|
| VTEP が 0 のドメイン | **error** | 宣言したが使っていない。意図があいまい |
| VTEP が 1 のドメイン | **出さない** | stretched や 1 つの DC で偽の警告になる |
| ドメインを書いた VTEP と書かない VTEP の混在 | **error** | 「書かない = 既定のドメイン」が別の明示のドメインと混じると意味があいまい |
| ドメインが 1 つだけ | **検査しない** | stretched の意図の明示に使える |
| サイト間の EVPN セッションとドメインの境界 | **info** | ADR-0010 の独立を保ちつつ読者に示せる。route server・トポロジー外の相手などで誤検知が出やすいので warning にしない |

## 見本 `valid_evpn_multisite.yaml` の設計

2 サイト、各サイトに spine 2・leaf 2・anycast BGW 2・サーバー 1。L2VNI 10100 (vlan-100) + L3VNI 10900 (vrf-tenant-a、Symmetric IRB)。DCI は直結の /31 が 2 本。

**アドレスの計画** (a1 をもとに整える):

| 用途 | サイト A | サイト B |
|---|---|---|
| spine の lo | 10.0.0.1, 10.0.0.2 | 10.0.1.1, 10.0.1.2 |
| leaf の lo | 10.0.0.11, 10.0.0.12 | 10.0.1.11, 10.0.1.12 |
| BGW の lo0 (PIP、EVPN) | 10.0.0.21, 10.0.0.22 | 10.0.1.21, 10.0.1.22 |
| BGW の lo1 (VIP、サイト内の VTEP、anycast) | 10.0.100.1 | 10.0.100.2 |
| BGW の lo2 (Multi-Site の VIP、サイト間の VTEP、anycast) | 10.0.200.1 | 10.0.200.2 |
| underlay の /31 | 10.1.0.0/24 | 10.2.0.0/24 |
| DCI の /31 | 10.3.0.0/31 (bgw1)、10.3.0.2/31 (bgw2) | — |
| SVI の anycast gateway | 192.168.100.1/24 (全 leaf で同じ) | 同左 |
| サーバー | 192.168.100.10 | 192.168.100.20 |

**AS**: サイト A = 65001、サイト B = 65002。サイト内の underlay は OSPF area 0、EVPN は iBGP (spine が RR)。DCI は eBGP (65001 ↔ 65002)。直結の underlay は IPv4 unicast、overlay は multihop の l2vpn_evpn。

**ドメイン**:

```yaml
layer2:
  overlay_domains:
    - {id: od-site-a, description: Site A intra-fabric}
    - {id: od-site-b, description: Site B intra-fabric}
    - {id: od-dci,    description: Multi-Site DCI}
  vteps:
    - {id: vtep-a-leaf1, sources: [a-leaf1-lo], overlay_domain: od-site-a}
    - {id: vtep-a-leaf2, sources: [a-leaf2-lo], overlay_domain: od-site-a}
    - {id: vtep-a-bgw-vip,   sources: [a-bgw1-lo1, a-bgw2-lo1], address: 10.0.100.1/32, overlay_domain: od-site-a}
    - {id: vtep-a-bgw-msvip, sources: [a-bgw1-lo2, a-bgw2-lo2], address: 10.0.200.1/32, overlay_domain: od-dci}
    # サイト B も同じ形
```

**BGP のセッション**: サイト内の underlay は OSPF (a1 の 16 本のまま)。サイト内の EVPN (spine が RR) は各サイト 8 本。DCI の underlay の eBGP IPv4 は 2 本 (bgw1 どうし、bgw2 どうし)。DCI の overlay の eBGP multihop EVPN は 2 本 (lo0 どうし)。

**tenant-a の BGP インスタンスは書かない**。Symmetric IRB では tenant-a の BGP のセッションは要らない (EVPN が経路を運ぶ)。VRF-lite で外に出すときだけ要る。

(まとめの注: Pass B で network-tech-reviewer は「tenant-a の BGP インスタンスを書く」としていた。Pass C で「書かない」に改めた)

**コメントに書く前提**:

1. DCI の underlay は BGW の lo0 (PIP) を広告する
2. MTU は MLNDL の対象外 (ADR-0020) だが、実機では DCI の経路上の全 IF で 1600 以上
3. BGW は L3VNI の設定 (tenant の VRF と IP のない SVI) を持つのが普通だが、MLNDL では書かない。L3VNI のトンネルの対は同じ VRF の L2VNI の和集合から導く
4. anycast BGW の lo1 / lo2 は 2 本に分ける (1 本の構成は範囲外)

**a1 の直し**: labels のキーを `fabric-role` に。`vrf-default` を宣言せず、BGP と L3 IF の `vrf: vrf-default` を消す。`vrf-tenant-a` の `route_targets.import` は `[65001:100, 65002:100]` のまま (両サイトの経路を受けるので妥当)。BGW に tenant-a の SVI は書かない (ADR-0026 D5 の 10 の warning は抑える決定)。

## 見落としやすい所

- **ドメインの定義に合わない配線**: 3 サイト以上で実際の DCI が hub-and-spoke なのに 3 つの VTEP に `od-dci` を付けると、構文はフルメッシュを主張する。validator は配線を見ない
- **Multi-Site の VIP と VIP のループバックを取り違えると EVPN の next-hop が壊れる**: どちらがサイト間用かは `overlay_domain` の id で初めて分かる。見本の VTEP の id を `vtep-*-bgw-vip` / `vtep-*-bgw-msvip` にする

## 推奨

1. L3VNI のドメインは同じ VRF の L2VNI のドメインの和集合で導く
2. 検査は「VTEP が 0 = error」「混在 = error」「VTEP が 1 = 出さない」「ドメインが 1 つ = 検査しない」「セッションとの照合 = info」
3. 見本は a1 をもとに、`overlay_domains` と VTEP の `overlay_domain:` の最小の差分で作る

## 自信がない点

1. L3VNI の和集合の案は、BGW が L2 の中継だけで tenant の VRF を持たない構成では BGW を余計に含める。範囲外に記すだけで十分と判断したが、別の ADR に上げる余地がある
2. DCI の underlay と overlay を 2 本の eBGP に分けた。1 本 (ipv4_unicast + l2vpn_evpn) にまとめる構成も多い
3. セッションとの照合の info の判定条件: route server の構成で誤検知が出る。見本 (直結の BGW の対) では出ない
