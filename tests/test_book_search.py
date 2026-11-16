"""The book search on our own embedder and store (2026-11-16): a book is cut into
pieces, embedded (here with the fake embedder) and searched by closeness to a
question; the indexing resumes where it stopped."""

from pathlib import Path

import pytest

pytest.importorskip("numpy")

from lib.embedder import FakeEmbedder  # noqa: E402
from lib.rag.rag_extractor import RAGExtractor  # noqa: E402
from lib.rag.vector_store import CampaignVectorStore  # noqa: E402

BOOK = """Chapter 1

The lighthouse keeper climbed the spiral stair every evening to light the great lamp.
The sea below was grey and the gulls cried over the rocks.

Chapter 2

In the village the baker woke before dawn. Bread and rolls filled the window of his shop,
and the smell of yeast drifted down the cobbled street.

Chapter 3

A hound howled on the moor at night. Nobody in the hall would cross the moor after dark,
for the hound was said to haunt the old family.
"""


@pytest.fixture
def book(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text(BOOK)
    camp = tmp_path / "camp"
    camp.mkdir()
    return path, camp


def test_a_book_is_cut_embedded_and_searched(book):
    path, camp = book
    meta = RAGExtractor(str(camp), chunk_size=200, embedder=FakeEmbedder()).extract_from_document(path)
    assert meta["total_chunks"] >= 3 and meta["indexing"] == "done"
    store = CampaignVectorStore(str(camp))
    assert store.progress() == (meta["total_chunks"], meta["total_chunks"])
    found = store.query_by_text("the hound on the moor", FakeEmbedder(), n_results=2)
    assert "hound" in found["documents"][0]
    assert 0 <= found["distances"][0] < found["distances"][1] <= 2     # cosine distances


def test_indexing_resumes_where_it_stopped(book, monkeypatch):
    path, camp = book
    monkeypatch.setenv("GM_EMBEDDER", "off")               # no background job
    RAGExtractor(str(camp), chunk_size=200).extract_from_document(path)
    store = CampaignVectorStore(str(camp))
    done, total = store.progress()
    assert done == 0 and total >= 3

    class Interrupted(FakeEmbedder):
        calls = 0

        def document(self, text):
            Interrupted.calls += 1
            if Interrupted.calls > 1:
                raise KeyboardInterrupt
            return super().document(text)
    with pytest.raises(KeyboardInterrupt):
        store.index(Interrupted())
    kept = CampaignVectorStore(str(camp)).count()
    assert kept <= 1                                         # saved at most what was done
    assert CampaignVectorStore(str(camp)).index(FakeEmbedder()) == total - kept   # only the rest
    assert CampaignVectorStore(str(camp)).progress() == (total, total)


def test_a_search_before_indexing_finishes_uses_what_is_done(book, monkeypatch):
    path, camp = book
    monkeypatch.setenv("GM_EMBEDDER", "off")
    RAGExtractor(str(camp), chunk_size=200).extract_from_document(path)
    store = CampaignVectorStore(str(camp))
    rows = store.chunks()
    store._save("fake", {rows[0]["id"]: FakeEmbedder().document(rows[0]["text"])})
    found = CampaignVectorStore(str(camp)).query_by_text("lighthouse", FakeEmbedder(), n_results=5)
    assert found["ids"] == [rows[0]["id"]]


def test_the_enhancer_searches_the_book(book, monkeypatch, tmp_path):
    """search_raw, which gm-search.sh --rag-only and gm-context.sh use."""
    import json

    from lib.entity_enhancer import EntityEnhancer
    path, _ = book
    ws = tmp_path / "ws"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    for name in ("npcs.json", "locations.json", "facts.json"):
        (camp / name).write_text(json.dumps({}))
    RAGExtractor(str(camp), chunk_size=200, embedder=FakeEmbedder()).extract_from_document(path)
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    monkeypatch.setattr("lib.rag.vector_store.CampaignVectorStore.is_available",
                        staticmethod(lambda: True))
    passages = EntityEnhancer(str(ws)).search_raw("bread from the baker", n_results=1)
    assert passages and "baker" in passages[0]["text"]
    assert Path(camp, "vectors", "chunks.json").exists()


# ---------- a book is indexed once, and only a finished index is used ----------

def test_a_second_campaign_from_the_same_book_copies_the_index(book, tmp_path, monkeypatch):
    from lib.rag import vector_store
    path, camp = book
    monkeypatch.setenv("GM_WORLD_STATE_BASE", str(tmp_path / "ws"))
    RAGExtractor(str(camp), chunk_size=200, embedder=FakeEmbedder()).extract_from_document(path)
    store = CampaignVectorStore(str(camp))
    shared = vector_store.shared_dir(store.source_key())
    assert (shared / "book.npz").exists()
    # the shared copy is checked against the model: make it look like the real one's
    model, vectors = store._vectors()
    from lib.embedder import MODEL_NAME
    store._save(MODEL_NAME, vectors)
    store.share()
    second = tmp_path / "second"
    second.mkdir()
    meta = RAGExtractor(str(second), chunk_size=200).extract_from_document(path)
    assert meta["indexing"] == "done (from an earlier campaign)"
    assert CampaignVectorStore(str(second)).complete()


def test_a_half_indexed_book_is_refused_with_what_to_do(book, monkeypatch):
    path, camp = book
    monkeypatch.setenv("GM_EMBEDDER", "off")
    RAGExtractor(str(camp), chunk_size=200).extract_from_document(path)
    message = CampaignVectorStore(str(camp)).not_ready()
    assert "still being indexed (0 of" in message and "gm-extract.sh wait" in message


def test_wait_says_done_or_to_call_again(book, monkeypatch):
    from lib.rag import vector_store
    path, camp = book
    monkeypatch.setenv("GM_EMBEDDER", "off")
    RAGExtractor(str(camp), chunk_size=200).extract_from_document(path)
    monkeypatch.setattr(vector_store.CampaignVectorStore, "is_available", staticmethod(lambda: True))
    monkeypatch.setattr(vector_store, "start_index_job", lambda d: False)
    assert vector_store.wait(str(camp), minutes=0) == 2               # still indexing
    CampaignVectorStore(str(camp)).index(FakeEmbedder())
    assert vector_store.wait(str(camp), minutes=0) == 0               # done


def test_the_loremaster_finds_the_chapter_by_meaning(book, monkeypatch):
    from lib.rag.coarse_index import CoarseIndex
    path, camp = book
    RAGExtractor(str(camp), chunk_size=200, embedder=FakeEmbedder()).extract_from_document(path)
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    index = CoarseIndex(embedder="meaning", store=CampaignVectorStore(str(camp)))
    index.build(Path(path).read_text())
    pointers = index.query("bread from the baker before dawn")
    assert index.method == "meaning"
    assert "baker" in index.load_chapter(pointers[0]["index"])["text"]
    monkeypatch.setenv("GM_EMBEDDER", "off")                          # no model: keywords
    assert index.query("baker bread") and index.method == "keyword"


def test_the_loremaster_refuses_a_half_indexed_book(book, monkeypatch, tmp_path):
    import json

    from lib.loremaster import Loremaster, LoremasterError
    from lib.rag import vector_store
    path, _ = book
    ws = tmp_path / "ws"
    camp = ws / "campaigns" / "c"
    camp.mkdir(parents=True)
    (ws / "active-campaign.txt").write_text("c")
    (camp / "campaign-overview.json").write_text(json.dumps({}))
    monkeypatch.setenv("GM_EMBEDDER", "off")
    RAGExtractor(str(camp), chunk_size=200).extract_from_document(path)
    import importlib  # the Loremaster imports it as rag.vector_store
    for module in (vector_store, importlib.import_module("rag.vector_store")):
        monkeypatch.setattr(module.CampaignVectorStore, "is_available", staticmethod(lambda: True))
    with pytest.raises(LoremasterError, match="gm-extract.sh wait"):
        Loremaster(str(ws), book_text=BOOK)
