# 🎥 DataSentinel — 5-Minute Demo Walkthrough Script

This guide provides a step-by-step walkthrough script for presenting or recording a 5-minute demo of **DataSentinel**, demonstrating all key capabilities: CLI interface, multi-source validation, schema drift detection, statistical anomaly detection, executive HTML/PDF report generation, and SQLite trend analysis.

---

## ⏱️ Demo Timeline (5 Minutes)

| Time | Segment | Focus |
|---|---|---|
| **0:00 - 0:45** | Project Overview & Architecture | Problem statement, domain overview, tech stack |
| **0:45 - 1:45** | Multi-Source Connectors & Rule Engine | YAML declarative rules, CSV/JSON/Excel loading |
| **1:45 - 2:45** | Validation & Rich Terminal Output | Running `validate`, Rich progress bars, summary tables |
| **2:45 - 3:45** | Schema Drift & Anomaly Detection | SHA-256 fingerprint diffs, Z-score & IQR outliers |
| **3:45 - 4:30** | Executive HTML & PDF Reports | Chart.js interactive dashboard & ReportLab PDF |
| **4:30 - 5:00** | Quality Verification & Conclusion | Mypy strict mode (0 errors), Pytest (79% coverage) |

---

## 🎬 Step-by-Step Demo Commands

### Step 1: Show CLI Help & Available Rule Types
Explain the Typer CLI and registered rule validators:
```bash
datasentinel --help
datasentinel list-rules
```
*Talking points:*
- Typer CLI with full `--help` documentation and usage examples on every command.
- Open/Closed Principle connector architecture allowing new adapters without code modification.
- Pluggable quality rules: `null_check`, `unique_check`, `range`, `regex`, `foreign_key`.

---

### Step 2: Inspect YAML Rule Configuration
Show how rules and thresholds are defined declaratively without hardcoded Python values:
```bash
datasentinel list-rules samples/configs/ecommerce_orders_rules.yaml
```
*Talking points:*
- All thresholds (null tolerances, duplicate constraints, min/max bounds, regex patterns, allowed values) are defined in YAML.
- Sensitive credentials read from environment variables (`${DATABASE_URL}`, `${SLACK_WEBHOOK_URL}`).

---

### Step 3: Run Validation Pipeline on E-Commerce Dataset
Execute quality validation, anomaly detection, baseline tracking, and report generation:
```bash
datasentinel validate samples/configs/ecommerce_orders_rules.yaml \
  --report-dir samples/generated_reports \
  --save-baseline \
  --no-alerts
```
*Talking points:*
- Rich styled terminal output with live progress bars.
- Real quality violations caught: 1 null order ID, 2 duplicate IDs, 2 corrupted email regex patterns, negative order amount, and invalid status enum.
- Statistical anomaly detection: Flagged extreme outliers ($98,500 and $145,000) using Z-score (|z| > 3) and IQR (1.5x fence) with confidence scores.

---

### Step 4: Schema Baseline Registration & Drift Diffing
Demonstrate schema fingerprinting and drift detection:
```bash
# Compare current dataset against registered baseline
datasentinel compare-schemas samples/configs/ecommerce_orders_rules.yaml
```
*Talking points:*
- SHA-256 fingerprint of column names, data types, nullability, and ordinal positions.
- Diffs detect column additions, removals, type changes, or nullability changes between pipeline runs.

---

### Step 5: Query Validation History & Trends
Show SQLite-backed historical tracking:
```bash
datasentinel history --limit 5
```
*Talking points:*
- SQLite persistence tracks pass rates, durations, rule counts, and anomaly frequency across pipeline runs for historical trend analysis.

---

### Step 6: Review Executive HTML and PDF Reports
Open the generated artifacts:
- HTML Dashboard: `samples/generated_reports/sample_report.html`
  - Embedded Chart.js donut chart (rule breakdown)
  - Historical trend line chart
  - Detailed violation evidence drawer
- PDF Report: `samples/generated_reports/sample_report.pdf`
  - High-resolution ReportLab document suitable for stakeholders and executives.

---

### Step 7: Testing & Type Safety Verification
Verify code quality and testing rigor:
```bash
# 1. Strict Mypy Typecheck (zero errors)
mypy datasentinel

# 2. Pytest Suite with Coverage (>75% line coverage)
pytest --cov=datasentinel --cov-report=term-missing
```
*Results:*
- **Mypy**: Success: no issues found in 39 source files (`mypy --strict`).
- **Pytest**: 41 passed in ~8 seconds, **79% line coverage**, including Hypothesis property-based tests.
