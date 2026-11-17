#!/usr/bin/env python3
"""Author per-book campaign-overview fields.

Import creates campaign-overview.json as the default scaffold (genre "Fantasy"),
so the book's own name, genre and tone have to be written in. The world's own
rules are not kept here: they are the ruleset's (world_rules.py, gm-rule.sh).
"""

import json
from pathlib import Path


def seed_overview(campaign_dir, fields: dict = None) -> dict:
    """Merge `fields` into campaign-overview.json.

    Returns the written overview. Existing keys are overwritten only for the keys
    provided (player_position, session_count, etc. are preserved otherwise).
    """
    path = Path(campaign_dir) / "campaign-overview.json"
    overview = json.loads(path.read_text()) if path.exists() else {}
    if fields:
        overview.update(fields)
    path.write_text(json.dumps(overview, indent=2))
    return overview


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seed campaign-overview")
    parser.add_argument("campaign_dir")
    parser.add_argument("--fields-json", nargs="?", const="-",
                        help="JSON object of overview fields to set; without a value: "
                             "read from after the command")
    args = parser.parse_args()

    if args.fields_json:
        from cli_output import json_input
        seed_overview(args.campaign_dir, json_input(args.fields_json, "--fields-json"))
        print("overview seeded")


if __name__ == "__main__":
    main()
