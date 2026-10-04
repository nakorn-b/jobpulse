from fastapi import FastAPI, APIRouter

router = APIRouter(
    prefix="/query",
    tags=["Query"],
)

@router.post("")
def query(user_input: str) -> dict:
    "Answer user question using their user input"

    return {"response": "Answer of user input"}