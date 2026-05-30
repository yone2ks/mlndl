# ADR-0003: `layer1.nodes.role` 語彙の確定

- **Status**: Draft
- **Date**: 2026-05-27
- **Deciders**: mlndl-spec-architect (Pass A)
- **Pass**: A (初回策定)

## Context

`layer1.nodes[].role` は物理/論理ノードの「役割」を表すフィールドで、可視化時のアイコン選択 (ndl-viz の `icon_role_map.yaml`)・レイアウト制約 (Spine-Leaf 整列)・eve-lab-builder の展開可否判定 (`role: hypervisor` はラボに展開しない) など多方面に影響する。

設計プラン (eve-ng-greedy-goblet.md) では以下の語彙が提案されている:

| role | implementation | 出典 |
|------|----------------|------|
| `spine` | vm / physical / container | 設計プラン |
| `leaf` | vm / physical / container | 設計プラン |
| `core` | physical | 設計プラン |
| `border` | vm / physical | 設計プラン |
| `host` / `server` | vm / physical / container | 設計プラン (両者を併記) |
| `hypervisor` | physical | 設計プラン |
| `vswitch` | vm | 設計プラン |
| `dvswitch` | vm | 設計プラン |

論点:

1. **`host` と `server` の重複** — どちらかに統一すべきか、意味的差異を残すか
2. **追加候補**: `router`, `firewall`, `load_balancer`, `tor`, `eor` 等
3. **複数役割**: 「border-leaf」のような兼任ノードをどう表現するか
4. **enum か文字列か**: pydantic `Literal[...]` で閉じた enum にするか、自由文字列か
5. **Phase 1 (L1 のみ) の最小セット vs 将来拡張**

## Decision

**Pass A 案: Phase 1 最小セットを Literal で確定 + 拡張用 `Literal | str` ハイブリッドにフォールバック許可。**

### Phase 1 語彙 (Literal で確定)

```python
RoleLiteral = Literal[
    # データセンター系
    "spine",
    "leaf",
    "tor",           # Top-of-Rack — leaf より一般的な業界用語として追加
    "core",
    "border",
    # エンドノード系
    "server",        # host を server に統一 (host を削除)
    # 仮想化基盤系
    "hypervisor",
    "vswitch",
    "dvswitch",
    # 汎用ネットワーク機器系
    "router",
    "firewall",
    "load_balancer",
]

# 拡張: Literal 外の値も受け入れる (warning を出す)
Role = Union[RoleLiteral, str]
```

### 主な決定

1. **`host` を削除、`server` に統一**: `host` は「ホストマシン」と「エンドノード」の両義があり混乱を招く。ホストマシンは `hypervisor` ロールが担う。エンドノードは `server` で統一。

2. **`tor` を追加**: Top-of-Rack の略語として業界標準。`leaf` と意味が近いが、Three-Tier 等の非 Clos アーキテクチャで区別したいケースに対応。

3. **`router` / `firewall` / `load_balancer` を Phase 1 で追加**: 原案のオリジナル概念は汎用的なネットワーク仮想化を想定しており、DC 特化に絞らない方が将来拡張に強い。

4. **`eor` (End-of-Row) は Phase 2 以降で検討**: 現代 DC ではほぼ消滅しており、Phase 1 では含めない。

5. **複数役割の表現**: `role` は単一値。兼任ロールは Phase 2 で `tags:` 補助フィールドの導入を検討。Phase 1 では単一 role のみ。

6. **`Literal | str` ハイブリッド**: 未知の role 値 (例: `wan_accelerator`) を完全に拒否せず、warning を出した上で受け入れる。neteye / NetBox アダプターから未知 role が出てきたとき、パースを止めずに pass-through できるようにするため。

### YAML 例

```yaml
layer1:
  nodes:
    - id: spine1
      role: spine              # OK (Literal にマッチ)
    - id: fw1
      role: firewall           # OK (Phase 1 で追加)
    - id: server1
      role: server             # OK (host から統一)
    - id: custom1
      role: wan-accelerator    # warning (Literal にマッチしないが許容)
```

### eve-lab-builder への影響

- `role: hypervisor` / `vswitch` / `dvswitch` は EVE-NG にデプロイしない (既決)
- `role: server` / `router` / `firewall` / `load_balancer` は `device_type` で実体決定
- 未知 role は eve-lab-builder 側で fallback (汎用 Linux VM として展開)

## Consequences

**良い影響:**

- `host`/`server` 重複の解消で学習コスト低下
- DC 特化語彙 (spine/leaf/tor/core/border) と汎用語彙 (router/firewall/lb) を両立
- Literal による型安全性 (IDE 補完・タイポ検出) を Phase 1 から享受
- `Literal | str` ハイブリッドにより未知 role でもアダプターが破綻しない

**悪い影響 / トレードオフ:**

- `host` 廃止により過去ドキュメントの書き換えが必要 (現状サンプルでは `server1` を使っており影響は小)
- `Literal | str` のハイブリッドは pydantic 上で warning ロジック (`field_validator`) が必要
- カスタム role は ndl-viz 側で default レイアウト扱い (Spine-Leaf 整列等の恩恵を受けられない)

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer1.py` の `L1Node.role` フィールド
- バリデーター: 未知 role の warning ロギング (blocking しない)
- エクスポーター: `exporter/cytoscape.py` の `classes: role-<role>` 生成
- サンプル: `tests/fixtures/valid_l1_simple.yaml` で `server` を使用 (統一済み)
- 文書: CLAUDE.md の role 語彙まとめ表を本 ADR の語彙に更新

## Alternatives Considered

- **案A** *(採用案)*: `host` → `server` 統一、`router`/`firewall`/`lb`/`tor` 追加、`Literal | str` ハイブリッド
  - 型安全性と拡張性の両立

- **案B**: DC 特化セットと汎用セットを別 enum で管理し用途に応じて切り替え
  - 却下理由: 切り替えトリガーが不明確で実装複雑度が高い。1 つの Literal にまとめる方が単純。

- **案C**: `role` を完全にユーザー定義文字列にし ndl-viz 側の `icon_role_map.yaml` で全マッピングを管理
  - 却下理由: タイポを検出できない。Spine-Leaf レイアウト等の構造的制約をスキーマレベルで保証できない。

- **案D**: `host` と `server` を両方残す (意味的差異を仕様で明文化)
  - 却下理由: 利用者が判断を迫られる。アダプターのマッピング規則も二重に必要。情報量が増えるメリットは低い。

## Pass A との差分 *(Pass C のみ記載)*

(Pass C で記述)

## References

- 関連 ADR: ADR-0004 (`implementation` × `role` 妥当組み合わせ)
- CLAUDE.md: 「VMware vSwitch / dvSwitch の表現」セクション、role 語彙まとめ表
- 設計プラン: 初期の設計プラン (リポジトリ外。現在は ADR が正)
- 外部資料: nextbox-ui-plugin (NetBox `device_role` 慣習)
