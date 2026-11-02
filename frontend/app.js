/**
 * Mini AI Business Intelligence Assistant Frontend Logic
 * Interacts with FastAPI backend to load KPIs, metadata, and answer queries.
 */

// Global Chart instance reference to allow clean re-rendering
let activeChartInstance = null;

// DOM Elements
const statusIndicator = document.getElementById("status-indicator");
const statusText = document.getElementById("status-text");
const kpiTotalRevenue = document.getElementById("kpi-total-revenue");
const kpiGrossDiscounts = document.getElementById("kpi-gross-discounts");
const kpiValidTxns = document.getElementById("kpi-valid-txns");
const kpiUnitsSold = document.getElementById("kpi-units-sold");
const kpiProductCount = document.getElementById("kpi-product-count");
const kpiRegionCount = document.getElementById("kpi-region-count");

const questionForm = document.getElementById("question-form");
const questionInput = document.getElementById("question-input");
const askBtn = document.getElementById("ask-btn");
const btnText = document.getElementById("btn-text");
const btnSpinner = document.getElementById("btn-spinner");

const emptyState = document.getElementById("empty-state");
const resultsSection = document.getElementById("results-section");
const resultIntentBadge = document.getElementById("result-intent-badge");
const resultInterpreterBadge = document.getElementById("result-interpreter-badge");
const resultQuestion = document.getElementById("result-question");
const resultAnswer = document.getElementById("result-answer");
const resultMetricLabel = document.getElementById("result-metric-label");
const resultMetricValue = document.getElementById("result-metric-value");
const dqNotesList = document.getElementById("dq-notes-list");

const chartCard = document.getElementById("chart-card");
const chartTitle = document.getElementById("chart-title");
const chartCanvas = document.getElementById("analytics-chart");

const tableCard = document.getElementById("table-card");
const tableHead = document.getElementById("table-head");
const tableBody = document.getElementById("table-body");

const copyBtn = document.getElementById("copy-btn");
const errorToast = document.getElementById("error-toast");
const errorMessage = document.getElementById("error-message");
const toastCloseBtn = document.getElementById("toast-close-btn");

