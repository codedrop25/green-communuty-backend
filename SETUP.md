# SETUP — 처음 받았을 때 해야 할 것

GitHub에서 저장소를 클론한 팀원이 **개발을 시작할 수 있는 상태**까지 가는 문서입니다.
매일의 실행 방법은 [`RUNNING.md`](./RUNNING.md), 설계 근거는 [`PLAN.md`](./PLAN.md),
코딩 규칙은 [`CLAUDE.md`](./CLAUDE.md)에 있습니다.

소요 시간: 처음이면 20~30분 (대부분 도구 설치와 Docker 이미지 내려받기).

---

## 0. 사전 설치

| 도구 | 필요 버전 | 확인 명령 | 비고 |
|---|---|---|---|
| Python | **3.13.x** (3.14 불가) | `python --version` | `pyproject.toml`이 `>=3.13,<3.14`로 고정 |
| Poetry | 2.x | `poetry --version` | 의존성 관리 |
| Docker Desktop | 최신 | `docker compose version` | MySQL·Redis 컨테이너, 통합 테스트에 필수 |
| Git | 최신 | `git --version` | |

### 설치 참고

```powershell
# Windows — winget 사용 시
winget install Python.Python.3.13
winget install Docker.DockerDesktop
winget install Git.Git

# Poetry (Windows PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

```bash
# macOS
brew install python@3.13 git
brew install --cask docker
curl -sSL https://install.python-poetry.org | python3 -
```

> **Python 버전 주의**
> 시스템에 3.12나 3.14가 함께 있으면 Poetry가 엉뚱한 버전을 잡을 수 있습니다.
> `poetry env use 3.13` 으로 명시하세요 (Windows는 `poetry env use py -3.13` 또는 python3.13 실행 파일의 전체 경로).

> **`make`는 필수가 아닙니다.**
> `Makefile`이 있지만 Windows에는 `make`가 기본 설치되어 있지 않습니다.
> 이 문서의 모든 명령은 `make` 없이 실행 가능한 원형으로 적었습니다.
> macOS/Linux나 Git Bash + make 환경이라면 `make install`, `make dev` 등 단축 명령을 써도 됩니다.

---

## 1. 클론

```bash
git clone <저장소 URL> community-backend
cd community-backend
```

---

## 2. 의존성 설치

```bash
poetry install
```

- 가상환경은 `poetry.toml`의 `in-project = true` 설정에 따라 **프로젝트 안 `.venv/`** 에 생성됩니다.
- dev 그룹(pytest, ruff, mypy, pre-commit 등)도 함께 설치됩니다.

---

## 3. `.env` 생성 — **가장 중요한 단계**

`.env`는 커밋되지 않습니다(`.gitignore`). 각자 직접 만들어야 합니다.

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# macOS / Linux / Git Bash
cp .env.example .env
```

### 3-1. 비밀번호 3개를 반드시 채운다

`.env.example`의 아래 3개 항목은 **비어 있고, 채우지 않으면 `docker compose`가 기동을 거부합니다.**
의도된 안전장치입니다.

```dotenv
MYSQL_PASSWORD=
MYSQL_ROOT_PASSWORD=
REDIS_PASSWORD=
```

값은 아래 명령으로 생성해 붙여넣으세요. 3개 모두 **서로 다른 값**으로 만듭니다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> ⚠️ `app`, `root`, `password`, `1234` 같은 값을 절대 쓰지 마세요.
> 자동화 봇이 노출된 DB를 상시 스캔하며, 약한 비밀번호는 몇 분 안에 뚫려
> 데이터베이스가 삭제되고 몸값 요구 테이블만 남습니다.
> 이 프로젝트 개발 중에도 실제로 발생했습니다.

> ⚠️ `docker-compose.yml`의 포트는 `127.0.0.1`에만 바인딩되어 있습니다.
> **이 설정을 풀지 마세요.** `- "3306:3306"` 처럼 바꾸면 DB가 외부 네트워크에 노출됩니다.

### 3-2. `SECRET_KEY`

