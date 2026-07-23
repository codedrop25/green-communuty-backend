# RUNNING — 실행 절차

프로젝트를 로컬에서 실행하고 확인·중지하는 절차입니다.

**처음 클론했다면 [`SETUP.md`](./SETUP.md)를 먼저 완료하세요.** 이 문서는
`poetry install`과 `.env` 준비가 끝난 상태를 전제로 합니다.

---

## 실행 방식 두 가지

| 방식 | 설명 | 언제 쓰나 |
|---|---|---|
| **A. 로컬 실행** (권장) | MySQL·Redis만 컨테이너, 앱은 호스트에서 `uvicorn --reload` | 평소 개발. 코드 저장 시 즉시 반영 |
| **B. 전체 컨테이너** | 앱까지 컨테이너로 기동 | 배포 형태 확인, Dockerfile 검증 |

---

## A. 로컬 실행 (평소 개발)

### 1. Docker Desktop 실행 확인

```bash
docker info
```

에러가 나면 Docker Desktop을 먼저 켜세요.

### 2. MySQL + Redis 기동

```bash
docker compose up -d mysql redis
```

상태 확인 — 두 컨테이너가 모두 `healthy`여야 합니다. 최초 실행은 MySQL 초기화에 30초 이상 걸립니다.

```bash
docker compose ps
```

```
NAME              STATUS
community-mysql   Up 40 seconds (healthy)
community-redis   Up 40 seconds (healthy)
```

### 3. 마이그레이션 적용

```bash
poetry run alembic upgrade head
```

이미 최신이면 아무 것도 출력되지 않습니다. 현재 리비전 확인:

```bash
poetry run alembic current
```

### 4. (선택) 초기 데이터 시딩

```bash
poetry run python -m scripts.seed
```

멱등하게 동작하므로 여러 번 실행해도 중복이 생기지 않습니다.

| 이메일 | 비밀번호 | 역할 |
|---|---|---|
| `admin@example.com` | `password123` | ADMIN |
| `user@example.com` | `password123` | USER |

> 로컬·데모 전용 계정입니다. 운영 환경에서는 이 스크립트를 실행하지 않습니다.

### 5. 개발 서버 기동

```bash
poetry run uvicorn app.main:app --reload
```

포트를 바꾸려면:

```bash
poetry run uvicorn app.main:app --reload --port 8001
```

정상 기동 시 로그(JSON) 마지막에 `Application startup complete.` 가 나옵니다.
`Ctrl+C`로 중지합니다.

---

## B. 전체 컨테이너 실행

```bash
docker compose up -d --build
```

- 앱 포트는 `.env`의 `APP_PORT`(기본 `8000`)를 따릅니다.
- 컨테이너 안에서는 `MYSQL_HOST=mysql`, `REDIS_HOST=redis`로 자동 덮어써지므로
  로컬 실행과 **같은 `.env`를 공유**할 수 있습니다.
- `ENVIRONMENT`가 `local` / `dev`일 때만 진입 시 `alembic upgrade head`가 자동 실행됩니다
  (`scripts/entrypoint.sh`). 그 외 환경에서는 건너뛰므로 배포 파이프라인의 별도 job에서 실행해야 합니다.

로그 확인:

```bash
docker compose logs -f app
```

코드를 고쳤다면 이미지를 다시 빌드해야 반영됩니다.

```bash
docker compose up -d --build app
```

---

## 실행 확인

### 헬스체크

```bash
curl http://localhost:8000/health/live     # 프로세스 생존
curl http://localhost:8000/health/ready    # DB/Redis 연결까지 확인
```

`/health/ready` 정상 응답:

```json
{"status":"ok","database":"ok","redis":"ok"}
```

`database` 또는 `redis`가 `error`면 **503**이 반환됩니다. 아래 트러블슈팅을 보세요.

### API 문서

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

> `ENVIRONMENT=production`이면 문서가 자동 비활성화됩니다.

### 로그인까지 확인 (시딩 후)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@example.com\",\"password\":\"password123\"}"
```

```powershell
# Windows PowerShell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login `
  -ContentType 'application/json' `
  -Body '{"email":"admin@example.com","password":"password123"}'
```

