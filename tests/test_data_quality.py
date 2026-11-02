"""
Tests for Data Quality audit and import pipeline.
Ensures questionable records (returned, zero quantity, missing values, duplicates)
are safely flagged and excluded from analytical calculations without crashing.
"""

import tempfile
from pathlib import Path
import pandas as pd
import pytest

from app.data_loader import import_csv_to_db, load_and_validate_csv
from app.database import get_db, init_db


@pytest.fixture
def temp_environment():
    """Create isolated temporary directory for test CSVs and test database."""
    temp_dir = tempfile.TemporaryDirectory()
    dir_path = Path(temp_dir.name)
    db_path = dir_path / "test_dq.db"
    init_db(db_path)

    yield dir_path, db_path

    temp_dir.cleanup()


def create_test_csv(file_path: Path, rows: list) -> Path:
    """Helper to generate a well-formed CSV file from row dictionaries."""
    df = pd.DataFrame(rows)
    df.to_csv(file_path, index=False)
    return file_path


def test_returned_transactions_flagged_and_excluded(temp_environment):
    """Verify that transactions marked 'Returned' are stored but flagged and excluded."""
    dir_path, db_path = temp_environment
    csv_file = dir_path / "test_returned.csv"

    rows = [
        {"Transaction_Id": "TXN_OK", "Order_date": "10-01-2026", "Product": "Desk", "Category": "Furniture", "Region": "North", "Sales_channel": "Online", "Quantity": 2, "Unit_price": 5000, "Discount_amount": 0, "Status": "Completed"},
        {"Transaction_Id": "TXN_RET", "Order_date": "12-01-2026", "Product": "Desk", "Category": "Furniture", "Region": "North", "Sales_channel": "Online", "Quantity": 1, "Unit_price": 5000, "Discount_amount": 0, "Status": "Returned"},
    ]
    create_test_csv(csv_file, rows)

    summary = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert summary["total_records"] == 2
    assert summary["valid_records"] == 1
    assert summary["flagged_records"] == 1

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_valid, data_quality_flag FROM sales_transactions WHERE transaction_id = 'TXN_RET';")
        row = cursor.fetchone()
        assert row["is_valid"] == 0
        assert "RETURNED_TRANSACTION" in row["data_quality_flag"]


def test_zero_quantity_flagged_and_excluded(temp_environment):
    """Verify that transactions with Quantity = 0 are flagged and excluded from revenue."""
    dir_path, db_path = temp_environment
    csv_file = dir_path / "test_zero_qty.csv"

    rows = [
        {"Transaction_Id": "TXN_ZERO", "Order_date": "10-01-2026", "Product": "Mouse", "Category": "Accessories", "Region": "South", "Sales_channel": "Online", "Quantity": 0, "Unit_price": 600, "Discount_amount": 0, "Status": "Completed"},
    ]
    create_test_csv(csv_file, rows)

    summary = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert summary["valid_records"] == 0
    assert summary["flagged_records"] == 1

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_valid, data_quality_flag FROM sales_transactions WHERE transaction_id = 'TXN_ZERO';")
        row = cursor.fetchone()
        assert row["is_valid"] == 0
        assert "ZERO_QUANTITY" in row["data_quality_flag"]


def test_negative_quantity_flagged(temp_environment):
    """Verify that negative quantities are detected and flagged."""
    dir_path, db_path = temp_environment
    csv_file = dir_path / "test_neg_qty.csv"

    rows = [
        {"Transaction_Id": "TXN_NEG", "Order_date": "10-01-2026", "Product": "Mouse", "Category": "Accessories", "Region": "South", "Sales_channel": "Online", "Quantity": -5, "Unit_price": 600, "Discount_amount": 0, "Status": "Completed"},
    ]
    create_test_csv(csv_file, rows)

    summary = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert summary["valid_records"] == 0
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_valid, data_quality_flag FROM sales_transactions WHERE transaction_id = 'TXN_NEG';")
        row = cursor.fetchone()
        assert row["is_valid"] == 0
        assert "NEGATIVE_QUANTITY" in row["data_quality_flag"]


def test_missing_unit_price_flagged(temp_environment):
    """Verify that null/missing unit prices are flagged and do not silently convert to 0."""
    dir_path, db_path = temp_environment
    csv_file = dir_path / "test_missing_price.csv"

    rows = [
        {"Transaction_Id": "TXN_NOPRICE", "Order_date": "10-01-2026", "Product": "Hub", "Category": "Accessories", "Region": "East", "Sales_channel": "Retail", "Quantity": 5, "Unit_price": None, "Discount_amount": 0, "Status": "Completed"},
    ]
    create_test_csv(csv_file, rows)

    summary = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert summary["valid_records"] == 0
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_valid, data_quality_flag, exclusion_reason FROM sales_transactions WHERE transaction_id = 'TXN_NOPRICE';")
        row = cursor.fetchone()
        assert row["is_valid"] == 0
        assert "MISSING_UNIT_PRICE" in row["data_quality_flag"]
        assert "Unit price is missing" in row["exclusion_reason"]


