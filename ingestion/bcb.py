"""Extract economic time series from the Banco Central do Brasil SGS API.

Series of interest (SGS codes):
  - 1     : USD/BRL exchange rate (daily)
  - 433   : IPCA (monthly inflation)
  - 432   : SELIC target rate

Docs: https://dadosabertos.bcb.gov.br/  (SGS REST/JSON, public, no key)
Loads into raw_bcb_series. Idempotent.

TODO (Phase 1): fetch each series, parse dd/mm/yyyy dates, load via dlt.
"""

from __future__ import annotations

SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json"


def extract_series(code: int) -> list[dict]:
    """Return raw observations for an SGS series. Implemented in Phase 1."""
    raise NotImplementedError("Phase 1: implement BCB SGS extraction")


def main() -> None:
    raise NotImplementedError("Phase 1: wire extract -> dlt -> raw_bcb_series")


if __name__ == "__main__":
    main()
