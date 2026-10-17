"""Small local RAG implementation. TF-IDF is the documented offline embedding substitute."""
import re
from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class SearchHit:
    chunk_id: int
    document_id: int
    title: str
    content: str
    score: float


def split_text(text: str, chunk_size: int = 700, overlap: int = 100) -> list[str]:
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


def retrieve(question: str, records: list[dict], top_k: int = 4) -> list[SearchHit]:
    if not records:
        return []
    corpus = [item["content"] for item in records]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    try:
        matrix = vectorizer.fit_transform(corpus + [question])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    except ValueError:
        return []
    ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)[:top_k]
    return [
        SearchHit(
            chunk_id=records[index]["chunk_id"],
            document_id=records[index]["document_id"],
            title=records[index]["title"],
            content=records[index]["content"],
            score=float(score),
        )
        for index, score in ranked if score > 0
    ]


def make_local_answer(question: str, hits: list[SearchHit]) -> str:
    if not hits:
        return "I could not find relevant information in the knowledge base. Try rephrasing your question or add a relevant article."
    # An extractive fallback keeps the demo useful without claiming to be an LLM.
    best = hits[0].content
    sentences = re.split(r"(?<=[.!?])\s+", best)
    terms = {word.lower() for word in re.findall(r"\w+", question) if len(word) > 2}
    ranked = sorted(sentences, key=lambda sentence: sum(term in sentence.lower() for term in terms), reverse=True)
    answer = " ".join(ranked[:2]).strip()
    return answer or best
