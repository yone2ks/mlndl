# ADR-0008: クラウドネットワークの表現 — `parent` / `labels` グルーピングと `location` 軸

- Status: Draft (`labels` のみ実装済み。始めるきっかけは [先送りした項目](../deferred.md))
- Pass: C (2026-09-15 改訂 — 旧 `scope` 案を撤回)
- 関連: ADR-0001 (attaches_to), ADR-0002 (ID 命名), ADR-0003 (role open-form), ADR-0005 (表現スコープ),
  ADR-0006 (endpoints), **ADR-0009 (メンバーシップ構成子の直交性)**, 0007-draft (レイヤー中心モデル=案B)

> **改訂履歴**: 初版は所属参照を `scope: <box-id>` としていたが、6 ラウンドの再検討の結果撤回した。
> 詳細な却下理由と代替候補の全リストは [ADR-0009](../0009-membership-orthogonality.md) を参照。

## Context

AWS VPC / Azure VNet / GCP VPC / OCI VCN のようなクラウド論理ネットワークを
mlndl でどう表現するか。VPC は物理基盤が完全に隠蔽された「純論理ネットワーク」であり、既存の
「L1=物理必須」前提 (ADR-0005 D1) と衝突する。

論点は 3 つに集約された:
1. クラウド固有型 (`cloud-vpc` 等) は特化しすぎではないか → 「cloud」は単なる所在では
2. VPC は特殊型でなく「ネットワーク要素をまとめる箱」として整理できないか
3. **その「箱への所属」をどう書くか** ← 6 ラウンド難航し、ADR-0009 で決着

## Decision

### D1. `type: cloud-*` 特化を廃止し、`location` 軸を導入

クラウド固有型 (`cloud-vpc` / `cloud-subnet` / `cloud-igw` …) は語彙爆発を招くため作らない。
代わりに、要素の「所在」を表す **`location`** を type と直交する注釈軸として持たせる。

- 値域: `cloud` / `on-prem` / `edge` … open-form (ADR-0003 と同じ思想、コアは値域非強制)
- 任意で `provider: aws | azure | gcp | oci` を併記
- クラウドとオンプレは**同一スキーマ**で書け、差分は属性のみ (実証で約 80% 共通)

> **未決 (Phase 3)**: `location` / `provider` は ADR-0009 D1 の分類軸そのものであり、
> `labels: {location: cloud, provider: aws}` に畳める。トップレベルのフィールド数を減らせるが、
> 専用フィールドの方が発見性が高いという反論もある。Phase 3 実装時に確定する。

### D2. 箱への所属は `parent` (階層) と `labels` (多軸) の 2 構成子で表現

VPC / VNet / pod / tenant は「要素をまとめる論理的な箱」として表現する。
箱に固有の新構成子・新型・新語は作らない。

**箱そのものも普通のノード**: `role: vpc` / `role: pod` (種別は open-form の `role` が担う)。
箱がノードであることにより、`cidr` / `extent` / `implicit_router` などの属性を持てる。

所属の表現は 2 つの直交した構成子に分ける (詳細は [ADR-0009](../0009-membership-orthogonality.md)):

| 構成子 | 意味論 | 多重性 | 値 |
|--------|--------|--------|-----|
| `parent: <box-id>` | **階層ネスト** (単一軸)。連鎖でネストを表現。`broadcast_domain` 等の構造クエリが辿る | 単一 | 既存 node ID 参照 |
| `labels: {axis: value}` | **多軸フラット分類**。az / pod / tenant / env のような直交軸を並列に付与 | 多重 (map) | 自由文字列 (**非参照**) |

```yaml
layer1:
  nodes:
    - {id: vpc-prod,   role: vpc,     location: cloud, provider: aws, cidr: 10.0.0.0/16, extent: region}
    - {id: subnet-web, role: subnet,  location: cloud, parent: vpc-prod, cidr: 10.0.1.0/24,
       labels: {az: ap-northeast-1a, tenant: acme}}
    - {id: web-1,      role: server,  location: cloud, parent: subnet-web, implementation: vm,
       labels: {az: ap-northeast-1a, tenant: acme, env: prod}}
    - {id: igw-prod,   role: gateway, kind: internet-gateway, parent: vpc-prod}

    # オンプレの箱も同じ書き方
    - {id: pod-tokyo,  role: pod,     location: on-prem, labels: {az: az-1a, site: tokyo}}
    - {id: leaf1,      role: leaf,    location: on-prem, parent: pod-tokyo,
       attaches_to: esxi-01, labels: {az: az-1a, tenant: acme}}
```

`parent` は `attaches_to` (supporting / 物理基盤依存) とは**直交した別概念** (Containment ≠ Realization)。
`labels` はさらにそのどちらとも直交する (Classification)。三者の関係は ADR-0009 D1 の表を参照。

### D3. 三軸の整理 (旧「縦と横」を改定)

初版は「縦 = `attaches_to`、横 = peer 接続」の二分法だったが、これは不完全だった。正しくは 3 軸ある。

