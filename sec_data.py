"""Free SEC EDGAR data adapter.
The SEC publishes company submissions and XBRL data through data.sec.gov.
A descriptive User-Agent is required for programmatic access.
"""
from __future__ import annotations
import os
import requests

SEC_BASE = "https://data.sec.gov"
USER_AGENT = os.getenv("SEC_USER_AGENT", "SmallCapPaperTrader/1.0 contact@example.com")


def _get(path: str):
    r = requests.get(SEC_BASE + path, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}, timeout=15)
    r.raise_for_status()
    return r.json()


def submissions(cik: str):
    return _get(f"/submissions/CIK{int(cik):010d}.json")


def company_facts(cik: str):
    return _get(f"/api/xbrl/companyfacts/CIK{int(cik):010d}.json")


def recent_filings(cik: str, forms=None, limit: int = 100):
    data = submissions(cik)
    recent = data.get("filings", {}).get("recent", {})
    forms = set(forms or [])
    out = []
    for i, form in enumerate(recent.get("form", [])):
        if forms and form not in forms:
            continue
        out.append({k: recent.get(k, [None] * len(recent.get("form", [])))[i] for k in ["accessionNumber", "filingDate", "reportDate", "form", "primaryDocument"]})
        if len(out) >= limit:
            break
    return out


def financing_risk(cik: str, limit: int = 100):
    """Flag filing types commonly associated with financing/dilution risk."""
    risky = {"S-1", "S-1/A", "S-3", "S-3/A", "424B3", "424B4", "424B5", "8-K"}
    filings = recent_filings(cik, risky, limit)
    keywords = ("offering", "registered direct", "atm", "convertible", "warrant", "securities purchase", "dilution", "reverse split")
    return [f for f in filings if any(k in str(f).lower() for k in keywords)]
