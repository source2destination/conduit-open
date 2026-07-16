"""
passes.py — four-pass structural reduction pipeline.

Ported from the Conduit-Reduction WPF widget. Behavior-equivalent:
the same input produces the same compressed output in both
implementations.

Passes 1 and 2 are lossy with respect to whitespace and duplicate
content (that's the point — they remove redundancy). Passes 3 and 4
are fully reversible via `restore()`.
"""
from __future__ import annotations

import math
import re
from collections import OrderedDict
from typing import Tuple


# ─────────────────────────────────────────────────────────────────────
# Token estimator (matches WPF: ceil(chars / 4))
# ─────────────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Rough token count. ~4 chars per token, minimum 1."""
    if not text:
        return 1
    return max(1, math.ceil(len(text) / 4))


# ─────────────────────────────────────────────────────────────────────
# Pass 1: Whitespace normalization
# ─────────────────────────────────────────────────────────────────────

def normalize_whitespace(text: str) -> str:
    """Collapse whitespace runs; normalize line endings; trim."""
    text = re.sub(r'\r\n|\r', '\n', text)              # line endings
    text = re.sub(r'[^\S\n]+', ' ', text)              # collapse horizontal ws
    text = re.sub(r'\n{3,}', '\n\n', text)             # max 2 consecutive newlines
    text = re.sub(r'[ \t]+\n', '\n', text)             # trailing ws on lines
    return text.strip()


# ─────────────────────────────────────────────────────────────────────
# Pass 2: Sentence-level deduplication
# ─────────────────────────────────────────────────────────────────────

_SENT_RX = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')


def _is_structural_only(s: str) -> bool:
    """Lines made only of structural punctuation — never dedupe these."""
    if not s:
        return True
    return all(c in '{}()[];,:' for c in s)


def dedup(text: str) -> str:
    """
    Paragraph-aware deduplication.

    - Paragraphs >= 20 chars: split to sentences, dedup exact repeats
      globally (>=15 char sentences only)
    - Paragraphs < 20 chars: passthrough, but drop consecutive exact
      duplicates unless structural-only (braces, punctuation lines)
    """
    paragraphs = text.split('\n')
    seen_sentences = set()
    result_paras = []
    prev_trimmed = None

    for para in paragraphs:
        trimmed = para.strip()

        if len(trimmed) < 20:
            # Short-line branch: drop only exact consecutive duplicates
            if (not _is_structural_only(trimmed)
                    and prev_trimmed is not None
                    and prev_trimmed == trimmed):
                continue
            result_paras.append(para)
            prev_trimmed = trimmed
            continue

        # Long-paragraph branch: sentence-level global dedup
        sentences = _SENT_RX.split(trimmed)
        kept = []
        for s in sentences:
            st = s.strip()
            if len(st) < 15 or st not in seen_sentences:
                kept.append(st)
                if len(st) >= 15:
                    seen_sentences.add(st)

        if kept:
            joined = ' '.join(kept)
            result_paras.append(joined)
            prev_trimmed = joined.strip()

    return '\n'.join(result_paras).rstrip()


# ─────────────────────────────────────────────────────────────────────
# Pass 3: Timestamp reference encoding (reversible)
# ─────────────────────────────────────────────────────────────────────

_TIMESTAMP_RX = re.compile(
    r'\b(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'
    r'(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b'
)
_REF_RX = re.compile(r'\[t=(\d+)\]')


def compress_timestamps(text: str) -> str:
    """
    First occurrence of each unique timestamp is kept in full.
    Subsequent occurrences collapse to `[t=N]` where N is the order
    of first appearance.
    """
    matches = list(_TIMESTAMP_RX.finditer(text))
    if len(matches) < 2:
        return text

    seen: dict = {}

    def repl(m: re.Match) -> str:
        ts = m.group(0)
        if ts not in seen:
            seen[ts] = len(seen)
            return ts
        return f'[t={seen[ts]}]'

    return _TIMESTAMP_RX.sub(repl, text)


