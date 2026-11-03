# Data Detective 🔍

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20|%203.14-3776AB.svg?style=flat&logo=python)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-2.2+-150458.svg?style=flat&logo=pandas)](https://pandas.pydata.org/)
[![ReportLab](https://img.shields.io/badge/ReportLab-4.0+-005571.svg?style=flat)](https://www.reportlab.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Data Detective** is a high-performance, lightweight, and secure web application for **Automated Exploratory Data Analysis (EDA)**, **Interactive Data Cleaning & Preprocessing**, **Dynamic Visualization Dashboards**, and **Publication-Ready PDF Report Generation**.

Engineered with a **100% ephemeral in-memory processing pipeline**, Data Detective never persists uploaded datasets to disk, enforcing strict confidentiality, rapid throughput, and complete multi-format compatibility across **CSV**, **Excel (.xlsx)**, **JSON**, and **JSON Lines (.jsonl / .ndjson)**.

---

## 🌟 Key Features by Phase

### Phase 1: System Foundation & Diagnostics
* **Live System Health Monitoring:** Real-time backend connectivity checks with automated recovery indicators.
* **Diagnostics Panel:** Instant inspection of server latency, API version, and root configuration.
* **Production Security Headers:** Out-of-the-box injection of `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, and `Referrer-Policy: strict-origin-when-cross-origin`.

### Phase 2: In-Memory Multi-Format Dataset Ingestion
* **Drag-and-Drop Ingestion:** Support for files up to **10 MB** in `.csv`, `.xlsx`, `.json`, `.jsonl`, and `.ndjson`.
* **Zero Disk Footprint:** Datasets are parsed directly in-memory into Pandas DataFrames and never saved to permanent storage.
* **Instant Profiling & Preview:** Displays real-time file size, row count, column count, detected format badge, data type schema, and a 5-row interactive preview.

### Phase 3: Automated Exploratory Data Analysis (EDA)
* **Statistical Summaries:** Computes mean, standard deviation, minimum, 25th percentile ($Q_1$), median, 75th percentile ($Q_3$), and maximum for all numerical metrics.
* **Categorical Profiling:** Unique count, top category, and mode frequency for text/discrete features.
* **Data Quality Auditing:** Exact missing value counts and percentages per column, plus complete duplicate row detection.
* **Outlier Detection via IQR:** Automated identification of extreme values using the Tukey Interquartile Range method ($[Q_1 - 1.5 \times \text{IQR},\, Q_3 + 1.5 \times \text{IQR}]$).
* **Correlation Matrices:** Pearson correlation coefficients computed across numerical attributes with NaN resilience.
* **Distribution Histograms:** Automated frequency binning and categorical distribution bars.

### Phase 4: Interactive Data Cleaning & Preprocessing Studio
* **Missing Value Imputation:**
  * Drop rows containing missing values (column-specific or across all columns).
  * Impute numerical missing values using **Mean** or **Median**.
  * Impute categorical missing values using **Mode**.
  * Fill with custom user-defined literal values.
* **Duplicate Management:** Automated detection and removal of duplicate rows with preservation of the first occurrence.
* **Safe Type Casting:** Convert column types into `Integer` (nullable `Int64`), `Float`, `String`, or `Datetime` without breaking on dirty records.
* **IQR Outlier Treatment:** Remove outlier rows or cap (clip) them strictly to calculated IQR bounds upon user confirmation.
* **Categorical Encoding:** One-click **Label Encoding** ($0..K-1$) and **One-Hot Encoding** (dummy binary indicators).
* **Feature Scaling:** **Min-Max Normalization** ($[0, 1]$) and **Z-Score Standardization** ($\mu = 0, \sigma = 1$).
* **Column Management:** Collision-safe column renaming and unneeded column dropping.
* **Live Studio Workflow:**
  * Visual scheduled operations pipeline.
  * Side-by-side **Before vs. After** difference metrics and preview comparison.
  * "Apply Cleaned Dataset" action to promote cleaned data to the working in-memory dataset for immediate re-analysis.
  * Direct downloads in **CSV**, **Excel (.xlsx)**, and **JSON** formats.

### Phase 5: Interactive Data Visualization Studio
* **Seven Built-In Chart Types:**
  1. **Bar Chart:** Categorical comparisons with optional aggregations (`Count`, `Sum`, `Mean`, `Median`) and top-14 category capping + "Other".
  2. **Line Chart:** Ordered sequence/trend analysis with intelligent downsampling (capped at 500 points for fluid rendering).
  3. **Pie & Donut Charts:** Category composition and proportion breakdown (top-9 categories + "Other").
  4. **Histogram:** Frequency distributions of numerical features with automated Sturges/Freedman-Diaconis binning.
  5. **Scatter Plot:** Bivariate numerical relationships with Pearson correlation $r$ calculation and point downsampling (capped at 1,000 points).
  6. **Box Plot:** Custom high-DPI Canvas 2D renderer displaying the five-number summary, IQR whiskers, and individual outlier markers.
  7. **Correlation Heatmap:** Interactive pairwise Pearson correlation matrix with adaptive color gradients and cell annotations.
* **Dataset Switcher (Original vs. Cleaned):** Seamlessly toggle between raw uploaded data and cleaned dataset with dynamic dropdown synchronization.
* **Analytical Dashboard Grid:** Multi-chart analytical workspace with individual chart card removal, metric badges, and bulk "Regenerate on Current Dataset".
* **High-Resolution PNG Exports:** Individual chart image download or single-click **Download All Charts (PNG)** batch export.

### Phase 6: Automated EDA Report Generation Studio
* **Publication-Ready PDF Generation:** Engineered using **ReportLab** with a professional 9-page layout.
* **Executive Document Structure:**
  1. **Cover Page:** Data Detective branding, dataset filename, timestamp, dimensions, and confidentiality badge.
  2. **Dataset Overview & Metadata:** Dimensions, numerical/categorical feature split, and memory footprint.
  3. **Statistical Profile:** Complete five-number statistical summaries.
  4. **Data Quality Analysis:** Missing value breakdown, duplicate counts, and column-wise cardinality.
  5. **Outlier Audit:** IQR formulas, quartile metrics, and outlier counts.
  6. **Correlation Matrix:** Tabular correlation metrics and embedded high-resolution Matplotlib heatmap.
  7. **Visual Distributions:** High-resolution embedded histogram, categorical frequency, and box plot figures.
  8. **Cleaning History & Before vs. After:** Complete transformation audit log and comparative row/column delta metrics.
* **Ephemeral Delivery:** Streamed directly over HTTP with zero PDF files stored on the server.

### Phase 7: Deployment Readiness & Security Hardening
* **Content-Based Security Verification:**
  * OpenXML ZIP archive magic header verification (`PK\x03\x04`) and archive component validation (`[Content_Types].xml`, `xl/workbook.xml`) to reject disguised malicious files.
  * Decompression bomb protection: Blocks Excel archives exceeding a safe uncompressed ceiling.
  * Binary payload detection: Inspects CSV and JSON files for null bytes (`b"\x00"`), rejecting executables or binaries renamed to `.csv`.
  * Safe flattening: Prevents relational 1-to-many nested array data corruption with descriptive guidance.
* **Environment Configuration:** Supports `.env` overrides for host, port, reload, CORS origins, and upload limits.
* **Fully Responsive UI:** Optimized across Desktop (1280px+), Tablet (768px), and Mobile (375px) devices.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Data Detective UI                             │
│       (HTML5 / Responsive CSS3 / Vanilla JavaScript / Chart.js)        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST (In-Memory Streams)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application Gateway                     │
│         (CORS, Security Headers, Global Sanitized Error Handlers)      │
└───────────┬───────────────────────┬──────────────────────┬─────────────┘
            │                       │                      │
            ▼                       ▼                      ▼
┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
│      EDA Engine       │ │  Cleaning Engine  │ │ Visualization Engine  │
│ (Parsing, Validation, │ │ (Imputation, IQR, │ │ (Downsampling, 7 chart│
│  Stats, Outliers,     │ │  Encoding, Scale, │ │  types, Sanitization) │
│  Correlations)        │ │  Exports CSV/XLSX)│ │                       │
└───────────┬───────────┘ └─────────┬─────────┘ └───────────────────────┘
            │                       │
            └───────────┬───────────┘
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         ReportLab PDF Engine                           │
│  (Multi-page publication document, embedded Matplotlib visualizations) │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Directory Structure

```
Data-Detective/
│
├── backend/
│   ├── main.py                     # FastAPI application entrypoint and route handlers
│   ├── requirements.txt            # Python production dependencies
│   ├── services/
│   │   ├── __init__.py             # Package marker
│   │   ├── eda_engine.py           # In-memory parsing, format validation, and EDA profiling
│   │   ├── cleaning_engine.py      # Data cleaning pipeline, imputation, and multi-format exports
│   │   ├── visualization_engine.py # Chart data transformations, downsampling, and payload generation
│   │   └── report_engine.py        # Publication-ready PDF report compiler via ReportLab
│   └── uploads/                    # Ephemeral uploads placeholder (.gitkeep)
│
├── frontend/
│   ├── index.html                  # Core application interface across all studio sections
│   ├── css/
│   │   └── style.css               # Responsive design, light theme, blue accents, cross-device polish
│   ├── js/
│   │   ├── chart.min.js            # Standalone offline local Chart.js bundle
│   │   └── script.js               # Dynamic API client, DOM controller, and chart rendering engine
│   └── assets/                     # Static assets (.gitkeep)
│
├── samples/                        # Production turnkey test datasets
│   ├── sample_sales.csv            # Retail sales CSV dataset
│   ├── sample_employees.xlsx       # Human resources Excel spreadsheet
│   ├── sample_users_flat.json      # Standard flat JSON records dataset
│   ├── sample_orders_nested.json   # Hierarchical nested JSON orders dataset
│   └── sample_events.jsonl         # Telemetry events JSON Lines dataset
│
├── .env.example                    # Template environment configuration file
├── .gitignore                      # Git exclusion rules
└── README.md                       # Complete project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
* **Python 3.10+** (Python 3.11, 3.12, 3.13, or 3.14 fully supported)
* A modern web browser (Chrome, Edge, Firefox, Safari)

### 2. Environment Setup

Clone the repository and navigate into the project directory:

```bash
git clone https://github.com/your-username/data-detective.git
cd data-detective
```

Create and activate a virtual environment:

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:
```bash
pip install -r backend/requirements.txt
```

Create your `.env` configuration file:
```bash
# On Linux / macOS:
cp .env.example .env

# On Windows:
copy .env.example .env
```

---

## 🏃 Running the Application

### 1. Start the FastAPI Backend

From the project root:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Or run directly via python:
```powershell
python backend/main.py
```

The backend server will initialize:
* **API Base URL:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Interactive Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Interactive ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 2. Start the Frontend

Serve the `frontend/` directory using Python's built-in HTTP server:

```powershell
python -m http.server 3000 --directory frontend
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000) in your web browser. The interface will automatically discover the backend on port 8000, verify connectivity, and update system status.

---

## 🌐 Production Deployment

### Production Execution with Uvicorn / Gunicorn
For production environments, execute Uvicorn with multiple worker processes:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or using Gunicorn with Uvicorn workers:
```bash
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `127.0.0.1` | Network interface IP to bind the server |
| `PORT` | `8000` | Port number for the FastAPI HTTP server |
| `RELOAD` | `false` | Enable hot-reloading for development |
| `ALLOWED_ORIGINS` | `*` | Comma-separated list of allowed CORS domains |
| `MAX_FILE_SIZE_MB`| `10` | Maximum allowed payload upload size in megabytes |
| `ENVIRONMENT` | `production`| Environment label returned by root health check |

### Customizing Frontend API Endpoint
If the backend is hosted on a separate domain (e.g. `https://api.datadetective.com`), configure the frontend without editing code:
1. Set `window.DATA_DETECTIVE_API_URL = "https://api.datadetective.com";` in a custom `<script>` tag or HTML meta tag.
2. Or set it in browser storage: `localStorage.setItem("DATA_DETECTIVE_API_URL", "https://api.datadetective.com")`.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Root endpoint returning application status, version, environment, and docs link |
| `GET` | `/health` | Health check returning `{"status": "healthy"}` |
| `POST`| `/api/upload` | Validates, parses in-memory, and returns metadata, schema, and 5-row preview |
| `POST`| `/api/analyze` | Automated EDA: Overview, statistical summary, missing values, duplicates, outliers, correlations, and distributions |
| `POST`| `/api/clean/preview` | Simulates cleaning pipeline in-memory; returns Before vs. After diff and operations log |
| `POST`| `/api/clean/download` | Applies cleaning pipeline and returns downloadable file in **CSV**, **Excel (.xlsx)**, or **JSON** |
| `POST`| `/api/export/original` | In-memory format conversion of raw uploaded datasets (e.g. CSV $\to$ JSON, JSON $\to$ Excel) |
| `POST`| `/api/visualize` | Server-side validated chart payload generation for 7 chart types with downsampling |
| `POST`| `/api/report/generate` | Compiles publication-ready 9-page PDF report with embedded charts and before/after comparisons |

---

## 📊 Supported File Formats & Ingestion Details

* **CSV (`.csv`):** Delimited text parsed with UTF-8 encoding (automatic fallback to Latin-1). Binary null-byte verification protects against disguised executables.
* **Excel (`.xlsx`):** Open Packaging Convention spreadsheet parsed via `openpyxl`. Protected by magic header checks (`PK\x03\x04`), internal OpenXML component validation (`[Content_Types].xml`), and decompression bomb ceilings.
* **JSON (`.json`):** Standard JSON arrays of objects (`[{"id": 1, ...}]`) or single wrapper objects (`{"data": [...]}`). Hierarchical objects are automatically flattened via `pd.json_normalize` up to 10 levels deep.
* **JSON Lines (`.jsonl`, `.ndjson`):** Newline-delimited JSON stream where each row represents an independent record object.
* **Nested Array Protection:** Relational 1-to-many arrays containing nested objects or multi-dimensional matrices are rejected with an explicit `400 Bad Request` explaining why they cannot be represented as a single table without data loss.

---

## 🧪 Testing & Verification

Comprehensive automated test suites are provided in the repository:

```powershell
# Run the complete Phase 7 Final Audit Suite:
python scratch/phase7_final_audit_suite.py

# Run the Multi-Format (CSV, XLSX, JSON) Comprehensive Suite:
python scratch/comprehensive_multiformat_suite.py

# Run the Phase 6 PDF Report Engine Suite:
python scratch/comprehensive_phase6_suite.py

# Run the Responsive Browser Verification Suite (Headless Chrome):
python scratch/verify_responsive_ui.py
```

---

## 🛠️ Troubleshooting

### 1. "Failed to reach backend at http://127.0.0.1:8000"
* Ensure the FastAPI backend server is active: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
* Check if port 8000 is occupied by another process (`netstat -ano | findstr :8000`).
* Check CORS settings: in `.env`, verify `ALLOWED_ORIGINS=*` or that your frontend domain is whitelisted.

### 2. "File exceeds maximum allowed size of 10 MB"
* The system strictly enforces a 10 MB ceiling for uploads to maintain responsiveness and prevent denial-of-service. Filter or downsample the dataset before uploading.

### 3. "Unsupported JSON structure: Field contains a nested array of objects"
* Relational 1-to-many arrays (e.g. `items: [{sku: "A"}, {sku: "B"}]`) cannot be converted into a single two-dimensional table without duplicating rows or discarding data. Flatten or normalize the array prior to ingestion.

### 4. Excel Upload "The uploaded file is a zip archive but does not contain valid Excel components"
* Ensure the file is an actual `.xlsx` spreadsheet, not a generic `.zip` archive or `.csv` file renamed with an `.xlsx` extension.

---

## 📄 License

This project is licensed under the MIT License — see the LICENSE file for details.
