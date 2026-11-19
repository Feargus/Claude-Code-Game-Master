#!/usr/bin/env python3
"""The book's pieces and their vectors, for searching a campaign's source book by meaning.

Kept in the campaign's `vectors/` folder (not in git: rebuilt from the book):

    chunks.json   the pieces of the book: [{"id", "text", "metadata"}], written at import
    book.npz      their vectors (16-bit), by id, and the name of the model that made them

The vectors come from the same model as the facts' (embedder.py, EmbeddingGemma),
made by a background job (`index`): one at a time (a lock), saving as it goes, so it
resumes where it stopped. About 4 s per piece of 1,500 characters on a Raspberry
Pi 4: some 15 minutes for a novel. A search before it is done uses the pieces
embedded so far, and says how far it is.

A search compares the question with every piece directly; a few thousand pieces
take milliseconds, so no database is needed (this replaced chromadb, 2026-11-16).
Distances are cosine distances (1 - similarity), as chromadb's were, so the
thresholds that read them (entity_enhancer.py) stay as they were.

    vector_store.py index <campaign folder>     the background job
    vector_store.py wait <campaign folder>      wait (up to 9 minutes) until it is done
    vector_store.py status <campaign folder>    how much of the book is indexed

A book is indexed once: the finished index is kept in world-state/book-index/<key>/
(the key: the book's text and how it is cut), and a later campaign from the same
book copies it in seconds. Nothing that needs the index uses a half-done one: the
readers refuse it with what to do (`not_ready`), and /import waits for it.
"""

import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CHUNKS = "chunks.json"
VECTORS = "book.npz"
SOURCE = "source.json"      # which book (its key in the shared index)
LOCK = "index.lock"
LOG = "index.log"
SAVE_EVERY = 10
SHARED = "book-index"       # world-state/book-index/<key>/: a book indexed once, for every campaign
ROOT = Path(__file__).resolve().parent.parent.parent


def book_key(text: str, chunk_size: int) -> str:
    """The same book, cut the same way, has the same key."""
    import hashlib
    return hashlib.sha256(f"{chunk_size}|{text}".encode()).hexdigest()[:16]


def shared_dir(key: str) -> Path:
    base = Path(os.environ.get("GM_WORLD_STATE_BASE") or ROOT / "world-state")
    return base / SHARED / key


