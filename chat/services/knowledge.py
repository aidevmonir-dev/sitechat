"""Find the help articles most relevant to a visitor's message (BM25, plain Python).

A site's knowledge base is tens of articles, not millions, so ranking them in memory per message is
fast and needs no vector database. The interface is one function, so embeddings can replace it later.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ..models import Article

K1 = 1.5
B = 0.75
TITLE_WEIGHT = 3  # a word in the title counts three times

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = frozenset(
    """a an and are as at be but by can do does for from had has have how i if in is it its me my of on or
    our so than that the their them then there these they this to was we were what when where which who
    why will with would you your about please tell hi hello hey thanks thank""".split()
)


def tokenize(text: str) -> list[str]:
    tokens = []
    for raw in _TOKEN.findall(text.lower()):
        if raw in _STOPWORDS or len(raw) < 2:
            continue
        for suffix in ("ing", "ies", "es", "ed", "s"):
            if raw.endswith(suffix) and len(raw) - len(suffix) >= 3:
                raw = raw[: -len(suffix)] + ("y" if suffix == "ies" else "")
                break
        tokens.append(raw)
    return tokens


def search(query: str, articles: list[Article], top_k: int = 4) -> list[Article]:
    """Return up to top_k articles that share words with the query, best match first."""
    terms = set(tokenize(query))
    if not terms or not articles:
        return []
    tokenized = [tokenize(a.title) * TITLE_WEIGHT + tokenize(a.body) for a in articles]
    count = len(tokenized)
    avg_len = sum(len(t) for t in tokenized) / count or 1.0
    doc_freq: Counter[str] = Counter()
    for tokens in tokenized:
        doc_freq.update(set(tokens) & terms)

    scored = []
    for article, tokens in zip(articles, tokenized):
        freqs = Counter(tokens)
        score = 0.0
        for term in terms:
            tf = freqs.get(term, 0)
            if tf:
                idf = math.log(1 + (count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                score += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * len(tokens) / avg_len))
        if score > 0:
            scored.append((score, article))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [article for _, article in scored[:top_k]]
