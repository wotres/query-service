from fastapi import FastAPI
from routers.query_router import router as query_router

app = FastAPI(title="Query Service")

app.include_router(query_router, prefix="/query", tags=["Query"])

