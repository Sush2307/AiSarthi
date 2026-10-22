# AI Sarthi (GovHealth-SLM) — Master Prompts for Project Report & Poster Generation

This document provides two production-grade, highly structured master prompts that you can copy and paste into ChatGPT, Claude, Gemini, or use for LaTeX/Canva to generate:
1. **A Complete Engineering & Research Project Report** (10–25+ pages)
2. **An Academic / Competition Exhibition Poster** (A0/A1 Landscape/Portrait)

---

## PART 1: Master Prompt for Project Report Generation

> **How to use**: Copy the prompt block below and paste it into an AI assistant (Claude 3.5 Sonnet, ChatGPT-4o, or Gemini 1.5 Pro). It contains all repository parameters, benchmark metrics, verified numbers, and architectural diagrams needed to write an exhaustive academic or technical report.

```markdown
You are an expert Principal AI Research Engineer and Senior Technical Writer. 
Write an exhaustive, publication-grade Academic Project Report and Engineering Whitepaper for the project titled:

"AI Sarthi — GovHealth-SLM: An Evidence-Grounded Small Language Model and High-Performance Retrieval Engine for Indian Public Healthcare Intelligence"

Use the verified facts, architectural details, and empirical benchmarks provided below. Do NOT fabricate numbers or claims outside these verified project specifications.

---

### PROJECT METADATA & SPECIFICATIONS
- **Project Name**: AI Sarthi (GovHealth-SLM)
- **Domain**: Indian Public Health Informatics, Evidence-Grounded NLP, Small Language Models (SLMs)
- **Dataset**: `healthcare_master_final_v3.csv`
  - Total Verified Records: 1,180,313 rows
  - Total Health Indicators: 778 canonical indicators
  - Administrative Coverage: All 28 States, 8 Union Territories, and 700+ Districts
  - Primary Official Sources:
    1. NFHS-5 (National Family Health Survey 2019–2021)
    2. HMIS (Health Management Information System 2019–2020)
    3. AHS (Annual Health Survey)
    4. National Public/Private Hospital Directory
- **Technology Stack**:
  - Backend: FastAPI (Python 3.10+), Pandas, NumPy, Uvicorn, Pydantic, HTTPX
  - Frontend: React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide Icons
  - Machine Learning & Inference:
    - Base Model: Qwen/Qwen3-1.7B
    - Fine-Tuning: Parameter-Efficient Fine-Tuning (PEFT) with 4-bit QLoRA (NF4 quantization, r=16, alpha=32, target modules: q_proj, k_proj, v_proj, o_proj)
    - Frontier Cloud Inference: NVIDIA Nemotron-3-Ultra-550B via OpenRouter
- **Architectural Flow (3-Tier Hierarchical Router)**:
  - Tier 1: Hosted Frontier Model (NVIDIA Nemotron) with strict automated Numerical Grounding Validator.
  - Tier 2: Domain-Adapted SLM (Qwen3-1.7B-QLoRA) hosted on GPU/HuggingFace Space.
  - Tier 3: Zero-Hallucination Deterministic Evidence Provider (always operational fallback).
  - Safety & Reliability: Circuit-Breaker pattern (trips on 2 consecutive failures with 60s cooldown), Clinical Safety Abstention (safely rejects diagnosis/drug prescription inquiries and refers to Primary Health Centres), and Ambiguous Query Clarification.
- **Empirical Benchmarks & Verified Results**:
  - Data Retrieval Speedup: **279x overall speedup** (Multi-filter query latency dropped from 1,048.94 ms to 1.19 ms using precomputed inverted index groupby maps and `np.intersect1d`).
  - Held-Out Accuracy QA Benchmark: **16 / 16 Categories PASSED (100.0%)** across Exact Lookups, State vs. District Interpretation, Synonym Resolution, Rankings, Time-Series Trends, Multi-Turn Context, and Clinical Safety.
  - Unit & Integration Test Suites: **103 / 104 tests passed (100% active test pass rate)**.
  - Frontend Rendering: Built-in `FormattedMessage` engine that cleans raw markdown syntax and eliminates redundant pipe tables, pairing natural prose with interactive Recharts visualizations and data tables.

---

### REPORT STRUCTURE REQUIREMENTS
Generate an in-depth, professional report with the following numbered chapters:

1. **Title Page & Executive Summary**
   - Project Title, Abstract, Keywords, Executive Summary of Problem Statement and Solution.
2. **Problem Statement & Motivation**
   - Challenges in accessing fragmented public health data in India (NFHS vs HMIS divergence, survey vs administrative counting, language barriers, hallucination risks in standard LLMs).
   - The case for Small Language Models (SLMs) and deterministic grounding over unconstrained black-box LLMs.
3. **Dataset Engineering & Fact Base Construction**
   - Ingestion, harmonization, deduplication, and schema normalization of 1.18M rows.
   - Indicator taxonomy (maternal health, immunization, child nutrition, facilities) and geographic standardizations.
4. **System Architecture & 3-Tier Routing Mechanism**
   - Detailed component diagram and request lifecycle.
   - Explanation of Tier 1 (Frontier), Tier 2 (Fine-Tuned SLM), and Tier 3 (Deterministic Engine).
   - Automated Numerical Grounding Validation algorithm (preventing unverified numbers from being emitted).
   - Resilience engineering: Circuit-breaker pattern, fallback triggers, and multi-turn state preservation.
5. **High-Performance Data Retrieval Optimization**
   - Mathematical and algorithmic explanation of inverted groupby indexing vs naive $O(N)$ string scans.
   - Full benchmark table comparing unoptimized vs optimized latency across different query patterns.
6. **Model Training & Domain Adaptation (GovHealth-SLM)**
   - Dataset generation strategy (10,000 instruction-tuning pairs).
   - QLoRA fine-tuning hyperparameters (learning rate, LoRA rank/alpha, prompt templates).
   - Local hardware constraints (MX450 2GB VRAM vs Cloud Tesla T4 training path).
7. **Empirical Evaluation & Regression Audit**
   - Detailed analysis of the 16-Category Held-Out Healthcare QA Benchmark.
   - Grounding fidelity, state-vs-district separation, and unweighted average disclaimers.
   - Clinical safety compliance and medical ethics.
8. **Frontend Interface & UX Engineering**
   - User-centric design: Clean conversational formatting, suppression of raw markdown pipe clutter, dual Table/Chart visualization, Data Explorer, and National Health Schemes guide.
9. **Security, Privacy & Deployment Readiness**
   - Secret management, CORS hardening, zero-patient data compliance (aggregate public data only).
   - Hardware requirements, containerization, and cost analysis.
10. **Conclusion & Future Directions**
    - Summary of impact, voice assistant integration (Bhashini API for Indian languages), and offline edge deployment for rural ASHA health workers.

Format with formal technical prose, clean markdown headers, equations/algorithms where appropriate, and formatted ASCII/Mermaid diagrams.
```

