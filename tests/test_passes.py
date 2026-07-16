"""Tests for the 4-pass pipeline.

Run directly:
    python -m pytest tests/
    python tests/test_passes.py
"""
import os
import sys

# Support running directly without install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from conduit_open.passes import (
    reduce,
    restore,
    normalize_whitespace,
    dedup,
    compress_timestamps,
    decompress_timestamps,
    dict_substitute,
    dict_desubstitute,
    reduction_pct,
    estimate_tokens,
)


SAMPLES = {
    "chat_repeats": (
        "User: How does context management work?\n"
        "Assistant: Context management tracks what the model has seen.\n"
        "User: Is the encoding deterministic?\n"
        "Assistant: Yes. The same input produces the same output.\n"
    ) * 8,

    "code_block": ("""public class Engine {
    private readonly ILogger _logger;
    public async Task<Result> CompressAsync(string input) {
        if (string.IsNullOrEmpty(input))
            throw new ArgumentException("null input", nameof(input));
        return new Result { Bytes = input.Length };
    }
}
""") * 6,

    "server_logs": "\n".join(
        f"[2026-04-17T05:31:10.534Z] INFO RequestHandler: "
        f"Processing request id={i:05d}"
        for i in range(60)
    ),

    "config_duplicates": (
        "[api]\n"
        "host=0.0.0.0\n"
        "port=8080\n"
        "debug=false\n"
        "log_level=INFO\n"
        "log_level=INFO\n"
        "rate_limit_requests=100\n"
        "rate_limit_requests=100\n"
    ),

    "single_short": (
        "User: What is token reduction?\n"
        "Assistant: It removes redundant context."
    ),

    "empty": "",
}


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ─────────────────────────────────────────────────────────────────────

def test_whitespace_idempotent():
    for name, text in SAMPLES.items():
        once = normalize_whitespace(text)
        twice = normalize_whitespace(once)
        _assert(once == twice, f"whitespace not idempotent on {name}")
    print("PASS: whitespace is idempotent")


def test_dedup_no_growth():
    """Dedup must never make output larger than input."""
    for name, text in SAMPLES.items():
        normalized = normalize_whitespace(text)
        deduped = dedup(normalized)
        _assert(
            len(deduped) <= len(normalized),
            f"dedup grew output on {name}: {len(normalized)} → {len(deduped)}",
        )
    print("PASS: dedup never grows input")


def test_timestamp_roundtrip():
    text = SAMPLES["server_logs"]
    compressed = compress_timestamps(text)
    restored = decompress_timestamps(compressed)
    _assert(
        restored == text,
        "timestamp roundtrip failed — output differs from input",
    )
    _assert(
        len(compressed) < len(text),
        "timestamp encoding should have reduced log corpus",
    )
    print(
        f"PASS: timestamp roundtrip on {len(text):,}→"
        f"{len(compressed):,} chars"
    )


def test_dict_roundtrip():
    text = (
        "The algorithm processes messages through multiple stages. "
        "The algorithm validates input before processing. "
        "The algorithm returns a processed response."
    )
    compressed = dict_substitute(text)
    restored = dict_desubstitute(compressed)
    _assert(
        restored == text,
        f"dict roundtrip failed:\n  in:  {text!r}\n  out: {restored!r}",
    )
    print(f"PASS: dict roundtrip ({len(text)}→{len(compressed)} chars)")


def test_dict_ignores_non_keytable_brackets():
    """Text that starts with [ but isn't a key table should pass through."""
    text = "[section]\nhost=localhost\nport=8080"
    out = dict_desubstitute(text)
    _assert(out == text, f"should have been unchanged, got: {out!r}")
    print("PASS: dict_desubstitute preserves non-keytable brackets")


def test_full_pipeline_no_crash():
    for name, text in SAMPLES.items():
        try:
            compressed = reduce(text)
            restored = restore(compressed)
        except Exception as e:
            raise AssertionError(f"reduce/restore crashed on {name}: {e}")
        _assert(
            isinstance(compressed, str) and isinstance(restored, str),
            f"reduce/restore returned non-string on {name}",
        )
    print("PASS: full pipeline runs on all samples without crash")


def test_reduction_positive_on_structured():
    """Structured corpora should show real savings."""
    for name in ("chat_repeats", "code_block", "server_logs"):
        compressed = reduce(SAMPLES[name])
        pct = reduction_pct(SAMPLES[name], compressed)
        _assert(
            pct > 10,
            f"expected >10% on {name}, got {pct:.1f}%",
        )
        print(f"PASS: {name} reduced by {pct:.1f}%")


def test_short_input_handled_cleanly():
    """Tiny input shouldn't crash or produce garbage."""
    for text in ("", "hi", "A.", "foo bar baz"):
        compressed = reduce(text)
        _assert(isinstance(compressed, str), f"non-string output for {text!r}")
    print("PASS: short inputs handled cleanly")


def test_token_estimate():
    _assert(estimate_tokens("") == 1, "empty should estimate 1 token")
    _assert(estimate_tokens("abcd") == 1, "4 chars = 1 token")
    _assert(estimate_tokens("abcde") == 2, "5 chars = 2 tokens")
    print("PASS: token estimate matches WPF convention")


# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_whitespace_idempotent()
    test_dedup_no_growth()
    test_timestamp_roundtrip()
    test_dict_roundtrip()
    test_dict_ignores_non_keytable_brackets()
    test_full_pipeline_no_crash()
    test_reduction_positive_on_structured()
    test_short_input_handled_cleanly()
    test_token_estimate()
    print("\nAll tests passed.")
