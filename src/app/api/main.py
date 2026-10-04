from fastapi import FastAPI
from app.api.routers import query

app = FastAPI()

app.include_router(query.router)

@app.get("/health")
def check_health():
    "Health Check"
    return {"status": "ok"}



