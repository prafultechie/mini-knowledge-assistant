
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, get_session, init_db
from app.limiter import limiter
from app.models import Chunk, Document, QuestionLog
from app.rag import (
    create_embeddings,
    generate_grounded_answer,
    make_local_answer,
    retrieve,
    retrieve_by_embeddings,
    split_text,
)
from app.schemas import (
    AskRequest,
    AskResponse,
    DocumentCreate,
    DocumentListItem,
    DocumentListResponse,
    DocumentResponse,
    SourceItem,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield
    await engine.dispose()


app = FastAPI(
    title="Mini Knowledge Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_ask_requests(request: Request, call_next):
    """Apply rate limiting before FastAPI validates the request body."""
    if request.url.path == "/ask" and request.method == "POST":
        try:
            limiter.check(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )

    return await call_next(request)


def utc_aware(value: datetime) -> datetime:
    """Ensure database timestamps are timezone-aware."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@app.get("/health")
async def health() -> dict[str, str]:
    """Check whether the API is responding."""
    return {"status": "ok"}


@app.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=201,
)
async def create_document(
    payload: DocumentCreate,
    session: AsyncSession = Depends(get_session),
):
    """Save a document, split it into chunks, and generate local embeddings."""
    title = payload.title.strip()
    content = payload.content.strip()

    if not title or not content:
        raise HTTPException(
            status_code=422,
            detail="Title and content must not be blank.",
        )

    pieces = split_text(
        content,
        settings.chunk_size,
        settings.chunk_overlap,
    )

    if not pieces:
        raise HTTPException(
            status_code=422,
            detail="The document does not contain usable text.",
        )

    # Generate embeddings using the local Ollama embedding model.
    try:
        embeddings = await create_embeddings(pieces)

        if len(embeddings) != len(pieces):
            raise RuntimeError(
                "The embedding count does not match the chunk count."
            )

    except Exception as exc:
        logger.exception("Local document embedding failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "Ollama embedding service is unavailable. "
                "Please check that Ollama is running and the "
                "embedding model is installed."
            ),
        ) from exc

    # Save the document and its embedded chunks.
    try:
        document = Document(
            title=title,
            content=content,
        )

        session.add(document)
        await session.flush()

        chunks = [
            Chunk(
                document_id=document.id,
                chunk_index=index,
                content=piece,
                embedding_json=json.dumps(embeddings[index]),
            )
            for index, piece in enumerate(pieces)
        ]

        session.add_all(chunks)

        await session.commit()
        await session.refresh(document)

    except Exception:
        await session.rollback()
        logger.exception("Document database save failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to save the document. Please try again.",
        )

    return DocumentResponse(
        document_id=document.id,
        title=document.title,
        created_at=utc_aware(document.created_at),
        status="indexed",
    )


@app.get(
    "/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Return a paginated list of uploaded documents."""
    total = (
        await session.scalar(
            select(func.count()).select_from(Document)
        )
        or 0
    )

    result = await session.scalars(
        select(Document)
        .order_by(
            Document.created_at.desc(),
            Document.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = [
        DocumentListItem(
            document_id=item.id,
            title=item.title,
            created_at=utc_aware(item.created_at),
        )
        for item in result.all()
    ]

    return DocumentListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@app.post(
    "/ask",
    response_model=AskResponse,
)
async def ask_question(
    payload: AskRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Retrieve relevant document chunks and generate a grounded answer."""
    question = payload.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question must not be blank.",
        )

    result = await session.execute(
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.content,
            Chunk.embedding_json,
            Document.title,
        )
        .join(
            Document,
            Document.id == Chunk.document_id,
        )
    )

    rows = result.all()

    records = [
        {
            "chunk_id": row.id,
            "document_id": row.document_id,
            "content": row.content,
            "title": row.title,
            "embedding": (
                json.loads(row.embedding_json)
                if row.embedding_json
                else None
            ),
        }
        for row in rows
    ]

    # Keep question logging in the same transaction as the request.
    await session.execute(
        QuestionLog.__table__.insert().values(
            question=question
        )
    )

    if not records:
        hits = []
        answer = (
            "I could not find any uploaded documents to answer "
            "your question. Please upload a document first."
        )

    else:
        try:
            # Create and persist embeddings for older chunks if needed.
            missing = [
                index
                for index, item in enumerate(records)
                if item["embedding"] is None
            ]

            if missing:
                missing_texts = [
                    records[index]["content"]
                    for index in missing
                ]

                vectors = await create_embeddings(missing_texts)

                if len(vectors) != len(missing):
                    raise RuntimeError(
                        "The embedding count does not match the chunk count."
                    )

                for index, vector in zip(missing, vectors):
                    records[index]["embedding"] = vector

                    await session.execute(
                        Chunk.__table__
                        .update()
                        .where(
                            Chunk.id
                            == records[index]["chunk_id"]
                        )
                        .values(
                            embedding_json=json.dumps(vector)
                        )
                    )

            # Embed the question using the same local model.
            question_vectors = await create_embeddings([question])

            if not question_vectors:
                raise RuntimeError(
                    "Ollama returned no question embedding."
                )

            question_vector = question_vectors[0]

            # Retrieve semantically relevant chunks.
            hits = retrieve_by_embeddings(
                question_vector,
                records,
            )

            # Generate an answer using the local Ollama LLM.
            answer = await generate_grounded_answer(
                question,
                hits,
            )

        except Exception as exc:
            await session.rollback()
            logger.exception("Local RAG request failed")

            raise HTTPException(
                status_code=502,
                detail=(
                    "The local AI service is temporarily unavailable. "
                    "Check Ollama and the required local models, "
                    "then try again."
                ),
            ) from exc

    try:
        await session.commit()

    except Exception:
        await session.rollback()
        logger.exception("Question log or embedding save failed")

        raise HTTPException(
            status_code=500,
            detail="Unable to complete the request. Please try again.",
        )

    sources = [
        SourceItem(
            document_id=hit.document_id,
            title=hit.title,
            chunk_id=hit.chunk_id,
            excerpt=hit.content[:280],
            score=round(hit.score, 4),
        )
        for hit in hits
    ]

    return AskResponse(
        answer=answer,
        sources=sources,
    )


@app.exception_handler(Exception)
async def safe_unexpected_error(
    request: Request,
    exc: Exception,
):
    """Log unexpected errors without exposing internal details."""
    logger.error(
        "Unhandled request error for %s %s",
        request.method,
        request.url.path,
        exc_info=(
            type(exc),
            exc,
            exc.__traceback__,
        ),
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "An unexpected error occurred. Please try again."
            )
        },
    )
