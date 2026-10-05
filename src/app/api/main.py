from fastapi import FastAPI
from app.api.routers import query, chat

app = FastAPI()

app.include_router(query.router)
app.include_router(chat.router)

@app.get("/health")
def check_health():
    "Health Check"
    return {"status": "ok"}