| 軸 | 意味 | 構成子 |
|----|------|--------|
| **Realization** | B の上で動く / B によって実現される | `attaches_to` (クラウドでは省略可 = 物理隠蔽) |
| **Containment** | B の境界の中に存在する | `parent` |
| **Adjacency** | B と対等に通信する | `endpoints:` / link (VPC ピアリング / TGW / Direct Connect / VPN) |

Adjacency は縦では表せない対等接続であり、ADR-0006 の `endpoints:` 慣習を流用した無向リンクとして
表現する (詳細構文は Phase 3 で確定)。

### D4. 箱の属性 (技術的な意味差の吸収)

クラウド間・オンプレ間の意味差を吸収するため、`role: vpc` / `pod` の箱は以下を持てる:

- `extent`: `region` | `global` (GCP VPC はグローバル、AWS/Azure/OCI はリージョン境界)
  - **旧名 `scope_extent` から改名** — 所属参照が `scope` でなくなったため語幹衝突が解消し、
    かつ `scope` は英語では本来この enum 用法が自然 (ADR-0009 の却下理由を参照)
- `implicit_router`: bool (AWS の暗黙ルータ。オンプレは明示機器)
- サブネットの `availability_zone` (AWS/OCI の AZ 縛り。オンプレは対応物なし = 任意)
  - `labels: {az: ...}` との重複に注意。**AZ 制約が規範的意味を持つ場合のみ**専用フィールドを使い、
    単なる分類は `labels` に置く。Phase 3 で線引きを確定する

### D5. スコープ外 (policy 層)

Security Group / NACL は stateful policy でありトポロジーではない。mlndl のスコープ外
(将来 `policies:` 構成子を別途検討、ADR-0005 の線引きに従う)。

## Consequences

- **ADR-0005 D1 を改定**: 「L1=物理必須」→「物理層は任意 (クラウドは物理を省略できる)」
- サブネット ≠ L2 ブロードキャストドメイン (クラウドは BUM 不在、L3 のみ)。
  Phase 2 の `broadcast_domain` クエリはクラウドサブネットを L2 ドメインと誤認しないこと。
  `location: cloud` かつ `role: subnet` は L2 非依存として扱う
- 語彙爆発を回避し、新プロバイダは `role` / `kind` を足すだけで対応可能
- `pod` は箱の「総称」ではなく `role` の推奨語彙の一つ (オンプレ DC の増設区画 = Point of Delivery)。
  Kubernetes Pod ではない旨を `docs/role-vocabulary.md` に注記すること
- **RFC8345 エクスポート**: `parent` → containment topology instance の `supporting-node`、
  各 `labels` 軸 → 軸ごとの network instance。初版の「拡張属性にしか落ちない」判定は ADR-0009 で撤回済み
- **Cytoscape エクスポート**: `parent` は compound node の `parent` プロパティに 1:1 でマップでき、
  ネストが自然に可視化される。`labels` は `data.labels` に転写 (Phase 1 実装済み)
- 既存 fixtures には影響なし (`parent` は Phase 3+、`labels` は純加算)

### Phase 別の実装

| Phase | `labels` | `parent` |
|-------|----------|----------|
| **Phase 1** (L1 のみ) | **実装済み** — `L1Node.labels: dict[str, str] \| None`、検証なし | 実装しない |
| Phase 2 (L2/L3/protocols) | 全エンティティへ横展開 (link / lag / vlan / vxlan / vrf / adjacency) | 実装しない |
| Phase 3+ (クラウド + クエリ) | 継続 | 本 ADR の受理と同時に実装 |

Phase 1 で `parent` を入れない理由: L1 単層では用途が `attaches_to` と重複気味であり
(VM ↔ hypervisor は既に `attaches_to` で表現済み)、VPC/pod の導入と同時に設計した方が
意味論の一貫性が保てるため。

### 未解決事項

- **障害軸と管理軸の混在**: `labels` はフラットな map なので、`blast_radius` クエリが
  「どのキーが障害軸か」を判定できない。当面は `docs/label-vocabulary.md` の分類 (障害軸 / 管理軸) を
  informative な指針とし、Phase 3+ で必要なら構造化構成子 (`fault_domains:` 等) に昇格させる
  (加算的変更のため既存の `labels` を壊さない)
- `location` / `provider` を `labels` に畳むか (D1 の注記)
- `availability_zone` 専用フィールドと `labels: {az: ...}` の線引き (D4)
- `labels` の継承ルール (親の labels を子が継承するか)。Phase 1 は継承なし・明示重複許容
- `parent` チェーンの validator 要件 (参照整合性 / 循環 / 自己参照はいずれも error)

## 却下した代替案

### 構造

- `type: cloud-vpc` 特化 → 語彙爆発。却下
- VPC = VRF エイリアス → VRF は L3 転送分離、VPC はサブネット群 + 境界の複合。粒度違い。却下
- **所属を単一構成子で表現** (階層と多軸を 1 語で被覆) → ADR-0005 D4 判定が 2 種類で割れるため不可。
  これが 6 ラウンドの命名難航の根本原因だった。ADR-0009 で 2 構成子に分離して決着