class CampaignVectorStore:
    """The book's pieces and vectors for one campaign."""

    def __init__(self, campaign_dir: str, collection_name: str = "document_chunks"):
        # Guard the str(None) trap: a caller with no active campaign passes "None".
        if campaign_dir is None or str(campaign_dir) in ("", "None"):
            raise ValueError("CampaignVectorStore requires a real campaign dir (no active campaign?)")
        self.campaign_dir = Path(campaign_dir)
        self.vectors_dir = self.campaign_dir / "vectors"
        self.collection_name = collection_name
        self._cache = None

    @staticmethod
    def is_available() -> bool:
        """Semantic recall is installed (the packages and the model)."""
        from embedder import files_missing, packages_missing
        return not packages_missing() and not files_missing()

    # ---------- the pieces ----------

    def chunks(self) -> list[dict]:
        path = self.vectors_dir / CHUNKS
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except ValueError:
            return []

    def set_chunks(self, chunks: list[str], metadatas: list[dict] | None = None,
                   ids: list[str] | None = None) -> int:
        """Store the book's pieces (texts only; the job embeds them). Replaces
        any earlier book and its vectors."""
        self.vectors_dir.mkdir(parents=True, exist_ok=True)
        ids = ids or [f"doc_{i:04d}" for i in range(len(chunks))]
        metadatas = metadatas or [{"chunk_index": i} for i in range(len(chunks))]
        rows = [{"id": i, "text": t, "metadata": m}
                for i, t, m in zip(ids, chunks, metadatas, strict=True)]
        _write(self.vectors_dir / CHUNKS, json.dumps(rows, ensure_ascii=False))
        with contextlib.suppress(FileNotFoundError):
            (self.vectors_dir / VECTORS).unlink()
        self._cache = None
        return len(rows)

    # ---------- the vectors ----------

    def _vectors(self) -> tuple[str, dict]:
        """(model name, {id: vector}), cached for this object."""
        if self._cache is None:
            path = self.vectors_dir / VECTORS
            if not path.exists():
                self._cache = ("", {})
            else:
                import numpy as np
                try:
                    with np.load(path) as data:
                        self._cache = (str(data["model"]), dict(zip(
                            data["ids"].tolist(), data["vectors"].astype("float32"), strict=True)))
                except (OSError, ValueError, KeyError):
                    self._cache = ("", {})
        return self._cache

    def _save(self, model: str, vectors: dict) -> None:
        import numpy as np
        ids = list(vectors)
        tmp = self.vectors_dir / (VECTORS + ".tmp.npz")
        np.savez(tmp, model=np.array(model), ids=np.array(ids, dtype=str),
                 vectors=(np.stack([vectors[i] for i in ids]).astype(np.float16) if ids
                          else np.zeros((0, 0), dtype=np.float16)))
        os.replace(tmp, self.vectors_dir / VECTORS)
        self._cache = (model, dict(vectors))

    def index(self, embedder, progress=None) -> int:
        """Embed the pieces that have no vector yet (all of them after a change of
        model), saving every SAVE_EVERY. Returns how many were embedded."""
        model, vectors = self._vectors()
        vectors = dict(vectors) if model == embedder.name else {}
        rows = self.chunks()
        wanted = {r["id"] for r in rows}
        vectors = {i: v for i, v in vectors.items() if i in wanted}
        todo = [r for r in rows if r["id"] not in vectors]
        for n, row in enumerate(todo, 1):
            vectors[row["id"]] = embedder.document(row["text"])
            if progress:
                progress(n, len(todo))
            if n % SAVE_EVERY == 0:
                self._save(embedder.name, vectors)
        if todo or model != embedder.name:
            self._save(embedder.name, vectors)
        return len(todo)

    def add_chunks(self, chunks: list[str], embeddings, metadatas=None, ids=None) -> int:
        """Pieces with their vectors already made (kept for the old interface)."""
        from embedder import MODEL_NAME
        self.set_chunks(chunks, metadatas, ids)
        rows = self.chunks()
        self._save(MODEL_NAME, {r["id"]: e for r, e in zip(rows, embeddings, strict=True)})
        return len(rows)

    # ---------- searching ----------

    def query_similar(self, query_embedding, n_results: int = 10, where: dict | None = None,
                      where_document: dict | None = None) -> dict[str, Any]:
        """The pieces closest to the query vector: {"ids", "documents", "metadatas",
        "distances"}, closest first. `where`: metadata values that must match."""
        import numpy as np
        _, vectors = self._vectors()
        q = np.asarray(query_embedding, dtype=np.float32)
        rows = [r for r in self.chunks() if r["id"] in vectors and all(
            r.get("metadata", {}).get(k) == v for k, v in (where or {}).items())]
        if where_document and "$contains" in where_document:
            rows = [r for r in rows if where_document["$contains"] in r["text"]]
        scored = sorted(((1.0 - float(vectors[r["id"]] @ q), r) for r in rows),
                        key=lambda pair: pair[0])[:n_results]
        return {"ids": [r["id"] for _, r in scored], "documents": [r["text"] for _, r in scored],
                "metadatas": [r.get("metadata", {}) for _, r in scored],
                "distances": [d for d, _ in scored]}

    def query_by_text(self, query_text: str, embedder, n_results: int = 10,
                      where: dict | None = None) -> dict[str, Any]:
        """As query_similar, the question embedded as a query."""
        return self.query_similar(embedder.query(query_text), n_results=n_results, where=where)

    def get_by_category(self, category: str, limit: int = 100) -> list[dict]:
        return [{"id": r["id"], "document": r["text"], "metadata": r.get("metadata", {})}
                for r in self.chunks() if r.get("metadata", {}).get("category") == category][:limit]

    # ---------- counts ----------

    def count(self) -> int:
        """Pieces that can be found (embedded)."""
        _, vectors = self._vectors()
        return sum(1 for r in self.chunks() if r["id"] in vectors)

    def count_by_category(self) -> dict[str, int]:
        counts = {}
        for r in self.chunks():
            cat = r.get("metadata", {}).get("category", "uncategorized")
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def progress(self) -> tuple[int, int]:
        """(pieces embedded, pieces in all)."""
        return self.count(), len(self.chunks())

    def complete(self) -> bool:
        done, total = self.progress()
        return total > 0 and done == total

    def not_ready(self) -> str:
        """'' when the book can be searched; else why not and what to do."""
        done, total = self.progress()
        if not total:
            return "This campaign has no book indexed (gm-extract.sh prepare)."
        if done < total:
            return (f"The book is still being indexed ({done} of {total} pieces). Wait for it: "
                    f"bash tools/gm-extract.sh wait")
        return ""

    # ---------- the shared index: a book is indexed once ----------

    def set_source(self, key: str, document: str) -> None:
        self.vectors_dir.mkdir(parents=True, exist_ok=True)
        _write(self.vectors_dir / SOURCE, json.dumps({"key": key, "document": document}))

    def source_key(self) -> str:
        path = self.vectors_dir / SOURCE
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("key", "") if path.exists() else ""
        except ValueError:
            return ""

    def from_shared(self, key: str) -> bool:
        """Copy the book's finished index from an earlier campaign, if there is one
        made with the current model. True when copied."""
        import shutil

        from embedder import MODEL_NAME
        source = CampaignVectorStore.__new__(CampaignVectorStore)
        source.campaign_dir, source.vectors_dir, source._cache = None, shared_dir(key), None
        source.collection_name = self.collection_name
        if not source.complete() or source._vectors()[0] != MODEL_NAME:
            return False
        self.vectors_dir.mkdir(parents=True, exist_ok=True)
        for name in (CHUNKS, VECTORS):
            shutil.copyfile(source.vectors_dir / name, self.vectors_dir / (name + ".tmp"))
            os.replace(self.vectors_dir / (name + ".tmp"), self.vectors_dir / name)
        self._cache = None
        return True

    def share(self) -> bool:
        """Put this campaign's finished index where later campaigns find it."""
        import shutil
        key = self.source_key()
        if not key or not self.complete():
            return False
        target = shared_dir(key)
        target.mkdir(parents=True, exist_ok=True)
        for name in (CHUNKS, VECTORS, SOURCE):
            shutil.copyfile(self.vectors_dir / name, target / (name + ".tmp"))
            os.replace(target / (name + ".tmp"), target / name)
        return True

    def clear(self) -> None:
        for name in (CHUNKS, VECTORS):
            with contextlib.suppress(FileNotFoundError):
                (self.vectors_dir / name).unlink()
        self._cache = None

    def persist(self) -> None:
        """Nothing to do: every change is written at once."""

    def get_stats(self) -> dict[str, Any]:
        model, _ = self._vectors()
        done, total = self.progress()
        return {"collection_name": self.collection_name, "total_chunks": total,
                "embedded_chunks": done, "model": model, "vectors_dir": str(self.vectors_dir),
                "categories": self.count_by_category()}


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------- the background job ----------

