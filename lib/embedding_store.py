#!/usr/bin/env python3
"""The campaign's embeddings: one vector per fact, place and plot, kept up to date
by a background job.

Kept in `embeddings.npz` beside facts.json, not in git (derived: rebuilt when
missing). Each entry has a key (`fact:f12`, `location:The Dry Quay`,
`plot:The Lapse`), a hash of the text it was made from, and the vector, stored
as 16-bit numbers (1.5 KB each; ranking doesn't notice the precision). A changed
text is embedded again; a change of model embeds everything again.

**When.** A command that records or rewrites a text (a fact, a place's
description, a plot's sentence) asks for an update (`request()`); when the
command ends, a background job starts and the command returns at once. The job
takes a lock (one job at a time), embeds what is new or changed, saving as it
goes, and exits. It runs while the player reads and types: about 6 s to load the
model, under a second per text (embedder.py). A command that reads the vectors
before the job is done uses what is there; a text without a vector yet is
treated as average (ranking, later).

    gm-recall.sh embed       run the update now, in the foreground
    gm-recall.sh status      the model, and how much of this campaign is embedded

Tests: GM_EMBEDDER=off (conftest) starts nothing; GM_EMBEDDER=fake updates at
once, in the same process, with the fake embedder.
"""

import atexit
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

STORE = "embeddings.npz"
LOCK = "embeddings.lock"
LOG = "embeddings.log"
SAVE_EVERY = 5              # entries embedded between saves, so a killed job loses little
LOG_LINES = 200
NOTES_AT_MOST = 10          # new facts in one job; more is a first embedding, not play


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def npc_text(name: str, sheet: dict) -> str:
    """Who someone is, in a line: name, role, background, what they are after."""
    identity = sheet.get("identity") or {}
    parts = [identity.get("role"), identity.get("background"),
             (sheet.get("status") or {}).get("goal"), (sheet.get("personality") or {}).get("want")]
    return f"{name}: " + "; ".join(str(p) for p in parts if p)


def location_text(name: str, place: dict) -> str:
    """What a place is: its description, or where it is while it has none."""
    return f"{name}: " + str(place.get("description") or place.get("position") or "").strip()


def texts(campaign_dir: Path) -> dict[str, str]:
    """What should have a vector: {key: text}. Facts (attitudes aside: they are
    adjectives, shown on the cards), places, people, and plots (what they are
    about and where they stand)."""
    def load(name):
        path = Path(campaign_dir) / name
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except ValueError:
            return {}
    out = {}
    for items in (load("facts.json") or {}).values():
        for f in items if isinstance(items, list) else []:
            if isinstance(f, dict) and f.get("id") and f.get("fact") and not f.get("attitude"):
                out[f"fact:{f['id']}"] = str(f["fact"])
    for name, loc in (load("locations.json") or {}).items():
        if isinstance(loc, dict):
            out[f"location:{name}"] = location_text(name, loc)
    for name, sheet in (load("npcs.json") or {}).items():
        if isinstance(sheet, dict):
            out[f"npc:{name}"] = npc_text(name, sheet)
    character = load("character.json") or {}
    if character.get("identity"):                  # to compare with (recall_notes.py)
        out["player"] = npc_text(character["identity"].get("name") or "the character", character)
    for key, plot in (load("plots.json") or {}).items():
        if isinstance(plot, dict):
            parts = [plot.get("description"), plot.get("stands"), plot.get("summary")]
            out[f"plot:{key}"] = f"{key}: " + " ".join(str(p) for p in parts if p)
    return out


class EmbeddingStore:
    def __init__(self, campaign_dir):
        self.dir = Path(campaign_dir)
        self.path = self.dir / STORE

    def load(self) -> tuple[str, dict]:
        """(model name, {key: (hash, vector)}); ('', {}) when there is none yet."""
        if not self.path.exists():
            return "", {}
        import numpy as np
        try:
            with np.load(self.path) as data:
                model = str(data["model"])
                return model, {k: (h, v) for k, h, v in
                               zip(data["keys"].tolist(), data["hashes"].tolist(), data["vectors"], strict=True)}
        except (OSError, ValueError, KeyError):
            return "", {}                          # damaged: rebuilt by the next job

    def save(self, model: str, entries: dict) -> None:
        """Written to a temporary file, then renamed: a reader never sees half a file."""
        import numpy as np
        keys = list(entries)
        vectors = (np.stack([entries[k][1] for k in keys]).astype(np.float16) if keys
                   else np.zeros((0, 0), dtype=np.float16))
        tmp = self.path.with_name(STORE + ".tmp.npz")
        np.savez(tmp, model=np.array(model), keys=np.array(keys, dtype=str),
                 hashes=np.array([entries[k][0] for k in keys], dtype=str), vectors=vectors)
        os.replace(tmp, self.path)

    def pending(self, embedder_name: str) -> tuple[dict, list[str]]:
        """({key: text} to embed, [keys whose text is gone])."""
        model, stored = self.load()
        if model != embedder_name:
            stored = {}
        wanted = texts(self.dir)
        todo = {k: t for k, t in wanted.items()
                if k not in stored or stored[k][0] != _hash(t)}
        return todo, [k for k in stored if k not in wanted]

    def update(self, embedder, limit: int = 0, progress=None) -> int:
        """Embed what is new or changed (at most `limit`, 0: all). Returns how many."""
        model, stored = self.load()
        if model != embedder.name:
            stored = {}
        todo, gone = self.pending(embedder.name)
        for key in gone:
            stored.pop(key, None)
        items = list(todo.items())[:limit or None]
        self.last_embedded = [k for k, _ in items]
        done = 0
        for key, text in items:
            stored[key] = (_hash(text), embedder.document(text))
            done += 1
            if progress:
                progress(done, len(items))
            if done % SAVE_EVERY == 0:
                self.save(embedder.name, stored)
        if done or gone or model != embedder.name:
            self.save(embedder.name, stored)
        return done

    def counts(self, embedder_name: str) -> tuple[int, int]:
        """(embedded and current, waiting)."""
        todo, _ = self.pending(embedder_name)
        return len(texts(self.dir)) - len(todo), len(todo)

    def vectors(self, embedder_name: str):
        """{key: vector (float32)} for the current texts, for ranking."""
        model, stored = self.load()
        if model != embedder_name:
            return {}
        wanted = texts(self.dir)
        return {k: v.astype("float32") for k, (h, v) in stored.items()
                if k in wanted and h == _hash(wanted[k])}