`access_token`이 반환되면 정상입니다.
Refresh Token은 응답 본문이 아니라 `Path=/api/v1/auth`로 제한된 **HttpOnly 쿠키**로 전달됩니다.

주요 엔드포인트:

| 그룹 | 경로 |
|---|---|
| 인증 | `POST /api/v1/auth/signup` · `login` · `refresh` · `logout` |
| 유저 | `GET/PATCH /api/v1/users/me`, `GET /api/v1/users` (ADMIN) |
| 게시글 | `GET/POST /api/v1/posts`, `GET/PATCH/DELETE /api/v1/posts/{id}` |
| 댓글 | `/api/v1/posts/{post_id}/comments` |

---

## 중지 · 재시작 · 초기화

```bash
# 앱만 중지 : uvicorn 터미널에서 Ctrl+C

# 컨테이너 중지 (데이터 유지)
docker compose down

# 컨테이너 재시작
docker compose restart mysql redis

# ⚠️ 컨테이너 중지 + 볼륨 삭제 (DB 데이터 전부 삭제)
docker compose down -v
```

`down -v` 이후에는 마이그레이션과 시딩을 다시 해야 합니다.

```bash
docker compose up -d mysql redis
poetry run alembic upgrade head
poetry run python -m scripts.seed
```

---

## 테스트 실행

```bash
poetry run pytest tests/unit          # 순수 로직, 컨테이너 불필요 (~2초)
poetry run pytest tests/integration   # 실제 MySQL/Redis 컨테이너 (~30초, Docker 필요)
poetry run pytest tests               # 전체
```

- 통합 테스트는 **testcontainers**가 별도 컨테이너를 띄웁니다. `docker compose`로 띄운 것과는 무관하며,
  Docker Desktop이 실행 중이어야 합니다.
- 컨테이너는 세션당 1회만 뜨고, 테스트 격리는 트랜잭션 롤백으로 합니다.

---

## 코드 품질 검사

```bash
poetry run ruff check app tests alembic scripts    # 린트
poetry run ruff format --check app tests           # 포맷 검사
poetry run mypy app                                # 타입 검사 (strict)
```

자동 수정:

```bash
poetry run ruff check app tests alembic scripts --fix
poetry run ruff format app tests alembic scripts
```

---

## 마이그레이션 명령

```bash
poetry run alembic upgrade head                        # 적용
poetry run alembic revision --autogenerate -m "설명"   # 생성 (모델 변경 후)
poetry run alembic downgrade -1                        # 1단계 되돌리기
poetry run alembic current                             # 현재 리비전
poetry run alembic history                             # 이력
poetry run alembic check                               # 모델과 마이그레이션 일치 검사
```

새 모델은 반드시 `app/infrastructure/database/model_registry.py`에 import를 추가하세요.
누락하면 Alembic이 테이블을 인식하지 못해 `DROP TABLE`을 생성합니다.

---

## `make` 단축 명령 (macOS / Linux / make 설치 환경)

| 명령 | 내용 |
|---|---|
| `make help` | 전체 명령 목록 |
| `make up` | MySQL + Redis 기동 |
| `make dev` | 개발 서버 |
| `make migrate` | 마이그레이션 적용 |
| `make seed` | 초기 데이터 |
| `make test` | 전체 테스트 |
| `make check` | lint + typecheck + test |
| `make down` / `make down-v` | 중지 / 중지 + 볼륨 삭제 |

Windows에는 `make`가 기본 설치되어 있지 않습니다. 위 원형 명령을 그대로 쓰면 됩니다.

---

## 트러블슈팅

### 기동 자체가 안 될 때

