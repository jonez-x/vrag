"""Pipeline configuration, loaded from config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path


@dataclass
class ChunkingConfig:
    split_on_headings: bool = True
    max_chars: int = 1200
    prefix_title: bool = False


@dataclass
class BM25Config:
    enabled: bool = True
    k1: float = 1.5
    b: float = 0.75
    stemming: bool = False
    stopwords: bool = False
    decompound: bool = False
    acronyms: bool = False


@dataclass
class DenseConfig:
    enabled: bool = False
    model: str = "bge-m3"
    url: str = "http://localhost:11434"
    cache_dir: str = ".vrag"
    batch_size: int = 32


@dataclass
class FusionConfig:
    method: str = "rrf"
    rrf_k: int = 60
    bm25_weight: float = 1.0
    dense_weight: float = 1.0


@dataclass
class GraphConfig:
    enabled: bool = False
    boost: float = 0.05


@dataclass
class RerankConfig:
    enabled: bool = False
    model: str = "BAAI/bge-reranker-v2-m3"
    top_n: int = 30


@dataclass
class SearchConfig:
    k: int = 5


@dataclass
class Config:
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    bm25: BM25Config = field(default_factory=BM25Config)
    dense: DenseConfig = field(default_factory=DenseConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    rerank: RerankConfig = field(default_factory=RerankConfig)
    search: SearchConfig = field(default_factory=SearchConfig)

    @classmethod
    def load(cls, path: str | Path = "config.toml") -> Config:
        path = Path(path)
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        return _from_dict(cls, data)


def _from_dict(dc_type, data: dict):
    kwargs = {}
    for f in fields(dc_type):
        if f.name not in data:
            continue
        value = data[f.name]
        default = f.default_factory() if callable(f.default_factory) else None  # type: ignore[misc]
        if default is not None and is_dataclass(default) and isinstance(value, dict):
            kwargs[f.name] = _from_dict(type(default), value)
        else:
            kwargs[f.name] = value
    return dc_type(**kwargs)
