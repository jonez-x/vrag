"""Dense retrieval: Ollama embeddings cached in a local sqlite-vec store."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import struct
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from ..config import DenseConfig


class EmbedderUnavailable(RuntimeError):
    """Raised when the embedding backend (Ollama or the model) is not reachable."""


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    """Calls Ollama's /api/embed — stdlib only, no client dependency."""

    def __init__(self, model: str, url: str = "http://localhost:11434", timeout: float = 120.0):
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        body = json.dumps({"model": self.model, "input": texts}).encode()
        req = urllib.request.Request(f"{self.url}/api/embed", body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:  # 404 = model not pulled
            detail = e.read().decode(errors="replace").strip()
            raise EmbedderUnavailable(
                f"Ollama rejected model '{self.model}' ({e.code}: {detail}) — try `ollama pull {self.model}`"
            ) from e
        except (urllib.error.URLError, OSError) as e:
            raise EmbedderUnavailable(f"Ollama not reachable at {self.url} ({e}) — is `ollama serve` running?") from e
        vecs = data.get("embeddings")
        if not vecs or len(vecs) != len(texts):
            raise EmbedderUnavailable(f"Ollama returned no embeddings for model '{self.model}'")
        return vecs


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class VectorStore:
    """Embedding cache keyed by (model, sha1(text)); similarity via sqlite-vec when loadable."""

    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS embeddings (model TEXT, hash TEXT, vec BLOB, PRIMARY KEY (model, hash))")
        self.has_vec = _load_sqlite_vec(self.db)

    def get_many(self, model: str, hashes: list[str]) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for i in range(0, len(hashes), 500):
            part = hashes[i : i + 500]
            q = f"SELECT hash, vec FROM embeddings WHERE model = ? AND hash IN ({','.join('?' * len(part))})"
            out.update(self.db.execute(q, [model, *part]).fetchall())
        return out

    def put_many(self, model: str, items: dict[str, list[float]]) -> None:
        self.db.executemany(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?)", [(model, h, _pack(v)) for h, v in items.items()]
        )
        self.db.commit()

    def similarities(self, model: str, query: list[float], hashes: list[str]) -> dict[str, float]:
        """Cosine similarity of `query` against the cached vectors for `hashes`."""
        if not self.has_vec:
            return {h: _cosine(query, _unpack(v)) for h, v in self.get_many(model, hashes).items()}
        q, out = _pack(query), {}
        for i in range(0, len(hashes), 500):
            part = hashes[i : i + 500]
            sql = (
                "SELECT hash, 1 - vec_distance_cosine(vec, ?) FROM embeddings "
                f"WHERE model = ? AND hash IN ({','.join('?' * len(part))})"
            )
            out.update(self.db.execute(sql, [q, model, *part]).fetchall())
        return out


def _load_sqlite_vec(db: sqlite3.Connection) -> bool:
    try:
        import sqlite_vec

        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        return True
    except Exception:  # missing wheel or Python built without extension support
        return False


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class DenseIndex:
    def __init__(self, docs: list[str], cfg: DenseConfig, embedder: Embedder | None = None,
                 store: VectorStore | None = None):
        self.cfg = cfg
        self.embedder = embedder or OllamaEmbedder(cfg.model, cfg.url)
        self.store = store or VectorStore(Path(cfg.cache_dir) / "embeddings.sqlite")
        self.hashes = [text_hash(d) for d in docs]
        cached = self.store.get_many(self.embedder.model, self.hashes)
        todo = list({h: d for h, d in zip(self.hashes, docs) if h not in cached}.items())
        for i in range(0, len(todo), cfg.batch_size):  # only new/changed chunks hit Ollama
            batch = todo[i : i + cfg.batch_size]
            vecs = self.embedder.embed([d for _, d in batch])
            self.store.put_many(self.embedder.model, {h: v for (h, _), v in zip(batch, vecs)})

    def scores(self, query: str) -> list[float]:
        if not self.hashes:
            return []
        (q,) = self.embedder.embed([query])
        sims = self.store.similarities(self.embedder.model, q, list(set(self.hashes)))
        return [sims[h] for h in self.hashes]
