# AI Sarthi Healthcare Training Dataset Quality Report

## 1. Dataset Overview & Split Breakdown
- **Total Instruction Examples**: 6,949
- **Train Split**: 5,559 examples (80.0%)
- **Validation Split**: 694 examples (10.0%)
- **Held-Out Test Benchmark**: 696 examples (10.0%)
- **Source Master Dataset**: `C:\sbproject\ai-sarthi\healthcare_master_final_v3.csv` (1,180,313 records)

## 2. Task Category Distribution
| Task ID | Task Category Name | Total Count | Train (80%) | Val (10%) | Test (10%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Task 01 | **Comparison** | 500 | 400 | 50 | 50 |
| Task 02 | **Conversational Follow Up** | 500 | 400 | 50 | 50 |
| Task 03 | **Exact Indicator Lookup** | 500 | 400 | 50 | 50 |
| Task 04 | **Indicator Aliases** | 500 | 400 | 50 | 50 |
| Task 05 | **Indicator Discovery** | 500 | 400 | 50 | 50 |
| Task 06 | **Missing Data Abstention** | 449 | 359 | 44 | 46 |
| Task 07 | **Multi Part Questions** | 500 | 400 | 50 | 50 |
| Task 08 | **Plain Language Summary** | 500 | 400 | 50 | 50 |
| Task 09 | **Rankings And Aggregations** | 500 | 400 | 50 | 50 |
| Task 10 | **Source And Period Explanation** | 500 | 400 | 50 | 50 |
| Task 11 | **State Vs District** | 500 | 400 | 50 | 50 |
| Task 12 | **Structured Query Plan** | 500 | 400 | 50 | 50 |
| Task 13 | **Time Series Trend** | 500 | 400 | 50 | 50 |
| Task 14 | **Unanswerable Abstention** | 500 | 400 | 50 | 50 |

## 3. Data Quality & Leakage Audit
| Audit Dimension | Result | Status |
| :--- | :--- | :--- |
| **Schema & Role Validity** | 0 invalid examples | **PASSED** (100% compliant) |
| **Duplicate Queries in Splits** | 0 duplicates | **PASSED** |
| **Train-to-Test Query Leakage** | 0 overlapping queries | **PASSED (Zero Leakage)** |
| **Train-to-Val Query Leakage** | 0 overlapping queries | **PASSED (Zero Leakage)** |
| **Numerical Grounding Traceability** | 4500/4500 (100.0%) | **PASSED (100% Grounded)** |
| **Null Value Integrity** | 0 nulls converted to zero | **PASSED (No false zeros)** |
| **Medical Disclaimer & Safety** | 0 unsupported causal claims | **PASSED (Informational only)** |

## 4. Verification Methodology
1. **Deterministic Calculations**: Comparison deltas, multi-district ranking spreads, and trend directions were verified with Python/Pandas arithmetic.
2. **Evidence Grounding**: Assistant targets extract only from verified rows in `healthcare_master_final_v3 (1).csv`.
3. **Geographic Scoping**: State-level indicator discovery queries explicitly prioritize state records (`geographic_level == 'state'`), preventing misattribution to random districts.
4. **Unit Safety**: Comparisons and rankings enforce matching units (percentages compared strictly to percentages, counts to counts).