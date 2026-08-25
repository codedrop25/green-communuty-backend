# 기본 비동기 처리 라이브
import asyncio

from app.infrastructure.cache.redis import redis_client
from app.infrastructure.database.session import SessionLocal
from app.modules.posts.post_repository import PostRepository


async def post_like_sync() -> None:
    while True:
        await asyncio.sleep(300)

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