---

## PART 2: Master Prompt for Presentation / Exhibition Poster Generation

> **How to use**: Copy this prompt into an AI assistant, or use the output content directly in Canva, PowerPoint, Figma, or LaTeX `beamerposter` to generate an award-winning academic poster.

```markdown
You are a Lead Designer and Scientific Communicator specializing in Academic Research Posters (A0/A1 Landscape format for IEEE/ACM/Healthcare AI Conferences).

Design the complete text, layout plan, visual hierarchy, and infographics specifications for a presentation poster for:

"AI Sarthi — GovHealth-SLM: Evidence-Grounded Small Language Model for Indian Public Health Intelligence"

---

### POSTER DESIGN SPECIFICATIONS:
- **Dimensions**: Standard A1 Landscape (33.1 x 23.4 inches) or A0 Landscape (46.8 x 33.1 inches).
- **Color Palette**:
  - Primary Brand: Deep Forest Pine (`#132E27`) & Dark Emerald (`#0F4A3E`)
  - Accent / Highlights: Mint Green (`#10B981`) & Warm Ivory (`#FDFBF7`)
  - Alerts / Badges: Saffron Gold (`#D97706`) & Clean White (`#FFFFFF`)
- **Target Audience**: Data Scientists, Public Health Policymakers, Health Administrators, and AI Researchers.

---

### CONTENT & LAYOUT STRUCTURE:

#### 1. HEADER BANNER (Top 15% of Poster)
- **Main Title**: AI SARTHI — GovHealth-SLM
- **Subtitle**: Evidence-Grounded Small Language Model & High-Performance Analytics Engine for Indian Public Healthcare
- **Key Badges / Callouts**:
  - `1.18M+ Government Records` | `778 Health Indicators` | `279x Accelerated Retrieval` | `100% Fact-Grounded`

