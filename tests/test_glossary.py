"""The glossary (lib/glossary.py): the world's own words, each with a line on
what it means, kept in world-bible.json. It replaces the voice's bare word list
and the WORLD INDEX's items; the brief lists only the terms."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import glossary as g
from lib.json_ops import JsonOperations
from lib.session_manager import SessionManager
from lib.world_bible import validate_bible

ROOT = Path(__file__).resolve().parent.parent


def _ops(dcc_world):
    return JsonOperations(str(Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"))


def test_add_show_and_reword(dcc_world):
    ops = _ops(dcc_world)
    assert g.add(ops, " Lantern  papers ", "The certificate of a ghost.") == "Lantern papers"
    assert g.add(ops, "the Test", "What the Dark sit at the Lantern Office.") == "the Test"
    assert list(g.glossary(ops)) == ["Lantern papers", "the Test"]
    assert g.glossary(ops)["Lantern papers"] == {"description": "The certificate of a ghost.",
                                                "plots": []}
    assert g.find(ops, "lantern PAPERS") == "Lantern papers"
    with pytest.raises(g.GlossaryError, match="in the glossary already"):
        g.add(ops, "LANTERN papers", "x")
    for term, text, why in (("", "x", "needs a term"), ("A: b", "x", "without a colon"),
                            ("ghost", "", "what the term means")):
        with pytest.raises(g.GlossaryError, match=why):
            g.add(ops, term, text)
    assert g.describe(ops, "the test", "Twelve questions.") == (
        "the Test", "What the Dark sit at the Lantern Office.")
    with pytest.raises(g.GlossaryError, match="did you mean: the Test"):
        g.describe(ops, "the Tset", "x")
    bible = ops.load_json("world-bible.json")
    assert validate_bible(bible)[0], validate_bible(bible)[1]
    bible["glossary"]["ghost"] = {"description": ""}
    assert "glossary 'ghost' needs a description" in validate_bible(bible)[1]


def test_the_brief_lists_the_terms_only(dcc_world):
    ops = _ops(dcc_world)
    g.add(ops, "Lantern papers", "The certificate of a ghost; forged ones are fragile.")
    g.add(ops, "the Test", "Twelve questions.")
    brief = SessionManager(dcc_world).get_full_context()
    assert "The world's own words" in brief and "Lantern papers, the Test" in brief
    assert "forged ones are fragile" not in brief
    assert "In-world terms to favor" not in brief


def test_a_campaign_from_before_the_glossary_keeps_its_word_list(dcc_world):
    ops = _ops(dcc_world)
    bible = ops.load_json("world-bible.json")
    bible.pop("glossary", None)
    bible.setdefault("voice", {})["vocab"] = ["ghost", "shell"]
    ops.save_json("world-bible.json", bible)
    assert g.terms(ops) == ["ghost", "shell"]


def test_the_command(dcc_world):
    env = dict(os.environ, GM_WORLD_STATE_BASE=dcc_world)

    def run(*words):
        return subprocess.run(["bash", str(ROOT / "tools" / "gm-glossary.sh"), *words],
                              capture_output=True, text=True, env=env)

    assert run("add", "Lit", "Someone with lantern papers.").returncode == 0
    assert run("show", "lit").stdout.strip() == "Lit: Someone with lantern papers."
    bad = run("show", "Dark")
    assert bad.returncode == 1 and "[ERROR] No term 'Dark'" in bad.stderr
    assert "Lit: Someone" in run("list").stdout
    stored = json.loads((Path(dcc_world) / "campaigns" / "dungeon-crawler-carl"
                         / "world-bible.json").read_text())
    assert stored["glossary"]["Lit"]["plots"] == []
