from fastapi import FastAPI

from app.api.routers import chat, search

app = FastAPI()

app.include_router(search.router)
app.include_router(chat.router)

@app.get("/health")
def check_health():
    "Health Check"
    return {"status": "ok"}