// Formatting Helpers
function formatNumber(val) {
    if (val === null || val === undefined) return "--";
    if (typeof val === "number") {
        return val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return String(val);
}

function formatInteger(val) {
    if (val === null || val === undefined) return "--";
    return Number(val).toLocaleString();
}

function humanizeHeader(key) {
    return key
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

// Show Error Toast
function showError(msg) {
    errorMessage.textContent = msg;
    errorToast.classList.remove("hidden");
    setTimeout(() => {
        errorToast.classList.add("hidden");
    }, 8000);
}

// Toast close event
if (toastCloseBtn) {
    toastCloseBtn.addEventListener("click", () => {
        errorToast.classList.add("hidden");
    });
}

// Load Application Health & Initial Summary
async function loadHealthAndSummary() {
    try {
        const healthRes = await fetch("/api/health");
        if (healthRes.ok) {
            const healthData = await healthRes.json();
            if (healthData.database_connected) {
                statusIndicator.className = "status-badge status-connected";
                statusText.textContent = `Connected (${healthData.valid_records} Valid Sales)`;
            } else {
                statusIndicator.className = "status-badge status-error";
                statusText.textContent = "DB Degraded";
            }
        } else {
            statusIndicator.className = "status-badge status-error";
            statusText.textContent = "Service Offline";
        }
    } catch (err) {
        statusIndicator.className = "status-badge status-error";
        statusText.textContent = "Offline";
    }

    try {
        const summaryRes = await fetch("/api/summary");
        if (summaryRes.ok) {
            const data = await summaryRes.json();
            kpiTotalRevenue.textContent = `${formatNumber(data.total_completed_net_revenue)}`;
            kpiGrossDiscounts.textContent = `Gross: ${formatNumber(data.total_completed_gross_revenue)} | Disc: ${formatNumber(data.total_discounts)}`;
            kpiValidTxns.textContent = `${formatInteger(data.valid_transactions)}`;
            kpiUnitsSold.textContent = `${formatInteger(data.total_units_sold)} units sold (${data.excluded_records_count} excluded)`;
            kpiProductCount.textContent = `${formatInteger(data.products_count)}`;
            kpiRegionCount.textContent = `${formatInteger(data.regions_count)}`;
        }
    } catch (err) {
        console.error("Failed to load initial summary metrics:", err);
    }
}

// Render Chart.js Visualization
function renderChart(chartConfig) {
    if (!chartConfig || !chartConfig.labels || !chartConfig.datasets) {
        chartCard.classList.add("hidden");
        return;
    }

    chartCard.classList.remove("hidden");
    chartTitle.textContent = chartConfig.title || "Data Visualization";

    // Destroy existing chart if present
    if (activeChartInstance) {
        activeChartInstance.destroy();
        activeChartInstance = null;
    }

    if (typeof Chart === "undefined") {
        console.warn("Chart.js not loaded. Skipping chart rendering.");
        return;
    }

    const ctx = chartCanvas.getContext("2d");

    // Standard dark mode chart options
    const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: "#94A3B8",
                    font: { family: "Inter", size: 12 },
                },
            },
            tooltip: {
                backgroundColor: "#1E293B",
                titleColor: "#F8FAFC",
                bodyColor: "#CBD5E1",
                borderColor: "rgba(255, 255, 255, 0.1)",
                borderWidth: 1,
                padding: 10,
                callbacks: {
                    label: function (context) {
                        let label = context.dataset.label || "";
                        if (label) label += ": ";
                        if (context.parsed.y !== null) {
                            label += context.parsed.y.toLocaleString();
                        }
                        return label;
                    },
                },
            },
        },
        scales: {
            x: {
                grid: { color: "rgba(255, 255, 255, 0.05)" },
                ticks: { color: "#94A3B8", font: { family: "Inter", size: 11 } },
            },
            y: {
                grid: { color: "rgba(255, 255, 255, 0.05)" },
                ticks: {
                    color: "#94A3B8",
                    font: { family: "Inter", size: 11 },
                    callback: function (val) {
                        return val >= 1000 ? (val / 1000).toFixed(0) + "k" : val;
                    },
                },
            },
        },
    };

    // If dual y-axis dataset
    if (chartConfig.datasets.some((ds) => ds.yAxisID === "y1")) {
        options.scales.y1 = {
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { color: "#F59E0B", font: { family: "Inter", size: 11 } },
        };
    }

    activeChartInstance = new Chart(ctx, {
        type: chartConfig.chart_type || "bar",
        data: {
            labels: chartConfig.labels,
            datasets: chartConfig.datasets,
        },
        options: options,
    });
}

