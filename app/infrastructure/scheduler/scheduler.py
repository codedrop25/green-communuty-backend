"""post_like_sync.py 의 코드를 5분마다 실행시켜주는 스케줄러"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.modules.posts.post_like_sync import post_like_sync

scheduler = AsyncIOScheduler()


# scheduler 시작 메서드
def start_scheduler() -> None:
    scheduler.add_job(
        post_like_sync, trigger="interval", minutes=5, id="post_like_sync", replace_existing=True
    )
    scheduler.start()


# scheduler 종료 메서드
def shutdown_scheduler() -> None:
    scheduler.shutdown()
