# Invoice Insights

End‑to‑end Python project: **FastAPI** backend + **Streamlit** frontend.

## Features

* Dropdown to choose company
* Invoice table (number, date, amount, paid, days‑to‑pay)
* KPIs: average days‑to‑pay, late invoices list
* Monthly totals chart (invoice vs paid)
* Late = paid > 30 days after invoice date (adjustable)

## Local dev

```bash
# clone repository
git clone <your‑repo> && cd invoice_insights

## backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
# leave running…

## frontend
cd ../frontend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

Visit <http://localhost:8501>.

## Live deployment

| Part | Host | Notes |
|------|------|-------|
| Backend | **Render.com** (free) | Build cmd: `pip install -r backend/requirements.txt`<br> Start cmd: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT` |
| Frontend | **Streamlit Community Cloud** | App file: `frontend/streamlit_app.py`<br>Secret: `API_ROOT=<Render URL>` |

Share Streamlit URL is what you share with reviewers.

## Tests

Run `pytest` from project root.

```bash
pip install -r tests/requirements.txt
pytest
```

Uses FastAPI TestClient to ensure endpoints respond and calculations are sane.


---

## Link

- 🚀 **Live Web App**: [https://technical-challengeautomate-5xuwd4zc4dn38al5ryuf2n.streamlit.app/](https://technical-challengeautomate-5xuwd4zc4dn38al5ryuf2n.streamlit.app/)
