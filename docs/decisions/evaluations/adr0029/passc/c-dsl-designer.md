# ADR-0029 Pass C — mlndl-dsl-designer

Pass B のユーザーの判断 (A1 / `overlay_domains` / `od-` / 1 本のループバックは先送り / `border-gateway` は informative) を前提に、実装に落とせる粒度で決める。

## 1. スキーマ

```python
# src/mlndl/schema/layer2.py
class OverlayDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str                                   # 推奨プレフィックス od-
    name: str | None = None
    description: str | None = None
    # members / type / 方式名は持たない

class Vtep(...):
    overlay_domain: Annotated[str | None, Ref("layer2.overlay_domains")] = None

class L2Layer(...):
    overlay_domains: list[OverlayDomain] = []   # 任意。空でも valid
```

- 未知のキーと未定義の参照は `extra="forbid"` と `Ref` で既存の仕組みが弾く
- 推奨プレフィックス `od-` は validator のプレフィックスの検査 (VTEP の隣)、ADR-0002 D7 の表、`docs/reference/`、CLAUDE.md に足す
- id の文法は全 id の検査がそのまま効く

## 2. 導出 (`derive.py`)

```python
def overlay_domain_of_vtep(topology) -> dict[str, str]:
    """VTEP id → ドメイン id。暗黙のドメインは特別な値を返す"""

def overlay_domain_members(topology) -> dict[str, list[str]]:
    """ドメイン id → その中の VTEP id (書いた順)。暗黙のドメインは '' (エクスポーターでは出さない)"""

def l2vni_tunnel_pairs(topology) -> dict[str, list[tuple[str, str, str]]]:
    """L2VNI id → [(vtep_a, vtep_b, domain_id)]。同じ L2VNI に参加し、同じドメインに属する VTEP の順不同の対"""

def cross_domain_stitchers(topology) -> dict[str, set[str]]:
    """L2VNI id → その L2VNI が 2 つ以上のドメインに広がるとき、複数のドメインに VTEP を持つ機器 (BGW)。
    1 つのドメインなら空。ADR-0026 D5 の 10 の抑制と、核心の検査の両方が使う"""

def l3vni_domains(topology) -> dict[str, set[str]]:
    """L3VNI id → 参加するドメイン。同じ VRF の L2VNI のドメインの和集合
    (試し書き a1 の BGW は vrf-tenant-a の L3 IF を持たず、「VRF の L3 IF を持つ機器」で引くと
    BGW が L3VNI に入らない。Symmetric IRB の Multi-Site では L3VNI も BGW で中継されるので、それは誤り)"""

def l3vni_tunnel_pairs(topology) -> dict[str, list[tuple[str, str, str]]]:
    """L3VNI id → 同じドメインの VTEP の対。VTEP は、その L3VNI と同じ VRF の L2VNI の vteps にあるもの"""
```

`l2vni_participants` は変えない。

## 3. 検査

| # | 内容 | severity | 理由 |
|---|---|---|---|
| A | L2VNI が 2 つ以上のドメインにまたがるのに、ドメインをつなぐ機器がない | **error** | DCI のトンネルを張る BGW がいない = データの通り道が切れている。方式中立のまま判定できる唯一の構造の条件 |
| B | ドメインを書いた VTEP と書かない VTEP の混在 | **error** | 暗黙のドメインは「全 VTEP が 1 つ」の意味。混ぜると「書いた VTEP のドメイン + 暗黙のドメイン」に読め、意味があいまいになる |
| C | VTEP が 1 つもないドメイン | **warning** | error は厳しすぎる (VTEP を後で足す前提で先に宣言する場合) |
| D | VTEP が 1 つだけのドメイン | **出さない** | stretched や「後で BGW を足す」構成で偽の警告になる |
| E | `overlay_domains` が 1 つだけ | **出さない** | 「書く意味がない」は注釈で十分 |
| F | サイト間の EVPN セッションとドメインの境界の照合 | **出さない** | ADR-0010 で制御プレーンとデータプレーンを独立に導く。RR の配下では一致しない |

