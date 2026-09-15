# ADR-0009: メンバーシップ構成子の直交性 — `attaches_to` / `parent` / `labels`

- **Status**: Accepted
- **Date**: 2026-09-15 (Accepted: 2026-09-16)
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author
- **Pass**: C 相当 (6 ラウンドの 5 エージェント並列評価を経て確定)
- **関連**: ADR-0001 (attaches_to), ADR-0002 (ID 命名), ADR-0003 (role open-form), ADR-0005 (表現スコープ・D4 判定), drafts/0008 (クラウドネットワーク表現)

> **Accepted の範囲**: 3 構成子の意味論・命名・直交性は確定済み。実装は段階的で、
> `attaches_to` は Phase 1 実装済み (ADR-0001)、`labels` も Phase 1 実装済み、
> `parent` は Phase 3+ で drafts/0008 の受理と同時に実装する。
> 決定そのものは確定しているため、実装段階に関わらず本 ADR は Accepted とする。


## Context

「あるノードが何に所属するか」を表す構成子の命名を 6 ラウンドにわたり検討した。
候補は `scope` → `pod` → `belongs_to` → `member_of` → `part_of` → `parent` → `facets` → `labels` と動き、
どの語も既存のネットワーク用語・プロジェクト内用語と衝突した。

**難航の根本原因は語彙の枯渇ではなく、構造の誤りだった。** mlndl の「グルーピング」には
意味の異なる 2 種類が混在しており、それを 1 つの構成子で表そうとしていた。

| 種別 | 例 | 性質 |
|------|-----|------|
| **階層ネスト** | vpc ⊃ subnet ⊃ instance | 単一軸・木構造・連鎖で辿る |
| **多軸フラット分類** | pod-tokyo / az-1a / tenant-acme | 複数軸・直交・並列 |

ADR-0005 の D4 判定フレームワークを**この 2 種類に分けて適用する**と、判定がきれいに割れる。

| 判定軸 | 階層ネスト | 多軸分類 |
|--------|:---------:|:-------:|
| 削除で参照整合性が崩れるか | **Yes** (subnet の CIDR が孤立する) | No |
| RFC8345 ノードグラフから消えるか | **Yes** | No |
| 値の変更で意味境界が変わるか | **Yes** (別 VPC に移すと到達性が変わる) | 軸による |
| broadcast_domain / blast_radius に影響するか | **Yes** | 軸による |
| **判定** | **規範側構成子** | **注釈側構成子** |

判定が割れる以上、別構成子にすべきである。これが本 ADR の出発点。

### 技術的な裏付け

多軸が必要なのは設計の好みではなく技術的必然である。

- **1 VPC ⊃ 複数 tenant は実在する** — AWS RAM の subnet sharing により、1 VPC の各サブネットを
  別アカウント (= tenant) に分割共有できる。Azure の shared subscription、GCP の Shared VPC も同型。
  したがって tenant と VPC は多対多であり、単一の階層参照では原理的に表現できない
- **pod と AZ も厳密な包含ではない** — 通常は AZ ⊇ 複数 pod だが、cross-AZ の stretched fabric
  (EVPN multi-site) では pod が AZ をまたぐ

### 業界の前例

階層コンテナとタグを**併存**させるのが業界の一致した結論である。一本化を試みていた mlndl が外れ値だった。

| | 階層コンテナ | タグ |
|---|---|---|
| NetBox | Region ⊃ Site ⊃ Location ⊃ Rack ⊃ Device (単一 FK) | tags |
| Kubernetes | ownerReferences (単一親) | labels (selector 可) / annotations (selector 不可) |
| AWS | Organizations OU 階層 | resource tags |
| Azure | Management Group ⊃ Subscription ⊃ RG | tags |
| GCP | Organization ⊃ Folder ⊃ Project | labels |

## Decision

### D1. 三構成子の直交性

mlndl は「所属」を **3 つの直交した構成子**で表現する。

