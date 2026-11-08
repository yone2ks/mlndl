# 宣言的参照 (`Annotated[str, Ref(...)]`) の試し書き比較

**題材**: 既存コードを読んだうえで、以下 2 つの「新しい構文」を追加する作業量を、現在の構造 (参照先はコメントのみ、validator に手書き検査が 31 か所) と、仮説の構造 (型が参照先を宣言し、汎用の検査が全参照を解決する) で比較する。

- A. MLAG の `peer_keepalive: {source: <L3 IF id>, destination_ip: <IP>}` を `layer1.lag[type: mlag]` に追加
- B. BUM 配送方式 `bum: {mode: ingress_replication | multicast, group?: <IP>}` を `layer2.vxlan[l2vni]` に追加

参照先の記述は現状、`src/mlndl/schema/layer1.py:201` のように**コメントで宣言**されるだけ (`peer_link: str  # 同一 lag リスト内の LacpLag.id を参照`)。実際の検査は `src/mlndl/validator.py` 内で `if lag.peer_link not in lag_ids: errors.append(...)` のような手書きの if ブロックとして**別の場所に**書かれており、ファイル先頭のコメント章 (L1〜L92) にもその旨が二重に列挙されている。grep: `未定義.*参照しています` のテンプレ 31 件。

---

## 現在の構造で「A. peer_keepalive」を足すのに触る所

| ファイル | 変更 |
|---|---|
| `src/mlndl/schema/layer1.py` | `MlagLag` に `peer_keepalive: PeerKeepalive \| None` を追加。`PeerKeepalive` モデルを新設 (`source: str`, `destination_ip: IPv4Address`)。コメントで「`source` は `layer3.interfaces[].id` を参照」と書く |
| `src/mlndl/validator.py` | (1) 冒頭の章コメント (L1〜L86) を追記 — 書き忘れると後任者がどこを見ればいいかわからない。(2) `_validate_l1` 内の `MlagLag` 分岐 (L311〜) に if ブロック 2 本 (source 参照の未定義検査 + 「同じ node に属するか」の検査)。(3) 同じ node チェックのために `l3iface_node` を L1 検査にも渡す必要が出る (今は L3 検査にしか渡していない。シグネチャ変更) |
| `src/mlndl/exporter/cytoscape.py` | 存在するなら MLAG エッジに `peer_keepalive` を属性として乗せる。参照解決は `l3iface` マップを別途作って手で引く |
| `tests/fixtures/` | valid 1 本 / invalid (未定義 source) 1 本 / invalid (別ノードの L3 IF) 1 本 |
| `docs/role-vocabulary.md` 等 | — (無関係) |

**件数**: スキーマ 2 行 + 新モデル / validator 2 ブロック + シグネチャ + 章コメント / cytoscape 1 ブロック / 文書は ADR 側のみ / fixture 3 本。

### 書き忘れが起きやすい所

- validator 冒頭の章コメント (L1〜L86) と、ファイル後方の if ブロックの**二重管理**。片方だけ更新しても CI は通る
- `l3iface_node` が L1 検査関数に渡っていない。シグネチャ変更を忘れると「未定義ノード参照」は検出するが「別ノードの L3 IF」は素通りする (`_validate_l1` に該当パスのテストがない)
- cytoscape のエクスポーターは「参照先の存在」を仮定して `dict[src]` で引く。参照検査を書き忘れると KeyError で落ちる

---

## 現在の構造で「B. BUM」を足すのに触る所

| ファイル | 変更 |
|---|---|
| `src/mlndl/schema/layer2.py` | `L2VxLAN` に `bum: BumConfig \| None`。`BumConfig` を Discriminated Union (`mode: Literal["ingress_replication" \| "multicast"]`) で新設。`multicast` のとき `group: IPv4Address` 必須 — これは `model_validator` で手書き |
| `src/mlndl/validator.py` | (1) 章コメント追記。(2) `_validate_l2` の VxLAN ループ (L475〜) に、`mode==multicast` のとき group が設定されているかの検査。(3) ingress_replication のとき `vteps` が 2 つ以上あるかの整合検査 (書き忘れがちな所) |
| `cytoscape.py` | 無関係 (属性だけ) |
| `tests/` | 3〜4 本 |

**件数**: BUM は**参照フィールドがないため、新規追加としては軽い**。だが「`multicast` のとき group 必須」のような**条件付き必須**は Discriminated Union で型表現する決まりに従うと `BumIngressReplication` / `BumMulticast` の 2 クラスに割れて、どちらを許すかの discriminator を `L2VxLAN.bum` 側でも書く必要が出てくる (= 新構文ごとに 1 クラスではなく最低 3 クラス)。

---

## 仮説: 参照先を型に書く構造

```python
# src/mlndl/schema/_refs.py (新設)
class Ref:
    def __init__(self, path: str): self.path = path   # 例: "layer3.interfaces"

RefL3If       = Annotated[str, Ref("layer3.interfaces")]
RefL1Node     = Annotated[str, Ref("layer1.nodes")]
RefLag        = Annotated[str, Ref("layer1.lag", kind="lacp")]  # 絞り込み可
RefVteps      = Annotated[list[str], Ref("layer2.vteps")]
```

```python
# layer1.py
class PeerKeepalive(BaseModel):
    source: RefL3If
    destination_ip: IPv4Address

class MlagLag(BaseModel):
    ...
    peer_keepalive: PeerKeepalive | None = None
```

```python
# layer2.py
class BumConfig(BaseModel):
    mode: Literal["ingress_replication", "multicast"]
    group: IPv4Address | None = None  # multicast のとき必須

class L2VxLAN(BaseModel):
    ...
    bum: BumConfig | None = None
```

