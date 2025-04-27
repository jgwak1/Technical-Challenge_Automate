"""Invoice Insights API (v2)

Enhancements:
* min / max days_to_pay
* weekly, monthly, annual totals
* company‑specific late definition = > average days_to_pay
* GPT‑powered `/company/{name}/insight` endpoint (requires OPENAI_API_KEY)
"""
from pathlib import Path
from typing import List, Dict

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

from g4f.client import Client
from g4f.Provider import OpenaiChat

DATA_PATH = Path(__file__).resolve().parents[0] / "data" / "invoices_clean.csv"

app = FastAPI(title="Invoice Insights API v2", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Load & normalise data ---- #
df = pd.read_csv(
    DATA_PATH,
    parse_dates=["Date Invoiced", "Date Paid"],
    dayfirst=False,
    infer_datetime_format=True
)

# Standardise column names ➜ snake_case
df.columns = (
    df.columns.str.strip()
              .str.lower()
              .str.replace(" ", "_", regex=False)
)

REQUIRED_COLS = {"client_name", "invoice_reference", "date_invoiced",
                 "invoice_amount", "paid_amount", "date_paid" }
missing_cols = REQUIRED_COLS - set(df.columns)
if missing_cols:
    raise RuntimeError(f"Missing expected columns: {missing_cols}")

# Days to pay
df["days_to_pay"] = (df["date_paid"] - df["date_invoiced"]).dt.days
companies: List[str] = sorted(f"company_{name}" for name in df["client_name"].dropna().unique())

# ---------- helpers ---------- #
def _company_df(company_name: str) -> pd.DataFrame:
    if company_name not in companies:
        raise HTTPException(404, "Company not found")
    
    company_number = int( company_name.split("_")[1] )
    return df[ df["client_name"] == company_number].copy()

# ---------- endpoints ---------- #
@app.get("/companies")
async def list_companies():
    # print(f"[DEBUG-2] companies: {companies}")
    return companies

@app.get("/company/{company_name}/invoices")
async def invoices(company_name: str):
    cdf = _company_df(company_name)

    cols = ["invoice_reference", "date_invoiced", "invoice_amount",
            "paid_amount", "days_to_pay"]
    return cdf[cols].sort_values("date_invoiced").to_dict(orient="records")

@app.get("/company/{company_name}/metrics")
async def metrics(company_name: str):
    cdf = _company_df(company_name)

    avg_dtp = float(cdf["days_to_pay"].mean())
    min_dtp = int(cdf["days_to_pay"].min())
    max_dtp = int(cdf["days_to_pay"].max())

    # Custom late definition: > average days_to_pay
    late_mask = cdf["days_to_pay"] > avg_dtp
    late_invoices = cdf.loc[late_mask, "invoice_reference"].tolist()

    def group_totals(freq: str, label: str) -> List[Dict]:
        grp = (cdf.set_index("date_invoiced")
                 .groupby(pd.Grouper(freq=freq))
                 .agg(invoice_total=("invoice_amount", "sum"),
                      paid_total=("paid_amount", "sum"),
                      invoice_count=("invoice_reference", "count"))
                 .reset_index())
        grp[label] = grp["date_invoiced"]
        if freq == "M":
            grp[label] = grp["date_invoiced"].dt.strftime("%Y-%m")
        elif freq == "W":
            grp[label] = grp["date_invoiced"].dt.strftime("%Y-%W")
        elif freq == "Y":
            grp[label] = grp["date_invoiced"].dt.year.astype(str)
        return grp[[label, "invoice_total", "paid_total", "invoice_count"]].to_dict(orient="records")

    monthly_totals = group_totals("M", "month")
    weekly_totals = group_totals("W", "week")
    annual_totals = group_totals("Y", "year")

    # Revenue over time (cumulative paid)
    revenue = (cdf.sort_values("date_invoiced")
                 .assign(cum_paid=cdf.sort_values("date_invoiced")["paid_amount"].cumsum())
                 [["date_invoiced", "cum_paid"]]
                 .rename(columns={"date_invoiced": "date"})
                 .to_dict(orient="records"))

    # Seasonality: avg invoices and value by calendar month (across years)
    seasonal = (cdf.copy()
                  .assign(month=cdf["date_invoiced"].dt.month)
                  .groupby("month")
                  .agg(avg_invoice_value=("invoice_amount", "mean"),
                       avg_invoice_count=("invoice_reference", "count"))
                  .reset_index()
                  .to_dict(orient="records"))

    return {
        "average_days_to_pay": round(avg_dtp, 2),
        "min_days_to_pay": min_dtp,
        "max_days_to_pay": max_dtp,
        "late_invoices": late_invoices,
        "monthly_totals": monthly_totals,
        "weekly_totals": weekly_totals,
        "annual_totals": annual_totals,
        "revenue_over_time": revenue,
        "seasonality": seasonal,
        "late_definition": f"> avg days_to_pay ({round(avg_dtp,2)} days)"
    }



# ############################################################################################

# Following feature is not working 

@app.post("/client/{company_name}/insight")
async def ai_insight(company_name: str, query: str):
    """Generate a natural-language insight using GPT based on the company dataframe."""

    cdf = _company_df(company_name)
    # Limit rows to keep prompt size reasonable
    sample = cdf.head(200).to_csv(index=False)
    print(sample)

    prompt = f"""You are an AI finance analyst. Answer the user's question about {company_name}
    using the data below. Be concise and quantitative.

    User question: {query}

    CSV data:
    {sample}
    """

    # Using gpt4free to generate the answer
    client = Client()    
    try:

        response = client.chat.completions.create(
            model= 'gpt-4o',
            messages= {"role": "user",  "content": prompt} , 
        ).choices[0].message.content.strip()

    except Exception as e:
        raise HTTPException(500, f"gpt4free error: {str(e)}")

    print(f"{response}")


    return {"answer": response}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000)