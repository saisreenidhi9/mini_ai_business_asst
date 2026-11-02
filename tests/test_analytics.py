"""
Unit and integration tests for analytical queries and calculations.
Validates business logic against an isolated test SQLite database.
"""

import sqlite3
import pytest
from pathlib import Path
import tempfile

from app.database import init_db
from app.analytics import (
    AnalyticsValueError,
    get_total_revenue,
    get_highest_revenue_product,
    get_monthly_revenue_trend,
    get_highest_sales_region,
    get_revenue_change_between_months,
    get_data_quality_notes,
)


@pytest.fixture
def test_db():
    """Create a temporary isolated SQLite database with controlled fixture records."""
    temp_dir = tempfile.TemporaryDirectory()
    db_file = Path(temp_dir.name) / "test_analytics.db"
    init_db(db_file)

    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row

    # Insert sample valid and flagged records
    # Valid completed sales:
    # 1. Product A, Region North, 2026-01: Qty 10, Price 100, Disc 50 -> Net: (10*100) - 50 = 950
    # 2. Product B, Region South, 2026-01: Qty 20, Price 50, Disc 0   -> Net: (20*50) - 0 = 1000
    # 3. Product A, Region South, 2026-02: Qty 15, Price 100, Disc 100 -> Net: (15*100) - 100 = 1400
    # 4. Product C, Region West,  2026-02: Qty 5,  Price 200, Disc 0   -> Net: (5*200) - 0 = 1000
    # Total Valid Net: 950 + 1000 + 1400 + 1000 = 4350.0
    # Total Valid Gross: 1000 + 1000 + 1500 + 1000 = 4500.0
    # Total Valid Disc: 50 + 0 + 100 + 0 = 150.0
    # Total Valid Units: 10 + 20 + 15 + 5 = 50

    # Flagged records (excluded):
    # 5. Returned txn
    # 6. Zero quantity txn
    # 7. Null unit price txn

    records = [
        ("T1", "05-01-2026", "2026-01-05", 2026, 1, "2026-01", "Product A", "Accessories", "North", "Online", 10, 100.0, 50.0, "Completed", 1000.0, 950.0, 1, "VALID", None),
        ("T2", "15-01-2026", "2026-01-15", 2026, 1, "2026-01", "Product B", "Accessories", "South", "Retail", 20, 50.0, 0.0, "Completed", 1000.0, 1000.0, 1, "VALID", None),
        ("T3", "10-02-2026", "2026-02-10", 2026, 2, "2026-02", "Product A", "Accessories", "South", "Online", 15, 100.0, 100.0, "Completed", 1500.0, 1400.0, 1, "VALID", None),
        ("T4", "20-02-2026", "2026-02-20", 2026, 2, "2026-02", "Product C", "Furniture", "West", "Retail", 5, 200.0, 0.0, "Completed", 1000.0, 1000.0, 1, "VALID", None),
        ("T5", "25-02-2026", "2026-02-25", 2026, 2, "2026-02", "Product A", "Accessories", "North", "Retail", 2, 100.0, 0.0, "Returned", 200.0, 200.0, 0, "RETURNED_TRANSACTION", "Status is Returned"),
        ("T6", "28-02-2026", "2026-02-28", 2026, 2, "2026-02", "Product B", "Accessories", "East", "Online", 0, 50.0, 0.0, "Completed", 0.0, 0.0, 0, "ZERO_QUANTITY", "Quantity is 0"),
        ("T7", "01-03-2026", "2026-03-01", 2026, 3, "2026-03", "Product C", "Furniture", "South", "Online", 4, None, 0.0, "Completed", 0.0, 0.0, 0, "MISSING_UNIT_PRICE", "Unit price is missing"),
    ]

    conn.executemany(
        """
        INSERT INTO sales_transactions (
            transaction_id, order_date_raw, order_date_iso, order_year, order_month,
            year_month, product, category, region, sales_channel, quantity,
            unit_price, discount_amount, status, gross_revenue, net_revenue,
            is_valid, data_quality_flag, exclusion_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        records,
    )
    conn.commit()

    yield conn

    conn.close()
    temp_dir.cleanup()


def test_total_revenue_calculation(test_db):
    """Test Question 1: Total net revenue matches documented formula and excludes flagged rows."""
    res = get_total_revenue(test_db)
    assert res["net_revenue"] == 4350.0
    assert res["gross_revenue"] == 4500.0
    assert res["total_discounts"] == 150.0
    assert res["units_sold"] == 50
    assert res["valid_transactions"] == 4
    assert res["excluded_records"] == 3


def test_highest_revenue_product(test_db):
    """Test Question 2: Highest revenue product correctly identified with rankings."""
    res = get_highest_revenue_product(test_db)
    # Product A generated: 950 + 1400 = 2350.0
    # Product B: 1000.0
    # Product C: 1000.0
    assert res["top_product"] == "Product A"
    assert res["top_product_net_revenue"] == 2350.0
    assert res["top_product_units"] == 25
    # Product A is top by revenue; check ranking order
    ranks = res["supporting_data"]
    assert ranks[0]["product"] == "Product A"
    assert ranks[0]["net_revenue"] == 2350.0


def test_monthly_revenue_trend(test_db):
    """Test Question 3: Monthly revenue aggregation in chronological order."""
    res = get_monthly_revenue_trend(test_db)
    assert res["months"] == ["2026-01", "2026-02"]
    # 2026-01: 950 + 1000 = 1950.0
    # 2026-02: 1400 + 1000 = 2400.0
    trend = res["supporting_data"]
    assert trend[0]["year_month"] == "2026-01"
    assert trend[0]["net_revenue"] == 1950.0
    assert trend[1]["year_month"] == "2026-02"
    assert trend[1]["net_revenue"] == 2400.0
    assert res["peak_month"] == "February 2026"
    assert res["peak_revenue"] == 2400.0


def test_highest_sales_region(test_db):
    """Test Question 4: Highest performing region by net revenue and units sold."""
    res = get_highest_sales_region(test_db)
    # North: 950.0 (10 units)
    # South: 1000.0 + 1400.0 = 2400.0 (35 units)
    # West: 1000.0 (5 units)
    assert res["top_region_by_revenue"] == "South"
    assert res["top_revenue"] == 2400.0
    assert res["top_region_by_units"] == "South"
    assert res["top_units"] == 35


def test_revenue_change_between_months_increase(test_db):
    """Test Question 5: Month-to-month comparison showing growth."""
    res = get_revenue_change_between_months(test_db, "January", "February")
    # Jan = 1950.0, Feb = 2400.0
    # Absolute change = 2400 - 1950 = 450.0
    # Pct change = (450 / 1950) * 100 = 23.08%
    assert res["month1_revenue"] == 1950.0
    assert res["month2_revenue"] == 2400.0
    assert res["absolute_change"] == 450.0
    assert res["percentage_change"] == pytest.approx(23.08, 0.01)
    assert res["direction"] == "increased"


def test_revenue_change_between_months_decrease(test_db):
    """Test Question 5: Month-to-month comparison showing decline."""
    res = get_revenue_change_between_months(test_db, "February", "January")
    assert res["absolute_change"] == -450.0
    assert res["percentage_change"] == pytest.approx(-18.75, 0.01)
    assert res["direction"] == "decreased"


def test_revenue_change_zero_baseline():
    """Test safe handling when baseline month revenue is zero."""
    temp_dir = tempfile.TemporaryDirectory()
    db_file = Path(temp_dir.name) / "test_zero_base.db"
    init_db(db_file)
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row

    # Month 1 has 0 net revenue, Month 2 has 500
    conn.execute(
        """
        INSERT INTO sales_transactions (
            transaction_id, order_date_raw, order_date_iso, order_year, order_month,
            year_month, product, category, region, sales_channel, quantity,
            unit_price, discount_amount, status, gross_revenue, net_revenue,
            is_valid, data_quality_flag, exclusion_reason
        ) VALUES 
        ('Z1', '01-01-2026', '2026-01-01', 2026, 1, '2026-01', 'P', 'C', 'N', 'O', 1, 100.0, 100.0, 'Completed', 100.0, 0.0, 1, 'VALID', NULL),
        ('Z2', '01-02-2026', '2026-02-01', 2026, 2, '2026-02', 'P', 'C', 'N', 'O', 5, 100.0, 0.0, 'Completed', 500.0, 500.0, 1, 'VALID', NULL);
        """
    )
    conn.commit()

    res = get_revenue_change_between_months(conn, "2026-01", "2026-02")
    assert res["month1_revenue"] == 0.0
    assert res["month2_revenue"] == 500.0
    assert res["absolute_change"] == 500.0
    # Zero baseline must not throw ZeroDivisionError; pct_change should be None
    assert res["percentage_change"] is None

    conn.close()
    temp_dir.cleanup()


def test_revenue_change_invalid_month(test_db):
    """Test error handling when requested month is not in the dataset."""
    with pytest.raises(AnalyticsValueError) as excinfo:
        get_revenue_change_between_months(test_db, "January", "December")
    assert "Month 'December' is not present in the dataset" in str(excinfo.value)


def test_data_quality_disclosures(test_db):
    """Test that data quality exclusions are properly retrieved and disclosed."""
    notes = get_data_quality_notes(test_db)
    assert len(notes) >= 3
    # Check that T5 (Returned), T6 (Zero quantity), T7 (Missing price) are listed
    combined_notes = " ".join(notes)
    assert "T5" in combined_notes
    assert "T6" in combined_notes
    assert "T7" in combined_notes
