from __future__ import annotations

"""
ThinkWiki Module: ai_config

Purpose:
- Resolve optional remote AI service configuration from environment variables.
- LLM and embedding features stay disabled unless explicitly configured.
"""

import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_EMBED_BASE_URL = "https://api.siliconflow.cn/v1/embeddings"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class LlmConfig:
    api_key: str
    base_url: str
    model: str


@dataclass(frozen=True)
class EmbedConfig:
    api_key: str
    base_urls: tuple[str, ...]
    model: str


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _validate_service_url(url: str, env_name: str) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(f"{env_name} must use http:// or https:// (got {parsed.scheme!r})")
    if not parsed.netloc:
        raise RuntimeError(f"{env_name} is not a valid URL: {url!r}")


def llm_is_configured() -> bool:
    return bool(
        _env("THINKWIKI_LLM_API_KEY")
        and _env("THINKWIKI_LLM_BASE_URL")
        and _env("THINKWIKI_LLM_MODEL")
    )


def resolve_llm_config() -> LlmConfig:
    api_key = _env("THINKWIKI_LLM_API_KEY")
    base_url = _env("THINKWIKI_LLM_BASE_URL")
    model = _env("THINKWIKI_LLM_MODEL")
    if not api_key and not base_url and not model:
        raise RuntimeError(
            "LLM is not configured. Set THINKWIKI_LLM_API_KEY, THINKWIKI_LLM_BASE_URL, "
            "and THINKWIKI_LLM_MODEL to enable OpenAI-compatible content generation."
        )
    missing = [
        name
        for name, value in (
            ("THINKWIKI_LLM_API_KEY", api_key),
            ("THINKWIKI_LLM_BASE_URL", base_url),
            ("THINKWIKI_LLM_MODEL", model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Incomplete LLM configuration. Set all of THINKWIKI_LLM_API_KEY, "
            f"THINKWIKI_LLM_BASE_URL, and THINKWIKI_LLM_MODEL. Missing: {', '.join(missing)}"
        )
    _validate_service_url(base_url, "THINKWIKI_LLM_BASE_URL")
    return LlmConfig(api_key=api_key, base_url=base_url, model=model)


def resolve_llm_temperature(kind: str, default_by_kind: dict[str, float]) -> float:
    env_override = _env("THINKWIKI_LLM_TEMPERATURE")
    if env_override:
        try:
            return float(env_override)
        except ValueError:
            default = default_by_kind.get(kind, 0.5)
            print(
                f"Warning: THINKWIKI_LLM_TEMPERATURE='{env_override}' is not a valid number; "
                f"using kind default ({default}).",
                file=sys.stderr,
            )
    return default_by_kind.get(kind, 0.5)


def embed_is_configured() -> bool:
    return bool(_env("THINKWIKI_EMBED_API_KEY"))


def resolve_embed_config() -> EmbedConfig:
    api_key = _env("THINKWIKI_EMBED_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Embedding is not configured. Set THINKWIKI_EMBED_API_KEY to enable semantic entity matching."
        )
    base_url_env = _env("THINKWIKI_EMBED_BASE_URL")
    if base_url_env:
        base_urls = tuple(item.strip() for item in base_url_env.split(",") if item.strip())
        if not base_urls:
            print(
                "Warning: THINKWIKI_EMBED_BASE_URL is set but empty; "
                f"falling back to {DEFAULT_EMBED_BASE_URL}.",
                file=sys.stderr,
            )
            base_urls = (DEFAULT_EMBED_BASE_URL,)
    else:
        base_urls = (DEFAULT_EMBED_BASE_URL,)
    model = _env("THINKWIKI_EMBED_MODEL") or DEFAULT_EMBED_MODEL
    for url in base_urls:
        _validate_service_url(url, "THINKWIKI_EMBED_BASE_URL")
    return EmbedConfig(api_key=api_key, base_urls=base_urls, model=model)
