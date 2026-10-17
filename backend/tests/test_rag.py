from app.rag import make_local_answer, retrieve, split_text


def test_split_text_keeps_all_content():
    text = "alpha beta gamma " * 100
    chunks = split_text(text, chunk_size=100, overlap=15)
    assert len(chunks) > 1
    assert all(chunks)
    assert "alpha" in " ".join(chunks)


def test_retrieve_ranks_relevant_chunk():
    records = [
        {"chunk_id": 1, "document_id": 1, "title": "Refunds", "content": "Customers can request a refund within thirty days."},
        {"chunk_id": 2, "document_id": 2, "title": "Office", "content": "The office kitchen closes at six in the evening."},
    ]
    hits = retrieve("When can a customer request a refund?", records)
    assert hits
    assert hits[0].chunk_id == 1


def test_no_match_returns_safe_fallback():
    assert "could not find relevant information" in make_local_answer("unknown", []).lower()
