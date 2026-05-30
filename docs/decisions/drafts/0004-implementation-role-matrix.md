# ADR-0004: `implementation` × `role` の妥当組み合わせ

- **Status**: Draft
- **Date**: 2026-05-27
- **Deciders**: mlndl-spec-architect (Pass A)
- **Pass**: A (初回策定)

## Context

CLAUDE.md で `implementation` は `vm | physical | container` の 3 値に固定済み (`virtual` は廃止)。一方 `role` は ADR-0003 で確定する語彙 (spine / leaf / tor / core / border / server / hypervisor / vswitch / dvswitch / router / firewall / load_balancer) を持つ。

両者の**妥当な組み合わせ・不正な組み合わせ**の判定基準が未明文化であるため、スキーマとバリデーターの実装指針として本 ADR で定義する。

論点:

1. **論理的に成立しない組み合わせ**: `role: vswitch` + `implementation: physical` は明らかに不正
2. **特殊ケース**: `role: hypervisor` + `implementation: vm` はネストハイパーバイザの表現として現実にある
3. **不正組み合わせへのバリデーター挙動**: error / warning / silent のどれにするか
4. **エスケープハッチ**: 特殊ケースを通すためのフラグが必要か

## Decision

**Pass A 案: マトリクス定義 + warning デフォルト + 厳格モードフラグ + エスケープハッチ。**

### マトリクス (Pass A)

凡例: ✅ 推奨、⚠ 許容 (warning)、❌ 不正 (strict mode で error)

| role | vm | physical | container |
|------|----|----------|-----------|
| `spine` | ✅ | ✅ | ⚠ (Cumulus VX container 等) |
| `leaf` | ✅ | ✅ | ⚠ |
| `tor` | ✅ | ✅ | ⚠ |
| `core` | ⚠ | ✅ | ❌ |
| `border` | ✅ | ✅ | ⚠ |
| `server` | ✅ | ✅ | ✅ |
| `hypervisor` | ⚠ (nested virt) | ✅ | ❌ |
| `vswitch` | ✅ | ❌ | ❌ |
| `dvswitch` | ✅ | ❌ | ❌ |
| `router` | ✅ | ✅ | ⚠ |
| `firewall` | ✅ | ✅ | ⚠ |
| `load_balancer` | ✅ | ✅ | ✅ (NGINX/HAProxy コンテナ) |

未知 role (`Literal | str` で pass-through された値): **常に ✅** (マトリクスが存在しないため判定不能)。

### バリデーター挙動

```python
# デフォルトモード (lenient)
MLNDLTopology.model_validate(data)
# → ⚠ は warning ログ、❌ も warning ログ (実行継続)

# 厳格モード (strict)
MLNDLTopology.model_validate(data, context={"strict": True})
# → ⚠ は warning、❌ は ValidationError
```

`context` は pydantic v2 の `ValidationInfo.context` で受け取り、`model_validator(mode="after")` 内で判定。

### エスケープハッチ

特殊ケース (例: nested virt で `role: hypervisor` + `implementation: vm`) を意図的に記述したい場合:

```yaml
layer1:
  nodes:
    - id: nested-esxi
      role: hypervisor
      implementation: vm
      allow_unusual_combination: true  # ⚠ セルの warning を silent 化
```

- `allow_unusual_combination: true` は **⚠ セルの warning のみ** 抑止する
- **❌ セルは strict mode でも `allow_unusual_combination` があっても error のまま** (意味的に成立しない組み合わせのため)

### `❌` セルの根拠

- `role: vswitch / dvswitch` + `physical`: vSwitch はハイパーバイザ内ソフトウェア機能。物理スイッチとして単独存在しない。
- `role: vswitch / dvswitch` + `container`: 同上。コンテナ単体で vSwitch は構成しない。
- `role: hypervisor` + `container`: ハイパーバイザはハードウェア仮想化レイヤ。コンテナの上では動かない。
- `role: core` + `container`: DC バックボーンのコアスイッチはコンテナで実装しない。

## Consequences

**良い影響:**

- マトリクスを spec として固定することで、利用者・アダプター実装者・下流ツールが整合性を判断できる
- デフォルト warning + strict mode のハイブリッドにより、CI/CD パイプラインでは厳格チェック、開発時には緩い体験を両立
- エスケープハッチで特殊ケースも明示的に通せる
- `vswitch/dvswitch` の `vm` 強制によりベストプラクティス外の記述を早期検出

**悪い影響 / トレードオフ:**

- マトリクス仕様が一段複雑化
- 厳格モードと lenient モードの動作差異はテストカバレッジを倍増させる
- `allow_unusual_combination` フィールドが検証回避手段として誤用される懸念

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer1.py` に `allow_unusual_combination: bool = False` を追加
- バリデーター:
  - `src/mlndl/validator.py` にマトリクス定数 `IMPL_ROLE_MATRIX: dict[tuple[str, str], str]`
  - `model_validator(mode="after")` で `context.get("strict")` を見て挙動分岐
- エクスポーター: 影響なし
- サンプル:
  - `tests/fixtures/warn_unusual_combo.yaml`: ⚠ ケース (warning が出ることを確認)
  - `tests/fixtures/invalid_vswitch_physical.yaml`: ❌ ケース (strict mode で error)
- 文書: CLAUDE.md セクション「2. `implementation` フィールド」にマトリクスへの参照リンクを追加

## Alternatives Considered

- **案A** *(採用案)*: マトリクス + warning デフォルト + 厳格モード + エスケープハッチ
  - 柔軟性と厳密性のバランスが取れている

- **案B**: 不正組み合わせは warning のみで error を出さない (柔軟性優先)
  - 却下理由: `role: vswitch` + `implementation: physical` のような意味の通らない組み合わせを通すと、eve-lab-builder / ndl-viz の下流処理でクラッシュや誤動作の原因になる。❌ セルは error にすべき。

- **案C**: マトリクスを仕様書に記載するだけでバリデーターに組み込まない (silent)
  - 却下理由: 仕様書を読まないユーザーが多い。バリデーターで warning を出すことで学習機会を提供できる。

- **案D**: `implementation: custom` を追加し、エスケープハッチ代わりにする
  - 却下理由: `implementation` の語彙を 4 値に拡張すると CLAUDE.md で確定済みの 3 値固定が崩れる。`allow_unusual_combination: true` フィールドの方が明示的でコストが低い。

## Pass A との差分 *(Pass C のみ記載)*

(Pass C で記述)

## References

- 関連 ADR: ADR-0003 (`role` 語彙の確定)
- CLAUDE.md: 「重要な設計決定 2. `implementation` フィールド」「6. VMware vSwitch / dvSwitch の表現」
- 設計プラン: 初期の設計プラン (リポジトリ外。現在は ADR が正) (role 語彙まとめ表)
- 外部資料: pydantic v2 `ValidationInfo.context`
