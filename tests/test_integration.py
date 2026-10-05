import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from scripts.local import Cluster, ROOT


@pytest.fixture(scope="module")
def cluster():
    with Cluster("ft", 8400, ROOT / ".runtime" / "tests" / str(uuid.uuid4())) as c:
        yield c


@pytest.fixture
def client():
    with httpx.Client(timeout=5, trust_env=False) as c:
        yield c


def payload(key=None):
    return {"student_id": "S001", "amount": 100, "idempotency_key": key or str(uuid.uuid4())}


def audit(c, cluster):
    r = c.get(cluster.url("database")+"/admin/audit", headers={"X-Demo-Token": cluster.token})
    r.raise_for_status()
    return r.json()


def test_normal_requests_and_health(cluster, client):
    assert client.get(cluster.url()+"/health").json()["status"] == "healthy"
    assert len(client.get(cluster.url()+"/api/students").json()) == 2
    assert client.get(cluster.url()+"/api/transcript/S001").json()["grades"]
    assert client.get(cluster.url()+"/api/transcript/UNKNOWN").status_code == 404
    assert "Campus reliability lab" in client.get(cluster.url()).text


def test_concurrent_duplicates_across_replicas(cluster, client):
    before = audit(client, cluster)
    body = payload()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: client.post(cluster.url()+"/api/payments", json=body), range(8)))
    assert all(r.status_code == 200 for r in results)
    assert len({r.json()["id"] for r in results}) == 1
    assert {r.headers["X-Worker"] for r in results} == {"payment1", "payment2"}
    after = audit(client, cluster)
    assert after["consistent"] and after["payment_count"] == before["payment_count"]+1


def test_key_payload_conflict(cluster, client):
    body = payload()
    assert client.post(cluster.url()+"/api/payments", json=body).status_code == 200
    body["amount"] = 101
    r = client.post(cluster.url()+"/api/payments", json=body)
    assert r.status_code == 409 and r.headers["X-Attempts"] == "1"


def test_rollback_restores_exact_pre_transaction_state(cluster, client):
    before = audit(client, cluster)
    client.post(cluster.url("database")+"/admin/fault", json={"interrupt": True}, headers={"X-Demo-Token": cluster.token}).raise_for_status()
    body = payload()
    # Direct storage request observes the rollback before gateway retry can complete the payment.
    r = client.post(cluster.url("database")+"/payments", json=body)
    assert r.status_code == 503
    assert audit(client, cluster) == before
    assert client.post(cluster.url()+"/api/payments", json=body).status_code == 200
    assert audit(client, cluster)["consistent"]


def test_lost_ack_does_not_double_charge(cluster, client):
    before = audit(client, cluster)
    client.post(cluster.url("database")+"/admin/fault", json={"response_loss": 1}, headers={"X-Demo-Token": cluster.token}).raise_for_status()
    r = client.post(cluster.url()+"/api/payments", json=payload())
    assert r.status_code == 200 and r.json()["duplicate"] and int(r.headers["X-Attempts"]) == 2
    assert audit(client, cluster)["payment_count"] == before["payment_count"]+1


def test_invalid_amount_and_unknown_student(cluster, client):
    for amount in (-1, 0, 0.5, True):
        body = {**payload(), "amount": amount}
        assert client.post(cluster.url()+"/api/payments", json=body).status_code == 422
    assert client.post(cluster.url()+"/api/payments", json={**payload(), "student_id": "bad"}).status_code == 404


def test_fault_controls_require_token(cluster, client):
    assert client.post(cluster.url("database")+"/admin/fault", json={"interrupt": True}).status_code == 403


def test_backup_restore_matches_checkpoint(cluster, client):
    before = audit(client, cluster)
    headers = {"X-Demo-Token": cluster.token}
    client.post(cluster.url("database")+"/admin/backup", headers=headers).raise_for_status()
    client.post(cluster.url()+"/api/payments", json=payload()).raise_for_status()
    client.post(cluster.url("database")+"/admin/restore", headers=headers).raise_for_status()
    assert audit(client, cluster) == before
