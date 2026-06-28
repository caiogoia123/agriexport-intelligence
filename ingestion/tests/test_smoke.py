"""Unit tests for the ingestion layer. All external calls are mocked."""

from __future__ import annotations

import importlib
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Module import sanity
# ---------------------------------------------------------------------------


def test_modules_import():
    for mod in ("ingestion.comexstat", "ingestion.bcb", "ingestion.commodity_prices"):
        assert importlib.import_module(mod) is not None


def test_api_base_is_https():
    from ingestion import comexstat

    assert comexstat.API_BASE.startswith("https://")


# ---------------------------------------------------------------------------
# comexstat — NCM reference (product dimension + filter source)
# ---------------------------------------------------------------------------


@pytest.fixture
def ncm_table_response():
    return {
        "data": {
            "list": [
                {"coNcm": "12019000", "noNCM": "Soja, exceto para semeadura", "unit": "KG"},
                {"coNcm": "10059010", "noNCM": "Milho em grão", "unit": "KG"},
                # next two are not agribusiness and must be filtered out:
                {"coNcm": "27090010", "noNCM": "Óleos brutos de petróleo", "unit": "KG"},
                {"coNcm": "26011100", "noNCM": "Minérios de ferro", "unit": "KG"},
            ]
        }
    }


def test_fetch_ncm_reference_filters_to_agri(ncm_table_response):
    from ingestion import comexstat

    comexstat._ncm_reference_cache = None  # reset cache
    mock_resp = MagicMock()
    mock_resp.json.return_value = ncm_table_response
    mock_resp.raise_for_status = MagicMock()

    with patch("ingestion.comexstat.requests.get", return_value=mock_resp):
        ref = comexstat.fetch_ncm_reference()

    # Petroleum and iron ore must be excluded; soja/milho kept and mapped.
    assert set(ref["ncm_code"]) == {"12019000", "10059010"}
    assert ref.loc[ref["ncm_code"] == "12019000", "commodity"].iloc[0] == "soja"
    assert ref.loc[ref["ncm_code"] == "10059010", "commodity"].iloc[0] == "milho"

    comexstat._ncm_reference_cache = None  # avoid leaking into other tests


# ---------------------------------------------------------------------------
# comexstat — export extraction
# ---------------------------------------------------------------------------


@pytest.fixture
def comexstat_export_response():
    return {
        "data": {
            "list": [
                {
                    "coNcm": "12019000",
                    "ncm": "Soja, exceto para semeadura",
                    "country": "China",
                    "state": "Mato Grosso",
                    "metricFOB": "404213999",
                    "metricKG": "797610684",
                },
                {
                    "coNcm": "10059010",
                    "ncm": "Milho em grão",
                    "country": "Irã",
                    "state": "Paraná",
                    "metricFOB": "120000000",
                    "metricKG": "500000000",
                },
            ]
        }
    }


def test_comexstat_extract_returns_dataframe(comexstat_export_response):
    from ingestion import comexstat

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = comexstat_export_response
    mock_resp.raise_for_status = MagicMock()

    # Patch sleep so the 12-month loop is instant; pass explicit ncm_codes.
    with patch("ingestion.comexstat.requests.post", return_value=mock_resp), patch(
        "ingestion.comexstat.time.sleep", return_value=None
    ):
        df = comexstat.extract_exports(2024, 2024, ncm_codes=["12019000", "10059010"])

    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == set(comexstat.WANTED_COLS)
    # 12 months x 2 rows (mock returns the same batch each month).
    assert len(df) == 24
    assert df["fob_usd"].dtype.kind in "if"  # numeric (int or float)
    assert df["ref_date"].iloc[0] == "2024-01"
    assert df["ref_date"].iloc[-1] == "2024-12"


def test_comexstat_empty_period(comexstat_export_response):
    from ingestion import comexstat

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"list": []}}
    mock_resp.raise_for_status = MagicMock()

    with patch("ingestion.comexstat.requests.post", return_value=mock_resp), patch(
        "ingestion.comexstat.time.sleep", return_value=None
    ):
        df = comexstat.extract_exports(2024, 2024, ncm_codes=["12019000"])

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    assert set(df.columns) == set(comexstat.WANTED_COLS)


# ---------------------------------------------------------------------------
# bcb
# ---------------------------------------------------------------------------


@pytest.fixture
def bcb_api_response():
    return [
        {"data": "01/01/2023", "valor": "5.2833"},
        {"data": "02/01/2023", "valor": "5.2991"},
        {"data": "03/01/2023", "valor": "5.3041"},
    ]


def test_bcb_extract_returns_dataframe(bcb_api_response):
    from ingestion import bcb

    mock_resp = MagicMock()
    mock_resp.json.return_value = bcb_api_response
    mock_resp.raise_for_status = MagicMock()

    with patch("ingestion.bcb.requests.get", return_value=mock_resp):
        df = bcb.extract_series(1, "01/01/2023", "03/01/2023")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert set(df.columns) == {"series_code", "series_name", "ref_date", "value"}
    assert df["series_name"].iloc[0] == "usd_brl"
    assert isinstance(df["ref_date"].iloc[0], date)


# ---------------------------------------------------------------------------
# commodity_prices (FRED)
# ---------------------------------------------------------------------------


@pytest.fixture
def fred_csv_bytes():
    # FRED fredgraph.csv: header + rows; "." marks a missing value.
    return (
        b"observation_date,PSOYBUSDM\n"
        b"2024-01-01,420.5\n"
        b"2024-02-01,431.2\n"
        b"2024-03-01,.\n"
    )


def test_commodity_prices_parses_fred(fred_csv_bytes):
    from ingestion import commodity_prices

    mock_resp = MagicMock()
    mock_resp.content = fred_csv_bytes
    mock_resp.raise_for_status = MagicMock()

    with patch("ingestion.commodity_prices.requests.get", return_value=mock_resp):
        df = commodity_prices.extract_prices("soja")

    assert set(df.columns) == {"commodity", "ref_date", "price", "unit", "fred_series", "source"}
    # The "." row is dropped → 2 valid observations.
    assert len(df) == 2
    assert df["commodity"].iloc[0] == "soja"
    assert df["unit"].iloc[0] == "USD/metric_ton"
    assert df["fred_series"].iloc[0] == "PSOYBUSDM"
    assert df["price"].iloc[0] == pytest.approx(420.5)
    assert isinstance(df["ref_date"].iloc[0], date)


def test_commodity_prices_invalid_commodity():
    from ingestion import commodity_prices

    with pytest.raises(ValueError, match="Unknown commodity"):
        commodity_prices.extract_prices("petroleo")
