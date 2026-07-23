# community-backend

FastAPI + MySQL + Redis 기반 엔터프라이즈 백엔드 보일러플레이트.

| 문서 | 내용 |
|---|---|
| [`SETUP.md`](./SETUP.md) | **처음 클론했다면 여기부터** — 도구 설치, `.env` 준비, 개발 워크플로우, 팀 규칙 |
| [`RUNNING.md`](./RUNNING.md) | 실행 절차 — 기동/확인/중지, 테스트, 트러블슈팅 |
| [`docs/`](./docs/README.md) | **학습 가이드** — Python·FastAPI를 처음 접하는 사람을 위한 7단계 문서 |
| [`PLAN.md`](./PLAN.md) | 설계 의도와 결정 근거 |
| [`CLAUDE.md`](./CLAUDE.md) | 개발 규칙 |

---

## 기술 스택

| 영역 | 선택 |
|---|---|
| 언어 / 프레임워크 | Python 3.13 + FastAPI |
| 패키지 관리 | Poetry 2.x |
| DB | MySQL 8.0 + SQLAlchemy 2.0 (Sync) + PyMySQL |
| 마이그레이션 | Alembic |
| 캐시 / 세션 | Redis 7 |
| 인증 | JWT (PyJWT) + bcrypt |
| 로깅 | structlog (JSON, request_id, 민감정보 마스킹) |
| 테스트 | pytest + testcontainers |
| 품질 | ruff (lint + format), mypy (strict) |

> `python-jose`와 `passlib`은 **사용하지 않습니다.** 둘 다 유지보수가 중단됐고,
> 특히 `python-jose`는 미패치 CVE를 안고 있습니다. 자세한 근거는 `PLAN.md` 2-1 참고.

---

## 빠른 시작

> ### ⚠️ 먼저 읽어주세요 — DB 비밀번호
>
> `.env`의 `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD` / `REDIS_PASSWORD`는 **비어 있으며,
> 채우지 않으면 `docker compose`가 기동을 거부합니다.** 의도된 동작입니다.
>
> `app`, `root`, `password` 같은 값을 쓰지 마세요. 자동화 봇이 노출된 DB를 상시
> 스캔하며, 약한 비밀번호는 몇 분 안에 뚫려 데이터베이스가 삭제되고 몸값 요구
> 테이블만 남습니다. 이 프로젝트 개발 중에도 실제로 발생했습니다.
>
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(32))"
> ```
>
> compose의 포트는 `127.0.0.1`에만 바인딩되어 있습니다. **이 설정을 풀지 마세요.**

```bash
# 1. 의존성 설치
poetry install

# 2. 환경 변수 준비 (비밀번호 3개를 반드시 채울 것)
cp .env.example .env

# 3. MySQL + Redis 기동
docker compose up -d mysql redis

# 4. 마이그레이션 적용
poetry run alembic upgrade head

# 5. (선택) 초기 데이터
poetry run python -m scripts.seed

