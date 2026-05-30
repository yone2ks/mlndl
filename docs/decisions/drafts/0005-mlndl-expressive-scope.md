# ADR-0005: mlndl の表現スコープ定義

- **Status**: Draft
- **Date**: 2026-05-29
- **Deciders**: mlndl-spec-architect (Pass A)
- **Pass**: A (初回策定)

## Context

ラウンド1 (ADR-0001〜0004) の完了直後、ユーザーが次の問題提起を行った:

> 「mlndl は **物理構成図、論理構成図、物理と論理の間の連携** を表現するための言語」
>
> 「role で spine, leaf hypervisor とか分ける必要ある?? role が広がりすぎない?? 新しい要素が出たら、都度追加するの? 何をどこまで表現する言語なのか整理した方がよい気がする。」

この発話は 2 つの問題を同時に提起している:

1. **mlndl の表現スコープが ADR として明文化されていない** — CLAUDE.md には散発的な記述 (「EVE-NG を知らない」「論文の三層モデル」等) があるが、「何を箱で表すか」「何を線で表すか」「何を扱わないか」を**機械的に判定できる**指針がない
2. **ADR-0003 で確定した 9 canonical roles の混在 (位置・機能・実行種別・管理目的)** が、「新概念が出るたびに role 語彙を増やすのか」という拡張性の不安を生んでいる

本 ADR はこの 2 問題のうち **(1) のスコープ定義のみ**を扱う。(2) は段階 2 で ADR-0003 を **Reopen** して扱う (ラウンド1.5 プラン参照)。

### 既存 ADR との関係 (Pass A 時点)

- **ADR-0001** (`attaches_to`): 物理-論理連携の中核フィールド。本 ADR が「三軸」のうち (c) を体現するメカニズムとして引用する
- **ADR-0002** (ID 命名規則): グローバル一意 ID の前提が本 ADR D2 の「層を跨ぐ `attaches_to: {interface: X}` が層を明示せず成立する」根拠
- **ADR-0003** (`role` 語彙): 本 ADR は role 語彙そのものを再判定しない。**ただし、ADR-0005 D3 の「含む / 含めない」リストが ADR-0003 再設計 (段階 2) の判定基準を提供する**
- **ADR-0004** (`implementation × role`): 「mlndl コアは技術的不可能性のみを error にする」基準と本 ADR の責務境界 (D3 表) は同じ思想軸にある。本 ADR は「どこまで表現するか」、ADR-0004 は「表現された組み合わせのうちどれを拒否するか」を扱う

### 制約

- mlndl は **EVE-NG / vCenter / NetBox / ndl-viz を知らない** (CLAUDE.md)
- 原案の三層モデル (L1/L2/L3) と RFC 8345 (multi-layer topology with supporting relationships) を継承する
- Phase 1 は **L1 のみ**を実装対象とする (CLAUDE.md「実装フェーズ」)

## Decision

### D1. mlndl の表現スコープを「三軸」で操作的に定義する

mlndl は次の三軸を表現する言語である。各軸は**何を箱として表現し、何を線として表現するか**を操作的に定義する。

#### (a) 物理構成図 — 物理的に「箱」と「ケーブル」のトポロジー

| 要素 | 定義 | mlndl での表現 |
|------|------|---------------|
| **箱** | 物理機器・ハイパーバイザホスト・VM・コンテナといった「実体」 | `layer1.nodes` (L1Node) |
| **線** | 物理ケーブル、および論理リンクの物理裏付け | `layer1.links` (L1Link) |
| **アグリゲーション primitive** | 複数物理リンクの束ね | `port_channels` (single-chassis LAG) / `mlag` (multi-chassis LAG) |

**port_channel と mlag の位置づけ**: いずれも「複数物理リンクを 1 つの論理リンクに束ねる」という**同じ意味論**の実装形式違いとして扱う。物理ポートを基盤とする論理束ねという意味で物理側 (a) と論理側 (b) の境界をまたぐが、ケーブル束ねの表現は (a) の核心概念であるため、**厳密な MECE よりも実用性を優先**して (a) に分類する。

