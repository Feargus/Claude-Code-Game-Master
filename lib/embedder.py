#!/usr/bin/env python3
"""Text in, vector out: EmbeddingGemma-300m (4-bit) on ONNX Runtime, for semantic recall.

A vector (an embedding) stands for what a text means; texts that mean similar
things get vectors that point the same way, so "the clown" finds "Pagliacci took
off his makeup and wept". Chosen by a benchmark on a Raspberry Pi 4 (2026-11-15):
0.5 GB of RAM, about 6 s to load, about 0.8 s per text.

Optional. It needs the `recall` extra (`uv sync --extra recall`: numpy,
onnxruntime, tokenizers) and the model files (`gm-recall.sh setup`, 217 MB, into
GM_MODELS_DIR, default `models/` beside `lib/`). Without them `get_embedder()`
returns None and everything works as before, by recency.

Tests set GM_EMBEDDER=fake: vectors from the words' hashes, the same every run,
so the suite needs neither the packages nor the model.

    gm-recall.sh setup      download and check the model files
    gm-recall.sh status     what is installed, and where
"""

import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_NAME = "embeddinggemma-300m-q4"
DIMENSIONS = 768
REPO = "onnx-community/embeddinggemma-300m-ONNX"
REVISION = "5090578d9565bb06545b4552f76e6bc2c93e4a66"     # the one tested on the Pi
FILES = {   # path in the repo: (size in bytes, sha256)
    "onnx/model_q4.onnx": (519322, "ad1dfee81a70f7944b9b9d1cc6e48075b832881cf33fab2f2b248be78f3f0043"),
    "onnx/model_q4.onnx_data": (196725760, "599962c3143b040de2dd05e5975be3e9091dd067cacc6a8f7186e3203bab9e02"),
    "tokenizer.json": (20323312, "4dda02faaf32bc91031dc8c88457ac272b00c1016cc679757d1c441b248b9c47"),
}
QUERY_PREFIX = "task: search result | query: "      # the model's own prompts
DOCUMENT_PREFIX = "title: none | text: "
MAX_TOKENS = 512


class EmbedderError(RuntimeError):
    """Semantic recall can't run as asked. The message says what to do."""


def models_dir() -> Path:
    return Path(os.environ.get("GM_MODELS_DIR") or ROOT / "models") / MODEL_NAME


def _local(path: str) -> Path:
    return models_dir() / Path(path).name


def packages_missing() -> list[str]:
    import importlib.util
    return [p for p in ("numpy", "onnxruntime", "tokenizers") if importlib.util.find_spec(p) is None]


def files_missing() -> list[str]:
    return [p for p, (size, _) in FILES.items()
            if not _local(p).exists() or _local(p).stat().st_size != size]


def _import_onnxruntime():
    """ONNX Runtime warns on import that it found no GPU (the Pi has none); its
    C++ code writes to the error stream directly, before any setting applies,
    so the stream is muted for the import only."""
    if "onnxruntime" in sys.modules:
        return sys.modules["onnxruntime"]
    sys.stderr.flush()
    saved = os.dup(2)
    try:
        with open(os.devnull, "w") as null:
            os.dup2(null.fileno(), 2)
            import onnxruntime
    finally:
        os.dup2(saved, 2)
        os.close(saved)
    return onnxruntime


