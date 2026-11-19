"""Tests for embeddings-coarse-index: chapter pointers, pluggable embedder, templates."""

from lib.rag.coarse_index import CoarseIndex, _template

SAMPLE = (
    "Chapter One\nThe spice must flow across the dunes of Arrakis. Paul watched.\n\n"
    "Chapter Two\nThe Fremen waited in the rocks, sietch-bound and patient.\n\n"
    "Chapter Three\nThe Baron Harkonnen schemed in his fortress on Giedi Prime.\n"
)


def test_build_and_query_returns_right_chapter_pointer():
    ci = CoarseIndex(embedder="keyword")
    assert ci.build(SAMPLE) == 3
    res = ci.query("spice dunes Arrakis Paul")
    assert res and res[0]["index"] == 0  # chapter one


def test_query_returns_pointers_not_text_blobs():
    ci = CoarseIndex()
    ci.build(SAMPLE)
    res = ci.query("Fremen sietch")
    assert all("index" in r and "text" not in r for r in res)
    # but the pointer resolves to the full chapter on demand
    assert "Fremen" in ci.load_chapter(res[0]["index"])["text"]


def test_embedder_is_pluggable_via_config():
    assert CoarseIndex(embedder="keyword").embedder == "keyword"
    assert CoarseIndex(embedder="meaning").embedder == "meaning"


def test_query_templates_branch_by_content_type():
    assert "mechanics" in _template("orc", "game-module")
    assert "atmosphere" in _template("tavern", "literary")


def test_no_results_when_nothing_matches():
    ci = CoarseIndex()
    ci.build(SAMPLE)
    assert ci.query("zzzzz nonexistent qqqqq") == []
