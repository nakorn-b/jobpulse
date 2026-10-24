from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.rag import LLMService, SimpleRetrievalStrategy
from app.storage.vector_db import QdrantService

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


class ChatRequest(BaseModel):
    message: str


class JobItem(BaseModel):
    # Qdrant payloads may carry extra fields; drop anything not listed here
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    category: str | None = None
    url: str | None = None
    posted_date: str | None = None
    description: str | None = None


class ChatResponse(BaseModel):
    response: str
    job_list: list[JobItem]


@lru_cache
def get_llm_service() -> LLMService:
    """Build the Qdrant client and LLM clients once and reuse them across requests."""
    return LLMService(QdrantService(), SimpleRetrievalStrategy())


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, llm: LLMService = Depends(get_llm_service)) -> ChatResponse:
    "Answer the user's message and return the jobs the answer is based on"
    try:
        result = llm.chat(request.message)
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=502, detail="Failed to generate a response")

    return ChatResponse(
        response=result["response"],
        job_list=[JobItem(**job) for job in result["job_list"]],
    )
