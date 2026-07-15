import csv
import io

from app.services.cube_comparison import CubeComparison


def missing_cards_csv(comparison: CubeComparison) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "card_name",
            "set",
            "collector_number",
            "required_quantity",
            "owned_matching_quantity",
            "missing_quantity",
            "match_status",
        ]
    )
    for item in comparison.allocations:
        if item.missing_quantity <= 0:
            continue
        card = item.cube_card
        writer.writerow(
            [
                card.original_name,
                card.set_name or card.set_code or "",
                card.collector_number or "",
                card.required_quantity,
                item.owned_quantity,
                item.missing_quantity,
                item.status.value,
            ]
        )
    return output.getvalue()
