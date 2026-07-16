# Conduit-Open

Drop-in Python middleware that reduces the token payload sent to LLM APIs. Four deterministic passes, no account, no telemetry, and no runtime dependencies beyond the Python standard library.

> While this is a much more limited version of our full capability, we thought it was still useful. Enjoy.

---

## What it does

Wrap any text before it hits your AI provider. Everything runs locally, deterministically.

1. **Whitespace normalization** — collapses redundant spacing and line endings
2. **Sentence-level deduplication** — drops exact-repeat sentences from long paragraphs; catches adjacent duplicates on short lines
3. **Timestamp encoding** — replaces repeated ISO timestamps with short references (`[t=0]`, `[t=1]`, ...)
4. **Dictionary substitution** — replaces frequent 7+ character words with single-char symbols when the math works out

The model receives a normalized, deduplicated form with reversible timestamp and dictionary encoding. Nothing is summarized, paraphrased, or inferred by another model.

---

## Install

```bash
pip install conduit-open
```

Or from source:

```bash
git clone https://github.com/Axiom-Symbiotic/conduit-open
cd conduit-open
pip install -e .
```

Zero runtime dependencies.

---

## Usage

### One-shot

```python
from conduit_open import reduce

smaller = reduce(long_prompt)
```

### As a stateful middleware

```python
from conduit_open import ConduitMiddleware

mw = ConduitMiddleware(verbose=True)

compressed = mw.compress(your_prompt)
response   = your_api_call(compressed)

# ... after a while ...
print(mw.stats())
# {'calls': 12, 'total_original_tokens': 4821,
#  'total_compressed_tokens': 3094, 'tokens_saved': 1727,
#  'reduction_pct': 35.82}
```

### CLI

```bash
conduit-open bench your_corpus.txt          # benchmark 4-pass vs zlib
conduit-open bench --stdin < data.txt       # pipe input
conduit-open compress your_file.txt         # write .copen file
```

---

## Honest numbers

Reductions range **from ~15% on conversational prose to ~49% on structured data**. The more structural regularity in your input, the more it saves.

| Corpus type | Typical reduction |
|-------------|-------------------|
| Server logs with timestamps | 40–55% |
| JSON / API payloads | 40–50% |
| Stack traces | 35–45% |
| Source code | 30–45% |
| Mixed enterprise data | 25–40% |
| Config files | 15–25% |
| Conversational prose | 15–25% |
| Truly random / pre-compressed | ~0% (correct) |

Against byte-preserving general-purpose algorithms, zlib on mixed enterprise data can reach a similar range. The 4-pass pipeline targets structural redundancy rather than byte-level entropy; passes 1 and 2 intentionally remove formatting and exact duplicate content, while passes 3 and 4 are reversible.

---

## Benchmark tool

The repo ships with a browser-side codec comparison at `benchmark/index.html`. It hash-verifies deflate/gzip on your input and labels all non-executed comparison rows as illustrative estimates. The page does not upload your data; it currently loads pako from a CDN. Use `conduit-open bench` for the authoritative 4-pass measurement.

---

## What this is not

- Not semantic compression
- Not model-generated approximation or summarization
- Not an AI wrapper calling another model
- Not a tokenizer-aware optimizer

It's a structural text pre-processor: regex/string based and deterministic. The same input always produces the same output.

---

## Limits

- **Short inputs** (under a few hundred characters) — key-table overhead can exceed savings
- **High-entropy data** (random, pre-compressed, encrypted) — nothing to remove
- **Pure novel prose with no repetition** — minimal savings, but no penalty

The CLI `bench` command tells you which category your data falls in.

---

## Companion products

- **[Conduit-Reduction](https://github.com/Axiom-Symbiotic/conduit-reduction)** — the same 4-pass algorithm packaged as a desktop widget. For end users who just want to paste, reduce, and paste.
- **Full Conduit** — the broader product this is a slice of. Adds corpus-indexed retrieval, memory management, PII stripping, provider routing, and a trust-mediated buffer layer. [axiomsymbiotic.org](https://axiomsymbiotic.org)

---

## License

MIT. Fork it, extend it, ship it.

---

Built by [Axiom Symbiotic](https://axiomsymbiotic.org).
