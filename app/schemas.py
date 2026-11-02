"""
Pydantic schemas for API request and response validation.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health endpoint response model."""
    status: str = Field(..., description="Application operational status")
    database_connected: bool = Field(..., description="Whether the SQLite database is reachable")
    total_records: int = Field(..., description="Total transactions in the database")
    valid_records: int = Field(..., description="Total valid completed transactions")
    version: str = Field(..., description="Application version")


class SummaryResponse(BaseModel):
    """Business summary metrics response model."""
    valid_transactions: int = Field(..., description="Count of valid completed transactions")
    total_completed_net_revenue: float = Field(..., description="Total net revenue from completed sales")
    total_completed_gross_revenue: float = Field(..., description="Total gross sales revenue")
    total_discounts: float = Field(..., description="Total discount amount applied")
    total_units_sold: int = Field(..., description="Total units sold across valid sales")
    products_count: int = Field(..., description="Number of distinct products")
    regions_count: int = Field(..., description="Number of distinct sales regions")
    excluded_records_count: int = Field(..., description="Number of excluded/flagged records")
    data_quality_warnings: List[str] = Field(default_factory=list, description="Data-quality warnings and exclusions")


class MetadataResponse(BaseModel):
    """Dataset metadata response model."""
    columns: List[str] = Field(..., description="Available table columns")
    date_range: Dict[str, Optional[str]] = Field(..., description="Min and max order dates in the dataset")
    available_months: List[str] = Field(..., description="Available chronological calendar months (YYYY-MM)")
    product_categories: List[str] = Field(..., description="Available product categories")
    products: List[str] = Field(..., description="List of all distinct products")
    regions: List[str] = Field(..., description="List of all distinct sales regions")
    sales_channels: List[str] = Field(..., description="List of all sales channels")
    data_quality_summary: Dict[str, Any] = Field(..., description="Summary of data-quality audit")


class QuestionRequest(BaseModel):
    """User natural-language query request."""
    question: str = Field(..., min_length=1, max_length=500, description="Natural language analytical question")


class ChartConfig(BaseModel):
    """Chart.js compatible visualization data."""
    chart_type: str = Field(..., description="Type of chart: 'bar', 'line', 'doughnut', etc.")
    title: str = Field(..., description="Chart title")
    labels: List[str] = Field(..., description="X-axis or category labels")
    datasets: List[Dict[str, Any]] = Field(..., description="Chart.js dataset definitions")


class QuestionResponse(BaseModel):
    """Structured response for natural language questions."""
    question: str = Field(..., description="Original user question")
    answer: str = Field(..., description="Clear, readable analytical answer")
    intent: str = Field(..., description="Interpreted analytical question intent")
    metric: str = Field(..., description="Metric used in calculation")
    value: Optional[Union[float, int, str]] = Field(None, description="Primary numerical result")
    unit: str = Field("currency units", description="Unit of measurement")
    supporting_data: List[Dict[str, Any]] = Field(default_factory=list, description="Tabular supporting data")
    chart: Optional[ChartConfig] = Field(None, description="Chart configuration for visualization")
    data_quality_notes: List[str] = Field(default_factory=list, description="Exclusions and quality caveats")
    interpreter_used: str = Field("rule_based_fallback", description="Interpretation method used (LLM or fallback)")
    error: Optional[str] = Field(None, description="Error message if question is unsupported or invalid")
