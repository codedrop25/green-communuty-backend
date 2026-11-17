from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.modules.users.user_model import User
from app.modules.users.user_repository import UserRepository
from app.modules.users.user_schemas import UserWithdrawRequest
from app.modules.users.user_withdrawals_model import UserWithdrawal, WithdrawalType


class UserWithdrawalService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = UserRepository(db)

    def withdraw_me(self, user_id: int, payload: UserWithdrawRequest) -> UserWithdrawal:
        """회원 탈퇴 처리.
        users TABLE 의 email, nickname, password_hash 는 NULL 값으로 UPDATE
        user_withdrawals TABLE 에 새로 INSERT"""

        # 1. 기존 users TABLE 에서 조회
        user = self._get_user_id(user_id)
        # exc) 해당 회원이 비활성화 상태라면 오류 출력
        if not user.user_is_active:
            raise AppError("이미 비활성화된 회원입니다.")

        # 1-1. 데이터 보존 기간, 재가입 불가 기간 계산
        retention_until, rejoin_blocked_until = self._calculate_withdrawal_dates(
            WithdrawalType.NORMAL
        )

        # 2. 탈퇴 기록 생성 (기존 회원 정보 사용)
        user_withdrawal = UserWithdrawal(
            user_id=user.user_id,
            user_withdrawal_email=user.user_email,
            user_withdrawal_nickname=user.user_nickname,
            user_role=user.user_role,
            user_withdrawal_type=WithdrawalType.NORMAL,
            user_withdrawal_reason=payload.user_withdrawal_reason,
            retention_until=retention_until,
            rejoin_blocked_until=rejoin_blocked_until,
        )

        try:
            # 3. 기존 users TABLE 정보 변경 (UPDATE)
            user.user_is_active = False
            user.user_email = None
            user.user_nickname = None
            user.user_password_hash = None

            # 4. user_withdrawals TABLE 에 추가 (INSERT)
            self._db.add(user_withdrawal)
            # 5. 두 작업을 하나의 트랜잭션으로 확정
            self._db.commit()
            self._db.refresh(user_withdrawal)

        except Exception as exc:
            self._db.rollback()
            raise AppError("회원 탈퇴 처리 중 오류가 발생했습니다.") from exc

        return user_withdrawal

    def get_withdrawal(self, user_id: int) -> UserWithdrawal:
        """탈퇴 이력 조회."""
        user_withdrawal = self._get_user_withdrawal_id(user_id)
        return user_withdrawal

    # --------------------------------------------------------------- 내부 메서드
    def _get_user_id(self, user_id: int) -> User:
        """회원 조회용 공통 내부 메서드."""
        # DB에서 회원 조회
        user = self._repository.get_by_id(user_id)
        # 해당 회원이 존재하지 않다면 오류 출력
        if user is None:
            raise NotFoundError("회원을 찾을 수 없습니다.")
        return user

    def _get_user_withdrawal_id(self, user_id: int) -> UserWithdrawal:
        """회원 탈퇴이력 조회용 공통 내부 메서드."""
        # DB에서 회원 탈퇴이력 조회
        user_withdrawal = self._repository.get_user_withdrawal(user_id)
        # 해당 회원 탈퇴이력이 존재하지 않다면 오류 출력
        if user_withdrawal is None:
            raise NotFoundError(
                "회원을 찾을 수 없습니다.",
            )
        return user_withdrawal

    def _calculate_withdrawal_dates(
        self,
        withdrawal_type: WithdrawalType,
    ) -> tuple[datetime | None, datetime | None]:
        """탈퇴 유형별 보관 만료일 및 재가입 제한일 계산."""

        now = datetime.now(UTC).replace(tzinfo=None)

        # 탈퇴 기록 보관 기간: 일반 탈퇴 - 5년(임시) / 제재 탈퇴 - 영구
        # datetime.timedelta(): 두 날짜의 차이를 계산하는 함수
        retention_until = (
            now + timedelta(days=365 * 5) if withdrawal_type == WithdrawalType.NORMAL else None
        )
        # 재가입 기간 제한: 일반 탈퇴 - 30일 / 제재 탈퇴 - 영구
        rejoin_blocked_until = (
            now + timedelta(days=30) if withdrawal_type == WithdrawalType.NORMAL else None
        )

        return retention_until, rejoin_blocked_until
