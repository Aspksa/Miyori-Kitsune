from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]{2,}", re.UNICODE)


class EmbeddingProvider(Protocol):
    name: str
    version: str
    dimensions: int
    neural: bool

    def available(self) -> bool:
        ...

    def encode(self, text: str) -> list[float]:
        ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class HashEmbeddingProvider:
    """Deterministic local fallback. Vector-based, but not a neural embedding model."""

    name: str = "miyori-hash-embedding"
    version: str = "0.1.0"
    dimensions: int = 384
    neural: bool = False

    def available(self) -> bool:
        return True

    def encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        normalized = " ".join(str(text).lower().split())
        tokens = _TOKEN_RE.findall(normalized)

        features: list[str] = []
        features.extend(f"w:{token}" for token in tokens)
        for token in tokens:
            padded = f"^{token}$"
            features.extend(f"c:{padded[i:i+3]}" for i in range(max(0, len(padded) - 2)))
        features.extend(f"p:{tokens[i]}_{tokens[i+1]}" for i in range(max(0, len(tokens) - 1)))

        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm > 0 else vector


class SentenceTransformersProvider:
    """Optional real neural embeddings from a locally available sentence-transformers model."""

    name = "sentence-transformers"
    version = "optional"
    neural = True

    def __init__(self, model_ref: str):
        self.model_ref = str(model_ref or "").strip()
        self._model = None
        self.dimensions = 0

    def available(self) -> bool:
        if not self.model_ref:
            return False
        model_path = Path(self.model_ref).expanduser()
        if not model_path.exists():
            return False
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            return True
        except Exception:
            return False

    def _load(self):
        if self._model is not None:
            return self._model
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_ref)
        try:
            self.dimensions = int(self._model.get_sentence_embedding_dimension() or 0)
        except Exception:
            self.dimensions = 0
        return self._model

    def encode(self, text: str) -> list[float]:
        model = self._load()
        result = model.encode([str(text)], normalize_embeddings=True)[0]
        values = result.tolist() if hasattr(result, "tolist") else list(result)
        if not self.dimensions:
            self.dimensions = len(values)
        return [float(value) for value in values]


_PROVIDER = None


def get_provider() -> EmbeddingProvider:
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER

    model_ref = os.environ.get("MIYORI_EMBEDDING_MODEL", "").strip()
    if model_ref:
        provider = SentenceTransformersProvider(model_ref)
        if provider.available():
            _PROVIDER = provider
            return _PROVIDER

    _PROVIDER = HashEmbeddingProvider()
    return _PROVIDER


def reset_provider_cache() -> None:
    global _PROVIDER
    _PROVIDER = None


def status() -> dict:
    provider = get_provider()
    return {
        "provider": provider.name,
        "version": provider.version,
        "dimensions": int(getattr(provider, "dimensions", 0) or 0),
        "neural": bool(getattr(provider, "neural", False)),
        "available": bool(provider.available()),
        "configured_model": os.environ.get("MIYORI_EMBEDDING_MODEL", "").strip() or None,
        "mode": "neural" if getattr(provider, "neural", False) else "local-vector-fallback",
        "note": (
            "Real neural embeddings are active."
            if getattr(provider, "neural", False)
            else "Using deterministic local vector fallback until a local neural embedding model is configured."
        ),
    }