#### (b) 論理構成図 — パケットの流れ・ブロードキャストドメイン・ルーティングドメイン

| 要素 | 定義 | mlndl での表現 |
|------|------|---------------|
| **箱** | 論理的なドメインや終端 (VLAN, VRF, VNI, BGP/OSPF/IS-IS ピア) | `layer2.vlans` / `layer3.vrfs` / `layer2.vxlan` / `protocols.bgp` 等 |
| **線** | 隣接関係・メンバーシップ・トンネル | `layer3.routing_adjacencies` / `layer2.vlans.trunk_ports` / `layer2.vxlan.members` |

論理構成は「**隣接の存在と形**」までを扱う:

- BGP / OSPF / IS-IS の隣接、`peer / local_as / remote_as / type[ebgp|ibgp] / role[underlay|overlay|route_reflector(_client)] / update_source / address_families / redistribute フラグ`
- OSPF `area`、IS-IS `level` / `area` / `system_id`
- BGP unnumbered (RFC 5549): `mode: unnumbered` フラグ、または `update_source` が loopback でない物理 IF を指している場合は unnumbered と解釈

#### (c) 物理-論理連携 — 「この論理 IF/Link はどの物理に乗っているか」

| 要素 | 定義 | mlndl での表現 |
|------|------|---------------|
| **連携プリミティブ** | 上位層が下位層の物理基盤を指す関係 | `attaches_to: {node: ...} / {interface: ...} / {link: ...}` (ADR-0001) |
| **RFC 8345 対応** | `supporting-node` / `supporting-termination-point` / `supporting-link` への可逆変換 | `exporter/rfc8345.py` が ID 逆引きで層復元 |

(c) の主役は ADR-0001 の `attaches_to` オブジェクト形式である。本 ADR は (c) を**三軸のうち独立した軸**として明示的に位置づけることで、「物理を書くだけ」「論理を書くだけ」では mlndl の本質を表現できないことを宣言する。

### D2. 三軸の境界規則

#### D2-1. インターフェース表現の層分散について

インターフェース設定が L1/L2/L3 に分かれることについては、意図的な設計決定として維持する。

**根拠**: 同一の「インターフェース」という概念が、物理・論理・アドレッシングの 3 つの異なる観点で表現される。OpenConfig のようなネスト構造でも Cisco IOS のような単一エンティティでもなく、RFC 8345 の多層 supporting モデルに従って**層別コレクション + attaches_to 参照**で表現する。

| 層 | 役割 | 例 |
|----|------|-----|
| `layer1.interfaces` | 物理ポート (ケーブルが挿さる「箱の口」) | `leaf1-swp51` (実体としての NIC/Port) |
| `layer2.subinterfaces` | VLAN タグ付き endpoint (L2 論理チャネル) | `leaf1-swp1.100` (parent + vlan_id) |
| `layer3.interfaces` | IP 終端を包含 (loopback / SVI / 物理 routed / tunnel) | `leaf1-lo`, `leaf1-vlan-100`, `leaf1-swp51-l3` |

**なぜこの分散が適切か**:

1. **三軸定義の帰結**: (a) 物理の「口」と (b) 論理の「IP 終端」は異なる概念軸にある。同一 entity に押し込めると三軸の境界が曖昧になる
2. **RFC 8345 との整合**: supporting termination-point の構造を忠実に表現できる。エクスポーター (`rfc8345.py`) での可逆変換が成立する
3. **attaches_to の意味論**: 「L3 IF が L1 物理ポートを supporting として持つ」という supporting 関係を `attaches_to` で明示的に表現できる
4. **DC エンジニアとの乖離について**: 現場では「swp51 一つ」として扱うが、mlndl は中間フォーマット (ユーザーが直接書く第一形式ではない)。ndl-viz 等が現場ビューを再構成する

