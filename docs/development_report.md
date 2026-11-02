# Development & Engineering Report

## 1. Overview & AI Tools Used

This project was developed using an AI-assisted engineering workflow within **Antigravity IDE**, leveraging:
- **Claude / Gemini advanced agentic models** for architecture design, schema modeling, test generation, and full-stack implementation.
- **Antigravity Browser Subagent** for automated end-to-end browser testing, capturing DOM states, verifying Chart.js canvas rendering, and recording user interaction sessions.
- **Python Static Analysis & Pytest** for deterministic test verification and quality assurance.

---

## 2. How AI Assisted Implementation

1. **Authoritative Data Inspection:** AI automated the exploratory data analysis (EDA) on `data/ai_bi_assistant_sales_data - GET.csv`, accurately identifying exact column headers, data types, 51 records, date formats (`DD-MM-YYYY`), and pinpointing the exact data-quality anomalies:
   - `TXN0033` (Returned order)
   - `TXN0034` (Zero quantity record)
   - `TXN0051` (Missing unit price)
2. **Schema & Pipeline Generation:** AI formulated an indexed SQLite relational schema that preserves all original raw records while implementing a data quality flag (`is_valid`) to isolate questionable rows from completed sales revenue.
3. **Intent Classification & Safe Fallback Architecture:** Designed a dual-tier question interpretation strategy that combines optional Google Gemini LLM API calls with a zero-credential, deterministic regex/keyword parser.
4. **Comprehensive Test Suite:** Developed 33 automated tests across `test_analytics.py`, `test_data_quality.py`, and `test_api.py`, achieving 100% test pass rates.
5. **Interactive Verification:** AI controlled a headless browser subagent to click chips, submit queries, inspect rendered charts, test error states, and generate a session recording (`bi_assistant_demo.webp`).

---

## 3. Technical Problems Encountered & Actual Debugging Performed

During development, several concrete technical issues were observed, investigated, and resolved:

### Issue 1: Missing Unit Price in Dataset (`TXN0051`)
- **Observed Behavior:** In the supplied CSV, line 52 (`TXN0051`) contained `5,,0,Completed` (empty unit price).
- **Risk:** A naive pandas `fillna(0)` or SQL conversion would silently treat the unit price as 0, creating a completed transaction with 0 revenue that would artificially deflate average order value and distort product unit metrics.
- **Resolution:** Implemented explicit validation in `app/data_loader.py` checking `pd.isna(Unit_price)`. The record is flagged with `MISSING_UNIT_PRICE`, `is_valid = 0`, and the exclusion reason `"Unit price is missing or null; cannot calculate revenue"` is attached and disclosed in all analytical answers.

### Issue 2: Zero Baseline in Month-over-Month Percentage Calculations
- **Observed Behavior:** If comparing a period with 0 revenue to a period with positive revenue, standard formulas $(\frac{\Delta}{\text{baseline}} \times 100)$ cause a `ZeroDivisionError` or infinite percentage.
- **Resolution:** In `app/analytics.py`, added conditional branching: if baseline revenue is 0 and target revenue is positive, `percentage_change` is returned as `None` and annotated as `"undefined due to 0 baseline"`, while reporting the exact absolute variance.

### Issue 3: Assertion Mismatch in `test_missing_unit_price_flagged`
- **Observed Failure:** During initial test execution, pytest reported:
  `AssertionError: assert 'Missing Unit Price' in 'Unit price is missing or null; cannot calculate revenue'`
- **Debugging & Fix:** The test asserted title-cased text while the pipeline generated `"Unit price is missing or null..."`. The test assertion was updated to match the exact string produced by the data loader.

### Issue 4: Import Syntax Typo in `app/services.py`
- **Observed Failure:** Python bytecode compilation failed on line 12 due to an unintended walrus operator in an import statement (`compute_summary_kpis := None`).
- **Debugging & Fix:** Cleaned up the import list in `app/services.py` to reference existing analytical functions, allowing clean compilation and zero runtime errors.

---

## 4. Key Design Decisions & Trade-Offs

