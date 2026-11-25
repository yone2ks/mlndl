# ADR-0029 Pass A — mlndl-dsl-designer

議題: EVPN Multi-Site を MLNDL でどう書くか。核心は、L2VNI の `vteps` が全 VTEP を平らに並べるので、サイトをまたぐ L2VNI に全サイトの VTEP を並べると、leaf どうしがサイトをまたいで直接トンネルを張るフルメッシュに読めること。Multi-Site のトンネルは段の構造 (サイト内の leaf ↔ BGW、BGW ↔ BGW) で、この段を書く構文がない。

## 既存の IaC / モデルとの比較

- **RFC 8345 の `network` + `supporting-network`**: Multi-Site は「サイトの overlay」と「DCI の overlay」の 2 つの network を BGW がつなぐ段の構造として素直に書ける。MLNDL は同じ VXLAN overlay に複数のドメインがあることを書けない
- **Istio のマルチクラスタの east-west gateway**: クラスタ内向けの gateway とクラスタ間の gateway を別に定義する。BGW のサイト内 VTEP と DCI 向け VTEP を別エントリに書くのと同じ形
- **Terraform の provider**: ドメインを独立のリソースにし、各リソースがどのドメインに属するかを指す。案 (a) に近い
- **Kubernetes の MultiClusterService (Submariner)**: L2VNI = Service、overlay のドメイン = クラスタと読める

RFC 8345 の階層そのものは採らないが、「同じ層の中で VTEP を分ける概念」を足しても階層の導入にはならない。

## 案の比較

### (a) `layer2.overlay_domains` + VTEP の `domain:` (推奨)

VTEP ごとにドメインが 1 つに決まる。L2VNI の `vteps` は平らなまま。BGW は「サイト内の VTEP」(ドメイン = そのサイト) と「DCI 向けの VTEP」(ドメイン = DCI) を別エントリで持つ (ADR-0014 D6 と同じ考え方)。

- 直交性: VTEP の属性なので同じ情報を 2 か所に書かない
- Ref: `domain: Annotated[str | None, Ref("layer2.overlay_domains")]`。汎用の参照検査で済む
- 互換: `domain` を書かなければ全 VTEP が暗黙の 1 つのドメイン。今の見本を書き換えずに済み、加算の変更

### (b) L2VNI の `vteps` を `[{domain, vteps}]` に

- 複数の L2VNI が同じ分け方を共有すると、VNI ごとに同じ分け方を繰り返す
- ドメインの name / description を置く場所がない
- 今の `vteps: [a, b]` と共存するには Union 型 (`list[str] | list[DomainGroup]`) が要り、直感的でない

### (c) EVPN のセッション (eBGP の両端) から導く

- 構文を足さないのが利点。ADR-0010 の「通り道は update_source から導く」と筋は通る
- 致命的: データプレーンが制御プレーンに依存する。制御プレーンを書かない見本で Multi-Site を書けない。EVPN 以外の VXLAN を書けない。推移閉包で導出が複雑。「書かれた情報だけを使い、推定で埋めない」に反する

### (d) `labels.site` から導く

- ADR-0009 D3・ADR-0017 に反する。labels は検査しない注釈で参照ではない。BGW の VTEP を特別に扱う手段もない

### (e) VTEP に `tier: site-local | multi-site`

- 方式名を構文に入れる (ADR-0014 D1・ADR-0005 D4 補則の問い 4)。却下

### (f) L2VNI に `stitched_by: [<BGW の VTEP>]`

- BGW の役割を言語に埋める。3 サイト以上・三角形の DCI・hub-and-spoke などに追随しない

## 参照のモデル

(a) は VTEP → ドメインの片方向の参照。id はトポロジー全体で一意 (ADR-0002 D5)。推奨プレフィックス `od-` か `overlay-` を ADR-0002 D7 に足す。L2VNI からドメインは直接指さず、VTEP を経て導く (ADR-0026 D1 と同じ片方向)。導出は `l2vni_overlay_domains(topology)` で、VNI ごとにドメインごとの参加 VTEP を返す。

## 型と制約

- `OverlayDomain(id, labels?, description?)`、`Vtep.domain: Annotated[str | None, Ref("layer2.overlay_domains")]`。Union 型は入れない
- 未定義のドメインは汎用の Ref の検査 (ADR-0015)
- validator: 2 つ以上のドメインにまたがる L2VNI で、各ドメインに「ほかのドメインの VTEP と同じ機器を sources に持つ VTEP」(= ドメインをまたぐ BGW) があるか。なければ warning
- ドメインの意味づけ (サイト = ドメインとは限らない) は informative

## VNI stitching

