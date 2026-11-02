"""
Deterministic SQL analytics engine for business intelligence calculations.
Executes parameterized queries against SQLite to compute accurate metrics.
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple


class AnalyticsValueError(ValueError):
    """Raised when analytical parameters (e.g. month names) are invalid or not found."""
    pass


def get_data_quality_notes(conn: sqlite3.Connection) -> List[str]:
    """Retrieve standard data quality notes explaining excluded records."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT transaction_id, data_quality_flag, exclusion_reason
        FROM sales_transactions
        WHERE is_valid = 0
        ORDER BY transaction_id ASC;
        """
    )
    rows = cursor.fetchall()
    notes: List[str] = []
    if rows:
        notes.append(
            f"{len(rows)} record(s) excluded from completed sales calculations to maintain data integrity:"
        )
        for r in rows:
            notes.append(
                f"• {r['transaction_id']}: {r['exclusion_reason']} (Flag: {r['data_quality_flag']})"
            )
    return notes


def get_total_revenue(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Calculate total net revenue, gross sales, discounts, and transaction volume
    for all valid, completed sales transactions.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            COUNT(*) AS valid_txn_count,
            COALESCE(SUM(quantity), 0) AS total_units_sold,
            COALESCE(SUM(gross_revenue), 0.0) AS total_gross_revenue,
            COALESCE(SUM(discount_amount), 0.0) AS total_discounts,
            COALESCE(SUM(net_revenue), 0.0) AS total_net_revenue
        FROM sales_transactions
        WHERE is_valid = 1;
        """
    )
    res = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) AS total_txns FROM sales_transactions;")
    total_txns = cursor.fetchone()["total_txns"]
    excluded_count = total_txns - res["valid_txn_count"]

    supporting_data = [
        {"metric": "Total Net Revenue", "amount": round(res["total_net_revenue"], 2), "unit": "currency units"},
        {"metric": "Total Gross Sales", "amount": round(res["total_gross_revenue"], 2), "unit": "currency units"},
        {"metric": "Total Discounts Given", "amount": round(res["total_discounts"], 2), "unit": "currency units"},
        {"metric": "Total Units Sold", "amount": res["total_units_sold"], "unit": "units"},
        {"metric": "Eligible Completed Transactions", "amount": res["valid_txn_count"], "unit": "transactions"},
        {"metric": "Excluded Questionable Records", "amount": excluded_count, "unit": "records"},
    ]

    return {
        "net_revenue": round(res["total_net_revenue"], 2),
        "gross_revenue": round(res["total_gross_revenue"], 2),
        "total_discounts": round(res["total_discounts"], 2),
        "units_sold": res["total_units_sold"],
        "valid_transactions": res["valid_txn_count"],
        "excluded_records": excluded_count,
        "supporting_data": supporting_data,
        "data_quality_notes": get_data_quality_notes(conn),
    }