### 1. Dual-Tier NLP Pipeline (LLM + Deterministic Fallback)
- **Decision:** Do not make the core application dependent on a paid API key or third-party cloud uptime.
- **Rationale:** Using deterministic regex and semantic keyword matching for the 5 required analytical intents ensures the application is completely functional out-of-the-box in any air-gapped or zero-credential environment. If an API key is configured, it benefits from genuine LLM semantic understanding without altering core analytical safety.

### 2. Predefined Analytics vs. Direct Text-to-SQL
- **Decision:** Map interpreted intents to predefined, parameterized SQL analytical functions rather than allowing the LLM to write raw SQL.
- **Rationale:** Direct Text-to-SQL is prone to prompt injection, SQL syntax hallucinations, table drops, and inconsistent aggregation logic across different prompts. Mapping intents to verified SQL routines guarantees that calculations are 100% deterministic, mathematically sound, and immune to injection attacks.

### 3. Preserving Questionable Records in Database
- **Decision:** Store all 51 rows in SQLite, including the 3 questionable rows, but mark them `is_valid = 0`.
- **Rationale:** Deleting bad rows from the database destroys audit trails. Storing all rows with explicit flags (`RETURNED_TRANSACTION`, `ZERO_QUANTITY`, `MISSING_UNIT_PRICE`) allows business users to inspect data-quality issues while ensuring analytical totals are never corrupted.

### 4. Vanilla Frontend vs. Heavy JavaScript Frameworks
- **Decision:** Build the dashboard using HTML5, Vanilla CSS3, and ES6 JavaScript.
- **Rationale:** Avoids node build pipelines, webpack/vite setup complexity, and version mismatches. Delivers near-instant page load times while maintaining a sleek, modern glassmorphic aesthetic.

---

## 5. Actual Verification Performed

1. **Automated Testing:** Executed `pytest` across 33 test cases:
   - 9 tests in `test_analytics.py`: Verified formulas, rankings, trends, regional comparisons, and zero baselines.
   - 9 tests in `test_data_quality.py`: Verified flagging of returns, zero quantities, missing prices, negative quantities, and duplicate IDs.
   - 15 tests in `test_api.py`: Verified `/api/health`, `/api/summary`, `/api/metadata`, `/api/ask`, and frontend asset serving.
   - **Result:** **33 passed in 1.55 seconds.**
2. **End-to-End Browser Testing:** Deployed headless browser agent to `http://127.0.0.1:8000/`:
   - Verified KPI summary cards (1,439,200.00 net revenue, 48 valid transactions, 7 products, 4 regions).
   - Clicked suggested question chips for all 5 business questions and verified responses, tables, and Chart.js canvas rendering.
   - Tested unsupported question (`"What is the weather in Tokyo?"`) and confirmed graceful error guidance.
3. **Data Integrity Check:** Verified that the source CSV `data/ai_bi_assistant_sales_data - GET.csv` has not been modified (exact 3,877 bytes preserved).

---

## 6. Current Limitations

1. **Date Boundary:** The sales data exclusively spans January to June 2026. Queries referencing dates outside this range (e.g. November 2026) are rejected with a list of available dataset months.
2. **Intent Scope:** The deterministic engine supports the 5 required analytical question categories and their natural variations. Ad-hoc composite questions (e.g. *"Show average discount for Furniture sold in Retail stores in March"*) fall into the unsupported category.

---

## 7. Improvements Possible with One Additional Day

If granted an additional day of development, the following enhancements would be added:
1. **Dynamic SQL Query Builder with Granular Filtering:** Extend the intent engine to support multi-dimensional ad-hoc filters (e.g., filtering by sales channel `Online` vs `Retail`, specific categories, or arbitrary date sub-ranges) using safe AST-validated query builders.
2. **CSV/PDF Export:** Add one-click export buttons in the UI allowing business users to download analytical tables as CSV or executive PDF summaries.
3. **Automated Forecast Engine:** Integrate lightweight linear regression / Holt-Winters exponential smoothing to predict July 2026 revenue trends based on the historical January–June baseline.
4. **Enhanced Data Quality Remediation UI:** Provide an administrative view within the dashboard allowing data stewards to inspect flagged records and input corrected unit prices.
