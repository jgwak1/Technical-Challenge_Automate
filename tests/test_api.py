import sys, pathlib, json
import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
print(ROOT)
sys.path.insert(0, str(ROOT))                       # put repo root on sys.path
sys.path.append(str(ROOT / "backend"))

from backend.app import app, companies

client = TestClient(app)

def test_companies():
    r = client.get("/companies")
    assert r.status_code == 200
    assert set(r.json()) == set(companies)

def test_company_endpoints():
    sample = companies[0]
    inv = client.get(f"/company/{sample}/invoices")
    met = client.get(f"/company/{sample}/metrics")
    assert inv.status_code == 200
    assert met.status_code == 200
    assert isinstance(inv.json(), list)
    assert "average_days_to_pay" in met.json()
