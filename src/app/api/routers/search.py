
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.routers.chat import JobItem, get_llm_service
from app.rag import LLMService

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


class SearchRequest(BaseModel):
    query: str
    k: int = 5


class SearchResponse(BaseModel):
    job_list: list[JobItem]


@router.post("", response_model=SearchResponse)
def search(request: SearchRequest, llm: LLMService = Depends(get_llm_service)) -> SearchResponse:
    "Return the jobs most relevant to the query, without generating an answer"
    try:
        docs = llm.retrieve(request.query, k=request.k)
    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(status_code=502, detail="Failed to retrieve jobs")

    return SearchResponse(job_list=[JobItem(**job) for job in docs])
