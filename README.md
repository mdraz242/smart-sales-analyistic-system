# Smart Sales Analytic System (WooCommerce B2C Sales Intelligence)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.36+-FF4B4B.svg)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Ready-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade Python web application and interactive business intelligence dashboard designed for WooCommerce B2C e-commerce stores. It connects securely via the official WooCommerce REST API v3, supports offline CSV/Excel data imports, reconciles top-line and unit metrics with 100% mathematical accuracy, and generates actionable statistical insights and AI-powered executive reports.

---

## 🌟 Key Features

1. **Executive Overview Dashboard**:
   - 12 high-impact executive KPI cards: Gross Sales, Net Sales, Revenue Collected, Total Orders, Units Sold, Average Order Value (AOV), Total Discounts, Total Refunds, Tax Collected, Shipping Revenue, Unique Customers, New vs Returning, Cancellation Rate, and Refund Rate.
   - Every KPI includes exact mathematical definitions, period-over-period baseline comparisons, and trend indicator badges.
   - Global multi-range date picker (Today, Yesterday, Last 7d, Last 30d, Last 90d, MTD, Previous Month, QTD, YTD, Custom).

2. **Product Performance Intelligence**:
   - **Top 20 Best-Selling Products**: Switchable ranking criteria by Units Sold, Net Sales, Gross Sales, Orders Count, and Sales Growth Velocity.
   - **Profitability & COGS Engine**: Cost of Goods Sold tracking, Gross Profit, and Gross Margin %.
   - **9-Class Automated Performance Taxonomy**:
     - *Best Sellers* (top 20% in volume & revenue)
     - *Rising Stars* (>25% unit velocity growth)
     - *Declining Products* (<-20% contraction)
     - *Low Performers* (stagnant bottom quartile)
     - *High Revenue Lines* (>=10% store revenue share)
     - *High Margin Lines* (gross margin $\ge 50\%$)
     - *Frequently Refunded Lines* (refund rate $> 1.5\times$ store average)
     - *Discount-Dependent Lines* ($\ge 25\%$ coupon/discount ratio)
     - *Stockout Risks* (<10 units remaining with high velocity)
   - Multi-product comparative trend analysis.

3. **Revenue & Sales Analytics**:
   - Dynamic time-series granularity (Daily, Weekly, Monthly) with dual-axis sales vs order volume.
   - **7x24 Peak Sales Heatmap**: Identifies peak purchasing hours and days of the week.
   - Breakdown by payment method, shipping method, coupon code, and customer geography.

4. **Category Intelligence**:
   - Category revenue share donut charts, unit volume, category-level AOV, and growth rates.
   - Multi-category products handled cleanly without double counting store-wide totals.
   - Product catalog drilldown by category.

5. **B2C Customer Intelligence & Retention**:
   - RFM behavioral customer segmentation: High-Value, Frequent Buyers, One-Time Customers, Inactive (>90 days), and Declining Frequency.
   - **Monthly Retention Cohort Heatmap**: Measures retention and repeat purchase behavior by acquisition month.
   - Pseudonymous privacy protection using SHA-256 hashed customer identifiers.

6. **Order & Fulfillment Analytics**:
   - Order status distribution (Completed, Processing, Cancelled, Failed, Refunded).
   - Fulfillment cycle time tracking (average hours and days from placement to completion).
   - Basket size analysis: average units per order and multi-item order percentages.

7. **Automated Business Insights & AI Report Generator**:
   - Pure statistical Python/Pandas rules engine producing plain-English prescriptive recommendations with severity badges (`CRITICAL`, `WARNING`, `OPPORTUNITY`, `INFO`).
   - Provider-independent LLM report generator (supports OpenAI, Anthropic, Gemini, or deterministic offline Analyst mode).
   - Zero hallucination: All statements strictly grounded in verified aggregated metrics.

8. **WooCommerce REST API Client & Synchronization**:
   - HMAC/Basic authentication with exponential backoff and rate-limit handling (`429 Retry-After`).
   - Incremental and full historical synchronization with idempotent upserting (eliminates duplicate orders and line items).

9. **Data Imports & Product Cost Management**:
   - CSV and Excel file uploader for Product Costs (COGS), SKU mapping, and offline orders.
   - Pre-validation preview table and row-level error reporting before committing to the database.

10. **Multi-Format Exports**:
    - Multi-sheet Excel workbook with formatted sheets for KPIs, Top 20 Products, Categories, and Actionable Insights.
    - Publication-ready Executive PDF report generated with ReportLab.
    - Active filter-aware CSV export.

---

## 📐 Mathematical Reconciliation & Metric Definitions

To ensure strict financial reconciliation with WooCommerce core accounting:

| Metric | Formula | Reconciled Definition |
| :--- | :--- | :--- |
| **Gross Sales** | $\sum (\text{item\_price} \times \text{quantity})$ | Total merchandise subtotal for completed/processing orders before discounts, taxes, or shipping. |
| **Total Discounts** | $\sum \text{coupon\_discount} + \sum \text{line\_discounts}$ | Total promotional coupon and item-level discounts. |
| **Total Refunds** | $\sum \|\text{refund\_amount}\|$ | Approved customer returns/refunds issued against completed/processing orders. |
| **Net Sales** | $\text{Gross Sales} - \text{Discounts} - \text{Refunds}$ | Top-line merchandise sales after promotional adjustments and customer returns. |
| **Revenue Collected** | $\text{Net Sales} + \text{Shipping} + \text{Tax}$ | Total settled cash and receivables. |
| **Average Order Value** | $\frac{\text{Net Sales}}{\text{Total Valid Orders}}$ | Average net merchandise spend per successful order. |
| **Units Sold** | $\sum \text{item\_quantity} - \sum \text{refunded\_units}$ | Net physical merchandise units sold. |
| **COGS & Margin** | $\text{Net Sales} - \sum (\text{unit\_cost} \times \text{units})$ | Gross profit and margin % evaluated only when cost data exists. |

