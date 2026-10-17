import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import engine, get_session, init_db
from app.limiter import limiter
from app.models import Chunk, Document, QuestionLog
from app.rag import make_local_answer, retrieve, split_text
from app.schemas import AskRequest, AskResponse, DocumentCreate, DocumentListItem, DocumentListResponse, DocumentResponse, SourceItem


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield
    await engine.dispose()


app = FastAPI(title="Mini Knowledge Assistant", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])


def utc_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents", response_model=DocumentResponse, status_code=201)
async def create_document(payload: DocumentCreate, session: AsyncSession = Depends(get_session)):
    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(status_code=422, detail="Title and content must not be blank.")
    pieces = split_text(content, settings.chunk_size, settings.chunk_overlap)
    document = Document(title=title, content=content)
    session.add(document)
    await session.flush()
    session.add_all([Chunk(document_id=document.id, chunk_index=index, content=piece) for index, piece in enumerate(pieces)])
    await session.commit()
    await session.refresh(document)
    return DocumentResponse(document_id=document.id, title=document.title, created_at=utc_aware(document.created_at), status="indexed")


@app.get("/documents", response_model=DocumentListResponse)
async def list_documents(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), session: AsyncSession = Depends(get_session)):
    total = await session.scalar(select(func.count()).select_from(Document)) or 0
    result = await session.scalars(select(Document).order_by(Document.created_at.desc(), Document.id.desc()).offset((page - 1) * page_size).limit(page_size))
    items = [DocumentListItem(document_id=item.id, title=item.title, created_at=utc_aware(item.created_at)) for item in result.all()]
    return DocumentListResponse(items=items, page=page, page_size=page_size, total=total)


@app.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest, request: Request, session: AsyncSession = Depends(get_session)):
    limiter.check(request)
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank.")
    await session.execute(QuestionLog.__table__.insert().values(question=question))
    result = await session.execute(select(Chunk.id, Chunk.document_id, Chunk.content, Document.title).join(Document, Document.id == Chunk.document_id))
    rows = result.all()
    records = [{"chunk_id": row.id, "document_id": row.document_id, "content": row.content, "title": row.title} for row in rows]
    # sklearn vectorization is CPU work, so keep it off the async event loop.
    hits = await asyncio.to_thread(retrieve, question, records)
    answer = make_local_answer(question, hits)
    await session.commit()
    sources = [SourceItem(document_id=hit.document_id, title=hit.title, chunk_id=hit.chunk_id, excerpt=hit.content[:280], score=round(hit.score, 4)) for hit in hits]
    return AskResponse(answer=answer, sources=sources)


@app.exception_handler(Exception)
async def safe_unexpected_error(_: Request, exc: Exception):
    # Do not return stack traces or connection details to the client.
    import logging
    logging.getLogger(__name__).exception("Unhandled request error", exc_info=exc)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred. Please try again."})
