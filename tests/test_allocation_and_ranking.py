from types import SimpleNamespace

from app.services.card_allocation import CubeCardInput, MatchStatus, OwnedCardInput, allocate_cards
from app.services.cube_comparison import build_comparison
from app.services.ranking import rank_cubes


def test_exact_printing_beats_name_only_and_prevents_double_counting() -> None:
    owned = [
        OwnedCardInput(1, "Pikachu", "pikachu", "BS", "58", 1),
        OwnedCardInput(2, "Pikachu", "pikachu", "JGL", "60", 1),
    ]
    cube_cards = [
        CubeCardInput(1, "Pikachu", "pikachu", None, "BS", "58", 1),
        CubeCardInput(2, "Pikachu", "pikachu", None, None, None, 2),
    ]

    allocations = allocate_cards(owned, cube_cards)

    assert allocations[0].owned_quantity == 1
    assert allocations[0].status == MatchStatus.EXACT
    assert allocations[1].owned_quantity == 1
    assert allocations[1].missing_quantity == 1
    assert allocations[1].status == MatchStatus.NAME_ONLY


def test_rejected_match_does_not_count_as_owned() -> None:
    owned = [OwnedCardInput(1, "Pikachu", "pikachu", None, None, 1)]
    cube_cards = [CubeCardInput(1, "Pikachu", "pikachu", None, None, None, 1)]

    allocations = allocate_cards(
        owned,
        cube_cards,
        rejected_pairs={("pikachu||", "pikachu||")},
    )

    assert allocations[0].owned_quantity == 0
    assert allocations[0].missing_quantity == 1


def test_completion_calculations_and_ranking_tiebreak() -> None:
    cube_a = SimpleNamespace(id=1, name="Alpha")
    cube_b = SimpleNamespace(id=2, name="Beta")
    comparison_a = build_comparison(
        cube_a,
        [
            allocate_cards(
                [OwnedCardInput(1, "A", "a", None, None, 1)],
                [CubeCardInput(1, "A", "a", None, None, None, 2)],
            )[0]
        ],
    )
    comparison_b = build_comparison(
        cube_b,
        [
            allocate_cards(
                [OwnedCardInput(1, "A", "a", None, None, 1)],
                [CubeCardInput(1, "A", "a", None, None, None, 1)],
            )[0]
        ],
    )

    ranked = rank_cubes([comparison_a, comparison_b])

    assert comparison_a.copy_completion == 0.5
    assert comparison_b.copy_completion == 1.0
    assert ranked[0].cube.name == "Beta"
