"""The helper process that keeps the model loaded (embed_helper.py).
It serves the fake embedder here, on a socket of the test's own."""

import time

import pytest

np = pytest.importorskip("numpy")

from lib import embed_helper  # noqa: E402
from lib.embedder import FakeEmbedder  # noqa: E402


@pytest.fixture
def helper(tmp_path, monkeypatch):
    monkeypatch.setenv("GM_EMBED_SOCKET", str(tmp_path / "h.sock"))
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    monkeypatch.setenv("GM_EMBED_IDLE", "60")
    yield
    embed_helper.stop()


def test_it_starts_by_itself_answers_and_stops(helper):
    assert embed_helper.ping() is None
    client = embed_helper.HelperEmbedder("fake")
    v = client.document("the red door")
    assert np.allclose(v, FakeEmbedder().document("the red door"))
    state = embed_helper.ping()
    assert state and state["served"] == 1 and client._local is None      # answered by the helper
    assert np.allclose(client.query("a door"), FakeEmbedder().query("a door"))
    assert embed_helper.stop() and embed_helper.ping() is None


def test_it_exits_when_unused(helper, monkeypatch):
    monkeypatch.setenv("GM_EMBED_IDLE", "1")
    embed_helper.HelperEmbedder("fake").document("x")
    time.sleep(2.5)
    assert embed_helper.ping() is None


def test_an_outdated_helper_is_replaced(helper, monkeypatch):
    embed_helper.HelperEmbedder("fake").document("x")
    old = embed_helper.ping()["pid"]
    monkeypatch.setenv("GM_EMBED_VERSION_EXTRA", "changed")            # as after a git pull
    embed_helper.HelperEmbedder("fake").document("x")
    assert embed_helper.ping()["pid"] != old


def test_without_a_helper_the_model_is_loaded_here(tmp_path, monkeypatch):
    monkeypatch.setenv("GM_EMBED_SOCKET", "/proc/no-such-place/h.sock")    # can't be made
    monkeypatch.setenv("GM_EMBEDDER", "fake")
    client = embed_helper.HelperEmbedder("fake")
    assert np.allclose(client.document("x"), FakeEmbedder().document("x"))
    assert client._local is not None
