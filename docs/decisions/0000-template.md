# ADR-NNNN: <短い決定タイトル>

- **Status**: Draft | Accepted | Superseded by ADR-XXXX
- **Date**: YYYY-MM-DD
- **Deciders**: <参加したエージェントの観点 (例: spec-architect, linguist, dsl-designer)>
- **Pass**: A (初回策定) | C (再設計後の最終版)
- **Supersedes**: drafts/NNNN-xxx.md *(Pass C の場合のみ)*

## Context

なぜこの決定が必要か。背景となる問題・制約・既存設計とのつながりを説明する。

## Decision

何を決めたか。短く、明確に。YAML 抜粋や型シグネチャがあればここに記載。

```yaml
# 決定内容を示す YAML 例 (あれば)
```

## Consequences

**良い影響:**
-

**悪い影響 / トレードオフ:**
-

**影響を受けるコンポーネント:**
- スキーマ: `src/mlndl/schema/`
- バリデーター: `src/mlndl/validator.py`
- エクスポーター: `src/mlndl/exporter/`
- サンプル: `tests/fixtures/`
- 文書: `CLAUDE.md`

## Alternatives Considered

- **案A** *(採用案)*: ...
- **案B**: 却下理由 — ...
- **案C**: 却下理由 — ...

## Pass A との差分 *(Pass C のみ記載)*

Pass A のドラフト (`drafts/NNNN-xxx.md`) からの変更点と理由。
偶然同一になった場合は「独立に同じ結論に到達した」と記載。

## References

- 関連 ADR: ADR-XXXX
- CLAUDE.md: 「重要な設計決定」セクション
- 原案の論文: 手元の場所は CLAUDE.local.md
- 外部資料: (RFC 番号, GitHub リンク 等)
