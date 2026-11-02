"""
Natural Language Question Interpretation Component.
Maps natural-language user queries to structured analytical intents.
Supports genuine LLM interpretation when credentials are configured,
with a robust, deterministic rule-based fallback.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.config import settings

logger = logging.getLogger(__name__)

# Valid analytical intents
INTENT_TOTAL_REVENUE = "total_revenue"
INTENT_TOP_PRODUCT = "highest_revenue_product"
INTENT_MONTHLY_TREND = "monthly_revenue_trend"
INTENT_TOP_REGION = "highest_sales_region"
INTENT_MONTH_COMPARISON = "revenue_change_between_months"
INTENT_UNSUPPORTED = "unsupported"
INTENT_INVALID = "invalid"

VALID_INTENTS = {
    INTENT_TOTAL_REVENUE,
    INTENT_TOP_PRODUCT,
    INTENT_MONTHLY_TREND,
    INTENT_TOP_REGION,
    INTENT_MONTH_COMPARISON,
}

MONTH_REGEX_STR = (
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|\d{4}-\d{2})\b"
)


class InterpretedQuery:
    """Structured representation of an interpreted user question."""

    def __init__(
        self,
        intent: str,
        parameters: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        interpreter_used: str = "rule_based_fallback",
        error_message: Optional[str] = None,
    ):
        self.intent = intent
        self.parameters = parameters or {}
        self.confidence = confidence
        self.interpreter_used = interpreter_used
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "interpreter_used": self.interpreter_used,
            "error_message": self.error_message,
        }


def _extract_months_from_text(text: str) -> List[str]:
    """Extract ordered month tokens from user question."""
    matches = re.findall(MONTH_REGEX_STR, text, flags=re.IGNORECASE)
    # Deduplicate while preserving order if different
    return matches


def interpret_question_deterministic(question: str) -> InterpretedQuery:
    """
    Deterministic rule-based pattern and semantic interpreter.
    Evaluates regex patterns and keywords to identify supported analytical queries.
    """
    raw_query = question.strip()
    if not raw_query:
        return InterpretedQuery(
            intent=INTENT_INVALID,
            interpreter_used="rule_based_fallback",
            error_message="Question cannot be empty. Please enter a valid business query.",
        )

    q = raw_query.lower()

    # Check for Month-over-Month comparison intent
    # Examples:
    # "How did revenue change between January and February?"
    # "Compare revenue in March and April"
    # "Change between Jan and Feb"
    # "Difference between 2026-01 and 2026-02"
    comparison_indicators = ["change", "compare", "difference", "between", "vs", "versus", "variance", "growth from"]
    has_comparison_kw = any(kw in q for kw in comparison_indicators)
    extracted_months = _extract_months_from_text(q)

    if (has_comparison_kw and len(extracted_months) >= 2) or len(extracted_months) >= 2:
        month1 = extracted_months[0]
        month2 = extracted_months[1]
        return InterpretedQuery(
            intent=INTENT_MONTH_COMPARISON,
            parameters={"month1": month1, "month2": month2},
            confidence=0.95,
            interpreter_used="rule_based_fallback",
        )
    elif has_comparison_kw and len(extracted_months) == 1:
        return InterpretedQuery(
            intent=INTENT_MONTH_COMPARISON,
            parameters={"month1": extracted_months[0], "month2": None},
            confidence=0.7,
            interpreter_used="rule_based_fallback",
            error_message=f"Only one month ('{extracted_months[0]}') was detected. Please provide two months to compare (e.g. 'How did revenue change between January and February?').",
        )

    # Check for Highest-Revenue Product
    # Examples:
    # "Which product generated the highest revenue?"
    # "Top product by revenue"
    # "Best selling product"
    # "Most profitable product"
    product_indicators = [
        "highest revenue product",
        "top product",
        "best selling product",
        "highest selling product",
        "best product",
        "product generated the highest revenue",
        "product with the highest revenue",
        "which product",
        "most revenue product",
        "product revenue",
        "top item",
        "best item",
    ]
    if any(ind in q for ind in product_indicators):
        return InterpretedQuery(
            intent=INTENT_TOP_PRODUCT,
            parameters={},
            confidence=0.95,
            interpreter_used="rule_based_fallback",
        )

    # Check for Monthly Revenue Trend
    # Examples:
    # "What is the monthly revenue trend?"
    # "Show sales month by month"
    # "Monthly sales"
    # "Revenue trend"
    trend_indicators = [
        "monthly revenue trend",
        "monthly trend",
        "revenue trend",
        "sales trend",
        "month by month",
        "month-by-month",
        "monthly breakdown",
        "monthly sales",
        "monthly revenue",
        "sales over time",
        "revenue over time",
        "trend",
    ]
    if any(ind in q for ind in trend_indicators):
        return InterpretedQuery(
            intent=INTENT_MONTHLY_TREND,
            parameters={},
            confidence=0.95,
            interpreter_used="rule_based_fallback",
        )

    # Check for Highest-Sales Region
    # Examples:
    # "Which region generated the highest sales?"
    # "Which region performs best?"
    # "Top region"
    # "Highest sales region"
    region_indicators = [
        "highest sales region",
        "which region",
        "top region",
        "best region",
        "region performs best",
        "region generated the highest",
        "region with the highest sales",
        "regional sales",
        "regional revenue",
        "region performance",
        "regional breakdown",
    ]
    if any(ind in q for ind in region_indicators):
        return InterpretedQuery(
            intent=INTENT_TOP_REGION,
            parameters={},
            confidence=0.95,
            interpreter_used="rule_based_fallback",
        )

    # Check for Total Revenue
    # Examples:
    # "What is the total revenue?"
    # "Show total sales"
    # "Overall revenue"
    # "How much revenue"
    total_rev_indicators = [
        "total revenue",
        "total sales",
        "overall revenue",
        "overall sales",
        "gross sales",
        "net revenue",
        "total income",
        "how much revenue",
        "how much did we sell",
        "how much money did we make",
        "what is the revenue",
        "total net revenue",
        "sales total",
    ]
    if any(ind in q for ind in total_rev_indicators):
        return InterpretedQuery(
            intent=INTENT_TOTAL_REVENUE,
            parameters={},
            confidence=0.95,
            interpreter_used="rule_based_fallback",
        )

    # Unsupported question handling
    return InterpretedQuery(
        intent=INTENT_UNSUPPORTED,
        interpreter_used="rule_based_fallback",
        error_message=(
            "I could not understand this question. Currently supported questions include:\n"
            "1. 'What is the total revenue?'\n"
            "2. 'Which product generated the highest revenue?'\n"
            "3. 'What is the monthly revenue trend?'\n"
            "4. 'Which region generated the highest sales?'\n"
            "5. 'How did revenue change between two months?' (e.g. between January and February)"
        ),
    )


def interpret_question_llm(question: str) -> Optional[InterpretedQuery]:
    """
    Attempt natural language interpretation using genuine LLM (Gemini REST API).
    Returns None if LLM is unconfigured, unreachable, or fails validation.
    """
    if not settings.GEMINI_API_KEY:
        return None

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"

    system_instruction = (
        "You are an expert NLP classifier for a Sales Business Intelligence Assistant. "
        "Classify the user's natural-language query into one of the following exact intents:\n"
        "- 'total_revenue': questions asking for overall/total sales or revenue.\n"
        "- 'highest_revenue_product': questions asking for top product, best-selling item, or highest revenue product.\n"
        "- 'monthly_revenue_trend': questions asking for month-by-month sales, monthly trend, or revenue over time.\n"
        "- 'highest_sales_region': questions asking for top performing region, best territory, or highest sales region.\n"
        "- 'revenue_change_between_months': questions comparing revenue between two specific months.\n"
        "- 'unsupported': any question outside sales analytics (e.g., weather, chit-chat, general trivia).\n\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "intent": "total_revenue" | "highest_revenue_product" | "monthly_revenue_trend" | "highest_sales_region" | "revenue_change_between_months" | "unsupported",\n'
        '  "parameters": {\n'
        '    "month1": "first month name or null",\n'
        '    "month2": "second month name or null"\n'
        "  },\n"
        '  "confidence": 0.95\n'
        "}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"System: {system_instruction}"},
                    {"text": f"User query: {question}"},
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.0,
        },
    }

    try:
        resp = requests.post(api_url, json=payload, timeout=8.0)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed = json.loads(text_part)
                llm_intent = parsed.get("intent")
                params = parsed.get("parameters", {})
                confidence = float(parsed.get("confidence", 0.9))

                if llm_intent in VALID_INTENTS:
                    return InterpretedQuery(
                        intent=llm_intent,
                        parameters=params,
                        confidence=confidence,
                        interpreter_used="gemini_llm",
                    )
                elif llm_intent == INTENT_UNSUPPORTED:
                    return InterpretedQuery(
                        intent=INTENT_UNSUPPORTED,
                        parameters={},
                        confidence=confidence,
                        interpreter_used="gemini_llm",
                        error_message="The configured LLM identified this question as outside the supported business analytics domain.",
                    )
    except Exception as e:
        logger.warning(f"Gemini LLM interpretation failed: {e}. Falling back to deterministic interpreter.")

    return None


def interpret_question(question: str) -> InterpretedQuery:
    """
    Main entry point for question interpretation.
    Prefers genuine LLM if configured and operational; seamlessly falls back
    to the robust deterministic rule-based interpreter.
    """
    raw_query = question.strip() if question else ""
    if not raw_query:
        return InterpretedQuery(
            intent=INTENT_INVALID,
            interpreter_used="rule_based_fallback",
            error_message="Question cannot be empty. Please enter a valid business query.",
        )

    # Attempt LLM interpretation if configured
    if settings.has_llm_configured:
        llm_result = interpret_question_llm(raw_query)
        if llm_result:
            return llm_result

    # Deterministic fallback
    return interpret_question_deterministic(raw_query)
