# =============================================================================
# 멀티스테이지 빌드 (PLAN.md 8-4)
#   builder : Poetry 로 의존성만 설치. 컴파일러/빌드 툴체인이 여기에만 남는다.
#   runtime : 가상환경과 앱 코드만 복사. 이미지가 작아지고 공격면이 줄어든다.
# =============================================================================

# ------------------------------------------------------------------ builder
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=2.4.1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

WORKDIR /app

# bcrypt / cryptography 등 네이티브 확장 빌드에 필요한 최소 도구.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

# 의존성 파일만 먼저 복사한다.
# 소스가 바뀌어도 의존성이 그대로면 이 레이어가 캐시되어 빌드가 빨라진다.
COPY pyproject.toml poetry.lock ./

# --no-root: 이 프로젝트는 package-mode=false 인 애플리케이션이다.
# --only main: 개발 의존성(pytest, ruff 등)은 런타임 이미지에 넣지 않는다.
RUN poetry install --only main --no-root

# ------------------------------------------------------------------ runtime
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 헬스체크와 entrypoint 대기 로직에 필요한 최소 패키지.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 루트로 실행하면 컨테이너 침해 시 피해 범위가 커진다. 전용 계정을 만든다.
RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app app ./app

RUN chmod +x scripts/entrypoint.sh

USER app

EXPOSE 8000

# liveness 엔드포인트를 사용한다 (DB/Redis 상태와 무관해야 재시작 루프에 빠지지 않는다).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health/live || exit 1

ENTRYPOINT ["./scripts/entrypoint.sh"]