**OpenConfig 風のネスト構造を採用しない理由**: OpenConfig は設定モデルで、nodes[].interfaces[].subinterfaces[].ipv4 のネスト構造を持つ。mlndl はトポロジー記述モデルであり、attaches_to で層間連携を表現する設計思想と根本的に異なる。採用すると参照パスが複雑化し、ADR-0001 の attaches_to の意味が失われる。

#### D2-2. 「物理ポートは L1、L3 IP 終端は L3」の一意化規則

`routed 物理 IF` (例: leaf1 の swp51 に 10.1.0.1/31 が直接乗る場合) は次の二段表現を採る:

- **L1 側**: `layer1.interfaces[id=leaf1-swp51]` (物理ポートとして)
- **L3 側**: `layer3.interfaces[id=leaf1-swp51-l3, attaches_to: {interface: leaf1-swp51}]` (IP 終端として)

両者を `attaches_to` で繋ぐ。OpenConfig 風に L1 ポートに直接 IP を生やすことは**しない**。

#### D2-3. `attaches_to: {interface: X}` は層を明示しない

ADR-0002 (グローバル一意 ID) の前提により、X は単一のオブジェクトに解決される。`{layer: layer1, interface: X}` のような層プレフィックスは ADR-0001 で廃止済み。

#### D2-4. RFC 8345 supporting termination-point モデルへの準拠

`attaches_to` は RFC 8345 の supporting 3 種 (node / TP / link) に**可逆変換可能**な形を保つ。

#### D2-5. MAC アドレスの責任分界

mlndl は MAC アドレスを**原則扱わない**。

例外候補 (Phase 2 以降に確定):
- `gateway_redundancy.anycast_mac` (EVPN anycast gateway 用)
- MLAG `system-mac`

これらは「上位ツール導出」(eve-lab-builder 等が自動生成) と「L3/MLAG スキーマに例外的に保持」の二択を Phase 2 で再判断する。Phase 1 では含めない。

#### D2-6. port_channel と MLAG の境界

D1 で述べた通り、両者は「複数物理リンクの束ね」意味論の実装形式違いとして (a) に分類する。厳密な MECE (論理側 (b) に分類する案) は本 ADR では採用しない。

### D3. 確定スコープ — 含む / 含めない

#### D3-1. 含む (Phase 1 + Phase 2)

**(a) 物理構成図要素 (Phase 1):**

- `nodes` (L1Node): `id`, `name`, `implementation` (`vm|physical|container`), `attaches_to`, `role`, `device_type`, `overrides`
- `interfaces` (L1Interface): `id`, `node`, `name`, `attaches_to` (任意)
- `links` (L1Link): `id`, `from`, `to`, `link_speed`, `mtu`, `link_role` (`underlay|access|peer-link|management|uplink`)
- `port_channels`: `id`, `node`, `members`, `lacp` (`mode`, `min_links`)
- `mlag`: `id`, `nodes`, `peer_link`, `peer_link_interface`, `domain_id`
- 表示メタ: `name`, `description`, `comment` (任意, 全構成要素)

**(b) 論理構成図要素 (Phase 2 で本格実装):**

- `layer2.vlans`: `id`, `vlan_id`, `trunk_ports`, `access_ports`
- `layer2.subinterfaces`: `id`, `parent` (L1 IF), `vlan_id` (VLAN タグ付き endpoint)
- `layer2.vxlan`: `id`, `type: l2vni | l3vni`, `vni`, `vlan` / `vrf`, `vtep_source`, `members`, `irb_mode`
- `layer3.vrfs`: `id`, `rd`, `l3vni`, `route_targets`
- `layer3.interfaces` (IP 終端を包含): `id`, `node`, `interface`, `ip` (IPv4/IPv6), `vrf`, `attaches_to`, `gateway_redundancy` (`anycast_gateway | VRRP`, `vip`)
- `layer3.tunnel_interfaces`: GRE / IPIP / IPSec VTI
- `layer3.tunnel_links`: `from`, `to` (両端の明示的な結びつき)
- `layer3.routing_adjacencies`: `id`, `type` (`bgp|ospf|isis`), `from`, `to`, `attaches_to: {link: ...}`
- `protocols.bgp`: `role: underlay | overlay`, `nodes[].local_as`, `neighbors[].remote_as`, `type[ebgp|ibgp]`, `role[route_reflector(_client)]`, `update_source`, `address_families`, `redistribute フラグ`
- `protocols.ospf`: `area`, `router_id`, `redistribute`
- `protocols.isis`: `level`, `area`, `system_id`
- `protocols.bfd`: `min_tx`, `min_rx`, `multiplier` (**隣接 timer の唯一の例外**として保持)

