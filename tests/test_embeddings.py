"""Semantic recall's groundwork: the embedder and the store kept up to date
(step 12a and 12b, 2026-11-15). The fake embedder stands in for the model, so
the suite needs neither the packages nor the model; one test uses the real
model when it is installed."""

import fcntl
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from lib import embedder as embedder_mod  # noqa: E402
from lib.embedding_store import LOCK, STORE, EmbeddingStore, job, texts  # noqa: E402
from lib.note_manager import NoteManager  # noqa: E402
from lib.plot_manager import PlotManager  # noqa: E402

CAMP = ("campaigns", "dungeon-crawler-carl")


def _camp(world) -> Path:
    return Path(world, *CAMP)


def test_the_fake_embedder_points_shared_words_the_same_way():
    fake = embedder_mod.FakeEmbedder()
    a, b, c = (fake.document(t) for t in ("the red door", "a red door opens", "seven blue fish"))
    assert np.allclose(a, fake.document("the red door"))          # the same every run
    assert float(a @ b) > float(a @ c) and abs(float(np.linalg.norm(a)) - 1) < 1e-6


def test_the_choice_of_embedder(monkeypatch):
    monkeypatch.setenv("GM_EMBEDDER", "off")
    assert embedder_mod.get_embedder() is None
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    assert embedder_mod.get_embedder().name == "fake"


def test_new_and_changed_texts_get_vectors(dcc_world, monkeypatch):
    monkeypatch.setenv("GM_EMBEDDER", "fake")              # updates at once, in this process
    notes = NoteManager(dcc_world)
    fid = notes.add_fact("The stairwell door is braced open.", holders=["player"])
    store = EmbeddingStore(_camp(dcc_world))
    vectors = store.vectors("fake")
    assert f"fact:{fid}" in vectors and len(vectors) == len(texts(_camp(dcc_world)))
    assert store.counts("fake") == (len(vectors), 0)

    PlotManager(dcc_world).add("The Descent", "Down the stairs.", stands="The timer runs.")
    before = store.load()[1]["plot:The Descent"][0]
    PlotManager(dcc_world).set_stands("The Descent", "Carl is on floor two.")
    assert store.load()[1]["plot:The Descent"][0] != before         # embedded again

    aid = notes.set_attitude("Mordecai", "wary", "player")       # adjectives: on the cards, not embedded
    assert aid and f"fact:{aid}" not in store.vectors("fake")
    assert all(k in texts(_camp(dcc_world)) for k in store.vectors("fake"))


def test_off_writes_nothing(dcc_world):
    NoteManager(dcc_world).add_fact("Nothing to embed.", holders=["player"])
    assert not (_camp(dcc_world) / STORE).exists()


def test_a_change_of_model_embeds_everything_again(dcc_world):
    store = EmbeddingStore(_camp(dcc_world))
    store.update(embedder_mod.FakeEmbedder())
    total = len(texts(_camp(dcc_world)))

    class Other(embedder_mod.FakeEmbedder):
        name = "other"
    assert store.pending("other")[0].keys() == texts(_camp(dcc_world)).keys()
    assert store.update(Other()) == total and store.load()[0] == "other"


def test_one_job_at_a_time(dcc_world, monkeypatch):
    """A job that finds the lock taken leaves at once; the running one picks up
    what is new."""
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    with open(_camp(dcc_world) / LOCK, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert job(_camp(dcc_world)) == 0
        assert not (_camp(dcc_world) / STORE).exists()
    assert job(_camp(dcc_world)) == 0 and (_camp(dcc_world) / STORE).exists()


@pytest.mark.skipif(embedder_mod.packages_missing() or embedder_mod.files_missing(),
                    reason="semantic recall not installed (uv sync; gm-recall.sh setup)")
def test_the_real_model_finds_the_clown():
    e = embedder_mod.Embedder()
    q = e.query("the clown")
    pagliacci = e.document("Pagliacci took off his makeup in the dark and wept.")
    convoy = e.document("Dario Vella has contracted Mirela Kostic's convoy.")
    assert float(q @ pagliacci) > float(q @ convoy)
