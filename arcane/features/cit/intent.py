"""CIT — Intent types and metadata model."""

from __future__ import annotations

from enum import Enum


class IntentType(str, Enum):
    FEAT = "feat"
    FIX = "fix"
    REFACTOR = "refactor"
    PERF = "perf"
    DEBT = "debt"
    DOCS = "docs"
    TEST = "test"
    CHORE = "chore"

    @classmethod
    def values(cls) -> list[str]:
        return [e.value for e in cls]


# Intents that contribute to debt score (numerator)
DEBT_INTENTS = {IntentType.DEBT, IntentType.FIX}
# Intents that reduce debt score (denominator)
HEALTHY_INTENTS = {IntentType.FEAT, IntentType.REFACTOR}
