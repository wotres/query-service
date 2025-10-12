import json
from typing import List, TypedDict

import redis
import psycopg
from psycopg.rows import dict_row

from config.settings import settings


# ----- 설정 -----
TABLE_NAME = "chats"  # 실제 테이블명이 다르면 여기만 변경하세요.


class HistoryItem(TypedDict):
    role: str          # "user" | "assistant" | "system"
    content: str       # message 컬럼에서 읽어온 값 (본문)


_redis_client: redis.Redis | None = None
_pg_conn: psycopg.Connection | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _get_pg() -> psycopg.Connection:
    global _pg_conn
    if _pg_conn is None:
        _pg_conn = psycopg.connect(settings.POSTGRES_DSN)
    return _pg_conn


def _redis_key(user_id: str, chat_id: str) -> str:
    # 요청하신 포맷
    return f"chat-history:user_{user_id}:{chat_id}"


def get_history(user_id: str, chat_id: str, limit: int | None = None) -> List[HistoryItem]:
    """
    1) Redis 히트 시: 반환
    2) 미스 시: Postgres 조회 -> Redis 캐싱 -> 반환
    반환 형식: 오래된 순(chronological)
    """
    if limit is None:
        limit = settings.HISTORY_MAX

    r = _get_redis()
    key = _redis_key(user_id, chat_id)
    cached = r.get(key)
    if cached:
        try:
            items: List[HistoryItem] = json.loads(cached)
            # Redis에는 오래된->최신 순으로 저장해두므로 마지막 limit만 슬라이스
            return items[-limit:]
        except json.JSONDecodeError:
            # 캐시 깨졌으면 삭제하고 DB 조회
            r.delete(key)

    # DB 조회 (최신 -> 오래된 LIMIT 후 역순으로 변환)
    conn = _get_pg()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT role, message AS content
            FROM {TABLE_NAME}
            WHERE user_id = %s AND chat_id = %s
            ORDER BY created_time DESC
            LIMIT %s
            """,
            (user_id, chat_id, limit),
        )
        rows = cur.fetchall()

    items: List[HistoryItem] = [
        {"role": row["role"], "content": row["content"]}
        for row in rows
    ]
    # 오래된 순으로 정렬 (created_time DESC로 뽑았으니 역순)
    items.reverse()

    # Redis 캐싱 (오래된->최신 순 리스트 그대로 저장)
    try:
        r.set(key, json.dumps(items), ex=settings.REDIS_TTL_SECONDS)
    except Exception:
        pass

    return items


def append_history(user_id: str, chat_id: str, role: str, content: str) -> None:
    """
    신규 메시지를 DB에 적재하고 Redis 캐시도 최신화(있으면) 합니다.
    - PostgreSQL 컬럼: user_id, chat_id, message, role, created_time
    - Redis value: [{"role":..., "content":...}, ...] (오래된->최신 순)
    """
    conn = _get_pg()
    with conn.cursor() as cur:
        # created_time은 DB default(now())라 가정
        cur.execute(
            f"""
            INSERT INTO {TABLE_NAME} (user_id, chat_id, message, role)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, chat_id, content, role),
        )
        conn.commit()

    # 캐시 갱신 (있으면)
    r = _get_redis()
    key = _redis_key(user_id, chat_id)
    cached = r.get(key)
    if cached:
        try:
            items: List[HistoryItem] = json.loads(cached)
        except json.JSONDecodeError:
            items = []
        # 최신 메시지를 맨 뒤에 추가 (오래된->최신 순 유지)
        items.append({"role": role, "content": content})
        # 최대 길이 유지
        if len(items) > settings.HISTORY_MAX:
            items = items[-settings.HISTORY_MAX:]
        r.set(key, json.dumps(items), ex=settings.REDIS_TTL_SECONDS)
