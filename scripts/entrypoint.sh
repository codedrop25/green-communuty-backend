#!/bin/sh
# 컨테이너 진입점.
#
# PLAN.md 8-3: 마이그레이션 자동 실행은 local/dev 에서만 수행한다.
#
# 운영에서 여러 인스턴스가 동시에 롤아웃되면 `alembic upgrade` 가 병렬로 실행되어
# 락 경합과 중복 적용 위험이 있다. 운영은 배포 파이프라인의 별도 job 으로 분리한다.
#
#   예) kubectl 사용 시: initContainer 가 아니라 Job 으로 마이그레이션을 먼저 실행

set -eu

ENVIRONMENT="${ENVIRONMENT:-local}"

case "$ENVIRONMENT" in
    local | dev)
        echo "[entrypoint] ENVIRONMENT=${ENVIRONMENT} — 마이그레이션을 적용합니다."
        alembic upgrade head
        ;;
    *)
        echo "[entrypoint] ENVIRONMENT=${ENVIRONMENT} — 마이그레이션을 건너뜁니다."
        echo "[entrypoint] 운영 배포에서는 별도 job 으로 'alembic upgrade head' 를 먼저 실행하세요."
        ;;
esac

# exec 로 교체해 uvicorn 이 PID 1 이 되게 한다.
# 그래야 docker stop 의 SIGTERM 이 uvicorn 에 직접 전달되어 graceful shutdown 이 동작한다.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
