import asyncio
from copy import deepcopy

import httpx
import pytest
from fastapi.responses import PlainTextResponse

from orders import demo
from orders.contract import Case, evaluate, expected
from orders.demo import run
from orders.service import create_service


@pytest.fixture(scope="module")
def report():
    return asyncio.run(run())


def test_protected_matrix(report):
    assert len(report["protected_app"]) == 16
    assert all(row["passed"] for row in report["protected_app"])
    assert sum(row["observed"]["status"] == 200 for row in report["protected_app"]) == 6


def test_status_alone_misses_both_modeled_failures(report):
    rows = [row for row in report["modeled_baseline"] if not row["passed"]]
    assert [row["mismatches"] for row in rows] == [["body"], ["state"]]
    assert all(row["expected"]["status"] == row["observed"]["status"] for row in rows)


def test_text_responses_and_app_errors_remain_in_evidence(monkeypatch):
    def unavailable_service(tokens):
        app = create_service(tokens)

        @app.middleware("http")
        async def simulate_outage(request, call_next):
            if request.url.path == "/orders/A1":
                return PlainTextResponse("x" * 600, status_code=503)
            if request.url.path == "/orders/B2":
                raise RuntimeError("synthetic outage")
            return await call_next(request)

        return app

    monkeypatch.setattr(demo, "create_service", unavailable_service)
    rows = asyncio.run(run())["protected_app"]
    assert len(rows) == 16
    by_case = {tuple(row["case"][key] for key in ("actor", "action", "order_id")): row for row in rows}
    plain = by_case[("alice", "read", "A1")]
    assert plain["mismatches"] == ["status", "body"]
    assert plain["observed"]["status"] == 503
    assert plain["observed"]["body"] == {"content_type": "text/plain; charset=utf-8",
                                         "text_preview": "x" * 512, "byte_length": 600, "truncated": True}
    crashed = by_case[("bob", "read", "B2")]["observed"]
    assert crashed["status"] == 500
    assert crashed["body"]["text_preview"] == "Internal Server Error"


def test_empty_response_is_recorded():
    body = demo.observed_body(httpx.Response(403, content=b""))
    assert body == {"content_type": "", "text_preview": "", "byte_length": 0, "truncated": False}


def test_full_store_is_checked():
    case = Case("admin", "hold", "A1")
    before = {"A1": {"owner": "alice", "status": "open"}, "B2": {"owner": "bob", "status": "open"}}
    actual = deepcopy(expected(case, before))
    actual["state"]["B2"]["status"] = "held"
    assert evaluate(case, before, actual)["mismatches"] == ["state"]


def test_missing_order_and_unknown_identity():
    async def check():
        app = create_service({"a": "alice", "b": "bob", "c": "admin"})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as client:
            missing = await client.get("/orders/missing", headers={"Authorization": "Bearer a"})
            invalid = await client.get("/orders/A1", headers={"Authorization": "Bearer other"})
        assert (missing.status_code, missing.json()) == (404, {"detail": "Order not found"})
        assert invalid.status_code == 401
        assert invalid.headers["www-authenticate"] == "Bearer"
    asyncio.run(check())


def test_duplicate_identities_rejected():
    with pytest.raises(ValueError):
        create_service({"one": "alice", "two": "admin"})
