# 🌎 AgriExport Intelligence

> End-to-end analytics-engineering pipeline tracking Brazilian agribusiness exports —
> from public APIs to a tested cloud warehouse to a live dashboard.

**[▶ Live dashboard](dashboards/README.md)** ·
**[Architecture](docs/architecture.md)**

[![CI](https://github.com/caiogoia123/agriexport-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/caiogoia123/agriexport-intelligence/actions/workflows/ci.yml)

---

## The business question

**Where are the risk and the opportunity in Brazil's agri-exports?**

- **Market concentration** — how exposed is each commodity to a few buyers? (HHI, top-5 share)
- **Product competitiveness** — is Brazil's implied export price (US$/ton) keeping up with the
  underlying commodity price (CEPEA)?
- **What drives export value** — how much of the FOB swing is *price* vs *FX (USD/BRL)* vs *volume*?

These map to real decisions: market diversification, product mix, and FX hedging.

## Key findings

- 📌 _(insight 1 — with a number)_
- 📌 _(insight 2)_
- 📌 _(insight 3)_

## How it works

Public APIs (Comex Stat, BCB, CEPEA) → Python ingestion → **BigQuery** → **dbt**
(staging → marts, star schema, tested) → **Power BI** + **Looker Studio**, automated with
**GitHub Actions**. Full diagram in [docs/architecture.md](docs/architecture.md).

## Repository layout

| Folder | What's inside |
|---|---|
| [`ingestion/`](ingestion/) | Python scripts that pull raw data from the public APIs |
| [`dbt/`](dbt/) | SQL transformations: `staging/` → `marts/` (star schema) + tests |
| [`dashboards/`](dashboards/) | Power BI file + link to the public Looker Studio dashboard |
| [`docs/`](docs/) | Architecture diagram and data model |

## Quickstart

```bash
# 1. Environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Transform locally with DuckDB (no cloud account needed)
cp dbt/profiles.example.yml ~/.dbt/profiles.yml
cd dbt && dbt deps && dbt build --target dev
```

Stack: `Python` · `BigQuery` · `dbt` · `DuckDB` (dev) · `GitHub Actions` · `Power BI` · `Looker Studio`.

## License

MIT — see [LICENSE](LICENSE).