**(c) 物理-論理連携 (Phase 1 から実装):**

- `attaches_to: {node: ...} / {interface: ...} / {link: ...}` (ADR-0001)

**特殊な隣接形式 (b の補足):**

- BGP unnumbered (RFC 5549): `routing_adjacencies` で `mode: unnumbered` フラグ、または `update_source` が loopback でない物理 IF を指している場合は unnumbered と解釈

**L3 アドレッシングの粒度:**

- interface IP (IPv4 / IPv6 両対応), prefix length, loopback IP, anycast VIP, RD, RT, AS 番号, router-id

#### D3-2. 含めない (Phase 1 確定。行き先を明示)

| 領域 | 行き先 |
|------|-------|
| **静的ルート (static route)** | Phase 2 で再判断 (redistribute フラグでの存在表明は許容) |
| **L2 トンネル (EoGRE / L2TPv3 / OTV)** | Phase 2 で再判断 (VxLAN は既存 `layer2.vxlan` 維持) |
| **ACL / NAT / Firewall policy / route-map / prefix-list** | 上位ツール (Ansible / NetBox config context) |
| **DHCP relay (helper-address)** | 上位ツール (ACL/NAT 同様の運用ポリシー設定) |
| **MAC アドレス全般 (anycast MAC / MLAG system-mac 含む)** | mlndl では原則扱わない。`gateway_redundancy.anycast_mac` / MLAG `system-mac` は Phase 2 以降に「上位ツール導出」vs「L3/MLAG スキーマ例外」の二択で再判断 |
| **WireGuard トンネル** | Phase 2+ (NOS native 非対応のため。Phase 1 スコープは GRE / IPIP / IPSec VTI のみ) |
| **EVPN advertise フラグ群** (`advertise-default-gw` / `advertise-svi-ip` / `advertise-pip`) | Phase 2 で再判断 (運用ポリシーかトポロジー意図かの境界要検討) |
| **BGP community / ECMP 設定 / BGP・OSPF・IS-IS timer (BFD 除く) / BGP 認証 / IPv6 RA / SLAAC 詳細チューニング** | 上位ツール |
| **L2 機能フラグ** (LLDP / CDP / STP / IGMP snooping / ARP suppression / Storm control / PortFast / BPDU guard) | 上位ツール |
| **物理配置** (rack / site / cabinet) | Phase 2 で再検討 (NetBox 領域候補) |
| **機種スペック** (CPU / RAM / template) | `eve-lab-builder/config/device_mapping.yaml` |
| **ケーブル詳細** (タイプ / 長さ / トランシーバ) | デプロイ詳細 |
| **仮想化詳細** (Container image / CNI / OVS / netns / veth) | デプロイ・OS 領域 |
| **アプリ・サービス層** (DHCP / DNS / NTP / AAA / SNMP / Syslog / LB pool) | サービス層 |
| **フロー監視** (sFlow / NetFlow / IPFIX) | 運用監視層 |
| **別パラダイムプロトコル** (PIM / MPLS-LDP / SR / IPsec / DMVPN) | Phase 2+ |
| **運用設定** (admin_up / power_state / STP priority) | 運用状態側 |
| **フロー制御** (flow control / PFC / DCB / ETS / DCBX) | 運用設定 (RoCE/AI 用途は Phase 3+ で再判断) |
| **可視化レイアウト指示** (座標 / 色 / アイコン) | ndl-viz / Cytoscape スタイル |

