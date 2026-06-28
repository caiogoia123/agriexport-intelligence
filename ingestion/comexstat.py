"""Extract Brazilian export data from the Comex Stat API (MDIC/SECEX).

Grain: month x NCM product x destination country x origin state.
Measures: FOB value (US$), net weight (kg).

Docs: https://api-comexstat.mdic.gov.br/general?language=en
Loads into the `raw` dataset/schema. Ingestion must be idempotent (re-runnable).

TODO (Phase 1):
  - paginate the API, with retry/backoff
  - normalize NCM, country and date fields
  - load into raw_comexstat_exports via dlt (merge/append, partitioned by ref_date)
"""

from __future__ import annotations

API_BASE = "https://api-comexstat.mdic.gov.br"


def extract_exports(year_from: int, year_to: int) -> list[dict]:
    """Return raw export rows for the given year range. Implemented in Phase 1."""
    raise NotImplementedError("Phase 1: implement Comex Stat extraction")


def main() -> None:
    raise NotImplementedError("Phase 1: wire extract -> dlt -> raw_comexstat_exports")


if __name__ == "__main__":
    main()
