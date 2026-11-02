"""
Business Logic & Query Orchestration Service.
Connects natural-language query interpretation with deterministic SQL analytics
to build transparent, verified business intelligence responses.
"""

import sqlite3
from typing import Any, Dict, Optional

from app.analytics import (
    AnalyticsValueError,
    get_data_quality_notes,
    get_dataset_metadata,
    get_highest_revenue_product,
    get_highest_sales_region,
    get_monthly_revenue_trend,
    get_revenue_change_between_months,
    get_total_revenue,
)
from app.database import connect_db
from app.question_interpreter import (
    INTENT_INVALID,
    INTENT_MONTH_COMPARISON,
    INTENT_MONTHLY_TREND,
    INTENT_TOP_PRODUCT,
    INTENT_TOP_REGION,
    INTENT_TOTAL_REVENUE,
    INTENT_UNSUPPORTED,
    interpret_question,
)
from app.schemas import ChartConfig, QuestionResponse, SummaryResponse


def format_currency_amount(amount: float) -> str:
    """Format numerical values with standard comma separation and two decimals."""
    return f"{amount:,.2f}"


def get_application_summary(db_path: Optional[str] = None) -> SummaryResponse:
    """Retrieve top-level KPI metrics and data-quality exclusions for dashboard cards."""
    conn = connect_db(db_path)
    try:
        rev_data = get_total_revenue(conn)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(DISTINCT product) AS cnt FROM sales_transactions WHERE is_valid = 1;")
        prod_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(DISTINCT region) AS cnt FROM sales_transactions WHERE is_valid = 1;")
        region_count = cursor.fetchone()["cnt"]

        warnings = rev_data.get("data_quality_notes", [])

        return SummaryResponse(
            valid_transactions=rev_data["valid_transactions"],
            total_completed_net_revenue=rev_data["net_revenue"],
            total_completed_gross_revenue=rev_data["gross_revenue"],
            total_discounts=rev_data["total_discounts"],
            total_units_sold=rev_data["units_sold"],
            products_count=prod_count,
            regions_count=region_count,
            excluded_records_count=rev_data["excluded_records"],
            data_quality_warnings=warnings,
        )
    finally:
        conn.close()