// Render Supporting Data Table
function renderSupportingTable(rows) {
    if (!rows || rows.length === 0) {
        tableCard.classList.add("hidden");
        return;
    }

    tableCard.classList.remove("hidden");
    tableHead.innerHTML = "";
    tableBody.innerHTML = "";

    const headers = Object.keys(rows[0]);

    // Build thead
    const headerRow = document.createElement("tr");
    headers.forEach((h) => {
        const th = document.createElement("th");
        th.textContent = humanizeHeader(h);
        if (typeof rows[0][h] === "number") {
            th.classList.add("cell-numeric");
        }
        headerRow.appendChild(th);
    });
    tableHead.appendChild(headerRow);

    // Build tbody
    rows.forEach((row) => {
        const tr = document.createElement("tr");
        headers.forEach((h) => {
            const td = document.createElement("td");
            const val = row[h];
            if (typeof val === "number") {
                td.classList.add("cell-numeric");
                td.textContent = h.includes("pct") || h.includes("share") || h.includes("growth")
                    ? `${val.toFixed(2)}%`
                    : Number.isInteger(val)
                    ? val.toLocaleString()
                    : val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            } else {
                td.textContent = val !== null && val !== undefined ? val : "--";
            }
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });
}

// Submit Natural-Language Question
async function submitQuestion(questionText) {
    const q = (questionText || questionInput.value).trim();
    if (!q) {
        showError("Please enter a question.");
        return;
    }

    // Set UI to loading state
    questionInput.value = q;
    askBtn.disabled = true;
    btnText.textContent = "Processing...";
    btnSpinner.classList.remove("hidden");

    try {
        const res = await fetch("/api/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: q }),
        });

        const data = await res.json();

        if (!res.ok) {
            showError(data.detail || "Error querying assistant.");
            return;
        }

        // Hide empty state, reveal results
        emptyState.classList.add("hidden");
        resultsSection.classList.remove("hidden");

        // Format Badges
        const intentDisplayNames = {
            total_revenue: "Total Net Revenue",
            highest_revenue_product: "Top Revenue Product",
            monthly_revenue_trend: "Monthly Trend",
            highest_sales_region: "Regional Performance",
            revenue_change_between_months: "Month-over-Month Variance",
            unsupported: "Unsupported Question",
            invalid: "Invalid Input",
        };
        resultIntentBadge.textContent = intentDisplayNames[data.intent] || data.intent;

        const interpreterNames = {
            rule_based_fallback: "Deterministic Rule Engine",
            gemini_llm: "Google Gemini LLM",
            openai_llm: "OpenAI LLM",
        };
        resultInterpreterBadge.textContent = interpreterNames[data.interpreter_used] || data.interpreter_used;

        // Populate Answer and Question
        resultQuestion.textContent = `"${data.question}"`;
        resultAnswer.textContent = data.answer;

        // Key Metric Highlight
        if (data.value !== null && data.value !== undefined && data.intent !== "unsupported" && data.intent !== "invalid") {
            resultMetricLabel.textContent = humanizeHeader(data.metric || "Primary Metric");
            const formattedVal = typeof data.value === "number" ? formatNumber(data.value) : data.value;
            resultMetricValue.textContent = `${formattedVal} ${data.unit !== "none" ? data.unit : ""}`;
            document.getElementById("metric-highlight-container").classList.remove("hidden");
        } else {
            document.getElementById("metric-highlight-container").classList.add("hidden");
        }

        // Data Quality Notes
        dqNotesList.innerHTML = "";
        const notes = data.data_quality_notes || [];
        if (notes.length > 0) {
            notes.forEach((note) => {
                const li = document.createElement("li");
                li.textContent = note;
                dqNotesList.appendChild(li);
            });
            document.getElementById("data-quality-box").classList.remove("hidden");
        } else {
            document.getElementById("data-quality-box").classList.add("hidden");
        }

        // If backend returned an error string inside structured response
        if (data.error && (data.intent === "unsupported" || data.intent === "invalid")) {
            showError(data.error);
        }

        // Render Chart
        renderChart(data.chart);

        // Render Supporting Table
        renderSupportingTable(data.supporting_data);

        // Scroll gracefully to results
        resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });

    } catch (err) {
        showError(`Network connection error: ${err.message}`);
    } finally {
        askBtn.disabled = false;
        btnText.textContent = "Ask Assistant";
        btnSpinner.classList.add("hidden");
    }
}

// Event Listeners
questionForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submitQuestion();
});

// Clickable Suggested Question Chips
document.querySelectorAll(".query-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        const text = chip.getAttribute("data-question");
        if (text) {
            submitQuestion(text);
        }
    });
});

// Copy Answer Button
if (copyBtn) {
    copyBtn.addEventListener("click", () => {
        const text = resultAnswer.textContent;
        if (navigator.clipboard && text) {
            navigator.clipboard.writeText(text).then(() => {
                const orig = copyBtn.innerHTML;
                copyBtn.textContent = "Copied!";
                setTimeout(() => {
                    copyBtn.innerHTML = orig;
                }, 2000);
            });
        }
    });
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    loadHealthAndSummary();
});
