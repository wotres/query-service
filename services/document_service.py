from typing import List, TypedDict
import httpx

from config.settings import settings


class SimilarDoc(TypedDict):
    title: str
    content: str
    distance: float


def fetch_similar_docs(selected_doc_title: str, query: str) -> List[SimilarDoc]:
    """
    RAG 서비스로부터 유사 문서 결과(0~3개)를 받아옵니다.
    - 응답 형식: { "results": [ { "title": "...", "content": "...", "distance": 0.123 }, ... ] }
    - 결과가 없거나(204/빈 배열) 오류 시 [] 반환
    """
    url = f"{settings.RAG_SERVICE_URL}/search"
    payload = {"title": selected_doc_title, "query": query}
    timeout = settings.REQUEST_TIMEOUT_SECONDS

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers={"Accept": "application/json"})
            # 결과가 없으면 204일 수도 있음
            if resp.status_code == 204:
                return []

            resp.raise_for_status()

            # JSON 파싱 안전 처리
            try:
                data = resp.json()
            except ValueError:
                return []

            results = data.get("results") or []
            out: List[SimilarDoc] = []

            for d in results[:3]:  # 최대 3개
                title = d.get("title") or ""
                content = d.get("content") or ""
                # distance 누락 시 기본값 0.0 (또는 None 허용하려면 타입 수정)
                distance_raw = d.get("distance", 0.0)
                try:
                    distance = float(distance_raw)
                except (TypeError, ValueError):
                    distance = 0.0

                out.append({"title": title, "content": content, "distance": distance})

            return out

    except Exception:
        # 실패 시 빈 리스트로 폴백
        return []