validator は**汎用の 1 本の walker** で済む:

```python
# validator.py (疑似コード)
def _collect_refs(topology):
    """pydantic model を再帰的に走査し、Annotated メタデータに Ref があれば検査"""
    for path, value, ref in walk(topology):
        space = _space_for(topology, ref.path)   # 既に _ID_SECTIONS で持っている
        if value not in space:
            yield ValidationError(path, f"未定義の {ref.path} '{value}' を参照しています")
```

このとき **「peer_keepalive を追加した」ことで validator.py には 1 行も触らない**。章コメントもシグネチャも増えない。

### 件数の比較

|   | 現在 | 仮説 |
|---|---:|---:|
| A. peer_keepalive — スキーマ | 新モデル 1 + 2 行 | 新モデル 1 + 2 行 |
| A. peer_keepalive — validator | 章コメント + if 2 本 + シグネチャ 1 | **0** |
| A. peer_keepalive — exporter | 1 ブロック (手で参照解決) | **0** (参照解決 API を呼ぶだけ) |
| B. BUM — スキーマ | 新モデル (条件付き必須に Discriminated Union だと計 3 クラス) | 同左 |
| B. BUM — validator | 章コメント + if 1〜2 本 | **0** |

参照フィールドのない「ただの属性追加」(BUM) は現状でもコストが低い。差が開くのは**参照を持つ構文** (peer_keepalive, 将来の VXLAN-GPE の NSH 対応, EVPN ESI の segment メンバー, etc) を増やすとき。

---

## 利用者 (ndl-viz, eve-lab-builder) 視点の API

ユーザーの言う「コード内で `layer2.vxlan.id` のように参照できる」は、おそらく**ID 文字列から実体へ**の双方向リンクを欲している。既存 API は参照先の存在を使う側が自分で `{v.id: v for v in topology.layer2.vxlan}` を組み立てている (`src/mlndl/exporter/cytoscape.py:45` の `_interface_nodes` が典型)。宣言的参照があれば次が自然に書ける:

```python
# 1. パス文字列での参照
vtep = topology.resolve("vtep-leaf1-leaf2")        # Vtep 実体
l3if = topology.resolve("spine1-lo", kind="l3if")  # 曖昧回避

# 2. 解決済み属性 (読み取り専用プロパティ)
for vni in topology.layer2.vxlan:
    if isinstance(vni, L2VxLAN):
        for v in vni.vteps_resolved:    # list[Vtep] (list[str] の裏側)
            print(v.sources_resolved)   # list[L3Interface]

# 3. 逆引き (この VLAN を使う VNI は?)
vlan = topology.layer2.vlans[0]
vlan.referenced_by  # [L2VxLAN(id="vni-10100"), L3Interface(id="leaf1-vlan-100"), ...]

# 4. 道順
topology.path("spine1-lo", "leaf1-lo")  # L1 links の列
```

4 は RFC 8345 の `trace()` に近く、「パッチパネル中継」のユースケースで CLAUDE.md が触れている NetBox 連携にも繋がる。1〜3 は現在、各ツールが自分で辞書を組み立てて実装している (`exporter/cytoscape.py` が良い例)。

---

## 推奨

1. **参照先はコメントではなく型 (`Annotated[str, Ref(...)]`) に書く**。validator の 31 の if ブロックは生成的な 1 本の walker に置き換えられる。章コメントとの二重管理が消える
2. ただし移行は漸進的に。まず新しい構文 (A. peer_keepalive や VXLAN-GPE の予定分) から `Ref` を使い、既存の 31 箇所は現状維持。walker が既存コードと同じエラー文言を出せることをテストで保証してから置換する
3. 利用者向け API としては、まず `topology.resolve(id)` と `*_resolved` プロパティの 2 つを公開する。逆引き (`referenced_by`) と `path()` は Phase 3 (`blast_radius` クエリ) に合流させる
4. `Ref("layer2.vxlan", kind="l2vni")` のような絞り込みは Discriminated Union との二重宣言になる。種類は型 (L2VxLAN vs L3VxLAN) で表現し、`Ref` は path のみに留める

### 注意点

- `_resolve_ref` (validator.py:978) が今「旧形式 `{interface:}` を新形式へ読み替える」役を兼ねている。Ref ベースに移すときは、Ref に「このフィールドは `{interface:}` も受ける旧形式を持つ」と宣言できる必要がある (= `Ref` にメタデータが要る)
- `Ref` に相互制約 (「`peer_keepalive.source` の node は MLAG の 2 ノードのどちらか」) は書けない。これは今の構造でも手書きの検査が残る。宣言的参照は「存在」までで、「意味的な整合性」は validator 側に残る

---

## 結果 (2026-10-21、[ADR-0015](../../0015-declarative-references.md))

仮説の構造を採用し、実装した。本文の「31 か所」は `未定義` を含む行の数で、固定の参照先を持つ存在の検査は 29 か所だった
(残りはキーで参照先を選ぶ参照の仕組みの中にある)。29 か所はすべて `Ref` の宣言と汎用の検査に置き換えた。

本文の提案のうち、次は採らなかった。

- **新しい構文から少しずつ `Ref` を使う**: 既存の検査も差分テスト (849 通り) で安全に置き換えられたので、一度に移した
- **`vni.vteps_resolved` / `vlan.referenced_by`**: スキーマに解決済みの属性を持たせると循環や YAML への書き出しが壊れるので、
  `topology.resolve(id)` と `topology.index()` だけにした。逆引きは Phase 3 のクエリと一緒に設計する

