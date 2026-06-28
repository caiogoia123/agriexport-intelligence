"""Extract/Load layer: pulls raw data from public APIs into the warehouse (EL pattern).

Sources:
  - comexstat        : Brazilian agribusiness exports (FOB, weight) by NCM x country x state x month
  - bcb              : macro series (USD/BRL, IPCA, SELIC) from Banco Central
  - commodity_prices : FRED monthly commodity benchmark prices (USD)

Plus a derived reference table (raw.ncm_reference) mapping each agri NCM code to
its commodity group — the join key between exports and commodity prices.
"""

from __future__ import annotations

import os

import duckdb

DB_PATH = os.environ.get("AGRIEXPORT_DB", "data/dev.duckdb")


def setup_database(db_path: str = DB_PATH) -> duckdb.DuckDBPyConnection:
    """Create the raw schema and tables if they don't exist. Returns an open connection."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    con = duckdb.connect(db_path)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.comexstat_exports (
            ref_date             VARCHAR,
            ncm_code             VARCHAR,
            ncm_description      VARCHAR,
            destination_country  VARCHAR,
            origin_state         VARCHAR,
            fob_usd              DOUBLE,
            net_weight_kg        DOUBLE,
            loaded_at            TIMESTAMP DEFAULT current_timestamp
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.ncm_reference (
            ncm_code     VARCHAR,
            commodity    VARCHAR,
            description  VARCHAR,
            loaded_at    TIMESTAMP DEFAULT current_timestamp
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.bcb_series (
            series_code  INTEGER,
            series_name  VARCHAR,
            ref_date     DATE,
            value        DOUBLE,
            loaded_at    TIMESTAMP DEFAULT current_timestamp
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.commodity_prices (
            commodity    VARCHAR,
            ref_date     DATE,
            price        DOUBLE,
            unit         VARCHAR,
            fred_series  VARCHAR,
            source       VARCHAR,
            loaded_at    TIMESTAMP DEFAULT current_timestamp
        )
    """)

    return con


def main(year_from: int = 2020, year_to: int = 2024) -> None:
    from ingestion import bcb, comexstat, commodity_prices

    con = setup_database()
    print("=== agriexport-intelligence - full ingestion run ===")

    print("\n[1/4] NCM reference (agribusiness product dimension)")
    df_ncm = comexstat.fetch_ncm_reference()
    print(f"  {len(df_ncm):,} agri NCM codes")
    con.execute("DELETE FROM raw.ncm_reference")
    con.execute(
        "INSERT INTO raw.ncm_reference (ncm_code, commodity, description) "
        "SELECT ncm_code, commodity, description FROM df_ncm"
    )
    print("  -> raw.ncm_reference")

    print(f"\n[2/4] Comex Stat agribusiness exports ({year_from}-{year_to})")
    df_exports = comexstat.extract_exports(year_from, year_to)
    print(f"  {len(df_exports):,} rows fetched")
    con.execute("DELETE FROM raw.comexstat_exports")
    con.execute(
        "INSERT INTO raw.comexstat_exports "
        "(ref_date, ncm_code, ncm_description, destination_country, "
        " origin_state, fob_usd, net_weight_kg) "
        "SELECT ref_date, ncm_code, ncm_description, destination_country, "
        "       origin_state, fob_usd, net_weight_kg FROM df_exports"
    )
    print("  -> raw.comexstat_exports")

    print("\n[3/4] BCB macro series")
    df_bcb = bcb.extract_all()
    print(f"  {len(df_bcb):,} observations fetched")
    con.execute("DELETE FROM raw.bcb_series")
    con.execute(
        "INSERT INTO raw.bcb_series (series_code, series_name, ref_date, value) "
        "SELECT series_code, series_name, ref_date, value FROM df_bcb"
    )
    print("  -> raw.bcb_series")

    print("\n[4/4] FRED commodity benchmark prices")
    df_prices = commodity_prices.extract_all()
    print(f"  {len(df_prices):,} price observations fetched")
    con.execute("DELETE FROM raw.commodity_prices")
    con.execute(
        "INSERT INTO raw.commodity_prices "
        "(commodity, ref_date, price, unit, fred_series, source) "
        "SELECT commodity, ref_date, price, unit, fred_series, source FROM df_prices"
    )
    print("  -> raw.commodity_prices")

    con.close()
    print("\nDone. Database:", DB_PATH)


if __name__ == "__main__":
    main()
