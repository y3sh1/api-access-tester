"""Compare observations against an independently specified order contract."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from itertools import product


@dataclass(frozen=True)
class Case:
    actor: str
    action: str
    order_id: str

    @property
    def name(self):
        return f"{self.actor}/{self.action}/{self.order_id}"


def cases():
    return [Case(*parts) for parts in product(
        ("alice", "bob", "admin", "guest"), ("read", "hold"), ("A1", "B2")
    )]


def expected(case, before):
    state = deepcopy(before)
    order = state[case.order_id]
    if case.actor == "guest":
        return {"status": 401, "body": {"detail": "Sign in"}, "state": state}
    if case.action == "hold" and case.actor != "admin":
        return {"status": 403, "body": {"detail": "Forbidden"}, "state": state}
    if case.actor != "admin" and order["owner"] != case.actor:
        return {"status": 404, "body": {"detail": "Order not found"}, "state": state}
    if case.action == "hold":
        order["status"] = "held"
    return {"status": 200, "body": deepcopy(order), "state": state}


def evaluate(case, before, observed):
    want = expected(case, before)
    differences = [key for key in want if want[key] != observed[key]]
    return {"case": asdict(case), "passed": not differences, "mismatches": differences,
            "before": before, "expected": want, "observed": observed}