class Embedder:
    """The real model. Loaded on first use; each vector has length 1."""

    name = MODEL_NAME

    def __init__(self, threads: int = 4):
        self.threads = threads
        self._session = None
        self._tokenizer = None

    def _load(self):
        if self._session is not None:
            return
        missing = packages_missing()
        if missing:
            raise EmbedderError(f"Semantic recall needs {', '.join(missing)}: "
                                f"uv sync --extra recall")
        if files_missing():
            raise EmbedderError("The model files are missing: bash tools/gm-recall.sh setup")
        ort = _import_onnxruntime()
        from tokenizers import Tokenizer
        ort.set_default_logger_severity(3)
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.threads
        self._session = ort.InferenceSession(str(_local("onnx/model_q4.onnx")), options,
                                             providers=["CPUExecutionProvider"])
        self._tokenizer = Tokenizer.from_file(str(_local("tokenizer.json")))
        self._tokenizer.no_padding()               # one text at a time: no padding needed
        self._tokenizer.enable_truncation(MAX_TOKENS)

    def _one(self, text: str):
        import numpy as np
        self._load()
        enc = self._tokenizer.encode(text)
        feed = {"input_ids": np.array([enc.ids], dtype=np.int64),
                "attention_mask": np.array([enc.attention_mask], dtype=np.int64)}
        vector = self._session.run(["sentence_embedding"], feed)[0][0].astype(np.float32)
        return vector / np.linalg.norm(vector)

    def query(self, text: str):
        """A question or a scene, to rank stored texts against."""
        return self._one(QUERY_PREFIX + text)

    def document(self, text: str):
        """A text to be found later (a fact, a place, a plot)."""
        return self._one(DOCUMENT_PREFIX + text)


class FakeEmbedder:
    """For tests: each word adds to a few dimensions picked by its hash, so texts
    that share words point the same way. Deterministic, instant, no packages
    beyond numpy."""

    name = "fake"

    def _vector(self, text: str):
        import numpy as np
        v = np.zeros(DIMENSIONS, dtype=np.float32)
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            h = hashlib.sha256(word.encode()).digest()
            for i in range(3):
                v[int.from_bytes(h[2 * i:2 * i + 2], "big") % DIMENSIONS] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    query = document = _vector


def get_embedder():
    """The embedder to use, or None when semantic recall isn't installed.
    GM_EMBEDDER=fake (tests) or off chooses explicitly."""
    choice = os.environ.get("GM_EMBEDDER", "")
    if choice == "off":
        return None
    if choice == "fake":
        return FakeEmbedder()
    if packages_missing() or files_missing():
        return None
    return Embedder()


# ---------- setup and status ----------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def setup() -> list[str]:
    """Download the model files that are missing, check them, and return what was done."""
    import urllib.request
    target = models_dir()
    target.mkdir(parents=True, exist_ok=True)
    done = []
    for path, (size, digest) in FILES.items():
        local = _local(path)
        if local.exists() and local.stat().st_size == size and _sha256(local) == digest:
            done.append(f"{local.name}: already there")
            continue
        part = local.with_name(local.name + ".part")
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{path}"
        print(f"Downloading {local.name} ({size / 1e6:.0f} MB) ...", flush=True)
        try:
            urllib.request.urlretrieve(url, part)
        except OSError as error:
            part.unlink(missing_ok=True)
            raise EmbedderError(f"Could not download {url}: {error}") from error
        if part.stat().st_size != size or _sha256(part) != digest:
            part.unlink(missing_ok=True)
            raise EmbedderError(f"{local.name} arrived damaged (wrong size or checksum); "
                                f"run the setup again.")
        part.replace(local)
        done.append(f"{local.name}: downloaded and checked")
    return done


def status() -> list[str]:
    missing = packages_missing()
    files = files_missing()
    lines = [f"Model: {MODEL_NAME} ({REPO} at {REVISION[:8]})",
             f"Folder: {models_dir()}",
             "Packages: " + ("installed" if not missing else
                             f"missing {', '.join(missing)} (uv sync --extra recall)"),
             "Files: " + ("all there" if not files else
                          f"missing {', '.join(Path(f).name for f in files)} "
                          f"(bash tools/gm-recall.sh setup)")]
    lines.append("Semantic recall: " + ("ready" if not missing and not files else
                                        "off; facts are ranked by recency"))
    return lines


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if action == "setup":
            for line in setup():
                print(line)
            print("[SUCCESS] The model is ready." if not packages_missing() else
                  "[SUCCESS] The model files are ready; the packages still need: "
                  "uv sync --extra recall")
        elif action == "status":
            print("\n".join(status()))
        else:
            print(f"[ERROR] Unknown action '{action}': setup or status.", file=sys.stderr)
            return 1
    except EmbedderError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
