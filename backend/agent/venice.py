"""Venice AI client — the agent's private reasoning brain.

Venice implements the OpenAI API spec, so we use the OpenAI SDK pointed at
`https://api.venice.ai/api/v1`. `include_venice_system_prompt=False` gives us a
clean system prompt for deterministic extraction.

When no API key is configured the client falls back to a deterministic heuristic
extractor that *mimics an injection-susceptible LLM* — it follows an override
instruction embedded in untrusted text. This keeps the agent runnable and
testable offline while preserving the security-relevant behavior the demo shows.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

EXTRACT_SYSTEM = (
    "You are a quarantined invoice reader. You ONLY extract the payment recipient "
    "address and the amount of USDC requested. Respond with strict JSON: "
    '{"to": "0x...", "amount_usdc": <number>}. Do not add commentary.'
)

_ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")
_AMOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*USDC", re.IGNORECASE)
# An injection tries to *override* the legitimate line with urgency / system framing.
_OVERRIDE_RE = re.compile(
    r"(ignore|instead|urgent|system|admin|actually|override|must)", re.IGNORECASE
)


class VeniceClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("VENICE_API_KEY")
        self.base_url = base_url or os.environ.get(
            "VENICE_BASE_URL", "https://api.venice.ai/api/v1"
        )
        self.model = model or os.environ.get("VENICE_MODEL", "venice-uncensored")
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
        return f"venice:{self.model}" if self.available else "heuristic-fallback"

    def chat(self, system: str, user: str, temperature: float = 0.0) -> str:
        """Raw chat completion via Venice (OpenAI-compatible)."""
        if not self._client:
            raise RuntimeError("Venice client not configured (no API key).")
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            extra_body={"venice_parameters": {"include_venice_system_prompt": False}},
        )
        return resp.choices[0].message.content or ""

    # ------------------------------------------------------------------ extract
    def extract_payment(self, invoice_text: str) -> dict:
        """Quarantined extraction of (to, amount_usdc) from untrusted invoice text.

        Returns {"to": str, "amount_usdc": float, "backend": str}. This is the
        injection surface: a malicious invoice can steer the recipient/amount.
        """
        if self._client:
            try:
                raw = self.chat(EXTRACT_SYSTEM, invoice_text)
                data = _parse_json_loose(raw)
                if data and "to" in data and "amount_usdc" in data:
                    return {
                        "to": str(data["to"]),
                        "amount_usdc": float(data["amount_usdc"]),
                        "backend": self.backend,
                    }
            except Exception:
                pass  # fall through to heuristic
        return _heuristic_extract(invoice_text)


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
    """Deterministic stand-in for an injection-susceptible reader.

    If the text contains an override instruction near an address, follow that
    (simulating a corrupted LLM); otherwise read the first stated recipient/amount.
    """
    addrs = _ADDR_RE.findall(invoice_text)
    amounts = [float(a) for a in _AMOUNT_RE.findall(invoice_text)]
    to = addrs[0] if addrs else "0x0000000000000000000000000000000000000000"
    amount = amounts[0] if amounts else 0.0

    if _OVERRIDE_RE.search(invoice_text):
        # An injected override steers toward the LAST mentioned address/amount.
        if addrs:
            to = addrs[-1]
        if amounts:
            amount = max(amounts)
    return {"to": to, "amount_usdc": amount, "backend": "heuristic-fallback"}