メッセージの案:

- A: 「L2VNI 'vni-10100' は 2 つのオーバーレイのドメイン ('od-site-a' / 'od-site-b') にまたがっていますが、両方のドメインに VTEP を持つ機器がありません。サイトのあいだを中継する機器 (BGW) の VTEP を両方のドメインに書いてください (ADR-0029)」
- B: 「VTEP 'vtep-a-leaf1' には overlay_domain が書かれていますが、VTEP 'vtep-b-leaf1' には書かれていません。overlay_domains を使うなら、すべての VTEP に書いてください (ADR-0029)」

## 4. ADR-0026 D5 の 10 の warning を抑える条件

機器 `n` と L2VNI `vx` について、次の両方が真なら warning を出さない。

1. `vx` が 2 つ以上のドメインにまたがる
2. `n` が `cross_domain_stitchers[vx.id]` に入る (= `n` が終端する VTEP のうち `vx.vteps` にあるものが 2 つ以上あり、それらのドメインが違う)

暗黙のドメインだけなら 1 が偽なので、今までどおり warning。

## 5. エクスポーター (Cytoscape)

規範のキー (`docs/exporter-cytoscape.md` に足す):

- `type: overlay_domain` のノード: `id` / `label` / `layer: layer2` / `description` / `vteps`。**暗黙のドメインは出さない** (書いていないものを出さない)
- 機器のノードの `vteps[]` の各要素に `overlay_domain` (書いたときだけ)
- `type: l2vni` に `tunnel_pairs: [{from, to, overlay_domain?}]`。ndl-viz が同じドメインの対だけ線を引くのに使う。辺 (`type: tunnel_pair`) は作らない (対の数が多く、ndl-viz が別の層で描く)
- `type: l3vni` に `overlay_domains: [...]`
- VTEP のノードは足さない

## 6. テストの観点

1. ドメインを書かない fixture がそのまま valid
2. `valid_evpn_multisite.yaml` で検査 A が通り、BGW を 1 台抜くと error
3. 混在で error (B)
4. VTEP のないドメインで warning (C)、1 つのドメインは warning なし (D)、ドメインが 1 つでも warning なし (E)
5. BGW に ADR-0026 D5 の 10 の warning が出ない。暗黙のドメインの fixture では今までどおり出る
6. `l2vni_tunnel_pairs` が同じドメインの対だけ返す (3 サイトの b3)
7. `l3vni_domains` が BGW を含む (a1)
8. `OverlayDomain` と VTEP の未知のキーが error
9. プレフィックス `od-` 以外で warning
10. 未定義のドメインの参照が error
11. エクスポーターの形。暗黙のドメインのときは出ない
12. 3 サイトで DCI がフルメッシュの 1 つのドメイン

## 7. 自信がない点

1. **L3VNI のドメイン**を「同じ VRF の L2VNI のドメインの和集合」にしたが、L2VNI を持たない VRF (L3 だけの EVPN のテナント) では空になる。今は「空なら空、validator は何も言わない」とする
2. **暗黙のドメインの値**を `''` にするか `None` にするか
3. **ドメインをつなぐ機器の判定**: 「2 つ以上のドメインに VTEP を持つ機器が 1 台いるか」で判定しているので、3 つのドメインにまたがる L2VNI で、ab と ac はつなぐが bc はつながない構成も通してしまう。DCI がフルメッシュなら問題にならない。ADR に「hub-and-spoke は範囲外」と明記する

## 後への申し送り

- VNI stitching は、L2VNI を「番号ごとのエントリ」にする ADR-0026 の流儀で、ドメインごとに参加の VTEP を分ければ書ける。VTEP 単位のドメインと整合する
- hub-and-spoke の DCI と route server は、「フルメッシュの集合」の定義ごと見直すので先送り
- 事業者網 (ADR-0018 の bridge) を経る DCI とは、構造の衝突はない