- **`attaches_to` への統合** (`{group: ...}` の 4 キー目) → ADR-0001 の D4/D5/D6/D7 が壊れる。却下
- **トップレベル `groups:` + `members: [...]` 列挙** → 情報の局所性を破壊。却下
- **CML Smart Annotation 方式** (箱オブジェクトなし、tag から導出) → 箱が属性を持てない。却下

### 命名

箱の所属参照および多軸分類キーの命名候補は **20 語以上を検討**した。
全候補と却下理由の一覧は [ADR-0009 の Alternatives Considered](../0009-membership-orthogonality.md#alternatives-considered) に集約している。

主要な却下語のみ再掲:

- `scope` (初版案) → DHCP scope / RFC 4007 / RFC 2365 との衝突。英語では enum を取る語で ID 参照を取らない
- `pod` → Cisco PoD / ACI Multi-Pod の「物理 Clos 増設単位」が確立。k8s Pod とも衝突。`role` 値としてのみ採用
- `belongs_to` → `attaches_to` と語形同型で弁別不能
- `group` → LAG / BGP group / security group、および **containerlab のパラメータ継承機構 `groups:`** と衝突
- `tags` → 802.1Q VLAN tag と衝突。mlndl は `layer2.vlans` 実装済みで衝突が現在進行形
- `domain` / `zone` / `namespace` / `container` / `tenant` / `enclave` / `compartment` / `realm` → 多重衝突・既存フィールドとの衝突・階層潰し

## 再検討の記録 (2026-11-07)

L1 の整理の中で、`parent` を今 (ndl_version 1.x の加算的な変更として) 入れるかを 5 エージェント
(spec-architect / linguist / dsl-designer / network-tech-reviewer / example-author) で再検討した。
**結論: 今は入れない。** 始めるきっかけは [先送りした項目](../deferred.md) の `parent` の行。

### 一致した点

| 論点 | 結論 |
|---|---|
| 名前 | `parent` のまま。GCP Resource Manager・AWS Organizations・Cytoscape の compound node・NetBox と同じ語。ADR-0011 D8 でサブ IF の親参照を `attaches_to` に移したので、構文の中で衝突する用法はない |
| 箱の置き場所 | 本 ADR D2 のとおり `layer1.nodes` に `role` で置く。別の区画 (`groups:` など) は試し書きでも局所性が崩れ、事業者網の箱 (ADR-0017) が `nodes` に残るため箱が 2 か所に分かれる。区画名の候補 (`domain` / `zone` / `scope` など) は ADR-0009 で却下済み |
| `parent` を持てるもの | L1 ノードだけ。VLAN・VRF・L3 IF は別の参照で所属を書けるので、足すと重なる |
| 親の数 | 1 つ |
| 検査 | 参照先の存在 (`Ref`)・自己参照・循環は error。「指した先が箱か」は検査しない (`role` の値に意味を持たせない。ADR-0003) |

### 今入れない理由

- 需要がクラウドに偏っている。オンプレ・WAN・ラボのサイト・pod・ラックは `labels` で足りる (ADR-0017 D1)。VPC ⊃ subnet ⊃ VM の入れ子は `labels` では書けない
- 親が 1 つだと、物理の階層 (サイト ⊃ ラック) と論理の階層 (fabric ⊃ pod) の交差を書けない。試し書きで、1 つのラックに別の pod の leaf が同居する例が出た。`labels` なら並べて書ける
- 今入れると、親を書くためだけの属性のない箱が増え、`labels.site` と `parent` の書き方が混ざる。どちらも ADR-0017 で決めたばかりの方針に逆行する
- 箱を `layer1.nodes` に置くことは、本 ADR の「ADR-0005 D1 を改定 (物理層は任意)」を受理しないと筋が通らない。ADR-0017 の事業者網の箱は、すでに同じ前提に立っている

### 入れるときに決めること

- `parent` は属性 (`cidr` など) を持つ箱にだけ使い、属性のない軸は `labels` に残す (規約として示す)
- subnet はノードではなく、属性を持つ L3 のプレフィックスである。箱として書くなら、転送の経路ではなく分類のためと明記する。L3 IF の `ip` が subnet の `cidr` に入るかの照合を検討する
- `parent` にしないもの: 事業者網の箱 (拠点は箱につながるのであって属さない)、VRF、MLAG ドメイン、EVPN の ES、仮想スタック (VSF / IRF)
- `labels.site` と `parent` を両方書いたときの扱い (どちらも残し、食い違いは検査しない案が出た)
- `attaches_to` と `parent` は独立した軸とし、ホストの `parent` を VM に継承させない (`labels` の継承と一緒に決める)
- 障害範囲は `parent` ではなく、障害軸の構成子 (ADR-0009 の未解決事項) で扱う
