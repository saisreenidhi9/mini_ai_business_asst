# Mini AI Business Intelligence Assistant

An executive-grade, database-backed sales analytics application that interprets natural-language business questions and returns accurate answers supported by SQLite calculations, interactive Chart.js visualizations, and transparent data-quality audits.

---

## 1. Project Overview & Problem Statement

### Problem Statement
Business stakeholders frequently need answers to critical sales performance questions—such as total revenue, top-selling products, regional volume, and month-over-month growth—without having to write raw SQL queries or navigate complicated BI software. However, generic LLM-based solutions often hallucinate numerical values, invent currency figures, or fail to handle data-quality discrepancies (such as returned orders, zero-quantity records, or missing price values).

### Objective
The **Mini AI Business Intelligence Assistant** bridges natural-language queries and verified relational database transactions. It utilizes an authoritative sales CSV dataset, cleans and normalizes records into an indexed SQLite database, interprets user intent via genuine LLM integration (with a deterministic rule-based fallback), and generates verifiable calculations, supporting tables, and responsive charts.

---

## 2. Key Features

- **Natural-Language Query Interface:** Ask questions in plain English (e.g., *"Which product generated the highest revenue?"*, *"How did revenue change between January and February?"*).
- **Deterministic SQL-Backed Accuracy:** Every numerical figure is computed via parameterized SQL queries executed against SQLite. No hallucinated business numbers.
- **Data Quality & Exclusions Audit:** Transparently isolates questionable transactions (such as returns, zero quantities, and missing prices) and explicitly discloses exclusions on every answer.
- **Dual-Mode Interpretation Pipeline:** Integrates with Google Gemini LLM when API credentials are provided, while offering an offline, deterministic regex/rule-based engine as fallback.
- **Executive BI Dashboard:** Modern dark glassmorphic interface built with vanilla HTML5, CSS3, and JavaScript, featuring real-time KPI summary cards, interactive Chart.js visualizations, and tabular drill-downs.
- **Comprehensive Automated Testing:** 33 automated `pytest` test cases covering analytics, data quality, API endpoints, edge cases, and zero-baseline variances.

---

## 3. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend Framework** | **FastAPI 0.110+** | High-performance, asynchronous REST API with automatic OpenAPI documentation and native Pydantic schema validation. |
| **Web Server** | **Uvicorn 0.28+** | Production-ready, lightning-fast ASGI server. |
| **Database** | **SQLite 3 (Built-in `sqlite3`)** | Zero-configuration, serverless, relational database with WAL mode and foreign key constraints enabled. |
| **Data Processing** | **Pandas 2.2+** | Robust CSV parsing, missing-value detection, and schema validation during import. |
| **AI / NLP** | **Google Gemini REST API / Rule-Based Engine** | Genuine LLM intent classification with an automatic, zero-dependency deterministic fallback. |
| **Frontend UI** | **HTML5, Vanilla CSS3, JavaScript (ES6+)** | Lightweight, framework-free, high-performance executive dashboard with glassmorphism aesthetics. |
| **Data Visualization** | **Chart.js** | Responsive, dynamic rendering of bar charts, line graphs, and comparative variance plots. |
| **Testing** | **Pytest & FastAPI TestClient (HTTPX)** | Isolated test database execution, regression protection, and deterministic unit/API test coverage. |

---

## 4. Project Directory Structure

```text
mini_ai_business_asst/
│
├── data/
│   └── ai_bi_assistant_sales_data - GET.csv   # Authoritative raw CSV sales dataset
│
├── app/
│   ├── __init__.py                            # Package metadata and version
│   ├── main.py                                # FastAPI app, routes, and static asset mount
│   ├── config.py                              # Environment settings and configuration
│   ├── database.py                            # SQLite connection manager, schema, and indexes
│   ├── schemas.py                             # Pydantic request/response validation schemas
│   ├── data_loader.py                         # CSV validation, data cleaning, and audit pipeline
│   ├── analytics.py                           # Deterministic SQL analytical aggregation functions
│   ├── question_interpreter.py                # Dual NLP intent interpreter (LLM & Rule-based)
│   └── services.py                            # Query orchestration and response formatting
│
├── frontend/
│   ├── index.html                             # Executive BI dashboard layout
│   ├── style.css                              # Modern dark glassmorphic design system
│   └── app.js                                 # Async API client, DOM updates, Chart.js rendering
│
├── tests/
│   ├── __init__.py                            # Test package
│   ├── test_analytics.py                      # Tests for the 5 analytical queries & formulas
│   ├── test_data_quality.py                   # Tests for returns, missing prices, zero quantities
│   └── test_api.py                            # End-to-end API and question endpoint tests
│
├── scripts/
│   └── import_data.py                         # Standalone CLI script to initialize/rebuild database
│
├── docs/
│   ├── architecture.md                        # Architectural design & data-flow Mermaid diagrams
│   └── development_report.md                  # Development history, trade-offs, and verification
│
├── database/
│   ├── .gitkeep                               # Preserves directory in version control
│   └── sales_bi.db                            # SQLite database (generated during initialization)
│
├── .env.example                               # Template for environment variables
├── .gitignore                                 # Git ignore rules (caches, DBs, venv)
├── requirements.txt                           # Pinned project dependencies
├── README.md                                  # Comprehensive user & developer guide
└── pytest.ini                                 # Pytest configuration
```

