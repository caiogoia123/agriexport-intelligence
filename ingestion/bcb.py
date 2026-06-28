"""Extract economic time series from the Banco Central do Brasil SGS API.

Series collected (SGS codes):
  - 1   : USD/BRL exchange rate (daily)
  - 433 : IPCA monthly inflation index
  - 432 : SELIC target rate

Docs: https://dadosabertos.bcb.gov.br/  (public REST/JSON, no API key required)
Loads into raw.bcb_series. Idempotent.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

SGS_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
MAX_RETRIES = 3
# BCB SGS rejects (HTTP 406) daily-series requests spanning more than ~10 years.
# Chunk into safe windows so any range works regardless of series frequency.
MAX_CHUNK_DAYS = 365 * 9


def _parse(d: str) -> datetime:
    return datetime.strptime(d, "%d/%m/%Y")


SERIES = {
    1: "usd_brl",
    433: "ipca",
    432: "selic",
}


def extract_series(
    code: int,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch one BCB SGS series and return a normalized DataFrame.

    Splits the range into <=9-year windows (BCB caps daily series at ~10y per
    request) and concatenates the results.

    Args:
        code: SGS series code (e.g. 1 for USD/BRL).
        start_date: First date to fetch in DD/MM/YYYY format.
        end_date: Last date to fetch in DD/MM/YYYY format.
    """
    frames = []
    chunk_start = _parse(start_date)
    final_end = _parse(end_date)

    while chunk_start <= final_end:
        chunk_end = min(chunk_start + timedelta(days=MAX_CHUNK_DAYS), final_end)
        raw = _fetch_window(
            code, chunk_start.strftime("%d/%m/%Y"), chunk_end.strftime("%d/%m/%Y")
        )
        frames.append(_normalize(raw, code))
        chunk_start = chunk_end + timedelta(days=1)

    return (
        pd.concat(frames, ignore_index=True)
        if frames
        else _normalize([], code)
    )


def _fetch_window(code: int, start_date: str, end_date: str) -> list[dict]:
    url = SGS_BASE.format(code=code)
    params = {"formato": "json", "dataInicial": start_date, "dataFinal": end_date}

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)
    return []


def _normalize(raw: list[dict], code: int) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=["series_code", "series_name", "ref_date", "value"])

    df = pd.DataFrame(raw)

    # BCB returns dates as "dd/MM/yyyy" strings.
    df["ref_date"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.date
    df["value"] = pd.to_numeric(df["valor"], errors="coerce")
    df["series_code"] = code
    df["series_name"] = SERIES.get(code, str(code))

    return df[["series_code", "series_name", "ref_date", "value"]].copy()


def extract_all(
    start_date: str = "01/01/2015",
    end_date: str | None = None,
) -> pd.DataFrame:
    """Extract all configured series and return as a single DataFrame."""
    if end_date is None:
        end_date = date.today().strftime("%d/%m/%Y")

    frames = []
    for code in SERIES:
        print(f"  BCB series {code} ({SERIES[code]})...")
        frames.append(extract_series(code, start_date, end_date))

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    from ingestion import setup_database

    con = setup_database()
    print("Extracting BCB macro series (2015-today)...")
    df = extract_all()
    print(f"  {len(df):,} observations fetched")

    con.execute("DELETE FROM raw.bcb_series")
    con.execute("INSERT INTO raw.bcb_series SELECT * FROM df")
    print("  Loaded into raw.bcb_series")
    con.close()


if __name__ == "__main__":
    main()
