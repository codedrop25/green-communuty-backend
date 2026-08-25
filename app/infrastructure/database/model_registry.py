"""Alembic autogenerate 를 위한 모델 등록 지점.

Alembic 은 `Base.metadata` 와 실제 DB 스키마를 비교해 마이그레이션을 만든다.
그런데 `Base.metadata` 에는 **import 된 적 있는 모델만** 등록된다.

모듈형 구조에서는 각 도메인의 `model.py` 를 아무도 import 하지 않은 채
`alembic revision --autogenerate` 가 실행될 수 있고, 그러면 Alembic 은
"메타데이터에 없는 테이블"로 판단해 **DROP TABLE 마이그레이션을 조용히 생성한다.**

이를 막기 위해 모든 모델을 이 한 곳에서 import 하고,
`alembic/env.py` 는 이 모듈만 import 하면 되도록 한다.

    ※ 새 도메인 모듈을 추가하면 아래에 import 를 반드시 한 줄 추가한다.
      (등록 목적의 side-effect import 이므로 미사용으로 보이는 것이 정상이다)
"""

from app.infrastructure.database.base import Base
from app.modules.menus.menu_model import Menu
from app.modules.comments.comment_model import Comment
from app.modules.posts.posts_image_model import PostImage
from app.modules.posts.posts_like_model import PostLike
from app.modules.posts.posts_model import Post
from app.modules.users.model import User

__all__ = ["Base", "Comment", "Menu", "Post", "User"]