| 構成子 | 意味論 | 方向 | 多重性 | 値域 | D4 判定 | 実装 |
|--------|--------|------|--------|------|---------|------|
| `attaches_to` | **Realization** — 下位層が物理基盤を提供する (RFC8345 supporting) | 縦 (下→上) | 単一 | 既存 ID 参照 (node/interface/link) | 規範側 | Phase 1 (ADR-0001) |
| `parent` | **Containment** — 論理的な箱への階層的所属 | 縦 (子→親) | 単一、連鎖でネスト | 既存 node ID 参照 | 規範側 | Phase 3+ (ADR-0008) |
| `labels` | **Classification** — 多軸の並列分類 | なし (属性) | 多重 (map) | 自由文字列 | **注釈側** | **Phase 1** |

```yaml
- id: ec2-app-tokyo-1a-01
  role: server
  implementation: vm
  attaches_to: hv-nitro-1a-01        # Realization
  parent: subnet-app-tokyo-1a        # Containment (Phase 3+)
  labels:                            # Classification
    az: ap-northeast-1a
    tier: app
    env: prod
```

3 つが並んでも混乱しない。意味が直交している上に、値の型が 3 種類とも異なる (文字列 / 文字列 / map)。

**書き分けの判定基準**:

> `attaches_to` は「**これを取り外すと動作が止まる**実行基盤」を指す。
> `parent` は「**取り外しても動作は続くが、分類から外れる**論理境界」を指す。
> `labels` は「**参照ではない属性**」を指す。

補助テスト: 「B が消えたら A は動くか?」— 止まるなら `attaches_to`、動くが所属不明になるなら `parent`。

### D2. `labels` は非参照

`labels` の値は**箱ノードへの参照ではなく、単なる文字列**である。

```yaml
labels: {pod: pod-tokyo}   # pod-tokyo という ID のノードを指してはいない
```

- 参照整合性の検証対象外。未定義 ID を書いても error にならない
- 値は ADR-0002 の ID 規則に従う必要がない (`ap-northeast-1a` のようにハイフンを含む値も可)
- **属性を持つ箱** (VPC の `cidr`、pod の `fabric_type` 等) に所属させたい場合は `parent:` を使う

この線引きにより、`labels` は注釈側構成子として一貫する (ADR-0005 D4 で全 No)。

**代償**: 「pod-tokyo という属性付きの箱に属し、かつ az-1a にも属する」を表現するとき、
`parent` に置けるのは片方だけになる。もう片方は文字列の label になる。これは意識的な割り切りである。

### D3. `labels` は open-form (キー・値ともに自由)

`role` (ADR-0003 D1) と同じ**注釈側構成子**として扱う。

```python
labels: dict[str, str] | None = None
```

- **キーもバリューも自由文字列**。mlndl コアは語彙チェックを一切しない
- 未指定 (`None`) でも valid
- **値の型は `str` のみ** (Phase 1)。`labels: {vlan: 100}` は error
- 推奨軸名は `docs/label-vocabulary.md` (informative)。障害軸 (`az`/`pod`/`rack`/`site`/`region`) と
  管理軸 (`tenant`/`env`/`stage`/`owner`/`cost-center`) に分類

**キーの構文**: ADR-0002 D1 の ID 正規表現 (`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`) への準拠を
**推奨**する (表記揺れ `az` / `AZ` / `availability_zone` を避けるため) が、
**Phase 1 では検証しない**。`validator.py` に severity 機構 (ADR-0002 D8 の `warning`) が
未実装のため。severity 機構の導入時に `warning` として実装する。

### D4. map 形式を採用 (フラットリストは不可)

```yaml
labels: {az: ap-northeast-1a, tenant: acme}   # 採用
tags: [az-ap-northeast-1a, tenant-acme]       # 却下
```

フラットリストを却下する理由:

