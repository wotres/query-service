from pydantic import BaseModel


class QueryRequest(BaseModel):
    user_id: str
    chat_id: str
    query: str
    selected_doc_title: str | None = None


class QueryResponse(BaseModel):
    answer: str
