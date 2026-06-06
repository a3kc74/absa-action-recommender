from pathlib import Path
import duckdb

DB_PATH = Path("data/local.duckdb")

# Delete child/dependent tables first, then dimension/source tables.
TABLE_ORDER = [
    "priority_items",
    "priority_runs",
    "peer_aspect_monthly_stats",
    "aspect_monthly_stats",
    "absa_annotations",
    "reviews",
    "crawl_runs",
    "restaurants",
]

con = duckdb.connect(str(DB_PATH))
existing_tables = {
    row[0]
    for row in con.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_type = 'BASE TABLE'
        """
    ).fetchall()
}

print(f"DB: {DB_PATH}")
print("Before:")
for table in sorted(existing_tables):
    count = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print(f"  {table}: {count}")

con.execute("BEGIN TRANSACTION")
try:
    for table in TABLE_ORDER:
        if table in existing_tables:
            con.execute(f'DELETE FROM "{table}"')
    # Clear any remaining base tables not listed above.
    for table in sorted(existing_tables - set(TABLE_ORDER)):
        con.execute(f'DELETE FROM "{table}"')
    con.execute("COMMIT")
except Exception:
    con.execute("ROLLBACK")
    raise

con.execute("CHECKPOINT")

print("After:")
for table in sorted(existing_tables):
    count = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print(f"  {table}: {count}")

con.close()