---

## 5. Prerequisites & Environment Setup

### Prerequisites
- **Python 3.11+** (Tested and verified on Python 3.14 on Windows)
- **Pip** package manager

### 1. Virtual Environment Setup (Recommended)
Open PowerShell or your terminal in the project root:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment:
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (cmd.exe):
.\venv\Scripts\activate.bat
# On Linux / macOS:
source venv/bin/activate
```

### 2. Dependency Installation
Install required dependencies:

```bash
pip install -r requirements.txt
```

### 3. Environment Variable Configuration
Copy `.env.example` to `.env` (optional):

```bash
cp .env.example .env
```

Available environment variables:
- `DATABASE_PATH`: Relative or absolute path to SQLite file (default: `database/sales_bi.db`).
- `DATA_DIR`: Directory where source CSV is stored (default: `data`).
- `GEMINI_API_KEY`: *(Optional)* Google Gemini API key. If omitted, the system defaults to the deterministic rule-based interpreter.
- `PORT`: Server port (default: `8000`).
- `HOST`: Server host (default: `127.0.0.1`).

---

## 6. Data Source & Quality Policy

### Authoritative Dataset
The original dataset is located at `data/ai_bi_assistant_sales_data - GET.csv`.
- Total records: **51 rows** (spanning January 3, 2026 to June 28, 2026).
- Original CSV is **never modified**; cleaning is strictly applied during the database import process.

### Revenue Definition
At the individual transaction level, revenue is defined as:

$$\text{Net Revenue} = (\text{Quantity} \times \text{Unit Price}) - \text{Discount Amount}$$

- **Gross Revenue:** $\text{Quantity} \times \text{Unit Price}$
- **Discount Amount:** Treated as a transaction-level discount.
- **Unit of Measurement:** Standardized as `"currency units"` (no fabricated currency symbols are applied).

### Data Quality & Exclusions Policy
To protect business decision-makers from distorted metrics:
1. **Returned Transactions:** Records with `Status == 'Returned'` are preserved in SQLite but assigned `is_valid = 0` with flag `RETURNED_TRANSACTION`. Excluded from completed sales totals.
2. **Zero Quantity Records:** Transactions with `Quantity == 0` are assigned `is_valid = 0` with flag `ZERO_QUANTITY`.
3. **Missing Unit Prices:** Records with null or missing `Unit_price` are flagged `MISSING_UNIT_PRICE` and excluded (never silently converted to zero).
4. **Audit Disclosure:** Any analytical answer derived from the database explicitly reports the number of excluded records and provides transaction-level rationale.

In the supplied dataset, exactly **3 records** are excluded:
- `TXN0033` (Monitor, 26-04-2026): Excluded because `Status == 'Returned'`.
- `TXN0034` (Keyboard, 28-04-2026): Excluded because `Quantity == 0`.
- `TXN0051` (Laptop Stand, 28-06-2026): Excluded because `Unit_price` is missing (`NaN`).

Valid, eligible completed sales: **48 records** yielding **1,439,200.00 currency units** net revenue.

---

## 7. Database Initialization & Data Import

The application initializes its database automatically upon server startup. To manually initialize or rebuild the database from the CLI:

```bash
# Initialize SQLite database from CSV
python scripts/import_data.py

# Force reset and re-import
python scripts/import_data.py --reset
```

Output:
```text
==================================================
Mini AI BI Assistant - Database Import Pipeline
==================================================
[*] Detected CSV data source: ai_bi_assistant_sales_data - GET.csv

