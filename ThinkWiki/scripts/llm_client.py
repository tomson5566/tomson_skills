from __future__ import annotations

"""
ThinkWiki Module: llm_client

Purpose:
- OpenAI-compatible chat completion client for crystallize and digest.
- Disabled unless THINKWIKI_LLM_* environment variables are fully configured.
"""

import json
import re
import sys
import time
from urllib import error as urllib_error
from urllib import request as urllib_request

from ai_config import resolve_llm_config, resolve_llm_temperature

LLM_TIMEOUT = 60
LLM_RETRIES = 3
USER_AGENT = "ThinkWiki/1.7.2"

_RETRY_BACKOFFS = [2, 5]

_TEMPERATURE_BY_KIND: dict[str, float] = {
    "concept": 0.3,
    "decision": 0.3,
    "synthesis": 0.5,
    "query": 0.7,
}

_SYSTEM_PROMPT = (
    "You are a knowledge synthesis assistant for ThinkWiki, a personal knowledge base. "
    "You read multiple source materials and produce structured wiki page content. "
    "Always respond with a single valid JSON object, no markdown fences, no extra prose. "
    "Each summary must end with a period (。 for Chinese, . for English)."
)

_PROMPT_TEMPLATES: dict[str, str] = {
    "concept": (
        'Create a concept page titled "{title}".\n'
        "Based on the source materials below, produce:\n"
        '- "summary": a concise 1-2 sentence definition of the concept. Must end with a period.\n'
        '- "key_points": 3-5 key points clarifying the concept (list of strings).\n'
        '- "body": a detailed explanation synthesizing the sources (2-4 paragraphs).\n'
        '- "findings": empty list.\n'
        '- "tensions": empty list.\n'
    ),
    "decision": (
        'Create a decision page titled "{title}".\n'
        "Based on the source materials below, produce:\n"
        '- "summary": a concise conclusion statement (1-2 sentences). Must end with a period.\n'
        '- "key_points": 3-5 key points supporting the decision (list of strings).\n'
        '- "body": the reasoning process and justification (2-4 paragraphs).\n'
        '- "findings": empty list.\n'
        '- "tensions": empty list.\n'
    ),
    "synthesis": (
        'Create a {page_kind} titled "{title}".\n'
        "Based on the source materials below, produce a cross-source synthesis:\n"
        '- "summary": a concise synthesis summary (1-2 sentences). Must end with a period.\n'
        '- "key_points": empty list.\n'
        '- "body": the synthesis narrative connecting insights across sources (2-4 paragraphs).\n'
        '- "findings": 3-6 cross-source findings (list of strings, each prefixed with the source title where relevant).\n'
        '- "tensions": 2-4 tensions, conflicts, or open questions across sources (list of strings).\n'
    ),
    "query": (
        'Create a query page titled "{title}".\n'
        "Based on the source materials below, produce:\n"
        '- "summary": a concise answer to the query (1-2 sentences). Must end with a period.\n'
        '- "key_points": 3-5 key points supporting the answer (list of strings).\n'
        '- "body": the full answer with evidence and reasoning (2-4 paragraphs).\n'
        '- "findings": empty list.\n'
        '- "tensions": empty list.\n'
    ),
}

_EMPTY_RESULT = {
    "summary": "",
    "key_points": [],
    "body": "",
    "findings": [],
    "tensions": [],
}

_TERMINAL_PUNCTUATION = ("。", "！", "？", ".", "!", "?")