로컬 개발은 `.env.example`의 기본값 그대로 동작합니다.
단, **32바이트 미만이거나 운영(`ENVIRONMENT=production`)에서 기본값이면 앱이 기동을 거부**합니다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 3-3. 포트가 이미 점유 중이라면

로컬에 MySQL(3306)이나 Redis(6379)가 이미 떠 있으면 `.env`에서 바꾸세요.
compose의 호스트측 매핑과 앱 접속 설정에 함께 반영됩니다.

```dotenv
MYSQL_PORT=3307
REDIS_PORT=6380
```

점유 여부 확인:

```powershell
netstat -ano | Select-String ":3306|:6379"   # Windows
```

```bash
lsof -i :3306 -i :6379                        # macOS / Linux
```

---

## 4. pre-commit 훅 등록

커밋 시점에 ruff(lint·format)와 mypy가 자동으로 돌아갑니다. **반드시 등록하세요.**

```bash
poetry run pre-commit install
```

최초 1회 전체 검사(선택):

```bash
poetry run pre-commit run --all-files
```

---

## 5. 인프라 기동 + 스키마 생성

```bash
# MySQL + Redis 기동
docker compose up -d mysql redis

# 컨테이너가 healthy 가 될 때까지 대기 (최초 실행은 30초 이상 걸립니다)
docker compose ps

# 마이그레이션 적용
poetry run alembic upgrade head

# (선택) 초기 데이터
poetry run python -m scripts.seed
```

시드 계정 (**로컬 전용**):

| 이메일 | 비밀번호 | 역할 |
|---|---|---|
| `admin@example.com` | `password123` | ADMIN |
| `user@example.com` | `password123` | USER |

---

## 6. 동작 확인


```bash
poetry run uvicorn app.main:app --reload
```

- API 문서: <http://localhost:8000/docs>
- 헬스체크: <http://localhost:8000/health/ready> → `{"status":"ok","database":"ok","redis":"ok"}`

여기까지 되면 셋업 완료입니다. 이후 실행은 [`RUNNING.md`](./RUNNING.md)를 보세요.

---

## 7. IDE 설정

### 인터프리터 경로

`.venv`가 프로젝트 안에 생성되므로 아래 경로를 인터프리터로 지정합니다.

```
Windows : .venv\Scripts\python.exe
macOS   : .venv/bin/python
```

- **PyCharm**: Settings → Project → Python Interpreter → Add → Poetry Environment (보통 자동 인식)
- **VS Code**: `Ctrl+Shift+P` → Python: Select Interpreter → `.\.venv\Scripts\python.exe`

### 권장 확장 (VS Code)

- `charliermarsh.ruff` — lint/format을 CLI와 동일한 규칙으로 맞춤
- `ms-python.mypy-type-checker`

포매터는 **ruff 하나로 통일**합니다. black, isort, flake8을 별도로 켜지 마세요 (`pyproject.toml`의 ruff 설정과 충돌합니다).

---

## 8. 개발 워크플로우

```bash
# 1. 최신 코드 반영
git switch main && git pull

# 2. 브랜치 생성
git switch -c feature/작업내용

# 3. 코드 작성 ...

# 4. 커밋 전 검증 (make check 와 동일)
poetry run ruff check app tests alembic scripts
poetry run mypy app
poetry run pytest tests

# 5. 커밋 (pre-commit 훅이 자동 실행됨)
git add .
git commit -m "feat: ..."
git push -u origin feature/작업내용
```

포맷 자동 수정:

```bash
poetry run ruff check app tests alembic scripts --fix
poetry run ruff format app tests alembic scripts
```

---

## 9. `git pull` 후 해야 할 것

팀원이 올린 변경을 받은 뒤에는 아래를 확인하세요. 건너뛰면 "내 로컬만 안 되는" 상황이 생깁니다.

