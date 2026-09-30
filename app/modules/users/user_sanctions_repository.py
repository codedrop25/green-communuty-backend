"""사용자 제재 이력 Repository."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.users.user_sanctions_model import UserSanction


class UserSanctionRepository:
    """사용자 제재 이력의 저장과 조회를 담당한다."""

    def __init__(self, db: Session) -> None:
        """DB 세션을 Repository 내부에 저장한다."""
        self._db = db

    # ----------------------------------------------------------------------------------

    def add_user_sanction(
        self,
        reported_user_id: int,
        user_sanction_type: str,
        user_sanction_reason: str,
        report_id: int,
        expires_at: datetime | None,
    ) -> UserSanction:
        """사용자 제재 이력을 저장한다."""

        # 전달받은 정보로 사용자 제재 객체를 생성한다.
        user_sanction = UserSanction(
            reported_user_id=reported_user_id,
            user_sanction_type=user_sanction_type,
            user_sanction_reason=user_sanction_reason,
            report_id=report_id,
            expires_at=expires_at,
        )

        # 생성한 제재 객체를 DB 저장 대상으로 등록한다.
        self._db.add(user_sanction)

        # INSERT 쿼리를 실행해 user_sanction_id를 발급받는다.
        # 아직 commit은 하지 않는다.
        self._db.flush()

        # DB에 저장된 최신 값을 객체에 다시 불러온다.
        self._db.refresh(user_sanction)

        # 저장된 제재 객체를 Service로 반환한다.
        return user_sanction
