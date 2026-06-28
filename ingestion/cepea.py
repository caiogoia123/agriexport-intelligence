"""Extract commodity price indices from CEPEA/ESALQ (file-based source).

CEPEA publishes price series (soy, corn, coffee, cattle, sugar) as CSV/XLS — there is
no clean API, which is intentional here: it demonstrates handling a "messy" file source
(encoding, decimal comma, header noise) alongside clean APIs.

Source: https://www.cepea.esalq.usp.br/
Loads into raw_cepea_prices. Idempotent.

TODO (Phase 1): download files, normalize decimals/encoding, load via dlt.
"""

from __future__ import annotations


def extract_prices(commodity: str) -> list[dict]:
    """Return raw price rows for a commodity. Implemented in Phase 1."""
    raise NotImplementedError("Phase 1: implement CEPEA file extraction")


def main() -> None:
    raise NotImplementedError("Phase 1: wire extract -> dlt -> raw_cepea_prices")


if __name__ == "__main__":
    main()