| 바뀐 파일 | 해야 할 일 |
|---|---|
| `poetry.lock` / `pyproject.toml` | `poetry install` |
| `alembic/versions/*` | `poetry run alembic upgrade head` |
| `.env.example` | 새로 추가된 키를 **내 `.env`에도 추가** (누락 시 기동 실패) |
| `docker-compose.yml` / `Dockerfile` | `docker compose up -d --build` |
| `.pre-commit-config.yaml` | `poetry run pre-commit install` 재실행 |

한 번에 확인:

```bash
git pull
poetry install
poetry run alembic upgrade head
```

---

## 10. 팀 규칙 (커밋 전 확인)

### 절대 커밋하지 않는 것

- `.env` — `.gitignore`에 등록되어 있지만 `git add -f`로 우회하지 마세요.
- 실제 비밀번호·토큰·키가 담긴 모든 파일
- `.venv/`, `__pycache__/`, `.mypy_cache/` 등 캐시

새 설정값을 추가했다면 **`.env.example`에도 반드시 추가**합니다 (값은 비워두거나 안전한 기본값으로).

### 모델을 추가·변경했다면

1. `app/infrastructure/database/model_registry.py`에 모델 import 추가
   → **누락하면 Alembic이 테이블을 인식하지 못해 `DROP TABLE` 마이그레이션을 생성합니다.**
2. 마이그레이션 생성 후 **생성된 파일을 직접 열어 검토**

```bash
poetry run alembic revision --autogenerate -m "add user phone"
poetry run alembic upgrade head
poetry run alembic check     # 모델과 마이그레이션이 일치하는지 검사
```

> `alembic.ini`는 **ASCII로만** 작성합니다. Alembic이 이 파일을 로케일 인코딩으로 읽기 때문에
> 한글 주석을 넣으면 한국어 Windows에서 `UnicodeDecodeError`가 납니다.

### 새 도메인을 추가했다면

`app/modules/posts/`를 복제하고 **두 곳**에 등록합니다.

1. `app/infrastructure/database/model_registry.py` — 모델 import
2. `app/api/v1/router.py` — 라우터 include

### 코드 스타일

- Router / Service / Repository 전부 **`def`** 로 작성합니다 (`async def` 아님).
  SQLAlchemy·redis-py의 동기 클라이언트를 쓰기 때문이며, `async def` 안에서 호출하면 이벤트 루프가 블로킹됩니다.
- `commit()`은 **Service에서만** 호출합니다. Repository는 `flush()`까지.
- 관계 조회는 `selectinload()`를 명시합니다 (`lazy="raise"`이므로 빠뜨리면 즉시 예외).
- 환경 변수는 `app.core.config.settings`로만 접근합니다 (`os.environ` 직접 접근은 ruff가 차단).

자세한 내용은 [`CLAUDE.md`](./CLAUDE.md) 5장, 근거는 [`PLAN.md`](./PLAN.md)에 있습니다.

---

## 11. 셋업이 안 될 때

| 증상 | 원인 / 해결 |
|---|---|
| `poetry install`이 Python 버전 오류로 실패 | 3.13이 아님 → `poetry env use 3.13` 후 재시도 |
| `docker compose up`이 `MYSQL_PASSWORD 를 .env 에 설정하세요`로 중단 | 3-1 단계 미완료 → `.env`의 비밀번호 3개를 채울 것 |
| 앱 기동 시 `SECRET_KEY 는 최소 32바이트` | `.env`의 `SECRET_KEY`가 너무 짧음 |
| 앱 기동 시 `THREADPOOL_MAX_WORKERS ... 보다 큽니다` | `THREADPOOL_MAX_WORKERS <= DB_POOL_SIZE + DB_MAX_OVERFLOW` 를 만족하도록 `.env` 수정 |
| 포트 충돌 (`port is already allocated`) | 3-3 단계 참고 → `.env`의 `MYSQL_PORT` / `REDIS_PORT` 변경 |
| 통합 테스트가 컨테이너 오류로 실패 | Docker Desktop이 실행 중인지 확인 |

그 외 실행 관련 오류는 [`RUNNING.md`](./RUNNING.md)의 트러블슈팅 표를 보세요.
