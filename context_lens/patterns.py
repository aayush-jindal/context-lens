from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class PatternResult:
    pattern_id: str
    severity: str
    message: str
    metric: float


class BasePattern:
    id: str = ""
    name: str = ""
    description: str = ""

    def analyze(self, session: dict) -> PatternResult | None:
        raise NotImplementedError


class RunawayAssistantPattern(BasePattern):
    id = "runaway_assistant"
    name = "Runaway Assistant Output"
    description = "Assistant output far exceeds user input"

    def analyze(self, session: dict) -> PatternResult | None:
        ratio = session.get("assistant_user_ratio", 0.0)
        if ratio > 5:
            return PatternResult(
                pattern_id=self.id,
                severity="warning",
                message=f"Runaway assistant output ({ratio:.1f}:1 ratio)",
                metric=ratio,
            )
        return None


class FileDumpPattern(BasePattern):
    id = "file_dump"
    name = "Probable File Dump"
    description = "Single assistant turn with very high token count"

    def analyze(self, session: dict) -> PatternResult | None:
        max_tokens = session.get("max_turn_tokens", 0)
        max_role = session.get("max_turn_role", "")
        if max_tokens > 3000 and max_role == "assistant":
            return PatternResult(
                pattern_id=self.id,
                severity="warning",
                message=f"Probable file dump ({max_tokens:,} tokens in one turn)",
                metric=float(max_tokens),
            )
        return None


class ContextAccumulationPattern(BasePattern):
    id = "context_accumulation"
    name = "Context Accumulation Risk"
    description = "Long sessions where early turns keep costing tokens"

    def analyze(self, session: dict) -> PatternResult | None:
        turns = session.get("turns", 0)
        if turns > 40:
            return PatternResult(
                pattern_id=self.id,
                severity="warning",
                message=f"Context accumulation risk ({turns} turns)",
                metric=float(turns),
            )
        return None


class LowSignalPattern(BasePattern):
    id = "low_signal"
    name = "Low Signal User Turns"
    description = "Tiny user inputs driving large agent spend"

    def analyze(self, session: dict) -> PatternResult | None:
        turns = session.get("turns", 0)
        user_tokens = session.get("user_tokens", 0)
        if turns <= 0 or user_tokens <= 0:
            return None
        avg = user_tokens / turns
        if avg < 20:
            return PatternResult(
                pattern_id=self.id,
                severity="warning",
                message=f"Low signal user turns (avg {avg:.0f} tokens/turn)",
                metric=avg,
            )
        return None


class LargeTerminalPattern(BasePattern):
    id = "large_terminal"
    name = "Large Terminal Output"
    description = "Terminal or tool output file with high token count"

    def analyze(self, session: dict) -> PatternResult | None:
        if "turns" in session:
            return None
        total_tokens = session.get("total_tokens", 0)
        if total_tokens > 5000:
            return PatternResult(
                pattern_id=self.id,
                severity="warning",
                message=f"Large terminal output ({total_tokens:,} tokens)",
                metric=float(total_tokens),
            )
        return None


class ShortSessionHighCostPattern(BasePattern):
    id = "short_session_high_cost"
    name = "Short Session High Cost"
    description = "Few turns but very high total token usage"

    def analyze(self, session: dict) -> PatternResult | None:
        turns = session.get("turns")
        if turns is None:
            return None
        total_tokens = session.get("total_tokens", 0)
        if turns < 6 and total_tokens > 3000:
            return PatternResult(
                pattern_id=self.id,
                severity="warning",
                message=f"Short session high cost ({turns} turns, {total_tokens:,} tokens)",
                metric=float(total_tokens),
            )
        return None


class PatternRegistry:
    def __init__(self) -> None:
        self._patterns: list[BasePattern] = []

    @property
    def patterns(self) -> list[BasePattern]:
        return list(self._patterns)

    def register(self, pattern: BasePattern) -> None:
        self._patterns.append(pattern)

    def analyze_session(self, session: dict) -> list[PatternResult]:
        results: list[PatternResult] = []
        for pattern in self._patterns:
            hit = pattern.analyze(session)
            if hit is not None:
                results.append(hit)
        return results

    def pattern_by_id(self, pattern_id: str) -> BasePattern | None:
        for pattern in self._patterns:
            if pattern.id == pattern_id:
                return pattern
        return None


def _default_registry() -> PatternRegistry:
    registry = PatternRegistry()
    registry.register(RunawayAssistantPattern())
    registry.register(FileDumpPattern())
    registry.register(ContextAccumulationPattern())
    registry.register(LowSignalPattern())
    registry.register(LargeTerminalPattern())
    registry.register(ShortSessionHighCostPattern())
    return registry


_DEFAULT_REGISTRY = _default_registry()


def detect_patterns(session_analysis: dict) -> list[str]:
    """Run all registered patterns and return warning message strings."""
    results = _DEFAULT_REGISTRY.analyze_session(session_analysis)
    return [r.message for r in results]


def get_registry() -> PatternRegistry:
    return _DEFAULT_REGISTRY