1. **値にハイフンを含む識別子で構造的に破綻する** — `az-ap-northeast-1a` は
   「軸=`az` / 値=`ap-northeast-1a`」なのか「軸=`az-ap` / 値=`northeast-1a`」なのか判定不能。
   AWS AZ / GCP zone / Azure region がすべてこの形
2. **ADR-0002 と結合してしまう** — 軸を ID プレフィックス規約に相乗りさせると、
   ID 命名規則 (ADR-0002) と多軸分類 (本 ADR) という独立した関心事が結合する。
   `{az: az-1a}` の局所的な冗長より深刻な直交性違反
3. 軸名の型付けができず、`blast_radius` クエリで軸指定が一級市民にならない
4. 同一軸の重複値 (`[az-1a, az-1b]`) を構造的に防げない

### D5. `label` / `tag` の bare 使用を禁止 (予約語)

将来のプロトコル拡張との衝突を構造的にゼロにする。

```markdown
bare `label` / `tag` は mlndl 全体でフィールド名として使用禁止。
整数セマンティクスのプロトコルフィールドは必ず修飾語を付ける:
- MPLS: mpls_label / label_stack / label_action
- 802.1Q: vlan_id (実装済み)、将来の Q-in-Q は stag_vlan_id / ctag_vlan_id
```

mlndl は既に 802.1Q を `tag` ではなく `vlan_id` と命名済みであり、この方針は現状と整合する。

## Consequences

**良い影響:**

- 6 ラウンドの命名難航が構造の分離で解消した。`parent` は GCP / AWS Organizations の
  既存概念に、`labels` は Kubernetes / containerlab / GCP / Prometheus / Docker の
  既存概念にそれぞれ落ちる
- **RFC8345 エクスポートが素直になった** — 従来「グルーピングは RFC8345 に対応物がなく
  拡張属性にしか落ちない」と判定していたが、多軸に分離した結果、RFC8345 の multi-topology model
  本来の使い方に写像できる: `parent` → containment topology instance の `supporting-node`、
  各 labels 軸 → 軸ごとの network instance。この過去判定は撤回する
- drafts/0008 D1 の `location:` / `provider:` を `labels` に畳める
  (`labels: {location: cloud, provider: aws}`)。トップレベルのフィールド数が減る
- Phase 1 の `labels` 追加は純加算で、既存 fixture / スキーマ / バリデーターに破壊的変更なし

**悪い影響 / トレードオフ:**

- ノードが持つ「所属系」フィールドが 3 つになる。ADR での明示的な書き分け説明が必須
- `labels` が注釈側であるため、**下流ツールは特定のキーの存在を前提にできない**。
  ndl-viz が `az` でグループ分けしても、`availability_zone` と書かれたら効かない
- **未解決: 障害軸と管理軸の混在** — `labels` はフラットな map なので、`blast_radius` クエリが
  「どのキーが障害軸か」を判定できない。`blast_radius(tenant=acme)` は意味をなさないが
  コアはそれを止められない。当面は `docs/label-vocabulary.md` の分類を informative な指針とし、
  Phase 3+ で必要性が明確になった時点で障害軸を構造化構成子 (`fault_domains:` 等) に昇格させる。
  **昇格は加算的変更であり既存の `labels` を壊さない**
