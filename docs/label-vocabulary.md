# mlndl labels 軸名リファレンス

> **ステータス: Informative (参考情報)**
>
> このドキュメントは [ADR-0009](decisions/0009-membership-orthogonality.md) D3 に基づく informative リファレンスです。
> mlndl コアのバリデーターはこのドキュメントを参照せず、`labels` のキー域・値域チェックを一切行いません。
> `role` (ADR-0003) と同じ**注釈側構成子**の扱いです。

---

## `labels` とは

ノードが**同時に複数の直交した軸に所属する**ことを表す key-value マップです。

```yaml
- id: leaf1
  role: leaf
  attaches_to: esxi-01       # Realization  — どこで動くか（物理基盤）
  parent: pod-tokyo          # Containment  — どこに属するか（論理階層・まだ書けない）
  labels:                    # Classification — どんな属性か（多軸）
    az: ap-northeast-1a
    tenant: acme
    env: prod
```

三者の役割分担は [ADR-0009](decisions/0009-membership-orthogonality.md) を参照してください。

`labels` は、同じ値を複数の要素が共有する**分類**です。1 つの要素だけを識別する値 (回線 ID、契約番号、資産タグ) は
`labels` ではなく `description` に書いてください ([ADR-0017](decisions/0017-sites-and-wan.md) D4)。

---

## 推奨軸名

`src/mlndl/constants.py` の `FAULT_AXIS_LABEL_KEYS` / `MANAGEMENT_AXIS_LABEL_KEYS` と同一の語彙です。

### 障害軸 (fault axis)

同じ値を持つノードは**同じ障害を共有しうる**軸。将来の `blast_radius` の問い合わせは、この軸をたどる候補になります。

| キー | 意味 | 値の例 | 備考 |
|------|------|--------|------|
| `az` | Availability Zone。電源・冷却・建屋の障害単位 | `ap-northeast-1a` | クラウド・オンプレ共通。AZ ⊇ 複数 pod が一般的 |
| `pod` | Clos ファブリックの増設単位 (Cisco PoD = Point of Delivery) | `pod-tokyo` | IS-IS / underlay BGP が pod 内で完結する。**Kubernetes Pod ではない** |
| `rack` | 物理ラック。ToR 障害・ラック電源の単位 | `rack-a01` | |
| `site` | 物理拠点 / データセンター建屋 | `tokyo` | DCI をまたぐ単位。値はサイトの名前をそのまま書く (`site-tokyo` としない)。図のサイトの枠にも使う。両端のノードの `site` が違うリンクがサイト間のリンク。事業者網の箱には付けない ([ADR-0017](decisions/0017-sites-and-wan.md) D1) |
| `region` | 地理リージョン | `ap-northeast-1` | クラウドのリージョン境界 |

### 管理軸 (management axis)

課金・所有・ライフサイクルの分類。**障害は伝播しません。**

| キー | 意味 | 値の例 |
|------|------|--------|
| `tenant` | テナント (管理・課金の単位) | `acme` |
| `env` | 環境区分 | `prod` / `stg` / `dev` |
| `stage` | デプロイ段階 | `canary` / `ga` |
| `owner` | 責任チーム | `net-infra` |
| `cost-center` | コストセンター | `eng-platform` |

---

## 慣習表記

- **キーの文字セット**: ADR-0002 D1 の ID 正規表現 (`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`) に準拠することを**推奨**します。
  表記揺れ (`az` / `AZ` / `availability_zone` / `availabilityZone`) を避けるためです。
  違反は **`warning`** になります（`validate_all()` と `python -m mlndl validate` で表示。
  error ではないので `validate()` の戻り値には含まれず、トポロジーは valid のまま。`--strict` で error に昇格）。
- **値は自由文字列**。ADR-0002 の ID 規則に従う必要はありません (`ap-northeast-1a` のようにハイフンを含む値も可)。
- **値は参照ではありません**。`labels: {pod: pod-tokyo}` の `pod-tokyo` は `layer1.nodes` の ID を
  指してはいません。属性を持つ箱に所属させたい場合は `parent:` を使ってください ([ADR-0009](decisions/0009-membership-orthogonality.md) D2)。
- **値の型は `str` のみ**。`labels: {vlan: 100}` は error です。

---

## ndl-viz での利用

| 状況 | ndl-viz の動作 |
|------|---------------|
| `site` がある | 同じ値のノードを 1 つの枠にまとめ、値を枠の名前にする。`site` のないノードには枠を出さない |
| 推奨軸名のキーがある | 軸別のフィルタ・色分けを既定で提供 |
| 推奨軸名にないキー (例: `ticket`) | フィルタ候補として列挙するが既定スタイルは適用しない |
| `labels` 未設定 | 何もしない。警告は出さない |

**重要**: `labels` は注釈側構成子のため、**下流ツールは特定のキーの存在を前提にできません。**
`az` でグループ分けする実装は、`availability_zone` と書かれたトポロジーでは効きません。
アダプター (NetBox / neteye) 側で推奨軸名へ正規化することを推奨します。

---

## 推奨しない用法

| 用法 | 理由 | 代替表現 |
|------|------|---------|
| `labels: {vpc: vpc-prod}` で階層を表現する | `labels` は多軸フラット分類。VPC ⊃ subnet ⊃ instance の階層は連鎖で辿れる必要がある | `parent: vpc-prod` (まだ書けない) |
| `labels: {node: leaf1}` のような ID 参照 | `labels` は非参照。参照整合性の検証対象外 | `attaches_to` / `parent` |
| `labels: {circuit-id: KD-0123}` のような識別子 | 同じ値を共有する要素がなく、分類にならない | `description` (ADR-0017 D4) |
| 同一軸に複数値を持たせる | map なので構造的に不可能 | 軸を分ける (`az` と `az-secondary` 等)、または障害軸の構造化を待つ |

---

## 将来の拡張

### 障害軸の構造化 (先送り)

現在の `labels` は障害軸と管理軸をフラットに混在させるため、`blast_radius` クエリが
「どのキーが障害軸か」を判定できません。`blast_radius(tenant=acme)` は意味をなしませんが、
mlndl コアはそれを止められません。

当面はこのドキュメントの分類 (障害軸 / 管理軸) を informative な指針とし、
`blast_radius` の問い合わせを作るときに必要性が明確になった時点で、
障害軸を構造化構成子 (`fault_domains:` 等) に昇格させる方針です。
**昇格は加算的変更であり、既存の `labels` を壊しません。**

### 適用範囲の拡大

`labels` は `layer1.nodes` にだけ書けます。
lag / vlan / vxlan / vrf / routing_neighbor などへ広げるかは先送りしています ([先送りした項目](decisions/deferred.md))。
リンク (`L1Link.labels`) は、リンクを分類で選ぶ用途が出るまで足しません ([ADR-0017](decisions/0017-sites-and-wan.md) D4)。

### 語彙の追加

`labels` は open-form のため、上記リストにない軸名を使っても mlndl コアは error を出しません。
新語彙を mlndl エコシステム全体で共有する場合は、このドキュメントへの Pull Request を送ってください。
mlndl の ADR は動かしません。

---

*参照: [ADR-0009](decisions/0009-membership-orthogonality.md) — D1・D2・D3 / [ADR-0003](decisions/0003-role-vocabulary.md) — 注釈側構成子の設計パターン*
