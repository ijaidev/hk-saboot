"""Optional LLM drafting behind a tiny provider interface.

The template path is the default and must work with no API key. A provider is
only allowed to rewrite the appeal body; the claim amounts and citations still
come from the deterministic audit, and the appeal verifier rejects anything
unsupported. Any provider failure falls back to the template.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol


class LLMError(Exception):
    """Provider failed or is unavailable."""


class DraftProvider(Protocol):
    name: str

    def draft(self, prompt: str) -> str:  # pragma: no cover - protocol
        ...


class TemplateProvider:
    name = "template"

    def draft(self, prompt: str) -> str:
        raise LLMError("template provider has no generative model")


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", timeout: int = 20):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def draft(self, prompt: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise LLMError(f"Gemini provider failed: {exc}") from exc
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Gemini provider returned an unexpected response") from exc


def provider_from_env() -> DraftProvider:
    """Return an LLM provider only when explicitly configured.

    Default is the template path. `SABOOT_LLM_PROVIDER=gemini` plus
    `GEMINI_API_KEY` enables the optional free-tier provider.
    """
    if os.environ.get("SABOOT_LLM_PROVIDER", "").strip().lower() == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if key:
            return GeminiProvider(key)
    return TemplateProvider()
