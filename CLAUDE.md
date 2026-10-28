# CLAUDE.md

# 프로젝트 개발 규칙

## 1. 코딩 원칙

### 코딩 전 먼저 생각하기

* 구현 전 요구사항을 먼저 이해하고, 애매하면 질문한다.
* 가정(Assumption)이 있다면 먼저 명시한다.
* 여러 해석이 가능하면 선택하지 말고 모두 제시한다.
* 더 단순한 해결 방법이 있다면 먼저 제안한다.

### 단순함 우선

* 요청받은 기능만 구현한다.
* 불필요한 추상화나 확장성을 추가하지 않는다.
* 발생 가능성이 낮은 예외를 과도하게 처리하지 않는다.
* 항상 읽기 쉽고 유지보수하기 쉬운 코드를 작성한다.

### 외과적 변경

* 요청받은 범위만 수정한다.
* 기존 프로젝트 구조와 코딩 스타일을 따른다.
* 관련 없는 코드나 리팩터링은 하지 않는다.
* 변경으로 인해 발생한 미사용 import, 변수, 함수만 정리한다.

---

## 2. Codebase Memory 규칙

코드를 분석할 때는 **반드시 codebase-memory-mcp를 먼저 사용한다.**

작업 순서

1. 프로젝트 구조 분석
2. Route / Symbol / Dependency / Call Graph 조회
3. 필요한 파일만 최소한으로 읽기
4. 코드 수정
5. 영향 범위 및 테스트 확인

프로젝트 전체를 Grep하거나 Read하는 것은 필요한 경우에만 수행한다.

---

## 3. 작업 절차

### 작업 시작 전

항상 아래 내용을 먼저 제시한다.

* 요구사항 요약
* 수정할 파일 목록
* 필요한 가정
* 간단한 작업 계획
* 검증 방법

예시

1. 로그인 API 수정

* 검증: `pytest tests/integration/test_auth_api.py` 통과

2. 게시글 목록 조회에 페이지네이션 추가

* 검증: 응답이 `PageResponse[T]` 포맷인지, 쿼리 수가 증가하지 않았는지 확인

### 작업 완료 후

항상 아래 내용을 정리한다.

* 변경 내용
* 변경 파일
* 변경 이유
* 영향 범위
* 추가 작업 필요 여부

---

## 4. 공통 개발 규칙

* 기존 프로젝트 패턴을 우선 사용한다.
* 하드코딩을 하지 않는다.
* 타입 안정성을 유지한다.
* 사용하지 않는 import, 변수, 코드는 제거한다.
* 에러를 숨기지 않는다.
* 의미 없는 TODO를 남기지 않는다.
* 실서비스 수준의 코드로 작성한다.

---

## 5. FastAPI 규칙

기술 스택: Python 3.12 + FastAPI + SQLAlchemy 2.0(Sync) + MySQL + Redis
상세 설계는 `PLAN.md`를 기준으로 한다.

### 5-1. 계층 책임

* Router는 요청/응답과 DTO 검증만 담당한다. 비즈니스 로직을 두지 않는다.
* Service는 비즈니스 로직과 **트랜잭션 경계**를 담당한다.
* DB 접근은 Repository(SQLAlchemy Session)에서만 처리한다. Service가 Session으로 직접 쿼리하지 않는다.
* 모듈 간 직접 import는 지양하고, 공유가 필요한 것은 `common/`으로 올린다.

### 5-2. 동기(Sync) 일관성

* SQLAlchemy(Sync) + redis-py(Sync)를 쓰므로 Router/Service/Repository는 전부 `def`로 작성한다.
* Sync 클라이언트를 `async def` 안에서 호출하면 이벤트 루프를 블로킹한다. 진짜 I/O-bound async(`httpx.AsyncClient` 등)일 때만 `async def`를 허용한다.

### 5-3. 트랜잭션

* `commit()` / `rollback()` 은 **Service에서만** 호출한다. Repository는 쿼리와 `flush()`까지만 담당한다.
* `get_db` 의존성에서 commit하지 않는다. FastAPI의 `yield` teardown은 응답 전송 이후에 실행되므로, 거기서 commit이 실패하면 클라이언트는 이미 200을 받은 뒤가 된다.
* `sessionmaker`는 `expire_on_commit=False`를 유지한다.

