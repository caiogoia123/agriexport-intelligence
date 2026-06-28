import duckdb

con = duckdb.connect("data/dev.duckdb", read_only=True)

query = """
SELECT * FROM raw.comexstat_exports LIMIT 10
"""

# query = """
# SELECT * FROM raw.ncm_reference LIMIT 10
# """

# query = """
# SELECT * FROM raw.bcb_series LIMIT 10
# """

# query = """
# SELECT * FROM raw.commodity_prices LIMIT 10
# """

con.sql(query).show(max_width=120)
