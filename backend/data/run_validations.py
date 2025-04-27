"""
cleaning_utils.py
-------------------------------------------------
Validation + rectification helpers for the invoice dataset.
All fixes are opinionated but safe:
  • anything we cannot fix automatically is left in place and logged.
  • after every call, a tuple (clean_df, issue_report) is returned:
        - clean_df      : the DataFrame after fixes
        - issue_report  : dict {check_name: DataFrame_of_rows_fixed_or_flagged}
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import re
from collections import defaultdict
import os

# ── configurable patterns & canonical column names ───────────────────────────
INV_REF_PATTERN = re.compile(r"^\d{4}-\d+$")         # YYYY-#####
DATE_COLS       = ("Date Invoiced", "Date Paid")
COL_REF         = "Invoice Reference"
COL_CLIENT      = "Client Name"
COL_DAYS        = "No. Days taken to Pay"
COL_INV_AMT     = "Invoice Amount"
COL_PAID_AMT    = "Paid Amount"
COL_UNPAID_AMT  = "Unpaid Amount"
# -----------------------------------------------------------------------------


# ╭────────────────────────── helper utilities ─────────────────────────────╮ #
def _str_clean(val: str | float | int) -> str:
    """Coerce value to stripped string; NaN becomes empty string."""
    if pd.isna(val):
        return ""
    return str(val).strip()


def _safe_to_int(val) -> int | np.nan:
    """Convert to int if possible, else NaN."""
    try:
        return int(val)
    except Exception:
        return np.nan
# ╰──────────────────────────────────────────────────────────────────────────╯ #


def load_csv(path: str) -> pd.DataFrame:
    """Standard loader that ensures obvious dtypes and trimming."""
    df = pd.read_csv(path)

    # Trim whitespace from object columns
    obj_cols = df.select_dtypes(include="object").columns
    df[obj_cols] = df[obj_cols].applymap(_str_clean)

    # Coerce numeric columns (keeps NaN on failure)
    numeric_cols = [COL_INV_AMT, COL_PAID_AMT, COL_DAYS]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def fix_invoice_reference(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fix invoice references:
    - Replace '/' with '-'
    - Uppercase and remove spaces
    - No zero-padding, just fix format
    Rows still not matching the pattern are returned for review.
    """
    work = df.copy()

    def _fix(ref: str) -> str:
        if not ref or pd.isna(ref):
            return ref
        ref = ref.upper().replace(" ", "").replace("/", "-")
        return ref

    work[COL_REF] = work[COL_REF].apply(_fix)

    bad_rows = work.loc[~work[COL_REF].str.match(INV_REF_PATTERN, na=False)]

    return work, bad_rows



def fix_dates(df: pd.DataFrame, cols: tuple[str, ...] = DATE_COLS) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    Parses dates using pandas.to_datetime; unparseable entries -> NaT and
    returned for review. Also normalises to date (not datetime) dtype.
    """
    work = df.copy()
    issues: dict[str, pd.DataFrame] = {}
    for c in cols:
        ser = pd.to_datetime(work[c], errors="coerce")
        bad = work[ser.isna()]
        issues[c] = bad
        work[c] = ser.dt.date
    return work, issues


def recalc_days_to_pay(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Recomputes No. Days Taken to Pay; mismatches are overwritten with
    the correct value and returned for audit.
    """
    work = df.copy()
    invoice_dates = pd.to_datetime(df['Date Invoiced'], errors='coerce')
    paid_dates = pd.to_datetime(df['Date Paid'], errors='coerce')
    # computed = (dates[DATE_COLS[1]] - dates[DATE_COLS[0]]).dt.days
    computed = ( paid_dates - invoice_dates ).dt.days
    mismatch = work.loc[computed != work[COL_DAYS]]
    work[COL_DAYS] = computed
    return work, mismatch


def fix_paid_vs_invoice(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Where Paid Amount > Invoice Amount, clip Paid Amount down to Invoice Amount.
    Flagged rows returned.
    """
    work = df.copy()
    mask = work[COL_PAID_AMT] > work[COL_INV_AMT]
    flagged = work.loc[mask]
    work.loc[mask, COL_PAID_AMT] = work.loc[mask, COL_INV_AMT]
    return work, flagged

def fill_missing(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Very light-touch missing-value handler:
      • numeric NaN -> 0
      • string NaN  -> ''
    Returns rows that had ANY originally-missing field.
    """
    work = df.copy()
    missing_rows = work[work.isna().any(axis=1)].copy()
    for col in work:
        if work[col].dtype.kind in "biufc":
            work[col] = work[col].fillna(0)
        else:
            work[col] = work[col].fillna("")
    return work, missing_rows


# ╭────────────────────── orchestrator ──────────────────────────────╮ #
def clean_and_validate(path_or_df) -> tuple[pd.DataFrame, dict[str, pd.DataFrame | dict]]:
    """
    High-level convenience: pass a CSV path *or* a DataFrame.
    Returns:
        clean_df      – fully cleaned
        issue_report  – dict of DataFrames that were touched/flagged
    """
    if isinstance(path_or_df, str):
        df = load_csv(path_or_df)
    else:
        df = path_or_df.copy()

    report: dict[str, pd.DataFrame | dict] = defaultdict(pd.DataFrame)

    # 1) Invoice reference format
    df, report["invoice_reference_fixed"] = fix_invoice_reference(df)

    # 2) Date columns
    df, date_issues = fix_dates(df)
    report["date_format_fixed"] = date_issues

    # 3) No. days mismatch
    df, report["days_to_pay_fixed"] = recalc_days_to_pay(df)

    # 4) Paid > Invoice
    df, report["paid_gt_invoice_clipped"] = fix_paid_vs_invoice(df)


    # 5) Handle remaining missing values
    df, report["missing_values_filled"] = fill_missing(df)

    return df, report
# ╰──────────────────────────────────────────────────────────────────╯ #


if __name__ == "__main__":

   file_dir = os.path.dirname(os.path.abspath(__file__))


   # 1) Clean in one step
   clean_df, issues = clean_and_validate(f"{file_dir}/Data for Technical Challenge.csv")

   # 2) Save cleaned file
   clean_df.to_csv(f"{file_dir}/invoices_clean.csv", index=False)

   # 3) Examine / log any fixes
   for name, bad in issues.items():
      if isinstance(bad, dict):
         for col, df_bad in bad.items():
               print(f"{name} – {col}: {len(df_bad)} rows fixed or flagged")
      else:
         print(f"{name}: {len(bad)} rows fixed or flagged")