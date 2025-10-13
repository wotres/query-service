from typing import Dict, Any, List

import httpx

from config.settings import settings
from models.query_model import QueryRequest, QueryResponse
from services.history_service import get_history, append_history
from services.document_service import fetch_similar_docs


def _build_messages(
    history: List[Dict[str, Any]],
    user_query: str,
    similar_docs: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, str]]:
    """
    OpenAI 스타일의 messages 생성.
    history는 이미 오래된->최신 순이라 가정.
    similar_docs가 있으면 system/context 메시지로 추가.
    """
    messages: List[Dict[str, str]] = []

    # 선택 문서 컨텍스트
    if similar_docs:
        context_lines = ["You are a helpful assistant. Use the provided documents when relevant.",
                         "Similar documents:"]
        for i, d in enumerate(similar_docs, 1):
            line = f"{i}. {d.get('title', '')}\n   {d.get('snippet', '')}"
            if d.get("url"):
                line += f"\n   URL: {d['url']}"
            context_lines.append(line)
        messages.append({"role": "system", "content": "\n".join(context_lines)})

    # 기존 히스토리
    for h in history:
        role = h.get("role", "user")
        content = h.get("content", "")
        messages.append({"role": role, "content": content})

    # 현재 사용자 문의
    messages.append({"role": "user", "content": user_query})
    return messages


def _call_llm(messages: List[Dict[str, str]]) -> str:
    """
    모의 OpenAI 스타일 LLM 서비스 호출.
    엔드포인트 예시: POST {LLM_SERVICE_URL}/v1/chat/completions
      body: { "model": "...", "messages": [...] }
      resp: { "choices": [{ "message": { "role": "assistant", "content": "..."}}] }
    """
    url = f"{settings.LLM_SERVICE_URL}/v1/chat/completions"
    payload = {"model": settings.LLM_MODEL, "messages": messages}
    headers = {}

    timeout = settings.REQUEST_TIMEOUT_SECONDS

    # 동기 httpx 사용 (라우터가 await하지 않으므로)
    with httpx.Client(timeout=timeout, headers=headers) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    try:
        content: str = data["choices"][0]["message"]["content"]
    except Exception:
        content = "죄송해요, 현재 답변을 생성하지 못했습니다."
    return content


def execute_query(request: QueryRequest) -> QueryResponse:
    """
    오케스트레이션:
      1) 히스토리 조회 (Redis -> Postgres -> Redis 캐시)
      2) selected_doc_title 있으면 RAG 호출로 유사 문서 3개
      3) 히스토리(최대 10개) + 현재 질문을 LLM 서비스에 전달
      4) LLM 응답 저장(옵션) 및 반환
    """
    user_id = request.user_id
    chat_id = request.chat_id
    query = request.query
    selected_doc_title = request.selected_doc_title

    # 1) 히스토리
    history = get_history(user_id=user_id, chat_id=chat_id, limit=settings.HISTORY_MAX)
    print(history)
    # 2) 유사 문서
    similar_docs = None
    if selected_doc_title:
        similar_docs = fetch_similar_docs(selected_doc_title, query)

    # 3) LLM 요청 메시지 구성 및 호출
    messages = _build_messages(history=history, user_query=query, similar_docs=similar_docs)
    answer = _call_llm(messages)
    print(messages)
    print(answer)
    # 4) 대화 기록에 현재 user/assistant 턴 적재
    try:
        append_history(user_id, chat_id, role="user", content=query)
        append_history(user_id, chat_id, role="assistant", content=answer)
    except Exception as e:
        print("대화 기록 저장 실패:", e)
        # 저장 실패는 응답 생성에는 영향을 주지 않음
        pass

    return QueryResponse(answer=answer)