--- Import Summary ---
Status:           success
File Name:        ai_bi_assistant_sales_data - GET.csv
Total Rows:       51
Valid Rows:       48
Flagged Rows:     3

--- Flagged Data-Quality Issues ---
  - [TXN0033] Flag: RETURNED_TRANSACTION | Reason: Transaction was returned; excluded from completed-sales revenue
  - [TXN0034] Flag: ZERO_QUANTITY | Reason: Quantity is 0; not an ordinary sales transaction
  - [TXN0051] Flag: MISSING_UNIT_PRICE | Reason: Unit price is missing or null; cannot calculate revenue

[+] Database initialization completed successfully.
```

---

## 8. Running the Application

Start the FastAPI application using Uvicorn:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Accessing the Web Interface
Open your web browser and navigate to:
```
http://127.0.0.1:8000/
```

### Accessing Interactive API Documentation (Swagger UI)
Interactive API documentation and schema explorer is available at:
```
http://127.0.0.1:8000/docs
```

---

## 9. Supported Business Questions & Baseline Results

The assistant answers all 5 required business questions with deterministic accuracy:

| # | Question Phrasing | Interpreted Intent | Baseline Calculation Result | Supporting Visualization |
|---|---|---|---|---|
| **1** | *"What is the total revenue?"* | `total_revenue` | **1,439,200.00 currency units** net revenue (Gross: 1,443,700.00, Discounts: 4,500.00, Units: 633, Valid Txns: 48, Excluded: 3). | Metric highlight card & financial summary table |
| **2** | *"Which product generated the highest revenue?"* | `highest_revenue_product` | **Monitor** (473,000.00 currency units across 9 txns, 50 units sold, 32.87% revenue share). *Volume leader: Wireless Mouse (228 units).* | Bar chart of all 7 products by net revenue |
| **3** | *"What is the monthly revenue trend?"* | `monthly_revenue_trend` | Chronological months (Jan–Jun 2026). Peak: **May 2026 (318,500.00)**; Lowest: **January 2026 (210,250.00)**. | Line chart with area fill showing monthly revenue progression |
| **4** | *"Which region generated the highest sales?"* | `highest_sales_region` | **South** leads across both net revenue (**411,200.00 currency units**, 28.57% share) and sales volume (**182 units sold**). | Dual-axis bar chart comparing net revenue and units sold |
| **5** | *"How did revenue change between January and February?"* | `revenue_change_between_months` | Revenue **increased by 24,350.00 currency units (+11.58%)** from Jan 2026 (210,250.00) to Feb 2026 (234,600.00). | Comparative variance bar chart |

---

## 10. REST API Specification

### `GET /api/health`
Returns application and database connectivity status.
```json
{
  "status": "healthy",
  "database_connected": true,
  "total_records": 51,
  "valid_records": 48,
  "version": "1.0.0"
}
```

### `GET /api/summary`
Returns database-calculated KPIs for dashboard summary cards.
```json
{
  "valid_transactions": 48,
  "total_completed_net_revenue": 1439200.0,
  "total_completed_gross_revenue": 1443700.0,
  "total_discounts": 4500.0,
  "total_units_sold": 633,
  "products_count": 7,
  "regions_count": 4,
  "excluded_records_count": 3,
  "data_quality_warnings": [
    "3 record(s) excluded from completed sales calculations to maintain data integrity:",
    "• TXN0033: Transaction was returned; excluded from completed-sales revenue (Flag: RETURNED_TRANSACTION)",
    "• TXN0034: Quantity is 0; not an ordinary sales transaction (Flag: ZERO_QUANTITY)",
    "• TXN0051: Unit price is missing or null; cannot calculate revenue (Flag: MISSING_UNIT_PRICE)"
  ]
}
```

### `GET /api/metadata`
Returns catalog dimensions, available date ranges, and distinct values.
```json
{
  "columns": ["transaction_id", "order_date_raw", "order_date_iso", "product", "..."],
  "date_range": {
    "min_date": "2026-01-03",
    "max_date": "2026-06-28"
  },
  "available_months": ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"],
  "product_categories": ["Accessories", "Electronics", "Furniture"],
  "products": ["Desk", "Keyboard", "Laptop Stand", "Monitor", "Office Chair", "USB-C Hub", "Wireless Mouse"],
  "regions": ["East", "North", "South", "West"],
  "sales_channels": ["Online", "Retail"],
  "data_quality_summary": { ... }
}
```

### `POST /api/ask`
Interprets a natural-language question and returns analytical results.

**Request Body:**
```json
{
  "question": "Which product generated the highest revenue?"
}
```

**Response:**
```json
{
  "question": "Which product generated the highest revenue?",
  "answer": "The product that generated the highest revenue is 'Monitor', generating 473,000.00 currency units in net revenue (50 units sold). By comparison, 'Wireless Mouse' was the volume leader with 228 units sold.",
  "intent": "highest_revenue_product",
  "metric": "net_revenue",
  "value": 473000.0,
  "unit": "currency units",
  "supporting_data": [
    {
      "rank": 1,
      "product": "Monitor",
      "category": "Electronics",
      "net_revenue": 473000.0,
      "revenue_share_pct": 32.87,
      "units_sold": 50,
      "transaction_count": 9
    },
    {
      "rank": 2,
      "product": "Desk",
      "category": "Furniture",
      "net_revenue": 222500.0,
      "revenue_share_pct": 15.46,
      "units_sold": 18,
      "transaction_count": 6
    }
  ],
  "chart": {
    "chart_type": "bar",
    "title": "Net Revenue by Product",
    "labels": ["Monitor", "Desk", "Office Chair", "USB-C Hub", "Wireless Mouse", "Keyboard", "Laptop Stand"],
    "datasets": [...]
  },
  "data_quality_notes": [
    "3 record(s) excluded from completed sales calculations to maintain data integrity:",
    "• TXN0033: Transaction was returned; excluded from completed-sales revenue (Flag: RETURNED_TRANSACTION)",
    "• TXN0034: Quantity is 0; not an ordinary sales transaction (Flag: ZERO_QUANTITY)",
    "• TXN0051: Unit price is missing or null; cannot calculate revenue (Flag: MISSING_UNIT_PRICE)"
  ],
  "interpreter_used": "rule_based_fallback",
  "error": null
}
```

---

## 11. AI Integration & Fallback Strategy

To ensure zero external dependencies while still supporting modern generative AI capabilities:
1. **Tier 1 (Genuine LLM):** If `GEMINI_API_KEY` is set in `.env`, the system queries the Google Gemini REST API with structured system instructions to classify the query into an intent and parameters JSON.
   - The LLM is **never allowed to generate SQL directly**; it strictly acts as a natural-language semantic parser.
   - If the LLM request times out, fails, or credentials are invalid, the system catches the error, logs a warning without leaking secrets, and automatically invokes Tier 2.
2. **Tier 2 (Deterministic Rule-Based Fallback):** Regex tokenizers and semantic pattern matchers parse variations of all 5 required business questions without requiring internet access or API keys.
3. **Transparency:** Every response marks `interpreter_used` (`"rule_based_fallback"` or `"gemini_llm"`). The system never fabricates that an LLM was used when the fallback handled the question.

---

## 12. Running Automated Tests

Run the full automated test suite using `pytest`:

```bash
pytest
```

To run with verbose output:
```bash
pytest -v
```

### Test Suite Summary:
- Total Tests: **33 passed** (0 failed).
- `test_analytics.py`: 9 tests verifying revenue formulas, rankings, monthly trends, regional comparisons, zero-baseline percentage handling, and exclusion disclosures.
- `test_data_quality.py`: 9 tests verifying isolation of returned items, zero quantities, negative values, null prices, and duplicate IDs.
- `test_api.py`: 15 tests verifying HTTP endpoints, query resolution, bad requests, missing fields, unsupported query handling, and frontend serving.

---

## 13. Troubleshooting & FAQ

- **Port 8000 already in use:** Specify a different port:
  `python -m uvicorn app.main:app --port 8080`
- **Database locked / concurrency error:** SQLite WAL mode is enabled by default to allow concurrent readers. Ensure previous Python processes are terminated if encountering file locks.
- **Where is the SQLite file?** It is stored in `database/sales_bi.db`. You can inspect it directly using standard SQLite tools (`sqlite3 database/sales_bi.db`).

---

## 14. Known Limitations

1. **Date Granularity:** The dataset covers January 2026 through June 2026. Queries requesting months outside this window (e.g., December) will return a clear message listing available months.
2. **Deterministic SQL Scope:** The deterministic engine supports the 5 required analytical question categories and their common synonyms. Arbitrary ad-hoc queries (e.g., *"What were sales for Desk in East region on Mondays?"*) return an unsupported status, directing the user to supported query formats.
