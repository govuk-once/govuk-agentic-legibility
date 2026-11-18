"""Small Okapi BM25 implementation over journey titles and descriptions.

Written inline rather than adding a dependency; the catalogue is ~550 short
documents, so a plain inverted index is plenty.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

STOPWORDS = frozenset(
    """a about after again all also am an and any are as at be been before being
    both but by can could did do does during each for from get got had has have
    here how i if im in into is it its just like me more my need of off on or our
    out over please so some such than that the their them then there these they
    this through to too up us very want was we were what when where which while
    who why will with would you your""".split()
)


def stem(word: str) -> str:
    """Very light suffix stripping, so 'sightings'/'sighting'/'sighted' meet."""
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower().replace("’", "'").replace("'", ""))
    return [stem(w) for w in words if w not in STOPWORDS]


class BM25:
    def __init__(
        self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75
    ) -> None:
        self.k1 = k1
        self.b = b
        self.doc_lengths = [len(doc) for doc in documents]
        self.avg_length = sum(self.doc_lengths) / max(len(documents), 1)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for index, doc in enumerate(documents):
            for term, freq in Counter(doc).items():
                self.postings[term].append((index, freq))
        n = len(documents)
        self.idf = {
            term: math.log((n - len(postings) + 0.5) / (len(postings) + 0.5) + 1)
            for term, postings in self.postings.items()
        }

    def scores(self, query: list[str]) -> dict[int, float]:
        """BM25 score for every document sharing at least one query term."""
        scores: dict[int, float] = defaultdict(float)
        for term in set(query):
            for index, freq in self.postings.get(term, ()):
                norm = self.k1 * (
                    1 - self.b + self.b * self.doc_lengths[index] / self.avg_length
                )
                scores[index] += self.idf[term] * freq * (self.k1 + 1) / (freq + norm)
        return scores