# 6. 개발 서버
poetry run uvicorn app.main:app --reload
```

- API 문서: http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health/ready

`make help`로 전체 명령을 볼 수 있습니다 (Windows에서는 Git Bash 또는 WSL 필요).

### 포트가 이미 사용 중이라면

로컬에 MySQL(3306)이나 Redis(6379)가 이미 떠 있으면 `.env`에서 포트를 바꾸세요.
`MYSQL_PORT` / `REDIS_PORT`는 compose의 호스트측 매핑에도 함께 적용됩니다.

```dotenv
MYSQL_PORT=3307
REDIS_PORT=6380
```

---

## 프로젝트 구조

```
app/
├── core/            # [레이어] 설정, 보안, 로깅, 예외, 미들웨어
├── infrastructure/  # [레이어] DB, Redis, S3 연결
├── common/          # [레이어] 모듈 간 공유 (스키마, 페이지네이션, 의존성)
├── modules/         # [기능] 도메인별 수직 슬라이스
│   └── {domain}/    #   router → service → repository → model
└── api/             # 라우터 취합 + 헬스체크
```

새 도메인을 추가하려면 `modules/posts/`를 복제하고 아래 **두 곳**에 등록하면 됩니다.

1. `app/infrastructure/database/model_registry.py` — 모델 import
2. `app/api/v1/router.py` — 라우터 include

---

## 알아둬야 할 설계 결정

### 1. 전부 `def`, `async def`가 아님

SQLAlchemy와 redis-py의 **동기** 클라이언트를 쓰기 때문입니다.
동기 호출을 `async def` 안에서 하면 이벤트 루프가 블로킹되므로,
`def`로 선언해 FastAPI가 threadpool에서 실행하도록 합니다.

이때 **threadpool 크기와 DB 커넥션 수가 맞아야 합니다.**

```
THREADPOOL_MAX_WORKERS <= DB_POOL_SIZE + DB_MAX_OVERFLOW
```

어기면 앱이 기동을 거부합니다. 부하가 걸려야 드러나는 `QueuePool` 타임아웃을
기동 시점 오류로 앞당기기 위한 것입니다.

### 2. `commit()`은 Service가 한다

`get_db` 의존성에서 commit하지 **않습니다.** FastAPI 0.106 이후 `yield` 의존성의
teardown은 **응답 전송 후** 실행되므로, 거기서 commit이 실패하면
클라이언트는 이미 200을 받은 뒤입니다.

- Repository: 쿼리와 `flush()`까지
- Service: `commit()`
- `get_db`: 세션 생성/반납 + 안전망 rollback

### 3. 지연 로딩 금지

모든 관계는 `lazy="raise"`입니다. 연관 데이터가 필요하면 Repository에서
`selectinload()`를 명시해야 하고, 빠뜨리면 조용한 N+1 대신 **즉시 예외**가 납니다.
`tests/integration/test_query_count.py`가 쿼리 수를 단언해 회귀를 막습니다.

### 4. Refresh Token은 1회용

`/auth/refresh`를 호출하면 기존 토큰은 즉시 폐기되고 새 토큰이 발급됩니다(회전).
**이미 회전에 사용된 토큰**이 다시 제출되면 탈취로 간주해 해당 유저의
모든 세션을 무효화합니다.

단, 정상적으로 로그아웃한 토큰의 재제출은 탈취가 아니므로 해당 요청만 거부합니다
(사용자가 뒤로가기를 눌러도 다른 기기가 끊기지 않도록).

Refresh Token은 응답 본문이 아니라 `Path=/api/v1/auth`로 제한된 **HttpOnly 쿠키**로
전달되어, XSS가 발생해도 탈취되지 않고 CSRF 노출면도 좁습니다.

### 5. 인가는 Service에서

라우트 전체를 막을 때는 `require_role(UserRole.ADMIN)`,
"내 글만 수정"처럼 데이터를 봐야 하는 검증은 **Service**에서 합니다.
Router에만 두면 다른 호출 경로에서 우회되기 때문입니다.

---

## 테스트

```bash
make test-unit          # 순수 로직만, 컨테이너 불필요 (~2초)
make test-integration   # 실제 MySQL/Redis 컨테이너 (~30초, Docker 필요)
make test               # 전체
```

- 통합 테스트가 주력입니다. Repository를 mock한 Service 테스트는
  SQL·FK·트랜잭션 오류를 mock 뒤에 가려 실제 버그를 잡지 못하므로 만들지 않습니다.
- 컨테이너는 **세션당 1회**만 뜨고, 테스트 격리는 트랜잭션 롤백으로 합니다.
- SQLite로 대체하지 않습니다. 타입/FK 동작이 달라 "테스트는 통과하는데 운영에서
  깨지는" 상황을 만들기 때문입니다.

---

## 마이그레이션

```bash
make migration m="add user phone"   # 생성 (모델 변경 후)
make migrate                        # 적용
make downgrade                      # 1단계 되돌리기
make check-migration                # 모델과 마이그레이션 일치 검사
```

- 새 모델은 **반드시** `model_registry.py`에 import를 추가하세요.
  누락하면 Alembic이 테이블을 인식하지 못해 `DROP TABLE`을 생성합니다.
- `alembic.ini`는 **ASCII로만** 작성합니다. Alembic이 이 파일을 로케일 인코딩으로
  읽기 때문에, 한글 주석을 넣으면 한국어 Windows에서 `UnicodeDecodeError`가 납니다.

---

## 운영 배포 시 확인 사항

| 항목 | 내용 |
|---|---|
| `SECRET_KEY` | 반드시 교체. 32바이트 미만이거나 기본값이면 기동 거부 |
| `ENVIRONMENT=production` | API 문서(`/docs`, `/openapi.json`) 자동 비활성화 |
| 마이그레이션 | **자동 실행되지 않습니다.** 배포 파이프라인의 별도 job에서 `alembic upgrade head` 실행 |
| `COOKIE_SECURE=true` | HTTPS 환경 필수 |
| 프론트 도메인 분리 시 | `COOKIE_SAMESITE=none` + `CORS_ORIGINS` 설정 (`Secure` 동반 필수) |
| 리버스 프록시 | `--proxy-headers` + `FORWARDED_ALLOW_IPS`를 신뢰할 수 있는 IP로 제한 |

`ENVIRONMENT`가 `local`/`dev`일 때만 컨테이너 진입 시 마이그레이션이 자동 적용됩니다.
운영에서 다중 인스턴스가 동시에 롤아웃되면 마이그레이션이 병렬 실행되기 때문입니다.

---

## 범위에 포함되지 않은 것

이메일 인증, 소셜 로그인, 범용 Rate Limiting, 파일 업로드 API,
Celery 작업 큐, CI/CD 파이프라인.

`app/infrastructure/storage/s3.py`는 클라이언트 스텁까지만 제공합니다.
