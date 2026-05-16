"""CIT — Technical debt score calculator."""

from __future__ import annotations

from arcane.core.repository import Repository
from arcane.features.cit.intent import DEBT_INTENTS, HEALTHY_INTENTS, IntentType


def compute_debt_score(repo: Repository, window: int = 50) -> dict:  # type: ignore[type-arg]
    """Compute a technical debt score from the last `window` commits.

    Score = (debt_count + fix_count) / max(1, feat_count + refactor_count)
    Normalized to 0–100.

    Returns a dict with: score, debt_count, fix_count, feat_count, refactor_count,
    total, window.
    """
    head = repo.refs.resolve_head()
    if not head:
        return {"score": 0, "total": 0, "window": window}

    counts: dict[str, int] = {t.value: 0 for t in IntentType}
    total = 0
    seen: set[str] = set()
    queue = [head]

    while queue and total < window:
        h = queue.pop(0)
        if h in seen:
            continue
        seen.add(h)
        try:
            c = repo.store.read_commit(h)
        except Exception:
            break
        counts[c.intent_type] = counts.get(c.intent_type, 0) + 1
        total += 1
        queue.extend(c.parents)

    debt_n = sum(counts.get(t.value, 0) for t in DEBT_INTENTS)
    healthy_d = max(1, sum(counts.get(t.value, 0) for t in HEALTHY_INTENTS))
    raw_ratio = debt_n / healthy_d
    # Clamp to 0–100 (ratio > 1 caps at 100)
    score = min(100, int(raw_ratio * 50))

    return {
        "score": score,
        "total": total,
        "window": window,
        "counts": counts,
        "debt_n": debt_n,
        "healthy_d": healthy_d,
    }