def test_duplicate_transaction_id_handling(temp_environment):
    """Verify that duplicate transaction IDs in the source data are flagged."""
    dir_path, db_path = temp_environment
    csv_file = dir_path / "test_dup.csv"

    rows = [
        {"Transaction_Id": "TXN_DUP", "Order_date": "01-01-2026", "Product": "Chair", "Category": "Furniture", "Region": "West", "Sales_channel": "Online", "Quantity": 2, "Unit_price": 5000, "Discount_amount": 0, "Status": "Completed"},
        {"Transaction_Id": "TXN_DUP", "Order_date": "02-01-2026", "Product": "Chair", "Category": "Furniture", "Region": "West", "Sales_channel": "Online", "Quantity": 2, "Unit_price": 5000, "Discount_amount": 0, "Status": "Completed"},
    ]
    create_test_csv(csv_file, rows)

    summary = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert summary["total_records"] == 2
    # Second occurrence must be flagged as duplicate
    assert summary["flagged_records"] >= 1


def test_discount_exceeds_gross_flagged(temp_environment):
    """Verify that discounts larger than gross revenue are flagged as invalid."""
    dir_path, db_path = temp_environment
    csv_file = dir_path / "test_high_discount.csv"

    rows = [
        # Gross = 2 * 100 = 200, but discount = 500
        {"Transaction_Id": "TXN_OVERDISC", "Order_date": "05-01-2026", "Product": "Mouse", "Category": "Accessories", "Region": "West", "Sales_channel": "Online", "Quantity": 2, "Unit_price": 100, "Discount_amount": 500, "Status": "Completed"},
    ]
    create_test_csv(csv_file, rows)

    summary = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert summary["valid_records"] == 0
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_valid, data_quality_flag FROM sales_transactions WHERE transaction_id = 'TXN_OVERDISC';")
        row = cursor.fetchone()
        assert row["is_valid"] == 0
        assert "DISCOUNT_EXCEEDS_GROSS" in row["data_quality_flag"]


def test_invalid_date_flagged(temp_environment):
    """Verify that unparseable date strings are flagged."""
    dir_path, db_path = temp_environment
    csv_file = dir_path / "test_bad_date.csv"

    rows = [
        {"Transaction_Id": "TXN_BADDATE", "Order_date": "not-a-valid-date", "Product": "Mouse", "Category": "Accessories", "Region": "West", "Sales_channel": "Online", "Quantity": 2, "Unit_price": 100, "Discount_amount": 0, "Status": "Completed"},
    ]
    create_test_csv(csv_file, rows)

    summary = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert summary["valid_records"] == 0
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_valid, data_quality_flag FROM sales_transactions WHERE transaction_id = 'TXN_BADDATE';")
        row = cursor.fetchone()
        assert row["is_valid"] == 0
        assert "INVALID_DATE" in row["data_quality_flag"]


def test_missing_required_column_raises_error(temp_environment):
    """Verify that importing a CSV missing required schema columns fails with clear error."""
    dir_path, _ = temp_environment
    csv_file = dir_path / "test_missing_col.csv"

    # Missing 'Unit_price' column entirely
    rows = [
        {"Transaction_Id": "T1", "Order_date": "01-01-2026", "Product": "Chair", "Category": "Furniture", "Region": "West", "Sales_channel": "Online", "Quantity": 2, "Status": "Completed"},
    ]
    create_test_csv(csv_file, rows)

    with pytest.raises(ValueError) as excinfo:
        load_and_validate_csv(csv_file)
    assert "missing required columns" in str(excinfo.value).lower()


def test_import_idempotency(temp_environment):
    """Verify that re-importing the same CSV without changes does not duplicate rows."""
    dir_path, db_path = temp_environment
    csv_file = dir_path / "test_idempotency.csv"

    rows = [
        {"Transaction_Id": "TXN_A", "Order_date": "10-01-2026", "Product": "Desk", "Category": "Furniture", "Region": "North", "Sales_channel": "Online", "Quantity": 2, "Unit_price": 5000, "Discount_amount": 0, "Status": "Completed"},
    ]
    create_test_csv(csv_file, rows)

    res1 = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert res1["status"] == "success"

    # Second import must recognize already imported file
    res2 = import_csv_to_db(csv_path=csv_file, db_path=db_path)
    assert res2["status"] == "already_imported"

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM sales_transactions;")
        assert cursor.fetchone()["cnt"] == 1