def get_highest_revenue_product(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Calculate revenue grouped by product.
    Returns the highest-revenue product and full ranked competing product table.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            product,
            category,
            COUNT(*) AS transaction_count,
            SUM(quantity) AS units_sold,
            SUM(gross_revenue) AS gross_revenue,
            SUM(discount_amount) AS total_discounts,
            SUM(net_revenue) AS net_revenue
        FROM sales_transactions
        WHERE is_valid = 1
        GROUP BY product, category
        ORDER BY net_revenue DESC;
        """
    )
    rows = [dict(r) for r in cursor.fetchall()]
    if not rows:
        raise AnalyticsValueError("No valid transactions found in database.")

    total_net = sum(r["net_revenue"] for r in rows)
    top_product = rows[0]

    # Find highest by units sold for comparison
    highest_units_product = max(rows, key=lambda x: x["units_sold"])

    supporting_data = []
    for rank, r in enumerate(rows, 1):
        share_pct = round((r["net_revenue"] / total_net * 100), 2) if total_net > 0 else 0.0
        supporting_data.append(
            {
                "rank": rank,
                "product": r["product"],
                "category": r["category"],
                "net_revenue": round(r["net_revenue"], 2),
                "revenue_share_pct": share_pct,
                "units_sold": r["units_sold"],
                "transaction_count": r["transaction_count"],
            }
        )

    chart = {
        "chart_type": "bar",
        "title": "Net Revenue by Product",
        "labels": [r["product"] for r in rows],
        "datasets": [
            {
                "label": "Net Revenue",
                "data": [round(r["net_revenue"], 2) for r in rows],
                "backgroundColor": "rgba(99, 102, 241, 0.8)",
                "borderColor": "rgb(99, 102, 241)",
                "borderWidth": 1,
            }
        ],
    }

    return {
        "top_product": top_product["product"],
        "top_product_net_revenue": round(top_product["net_revenue"], 2),
        "top_product_units": top_product["units_sold"],
        "top_product_category": top_product["category"],
        "highest_units_product": highest_units_product["product"],
        "highest_units_sold": highest_units_product["units_sold"],
        "total_catalog_revenue": round(total_net, 2),
        "supporting_data": supporting_data,
        "chart": chart,
        "data_quality_notes": get_data_quality_notes(conn),
    }


def get_monthly_revenue_trend(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Group eligible transactions chronologically by calendar month.
    Computes monthly net revenue, gross revenue, discounts, units sold, and growth rates.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            year_month,
            order_year,
            order_month,
            COUNT(*) AS transaction_count,
            SUM(quantity) AS units_sold,
            SUM(gross_revenue) AS gross_revenue,
            SUM(discount_amount) AS total_discounts,
            SUM(net_revenue) AS net_revenue
        FROM sales_transactions
        WHERE is_valid = 1
        GROUP BY year_month, order_year, order_month
        ORDER BY year_month ASC;
        """
    )
    rows = [dict(r) for r in cursor.fetchall()]
    if not rows:
        raise AnalyticsValueError("No valid transactions found in database.")

    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    supporting_data = []
    prev_revenue = None

    for r in rows:
        month_label = f"{month_names.get(r['order_month'], r['order_month'])} {r['order_year']}"
        net_rev = round(r["net_revenue"], 2)

        if prev_revenue is not None and prev_revenue > 0:
            growth_pct = round(((net_rev - prev_revenue) / prev_revenue) * 100, 2)
        else:
            growth_pct = None

        supporting_data.append(
            {
                "year_month": r["year_month"],
                "month_label": month_label,
                "net_revenue": net_rev,
                "gross_revenue": round(r["gross_revenue"], 2),
                "discounts": round(r["total_discounts"], 2),
                "units_sold": r["units_sold"],
                "transaction_count": r["transaction_count"],
                "mom_growth_pct": growth_pct,
            }
        )
        prev_revenue = net_rev

    # Peak and lowest month identification
    peak_month = max(supporting_data, key=lambda x: x["net_revenue"])
    lowest_month = min(supporting_data, key=lambda x: x["net_revenue"])

    chart = {
        "chart_type": "line",
        "title": "Monthly Net Revenue Trend (2026)",
        "labels": [item["month_label"] for item in supporting_data],
        "datasets": [
            {
                "label": "Net Revenue",
                "data": [item["net_revenue"] for item in supporting_data],
                "borderColor": "rgb(16, 185, 129)",
                "backgroundColor": "rgba(16, 185, 129, 0.15)",
                "borderWidth": 3,
                "tension": 0.25,
                "fill": True,
            }
        ],
    }

    return {
        "months": [item["year_month"] for item in supporting_data],
        "peak_month": peak_month["month_label"],
        "peak_revenue": peak_month["net_revenue"],
        "lowest_month": lowest_month["month_label"],
        "lowest_revenue": lowest_month["net_revenue"],
        "supporting_data": supporting_data,
        "chart": chart,
        "data_quality_notes": get_data_quality_notes(conn),
    }