---

## 🏗️ Repository Architecture

```
├── backend/
│   ├── app/
│   │   ├── config.py              # Pydantic Settings & environment variables
│   │   ├── database.py            # SQLAlchemy engine, session maker, SQLite/PostgreSQL
│   │   ├── models/                # Normalized relational SQLAlchemy models
│   │   │   ├── store.py           # Store & User accounts
│   │   │   ├── product.py         # Products, Variations, Categories, Snapshots
│   │   │   ├── order.py           # Orders, Line Items, Refunds, Coupons
│   │   │   ├── customer.py        # Customer profiles & privacy hashing
│   │   │   ├── cost.py            # Product unit cost history
│   │   │   └── sync.py            # Synchronization and report logs
│   │   ├── schemas/               # Pydantic validation schemas
│   │   ├── services/              # Core business engines
│   │   │   ├── analytics_engine.py      # Core metrics, 9-class classifier, cohorts
│   │   │   ├── insights_engine.py       # Automated plain-English insight generator
│   │   │   ├── ai_report_service.py     # Provider-independent LLM report generator
│   │   │   ├── import_service.py        # CSV/Excel validation & COGS import
│   │   │   ├── export_service.py        # Multi-tab Excel & PDF report generator
│   │   │   ├── woocommerce_client.py    # WooCommerce REST API v3 client
│   │   │   ├── sync_service.py          # Incremental synchronization engine
│   │   │   └── sample_data_generator.py # 180-day realistic sample e-commerce seeder
│   │   ├── api/
│   │   │   ├── main.py            # FastAPI entrypoint with auto-seeding lifespan
│   │   │   └── routers/           # Analytics, Sync, Imports, and Reports endpoints
│   │   └── utils/                 # Timezones, currency, and date window helpers
├── frontend/
│   ├── app.py                     # Streamlit main dashboard with 10 interactive modules
│   ├── components/                # Modular UI components (KPI cards, Plotly charts, filters)
│   └── styles/                    # Modern SaaS dark/light CSS design tokens
├── tests/                         # Pytest automated test suite (18 unit & integration tests)
├── data/sample_import_files/      # Ready-to-use CSV and Excel sample cost files
├── reports_output/                # Generated sample Excel and PDF report artifacts
├── docker-compose.yml             # Docker Compose orchestration
├── Dockerfile                     # Container build file
├── requirements.txt               # Dependencies
├── .env.example                   # Environment variable template
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.12 or higher
- Git

### 2. Installation
```bash
# Clone the repository
git clone <repo-url>
cd python

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
```

### 3. Launching the Interactive Streamlit Dashboard
```bash
source .venv/bin/activate
streamlit run frontend/app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.  
*Note: On first run, the platform automatically initializes SQLite and seeds a realistic 180-day B2C dataset with 24 products, 800+ orders, refunds, and customer accounts so you can immediately explore full analytics!*

### 4. Running the FastAPI REST Backend (Optional)
```bash
source .venv/bin/activate
uvicorn backend.app.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 🐳 Docker Deployment

To spin up the entire platform (FastAPI, Streamlit Dashboard, and PostgreSQL) with Docker Compose:

```bash
docker-compose up --build
```
- Dashboard: [http://localhost:8501](http://localhost:8501)
- FastAPI REST API: [http://localhost:8000](http://localhost:8000)
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Running Automated Tests

Run the full pytest suite verifying financial calculations, period reconciliation, refund handling, order normalization, and REST endpoints:

```bash
source .venv/bin/activate
pytest tests/ -v
```

All 18 tests execute in ~2 seconds:
- `test_metric_reconciliation`: Reconciles Gross - Discounts - Refunds = Net Sales.
- `test_cancelled_orders_excluded_from_sales`: Ensures cancelled/failed orders do not corrupt revenue.
- `test_executive_kpis_period_comparison`: Verifies delta and trend pill generation.
- `test_category_analytics_no_double_counting`: Verifies multi-category weighting integrity.
- `test_customer_cohorts_and_segments`: Validates monthly cohort retention matrix.
- `test_order_sync_normalization_and_idempotency`: Verifies duplicate sync prevention.
- `test_product_ranking_by_units_and_net_sales`: Verifies switchable rankings.
- `test_product_classification_rules`: Tests the 9-class product performance taxonomy.
- `test_automated_insights_generation`: Tests plain-English prescription generation.
- `test_validate_and_commit_product_costs`: Tests row-level CSV validation and cost commit.
- `test_excel_and_pdf_export_generation`: Tests binary workbook and PDF generation.
- `test_health_endpoint`, `test_kpi_endpoint`, `test_products_endpoint`, etc.

---

## 🔌 Connecting a Live WooCommerce Store

1. In WooCommerce Admin, navigate to **WooCommerce > Settings > Advanced > REST API**.
2. Click **Add Key**, select **Read/Write** permissions, and generate keys.
3. Open the **WooCommerce Sync** page in the CommercePulse dashboard.
4. Enter your Store URL, Consumer Key, and Consumer Secret.
5. Click **Test API Connection** to verify connectivity and store metadata.
6. Click **Run Incremental Sync** or **Run Full Re-Sync**. All records will be safely normalized and indexed without duplicate records.

---

## 📄 License
This project is licensed under the MIT License.
