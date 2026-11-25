# ADR-0029 Pass B — mlndl-dsl-designer

前提: Pass A の推奨モデル (ドメイン = 中でフルメッシュにトンネルを張る VTEP の集合、1 つの VTEP は 1 つのドメイン、DCI も 1 つのドメイン、BGW は 2 つのドメインに VTEP を 1 つずつ持つ)。書く場所 A1 (VTEP に `domain:` + ドメインの一覧) と A2 (ドメインが `members` で VTEP を並べ、L2VNI が `domains` を指す) を比べる。

## 既存の言語との比較

- **Kubernetes の Service と EndpointSlice**: EndpointSlice が属する Service を指す。子 → 親の片方向の参照で、参照先は 1 つ。A1 と同じ形
- **MLNDL の `layer1.lags[].node`**: LAG が属する機器を単数のキーで指す (ADR-0023)。A1 と同じ形。ADR-0018 の `bridges.ports` は A2 と同じ形だが、ports は「どのポートで転送するか」という箱の構成要素で、VTEP とドメインの関係とは意味が違う

ADR-0005 D2-1 (エンティティは箱、関係は参照) と ADR-0015 の Ref からすると、参照先が 1 つに決まるドメインは VTEP の属性 (単一の参照) で書くのが筋。**A1 が MLNDL の既存の筋と一致する**。

## 直交性

- **A1**: ドメインは VTEP の `domain` の 1 か所にしか書けない。L2VNI の `vteps` は変えない
- **A2**: VTEP の id が `members` と `L2VxLAN.vteps` の両方に出る。「members に書いて vteps に書き忘れた」「vteps に書いてどのドメインにも入れていない」の 2 方向の食い違いが起きる。`members ⊆ vteps` の包含は ADR-0015 の宣言的な参照では捉えられず、validator に手で書く。**A2 は直交性で明らかに劣る**

## 参照のモデル

- **A1**: `Vtep.domain: Annotated[str | None, Ref("layer2.overlay_domains")]`。汎用の検査 1 本。1 対 1 が型で決まる
- **A2**: `members: Annotated[list[str], Ref("layer2.vteps")]`。1 つの VTEP が 2 つのドメインの members に出ないことを validator で検査する (bridge のポートの重複と同じ形)。参照の向きが逆 (親 → 子) で、ADR-0014 D4 で L2VNI から VTEP を外出ししたときの「集約する側に書かない」方針にも逆行する

ドメインを書かないときも A1 が扱いやすい: `domain` のない VTEP を暗黙のドメインに入れ、エクスポーターは今までどおり全 VTEP のフルメッシュを出す。A2 では「どのドメインの members にも入っていない VTEP」の扱いがあいまいになる。

## 型 (A1)

```python
class OverlayDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str | None = None
    description: str | None = None

class Vtep(BaseModel):
    ...
    domain: Annotated[str | None, Ref("layer2.overlay_domains")] = None

class L2Layer(BaseModel):
    ...
    overlay_domains: list[OverlayDomain] = []
```

- 型で表す: ドメインの参照 (Ref)、1 つの VTEP は 1 つのドメイン (単数のフィールド)、ドメインは id を持つ箱
- validator で表す: ドメインの VTEP が 1 つ (warning)、BGW なしでドメインをまたぐ L2VNI (error)、ドメインを書いた VTEP と書かない VTEP の混在 (error)
- 文書だけ: サイト = ドメインとは限らない、`labels.site` との対応は検査しない、方式 (anycast BGW / vPC / ESI-LAG) は書かない

## 導出

```python
def vtep_domain(topology) -> dict[str, str]:
    """VTEP id → ドメイン id。domain を書かない VTEP は暗黙のドメイン"""

def l2vni_tunnel_pairs(topology) -> dict[str, list[tuple[str, str]]]:
    """L2VNI id → 同じドメインに属する VTEP の順不同の対。ドメインをまたぐ対は出さない"""

def domain_gateways(topology) -> dict[str, dict[str, set[str]]]:
    """ドメイン id → {機器 id → その機器がこのドメインに持つ VTEP}。2 つ以上のドメインに出る機器が BGW"""
```