# ---------- the background job ----------

def _log(campaign_dir: Path, line: str) -> None:
    path = Path(campaign_dir) / LOG
    with contextlib.suppress(OSError):
        old = path.read_text(encoding="utf-8").splitlines()[-LOG_LINES:] if path.exists() else []
        path.write_text("\n".join(old + [f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}"]) + "\n",
                        encoding="utf-8")


def job(campaign_dir) -> int:
    """The background job: one at a time (a lock); embeds until nothing is waiting.
    A job that finds the lock taken leaves: the running one picks up the new texts."""
    import fcntl

    from embedder import get_embedder
    campaign_dir = Path(campaign_dir)
    embedder = get_embedder()
    if embedder is None:
        return 0
    store = EmbeddingStore(campaign_dir)
    total = 0
    with open(campaign_dir / LOCK, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        start = time.time()
        new_facts = []
        try:
            while True:
                done = store.update(embedder)
                total += done
                new_facts += [k[5:] for k in store.last_embedded if k.startswith("fact:")]
                if not done:
                    break
            # Notes for the next command (recall_notes.py); not after a first embedding
            # of a whole campaign, which would make a note of every fact.
            if 0 < len(new_facts) <= NOTES_AT_MOST:
                from recall_notes import add_notes, make_notes
                add_notes(campaign_dir, make_notes(campaign_dir, new_facts, embedder,
                                                   store.vectors(embedder.name)))
        except Exception as error:                 # noqa: BLE001 (a background job must log, not crash silently)
            _log(campaign_dir, f"error after {total}: {type(error).__name__}: {error}")
            return 1
        if total:
            _log(campaign_dir, f"embedded {total} in {time.time() - start:.0f} s")
    return 0


_requested: set = set()


def request(campaign_dir) -> None:
    """Ask for an update when this command ends (once per command, however many
    texts it wrote). Does nothing when semantic recall isn't installed."""
    choice = os.environ.get("GM_EMBEDDER", "")
    if choice == "off" or campaign_dir is None:
        return
    campaign_dir = Path(campaign_dir).resolve()
    if choice == "fake":                           # tests: at once, in this process
        from embedder import FakeEmbedder
        EmbeddingStore(campaign_dir).update(FakeEmbedder())
        return
    if campaign_dir in _requested:
        return
    if not _requested:
        atexit.register(_start_jobs)
    _requested.add(campaign_dir)


def _start_jobs() -> None:
    from embedder import files_missing, packages_missing
    if packages_missing() or files_missing():
        return
    for campaign_dir in _requested:
        with contextlib.suppress(OSError), open(campaign_dir / LOG, "a") as log:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "job",
                              str(campaign_dir)], stdin=subprocess.DEVNULL, stdout=log,
                             stderr=log, start_new_session=True, close_fds=True)


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["job"] and len(args) == 2:
        return job(args[1])
    from campaign_manager import CampaignManager
    from embedder import get_embedder
    campaign = CampaignManager().get_active_campaign_dir()
    if campaign is None:
        print("[ERROR] No active campaign.", file=sys.stderr)
        return 1
    store = EmbeddingStore(campaign)
    embedder = get_embedder()
    if args[:1] == ["status"]:
        if embedder is None:
            print("This campaign: not embedded (semantic recall is off)")
        else:
            have, waiting = store.counts(embedder.name)
            print(f"This campaign: {have} texts embedded, {waiting} waiting")
        return 0
    if args[:1] == ["embed"]:
        if embedder is None:
            print("[ERROR] Semantic recall isn't installed: bash tools/gm-recall.sh status",
                  file=sys.stderr)
            return 1
        def show(done, total):
            print(f"\r  {done}/{total}", end="", flush=True)
        start = time.time()
        done = store.update(embedder, progress=show)
        print(f"\n[SUCCESS] Embedded {done} texts in {time.time() - start:.0f} s." if done
              else "[SUCCESS] Everything is embedded already.")
        return 0
    print("[ERROR] Use: embedding_store.py status | embed | job <campaign folder>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
