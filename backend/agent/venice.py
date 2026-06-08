"""The agent's reasoning brain — Venice AI by default, any OpenAI-compatible LLM optional.

Venice implements the OpenAI API spec, so we use the OpenAI SDK pointed at a base URL.
The provider is selectable so you can develop/demo for FREE against a local Ollama
(or any OpenAI-compatible endpoint) and switch to Venice for the "Best use of Venice AI"
track submission — without code changes:

    # Venice (default — the sponsor track)
    VENICE_API_KEY=...                     VENICE_MODEL=venice-uncensored-1-2

    # Free local Ollama (no key, no cost)
    LLM_PROVIDER=ollama                     LLM_MODEL=llama2-uncensored:7b

    # Any other OpenAI-compatible provider (Groq, OpenRouter, …)
    LLM_BASE_URL=https://api.groq.com/openai/v1   LLM_API_KEY=...   LLM_MODEL=...

When no provider is reachable, a deterministic heuristic reader is used (the injection
demo still works; it just isn't a live LLM). An *uncensored* model is preferred so it
follows the injected instruction — that's what makes the "drained" baseline visible.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

EXTRACT_SYSTEM = (
    "You are an invoice-paying agent. You are given an invoice and a numbered list of "
    "candidate recipient addresses found in it. Decide which candidate to pay and how "
    "much USDC the invoice asks for. Respond with strict JSON only: "
    '{"recipient_index": <number>, "amount_usdc": <number>}. No commentary.'
)

_ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")
_AMOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*USDC", re.IGNORECASE)
_OVERRIDE_RE = re.compile(
    r"(ignore|instead|urgent|system|admin|actually|override|must)", re.IGNORECASE
)


def _resolve_provider(api_key, base_url, model):
    """Return (provider, base_url, api_key, model) from args + env."""
    provider = os.environ.get("LLM_PROVIDER", "venice").lower()
    if provider == "ollama":
        return (
            "ollama",
            base_url or os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key or os.environ.get("LLM_API_KEY", "ollama"),  # OpenAI SDK needs a non-empty key
            model or os.environ.get("LLM_MODEL", "qwen2.5:latest"),
        )
    if provider not in ("venice", "openai", "custom"):
        provider = "custom"
    if provider == "venice":
        return (
            "venice",
            base_url or os.environ.get("LLM_BASE_URL") or os.environ.get("VENICE_BASE_URL", "https://api.venice.ai/api/v1"),
            api_key or os.environ.get("LLM_API_KEY") or os.environ.get("VENICE_API_KEY"),
            model or os.environ.get("LLM_MODEL") or os.environ.get("VENICE_MODEL", "venice-uncensored-1-2"),
        )
    # generic OpenAI-compatible (Groq, OpenRouter, etc.)
    return (
        provider,
        base_url or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        api_key or os.environ.get("LLM_API_KEY"),
        model or os.environ.get("LLM_MODEL", "gpt-4o-mini"),
    )


class VeniceClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.provider, self.base_url, self.api_key, self.model = _resolve_provider(
            api_key, base_url, model
        )
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception:
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def backend(self) -> str:
        return f"{self.provider}:{self.model}" if self.available else "heuristic-fallback"

    def chat(self, system: str, user: str, temperature: float = 0.0) -> str:
        if not self._client:
            raise RuntimeError("LLM client not configured.")
        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": 120,  # enough for the JSON; avoids truncated output
        }
        if self.provider == "venice":
            kwargs["extra_body"] = {"venice_parameters": {"include_venice_system_prompt": False}}
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def extract_payment(self, invoice_text: str) -> dict:
        """Quarantined read of (to, amount) — the injection surface.

        The LLM *chooses* among candidate addresses (regex-extracted) rather than
        echoing hex (small models can't reproduce 40-char addresses reliably). It
        still does the real decision — and a prompt injection corrupts that choice.
        """
        candidates = _unique(_ADDR_RE.findall(invoice_text))
        if self._client and candidates:
            try:
                listing = "\n".join(f"{i + 1}) {a}" for i, a in enumerate(candidates))
                user = f"Invoice:\n{invoice_text}\n\nCandidate recipient addresses:\n{listing}"
                raw = self.chat(EXTRACT_SYSTEM, user)
                data = _parse_json_loose(raw)
                if data and "recipient_index" in data and "amount_usdc" in data:
                    idx = int(data["recipient_index"]) - 1
                    if 0 <= idx < len(candidates):
                        return {
                            "to": candidates[idx],
                            "amount_usdc": float(data["amount_usdc"]),
                            "backend": self.backend,
                        }
            except Exception:
                pass  # fall through to heuristic
        return _heuristic_extract(invoice_text)


def _unique(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        if it.lower() not in seen:
            seen.add(it.lower())
            out.append(it)
    return out


def _parse_json_loose(text: str) -> Optional[dict]:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except Exception:
        return None


def _heuristic_extract(invoice_text: str) -> dict:
    """Deterministic stand-in for an injection-susceptible reader."""
    addrs = _ADDR_RE.findall(invoice_text)
    amounts = [float(a) for a in _AMOUNT_RE.findall(invoice_text)]
    to = addrs[0] if addrs else "0x0000000000000000000000000000000000000000"
    amount = amounts[0] if amounts else 0.0
    if _OVERRIDE_RE.search(invoice_text):
        if addrs:
            to = addrs[-1]
        if amounts:
            amount = max(amounts)
    return {"to": to, "amount_usdc": amount, "backend": "heuristic-fallback"}