- `labels` の継承ルール (親の labels を子が継承するか) は未定義。Phase 1 は継承なし・明示重複許容

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer1.py` — `L1Node.labels: dict[str, str] | None` を追加 (Phase 1)
- 定数: `src/mlndl/constants.py` — `FAULT_AXIS_LABEL_KEYS` / `MANAGEMENT_AXIS_LABEL_KEYS` (informative)
- バリデーター: `src/mlndl/validator.py` — Phase 1 では検証を追加しない
- エクスポーター: `src/mlndl/exporter/cytoscape.py` — `data.labels` に転写
- サンプル: `tests/fixtures/valid_labels_multi_axis.yaml` (新規)
- 文書: `docs/label-vocabulary.md` (新規), `CLAUDE.md`, `drafts/0008`

## Alternatives Considered

### 構造の代替案

- **単一構成子で階層と多軸の両方を表現** *(6 ラウンド続けた元の方針)*: 却下。ADR-0005 D4 判定が
  2 種類で割れる以上、別構成子にすべき。「多軸と階層を 1 語で被覆する語」が英語に存在しないため
  命名が永久に収束しなかった
- **`attaches_to` に統合** (`attaches_to: {group: pod-tokyo}` の 4 キー目): 却下。
  RFC8345 supporting-node は「下位層のノードが上位層のノードを実現する」関係であり論理包含とは別物。
  ADR-0001 の D4 (multi-homing は Phase 2 まで scalar) / D5 (上位層 attach は error) /
  D6 (循環検出) / D7 (往復変換) がすべて壊れる
- **トップレベル `groups:` + `members: [...]` 列挙**: 却下。情報の局所性を破壊する
  (ノード定義を読んでも所属が分からず逆引きが必要)。ノード追加時に 2 箇所修正が必要。
  ネスト (subnet が VPC の member かつ instance のコンテナ) の記述が煩雑
- **CML Smart Annotation 方式** (箱オブジェクトを持たず tag から箱を導出): 却下。
  mlndl の箱は属性 (`cidr` / `availability_zone` / `implicit_router`) を持つ必要があり、
  tag は宿主を持たないため表現できない。YAML 試し書きで 4 段ネストに使えないことが即座に判明した。
  ただし ndl-viz の可視化 API (`parent` 連鎖からポリゴンを自動生成し、ユーザーが矩形を手で描かない)
  としては参考になる

### 多軸分類キーの命名候補

| 候補 | 却下理由 |
|------|---------|
| **`labels`** | **採用** |
| `tags` | 802.1Q VLAN tag / tagged・untagged port / QinQ と衝突。mlndl は `layer2.vlans` を実装済みで、衝突は**今そこにある**。`labels` の MPLS 衝突は未実装 (ADR-0005 D3-2 の Phase 2+ 再検討扱い) で**将来のもの**。また map 形式でも、802.1Q には Q-in-Q の outer/inner tag や VLAN name という「タグに名前を付ける」概念が実在するため型による曖昧性解消が効かない |
| `tagging` / `labeling` | 動名詞形。既存 DSL の動名詞 (`logging:` / `monitoring:` / `caching:` / `tracing:`) はすべて**機能設定セクション**であり、データの入れ物としての前例が K8s / Terraform / Ansible / Compose / Helm / Kustomize / containerlab のいずれにも存在しない。`labeling` は SRE/DevOps 文脈で ML の教師データ作成を強く連想させる |
| `facets` | 衝突ゼロで多軸表現力も最高だったが、DSL キーとしての流通実績がなく直感に訴えない |
| `annotations` | K8s が明示的に「selector に使えない非識別メタデータ」と規定しており、グルーピング用途と意味が真逆。ただし将来「識別に使わない補助情報」が必要になった際は K8s に倣って追加する拡張パスが開いている |
| `group` | LAG / BGP peer-group / security group と多重衝突。さらに **containerlab の `groups:` はパラメータ継承機構**であり、`clab graph` がその値を段組みヒントに流用している (値域は spine/leaf/server = mlndl の `role` 相当)。下流アダプター実装者が取り違える実害がある |

### 階層参照キーの命名候補 (`parent` に至るまで)

| 候補 | 却下理由 |
|------|---------|
| **`parent`** | **採用**。GCP Resource Manager (`parent: projects/foo`) / AWS Organizations (`ParentId`) の前例。音読が所有格 (`X's parent is Y`) と述語 (`X is a child of Y`) の両方で成立し、ネスト連鎖で壊れない |
| `scope` | 英語の technical usage で `scope` は一貫して**範囲・程度・レベルを示す enum を取る語**であり ID 参照を取る語ではない (K8s CRD `spec.scope: Namespaced\|Cluster` / OAuth `scope=openid profile` / RFC 4007 IPv6 address scope / RFC 2365 multicast scope)。決定打は **DHCP scope** — 「あるサブネットに対する IP アドレス範囲」であり、mlndl の箱は `cidr` を持つため `role: subnet` + `cidr:` + `scope:` が DHCP scope の教科書的シグネチャと一致し、しかも意味が反転する。Azure RBAC の `scope` は ID を取るが定義は "the set of resources that access **applies to**" (作用域) で意味方向が逆。さらに ADR-0005 の「表現スコープ」というメタ用語、drafts/0008 D4 の `scope_extent` とも語幹衝突 |
| `pod` | Cisco PoD (Point of Delivery) / ACI Multi-Pod / Facebook F4-F16 / Juniper IP Fabric のいずれでも「**物理 Clos ファブリックの増設単位**」という具体的意味が確立しており、物理が隠蔽された VPC の総称にはならない。Kubernetes Pod との衝突も致命的。`labels` の推奨軸名としてのみ採用 |
| `belongs_to` | `attaches_to` と語形が同型 (`X_to:` + 単一値) で視覚的に弁別できない。YAML 実証で「grep の頭が入れ替わってもエラーにならないコピペ事故が起きる」と判定 |
| `member_of` | 「属している」関係は伝わるが、参照先が抽象的な箱であることを喚起しない |
| `part_of` | 「spine1 は esxi-01 の part」とも読め、`attaches_to` との両義性が残る |
| `context` | Cisco NX-OS の `vrf context <name>` は VRF 定義の正式コマンド構文。ASA の security context も現役 |
| `unit` | Juniper の `unit N` はサブインターフェース定義の正式構文 |
| `frame` | Ethernet frame / PPP frame。L2 PDU の最基本用語 |
| `block` | CIDR block / IP block |
| `cell` | 5G/LTE 無線セル / ATM cell (53 バイト固定長 PDU) |
| `space` | address space / namespace。`cidr` と並ぶと区別がつかない |
| `enclosure` | disk / blade enclosure = 物理筐体。「抽象的な箱」と真逆 |
| `boundary` | 業界用法では常に「線・エッジ」であって「面・箱」ではない。OSPF ABR/ASBR とも競合 |
| `precinct` / `territory` / `province` / `estate` | ネットワーク用語との衝突はゼロだが実務者に異物感が強い。`precinct` は 4 段ネスト (「VPC の precinct が tenant」) で同格区画の含意と矛盾 |
| `domain` / `zone` / `namespace` / `container` / `tenant` / `enclave` / `compartment` / `realm` | drafts/0008 の初回検討で却下済み (多重衝突 / 既存フィールドとの衝突 / 階層潰し) |

## References

- 関連 ADR: ADR-0001 (attaches_to), ADR-0002 (ID 命名・D8 severity), ADR-0003 (role open-form・注釈側構成子のパターン), ADR-0005 (D4 判定フレームワーク), drafts/0008 (クラウドネットワーク表現)
- `docs/label-vocabulary.md` — 推奨軸名 (informative)
- RFC 8345 §4.1 — supporting-node の定義 ("another node that is in an **underlay network**")
- RFC 3031 — MPLS Architecture (label の中核性: label stack / LSR / LDP)
- RFC 4007 — IPv6 Scoped Address Architecture
- RFC 2365 — Administratively Scoped IP Multicast
- IEEE 802.1Q — VLAN tagging
- Kubernetes — labels (selector 可) / annotations (selector 不可) / ownerReferences の三層分離
- GCP Resource Manager — `parent: projects/foo` の階層参照
- AWS RAM — VPC subnet sharing (1 VPC ⊃ 複数 tenant の実在証明)
- containerlab — `labels:` (Docker labels 由来の map) / `groups:` (パラメータ継承機構)
- Cisco Modeling Labs 2.7+ — Smart Annotations (tag から箱を導出する方式)
