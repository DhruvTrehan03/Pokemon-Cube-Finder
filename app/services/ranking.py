from typing import Protocol

from app.services.cube_comparison import CubeComparison


class CubeRankingStrategy(Protocol):
    def score(self, comparison: CubeComparison) -> float:
        ...


class CompletionRankingStrategy:
    def score(self, comparison: CubeComparison) -> float:
        return comparison.copy_completion


class CostToCompleteRankingStrategy:
    """Placeholder for future price-aware ranking."""

    def score(self, comparison: CubeComparison) -> float:
        raise NotImplementedError("Pricing is intentionally out of scope for v1.")


def rank_cubes(
    comparisons: list[CubeComparison],
    sort: str = "copy_completion",
) -> list[CubeComparison]:
    if sort == "missing_copies":
        return sorted(comparisons, key=lambda item: (item.missing_copies, item.cube.name.casefold()))
    if sort == "unique_completion":
        return sorted(
            comparisons,
            key=lambda item: (-item.unique_completion, item.missing_copies, item.cube.name.casefold()),
        )
    if sort == "cost_to_complete":
        return sorted(
            comparisons,
            key=lambda item: (
                item.tcgplayer_missing_market_cost,
                item.unpriced_missing_copies,
                item.missing_copies,
                item.cube.name.casefold(),
            ),
        )
    if sort == "cube_name":
        return sorted(comparisons, key=lambda item: item.cube.name.casefold())
    return sorted(
        comparisons,
        key=lambda item: (
            -item.copy_completion,
            item.missing_copies,
            item.missing_unique_cards,
            item.cube.name.casefold(),
        ),
    )
