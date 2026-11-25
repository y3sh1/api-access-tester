"""A small in-memory order service. A new instance owns its entire data store."""
import os
from dataclasses import dataclass
from pathlib import Path
import json

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass(frozen=True)
class User:
    name: str
    role: str


USERS = {
    "alice": User("alice", "customer"),
    "bob": User("bob", "customer"),
    "admin": User("admin", "administrator"),
}
POLICY = json.loads(Path(__file__).with_name("policy.json").read_text(encoding="utf-8"))
bearer = HTTPBearer(auto_error=False)


def create_service(tokens: dict[str, str]) -> FastAPI:
    if set(tokens.values()) != set(USERS) or len(tokens) != len(USERS) or "" in tokens:
        raise ValueError("Supply a distinct nonempty bearer token for each demo account")
    accounts = {token: USERS[name] for token, name in tokens.items()}
    app = FastAPI(title="Order access contract")
    orders = {
        "A1": {"id": "A1", "owner": "alice", "item": "notebook", "status": "open"},
        "B2": {"id": "B2", "owner": "bob", "item": "lamp", "status": "open"},
    }
    app.state.orders = orders

    def principal(auth: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
        account = accounts.get(auth.credentials) if auth else None
        if account is None:
            raise HTTPException(401, "Sign in", headers={"WWW-Authenticate": "Bearer"})
        return account

    def authorized(order_id: str, user: User, action: str) -> dict:
        scope = POLICY.get(user.role, {}).get(action, "none")
        if scope not in {"own", "all"}:
            raise HTTPException(403, "Forbidden")
        order = orders.get(order_id)
        if order is None or (scope == "own" and order["owner"] != user.name):
            raise HTTPException(404, "Order not found")
        return order

    @app.get("/orders/{order_id}")
    async def read(order_id: str, user: User = Depends(principal)):
        return authorized(order_id, user, "read")

    @app.post("/admin/orders/{order_id}/hold")
    async def hold(order_id: str, user: User = Depends(principal)):
        order = authorized(order_id, user, "hold")
        order["status"] = "held"
        return order

    return app


def from_environment() -> FastAPI:
    """Uvicorn factory for a local manual run."""
    return create_service({os.environ["ORDER_TOKEN_" + name.upper()]: name for name in USERS})
