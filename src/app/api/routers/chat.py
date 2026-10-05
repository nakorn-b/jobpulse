from functools import lru_cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.rag import LLMService
from app.rag.rag_fusion import RAGFusionStrategy
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

    id: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    posted_date: Optional[str] = None
    description: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    job_list: List[JobItem]


@lru_cache
def get_llm_service() -> LLMService:
    """Build the Qdrant client and LLM clients once and reuse them across requests."""
    return LLMService(QdrantService(), RAGFusionStrategy())


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
