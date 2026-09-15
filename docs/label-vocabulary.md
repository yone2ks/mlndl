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
  parent: pod-tokyo          # Containment  — どこに属するか（論理階層・Phase 3+）
  labels:                    # Classification — どんな属性か（多軸）
    az: ap-northeast-1a
    tenant: acme
    env: prod
```

三者の役割分担は [ADR-0009](decisions/0009-membership-orthogonality.md) を参照してください。

---

## 推奨軸名

`src/mlndl/constants.py` の `FAULT_AXIS_LABEL_KEYS` / `MANAGEMENT_AXIS_LABEL_KEYS` と同一の語彙です。

### 障害軸 (fault axis)

同じ値を持つノードは**同じ障害を共有しうる**軸。Phase 3+ の `blast_radius` クエリはこの軸を辿る候補になります。

| キー | 意味 | 値の例 | 備考 |
|------|------|--------|------|
| `az` | Availability Zone。電源・冷却・建屋の障害単位 | `ap-northeast-1a` | クラウド・オンプレ共通。AZ ⊇ 複数 pod が一般的 |
| `pod` | Clos ファブリックの増設単位 (Cisco PoD = Point of Delivery) | `pod-tokyo` | IS-IS / underlay BGP が pod 内で完結する。**Kubernetes Pod ではない** |
| `rack` | 物理ラック。ToR 障害・ラック電源の単位 | `rack-a01` | |
| `site` | 物理拠点 / データセンター建屋 | `site-tokyo` | DCI をまたぐ単位 |
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
  ただし**現時点でバリデーターは検証しません** — `validator.py` に severity 機構 (ADR-0002 D8 の `warning`) が
  未実装のためです。severity 機構の導入時に `warning` として実装予定。
- **値は自由文字列**。ADR-0002 の ID 規則に従う必要はありません (`ap-northeast-1a` のようにハイフンを含む値も可)。
- **値は参照ではありません**。`labels: {pod: pod-tokyo}` の `pod-tokyo` は `layer1.nodes` の ID を
  指してはいません。属性を持つ箱に所属させたい場合は `parent:` を使ってください ([ADR-0009](decisions/0009-membership-orthogonality.md) D2)。
- **値の型は `str` のみ** (Phase 1)。`labels: {vlan: 100}` は error です。

---

## ndl-viz での利用

| 状況 | ndl-viz の動作 |
|------|---------------|
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
| `labels: {vpc: vpc-prod}` で階層を表現する | `labels` は多軸フラット分類。VPC ⊃ subnet ⊃ instance の階層は連鎖で辿れる必要がある | `parent: vpc-prod` (Phase 3+) |
| `labels: {node: leaf1}` のような ID 参照 | `labels` は非参照。参照整合性の検証対象外 | `attaches_to` / `parent` |
| 同一軸に複数値を持たせる | map なので構造的に不可能 | 軸を分ける (`az` と `az-secondary` 等)、または Phase 3+ の構造化構成子を待つ |

---

## 将来の拡張

### 障害軸の構造化 (Phase 3+ 検討)

現在の `labels` は障害軸と管理軸をフラットに混在させるため、`blast_radius` クエリが
「どのキーが障害軸か」を判定できません。`blast_radius(tenant=acme)` は意味をなしませんが、
mlndl コアはそれを止められません。

当面はこのドキュメントの分類 (障害軸 / 管理軸) を informative な指針とし、
`blast_radius` を実装する Phase 3+ で必要性が明確になった時点で、
障害軸を構造化構成子 (`fault_domains:` 等) に昇格させる方針です。
**昇格は加算的変更であり、既存の `labels` を壊しません。**

### 適用範囲の拡大

Phase 1 では `layer1.nodes` にのみ `labels` を実装しています。
Phase 2 で link / lag / vlan / vxlan / vrf / routing_adjacency へ横展開予定です。

### 語彙の追加

`labels` は open-form のため、上記リストにない軸名を使っても mlndl コアは error を出しません。
新語彙を mlndl エコシステム全体で共有する場合は、このドキュメントへの Pull Request を送ってください。
mlndl の ADR は動かしません。

---

*参照: [ADR-0009](decisions/0009-membership-orthogonality.md) — D1・D2・D3 / [ADR-0003](decisions/0003-role-vocabulary.md) — 注釈側構成子の設計パターン*
