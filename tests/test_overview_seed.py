"""overview_seed: a book's name, genre and tone written into campaign-overview.json
at import; the other fields stay."""

import json

from lib.overview_seed import seed_overview


def test_seed_sets_fields_preserving_others(tmp_path):
    (tmp_path / "campaign-overview.json").write_text(json.dumps({
        "campaign_name": "scaffold", "genre": "Fantasy",
        "player_position": {"current_location": "X"}, "session_count": 3,
    }))
    seed_overview(str(tmp_path), fields={"campaign_name": "The Iron Tangle",
                                         "genre": "LitRPG / Comedy-Horror"})
    o = json.loads((tmp_path / "campaign-overview.json").read_text())
    assert o["campaign_name"] == "The Iron Tangle"
    assert o["genre"] == "LitRPG / Comedy-Horror"
    assert o["session_count"] == 3
    assert o["player_position"] == {"current_location": "X"}
    assert "campaign_rules" not in o
