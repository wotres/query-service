import json
from typing import List, TypedDict
import redis
import psycopg
from psycopg.rows import dict_row
from config.settings import settings

TABLE_NAME = "chats"


class HistoryItem(TypedDict):
    role: str
    content: str


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
    return f"chat-history:user_{user_id}:{chat_id}"


def get_history(user_id: str, chat_id: str, limit: int | None = None) -> List[HistoryItem]:
    """Redis list에서 최근 메시지를 오래된 순으로 가져오기"""
    if limit is None:
        limit = settings.HISTORY_MAX

    r = _get_redis()
    key = _redis_key(user_id, chat_id)
    data = r.lrange(key, -limit, -1)  # 최신 limit개
    if data:
        return [json.loads(x) for x in data]

    # 캐시에 없으면 DB에서 불러오기
    conn = _get_pg()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT role, message AS content
            FROM {TABLE_NAME}
            WHERE user_id = %s AND chat_id = %s
            ORDER BY created_time ASC
            LIMIT %s
            """,
            (user_id, chat_id, limit),
        )
        rows = cur.fetchall()

    items = [{"role": row["role"], "content": row["content"]} for row in rows]

    # Redis에 다시 채워넣기
    if items:
        with r.pipeline() as pipe:
            for item in items:
                pipe.rpush(key, json.dumps(item, ensure_ascii=False))
            pipe.expire(key, settings.REDIS_TTL_SECONDS)
            pipe.execute()

    return items

def append_history(user_id: str, chat_id: str, role: str, content: str) -> None:
    conn = _get_pg()
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT title FROM {TABLE_NAME} WHERE user_id=%s AND chat_id=%s LIMIT 1",
            (user_id, chat_id),
        )
        row = cur.fetchone()
        title = row[0] if row and row[0] else (content[:2] if content else "채팅")

        cur.execute(
            f"""
            INSERT INTO {TABLE_NAME} (user_id, chat_id, title, message, role)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, chat_id, title, content, role),
        )
        conn.commit()

    # Redis에 list로 추가
    r = _get_redis()
    key = _redis_key(user_id, chat_id)

    with r.pipeline() as pipe:
        pipe.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
        pipe.ltrim(key, -settings.HISTORY_MAX, -1)
        pipe.expire(key, settings.REDIS_TTL_SECONDS)
        pipe.execute()

