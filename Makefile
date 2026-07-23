.DEFAULT_GOAL := help
.PHONY: help install dev up down logs migrate migration downgrade seed \
        lint format typecheck test test-unit test-integration check clean

help: ## 사용 가능한 명령 목록
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- 셋업
install: ## 의존성 설치 + pre-commit 훅 등록
	poetry install
	poetry run pre-commit install

# ---------------------------------------------------------------- 실행
dev: ## 로컬 개발 서버 (자동 리로드)
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

up: ## MySQL + Redis 만 기동 (앱은 로컬에서 실행)
	docker compose up -d mysql redis

up-all: ## 앱까지 포함해 전체 기동
	docker compose up -d --build

down: ## 컨테이너 중지 (데이터는 유지)
	docker compose down

down-v: ## 컨테이너 중지 + 볼륨 삭제 (데이터 전부 삭제됨)
	docker compose down -v

logs: ## 앱 로그 추적
	docker compose logs -f app

# ---------------------------------------------------------------- DB
migrate: ## 마이그레이션 적용
	poetry run alembic upgrade head

migration: ## 마이그레이션 생성  예) make migration m="add user phone"
	poetry run alembic revision --autogenerate -m "$(m)"

downgrade: ## 마이그레이션 1단계 되돌리기
	poetry run alembic downgrade -1

check-migration: ## 모델과 마이그레이션이 일치하는지 검사 (CI 용)
	poetry run alembic check

seed: ## 초기 데이터 시딩
	poetry run python -m scripts.seed

# ---------------------------------------------------------------- 품질
lint: ## 린트 검사
	poetry run ruff check app tests alembic scripts

format: ## 코드 포맷팅 + 자동 수정
	poetry run ruff check app tests alembic scripts --fix
	poetry run ruff format app tests alembic scripts

typecheck: ## 타입 검사
	poetry run mypy app

test: ## 전체 테스트
	poetry run pytest tests

test-unit: ## 단위 테스트만 (컨테이너 불필요, 빠름)
	poetry run pytest tests/unit

test-integration: ## 통합 테스트만 (Docker 필요)
	poetry run pytest tests/integration

check: lint typecheck test ## 커밋 전 전체 검증

# ---------------------------------------------------------------- 정리
clean: ## 캐시 파일 삭제
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