`l2vni_participants` は変えない (参加機器 = VTEP の sources のノード)。参加機器とトンネルの対は別で、エクスポーターはトンネルの対で辺を描く。

## 検査

| # | 検査 | severity |
|---|---|---|
| 1 | `Vtep.domain` の参照先が実在 (汎用の Ref) | error |
| 2 | 1 つでも VTEP に `domain` を書いたら、全 VTEP に書く (混在を許さない) | error |
| 3 | どの VTEP も属さないドメイン | warning |
| 4 | VTEP が 1 つだけのドメイン | warning |
| 5 | L2VNI の VTEP が 2 つ以上のドメインにまたがるのに、2 つのドメインに VTEP を持つ機器 (BGW) が 1 台もない | error |
| 6 | `overlay_domains` が 1 つだけ (書く必要がない) | warning |
| 7 | サイト間の EVPN セッションの両端が BGW どうしか | **しない**。制御プレーンとデータプレーンを独立に保つ (ADR-0010) |
| 8 | ADR-0026 D5 の 10 の warning を、2 つのドメインに VTEP を持つ機器なら出さない | 抑制 |

#5 は構成図の意味を壊す (届かない) ので error。ほかは「変だが動く」。

## 将来の拡張

A1 は、拡張をドメインの箱に足す方向で素直に乗る。

- **VNI stitching**: VNI の一意性を「同じドメインの中」に緩める (ADR-0027 の「検査を緩める」の範囲)。A1 なら VTEP の属性を見るだけ。A2 は `vteps` と `members` の両方を見るので複雑
- **L3VNI**: VRF の L3 IF を持つ機器の VTEP を導き、そのドメインを集めれば L3VNI のドメインの範囲が決まる。A1 なら 1 段
- **BUM の方式**: ドメインの属性に足せる余地がある (方式名を書かない原則の範囲で)

**A1 のほうが拡張しやすい**。

## 推奨

**A1 (VTEP の `domain:` + `layer2.overlay_domains`) を採る**。(i) 1 つの VTEP が 1 つのドメインであることが型で決まる、(ii) L2VNI を変えないので ADR-0014 D4 と整合し、今の 5 本の fixture は書き換えなしで valid、(iii) 同じ情報を 2 か所に書けない、(iv) ADR-0015 の参照 1 本で検査が付き、VNI stitching・L3VNI・BUM の方式への拡張もドメインに属性を足すだけ。暗黙のドメインは内部の id として扱い、エクスポーターは常にドメインを出す (下流のツールが分岐しなくて済む)。

## ユーザーに判断してもらう論点

1. **一覧の名前**: `overlay_domains` / `vxlan_domains` / `fabrics`。構造としてはどれでも A1 は成り立つ。「DCI もドメイン」との整合から `overlay_domains` を残したい
2. **暗黙のドメイン**: (a) `domain` の省略を許す (加算、fixture はそのまま) / (b) `overlay_domains` を書いたら全 VTEP に必須。**(a) と検査 #2 の併用を推奨** (1 つのドメインなら書かない、Multi-Site では全 VTEP に書く)
3. **BGW なしでドメインをまたぐ L2VNI**: error (推奨) か warning か
4. **検査 #7**: しない (推奨)
5. **L3VNI のドメインの範囲**: VRF から VTEP を導き、そのドメインを集める (推奨)。ADR-0014 D3 を補う

## 後の ADR への申し送り

- VNI stitching (deferred.md 50): A1 に素直に乗る。今回やるか別の ADR か
- RT の付け替え・BUM の配送方式: ドメインの属性に乗せる余地だけ残す
- マルチアクセス (deferred.md): 「共有の媒体 = 名前付きの箱」の流儀で書けるか後で確かめる
- `role: border-gateway`: linguist・spec-architect の判断
- エクスポーター: VTEP のデータに `overlay_domain`、辺はトンネルの対から。暗黙のドメインも明示して出す
