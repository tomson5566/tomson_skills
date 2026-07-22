from __future__ import annotations

"""
ThinkWiki Module: embed_client

Purpose:
- OpenAI-compatible embedding HTTP client for semantic entity matching.
- Disabled unless THINKWIKI_EMBED_API_KEY is configured.
"""

import json
import sys
from typing import Iterable
from urllib import error as urllib_error
from urllib import request as urllib_request

from ai_config import resolve_embed_config

EMBED_TIMEOUT = 10
USER_AGENT = "ThinkWiki/1.7.2"


class EmbedServiceUnavailable(Exception):
    """Raised when embedding endpoints are unreachable or misconfigured."""


def _post_json(url: str, payload: dict, api_key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=EMBED_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_embeddings(response: dict, count: int) -> list[list[float]]:
    data = response.get("data")
    if isinstance(data, list) and data:
        vectors: list[list[float]] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("embedding"), list):
                vectors.append([float(x) for x in item["embedding"]])
        if len(vectors) == count:
            return vectors
    if isinstance(response, list) and len(response) == count:
        return [[float(x) for x in item] for item in response]
    raise ValueError("Unexpected embedding response shape")


def _normalize(vector: list[float]) -> list[float]:
    norm = sum(x * x for x in vector) ** 0.5
    if norm == 0:
        return vector
    return [x / norm for x in vector]


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    """Embed a batch of texts via the configured OpenAI-compatible embedding API."""
    text_list = [str(t).strip() for t in texts if str(t).strip()]
    if not text_list:
        return []
    config = resolve_embed_config()
    payload = {"input": text_list, "model": config.model}
    last_error: Exception | None = None
    for endpoint in config.base_urls:
        try:
            response = _post_json(endpoint, payload, config.api_key)
            vectors = _extract_embeddings(response, len(text_list))
            return [_normalize(v) for v in vectors]
        except urllib_error.HTTPError as exc:
            if 400 <= exc.code <= 499:
                if exc.code in (401, 403):
                    raise EmbedServiceUnavailable(
                        f"Embedding auth failed (HTTP {exc.code}): check THINKWIKI_EMBED_API_KEY"
                    ) from exc
                raise EmbedServiceUnavailable(f"Embedding client error (HTTP {exc.code})") from exc
            last_error = exc
            continue
        except (urllib_error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
    raise EmbedServiceUnavailable(f"All embedding endpoints failed: {last_error}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
