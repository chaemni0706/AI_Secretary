"""BudgetAlertService — per-category budget usage + warning/exceeded status.

Rule-driven by ``ledger_budget_rules.json``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.services import ledger_common as common


def _status_for(usage_rate: float, warn: int, exceed: int) -> str:
    if usage_rate >= exceed:
        return "exceeded"
    if usage_rate >= warn:
        return "warning"
    return "normal"


def compute_budget_usage(spent_by_category: Dict[str, int]) -> List[Dict[str, Any]]:
    """Return budget usage rows for categories that have a configured budget."""
    rules = common.load_budget_rules()
    budgets: Dict[str, int] = rules.get("default_monthly_budgets", {})
    warn = int(rules.get("warning_threshold", 80))
    exceed = int(rules.get("exceeded_threshold", 100))

    out: List[Dict[str, Any]] = []
    for category, budget in budgets.items():
        spent = int(spent_by_category.get(category, 0))
        if budget <= 0:
            usage_rate = 0
        else:
            usage_rate = round(spent / budget * 100)
        out.append({
            "category": category,
            "budget": budget,
            "spent": spent,
            "usage_rate": usage_rate,
            "status": _status_for(usage_rate, warn, exceed),
        })
    # surface the most-used categories first
    out.sort(key=lambda r: r["usage_rate"], reverse=True)
    return out


def budget_alerts(spent_by_category: Dict[str, int]) -> List[Dict[str, Any]]:
    """Compact alerts (warning/exceeded only) for the dashboard."""
    rules = common.load_budget_rules()
    labels = rules.get("status_labels", {})
    alerts = []
    for row in compute_budget_usage(spent_by_category):
        if row["status"] in ("warning", "exceeded"):
            alerts.append({
                "category": row["category"],
                "usage_rate": row["usage_rate"],
                "status": row["status"],
                "status_label": labels.get(row["status"], row["status"]),
                "budget": row["budget"],
                "spent": row["spent"],
            })
    return alerts
