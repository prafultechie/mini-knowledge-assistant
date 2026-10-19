
import asyncio
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
from app.rag import make_local_answer, retrieve, split_text
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
    try:
        yield
    finally:
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


def utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@app.get("/health")
async def health() -> dict[str, str]:
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
            detail="Document content cannot be empty.",
        )

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
            )
            for index, piece in enumerate(pieces)
        ]

        session.add_all(chunks)
        await session.commit()
        await session.refresh(document)

        return DocumentResponse(
            document_id=document.id,
            title=document.title,
            created_at=utc_aware(document.created_at),
            status="indexed",
        )

    except Exception:
        await session.rollback()
        raise


@app.get(
    "/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
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


@app.post("/ask", response_model=AskResponse)
async def ask_question(
    payload: AskRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    limiter.check(request)

    question = payload.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question must not be blank.",
        )

    try:
        await session.execute(
            QuestionLog.__table__.insert().values(
                question=question
            )
        )

        result = await session.execute(
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.content,
                Document.title,
            ).join(
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
            }
            for row in rows
        ]

        # Run CPU-intensive retrieval outside the async event loop.
        hits = await asyncio.to_thread(
            retrieve,
            question,
            records,
        )

        answer = make_local_answer(question, hits)

        await session.commit()

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

    except HTTPException:
        await session.rollback()
        raise

    except Exception:
        await session.rollback()
        raise


@app.exception_handler(Exception)
async def safe_unexpected_error(
    request: Request,
    exc: Exception,
):
    # Log the exception internally without exposing details to clients.
    logger.error(
        "Unhandled request error for %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "An unexpected error occurred. Please try again."
            )
        },
    )
