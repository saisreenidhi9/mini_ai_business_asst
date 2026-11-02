"""
Data loading and quality validation pipeline.
Imports CSV transaction data into SQLite while enforcing business data quality policies.
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.config import settings
from app.database import get_db, init_db


REQUIRED_COLUMNS = [
    "Transaction_Id",
    "Order_date",
    "Product",
    "Category",
    "Region",
    "Sales_channel",
    "Quantity",
    "Unit_price",
    "Discount_amount",
    "Status",
]


def find_csv_file(data_dir: Path | str | None = None) -> Path:
    """
    Locate the authoritative CSV data source inside data directory.
    Does not assume a fixed filename; inspects files in data/.
    """
    dir_path = Path(data_dir) if data_dir else settings.DATA_DIR
    if not dir_path.exists():
        raise FileNotFoundError(f"Data directory does not exist: {dir_path}")

    csv_files = sorted(list(dir_path.glob("*.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No CSV file found in data directory: {dir_path}")

    # If multiple CSVs exist, prefer 'sales' or take the first
    for f in csv_files:
        if "sales" in f.name.lower():
            return f
    return csv_files[0]


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file for change detection and idempotency."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def parse_order_date(date_str: Any) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    """
    Parse date string into ISO date (YYYY-MM-DD), year, month, and year_month (YYYY-MM).
    Supports DD-MM-YYYY, YYYY-MM-DD, and DD/MM/YYYY formats.
    """
    if pd.isna(date_str) or not str(date_str).strip():
        return None, None, None, None

    date_str_clean = str(date_str).strip()
    formats_to_try = [
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(date_str_clean, fmt)
            iso_date = dt.strftime("%Y-%m-%d")
            year = dt.year
            month = dt.month
            year_month = dt.strftime("%Y-%m")
            return iso_date, year, month, year_month
        except ValueError:
            continue

    return None, None, None, None


def load_and_validate_csv(csv_path: Path) -> pd.DataFrame:
    """
    Read CSV file and validate that required schema columns are present.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # Normalize column names: trim whitespace
    df.columns = [c.strip() for c in df.columns]

    # Validate required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"CSV file '{csv_path.name}' is missing required columns: {missing_cols}. "
            f"Available columns: {list(df.columns)}"
        )

    return df


