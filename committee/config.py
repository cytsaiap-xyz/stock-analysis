import os

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Two-tier mapping (spec decision #6). Override via env if a model tool-calls poorly.
# These defaults are CANDIDATES to validate in the live smoke test (Task 13 / spec section 10).
MODEL_REASONER = os.environ.get("MODEL_REASONER", "moonshotai/kimi-k2.6")
MODEL_TOOL_CALLER = os.environ.get("MODEL_TOOL_CALLER", "meta/llama-3.3-70b-instruct")

CACHE_DIR = os.environ.get("CACHE_DIR", "cache")
