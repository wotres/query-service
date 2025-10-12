from fastapi import APIRouter
from models.query_model import QueryRequest, QueryResponse
from services import query_service

router = APIRouter()


@router.post("", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    return query_service.execute_query(request)