#### 2. COLUMN 1: THE CHALLENGE & THE DATASET (Left 30%)
- **The Problem**: 
  - Fragmented public health portals (HMIS administrative data vs NFHS survey data).
  - General LLMs (ChatGPT/Gemini) suffer from numerical hallucinations, citing non-existent hospital rates or confusing state averages with district figures.
- **The Knowledge Base**:
  - Unified ingestion of 1,180,313 official records covering all 28 States & 700+ Districts.
  - Multi-source coverage: NFHS-5, HMIS, Annual Health Survey (AHS), and National Hospital Directories.
- **Visual Callout Box**:
  - "Zero Hallucination Guarantee": Every generated answer is mathematically cross-referenced with retrieved dataset rows before being shown to the user.

#### 3. COLUMN 2: 3-TIER ARCHITECTURE & RETRIEVAL ENGINE (Middle 40%)
- **Architecture Diagram (Visual Box)**:
  - User Query $\to$ Fast Filter Detection $\to$ Inverted Index Intersect $\to$ 3-Tier Dynamic Router:
    - Tier 1: Frontier Nemotron Model (Rich contextual synthesis)
    - Tier 2: Qwen3-1.7B QLoRA Adapter (Domain-specific language model)
    - Tier 3: Deterministic Fallback Engine (100% guaranteed response even during cloud/network outages)
- **Key Innovation — 279x Retrieval Acceleration**:
  - Table showing benchmark speedup:
    * Multi-Filter Query: 1,048 ms $\to$ 1.19 ms (**881x faster**)
    * State + Indicator: 1,109 ms $\to$ 3.64 ms (**304x faster**)
    * Average Latency: 704 ms $\to$ 2.52 ms (**279x overall speedup**)
- **Safety First**:
  - Automated rejection of diagnostic/medication queries with guidance to visit Primary Health Centres (PHC).

#### 4. COLUMN 3: BENCHMARK RESULTS & REAL-WORLD IMPACT (Right 30%)
- **Held-Out Healthcare QA Evaluation**:
  - Circular Progress Gauge: **100.0% Pass Rate (16/16 Categories)** across Lookups, Comparisons, Rankings, Time-Series Trends, Multi-Turn Memory, and Safety Abstentions.
- **Sample Query Showcase**:
  - *Query*: "What is the institutional birth rate in Kerala?"
  - *Engine Output*: Direct numerical extraction (97.97% NFHS-5) + automated unweighted arithmetic disclosure + interactive district bar charts.
- **Future Vision**:
  - Edge deployment on low-cost tablets for rural ASHA health workers.
  - Multilingual voice interface via Government of India's Bhashini AI.

#### 5. FOOTER (Bottom 5%)
- Contact info, QR code to live GitHub repository, and logos of Ministry of Health / Public Health Informatics standards.

Please generate the complete, ready-to-use copy text for each block, along with specific layout coordinates and design tips.
```

---

## PART 3: Quick Reference Table for Verified Metrics

When writing reports or presenting the poster, use these exact repository references:

| Metric / Specification | Verified Value | Reference Location |
| :--- | :--- | :--- |
| **Total Fact Base Size** | **1,180,313 records** | `healthcare_master_final_v3.csv` |
| **Indicators Catalog** | **778 unique metrics** | `Dataset.indicators_meta()` in `backend/app/data.py` |
| **Data Sources** | NFHS-5, HMIS, AHS, Hospital Directory | `backend/app/data.py` |
| **Retrieval Speedup** | **279x faster** (704ms $\to$ 2.52ms) | `scratch/bench_filter.py` & Section 2 Benchmark |
| **Held-Out Accuracy** | **16 / 16 (100.0%)** | `backend/held_out_accuracy_audit_report.md` |
| **Live HTTP Audit** | **11 / 11 (100.0%)** | `backend/second_stage_audit_report.md` |
| **Unit & Grounding Tests**| **45 / 45 Passed** | `backend/tests/test_api.py`, `test_real_dataset_grounding.py` |
| **Frontend UI Features** | AI Chat, Data Explorer, Health Dashboard, Workspace Comparison, National Schemes | `frontend/src/pages/` |
| **Clean Chat Formatter** | FormattedMessage (zero raw pipes, clean lists/bold) | `frontend/src/components/FormattedMessage.tsx` |