def decompress_timestamps(text: str) -> str:
    """Inverse of compress_timestamps. Rebuilds the order-of-appearance map."""
    order = []
    seen_set = set()
    for m in _TIMESTAMP_RX.finditer(text):
        ts = m.group(0)
        if ts not in seen_set:
            order.append(ts)
            seen_set.add(ts)

    def repl(m: re.Match) -> str:
        idx = int(m.group(1))
        return order[idx] if idx < len(order) else m.group(0)

    return _REF_RX.sub(repl, text)


# ─────────────────────────────────────────────────────────────────────
# Pass 4: Dictionary substitution (reversible via prepended key table)
# ─────────────────────────────────────────────────────────────────────

# Matches WPF symbol set
_SYMBOLS = list('!@#$%^&*~`|<>?αβγδεζηθικλμνξπρστυφχψω')
_WORD_RX = re.compile(r'[A-Za-z]{7,}')


def dict_substitute(text: str) -> str:
    """
    Replace frequent 7+ char words with single-char symbols where net
    savings are positive. Prepends `[X=word Y=word ...]` key table.
    """
    freq: dict = {}
    for m in _WORD_RX.finditer(text):
        w = m.group(0)
        freq[w] = freq.get(w, 0) + 1

    subs = OrderedDict()
    idx = 0
    # Order by (occurrences × chars_saved_each) descending
    ranked = sorted(freq.items(), key=lambda kv: -kv[1] * (len(kv[0]) - 1))
    for word, occurrences in ranked:
        if idx >= len(_SYMBOLS):
            break
        saving_per = len(word) - 1      # symbol is 1 char
        key_cost = len(word) + 3        # "X=Word "
        net = saving_per * occurrences - key_cost
        if net > 0:
            subs[word] = _SYMBOLS[idx]
            idx += 1

    if not subs:
        return text

    # Replace longest-first with word boundaries to avoid partial matches
    result = text
    for word in sorted(subs.keys(), key=len, reverse=True):
        result = re.sub(
            rf'\b{re.escape(word)}\b',
            subs[word],
            result,
        )

    key_table = ' '.join(f'{sym}={word}' for word, sym in subs.items())
    return f'[{key_table}]{result}'


def dict_desubstitute(text: str) -> str:
    """Inverse of dict_substitute. Parses the `[key=word ...]` header."""
    if not text.startswith('['):
        return text
    end = text.find(']')
    if end < 0:
        return text

    header = text[1:end]
    body = text[end + 1:]

    # Only treat as a key table if every space-separated token has an '=' and
    # looks like "symbol=word". Otherwise, leave text alone (it was a
    # genuine bracket in the source content).
    pairs = header.split(' ')
    subs = {}
    for pair in pairs:
        if '=' not in pair:
            return text  # not a key table
        sym, word = pair.split('=', 1)
        if not sym or not word:
            return text
        subs[sym] = word

    result = body
    for sym, word in subs.items():
        result = result.replace(sym, word)
    return result


# ─────────────────────────────────────────────────────────────────────
# Full pipeline
# ─────────────────────────────────────────────────────────────────────

def reduce(text: str) -> str:
    """Run all 4 passes. Returns compressed text ready to send."""
    t = normalize_whitespace(text)
    t = dedup(t)
    t = compress_timestamps(t)
    t = dict_substitute(t)
    return t


def restore(compressed: str) -> str:
    """
    Invert passes 3 and 4. Passes 1 and 2 are lossy (whitespace and
    duplicate content are gone by design); output is the normalized
    deduped form of the original.
    """
    t = dict_desubstitute(compressed)
    t = decompress_timestamps(t)
    return t


def reduction_pct(original: str, compressed: str) -> float:
    """Percentage saved in token-estimate terms (WPF convention)."""
    if not original:
        return 0.0
    orig_tok = estimate_tokens(original)
    comp_tok = estimate_tokens(compressed)
    return (1 - comp_tok / orig_tok) * 100
