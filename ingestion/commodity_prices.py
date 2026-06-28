"""Extract monthly commodity benchmark prices from FRED (St. Louis Fed).

Originally this project planned to use CEPEA/ESALQ spot prices, but the CEPEA
site blocks programmatic access (HTTP 403 / Cloudflare). FRED publishes the
IMF/World Bank Primary Commodity Prices as keyless CSV downloads, covering the
same commodities in USD — a clean, current, no-auth replacement.

Endpoint (no API key): https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>
CSV shape: two columns `observation_date` (YYYY-MM-DD, 1st of month) and the
series id (float; missing values appear as ".").

Units differ per commodity (see SERIES) — normalization to a common unit is
left to the dbt transform layer. Loads into raw.commodity_prices. Idempotent.
"""

from __future__ import annotations

import io
import time

import pandas as pd
import requests

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
MAX_RETRIES = 3

# commodity group (matches comexstat AGRI_HEADINGS) → FRED series + unit.
SERIES = {
    "soja": {"fred_series": "PSOYBUSDM", "unit": "USD/metric_ton"},
    "milho": {"fred_series": "PMAIZMTUSDM", "unit": "USD/metric_ton"},
    "cafe": {"fred_series": "PCOFFOTMUSDM", "unit": "US_cents/lb"},
    "acucar": {"fred_series": "PSUGAISAUSDM", "unit": "US_cents/lb"},
    "carne_bovina": {"fred_series": "PBEEFUSDM", "unit": "US_cents/lb"},
}

_HEADERS = {"User-Agent": "agriexport-intelligence/1.0 (+https://github.com/caiogoia123)"}


def extract_prices(commodity: str) -> pd.DataFrame:
    """Fetch one commodity's monthly price series from FRED.

    Returns DataFrame[commodity, ref_date, price, unit, fred_series, source].
    """
    if commodity not in SERIES:
        raise ValueError(f"Unknown commodity '{commodity}'. Valid: {list(SERIES)}")

    meta = SERIES[commodity]
    series_id = meta["fred_series"]
    content = _download_with_retry(series_id)
    return _parse_csv(content, commodity, series_id, meta["unit"])


def _download_with_retry(series_id: str) -> bytes:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                FRED_CSV, params={"id": series_id}, headers=_HEADERS, timeout=30
            )
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)
    return b""


def _parse_csv(content: bytes, commodity: str, series_id: str, unit: str) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(content))

    # Columns: observation_date, <series_id>. Normalize names.
    date_col = df.columns[0]
    value_col = series_id if series_id in df.columns else df.columns[1]

    df = df.rename(columns={date_col: "ref_date", value_col: "price"})
    df["ref_date"] = pd.to_datetime(df["ref_date"], errors="coerce").dt.date
    df["price"] = pd.to_numeric(df["price"], errors="coerce")  # "." → NaN
    df = df.dropna(subset=["ref_date", "price"])

    df["commodity"] = commodity
    df["unit"] = unit
    df["fred_series"] = series_id
    df["source"] = "FRED"

    return df[["commodity", "ref_date", "price", "unit", "fred_series", "source"]].copy()


def extract_all() -> pd.DataFrame:
    """Extract all configured commodities into a single DataFrame."""
    frames = []
    for commodity in SERIES:
        print(f"  FRED {commodity} ({SERIES[commodity]['fred_series']})...")
        try:
            frames.append(extract_prices(commodity))
        except Exception as exc:  # noqa: BLE001 - log and continue per source
            print(f"    WARNING: failed to fetch {commodity}: {exc}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    from ingestion import setup_database

    con = setup_database()
    print("Extracting FRED commodity benchmark prices...")
    df = extract_all()
    print(f"  {len(df):,} price observations fetched")

    con.execute("DELETE FROM raw.commodity_prices")
    con.execute(
        "INSERT INTO raw.commodity_prices "
        "(commodity, ref_date, price, unit, fred_series, source) "
        "SELECT commodity, ref_date, price, unit, fred_series, source FROM df"
    )
    print("  Loaded into raw.commodity_prices")
    con.close()


if __name__ == "__main__":
    main()
