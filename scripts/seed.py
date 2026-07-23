"""초기 데이터 시딩.

로컬 개발과 데모용이다. 멱등하게 동작하므로 여러 번 실행해도 중복이 생기지 않는다.

    poetry run python -m scripts.seed
"""

from sqlalchemy.orm import Session

from app.core.logging_config import configure_logging, get_logger
from app.core.security import hash_password
from app.infrastructure.database.session import SessionLocal
from app.modules.comments.model import Comment
from app.modules.posts.model import Post
from app.modules.users.model import User, UserRole
from app.modules.users.repository import UserRepository

logger = get_logger(__name__)

ADMIN_EMAIL = "admin@example.com"
USER_EMAIL = "user@example.com"
# 로컬 전용 계정이다. 운영 환경에서는 이 스크립트를 실행하지 않는다.
DEFAULT_PASSWORD = "password123"


def _get_or_create_user(db: Session, email: str, nickname: str, role: UserRole) -> User:
    existing = UserRepository(db).get_by_email(email)
    if existing is not None:
        return existing

    user = User(
        email=email,
        password_hash=hash_password(DEFAULT_PASSWORD),
        nickname=nickname,
        role=role,
    )
    db.add(user)
    db.flush()
    logger.info("seed_user_created", email=email, role=role.value)
    return user


def seed() -> None:
    configure_logging()

    with SessionLocal() as db:
        admin = _get_or_create_user(db, ADMIN_EMAIL, "관리자", UserRole.ADMIN)
        member = _get_or_create_user(db, USER_EMAIL, "일반유저", UserRole.USER)

        # 게시글이 하나도 없을 때만 예시 데이터를 넣는다.
        if db.query(Post).count() == 0:
            post = Post(
                title="환영합니다 🎉",
                content="이 게시글은 시드 스크립트가 생성했습니다.",
                author_id=admin.id,
            )
            db.add(post)
            db.flush()

            db.add(
                Comment(
                    content="첫 댓글입니다.",
                    post_id=post.id,
                    author_id=member.id,
                )
            )
            logger.info("seed_post_created", post_id=post.id)

        db.commit()

    logger.info("seed_completed", admin=ADMIN_EMAIL, user=USER_EMAIL)


if __name__ == "__main__":
    seed()