### D4. 「構成要素」と「注釈」の判定枠組 (適用は段階 2 結論後)

ADR-0005 は判定**枠組**としてのみ提示する。`role` や `description` 等の個別語彙への適用は **ADR-0003 再設計 (段階 2) 完了後に Consequences へ追記する**。本 ADR が段階 2 の結論を先取りすると循環参照になるため。

#### D4-1. 判定基準

| 種別 | 操作的特徴 |
|------|----------|
| **構成要素そのもの** | (1) 削除すると参照整合性が崩れる<br>(2) RFC 8345 ノードグラフから消える<br>(3) トポロジーの意味 (broadcast_domain, blast_radius 等) が変わる |
| **注釈** | (1) 削除しても参照整合性は維持される<br>(2) 可視化や分類のヒントにすぎない<br>(3) 値の変更で意味境界が変わらない |

#### D4-2. 段階 2 を縛らない範囲での明確な適用例

- **`description` / `comment`**: 注釈側として全構成要素に optional 許可
- **`gateway_redundancy.protocol: anycast_gateway` のような enum 値**: 値の変更で動作意味が変わるため、注釈ではなく**運用パラメータ**として扱う

#### D4-3. 段階 2 で適用予定の項目

- `layer1.nodes.role` (段階 2 で ADR-0003 を Reopen し α/β/γ/δ/ε の 5 案で再評価)
- canonical 語彙のオープン/クローズ判定

これらは ADR-0003v2 (Pass A2 → C2) の結論を待ち、本 ADR の Consequences に**事後追記**する。

### D5. 三軸と Phase 1/2 の対応

| Phase | 実装対象 | 軸 |
|-------|---------|----|
| **Phase 1** | L1 entities (nodes / interfaces / links / port_channels / mlag) + `attaches_to` の supporting model | (a) 物理構成図のみ |
| **Phase 2** | L2 / L3 / protocols スキーマ、`routing_adjacencies`, `vxlan`, `vrf`, `tunnel_interfaces`, validator 完全実装 | (b) 論理構成図 + (c) 物理-論理連携の本格運用 |
| **Phase 3+** | 別パラダイムプロトコル (PIM / MPLS-LDP / SR)、broadcast_domain / blast_radius クエリ拡張、追加ユースケース | 拡張 |

## Consequences

### 良い影響

- **スコープの操作的判定が可能**: 新概念 (例: `sdn-controller`, `dpu-offload`, `service-mesh`) が出現した際、D3 表と D4 枠組に照らして「含む / 含めない」を機械的に判定できる
- **論文継承の明文化**: 原案の三層モデル + RFC 8345 supporting model が ADR レベルで明示される
- **ADR-0003 再設計の指針提供**: D3-2「含めない」リストおよび D4 判定枠組が、段階 2 での role 語彙再評価の判定軸を提供する
- **インターフェース表現の一貫性**: 「物理は L1、論理 (VLAN タグ) は L2、IP 終端は L3」という分類軸が明示され、ADR-0001 の attaches_to 設計が完結する
- **「mlndl は EVE-NG を知らない」原則の構造化**: D3-2 の「含めない」リストで具体化される

### 悪い影響 / トレードオフ

- **インターフェースの「二重表現」负担 (D2-2)**: routed 物理 IF を L1 と L3 両方に書く規範を採用したため、YAML が若干冗長になる。ただし RFC 8345 supporting model との往復変換性が担保される
- **port_channel / MLAG の MECE 妥協**: 厳密には論理束ね (b) だが実用性を優先して (a) に分類。Phase 2 で `bundles` 統合議論が再燃する可能性
- **D4 の段階 2 先送り**: 本 ADR の Consequences は段階 2 完了後に追記が必要な不完全な状態で Accepted になる
- **「含めない」リストの保守負担**: 新技術出現時に D3-2 表を更新する判断が必要

### 影響を受けるコンポーネント

