"""
middleware.py — session-level wrapper with running stats.

Instantiate once per session or connection. Each `compress()` call
runs the full 4-pass pipeline and tracks cumulative reduction so you
can see how much you've saved across a conversation.
"""
from __future__ import annotations

import time

from .passes import reduce, restore, reduction_pct, estimate_tokens


class ConduitMiddleware:
    """
    Stateful compression middleware. Thread-safety is the caller's
    responsibility — each session should own its own instance.
    """

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self._call_count = 0
        self._total_original_chars = 0
        self._total_compressed_chars = 0
        self._total_original_tokens = 0
        self._total_compressed_tokens = 0

    def compress(self, text: str) -> str:
        """Run the full 4-pass reduction. Returns the compressed string."""
        t0 = time.perf_counter()
        compressed = reduce(text)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        orig_tok = estimate_tokens(text)
        comp_tok = estimate_tokens(compressed)

        self._call_count += 1
        self._total_original_chars += len(text)
        self._total_compressed_chars += len(compressed)
        self._total_original_tokens += orig_tok
        self._total_compressed_tokens += comp_tok

        if self.verbose:
            pct = reduction_pct(text, compressed)
            print(
                f"[conduit] call={self._call_count} "
                f"{orig_tok:,}→{comp_tok:,} tok "
                f"({pct:.1f}%) {elapsed_ms:.0f}ms"
            )

        return compressed

    def decompress(self, compressed: str) -> str:
        """
        Best-effort restore.

        Passes 3 and 4 are fully invertible. Passes 1 and 2 are lossy
        by design (whitespace and duplicate content are the point to
        remove). Output is the normalized deduped form.
        """
        return restore(compressed)

    def stats(self) -> dict:
        """Session-level cumulative stats."""
        if self._total_original_tokens == 0:
            return {"calls": 0, "reduction_pct": 0.0}
        overall = (
            1 - self._total_compressed_tokens / self._total_original_tokens
        ) * 100
        return {
            "calls": self._call_count,
            "total_original_tokens": self._total_original_tokens,
            "total_compressed_tokens": self._total_compressed_tokens,
            "tokens_saved": (
                self._total_original_tokens - self._total_compressed_tokens
            ),
            "reduction_pct": round(overall, 2),
        }

    def reset(self) -> None:
        """Clear all session counters."""
        self._call_count = 0
        self._total_original_chars = 0
        self._total_compressed_chars = 0
        self._total_original_tokens = 0
        self._total_compressed_tokens = 0
