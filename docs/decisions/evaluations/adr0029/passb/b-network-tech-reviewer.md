# ADR-0029 Pass B — network-tech-reviewer

前提: Pass A の推奨モデル (ドメイン = 中でフルメッシュにトンネルを張る VTEP の集合、1 つの VTEP は 1 つのドメイン、DCI も 1 つのドメイン、BGW は 2 つのドメインに VTEP を 1 つずつ持つ)。これで今の EVPN Multi-Site の実装を過不足なく表せるかを確かめた。

## 技術的な正しさ (△)

関係の形としては方式中立で、NX-OS の anycast BGW・vPC BGW・RFC 9014・Arista の典型の構成・Juniper の seamless stitching (VXLAN-VXLAN) を、どれも「VTEP を 2 つ (サイト内と DCI)」で素直に書ける。段のある張り方もドメインで表せる。stretched fabric は「2 サイトの leaf を同じドメインに、`labels.site` は別の値」で破綻しない。3 サイト以上のフルメッシュの DCI は DCI のドメインの VTEP を増やすだけ。静的 VXLAN やハイパーバイザの TEP も、EVPN の語を構文に出さない限り同じドメインに載せてよい。

ただし 3 つの穴がある。

1. **1 本のループバックで両方を終端する構成** (Arista の Multi-Domain EVPN の一部、Juniper の一部、自作のハイパーバイザ VTEP)。同じ L3 IF が 2 つの VTEP エントリに現れる必要があり、ADR-0014 の「同じ L3 IF を 2 つの VTEP に書かない = error」に抵触する
2. **hub-and-spoke の DCI** (階層の Multi-Site、route server だけがハブ)。ドメインの定義が「中でフルメッシュ」なので、この形はモデルの外になる
3. **L3VNI のトンネルの範囲**。Pass A は結論を書いていない

## 業界の実装との対応

| 構成 | NX-OS | Arista EOS | Juniper |
|---|---|---|---|
| anycast BGW のサイト内 VTEP | `nve1 source loopback1` | `vxlan source-interface Loopback1` + `virtual vtep` | (seamless stitching) |
| サイト間の VTEP (Multi-Site の VIP) | `multisite border-gateway interface loopback100` | multi-domain / VXLAN-to-VXLAN gateway の 2 本目の source | EVPN-VXLAN ↔ EVPN-MPLS stitching |
| vPC BGW | vPC + `evpn multisite border-gateway` | MLAG + 共有の virtual vtep | — |
| DCI の underlay | eBGP で lo0 と lo100 を広告 | 同左 | 同左 |

どれも「2 本のループバック」が主流。例外 (1 本) は注記で逃げる。

## 見落としやすい所

- **試し書き a1 で DCI の underlay の経路交換が欠けて見える**。BGW の lo0 と Multi-Site の VIP が相手のサイトに届かないと、multihop の EVPN もサイト間のトンネルも成り立たない。再配布の方針は MLNDL の対象外なので、見本のコメントで「DCI の underlay は BGW のループバックを相手のサイトに広告する前提」と書く
- **a1 に tenant-a の BGP インスタンスがない**。Symmetric IRB で BGW が Type-5 を再広告するには、VRF ごとの BGP インスタンスが普通は要る。見本では書く
- **BGW のインターフェースの MTU**。1600 以上を推奨するベンダーが多い。インターフェースの MTU は MLNDL で未実装なので、見本ではコメントで注記
- 「1 台が 2 つのドメインに VTEP を 1 つずつ = BGW」のモデルは、1 本のループバックの構成を禁じる方向に働く

## 足りない所 (最小の追加)

1. **L3VNI のドメインの導き方を ADR に書く**。構文は足さない。`l3vni_tunnel_pairs` を「その L3VNI の VRF の L3 IF を持つ機器が終端する VTEP のうち、同じドメインに属する対」と定義する。BGW の 2 つの VTEP が L3VNI でも使われ、サイト内とサイト間で別の対が導かれる
2. **1 本のループバックで両方を終端する構成の逃げ道**: 「同じ L3 IF を 2 つの VTEP に書かない」を、「違うドメインの 2 つの VTEP に現れるなら warning」に緩める
3. **検査**: L2VNI が 2 つ以上のドメインに参加し、ドメインをまたぐ VTEP を持つ機器のあいだに l2vpn_evpn のセッションがないとき warning (RS 経由などで両端が BGW でない構成があるので error にしない)
4. **推奨プレフィックス**: `od-` が広く通じる
5. **`labels.site` とドメイン**: 検査しない。concepts.ja.md に「拠点 ≠ ドメイン」の例 (1 拠点に 2 ファブリック、stretched fabric) を載せる

## 多すぎる所

- `role: border-gateway`・`link_role: dci` を推奨語彙にするのは不要。関係から導けるので informative の範囲に留める
- 「ドメインに VTEP が 1 つ」の warning は不要。stretched や 1 つの DC で偽の警告になる。info か、出さない
- 「VTEP が複数のドメインに属せる」(linguist の Pass A 案) は却下
- a2 の L2VNI の `stitching` は Multi-Site には要らない。VNI stitching のときだけ (先送り)

## 推奨

- Pass A の推奨モデルを主案に採る。破綻は小さく、多くの実装を自然に書ける
- 書き方は **A2 (`layer2.overlay_domains` + members)** を推す。ドメインの name / description を置く場所があり、ADR-0018 の `bridges` と同じ流儀。A1 も技術的には等価だが、ドメインに属性を付けたいとき後から拡張しにくい
  - (まとめの注: A1 もドメインの一覧 `overlay_domains` を持つので、ドメインの name / description や将来の属性は A1 でも置ける。この理由は A1 と A2 の差にならない)
- 1 本のループバックの構成の逃げを、ADR-0014 の検査の緩和として入れる
- L3VNI は `vteps` を持たせず、VRF を経てドメインを導く。VNI stitching と hub-and-spoke は範囲外
- 見本 `valid_evpn_multisite.yaml` は 2 サイト・anycast BGW 2 台・L2VNI 1 + L3VNI 1・DCI は直結 (RS なし) で十分。(a) BGW のループバックを DCI の underlay に広告する前提、(b) tenant-a の BGP インスタンスも書く、(c) MTU は MLNDL の対象外だが実機では 1600 以上、(d) a1 の AS の設計 (65001 / 65002) はそのままでよい

## ユーザーに判断してもらう論点

1. 書き方: A1 か A2 か。推奨 A2
2. 名前: 推奨 `overlay_domains`
3. 1 本のループバックで 2 つのドメインに属する VTEP を許すか: 推奨「warning に緩めて許す」
4. `role: border-gateway` を推奨語彙に足すか: 推奨「足さない。関係から導く」
5. ndl-viz はドメインを枠で描き、同じドメインの VTEP の対だけトンネルの線を引く: 推奨「そうする」
6. hub-and-spoke / RS だけの DCI: 推奨「範囲外、別の ADR」
