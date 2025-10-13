## 로컬 실행
```bash
$ pip install -r requirements.txt
# ai-assistant-k8s private repo redis / postgresql / mock-llm-service / rag-service 실행
$ uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## Docker 실행
```bash
# 이미지 빌드
$ docker build -t query-service:ai-assistant .
# 컨테이너 실행
$ docker run -d -p 8000:8000 --name query-service query-service:ai-assistant
```

## test
```bash
# 기본 호출
$ curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_1",
    "chat_id": "chat_1",
    "query": "fast api 란?"
  }'

# RAG 연동 케이스
$ curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_1",
    "chat_id": "chat_1",
    "query": "chunk 란?",
    "selected_doc_title": "Test Title"
  }'
```