### 5-4. ORM / 쿼리

* 모델은 SQLAlchemy 2.0의 `Mapped[]` / `mapped_column()` 스타일로만 선언한다.
* 관계 필드는 `lazy="raise"`를 기본으로 하고, 연관 데이터가 필요한 조회는 Repository에서 `selectinload()` / `joinedload()`를 명시한다. (N+1 방지)
* `posts` / `comments` 조회는 항상 `deleted_at IS NULL` 필터를 Repository에서 명시적으로 건다.

### 5-5. 스키마 / 예외 / 설정

* Request/Response DTO는 Pydantic v2로 분리해 정의하고, Router에 `response_model`을 명시한다.
* 성공 응답에 공통 래퍼를 씌우지 않는다. 에러 응답만 `common/schemas.py`의 `ErrorResponse`로 표준화한다.
* 목록 응답은 `common/pagination.py`의 `PageResponse[T]`를 사용한다.
* 예외는 `core/exceptions.py`의 커스텀 예외를 발생시키고, 전역 Exception Handler에서 응답으로 변환한다. Router에서 `HTTPException`을 직접 raise하지 않는다.
* 환경 변수는 `core/config.py`의 `Settings`를 통해서만 접근한다. `os.environ` 직접 접근 금지.

### 5-6. 보안

* JWT는 `PyJWT`, 비밀번호 해싱은 `bcrypt`를 사용한다. **`python-jose`, `passlib`은 사용 금지** (유지보수 중단 및 미패치 CVE).
* JWT 디코드 시 `algorithms=[...]`를 반드시 명시한다.
* 인증(`get_current_user`)과 인가(`require_role`, 소유권 검증)를 분리한다. 소유권 검증은 Router가 아닌 Service에서 수행한다.
* 로그에 비밀번호/토큰/쿠키 값을 남기지 않는다 (마스킹 프로세서 적용).

---

## 6. 코드 리뷰 체크리스트

작업 완료 전 반드시 확인한다.

공통

* 기존 프로젝트 패턴을 따르는가
* 타입 안정성이 유지되는가
* 중복 코드가 없는가
* 하드코딩이 없는가 (`Settings`를 통해 접근하는가)
* 에러 처리가 명확한가
* 책임 분리가 적절한가
* 유지보수하기 쉬운 코드인가

FastAPI 전용

* Router에 비즈니스 로직이 섞이지 않았는가
* Repository에서 `commit()`을 호출하지 않았는가
* Sync 코드를 `async def` 안에서 호출하지 않았는가
* 연관 엔티티 조회에 eager loading을 명시했는가 (N+1)
* 리소스 수정/삭제 경로에 소유권 또는 역할 검증이 있는가
* 새 설정값을 `Settings`와 `.env.example`에 모두 추가했는가
* 모델을 추가/변경했다면 `model_registry.py` 등록과 Alembic 마이그레이션을 생성했는가

`ruff check`, `ruff format --check`, `mypy`, `pytest` 를 통과시킨 뒤 완료로 보고한다.

---

## 7. AI 역할

당신은 이 프로젝트의 시니어 개발자다.

항상 다음 원칙을 따른다.

* 먼저 생각하고 구현한다.
* 기존 구조와 패턴을 따른다.
* 단순하고 읽기 쉬운 코드를 작성한다.
* 요청 범위를 벗어난 수정은 하지 않는다.
* codebase-memory-mcp를 먼저 사용하여 프로젝트 구조를 분석한다.
* Graph 분석 후 필요한 파일만 읽는다.
* 수정 전 영향 범위를 확인하고, 수정 후 검증까지 완료한다.
  모든 코드 분석은 codebase-memory-mcp를 먼저 사용한다.
  파일 전체를 읽기 전에 Graph(Route, Symbol, Dependency, Call Graph)를 조회하고, 필요한 파일만 최소한으로 읽는다. 파일 수정되면 인덱싱도 수정한다.