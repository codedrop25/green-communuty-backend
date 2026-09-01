"""5분마다 반복하며 redis data 를 DB 와 동기화."""

from app.infrastructure.cache.redis import redis_client
from app.infrastructure.database.session import SessionLocal
from app.modules.posts.post_repository import PostRepository


async def post_like_sync() -> None:
    # HTTP 요청이 없으므로 직접 DB 세션 생성
    db = SessionLocal()

    # * redis_client : redis 접속 객체, redis.py 에서 작성
    try:
        repository = PostRepository(db=db, redis=redis_client)
        repository.scan_like_to_db()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
