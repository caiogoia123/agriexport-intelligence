"""Extract Brazilian agribusiness export data from the Comex Stat API (MDIC/SECEX).

Grain: month x NCM product x destination country x origin state.
Measures: FOB value (US$), net weight (kg).

The raw API returns ALL exports (incl. petroleum, iron ore). We restrict to
agribusiness by building an explicit list of 8-digit NCM codes from the API's
own NCM reference table (`/tables/ncm`), filtered to the agribusiness headings
in AGRI_HEADINGS. This is auditable and self-updating (no hard-coded code list).

The `ncm` filter on /general matches FULL 8-digit codes only (4-digit prefixes
return nothing — verified), hence the reference-table expansion.

Docs: https://api-comexstat.mdic.gov.br/general?language=en
Loads into raw.comexstat_exports. Idempotent.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

API_BASE = "https://api-comexstat.mdic.gov.br"
PAGE_SIZE = 10_000
MAX_RETRIES = 4
RATE_LIMIT_SLEEP = 2.0  # base spacing; API allows ~10 req / 10 s

# Agribusiness NCM headings (first 4 digits) → commodity group.
# Chapters 01-24 cover food/agri; cotton (ch.52) and pulp (ch.47) are added
# explicitly as they sit outside that range. Source: MAPA/Agrostat classification.
AGRI_HEADINGS = {
    "0201": "carne_bovina",
    "0202": "carne_bovina",
    "0207": "carne_frango",
    "0901": "cafe",
    "1005": "milho",
    "1201": "soja",
    "1507": "soja",
    "2304": "soja",
    "1701": "acucar",
    "4703": "celulose",
    "5201": "algodao",
    "5203": "algodao",
}

# Confirmed response field names (live exploration 2026-06).
FIELD_MAP = {
    "coNcm": "ncm_code",
    "ncm": "ncm_description",
    "country": "destination_country",
    "state": "origin_state",
    "metricFOB": "fob_usd",
    "metricKG": "net_weight_kg",
    "_ref_date": "ref_date",
}

WANTED_COLS = [
    "ref_date",
    "ncm_code",
    "ncm_description",
    "destination_country",
    "origin_state",
    "fob_usd",
    "net_weight_kg",
]

_HEADERS = {
    # Comex Stat sits behind Cloudflare; a browser-like UA + Origin are required.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://comexstat.mdic.gov.br/",
    "Origin": "https://comexstat.mdic.gov.br",
}

_ncm_reference_cache: pd.DataFrame | None = None


# ---------------------------------------------------------------------------
# NCM reference (product dimension + filter source)
# ---------------------------------------------------------------------------


def fetch_ncm_reference() -> pd.DataFrame:
    """Fetch the full NCM table and return only agribusiness codes.

    Returns DataFrame[ncm_code, commodity, description] for the ~86 agri codes.
    Cached for the process lifetime.
    """
    global _ncm_reference_cache
    if _ncm_reference_cache is not None:
        return _ncm_reference_cache

    resp = requests.get(f"{API_BASE}/tables/ncm", headers=_HEADERS, timeout=60)
    resp.raise_for_status()
    items = resp.json().get("data", {}).get("list", [])

    rows = []
    for it in items:
        code = str(it.get("coNcm", "")).zfill(8)
        commodity = AGRI_HEADINGS.get(code[:4])
        if commodity:
            rows.append(
                {"ncm_code": code, "commodity": commodity, "description": it.get("noNCM")}
            )

    _ncm_reference_cache = pd.DataFrame(rows, columns=["ncm_code", "commodity", "description"])
    return _ncm_reference_cache


def agri_ncm_codes() -> list[str]:
    """Return the list of 8-digit agribusiness NCM codes used for filtering."""
    return sorted(fetch_ncm_reference()["ncm_code"].tolist())


# ---------------------------------------------------------------------------
# Export extraction
# ---------------------------------------------------------------------------


def extract_exports(
    year_from: int,
    year_to: int,
    ncm_codes: list[str] | None = None,
) -> pd.DataFrame:
    """Return monthly agribusiness export rows for the given year range.

    Iterates month by month (the API has no month field in the response, so we
    inject it per request) and filters to ``ncm_codes`` (defaults to all agri).
    """
    if ncm_codes is None:
        ncm_codes = agri_ncm_codes()

    frames: list[pd.DataFrame] = []
    for year in range(year_from, year_to + 1):
        for month in range(1, 13):
            period = f"{year:04d}-{month:02d}"
            rows = _fetch_period(period, ncm_codes)
            if rows:
                frames.append(_normalize(rows, period))
            print(f"    Comex Stat {period}: {len(rows):,} rows")

    return pd.concat(frames, ignore_index=True) if frames else _empty_df()


def _fetch_period(period: str, ncm_codes: list[str]) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        payload = _build_payload(period, page, ncm_codes)
        data = _post_with_retry(f"{API_BASE}/general", payload)
        batch: list[dict] = data.get("data", {}).get("list", [])
        if not batch:
            break
        for row in batch:
            row["_ref_date"] = period  # API omits the month — inject it
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        time.sleep(RATE_LIMIT_SLEEP)
    time.sleep(RATE_LIMIT_SLEEP)
    return rows


def _build_payload(period: str, page: int, ncm_codes: list[str]) -> dict:
    return {
        "flow": "export",
        "typeMonthly": True,
        "grana": "country",
        "period": {"from": period, "to": period},
        "filters": [{"filter": "ncm", "values": ncm_codes}],
        "page": page,
        "pageSize": PAGE_SIZE,
        "details": ["ncm", "country", "state"],
        "metrics": ["metricFOB", "metricKG"],
    }


def _post_with_retry(url: str, payload: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, headers=_HEADERS, timeout=60)
            if resp.status_code == 429:
                # Rate limited — wait out the window and retry.
                time.sleep(12)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** (attempt + 2))  # 4s, 8s, 16s
    return {}


def _normalize(rows: list[dict], period: str) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df.rename(columns={k: v for k, v in FIELD_MAP.items() if k in df.columns})

    if "ref_date" not in df.columns:
        df["ref_date"] = period

    for col in ("fob_usd", "net_weight_kg"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    present = [c for c in WANTED_COLS if c in df.columns]
    return df[present].copy()


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=WANTED_COLS)


def main() -> None:
    from ingestion import setup_database

    con = setup_database()
    print("Extracting Comex Stat agribusiness exports (2020-2024)...")
    df = extract_exports(2020, 2024)
    print(f"  {len(df):,} rows fetched")

    con.execute("DELETE FROM raw.comexstat_exports")
    con.execute(
        "INSERT INTO raw.comexstat_exports "
        "(ref_date, ncm_code, ncm_description, destination_country, "
        " origin_state, fob_usd, net_weight_kg) "
        "SELECT ref_date, ncm_code, ncm_description, destination_country, "
        "       origin_state, fob_usd, net_weight_kg FROM df"
    )
    print("  Loaded into raw.comexstat_exports")
    con.close()


if __name__ == "__main__":
    main()
