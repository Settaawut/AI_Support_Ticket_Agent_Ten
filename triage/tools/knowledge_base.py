"""search_knowledge_base: BM25 over the bundled bilingual FAQ."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Any

from pydantic import BaseModel, Field

from triage.data import load_json
from triage.models import Language
from triage.tools.base import Tool
from triage.tools.bm25 import BM25Index, ScoredDoc

TOP_K = 3
MIN_SCORE = 1.0  # below this, matches are noise (a single common word)


@dataclass(frozen=True)
class _Corpus:
    articles: list[dict[str, Any]]
    index: BM25Index


@cache
def _corpus(language: Language | None) -> _Corpus:
    """One cached index per language filter (None = all languages)."""
    articles = [
        a for a in load_json("kb.json") if language is None or a["language"] == language.value
    ]
    texts = [f"{a['title']} {a['title']} {' '.join(a['tags'])} {a['body']}" for a in articles]
    return _Corpus(articles, BM25Index(texts))


class SearchKnowledgeBaseArgs(BaseModel):
    query: str = Field(description="Short search query describing ONE customer need.")
    language: Language = Field(
        description="Preferred article language: 'th' or 'en'. Falls back to all languages."
    )


def search_knowledge_base(args: SearchKnowledgeBaseArgs) -> dict[str, Any]:
    preferred = args.language if args.language is not Language.OTHER else None
    hits, corpus = _search(preferred, args.query)
    fallback = False
    if not hits and preferred is not None:
        hits, corpus = _search(None, args.query)
        fallback = True
    if not hits:
        return {
            "query": args.query,
            "results": [],
            "message": "No relevant article found. Do not invent an answer for this need.",
        }
    return {
        "query": args.query,
        "language_fallback": fallback,
        "results": [
            {
                "id": corpus.articles[h.index]["id"],
                "title": corpus.articles[h.index]["title"],
                "language": corpus.articles[h.index]["language"],
                "score": round(h.score, 2),
                "content": corpus.articles[h.index]["body"],
            }
            for h in hits
        ],
    }


def _search(language: Language | None, query: str) -> tuple[list[ScoredDoc], _Corpus]:
    corpus = _corpus(language)
    return corpus.index.search(query, top_k=TOP_K, min_score=MIN_SCORE), corpus


KNOWLEDGE_BASE_TOOL = Tool(
    name="search_knowledge_base",
    description=(
        "Search the help-center knowledge base (English and Thai articles). Use one focused "
        "query per customer need. Returns the top articles with ids, scores and content, or "
        "an explicit 'no result'. Only facts from returned articles may be used in replies."
    ),
    args_model=SearchKnowledgeBaseArgs,
    handler=search_knowledge_base,
)
