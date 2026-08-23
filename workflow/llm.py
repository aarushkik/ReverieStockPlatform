"""
A generic completion interface for the synthesis step.

``agent_logic.run_llm_agent`` cannot be reused here: its prompt, its JSON
schema and its heuristic fallback are welded together for one specific
stock-scoring task. The engine needs a plain ``(prompt, system) -> text`` call
with no opinions about content.

The one rule this module adds to the five providers it wraps:

    **When the model is unavailable, raise. Never return text.**

``agent_logic.chat_with_ai_copilot`` currently returns a canned sentence -
"Market Copilot Note: Ticker X is currently consolidating..." - when every
provider fails, formatted identically to a real answer. A user with an expired
key cannot tell they are reading a template. In a workflow whose entire premise
is that claims are checkable, a fabricated answer at the last step would undo
everything upstream, so failure here propagates and the run reports no memo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import requests

__all__ = [
    "NoModelConfigured",
    "ModelCallFailed",
    "Provider",
    "available_providers",
    "best_provider",
    "active_model_label",
    "make_completer",
    "DEFAULT_TIMEOUT",
    "PREFERENCE",
]

DEFAULT_TIMEOUT = 45.0


class NoModelConfigured(RuntimeError):
    """No provider has an API key set."""


class ModelCallFailed(RuntimeError):
    """A provider was configured but the call did not succeed."""


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    env_var: str
    default_model: str

    @property
    def configured(self) -> bool:
        value = os.environ.get(self.env_var, "").strip()
        # Placeholder keys are the usual cause of a "configured" provider that
        # fails on every call.
        return bool(value) and not value.upper().startswith("YOUR_")


PROVIDERS: Dict[str, Provider] = {
    p.key: p for p in (
        Provider("featherless", "Featherless", "FEATHERLESS_API_KEY",
                 os.environ.get("FEATHERLESS_MODEL") or "Qwen/Qwen2.5-72B-Instruct"),
        Provider("openai", "OpenAI", "OPENAI_API_KEY", "gpt-4o-mini"),
        Provider("anthropic", "Anthropic", "ANTHROPIC_API_KEY",
                 "claude-3-5-sonnet-20241022"),
        Provider("deepseek", "DeepSeek", "DEEPSEEK_API_KEY", "deepseek-chat"),
        Provider("gemini", "Gemini", "GEMINI_API_KEY", "gemini-2.5-flash"),
    )
}


# Capability ranking, best first. The app picks from this automatically rather
# than asking the user, because "which model" is not a decision a person opening
# a market terminal has the information to make - the useful answer is always
# "the best one you have a key for", and offering a dropdown of names invites
# picking a weaker model by accident. The order reflects reasoning quality on
# analytical text; it only has any effect when more than one key is present.
PREFERENCE: Tuple[str, ...] = (
    "anthropic",
    "openai",
    "gemini",
    "deepseek",
    "featherless",
)


def available_providers() -> List[Provider]:
    """Providers with a usable key, best first."""
    ranked = {key: i for i, key in enumerate(PREFERENCE)}
    return sorted(
        (p for p in PROVIDERS.values() if p.configured),
        key=lambda p: ranked.get(p.key, len(ranked)),
    )


def best_provider() -> Optional[Provider]:
    """The highest-ranked provider that has a key, or None."""
    found = available_providers()
    return found[0] if found else None


def active_model_label() -> str:
    """What the UI shows instead of a model picker."""
    provider = best_provider()
    if provider is None:
        return "no model configured"
    model = provider.default_model
    # Featherless model ids are org/name; the name alone is what a person reads.
    return f"{provider.label} · {model.split('/')[-1]}"


# ==============================================================================
# TRANSPORTS
# ==============================================================================
# All of these speak the same shape: system + user in, text out. Each raises
# ModelCallFailed rather than returning anything on error.


def _openai_compatible(url: str, api_key: str, model: str, prompt: str,
                       system: str, timeout: float) -> str:
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=timeout,
    )
    if response.status_code != 200:
        raise ModelCallFailed(f"HTTP {response.status_code}: {response.text[:200]}")
    payload = response.json()
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelCallFailed(f"unexpected response shape: {payload}") from exc


def _anthropic(api_key: str, model: str, prompt: str, system: str,
               timeout: float) -> str:
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": model, "max_tokens": 2000, "system": system,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise ModelCallFailed(f"HTTP {response.status_code}: {response.text[:200]}")
    payload = response.json()
    try:
        return payload["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelCallFailed(f"unexpected response shape: {payload}") from exc


def _gemini(api_key: str, model: str, prompt: str, system: str,
            timeout: float) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ModelCallFailed("google-genai is not installed") from exc

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system),
        )
    except Exception as exc:  # noqa: BLE001 - SDK raises many types
        raise ModelCallFailed(str(exc)) from exc

    text = getattr(response, "text", None)
    if not text:
        raise ModelCallFailed("empty response")
    return text


def _dispatch(provider: Provider, prompt: str, system: str, model: str,
              timeout: float) -> str:
    api_key = os.environ[provider.env_var].strip()
    if provider.key == "featherless":
        return _openai_compatible(
            "https://api.featherless.ai/v1/chat/completions",
            api_key, model, prompt, system, timeout)
    if provider.key == "openai":
        return _openai_compatible(
            "https://api.openai.com/v1/chat/completions",
            api_key, model, prompt, system, timeout)
    if provider.key == "deepseek":
        return _openai_compatible(
            "https://api.deepseek.com/v1/chat/completions",
            api_key, model, prompt, system, timeout)
    if provider.key == "anthropic":
        return _anthropic(api_key, model, prompt, system, timeout)
    if provider.key == "gemini":
        return _gemini(api_key, model, prompt, system, timeout)
    raise ModelCallFailed(f"no transport for provider {provider.key!r}")


# ==============================================================================
# FACTORY
# ==============================================================================


def make_completer(
    provider_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Callable[[str, str], str]:
    """Build the ``(prompt, system) -> text`` callable the engine expects.

    Raises :class:`NoModelConfigured` immediately if nothing is set up, so the
    caller can decide what to do *before* running a workflow rather than
    discovering it at the synthesis step.

    The returned callable tries the chosen provider, then falls back through the
    other configured ones. If all of them fail it raises - it never returns a
    placeholder, which is the whole point.
    """
    candidates: List[Provider]
    if provider_key:
        chosen = PROVIDERS.get(provider_key)
        if chosen is None:
            raise NoModelConfigured(f"unknown provider {provider_key!r}")
        if not chosen.configured:
            raise NoModelConfigured(
                f"{chosen.label} selected but {chosen.env_var} is not set")
        candidates = [chosen] + [p for p in available_providers() if p.key != chosen.key]
    else:
        candidates = available_providers()

    if not candidates:
        raise NoModelConfigured(
            "no language model configured; set one of: "
            + ", ".join(p.env_var for p in PROVIDERS.values())
        )

    def complete(prompt: str, system: str) -> str:
        failures = []
        for provider in candidates:
            use_model = model if (model and provider is candidates[0]) else provider.default_model
            try:
                text = _dispatch(provider, prompt, system, use_model, timeout)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{provider.label}: {exc}")
                continue
            if text and text.strip():
                return text
            failures.append(f"{provider.label}: empty response")
        raise ModelCallFailed("all providers failed -> " + " | ".join(failures))

    return complete
