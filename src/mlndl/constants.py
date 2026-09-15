"""mlndl 定数定義"""

# 入力サイズ上限 (ADR-0004 セキュリティ要件)
MAX_TOPOLOGY_BYTES: int = 1 * 1024 * 1024  # 1MB

# 推奨 role 語彙 (informative — コアバリデーターは使用しない)
# 詳細: docs/role-vocabulary.md / ADR-0003 D4
CANONICAL_ROLES: frozenset[str] = frozenset({
    "spine",
    "leaf",
    "core",
    "border",
    "server",
    "firewall",
    "load-balancer",
    "hypervisor",
    "management",
})

# ---------------------------------------------------------------------------
# labels 推奨軸名 (informative — コアバリデーターは使用しない)
# 詳細: docs/label-vocabulary.md / ADR-0009
# ---------------------------------------------------------------------------

# 障害軸: 値が同じノードは同じ障害を共有しうる。
# Phase 3+ の blast_radius クエリはこの軸を辿る候補となる。
FAULT_AXIS_LABEL_KEYS: frozenset[str] = frozenset({
    "az",
    "pod",
    "rack",
    "site",
    "region",
})

# 管理軸: 課金・所有・ライフサイクルの分類。障害は伝播しない。
MANAGEMENT_AXIS_LABEL_KEYS: frozenset[str] = frozenset({
    "tenant",
    "env",
    "stage",
    "owner",
    "cost-center",
})

RECOMMENDED_LABEL_KEYS: frozenset[str] = (
    FAULT_AXIS_LABEL_KEYS | MANAGEMENT_AXIS_LABEL_KEYS
)