def _format_sources(sources: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for index, source in enumerate(sources, 1):
        title = str(source.get("title", "")).strip() or f"Source {index}"
        body = str(source.get("body", "")).strip()
        parts.append(f"## Source {index}: {title}\n{body}")
    return "\n\n".join(parts)


def _call_llm(messages: list[dict[str, str]], temperature: float = 0.5) -> str:
    config = resolve_llm_config()
    payload = json.dumps({
        "model": config.model,
        "messages": messages,
        "temperature": temperature,
    }).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(LLM_RETRIES):
        try:
            req = urllib_request.Request(
                config.base_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.api_key}",
                    "User-Agent": USER_AGENT,
                },
                method="POST",
            )
            with urllib_request.urlopen(req, timeout=LLM_TIMEOUT) as response:
                result = json.loads(response.read().decode("utf-8"))
            choices = result.get("choices") if isinstance(result, dict) else None
            if not choices or not isinstance(choices, list):
                raise ValueError("LLM response missing choices")
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = str(message.get("content") or "").strip()
            content = re.sub(
                r"<think>.*?</think>",
                "",
                content,
                flags=re.DOTALL,
            ).strip()
            if content:
                return content
            raise ValueError("LLM response has empty content")
        except urllib_error.HTTPError as exc:
            last_error = exc
            if 400 <= exc.code <= 499:
                break
            if attempt < LLM_RETRIES - 1 and attempt < len(_RETRY_BACKOFFS):
                time.sleep(_RETRY_BACKOFFS[attempt])
            continue
        except (urllib_error.URLError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < LLM_RETRIES - 1 and attempt < len(_RETRY_BACKOFFS):
                time.sleep(_RETRY_BACKOFFS[attempt])
            continue
    raise last_error or RuntimeError("LLM call failed after retries")


def _parse_result(content: str) -> dict[str, object]:
    cleaned = content.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    brace_start = cleaned.find("{")
    brace_end = cleaned.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        cleaned = cleaned[brace_start:brace_end + 1]
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")

    summary_raw = parsed.get("summary")
    body_raw = parsed.get("body")
    if not isinstance(summary_raw, str) or not isinstance(body_raw, str):
        raise ValueError("LLM response has non-string summary or body")

    def _str_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    summary = summary_raw.strip()
    if summary and not summary.endswith(_TERMINAL_PUNCTUATION):
        ascii_count = sum(1 for c in summary if ord(c) < 128)
        summary += "." if ascii_count > len(summary) / 2 else "。"

    return {
        "summary": summary,
        "key_points": _str_list(parsed.get("key_points")),
        "body": body_raw.strip(),
        "findings": _str_list(parsed.get("findings")),
        "tensions": _str_list(parsed.get("tensions")),
    }


def _fallback(sources: list[dict[str, str]], title: str, reason: str = "") -> dict[str, object]:
    if reason:
        display_title = title or "<untitled>"
        print(f"Warning: LLM call failed for '{display_title}' ({reason}). Using degraded fallback result.", file=sys.stderr)
    first = sources[0] if sources else {}
    first_title = str(first.get("title", "")).strip() or title
    first_body = str(first.get("body", "")).strip()
    return {
        "summary": first_title,
        "key_points": [],
        "body": first_body[:500],
        "findings": [],
        "tensions": [],
    }


def llm_crystallize(
    sources: list[dict[str, str]],
    kind: str,
    title: str,
    raise_on_failure: bool = False,
) -> dict[str, object]:
    if not sources:
        result = dict(_EMPTY_RESULT)
        result["summary"] = title
        return result

    template = _PROMPT_TEMPLATES.get(kind, _PROMPT_TEMPLATES["concept"])
    user_content = (
        template.format(title=title, page_kind="synthesis page")
        + "\n\n--- Source Materials ---\n\n"
        + _format_sources(sources)
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        content = _call_llm(messages, temperature=resolve_llm_temperature(kind, _TEMPERATURE_BY_KIND))
        return _parse_result(content)
    except Exception as exc:
        if raise_on_failure:
            raise
        return _fallback(sources, title, reason=str(exc))


def llm_digest(
    sources: list[dict[str, str]],
    title: str,
    raise_on_failure: bool = False,
) -> dict[str, object]:
    if not sources:
        result = dict(_EMPTY_RESULT)
        result["summary"] = title
        return result

    template = _PROMPT_TEMPLATES["synthesis"]
    user_content = (
        template.format(title=title, page_kind="synthesis digest page")
        + "\n\n--- Source Materials ---\n\n"
        + _format_sources(sources)
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        content = _call_llm(messages, temperature=resolve_llm_temperature("synthesis", _TEMPERATURE_BY_KIND))
        return _parse_result(content)
    except Exception as exc:
        if raise_on_failure:
            raise
        return _fallback(sources, title, reason=str(exc))
