from app import config, tools


def test_select_returns_rows():
    out = tools.run_sql(config.DB_PATH, "SELECT COUNT(*) AS n FROM products")
    assert out.splitlines() == ["n", "16"]


def test_writes_are_rejected():
    assert tools.run_sql(config.DB_PATH, "DELETE FROM orders").startswith("ERROR")
    # Even if a write sneaks past the SELECT check, the connection is read-only.
    assert "readonly" in tools.run_sql(config.DB_PATH, "WITH x AS (SELECT 1) DELETE FROM orders").lower()


def test_sql_errors_are_returned_not_raised():
    assert tools.run_sql(config.DB_PATH, "SELECT nope FROM orders").startswith("ERROR")


def test_schema_lists_tables():
    schema = tools.describe_schema(config.DB_PATH)
    for table in ["customers", "products", "orders", "order_items", "refunds"]:
        assert f"CREATE TABLE {table}" in schema