def import_csv_to_db(
    csv_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
    force_reimport: bool = False,
) -> Dict[str, Any]:
    """
    Import transactions from CSV into SQLite with full data-quality audit.
    Prevents duplicate re-imports unless force_reimport is True.
    Preserves all records in SQLite while flagging questionable records.
    """
    init_db(db_path)
    target_csv = csv_path if csv_path else find_csv_file()
    file_hash = calculate_file_hash(target_csv)

    # Check if already imported
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, total_records, valid_records, flagged_records FROM import_history WHERE file_hash = ? ORDER BY id DESC LIMIT 1;",
            (file_hash,),
        )
        existing_import = cursor.fetchone()

        if existing_import and not force_reimport:
            # Check row count in sales_transactions
            cursor.execute("SELECT COUNT(*) AS cnt FROM sales_transactions;")
            row_count = cursor.fetchone()["cnt"]
            if row_count > 0:
                cursor.execute(
                    "SELECT transaction_id, data_quality_flag, exclusion_reason FROM sales_transactions WHERE is_valid = 0;"
                )
                flagged_rows = [
                    {
                        "transaction_id": r["transaction_id"],
                        "flag": r["data_quality_flag"],
                        "reason": r["exclusion_reason"],
                    }
                    for r in cursor.fetchall()
                ]
                return {
                    "status": "already_imported",
                    "filename": target_csv.name,
                    "file_hash": file_hash,
                    "total_records": existing_import["total_records"],
                    "valid_records": existing_import["valid_records"],
                    "flagged_records": existing_import["flagged_records"],
                    "flagged_details": flagged_rows,
                }

    # Load and validate raw CSV
    df = load_and_validate_csv(target_csv)

    processed_records: List[Dict[str, Any]] = []
    seen_transaction_ids = set()
    valid_count = 0
    flagged_count = 0
    flagged_details: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        raw_txn_id = str(row["Transaction_Id"]).strip() if pd.notna(row["Transaction_Id"]) else f"MISSING_{idx}"
        raw_order_date = str(row["Order_date"]).strip() if pd.notna(row["Order_date"]) else ""
        raw_product = str(row["Product"]).strip() if pd.notna(row["Product"]) else None
        raw_category = str(row["Category"]).strip() if pd.notna(row["Category"]) else None
        raw_region = str(row["Region"]).strip() if pd.notna(row["Region"]) else None
        raw_channel = str(row["Sales_channel"]).strip() if pd.notna(row["Sales_channel"]) else None
        raw_status = str(row["Status"]).strip() if pd.notna(row["Status"]) else "Unknown"

        # Safe parsing of numeric values
        try:
            quantity_val = int(row["Quantity"]) if pd.notna(row["Quantity"]) else None
        except (ValueError, TypeError):
            quantity_val = None

        try:
            unit_price_val = float(row["Unit_price"]) if pd.notna(row["Unit_price"]) else None
        except (ValueError, TypeError):
            unit_price_val = None

        try:
            discount_val = float(row["Discount_amount"]) if pd.notna(row["Discount_amount"]) else 0.0
        except (ValueError, TypeError):
            discount_val = 0.0

        iso_date, order_year, order_month, year_month = parse_order_date(raw_order_date)

        # Evaluate Data Quality Rules
        is_valid = 1
        flags: List[str] = []
        reasons: List[str] = []

        # Duplicate ID check
        if raw_txn_id in seen_transaction_ids:
            is_valid = 0
            flags.append("DUPLICATE_TRANSACTION_ID")
            reasons.append(f"Duplicate Transaction ID '{raw_txn_id}' found in dataset")
        else:
            seen_transaction_ids.add(raw_txn_id)

        # Date validity check
        if not iso_date:
            is_valid = 0
            flags.append("INVALID_DATE")
            reasons.append(f"Unparseable or missing order date: '{raw_order_date}'")

        # Missing required dimensional fields
        if not raw_product:
            is_valid = 0
            flags.append("MISSING_PRODUCT")
            reasons.append("Missing product name")

        if not raw_region:
            is_valid = 0
            flags.append("MISSING_REGION")
            reasons.append("Missing region identifier")

        # Returned status check
        if raw_status.lower() == "returned":
            is_valid = 0
            flags.append("RETURNED_TRANSACTION")
            reasons.append("Transaction was returned; excluded from completed-sales revenue")

        # Quantity checks
        if quantity_val is None:
            is_valid = 0
            flags.append("NON_NUMERIC_QUANTITY")
            reasons.append("Quantity is missing or non-numeric")
        elif quantity_val == 0:
            is_valid = 0
            flags.append("ZERO_QUANTITY")
            reasons.append("Quantity is 0; not an ordinary sales transaction")
        elif quantity_val < 0:
            is_valid = 0
            flags.append("NEGATIVE_QUANTITY")
            reasons.append(f"Quantity is negative ({quantity_val})")

        # Unit price checks
        if unit_price_val is None:
            is_valid = 0
            flags.append("MISSING_UNIT_PRICE")
            reasons.append("Unit price is missing or null; cannot calculate revenue")
        elif unit_price_val < 0:
            is_valid = 0
            flags.append("NEGATIVE_UNIT_PRICE")
            reasons.append(f"Unit price is negative ({unit_price_val})")

        # Discount checks
        if discount_val < 0:
            is_valid = 0
            flags.append("NEGATIVE_DISCOUNT")
            reasons.append(f"Discount amount cannot be negative ({discount_val})")

        # Revenue computation
        if quantity_val is not None and unit_price_val is not None and quantity_val > 0 and unit_price_val > 0:
            gross_revenue = float(quantity_val * unit_price_val)
            net_revenue = float(gross_revenue - discount_val)
            if discount_val > gross_revenue:
                is_valid = 0
                flags.append("DISCOUNT_EXCEEDS_GROSS")
                reasons.append(f"Discount ({discount_val}) exceeds gross revenue ({gross_revenue})")
        else:
            gross_revenue = 0.0
            net_revenue = 0.0

        if is_valid == 1:
            data_quality_flag = "VALID"
            exclusion_reason = None
            valid_count += 1
        else:
            data_quality_flag = "|".join(flags)
            exclusion_reason = "; ".join(reasons)
            flagged_count += 1
            flagged_details.append(
                {
                    "transaction_id": raw_txn_id,
                    "order_date": raw_order_date,
                    "product": raw_product,
                    "quantity": quantity_val,
                    "unit_price": unit_price_val,
                    "status": raw_status,
                    "flag": data_quality_flag,
                    "reason": exclusion_reason,
                }
            )

        processed_records.append(
            {
                "transaction_id": raw_txn_id,
                "order_date_raw": raw_order_date,
                "order_date_iso": iso_date,
                "order_year": order_year,
                "order_month": order_month,
                "year_month": year_month,
                "product": raw_product,
                "category": raw_category,
                "region": raw_region,
                "sales_channel": raw_channel,
                "quantity": quantity_val,
                "unit_price": unit_price_val,
                "discount_amount": discount_val,
                "status": raw_status,
                "gross_revenue": gross_revenue,
                "net_revenue": net_revenue,
                "is_valid": is_valid,
                "data_quality_flag": data_quality_flag,
                "exclusion_reason": exclusion_reason,
            }
        )

    # Insert into database using parameterized queries inside a transaction
    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # Insert or replace transactions
        cursor.executemany(
            """
            INSERT OR REPLACE INTO sales_transactions (
                transaction_id, order_date_raw, order_date_iso, order_year, order_month,
                year_month, product, category, region, sales_channel, quantity,
                unit_price, discount_amount, status, gross_revenue, net_revenue,
                is_valid, data_quality_flag, exclusion_reason
            ) VALUES (
                :transaction_id, :order_date_raw, :order_date_iso, :order_year, :order_month,
                :year_month, :product, :category, :region, :sales_channel, :quantity,
                :unit_price, :discount_amount, :status, :gross_revenue, :net_revenue,
                :is_valid, :data_quality_flag, :exclusion_reason
            );
            """,
            processed_records,
        )

        # Log import record
        cursor.execute(
            """
            INSERT INTO import_history (filename, file_hash, total_records, valid_records, flagged_records)
            VALUES (?, ?, ?, ?, ?);
            """,
            (target_csv.name, file_hash, len(df), valid_count, flagged_count),
        )

    return {
        "status": "success",
        "filename": target_csv.name,
        "file_hash": file_hash,
        "total_records": len(df),
        "valid_records": valid_count,
        "flagged_records": flagged_count,
        "flagged_details": flagged_details,
    }
