import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.experiment_results import ROOT, load_results
from app.gateway import app
from scripts.visualize_results import build


def test_degraded_is_not_double_counted_as_error():
    data = load_results(ROOT / "results" / "final")
    ft = [r for r in data["cases"] if r["mode"] == "ft" and r["scenario"] == "timeout"]
    assert len(ft) == 3
    assert all(r["degraded_responses"] == 5 and r["errors"] == 0 for r in ft)
    assert all(r["successful_requests"] + r["degraded_responses"] + r["errors"] == r["requests"] for r in data["cases"])


def test_results_cannot_read_outside_project():
    with pytest.raises(ValueError, match="inside"):
        load_results(ROOT.parent)


def test_results_endpoint_and_page(monkeypatch):
    data = load_results(ROOT / "results" / "final")
    monkeypatch.setattr("app.gateway.latest_results", lambda: data)
    with TestClient(app) as client:
        response = client.get("/api/experiments/latest")
        assert response.status_code == 200 and len(response.json()["cases"]) == 54
        assert response.headers["cache-control"] == "no-store"
        assert "EXPERIMENT_DATA" in client.get("/results").text


def test_standalone_export_embeds_real_data_and_escapes_script(monkeypatch):
    directory = ROOT / ".runtime" / "tests" / str(uuid.uuid4())
    directory.mkdir(parents=True)
    data = load_results(ROOT / "results" / "final")
    data["run"] = "</script><script>alert(1)</script>"
    monkeypatch.setattr("scripts.visualize_results.load_results", lambda _: data)
    path = build(directory)
    text = path.read_text(encoding="utf-8")
    embedded = text.split("window.EXPERIMENT_DATA=", 1)[1].split(";\nconst $", 1)[0]
    assert json.loads(embedded) == data
    assert "</script>" not in embedded
    assert "/*EXPERIMENT_DATA*/null" not in text
