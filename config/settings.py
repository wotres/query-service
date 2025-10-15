import os


class Settings:
    # 기본 동작
    HISTORY_MAX: int = int(os.getenv("HISTORY_MAX", 10))
    REDIS_TTL_SECONDS: int = int(os.getenv("REDIS_TTL_SECONDS", 3600))

    # Redis (단일 마스터 접속; sentinel 쓰려면 별도 코드 필요)
    # 컨테이너 내부에서 접속 시: redis-master:6379
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://:redis@127.0.0.1:6379/0")

    # Postgres DSN (psycopg v3)
    # 컨테이너 내부에서 접속 시: postgres:5432 / 외부 접속 시: ip:5432
    POSTGRES_DSN: str = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")

    # 외부 서비스
    RAG_SERVICE_URL: str = os.getenv("RAG_SERVICE_URL", "http://localhost:8001")
    LLM_SERVICE_URL: str = os.getenv("LLM_SERVICE_URL", "http://localhost:8888")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "mock-llm")

    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", 15))

    class Config:
        env_file = ".env"


settings = Settings()