def process_question(question_text: str, db_path: Optional[str] = None) -> QuestionResponse:
    """
    End-to-end question processing pipeline:
    1. Interprets natural language question into intent and parameters.
    2. Executes safe, deterministic SQL analytics.
    3. Formats readable business answers with supporting tables and charts.
    """
    raw_query = question_text.strip() if question_text else ""
    interpretation = interpret_question(raw_query)

    # Handle invalid or empty questions
    if interpretation.intent == INTENT_INVALID:
        return QuestionResponse(
            question=raw_query,
            answer="Please enter a valid question. The input was empty or whitespace only.",
            intent=INTENT_INVALID,
            metric="none",
            value=None,
            unit="none",
            supporting_data=[],
            chart=None,
            data_quality_notes=[],
            interpreter_used=interpretation.interpreter_used,
            error=interpretation.error_message or "Empty question.",
        )

    # Handle unsupported questions
    if interpretation.intent == INTENT_UNSUPPORTED:
        return QuestionResponse(
            question=raw_query,
            answer=(
                "I am unable to answer this question because it is outside the supported sales analytics domain. "
                "You can ask about total revenue, top products, monthly revenue trends, top regions, "
                "or month-to-month revenue comparisons."
            ),
            intent=INTENT_UNSUPPORTED,
            metric="none",
            value=None,
            unit="none",
            supporting_data=[],
            chart=None,
            data_quality_notes=[],
            interpreter_used=interpretation.interpreter_used,
            error=interpretation.error_message,
        )

    # Connect to database for analytical execution
    conn = connect_db(db_path)
    try:
        # 1. Total Revenue
        if interpretation.intent == INTENT_TOTAL_REVENUE:
            data = get_total_revenue(conn)
            net_rev_fmt = format_currency_amount(data["net_revenue"])
            gross_rev_fmt = format_currency_amount(data["gross_revenue"])
            discount_fmt = format_currency_amount(data["total_discounts"])

            answer = (
                f"The total completed net revenue is {net_rev_fmt} currency units across "
                f"{data['valid_transactions']} eligible sales transactions (selling {data['units_sold']:,} total units). "
                f"This reflects {gross_rev_fmt} in gross sales less {discount_fmt} in customer discounts."
            )

            return QuestionResponse(
                question=raw_query,
                answer=answer,
                intent=INTENT_TOTAL_REVENUE,
                metric="net_revenue",
                value=data["net_revenue"],
                unit="currency units",
                supporting_data=data["supporting_data"],
                chart=None,
                data_quality_notes=data["data_quality_notes"],
                interpreter_used=interpretation.interpreter_used,
                error=None,
            )

        # 2. Highest-Revenue Product
        elif interpretation.intent == INTENT_TOP_PRODUCT:
            data = get_highest_revenue_product(conn)
            top_rev_fmt = format_currency_amount(data["top_product_net_revenue"])
            top_item = data["top_product"]
            top_units = data["top_product_units"]

            answer = (
                f"The product that generated the highest revenue is '{top_item}', generating "
                f"{top_rev_fmt} currency units in net revenue ({top_units:,} units sold). "
                f"By comparison, '{data['highest_units_product']}' was the volume leader with "
                f"{data['highest_units_sold']:,} units sold."
            )

            chart_obj = ChartConfig(**data["chart"]) if data.get("chart") else None

            return QuestionResponse(
                question=raw_query,
                answer=answer,
                intent=INTENT_TOP_PRODUCT,
                metric="net_revenue",
                value=data["top_product_net_revenue"],
                unit="currency units",
                supporting_data=data["supporting_data"],
                chart=chart_obj,
                data_quality_notes=data["data_quality_notes"],
                interpreter_used=interpretation.interpreter_used,
                error=None,
            )

        # 3. Monthly Revenue Trend
        elif interpretation.intent == INTENT_MONTHLY_TREND:
            data = get_monthly_revenue_trend(conn)
            peak_fmt = format_currency_amount(data["peak_revenue"])
            lowest_fmt = format_currency_amount(data["lowest_revenue"])
            num_months = len(data["months"])

            answer = (
                f"Monthly net revenue across {num_months} recorded months peaked in {data['peak_month']} "
                f"at {peak_fmt} currency units, with the lowest revenue recorded in {data['lowest_month']} "
                f"at {lowest_fmt} currency units."
            )

            chart_obj = ChartConfig(**data["chart"]) if data.get("chart") else None

            return QuestionResponse(
                question=raw_query,
                answer=answer,
                intent=INTENT_MONTHLY_TREND,
                metric="monthly_net_revenue",
                value=data["peak_revenue"],
                unit="currency units",
                supporting_data=data["supporting_data"],
                chart=chart_obj,
                data_quality_notes=data["data_quality_notes"],
                interpreter_used=interpretation.interpreter_used,
                error=None,
            )

        # 4. Highest-Sales Region
        elif interpretation.intent == INTENT_TOP_REGION:
            data = get_highest_sales_region(conn)
            top_rev_fmt = format_currency_amount(data["top_revenue"])
            top_reg = data["top_region_by_revenue"]
            top_units = data["top_units"]

            answer = (
                f"The region with the highest sales is '{top_reg}', generating {top_rev_fmt} "
                f"currency units in net revenue and {top_units:,} total units sold. "
                f"'{top_reg}' is the top performer across both net revenue and sales volume."
            )

            chart_obj = ChartConfig(**data["chart"]) if data.get("chart") else None

            return QuestionResponse(
                question=raw_query,
                answer=answer,
                intent=INTENT_TOP_REGION,
                metric="net_revenue_and_volume",
                value=data["top_revenue"],
                unit="currency units",
                supporting_data=data["supporting_data"],
                chart=chart_obj,
                data_quality_notes=data["data_quality_notes"],
                interpreter_used=interpretation.interpreter_used,
                error=None,
            )

        # 5. Month-over-Month Comparison
        elif interpretation.intent == INTENT_MONTH_COMPARISON:
            if interpretation.error_message:
                return QuestionResponse(
                    question=raw_query,
                    answer=interpretation.error_message,
                    intent=INTENT_MONTH_COMPARISON,
                    metric="none",
                    value=None,
                    unit="none",
                    supporting_data=[],
                    chart=None,
                    data_quality_notes=get_data_quality_notes(conn),
                    interpreter_used=interpretation.interpreter_used,
                    error=interpretation.error_message,
                )

            m1 = interpretation.parameters.get("month1")
            m2 = interpretation.parameters.get("month2")

            try:
                data = get_revenue_change_between_months(conn, m1, m2)
            except AnalyticsValueError as ave:
                return QuestionResponse(
                    question=raw_query,
                    answer=f"Could not compare months: {str(ave)}",
                    intent=INTENT_MONTH_COMPARISON,
                    metric="none",
                    value=None,
                    unit="none",
                    supporting_data=[],
                    chart=None,
                    data_quality_notes=get_data_quality_notes(conn),
                    interpreter_used=interpretation.interpreter_used,
                    error=str(ave),
                )

            abs_change_fmt = format_currency_amount(abs(data["absolute_change"]))
            m1_rev_fmt = format_currency_amount(data["month1_revenue"])
            m2_rev_fmt = format_currency_amount(data["month2_revenue"])

            if data["percentage_change"] is not None:
                sign = "+" if data["percentage_change"] > 0 else ""
                pct_str = f" ({sign}{data['percentage_change']:.2f}%)"
            else:
                pct_str = " (percentage change undefined due to 0 baseline)"

            answer = (
                f"Revenue {data['direction']} by {abs_change_fmt} currency units{pct_str} "
                f"from {data['month1_label']} ({m1_rev_fmt} currency units) to "
                f"{data['month2_label']} ({m2_rev_fmt} currency units)."
            )

            chart_obj = ChartConfig(**data["chart"]) if data.get("chart") else None

            return QuestionResponse(
                question=raw_query,
                answer=answer,
                intent=INTENT_MONTH_COMPARISON,
                metric="revenue_variance",
                value=data["absolute_change"],
                unit="currency units",
                supporting_data=data["supporting_data"],
                chart=chart_obj,
                data_quality_notes=data["data_quality_notes"],
                interpreter_used=interpretation.interpreter_used,
                error=None,
            )

        # Fallback for unexpected intent
        return QuestionResponse(
            question=raw_query,
            answer="Unsupported analytical request.",
            intent=INTENT_UNSUPPORTED,
            metric="none",
            value=None,
            unit="none",
            supporting_data=[],
            chart=None,
            data_quality_notes=get_data_quality_notes(conn),
            interpreter_used=interpretation.interpreter_used,
            error="Unrecognized analytical intent.",
        )

    finally:
        conn.close()
