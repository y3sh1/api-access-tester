import asyncio
from copy import deepcopy

import httpx
import pytest

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
