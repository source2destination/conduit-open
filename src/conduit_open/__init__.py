"""
conduit_open — deterministic structural reduction for LLM API payloads

Four-pass pipeline matching the Conduit-Reduction desktop widget:
  1. Whitespace normalization
  2. Sentence-level deduplication
  3. Timestamp reference encoding
  4. Dictionary substitution

Wrap any prompt before it hits your model provider.
"""
from .middleware import ConduitMiddleware
from .passes import reduce, restore, reduction_pct, estimate_tokens

__version__ = "0.1.0"
__all__ = [
    "ConduitMiddleware",
    "reduce",
    "restore",
    "reduction_pct",
    "estimate_tokens",
]