サイトごとに違う VNI 番号を使う構成は、今の「VNI はトポロジー全体で一意」と衝突する。

1. **先送り (推奨)**。deferred.md 50 行目のまま。Multi-Site の見本は VNI 番号を全サイト共通で書く
2. 書くなら、VNI の一意性を「同じドメインの中」に緩める (1.x で許す「検査を緩める」の範囲)。ほかの検査への影響は Pass B で

## 推奨

(a) 案。`layer2.overlay_domains` と VTEP の任意のフィールド `domain:` を加算で足す。BGW はサイト内の VTEP と DCI 向けの VTEP を別エントリで書き、段の構造は「1 台が 2 つのドメインの VTEP を持つこと」で表す。方式名 (BGW / anycast / site / fabric) を言語に入れない。VNI stitching は先送り。

```yaml
layer2:
  overlay_domains:
    - {id: od-dc1-fabric, description: "DC1 fabric overlay"}
    - {id: od-dc2-fabric}
    - {id: od-dci,        description: "Multi-Site DCI overlay"}
  vteps:
    - {id: vtep-dc1-leaf12,  sources: [dc1-leaf1-lo, dc1-leaf2-lo], address: 10.1.100.12/32, domain: od-dc1-fabric}
    - {id: vtep-dc1-bgw,     sources: [dc1-bgw1-lo,  dc1-bgw2-lo ], address: 10.1.100.21/32, domain: od-dc1-fabric}
    - {id: vtep-dc1-bgw-dci, sources: [dc1-bgw1-lo2, dc1-bgw2-lo2], address: 203.0.113.1/32, domain: od-dci}
    - {id: vtep-dc2-leaf12,  sources: [dc2-leaf1-lo, dc2-leaf2-lo], address: 10.2.100.12/32, domain: od-dc2-fabric}
    - {id: vtep-dc2-bgw,     sources: [dc2-bgw1-lo,  dc2-bgw2-lo ], address: 10.2.100.21/32, domain: od-dc2-fabric}
    - {id: vtep-dc2-bgw-dci, sources: [dc2-bgw1-lo2, dc2-bgw2-lo2], address: 203.0.113.2/32, domain: od-dci}
  vxlans:
    - id: vni-10100
      type: l2vni
      vni: 10100
      vlans: [vlan-100]
      vteps: [vtep-dc1-leaf12, vtep-dc1-bgw, vtep-dc1-bgw-dci,
              vtep-dc2-leaf12, vtep-dc2-bgw, vtep-dc2-bgw-dci]
```

## Pass B の論点

1. `domain:` を任意 (省略時は暗黙の 1 つ) にしてよいか。ドメインが 1 つなら `overlay_domains:` を書かせない形を保てるか
2. 1 つの VTEP が複数のドメインに属せるか。推奨は 1 対 1 で、ドメインをまたぐ機器は VTEP を 2 エントリ書く
3. BGW の VTEP を特別に扱わず、「2 つのドメインに同じ機器が VTEP を持つ」ことから段の構造を導けるか
4. プレフィックス (`od-` / `overlay-`) とキー名 (`domain` は汎用的すぎないか。`overlay_domain` / `tunnel_domain`)
5. ドメインに `labels` と `description` 以外を持たせるか (方式名は入れない)
6. エクスポーター: VTEP をドメインごとに compound node でまとめるか、属性に出すだけか
7. 「2 つのドメインにまたがる L2VNI に、ドメインをまたぐ VTEP がない」を warning か error か
8. VNI stitching の先送りの記録、または「ドメインの中で一意」に緩めるか
9. ドメインから導いた段の構造と、l2vpn_evpn のセッションの連結成分が食い違うとき検査するか
10. 今の見本が変更なしで valid のままかを実測
11. `labels.site` と `overlay_domains` の責務の分離 (1 対 1 ではない) を concepts.ja.md で説明できるか

## その後への波及

- マルチアクセスの OSPF / IS-IS (deferred.md) で「同じ bridge・トンネルのドメインを共有する複数ノード」の形が出る。同じ概念にそろえられるかを確かめる
- BUM の配送方式がドメインごとに変わるなら、ドメインの属性に置けるか (方式名は入れない)
- RFC 8345 のエクスポーターでは overlay_domains が network に素直に対応する

## 参照したファイル

- CLAUDE.md、src/mlndl/schema/layer2.py、src/mlndl/derive.py
- docs/decisions/0014-vteps.md、0026-l2vni-vlans.md、deferred.md
- docs/decisions/evaluations/adr0014/neutral/05_multisite_bgw_anycast.yaml
- docs/decisions/evaluations/adr0010/d8-r3/C7_multisite_bgw.yaml
