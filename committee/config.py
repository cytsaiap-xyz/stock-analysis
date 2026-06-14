import os
from typing import Any, Dict, Mapping

from dotenv import load_dotenv

# Load .env BEFORE resolving provider/model below. config is imported (often
# transitively) before a front-end's own load_dotenv() runs, so without this the
# env snapshot misses .env and silently falls back to the built-in defaults.
load_dotenv()

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

# Per-provider connection + two-tier model defaults. Both providers are
# OpenAI-compatible, so switching is just base_url + api key + model ids.
# Pick the provider with LLM_PROVIDER; override any model with MODEL_* env.
_PROVIDERS: Dict[str, Dict[str, str]] = {
    "nvidia": {
        "base_url": NVIDIA_BASE_URL,
        "api_key_env": "NVIDIA_API_KEY",
        "reasoner": "moonshotai/kimi-k2.6",
        "tool_caller": "meta/llama-3.3-70b-instruct",
    },
    "openrouter": {
        "base_url": OPENROUTER_BASE_URL,
        "api_key_env": "OPENROUTER_API_KEY",
        "reasoner": "deepseek/deepseek-v4-flash:free",
        "tool_caller": "qwen/qwen3-coder:free",
    },
    "google": {
        "base_url": GOOGLE_BASE_URL,
        "api_key_env": "GOOGLE_API_KEY",
        "reasoner": "gemma-4-31b-it",
        "tool_caller": "gemma-4-31b-it",
    },
}


def resolve(env: Mapping[str, str]) -> Dict[str, Any]:
    """Resolve provider connection + model tiers from an environment mapping.

    Pure (takes the env in) so it is testable without mutating os.environ.
    Each provider keeps its own model config via per-provider env vars
    (e.g. NVIDIA_MODEL_REASONER, OPENROUTER_MODEL_TOOL_CALLER); they never leak
    across providers. Fall back to the provider's built-in default.
    """
    provider = env.get("LLM_PROVIDER", "nvidia").lower()
    if provider not in _PROVIDERS:
        raise ValueError("Unknown LLM_PROVIDER: {!r} (expected one of {})".format(
            provider, ", ".join(sorted(_PROVIDERS))))
    p = _PROVIDERS[provider]
    pre = provider.upper()
    # A model env may be a comma-separated list: first is primary, rest are
    # fallbacks tried in order when the primary is unavailable (429/5xx/404).
    reasoner = _models(env.get(pre + "_MODEL_REASONER") or p["reasoner"])
    tool_caller = _models(env.get(pre + "_MODEL_TOOL_CALLER") or p["tool_caller"])
    return {
        "provider": provider,
        "base_url": p["base_url"],
        "api_key_env": p["api_key_env"],
        "reasoner": reasoner[0],
        "reasoner_fallbacks": reasoner[1:],
        "tool_caller": tool_caller[0],
        "tool_caller_fallbacks": tool_caller[1:],
    }


def _models(raw: str) -> list:
    return [m.strip() for m in str(raw).split(",") if m.strip()]


_R = resolve(os.environ)
LLM_PROVIDER = _R["provider"]
BASE_URL = _R["base_url"]
API_KEY_ENV = _R["api_key_env"]
MODEL_REASONER = _R["reasoner"]
MODEL_TOOL_CALLER = _R["tool_caller"]
MODEL_REASONER_FALLBACKS = _R["reasoner_fallbacks"]
MODEL_TOOL_CALLER_FALLBACKS = _R["tool_caller_fallbacks"]

CACHE_DIR = os.environ.get("CACHE_DIR", "cache")

# Chair self-reflection passes before VERIFY (0 disables). Default on, env-overridable.
REFLECTION_PASSES = int(os.environ.get("REFLECTION_PASSES", "1"))

# Round-robin discussion rounds replacing scripted CHALLENGE+REBUTTAL (0 disables).
DISCUSSION_ROUNDS = int(os.environ.get("DISCUSSION_ROUNDS", "2"))

# Discussion engine: "roundrobin" (sequential, default) or "dynamic" (AutoGen SelectorGroupChat).
DISCUSSION_MODE = os.environ.get("DISCUSSION_MODE", "roundrobin")
# Hard cap on dynamic-mode turns (selector may end earlier on consensus).
DISCUSSION_MAX_TURNS = int(os.environ.get("DISCUSSION_MAX_TURNS", "12"))