| 메시지 | 원인 / 해결 |
|---|---|
| `MYSQL_PASSWORD 를 .env 에 설정하세요` | `.env`의 `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD` / `REDIS_PASSWORD`가 비어 있음. [`SETUP.md`](./SETUP.md) 3-1 참고 |
| `SECRET_KEY 는 최소 32바이트 이상이어야 합니다` | `.env`의 `SECRET_KEY`가 짧음. `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `THREADPOOL_MAX_WORKERS(...) 가 DB 커넥션 총량(...) 보다 큽니다` | `THREADPOOL_MAX_WORKERS <= DB_POOL_SIZE + DB_MAX_OVERFLOW` 가 되도록 `.env` 수정 |
| `COOKIE_SAMESITE=none 은 COOKIE_SECURE=true 를 함께` | 두 값을 짝으로 맞출 것. 로컬은 `lax` + `false` |
| `ValidationError` (그 외 필드) | `.env.example`에 새로 추가된 키가 내 `.env`에 없을 수 있음. 두 파일을 비교할 것 |
| `port is already allocated` | 3306/6379가 이미 점유됨. `.env`의 `MYSQL_PORT` / `REDIS_PORT`를 3307 / 6380 등으로 변경 후 `docker compose up -d` 재실행 |
| `Cannot connect to the Docker daemon` | Docker Desktop이 꺼져 있음 |

### 기동 후 동작이 이상할 때

| 증상 | 원인 / 해결 |
|---|---|
| `/health/ready`가 `database: error` | ① MySQL 컨테이너가 아직 `healthy`가 아님 → `docker compose ps` 확인 ② `.env`의 `MYSQL_PORT`와 compose 매핑이 어긋남 ③ 비밀번호 변경 후 기존 볼륨이 남아 있음 → `docker compose down -v` 후 재기동 |
| `/health/ready`가 `redis: error` | `REDIS_PASSWORD`가 컨테이너 기동 시점 값과 다름 → `docker compose down -v` 후 재기동 |
| `Table 'community.users' doesn't exist` | 마이그레이션 미적용 → `poetry run alembic upgrade head` |
| `Access denied for user 'app'` | `.env`의 비밀번호를 바꿨는데 MySQL 볼륨에 옛 비밀번호가 남아 있음. **볼륨 초기화가 필요합니다** → `docker compose down -v` |
| `sqlalchemy.exc.InvalidRequestError: 'Post.comments' is not available due to lazy='raise'` | 의도된 동작. Repository 조회에 `selectinload()`를 명시해야 합니다 (N+1 방지) |
| `TimeoutError: QueuePool limit ... reached` | 커넥션 풀 고갈. `.env`의 `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` 확인 |
| `UnicodeDecodeError` (alembic 실행 시) | `alembic.ini`에 비ASCII 문자가 들어감. ASCII로만 작성해야 합니다 |
| 코드를 고쳐도 반영되지 않음 | 방식 B(전체 컨테이너)로 실행 중임 → `docker compose up -d --build app`, 또는 방식 A로 전환 |
| curl로 **한글·이모지가 든 JSON**을 보내면 `400 BAD_REQUEST` / `There was an error parsing the body` | 서버 문제가 아니라 셸(특히 Git Bash)이 `-d '{"title":"한글"}'`의 멀티바이트를 깨뜨리는 것. 본문을 파일로 저장해 `--data-binary @body.json`으로 보내거나, `/docs`·PowerShell `Invoke-RestMethod`를 사용할 것 |

### 상태 점검 명령

```bash
docker compose ps                    # 컨테이너 상태
docker compose logs mysql            # MySQL 로그
docker compose logs redis            # Redis 로그
docker compose logs -f app           # 앱 로그 (방식 B)
poetry run alembic current           # 적용된 마이그레이션
curl http://localhost:8000/health/ready
```

DB에 직접 접속해 확인:

```bash
docker compose exec mysql mysql -u app -p community
# 비밀번호는 .env 의 MYSQL_PASSWORD
```

---

## 운영 배포 시 추가 확인

로컬 실행과 다른 점만 정리합니다. 자세한 내용은 [`README.md`](./README.md)를 보세요.

| 항목 | 내용 |
|---|---|
| `SECRET_KEY` | 반드시 교체. 기본값이면 기동 거부 |
| `ENVIRONMENT=production` | `/docs`, `/openapi.json` 자동 비활성화 |
| 마이그레이션 | **자동 실행되지 않습니다.** 배포 파이프라인의 별도 job에서 `alembic upgrade head` 실행 |
| `COOKIE_SECURE=true` | HTTPS 환경 필수 |
| 프론트 도메인 분리 | `COOKIE_SAMESITE=none` + `CORS_ORIGINS` 설정 (`Secure` 동반 필수) |
| 리버스 프록시 | `--proxy-headers` + `FORWARDED_ALLOW_IPS`를 신뢰 가능한 IP로 제한 |
