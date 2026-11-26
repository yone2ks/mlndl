# ADR-0029 Pass A — mlndl-linguist

議題: EVPN Multi-Site の命名と意味論。(1) overlay のドメインの名前、(2) BGW を関係で書くか、(3) VNI stitching の名前と向き。

## 1. overlay のドメインを表す語

「サイトの中では直接トンネルを張り、BGW で境を接する overlay の分け方の単位」の名前。今の `labels.site` (ADR-0017。注釈で参照ではない) と、「サイト」が物理の拠点とこのドメインの 2 つの意味になりうる。

| 案 | 直感性 | 多義性のなさ | 業界の慣用 | 内部の一貫性 | 総合 |
|---|---|---|---|---|---|
| `fabric` | A | B (SP / WAN の "fabric" とずれる) | A (NX-OS・NDFC・Apstra・CloudVision が fabric の単位で管理) | A | **A** |
| `site` | A | C (`labels.site` と衝突。拠点 ≠ ドメインの場合がある) | A (Cisco の EVPN Multi-Site の用語) | C (ADR-0017 と真っ向からぶつかる) | C |
| `domain` | B (何の domain か見えない) | C (broadcast / failure / routing / admin domain と衝突。L2VNI 自体が broadcast domain) | B | B | C |
| `overlay_domain` | A | A | B | B (ほかは 1 語の名前が中心) | B |
| `evpn_site` / `multisite` | A | A | A | D (方式名。ADR-0005 D4 補則の問い 4) | D |
| 新しい構成子なし (`labels.site` に兼ねさせる) | B | D (注釈に規範の意味を乗せる。ADR-0009 D1/D2) | — | D | D |

**推奨: `fabric`**

- `labels.site` を拠点 (物理)、`fabric` を overlay の 1 かたまり (論理) と棲み分ければ ADR-0017 を動かさずに済む。「大阪に 2 ファブリック」「東京と大阪で 1 ファブリック (stretched)」もある
- `labels.site` は注釈、`fabric` は規範 (なくすと BGW がどの境を守るか決まらない)。別の語にするのが ADR-0009 D1 の筋
- ADR-0028: 一覧は `layer2.fabrics`、参照キーは `fabric:`、プレフィックス `fabric-`

懸念: SONiC / P4 では ASIC の中の fabric を指すことがあるので、文書で「Clos / VXLAN overlay の 1 つの管理単位」と限定する。1 ファブリック = 1 拠点が大半なので、`labels.site` と `fabric` に同じ値を 2 回書く冗長は直交性の代償として受け入れる。

## 2. BGW を表す語

| 案 | 直感性 | 多義性のなさ | 業界の慣用 | 内部の一貫性 | 総合 |
|---|---|---|---|---|---|
| 1. 複数の fabric に面する VTEP (関係で表す) | B | A | A | **A** (ADR-0014 D1 と揃う) | **A** |
| 2. `role: border-gateway` を推奨語彙に (informative) | A | A | A | A (ADR-0003 の open-form) | **A** |
| 3. `is_border_gateway` のフラグ | A | B | B | C | C |
| 4. 専用の型 `border_gateways` | A | A | B | D | D |
| 5. `multisite_role: BGW` | A | A | A | D (方式名) | D |

**推奨: 案 1 と案 2 の併用**。BGW かどうかは「VTEP が面する fabric が 2 つ以上か」で機械的に判定する (方式中立)。`role: border-gateway` は人と ndl-viz のための目印で、validator は読まない。`bgw` は BGP と紛らわしいので値に使わない。

懸念: 「VTEP が複数の fabric に属する」か「fabric ごとに別の VTEP エントリ」かは Pass B の争点。言語的にはどちらも通る。

## 3. VNI stitching の関係の名前と向き

| 案 | 直感性 | 多義性のなさ | 業界の慣用 | 内部の一貫性 | 総合 |
|---|---|---|---|---|---|
| `stitches` | A | A | **A** (RFC 9135・NX-OS・NDFC の "VNI stitching") | B | **A** |
| `equivalent_to` | B | A | C | B | B |
| `translates_to` | B | C | B | D (ADR-0026 D3 で "translation" を避けた) | D |
| `maps_to` | A | B (広すぎ) | B | B | B |
| `bridges_to` | B | C (`layer2.bridges` と衝突) | B | D | D |
| `peered_with` | C | C (BGP の peer・MLAG のピアリンクと衝突) | — | D | D |

**推奨: `stitches`**。関係は対等なので向きのない `endpoints: [vni-a, vni-b]` (ADR-0006 の L1 リンクと同じ)。独立のエンティティなら `vni_stitches`。日本語話者には「縫う」の印象が強いので、リファレンスで「RFC 9135 の VNI stitching」と注記する。

## 4. 命名の観点からの骨格

```yaml
layer2:
  fabrics:
    - {id: fabric-tokyo, name: Tokyo EVPN Fabric}
    - {id: fabric-osaka, name: Osaka EVPN Fabric}
  vteps:
    - {id: vtep-tokyo-leaf12, sources: [tokyo-leaf1-lo, tokyo-leaf2-lo], address: 10.0.100.12/32, fabric: fabric-tokyo}
    - {id: vtep-tokyo-bgw,    sources: [tokyo-bgw1-lo, tokyo-bgw2-lo],  address: 10.0.100.21/32, fabrics: [fabric-tokyo]}
    - {id: vtep-tokyo-dci,    sources: [tokyo-bgw1-lo2, tokyo-bgw2-lo2], address: 10.0.200.21/32, fabrics: [fabric-tokyo, fabric-osaka]}
  vxlans:
    - {id: vni-10100-tokyo, type: l2vni, vni: 10100, fabric: fabric-tokyo, vlans: [vlan-100], vteps: [vtep-tokyo-leaf12, vtep-tokyo-bgw]}
    - {id: vni-20100-osaka, type: l2vni, vni: 20100, fabric: fabric-osaka, vlans: [vlan-100-osaka], vteps: [vtep-osaka-leaf12, vtep-osaka-bgw]}
  vni_stitches:
    - {id: stitch-tenant-a-l2, endpoints: [vni-10100-tokyo, vni-20100-osaka], via: vtep-tokyo-dci}
layer1:
  nodes:
    - {id: tokyo-bgw1, role: border-gateway, labels: {site: tokyo}}
```

**避けるべき名前**: `multisite_*` / `evpn_site` / `bgw_role` (方式名)、`site` をドメインに兼用、`domain` / `zone` (多重の衝突)、`translates_to` (ADR-0026 D3)、`bridges_to` (ADR-0018)、`is_bgw`、`vni_stitching: {from, to}` (向きのある表現)。

## Pass B の論点

1. 「VTEP が複数の fabric に属する」か「fabric ごとに別の VTEP エントリ」か。`fabric:` と `fabrics:` の併置は ADR-0028 D1 の単数 / 複数の使い分けに照らして揺れが残る
2. VNI の番号のトポロジー全体での一意性を fabric の中に緩めるか (deferred.md 50 行目)
3. `labels.site` と `fabric` の対応を検査するか (おそらくしない。文書で明示)
4. `role: border-gateway` を role-vocabulary に足すか、ndl-viz の描き方への影響
5. ADR-0026 D5 の 10 の warning (BGW にポートも SVI もない) を、DCI に面する VTEP なら抑える規則が自然に書けるか
6. `stitches` / `vni_stitches` の日本語での読みやすさ