def get_highest_sales_region(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Calculate performance grouped by region.
    Discloses both net revenue and units sold metrics explicitly.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            region,
            COUNT(*) AS transaction_count,
            SUM(quantity) AS units_sold,
            SUM(gross_revenue) AS gross_revenue,
            SUM(discount_amount) AS total_discounts,
            SUM(net_revenue) AS net_revenue
        FROM sales_transactions
        WHERE is_valid = 1
        GROUP BY region
        ORDER BY net_revenue DESC;
        """
    )
    rows = [dict(r) for r in cursor.fetchall()]
    if not rows:
        raise AnalyticsValueError("No valid transactions found in database.")

    total_net = sum(r["net_revenue"] for r in rows)
    total_units = sum(r["units_sold"] for r in rows)

    top_by_revenue = rows[0]
    top_by_units = max(rows, key=lambda x: x["units_sold"])

    supporting_data = []
    for rank, r in enumerate(rows, 1):
        rev_share = round((r["net_revenue"] / total_net * 100), 2) if total_net > 0 else 0.0
        unit_share = round((r["units_sold"] / total_units * 100), 2) if total_units > 0 else 0.0
        supporting_data.append(
            {
                "rank": rank,
                "region": r["region"],
                "net_revenue": round(r["net_revenue"], 2),
                "revenue_share_pct": rev_share,
                "units_sold": r["units_sold"],
                "units_share_pct": unit_share,
                "transaction_count": r["transaction_count"],
            }
        )

    chart = {
        "chart_type": "bar",
        "title": "Regional Performance: Net Revenue & Units Sold",
        "labels": [r["region"] for r in rows],
        "datasets": [
            {
                "label": "Net Revenue",
                "data": [round(r["net_revenue"], 2) for r in rows],
                "backgroundColor": "rgba(6, 182, 212, 0.8)",
                "borderColor": "rgb(6, 182, 212)",
                "borderWidth": 1,
                "yAxisID": "y",
            },
            {
                "label": "Units Sold",
                "data": [r["units_sold"] for r in rows],
                "backgroundColor": "rgba(245, 158, 11, 0.8)",
                "borderColor": "rgb(245, 158, 11)",
                "borderWidth": 1,
                "yAxisID": "y1",
            },
        ],
    }

    return {
        "top_region_by_revenue": top_by_revenue["region"],
        "top_revenue": round(top_by_revenue["net_revenue"], 2),
        "top_region_by_units": top_by_units["region"],
        "top_units": top_by_units["units_sold"],
        "supporting_data": supporting_data,
        "chart": chart,
        "data_quality_notes": get_data_quality_notes(conn),
    }


def parse_month_token(month_str: str, available_year_months: List[str]) -> str:
    """
    Resolve a user month token (e.g. 'January', '01', 'Jan', '2026-01')
    to an available year_month (e.g. '2026-01') in the dataset.
    """
    clean_str = month_str.strip().lower()

    # Exact match for YYYY-MM
    for ym in available_year_months:
        if clean_str == ym.lower():
            return ym

    month_name_map = {
        "january": 1, "jan": 1, "1": 1, "01": 1,
        "february": 2, "feb": 2, "2": 2, "02": 2,
        "march": 3, "mar": 3, "3": 3, "03": 3,
        "april": 4, "apr": 4, "4": 4, "04": 4,
        "may": 5, "5": 5, "05": 5,
        "june": 6, "jun": 6, "6": 6, "06": 6,
        "july": 7, "jul": 7, "7": 7, "07": 7,
        "august": 8, "aug": 8, "8": 8, "08": 8,
        "september": 9, "sep": 9, "sept": 9, "9": 9, "09": 9,
        "october": 10, "oct": 10, "10": 10,
        "november": 11, "nov": 11, "11": 11,
        "december": 12, "dec": 12, "12": 12,
    }

    target_month_num = month_name_map.get(clean_str)
    if target_month_num is None:
        raise AnalyticsValueError(
            f"Month '{month_str}' could not be identified. Please specify a valid month (e.g., 'January' or '2026-01')."
        )

    # Find matching month in dataset
    matches = [ym for ym in available_year_months if int(ym.split("-")[1]) == target_month_num]
    if not matches:
        avail_str = ", ".join(available_year_months)
        raise AnalyticsValueError(
            f"Month '{month_str}' is not present in the dataset. Available months are: {avail_str}."
        )

    if len(matches) > 1:
        # Ambiguous year
        raise AnalyticsValueError(
            f"Month '{month_str}' appears in multiple years ({', '.join(matches)}). Please specify the year (e.g. '{matches[0]}')."
        )

    return matches[0]


def get_revenue_change_between_months(
    conn: sqlite3.Connection,
    month1_raw: str,
    month2_raw: str,
) -> Dict[str, Any]:
    """
    Compare revenue between two months.
    Calculates absolute change, percentage change, and directional trend.
    Handles zero-baseline safely.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT year_month
        FROM sales_transactions
        WHERE is_valid = 1 AND year_month IS NOT NULL
        ORDER BY year_month ASC;
        """
    )
    available_months = [r["year_month"] for r in cursor.fetchall()]

    if not available_months:
        raise AnalyticsValueError("No transaction data available for comparison.")

    ym1 = parse_month_token(month1_raw, available_months)
    ym2 = parse_month_token(month2_raw, available_months)

    # Query metrics for each month
    cursor.execute(
        """
        SELECT 
            year_month,
            COUNT(*) AS txn_count,
            SUM(quantity) AS units_sold,
            SUM(gross_revenue) AS gross_revenue,
            SUM(discount_amount) AS discounts,
            SUM(net_revenue) AS net_revenue
        FROM sales_transactions
        WHERE is_valid = 1 AND year_month IN (?, ?)
        GROUP BY year_month;
        """,
        (ym1, ym2),
    )
    results = {r["year_month"]: dict(r) for r in cursor.fetchall()}

    m1_data = results.get(ym1, {"net_revenue": 0.0, "units_sold": 0, "txn_count": 0, "discounts": 0.0, "gross_revenue": 0.0})
    m2_data = results.get(ym2, {"net_revenue": 0.0, "units_sold": 0, "txn_count": 0, "discounts": 0.0, "gross_revenue": 0.0})

    m1_rev = round(float(m1_data["net_revenue"]), 2)
    m2_rev = round(float(m2_data["net_revenue"]), 2)
    absolute_change = round(m2_rev - m1_rev, 2)

    # Safe percentage change computation
    if m1_rev > 0:
        pct_change: Optional[float] = round((absolute_change / m1_rev) * 100, 2)
    elif m1_rev == 0 and m2_rev == 0:
        pct_change = 0.0
    else:
        # Zero baseline: mathematically undefined percentage
        pct_change = None

    if absolute_change > 0:
        direction = "increased"
    elif absolute_change < 0:
        direction = "decreased"
    else:
        direction = "remained unchanged"

    month_name_map = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    def format_label(ym_str: str) -> str:
        parts = ym_str.split("-")
        y = int(parts[0])
        m = int(parts[1])
        return f"{month_name_map.get(m, m)} {y}"

    m1_label = format_label(ym1)
    m2_label = format_label(ym2)

    supporting_data = [
        {
            "period": m1_label,
            "year_month": ym1,
            "net_revenue": m1_rev,
            "gross_revenue": round(float(m1_data["gross_revenue"]), 2),
            "discounts": round(float(m1_data["discounts"]), 2),
            "units_sold": m1_data["units_sold"],
            "transactions": m1_data["txn_count"],
        },
        {
            "period": m2_label,
            "year_month": ym2,
            "net_revenue": m2_rev,
            "gross_revenue": round(float(m2_data["gross_revenue"]), 2),
            "discounts": round(float(m2_data["discounts"]), 2),
            "units_sold": m2_data["units_sold"],
            "transactions": m2_data["txn_count"],
        },
        {
            "period": "Variance (Change)",
            "year_month": f"{ym1} → {ym2}",
            "net_revenue": absolute_change,
            "gross_revenue": round(float(m2_data["gross_revenue"]) - float(m1_data["gross_revenue"]), 2),
            "discounts": round(float(m2_data["discounts"]) - float(m1_data["discounts"]), 2),
            "units_sold": m2_data["units_sold"] - m1_data["units_sold"],
            "transactions": m2_data["txn_count"] - m1_data["txn_count"],
        },
    ]

    chart = {
        "chart_type": "bar",
        "title": f"Revenue Comparison: {m1_label} vs {m2_label}",
        "labels": [m1_label, m2_label],
        "datasets": [
            {
                "label": "Net Revenue",
                "data": [m1_rev, m2_rev],
                "backgroundColor": ["rgba(99, 102, 241, 0.8)", "rgba(16, 185, 129, 0.8)"],
                "borderColor": ["rgb(99, 102, 241)", "rgb(16, 185, 129)"],
                "borderWidth": 1,
            }
        ],
    }

    return {
        "month1_label": m1_label,
        "month1_year_month": ym1,
        "month1_revenue": m1_rev,
        "month2_label": m2_label,
        "month2_year_month": ym2,
        "month2_revenue": m2_rev,
        "absolute_change": absolute_change,
        "percentage_change": pct_change,
        "direction": direction,
        "supporting_data": supporting_data,
        "chart": chart,
        "data_quality_notes": get_data_quality_notes(conn),
    }


def get_dataset_metadata(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Retrieve full catalog and dataset metadata."""
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(sales_transactions);")
    columns = [r["name"] for r in cursor.fetchall()]

    cursor.execute(
        """
        SELECT 
            MIN(order_date_iso) AS min_date,
            MAX(order_date_iso) AS max_date
        FROM sales_transactions
        WHERE order_date_iso IS NOT NULL;
        """
    )
    dr = cursor.fetchone()

    cursor.execute(
        """
        SELECT DISTINCT year_month
        FROM sales_transactions
        WHERE year_month IS NOT NULL
        ORDER BY year_month ASC;
        """
    )
    available_months = [r["year_month"] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT category FROM sales_transactions WHERE category IS NOT NULL ORDER BY category;")
    categories = [r["category"] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT product FROM sales_transactions WHERE product IS NOT NULL ORDER BY product;")
    products = [r["product"] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT region FROM sales_transactions WHERE region IS NOT NULL ORDER BY region;")
    regions = [r["region"] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT sales_channel FROM sales_transactions WHERE sales_channel IS NOT NULL ORDER BY sales_channel;")
    channels = [r["sales_channel"] for r in cursor.fetchall()]

    cursor.execute(
        """
        SELECT data_quality_flag, COUNT(*) as cnt
        FROM sales_transactions
        GROUP BY data_quality_flag;
        """
    )
    flags_breakdown = {r["data_quality_flag"]: r["cnt"] for r in cursor.fetchall()}

    return {
        "columns": columns,
        "date_range": {
            "min_date": dr["min_date"] if dr else None,
            "max_date": dr["max_date"] if dr else None,
        },
        "available_months": available_months,
        "product_categories": categories,
        "products": products,
        "regions": regions,
        "sales_channels": channels,
        "data_quality_summary": {
            "flags_breakdown": flags_breakdown,
            "notes": get_data_quality_notes(conn),
        },
    }
