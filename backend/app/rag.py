
"""RAG utilities using local Ollama embeddings and LLM."""

import math
import re
from dataclasses import dataclass
from typing import Any

import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings

OLLAMA_URL = "http://localhost:11434"


@dataclass
class SearchHit:
    chunk_id: int
    document_id: int
    title: str
    content: str
    score: float


def split_text(
    text: str, chunk_size: int = 700, overlap: int = 100
) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= len(text):
            break
        start = max(end - overlap, start + 1)

    return chunks


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Create real embeddings locally using Ollama."""

    if not texts:
        return []

    vectors = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=5.0)
    ) as client:
        for text in texts:
            response = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={
                    "model": settings.openai_embedding_model,
                    "input": text,
                },
            )
            response.raise_for_status()
            embeddings = response.json().get("embeddings", [])

            if not embeddings or not embeddings[0]:
                raise RuntimeError("Ollama returned no embedding.")

            vectors.append(embeddings[0])

    return vectors


def retrieve(
    question: str,
    records: list[dict[str, Any]],
    top_k: int = 4,
) -> list[SearchHit]:
    """TF-IDF fallback used by offline tests."""

    if not records:
        return []

    corpus = [item["content"] for item in records]
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
    )

    try:
        matrix = vectorizer.fit_transform(corpus + [question])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    except ValueError:
        return []

    ranked = sorted(
        enumerate(scores),
        key=lambda pair: pair[1],
        reverse=True,
    )[:top_k]

    return [
        SearchHit(
            chunk_id=records[index]["chunk_id"],
            document_id=records[index]["document_id"],
            title=records[index]["title"],
            content=records[index]["content"],
            score=float(score),
        )
        for index, score in ranked
        if score > 0
    ]


def retrieve_by_embeddings(
    question_vector: list[float],
    records: list[dict[str, Any]],
    top_k: int = 4,
) -> list[SearchHit]:
    """Rank stored embeddings using cosine similarity."""

    if not records:
        return []

    query_norm = math.sqrt(sum(v * v for v in question_vector))
    if query_norm == 0:
        return []

    scored = []

    for record in records:
        vector = record.get("embedding")
        if not vector or len(vector) != len(question_vector):
            continue

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            continue

        score = sum(
            a * b for a, b in zip(question_vector, vector)
        ) / (query_norm * norm)

        scored.append((record, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [
        SearchHit(
            chunk_id=record["chunk_id"],
            document_id=record["document_id"],
            title=record["title"],
            content=record["content"],
            score=float(score),
        )
        for record, score in scored[:top_k]
        if score > 0.15
    ]


def make_local_answer(
    question: str,
    hits: list[SearchHit],
) -> str:
    """Safe extractive fallback."""

    if not hits:
        return (
            "I could not find relevant information in the knowledge base. "
            "Try rephrasing your question or add a relevant article."
        )

    best = hits[0].content
    sentences = re.split(r"(?<=[.!?])\s+", best)
    terms = {
        word.lower()
        for word in re.findall(r"\w+", question)
        if len(word) > 2
    }

    ranked = sorted(
        sentences,
        key=lambda sentence: sum(
            term in sentence.lower() for term in terms
        ),
        reverse=True,
    )

    return " ".join(ranked[:2]).strip() or best


async def generate_grounded_answer(
    question: str,
    hits: list[SearchHit],
) -> str:
    """Generate an answer using only retrieved context."""

    if not hits:
        return make_local_answer(question, hits)

    context = "\n\n".join(
        f"[Source {i}: {hit.title}]\n{hit.content}"
        for i, hit in enumerate(hits, start=1)
    )

    payload = {
        "model": settings.openai_model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a knowledge-base assistant. Answer using only "
                    "the supplied source context. Do not invent facts or "
                    "use outside knowledge. If the sources do not answer "
                    "the question, say that the information could not be "
                    "found in the knowledge base. Keep the answer concise."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Source context:\n{context}"
                ),
            },
        ],
        "options": {"temperature": 0},
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(180.0, connect=5.0)
    ) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    answer = data.get("message", {}).get("content", "").strip()
    return answer or make_local_answer(question, hits)
