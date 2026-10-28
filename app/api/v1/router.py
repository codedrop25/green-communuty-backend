"""v1 API 라우터 취합.

각 모듈은 자신의 `router` 만 노출하고, 버전 prefix 부여는 이 파일이 담당한다.
덕분에 v2 를 추가할 때 모듈 코드를 건드리지 않고 이 계층만 추가하면 된다.

    ※ 새 도메인 모듈을 추가하면 여기에 `include_router` 를 한 줄 추가한다.
"""

from fastapi import APIRouter, Depends

from app.common.dependencies import get_current_user
from app.modules.auth.router import router as auth_router
from app.modules.comments.comment_router import router as comments_router
from app.modules.menus.menu_router import router as menus_router
from app.modules.posts.post_router import router as posts_router
from app.modules.users.user_router import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router)

# 인증 진입점을 제외한 모든 서비스 API는 로그인한 사용자만 이용한다.
protected_router = APIRouter(dependencies=[Depends(get_current_user)])
protected_router.include_router(users_router)
protected_router.include_router(posts_router)
protected_router.include_router(comments_router)
protected_router.include_router(menus_router)
api_router.include_router(protected_router)
