"""
cli.py — command-line benchmark and compression tool.

Commands:
    conduit-open bench <file>         Benchmark 4-pass vs zlib
    conduit-open bench --stdin        Read from stdin
    conduit-open compress <file>      Write .copen output
"""
from __future__ import annotations

import argparse
import hashlib
import math
import sys
import time
import zlib
from collections import Counter
from pathlib import Path

from .passes import reduce, restore, estimate_tokens


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1048576:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1048576:.2f} MB"


def _shannon_entropy(data: bytes) -> float:
    """Bits per byte — Shannon entropy of the input."""
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _run_bench(text: str) -> None:
    data = text.encode("utf-8")
    orig_bytes = len(data)
    orig_hash = hashlib.sha256(data).hexdigest()[:16]
    entropy = _shannon_entropy(data)
    theoretical_max = (1 - entropy / 8) * 100

    print(f"\n{'=' * 68}")
    print("  CONDUIT-OPEN — benchmark")
    print(f"  {_fmt_bytes(orig_bytes)}   sha256: {orig_hash}")
    print(
        f"  entropy: {entropy:.3f} bits/byte   "
        f"entropy upper bound: {theoretical_max:.1f}%"
    )
    print(f"{'=' * 68}\n")

    print(f"  {'method':<24} {'output':>10} {'reduction':>10}  verify  ms")
    print(f"  {'-' * 62}")

    # zlib baselines for honest comparison
    for name, level in [("zlib-6", 6), ("zlib-9", 9)]:
        t0 = time.perf_counter()
        comp = zlib.compress(data, level)
        decomp = zlib.decompress(comp)
        elapsed = (time.perf_counter() - t0) * 1000
        ok = hashlib.sha256(decomp).hexdigest()[:16] == orig_hash
        pct = (1 - len(comp) / orig_bytes) * 100
        print(
            f"  {name + ' (baseline)':<24} "
            f"{_fmt_bytes(len(comp)):>10} "
            f"{pct:>9.2f}%   "
            f"{'OK' if ok else 'FAIL':<6} "
            f"{elapsed:.0f}ms"
        )

    # 4-pass (measured in both bytes and tokens)
    t0 = time.perf_counter()
    compressed = reduce(text)
    elapsed = (time.perf_counter() - t0) * 1000

    comp_bytes = len(compressed.encode("utf-8"))
    byte_pct = (1 - comp_bytes / orig_bytes) * 100 if orig_bytes else 0.0

    orig_tok = estimate_tokens(text)
    comp_tok = estimate_tokens(compressed)
    tok_pct = (1 - comp_tok / orig_tok) * 100 if orig_tok else 0.0

    print(
        f"  {'4-pass (bytes)':<24} "
        f"{_fmt_bytes(comp_bytes):>10} "
        f"{byte_pct:>9.2f}%   "
        f"{'N/A':<6} "
        f"{elapsed:.0f}ms"
    )
    print(
        f"  {'4-pass (tokens)':<24} "
        f"{comp_tok:>10,} "
        f"{tok_pct:>9.2f}%   "
        f"{'N/A':<6} "
        f"{elapsed:.0f}ms"
    )

    print(
        "\n  4-pass is lossy on whitespace and duplicate content by design."
        "\n  If you need full fidelity, keep the original alongside the"
        "\n  compressed payload.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="conduit-open",
        description="Deterministic structural reduction for LLM API payloads",
    )
    sub = parser.add_subparsers(dest="command")

    bench = sub.add_parser("bench", help="Benchmark reduction on input data")
    bench.add_argument("file", nargs="?", help="Input file (omit for stdin)")
    bench.add_argument(
        "--stdin", action="store_true", help="Read from stdin"
    )

    comp = sub.add_parser("compress", help="Compress a file")
    comp.add_argument("file", help="Input file")
    comp.add_argument(
        "-o", "--output",
        help="Output file (default: <file>.copen)",
    )

    args = parser.parse_args()

    if args.command == "bench":
        if args.file:
            text = Path(args.file).read_text(
                encoding="utf-8", errors="replace"
            )
        else:
            text = sys.stdin.read()
        _run_bench(text)

    elif args.command == "compress":
        text = Path(args.file).read_text(
            encoding="utf-8", errors="replace"
        )
        compressed = reduce(text)
        out_path = args.output or args.file + ".copen"
        Path(out_path).write_text(compressed, encoding="utf-8")
        orig_tok = estimate_tokens(text)
        comp_tok = estimate_tokens(compressed)
        pct = (1 - comp_tok / orig_tok) * 100 if orig_tok else 0.0
        print(
            f"Compressed: {args.file} → {out_path}  "
            f"({orig_tok:,} → {comp_tok:,} tok, {pct:.1f}%)"
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
