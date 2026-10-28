"""N+1 회귀 방지 (PLAN.md 3-5, 10-3).

"댓글이 늘어나도 쿼리 수가 늘지 않는다"를 숫자로 고정한다.
이 테스트가 없으면 누군가 `selectinload` 를 지워도 기능 테스트는 그대로 통과한다.
"""

from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event

from tests.integration.conftest import API

pytestmark = pytest.mark.integration


@contextmanager
def count_queries(engine: Engine) -> Iterator[list[str]]:
    """블록 안에서 실행된 SELECT 문을 수집한다."""
    statements: list[str] = []

    def _before_execute(
        _conn: Any, _cursor: Any, statement: str, *_args: Any, **_kwargs: Any
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _before_execute)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _before_execute)


@pytest.fixture
def post_with_comments(client: TestClient, signup: Callable[..., dict[str, str]]) -> Generator[int]:
    """댓글 5개가 달린 게시글."""
    headers = signup("nplus1@example.com", "작성자")
    post_id = client.post(
        f"{API}/posts", headers=headers, json={"post_title": "N+1", "post_content": "본문"}
    ).json()["post_id"]

    for i in range(5):
        client.post(
            f"{API}/posts/{post_id}/comments",
            headers=headers,
            json={"comment_content": f"댓글 {i}"},
        )

    yield int(post_id)


def test_comment_list_query_count_is_constant(
    client: TestClient,
    engine: Engine,
    post_with_comments: int,
    signup: Callable[..., dict[str, str]],
) -> None:
    """댓글 페이지는 댓글 수와 무관하게 고정된 SELECT만 쓴다."""
    headers = signup("comment-reader@example.com", "독자")
    with count_queries(engine) as statements:
        response = client.get(f"{API}/posts/{post_with_comments}/comments", headers=headers)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 5
    assert len(statements) <= 5, f"쿼리가 {len(statements)}개 실행됨 — N+1 가능성:\n" + "\n".join(
        statements
    )


def test_post_list_query_count_is_constant(
    client: TestClient, engine: Engine, signup: Callable[..., dict[str, str]]
) -> None:
    """목록 조회도 게시글 수와 무관해야 한다.

    기대: 사용자 인증 + 공지 + COUNT + 작성자가 JOIN된 게시글 목록
    """
    headers = signup("listcount@example.com", "작성자")
    for i in range(5):
        client.post(
            f"{API}/posts", headers=headers, json={"post_title": f"글 {i}", "post_content": "본문"}
        )

    with count_queries(engine) as statements:
        response = client.get(f"{API}/posts", headers=headers, params={"page": 1, "size": 10})

    assert response.status_code == 200
    assert len(response.json()["items"]) >= 5
    assert len(statements) <= 5, f"쿼리가 {len(statements)}개 실행됨 — N+1 가능성:\n" + "\n".join(
        statements
    )
