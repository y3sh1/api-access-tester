"""Exercise the protected app in memory, then score a separate modeled baseline."""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import secrets

import httpx

from .contract import cases, evaluate
from .service import USERS, create_service


def observed_body(response):
    try:
        return response.json()
    except ValueError:
        preview = response.content[:512]
        return {"content_type": response.headers.get("content-type", "")[:128],
                "text_preview": preview.decode("utf-8", errors="replace"),
                "byte_length": len(response.content),
                "truncated": len(preview) < len(response.content)}


async def run():
    baseline = json.loads(Path(__file__).with_name("modeled-observations.json").read_text(encoding="utf-8"))
    tokens = {name: secrets.token_urlsafe(24) for name in USERS}
    fixed, modeled = [], []
    for case in cases():
        app = create_service({token: name for name, token in tokens.items()})
        before = deepcopy(app.state.orders)
        headers = {"Authorization": "Bearer " + tokens[case.actor]} if case.actor in tokens else {}
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://fixture") as client:
            if case.action == "read":
                response = await client.get(f"/orders/{case.order_id}", headers=headers)
            else:
                response = await client.post(f"/admin/orders/{case.order_id}/hold", headers=headers)
        actual = {"status": response.status_code, "body": observed_body(response), "state": deepcopy(app.state.orders)}
        fixed.append(evaluate(case, before, actual))
        previous = deepcopy(actual)
        previous.update(baseline.get(case.name, {}))
        modeled.append(evaluate(case, before, previous))
    return {"modeled_baseline": modeled, "protected_app": fixed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write full JSON evidence")
    args = parser.parse_args()
    report = asyncio.run(run())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for label, rows in report.items():
        print(f"{label}: {sum(r['passed'] for r in rows)}/{len(rows)} passed")
        for row in rows:
            if not row["passed"]:
                case = row["case"]
                print("  " + "/".join(case.values()) + "  mismatches: " + ", ".join(row["mismatches"]))
    return int(any(not row["passed"] for row in report["protected_app"]))


if __name__ == "__main__":
    raise SystemExit(main())
