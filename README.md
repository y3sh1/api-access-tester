# API Access Tester

A buyer can see their own orders. An administrator can read every order and place an order on hold. This FastAPI exercise checks those rules for Alice, Bob, an administrator and a guest. Every case records the response body and the entire order store before and after the operation.

## Run the demo

Use Python 3.13 in a virtual environment. From the repository root run these commands.

~~~console
python -m pip install -r requirements.txt
python -m orders.demo --output report.json
python -m pytest -q
~~~

The demo uses httpx's in-process ASGI transport. It creates a fresh store and temporary credentials for each run. With Docker, run the same demo or the tests as follows.

~~~console
docker build -t order-contract .
docker run --rm order-contract
docker run --rm order-contract python -m pytest -q -p no:cacheprovider
~~~

## Access policy

| Identity | Read own order | Read another order | Place any order on hold |
| --- | --- | --- | --- |
| Guest | 401 | 401 | 401 |
| Customer | 200 | 404 | 403 |
| Administrator | 200 | 200 | 200 |

The service reads permissions from [orders/policy.json](orders/policy.json). The contract in [orders/contract.py](orders/contract.py) encodes the expected business rules separately so that an accidental permission change can fail the suite. Alice owns A1 and Bob owns B2. Both orders start open. A successful hold must change only the selected order to held.

## What the demo found

~~~text
modeled_baseline: 14/16 passed
  alice/read/B2  mismatches: body
  bob/hold/B2  mismatches: state
protected_app: 16/16 passed
~~~

The protected column below comes from invoking the FastAPI app. The baseline reuses those observations with two documented, synthetic substitutions from [the baseline fixture](orders/modeled-observations.json). Both go through the same evaluator. The repository contains one runnable API implementation, the protected service.

| Case | Expected evidence | Modeled baseline | Protected app |
| --- | --- | --- | --- |
| Alice reads B2 | 404 with only the error message | 404 body also contains Bob's lamp order | 404 with only the error |
| Bob puts B2 on hold | 403 and both orders stay open | 403 and B2 changes to held | 403 and B2 stays open |

The 16-case matrix also includes authorized reads and holds so an implementation that denies every request will fail. The demo exits with status 1 on a protected-service mismatch. If the app returns an empty or non-JSON body, the report retains the status, content type, body size and a preview of up to 512 bytes. Full per-case results are in [the recorded JSON report](examples/evidence.json).

## Run the API manually

Set three distinct, nonempty environment variables called ORDER_TOKEN_ALICE, ORDER_TOKEN_BOB and ORDER_TOKEN_ADMIN in your shell. Start the service with the command below. Open the local FastAPI documentation at http://127.0.0.1:8000/docs and use **Authorize** to enter one of your tokens.

~~~console
python -m uvicorn orders.service:from_environment --factory --host 127.0.0.1
~~~

## Scope and limitations

All data is synthetic and resets on restart. The exercise covers one read and one administrative state transition. It uses a single in-memory process, and token provisioning, session lifecycle, concurrency across workers and production identity providers are outside its scope. The modeled baseline demonstrates the evaluator's sensitivity. A reproduced defect on an external service would require independent evidence.

## Sources and attribution

The object-level and function-level categories follow [OWASP API Security Top 10, 2023](https://api-security.owasp.org/editions/2023/en/0x11-t10/). The transport setup follows the [FastAPI async testing documentation](https://fastapi.tiangolo.com/advanced/async-tests/). The service, policy, cases and synthetic observations were written for this project. FastAPI, httpx, pytest, Uvicorn and the Docker Python image are third-party dependencies.
