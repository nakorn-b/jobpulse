from app.rag import LLMService, RAGFusionStrategy
from app.storage.vector_db import QdrantService
from fastapi import APIRouter
from app.rag.rag_fusion import RAGFusionStrategy

router = APIRouter(
    prefix="/query",
    tags=["Query"],
)

@router.post("")
def query(user_input: str) -> dict:
    "Answer user question using their user input"
    qdrant = QdrantService()
    strategy = RAGFusionStrategy()
    llm = LLMService(qdrant, strategy)
    response = llm.query(user_input)
    return {"response": response}