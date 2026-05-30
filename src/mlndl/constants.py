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