def index_job(campaign_dir) -> int:
    """Embed the book's pieces until all are done; one job at a time."""
    import fcntl

    from embedder import get_embedder
    store = CampaignVectorStore(campaign_dir)
    embedder = get_embedder()
    if embedder is None or not store.chunks():
        return 0
    store.vectors_dir.mkdir(parents=True, exist_ok=True)
    with open(store.vectors_dir / LOCK, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        start = time.time()
        try:
            done = store.index(embedder)
        except Exception as error:                 # noqa: BLE001 (a background job logs, it doesn't crash silently)
            _log(store, f"error: {type(error).__name__}: {error}")
            return 1
        _log(store, f"indexed {done} pieces in {time.time() - start:.0f} s "
                    f"({store.count()} of {len(store.chunks())})")
        if store.share():
            _log(store, f"shared for later campaigns: {shared_dir(store.source_key())}")
    return 0


def _job_running(store: CampaignVectorStore) -> bool:
    import fcntl
    if not (store.vectors_dir / LOCK).exists():
        return False
    with open(store.vectors_dir / LOCK, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock, fcntl.LOCK_UN)
    return False


def wait(campaign_dir, minutes: float = 9.0) -> int:
    """Wait until the book is indexed, at most `minutes` (a command may run for 10
    at most). Starts the job again if none is running (after a restart). 0: done;
    2: still indexing, call again; 1: it can't be indexed."""
    store = CampaignVectorStore(campaign_dir)
    if not store.chunks():
        print("[ERROR] This campaign has no book to index (gm-extract.sh prepare).", file=sys.stderr)
        return 1
    if not CampaignVectorStore.is_available():
        print("[ERROR] The book can't be indexed: semantic recall isn't installed "
              "(bash tools/gm-recall.sh status).", file=sys.stderr)
        return 1
    deadline, start = time.time() + minutes * 60, store.count()
    began = time.time()
    while True:
        store._cache = None
        done, total = store.progress()
        if done >= total:
            print(f"[SUCCESS] The book is indexed: {total} pieces.")
            return 0
        if not _job_running(store):
            start_index_job(campaign_dir)
        if time.time() >= deadline:
            rate = (done - start) / max(1.0, time.time() - began)
            left = f", about {round((total - done) / rate / 60)} min left" if rate > 0 else ""
            print(f"Still indexing: {done} of {total} pieces{left}. "
                  f"Run bash tools/gm-extract.sh wait again.")
            return 2
        time.sleep(10)


def start_index_job(campaign_dir) -> bool:
    """Start the job in the background; False when semantic recall isn't installed."""
    if os.environ.get("GM_EMBEDDER") == "off" or not CampaignVectorStore.is_available():
        return False
    store = CampaignVectorStore(campaign_dir)
    store.vectors_dir.mkdir(parents=True, exist_ok=True)
    with open(store.vectors_dir / LOG, "a") as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "index",
                          str(Path(campaign_dir).resolve())], stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, start_new_session=True, close_fds=True)
    return True


def _log(store: CampaignVectorStore, line: str) -> None:
    with contextlib.suppress(OSError), open(store.vectors_dir / LOG, "a") as log:
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")


def status_line(campaign_dir) -> str:
    """One line for gm-recall.sh status; '' when the campaign has no book."""
    store = CampaignVectorStore(campaign_dir)
    done, total = store.progress()
    if not total:
        return ""
    if done >= total:
        return f"The book: all {total} pieces indexed"
    return f"The book: {done} of {total} pieces indexed (the job goes on in the background)"


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "index":
        return index_job(sys.argv[2])
    if len(sys.argv) in (3, 4) and sys.argv[1] == "wait":
        return wait(sys.argv[2], float(sys.argv[3]) if len(sys.argv) == 4 else 9.0)
    if len(sys.argv) == 3 and sys.argv[1] == "status":
        print(status_line(sys.argv[2]) or "This campaign has no book indexed.")
        return 0
    print("[ERROR] Use: vector_store.py index | status <campaign folder>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