- **スキーマ** (`src/mlndl/schema/`): Phase 1 (`layer1.py`) の field 定義範囲を D3-1 に揃える
- **バリデーター** (`src/mlndl/validator.py`): D3-2 の「含めない」要素がフィールドとして書かれた場合は `extra="forbid"` で拒否
- **エクスポーター** (`src/mlndl/exporter/rfc8345.py`): D2-4 (RFC 8345 supporting model への可逆性) を担保
- **サンプル** (`tests/fixtures/`): Phase 1 fixtures は D3-1 (a) のみで構成
- **ADR-0003 (再設計予定)**: 本 ADR の D3 + D4 が直接の入力となる
- **ADR-0004 (条件付き影響)**: 段階 2 で `role: hypervisor` 語彙が変わる場合、ADR-0004 D-1 の文言調整が必要

## Alternatives Considered

### 採用案: 三軸 (物理 / 論理 / 物理-論理連携) + RFC 8345 supporting model + 層分散 (D1-D5)

- ユーザー発話「物理構成図、論理構成図、物理と論理の間の連携」に最も直接的に対応
- 原案の三層モデル (L1/L2/L3) と RFC 8345 を継承
- ADR-0001〜0004 の既存決定と矛盾しない

### 却下案 A: 単一フラット (OpenConfig 風) 構造

すべてのインターフェース・隣接・VLAN を単一のコレクションにネストし、`type` フィールドで判別する。

**却下理由**:
- RFC 8345 の multi-layer topology モデルから乖離。supporting-TP の対応関係が失われる
- ADR-0001 の `attaches_to` が「同一コレクション内の参照」になり、層間連携という概念自体が薄まる
- OpenConfig は**設定モデル**、mlndl は**トポロジー記述モデル**で設計思想軸が異なる

### 却下案 B: スコープを物理 (a) のみに限定

mlndl を「物理トポロジー記述言語」と再定義し、論理層 (b) は別パッケージへ。

**却下理由**:
- ユーザー発話が明示的に「論理構成図」と「物理と論理の間の連携」を含めている
- broadcast_domain / blast_radius クエリは L2/L3 を含む層構造を前提とする
- 原案の三層モデルを 1 層に縮小することは論文継承性に反する

### 却下案 C: より広いスコープ (運用ポリシー込み)

ACL / NAT / DHCP relay / route-map / 設定パラメータも mlndl に含める。

**却下理由**:
- 「mlndl は EVE-NG を知らない」原則 (CLAUDE.md) と矛盾
- ADR-0004 の「mlndl コアは技術的不可能性のみ error」の関心分離原則と整合しない

### 却下案 D: RFC 8345 完全準拠 (`supporting-node` / `supporting-tp` / `supporting-link` を 3 別フィールドに復元)

**却下理由**:
- ADR-0001 で確定済みの「`attaches_to` 統一」を覆す
- RFC 8345 互換性はエクスポーターで十分担保される (ADR-0001 D7)

## References

- [ADR-0001](../0001-attaches-to.md) — `attaches_to` の使い分け基準 (本 ADR の (c) の中核メカニズム)
- [ADR-0002](../0002-id-naming-convention.md) — ID 命名規則とグローバル一意性 (本 ADR D2-3 の前提)
- [ADR-0003](../0003-role-vocabulary.md) — `role` 語彙 (段階 2 で本 ADR を入力に Reopen 予定)
- [ADR-0004](../0004-implementation-role-matrix.md) — `implementation × role` (本 ADR と関心分離思想を共有)
- `CLAUDE.md`
- ラウンド1.5 の作業プラン (リポジトリ外) — ラウンド1.5 全体プラン
- RFC 8345 — A YANG Data Model for Network Topologies
- RFC 8346 — A YANG Data Model for Layer 3 Topologies
- RFC 8943 — A YANG Data Model for Layer 2 Network Topologies
- MLNDL 原案 (NAIST, 2011) の論文 (手元の場所は CLAUDE.local.md)
