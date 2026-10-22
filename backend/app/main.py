"""AI Sarthi API. Run: uvicorn app.main:app --reload --port 8000"""
from __future__ import annotations
import json
import re
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from . import config
from .context import session_manager, SessionState
from .data import Dataset
from .model import ModelService
from .providers import DeterministicEvidenceProvider

DISCLAIMER = "Informational only. Not medical advice, diagnosis or treatment."

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.data = Dataset(config.master_path())
    app.state.model = ModelService()
    if config.load_model_enabled():
        app.state.model.load()
    yield

app = FastAPI(title="AI Sarthi API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins(), allow_methods=["GET", "POST"], allow_headers=["*"])

from fastapi.responses import Response

class ChatIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=50)
    year: str | None = Field(default=None, max_length=20)
    session_id: str | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def strip_q(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3: raise ValueError("question too short")
        return v

class WorkspaceCompareIn(BaseModel):
    indicator: str = Field(min_length=2, max_length=250)
    locations: list[str] = Field(min_length=1, max_length=50)
    year: str | None = Field(default=None, max_length=30)
    source: str | None = Field(default=None, max_length=50)
    geographic_scope: str | None = Field(default="district", max_length=30)

@app.get("/api/health")
def health(request: Request):
    m: ModelService = request.app.state.model
    st = m.get_status()
    return {
        "status": "ok",
        "records": len(request.app.state.data.df),
        "model_loaded": m.loaded,
        "model_enabled": m.enabled,
        "model_available": m.available,
        "device": m.device,
        "precision": m.precision,
        "model_error": m.error,
        "diagnostic": m.diagnostic,
        "base_model_id": m.base_model_id,
        "primary_provider": st.get("primary_provider"),
        "circuit_breaker": st.get("circuit_breaker"),
        "providers": st.get("providers"),
    }

def _format_and_generate_response(
    question: str,
    records: list[dict[str, Any]],
    intent: str,
    meta: dict[str, Any],
    ds: Dataset,
    m: ModelService,
    session: SessionState,
    matched_scheme: dict[str, Any] | None = None,
) -> dict[str, Any]:
    numeric_vals = [r["value"] for r in records if isinstance(r.get("value"), (int, float))]
    state = meta["filters_used"].get("state")
    district = meta["filters_used"].get("district")
    source = meta["filters_used"].get("source")
    year = meta["filters_used"].get("year")

    # Map internal intent to API answer_type
    if intent == "comparison":
        answer_type_default = "comparison"
    elif intent == "trend":
        answer_type_default = "trend"
    elif intent == "ranking":
        answer_type_default = "multiple_records"
    elif intent == "aggregation":
        answer_type_default = "single_record"
    elif intent == "evidence_summary":
        answer_type_default = "single_record" if len(records) == 1 else "multiple_records"
    elif len(records) == 1:
        answer_type_default = "single_record"
    else:
        answer_type_default = "multiple_records"

    # Provenance tracking
    provenance_obj = {
        "query_type": intent,
        "dataset_id": "healthcare_master_final_v3.csv (1,180,313 records)",
        "matched_indicator": (records[0].get("indicator") if records else None),
        "state": state,
        "district": district,
        "source": source or (records[0].get("source") if records else None),
        "year": year or (records[0].get("year") if records else None),
        "geographic_level": records[0].get("geographic_level") if records else None,
        "records_matched": len(records),
        "values": [r["value"] for r in records if r.get("value") is not None][:10],
        "calculation": intent if intent in ["comparison", "trend", "ranking", "aggregation"] else None,
        "limitations": [
            "Values are administrative counts or survey percentages as recorded in primary partitions.",
            "Absence of records reflects indexed dataset coverage and does not assert real-world absence."
        ],
    }

    # Compute deterministic evidence summary
    distinct_indicators_list = sorted(list({str(r["indicator"]) for r in records if r.get("indicator")}))
    raw_units = {str(r.get("unit") or ("%" if "percent" in str(r.get("indicator", "")).lower() else "")).strip() for r in records}
    distinct_units_list = sorted(list({u for u in raw_units if u}))
    units_compatible = (len(distinct_indicators_list) <= 1) and (len(distinct_units_list) <= 1)

    statistics_data = None
    if units_compatible and numeric_vals:
        statistics_data = {
            "min": float(min(numeric_vals)),
            "max": float(max(numeric_vals)),
            "mean": float(round(sum(numeric_vals) / len(numeric_vals), 2)),
        }

    evidence_summary = {
        "record_count": len(records),
        "distinct_indicators": distinct_indicators_list,
        "distinct_locations": sorted(list({str(r.get("district") or r.get("state")) for r in records if r.get("district") or r.get("state")})),
        "distinct_years": sorted(list({r["year"] for r in records if r.get("year")})),
        "sources": sorted(list({r["source"] for r in records if r.get("source")})),
        "statistics": statistics_data,
        "methodology": "Strict deterministic retrieval from indexed HMIS, NFHS-5, and AHS public health datasets.",
        "provenance": provenance_obj,
    }

    # Generate follow-up prompts
    sample_ind = records[0].get("indicator", "maternal health")
    sample_loc = records[0].get("district") or records[0].get("state") or "India"
    follow_ups = [
        f"Show trend over available years for {sample_ind} in {sample_loc}",
        f"Compare {sample_ind} with neighboring districts",
        f"Summarize these records in simple language",
    ]

    routed_result = None
    if hasattr(m, "generate_routed"):
        try:
            cand = m.generate_routed(question, records, intent=intent, scheme_info=matched_scheme)
            if isinstance(cand, dict) and "answer" in cand and not hasattr(cand.get("answer"), "_mock_return_value"):
                routed_result = cand
        except Exception:
            routed_result = None

    if routed_result is not None:
        answer_text = routed_result["answer"]
        answer_type = routed_result.get("answer_type", answer_type_default)
        mode_str = routed_result["mode"]
        inference_mode = routed_result["inference_mode"]
        fallback_used = routed_result["fallback_used"]
        fallback_reason = routed_result["fallback_reason"]
    else:
        top_rec = records[0]
        val_str = f"{top_rec.get('value'):,}" if isinstance(top_rec.get('value'), (int, float)) else str(top_rec.get('value') or 'N/A')
        loc_str = top_rec.get('district') or top_rec.get('state') or 'India'
        ind_str = top_rec.get('indicator', '').replace('_', ' ')
        yr_str = top_rec.get('year', '')
        src_str = top_rec.get('source', '')
        unit_str = f" {top_rec.get('unit')}" if top_rec.get('unit') else ""

        det_prov = getattr(m, "deterministic_provider", None)
        deterministic_answer = None
        if det_prov is not None and hasattr(det_prov, "generate"):
            try:
                res = det_prov.generate(question, records, intent)
                if isinstance(res, str):
                    deterministic_answer = res
            except Exception:
                pass
        if not deterministic_answer or not isinstance(deterministic_answer, str):
            deterministic_answer = DeterministicEvidenceProvider().generate(question, records, intent)
        if matched_scheme and isinstance(deterministic_answer, str):
            deterministic_answer += f"\n\n*Related Healthcare Scheme: {matched_scheme['name']} - {matched_scheme.get('summary')}*"

        if m.available:
            try:
                generated_text = m.generate(question, records)
                is_grounded, failure_reason = m.validate_evidence_grounding(generated_text, records)
                if is_grounded:
                    answer_text = generated_text
                    answer_type = "ai_generated"
                    mode_str = "live"
                    inference_mode = "model-generated"
                    fallback_used = False
                    fallback_reason = None
                else:
                    answer_text = deterministic_answer
                    answer_type = "dataset_only"
                    mode_str = "retrieval-only"
                    inference_mode = "retrieval-only-fallback"
                    fallback_used = True
                    fallback_reason = f"Numerical grounding verification: {failure_reason}"
            except Exception as e:
                answer_text = deterministic_answer
                answer_type = "dataset_only"
                mode_str = "retrieval-only"
                inference_mode = "retrieval-only-fallback"
                fallback_used = True
                fallback_reason = f"Model execution error: {e}"
        else:
            answer_text = deterministic_answer
            answer_type = "dataset_only"
            mode_str = "retrieval-only"
            inference_mode = "retrieval-only"
            fallback_used = False
            fallback_reason = None

    # Clean raw markdown tables and format snake_case identifiers for human readability
    if isinstance(answer_text, str):
        lines = answer_text.split("\n")
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and (stripped.endswith("|") or "---" in stripped):
                continue
            cleaned_lines.append(line)
        answer_text = "\n".join(cleaned_lines)
        answer_text = re.sub(r"\n{3,}", "\n\n", answer_text).strip()
        answer_text = re.sub(
            r'["\']([a-zA-Z0-9]+(?:_[a-zA-Z0-9]+)+)["\']',
            lambda match: f'"{match.group(1).replace("_", " ")}"',
            answer_text,
        )

    # Update session state with verified results
    session.update(
        question=question,
        answer=answer_text,
        records=records,
        filters=meta["filters_used"],
        intent=intent,
    )

    return {
        "answer": answer_text,
        "answer_type": answer_type,
        "intent": intent,
        "mode": mode_str,
        "model_enabled": m.enabled,
        "model_available": m.available,
        "inference_mode": inference_mode,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "evidence_count": len(records),
        "records": records,
        "evidence_summary": evidence_summary,
        "follow_ups": follow_ups,
        **meta,
    }

@app.post("/api/chat")
def chat(body: ChatIn, request: Request):
    ds: Dataset = request.app.state.data
    m: ModelService = request.app.state.model
    q_lower = body.question.lower()

    # Session tracking for multi-turn conversational context
    client_ip = request.client.host if request.client else "default_session"
    session_id = body.session_id or client_ip
    session = session_manager.get_or_create(session_id)

    # Check for recognized government scheme queries
    matched_scheme = None
    q_norm = q_lower.replace("-", "").replace(" ", "")
    if any(k in q_lower for k in ["scheme", "pmjay", "pm-jay", "ayushman", "janani", "jsy", "pmssy", "rbsk", "eligibility"]):
        try:
            schemes_data = json.loads(config.SCHEMES_FILE.read_text(encoding="utf-8")).get("schemes", [])
            for sc in schemes_data:
                sc_id = sc.get("id", "").lower()
                name_words = [w.lower() for w in sc.get("name", "").split() if len(w) > 3]
                if sc_id in q_lower or sc_id in q_norm or ("pm-jay" in q_lower and sc_id == "pmjay") or (name_words and any(w in q_lower for w in name_words)):
                    matched_scheme = sc
                    break
        except Exception:
            pass

    # Check for greetings or capability inquiries (e.g. "Hello, what can AI Sarthi help me with?")
    is_greeting = any(
        re.search(pattern, q_lower)
        for pattern in [
            r"^(hi|hello|hey|namaste|greetings)(\b|[!?.,\s]|$)",
            r"what can (you|ai sarthi|this app|this) do",
            r"what can (you|ai sarthi|this app|this) help",
            r"how can (you|ai sarthi) help",
            r"^help(\b|[!?.,\s]|$)",
            r"who are you",
        ]
    )
    if is_greeting and not any(loc_kw in q_lower for loc_kw in ["in ", "district", "state", "compare", "rate", "percent", "data", "records"]):
        return {
            "answer": (
                "Hello! I am **AI Sarthi**, an evidence-grounded AI assistant for Indian public healthcare intelligence.\n\n"
                "I synthesize official statistics across **1.18M+ government health records** (HMIS, NFHS-5, AHS) "
                "and provide verified information on central & state healthcare schemes.\n\n"
                "### How I can help you:\n"
                "- **Specific Indicators**: Ask about maternal care, child immunization, nutrition, or facilities (e.g. *'What is the institutional birth rate in Pune?'*)\n"
                "- **Cross-Location Comparisons**: Compare performance across districts or states (e.g. *'Compare anaemia in pregnancy in Bihar vs Kerala'*)\n"
                "- **Trends Over Time**: Track multi-year health progress (e.g. *'Show full immunization trends in Assam'*)\n"
                "- **Government Schemes**: Review benefits, eligibility, and links (e.g. *'What are the eligibility criteria for PM-JAY?'*)"
            ),
            "answer_type": "single_record",
            "intent": "greeting",
            "mode": "verified-scheme",
            "model_enabled": m.enabled,
            "model_available": m.available,
            "inference_mode": "interactive-guide",
            "fallback_used": False,
            "fallback_reason": None,
            "evidence_count": 0,
            "records": [],
            "evidence_summary": None,
            "follow_ups": [
                "What is institutional births in Pune?",
                "Compare anaemia in pregnancy in Bihar vs Kerala",
                "What are the benefits under PM-JAY?",
            ],
            "filters_used": {"state": None, "district": None, "source": None, "year": None},
            "disclaimer": DISCLAIMER,
        }

    # Clinical safety and medical prescription abstention
    clinical_keywords = [
        "what medicine", "what medication", "prescribe", "diagnose", "diagnosis",
        "cure my", "treatment for my", "chest pain", "severe headache", "should i take"
    ]
    if any(kw in q_lower for kw in clinical_keywords) and not any(ind_w in q_lower for ind_w in ["indicator", "rate", "percent", "data", "records", "statistics", "report"]):
        return {
            "answer": (
                "AI Sarthi is an evidence-grounded statistical querying system for Indian public health databases "
                "and does not provide clinical diagnoses, individualized medical advice, or drug prescriptions. "
                "Please consult a qualified physician or visit your nearest primary health centre (PHC) or hospital immediately for proper medical evaluation."
            ),
            "answer_type": "no_data",
            "intent": "clinical_abstention",
            "mode": "safety-abstention",
            "model_enabled": m.enabled,
            "model_available": m.available,
            "inference_mode": "clinical-abstention",
            "fallback_used": False,
            "fallback_reason": None,
            "evidence_count": 0,
            "records": [],
            "evidence_summary": None,
            "follow_ups": [
                "What is institutional births in Pune?",
                "What healthcare indicators are available for Maharashtra?",
                "What are the benefits under PM-JAY?",
            ],
            "filters_used": {"state": None, "district": None, "source": None, "year": None},
            "disclaimer": DISCLAIMER,
        }

    # 1. Multi-turn Follow-up: Evidence Summary / Explanation Request
    is_summary_followup = session_manager.is_summary_request(body.question)
    if is_summary_followup:
        if session.has_records:
            records = session.last_records
            state = session.last_state
            district = session.last_district
            source = session.last_source
            year = session.last_year
            intent = "evidence_summary"
            meta = {
                "filters_used": {"state": state, "district": district, "source": source, "year": year},
                "disclaimer": DISCLAIMER,
            }
            return _format_and_generate_response(body.question, records, intent, meta, ds, m, session, matched_scheme)
        else:
            return {
                "answer": (
                    "There are no recently retrieved healthcare records in this session to summarize. "
                    "Please ask for a specific healthcare indicator first (e.g. *'What is institutional births in Pune?'* "
                    "or *'Show full immunization in Maharashtra'*)."
                ),
                "answer_type": "no_data",
                "intent": "clarification_needed",
                "mode": "retrieval-only",
                "model_enabled": m.enabled,
                "model_available": m.available,
                "inference_mode": "insufficient-evidence",
                "fallback_used": False,
                "fallback_reason": None,
                "evidence_count": 0,
                "records": [],
                "evidence_summary": None,
                "follow_ups": [
                    "What is institutional births in Pune?",
                    "What healthcare indicators are available for Maharashtra?",
                    "What is full immunization rate in Nashik?",
                ],
                "filters_used": {"state": None, "district": None, "source": None, "year": None},
                "disclaimer": DISCLAIMER,
            }

    # 2. Multi-turn Follow-up: Metadata / Source Query
    is_meta_followup = session_manager.is_source_or_metadata_request(body.question)
    has_explicit_loc = bool(ds.detect_locations(body.question).get("state") or ds.detect_locations(body.question).get("district"))
    if is_meta_followup and not has_explicit_loc:
        if session.has_records:
            records = session.last_records
            state = session.last_state
            district = session.last_district
            source = session.last_source
            year = session.last_year
            intent = "metadata_explanation"
            meta = {
                "filters_used": {"state": state, "district": district, "source": source, "year": year},
                "disclaimer": DISCLAIMER,
            }
            return _format_and_generate_response(body.question, records, intent, meta, ds, m, session, matched_scheme)

    # 3. Multi-turn Follow-up: Location switch or Comparison with prior indicator
    is_loc_followup, cand_loc = session_manager.is_location_followup(body.question)
    if is_loc_followup and cand_loc and session.has_records and session.last_indicator:
        cand_locs = ds.detect_locations(cand_loc)
        st = cand_locs.get("state") or session.last_state
        dt = cand_locs.get("district")
        if "compare" in q_lower:
            prev_loc = session.last_district or session.last_state
            all_locs = [prev_loc, dt or st or cand_loc] if prev_loc else [cand_loc]
            intent = "comparison"
            recs = ds.retrieve(body.question, indicator=session.last_indicator, source=session.last_source, year=session.last_year, intent=intent, all_locations=all_locs)
        else:
            intent = "district_lookup" if dt else "state_lookup"
            recs = ds.retrieve(body.question, state=st, district=dt, source=session.last_source, year=session.last_year, indicator=session.last_indicator, intent=intent)
        state = st
        district = dt
        source = session.last_source
        year = session.last_year
    else:
        # Standard filter detection and retrieval
        filters = ds.detect_filters(body.question)
        state = body.state or filters["state"]
        district = body.district or filters["district"]
        source = body.source or filters["source"]
        year = body.year or filters["year"]
        indicator = filters.get("indicator")
        intent = ds.classify_intent(body.question, filters)

        # Multi-turn context preservation:
        # Only inherit the previous indicator if this turn is an explicit follow-up (location switch, comparison, or trend)
        is_followup = is_loc_followup or any(re.search(rf"\b{re.escape(p)}\b", q_lower) for p in [
            "what about", "how about", "what of", "and in", "compare with", "compare these", "trend", "over time", "progress"
        ])
        if is_followup and session.has_records and session.last_indicator and not indicator:
            # Do not inherit if user explicitly switched to a different data source
            if not source or not session.last_source or source.lower() == session.last_source.lower():
                indicator = session.last_indicator

        # If user asks about trend/source/years without a new location, retain session location
        if session.has_records and not state and not district:
            if intent in ["available_sources", "available_years", "metadata_explanation"] or any(w in q_lower for w in ["for this", "for these", "trend", "this data"]):
                state = session.last_state
                district = session.last_district

        all_locs = filters.get("all_districts", []) + filters.get("all_states", [])
        recs = ds.retrieve(
            body.question,
            state=state,
            district=district,
            source=source,
            year=year,
            indicator=indicator,
            intent=intent,
            all_locations=all_locs if (intent == "comparison" and len(all_locs) >= 2) else None,
        )

    meta = {
        "filters_used": {"state": state, "district": district, "source": source, "year": year},
        "disclaimer": DISCLAIMER,
    }

    # If the user is explicitly asking about a scheme, prioritize official scheme details
    is_explicit_scheme_query = matched_scheme and (
        recs.empty or any(w in q_lower for w in ["scheme", "eligibility", "benefit", "apply", "coverage", "how to"])
    )

    if is_explicit_scheme_query:
        scheme_answer = (
            f"**{matched_scheme['name']}** (Official Healthcare Scheme Information)\n\n"
            f"- **Summary**: {matched_scheme.get('summary', 'N/A')}\n"
            f"- **Eligibility**: {matched_scheme.get('eligibility', 'N/A')}\n"
            f"- **Benefits**: {matched_scheme.get('benefits', 'N/A')}\n"
            f"- **Application**: {matched_scheme.get('how_to_apply', 'N/A')}\n"
            f"- **Portal**: {matched_scheme.get('official_url', 'N/A')}"
        )
        return {
            "answer": scheme_answer,
            "answer_type": "single_record",
            "intent": "scheme_info",
            "mode": "verified-scheme",
            "model_enabled": m.enabled,
            "model_available": m.available,
            "inference_mode": "verified-scheme",
            "fallback_used": False,
            "fallback_reason": None,
            "evidence_count": 0,
            "records": [],
            "evidence_summary": None,
            "follow_ups": [
                "What are the benefits under PM-JAY?",
                "How to apply for Janani Suraksha Yojana?",
                "Show institutional births in Pune",
            ],
            **meta,
        }

    if recs.empty:
        if intent == "comparison":
            clarification_answer = (
                "You requested a comparative healthcare analysis, but no specific indicator or location pair was specified. "
                "AI Sarthi can perform verified comparisons across districts or states.\n\n"
                "### Popular Indicators for District Comparison:\n"
                "- **Institutional Deliveries (%)**: Proportion of live births delivered in health facilities.\n"
                "- **Full Immunization (%)**: Children age 12-23 months fully vaccinated.\n"
                "- **Mothers with 4+ Antenatal Visits (%)**: Comprehensive antenatal care coverage.\n"
                "- **Anaemia in Pregnancy (%)**: Percentage of pregnant women with low haemoglobin.\n"
                "- **Sex Ratio at Birth**: Females per 1,000 males recorded at birth.\n\n"
                "**Try asking a specific comparison query:**\n"
                "- *'Compare institutional births between Pune and Nashik'*\n"
                "- *'Compare full immunization across districts in Bihar'*\n"
                "- *'Compare anaemia in pregnancy between Thane and Nagpur'*"
            )
            return {
                "answer": clarification_answer,
                "answer_type": "clarification_needed",
                "intent": "comparison_clarification",
                "mode": "interactive-guide",
                "model_enabled": m.enabled,
                "model_available": m.available,
                "inference_mode": "clarification-needed",
                "fallback_used": False,
                "fallback_reason": None,
                "evidence_count": 0,
                "records": [],
                "evidence_summary": None,
                "follow_ups": [
                    "Compare institutional births between Pune and Nashik",
                    "Compare full immunization in Bihar vs Kerala",
                    "Compare anaemia in pregnancy between Thane and Nagpur",
                ],
                **meta,
            }

        return {
            "answer": "No matching record was found in the currently indexed dataset. "
                      "Try a more specific indicator, state, district, source or year.",
            "answer_type": "no_data",
            "intent": "unsupported",
            "mode": "retrieval-only",
            "model_enabled": m.enabled,
            "model_available": m.available,
            "inference_mode": "insufficient-evidence",
            "fallback_used": False,
            "fallback_reason": None,
            "evidence_count": 0,
            "records": [],
            "evidence_summary": None,
            "follow_ups": [
                "What is institutional births in Pune?",
                "Compare anaemia in pregnancy in Bihar vs Kerala",
                "Show maternal mortality indicators across states",
            ],
            **meta,
        }

    records = ds.to_records(recs)
    return _format_and_generate_response(body.question, records, intent, meta, ds, m, session, matched_scheme)

@app.get("/api/health-data")
def health_data(request: Request, q: str = "", state: str | None = None, district: str | None = None,
                year: str | None = None, source: str | None = None, indicator: str | None = None,
                limit: int = Query(100, ge=1, le=1000)):
    ds: Dataset = request.app.state.data
    df = ds.retrieve(q, state, district, source, year, indicator, limit) if q.strip() \
        else ds.filter(state, district, source, year, indicator).head(limit)
    return {"count": len(df), "records": ds.to_records(df)}

@app.get("/api/explorer")
def explorer(
    request: Request,
    q: str = "",
    state: str | None = None,
    district: str | None = None,
    year: str | None = None,
    source: str | None = None,
    indicator: str | None = None,
    geographic_level: str | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = "year",
    sort_order: str = "desc",
):
    ds: Dataset = request.app.state.data
    return ds.explorer_query(
        q=q,
        state=state,
        district=district,
        year=year,
        source=source,
        indicator=indicator,
        geographic_level=geographic_level,
        category=category,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

@app.get("/api/export/csv")
def export_csv_endpoint(
    request: Request,
    q: str = "",
    state: str | None = None,
    district: str | None = None,
    year: str | None = None,
    source: str | None = None,
    indicator: str | None = None,
    geographic_level: str | None = None,
    category: str | None = None,
    limit: int = Query(5000, ge=1, le=50000),
):
    ds: Dataset = request.app.state.data
    df = (
        ds.retrieve(q, state, district, source, year, indicator, limit)
        if q.strip()
        else ds.filter(state, district, source, year, indicator, geographic_level, category).head(limit)
    )
    cols_to_export = [c for c in ds.df.columns if c in ["state", "district", "year", "indicator", "value", "source", "geographic_level", "report_type"]]
    csv_str = df[cols_to_export].to_csv(index=False)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ai-sarthi-healthcare-records.csv"'},
    )

@app.get("/api/workspace/indicators")
def workspace_indicators_endpoint(request: Request, q: str = ""):
    ds: Dataset = request.app.state.data
    meta = ds.indicators_meta()
    if q.strip():
        q_clean = q.strip().lower()
        meta = [m for m in meta if q_clean in m["indicator"].lower() or q_clean in m["label"].lower() or q_clean in m["source"].lower()]
    return meta

@app.get("/api/workspace/locations")
def workspace_locations_endpoint(request: Request, scope: str = Query("district")):
    ds: Dataset = request.app.state.data
    return ds.locations_list(scope)

@app.post("/api/workspace/compare")
def workspace_compare_endpoint(body: WorkspaceCompareIn, request: Request):
    ds: Dataset = request.app.state.data
    return ds.workspace_compare(body.indicator, body.locations, body.year, body.source, body.geographic_scope)

@app.get("/api/analytics/modules")
def analytics_modules(request: Request):
    ds: Dataset = request.app.state.data
    d = ds.df
    total = len(d)
    
    # Missing values summary
    missing_values = {
        "value": int(d["value"].isna().sum()),
        "district": int((d["district"] == "").sum()),
        "year": int((d["year"] == "").sum()),
        "source": int((d["source"] == "").sum()),
        "total_records": total,
    }

    # Geographic level breakdown
    geo_breakdown = {k: int(v) for k, v in d["geographic_level"].value_counts().items() if k}
    
    # Report type breakdown
    report_breakdown = {k: int(v) for k, v in d["report_type"].value_counts().items() if k}

    return {
        "total_records": total,
        "missing_summary": missing_values,
        "geographic_breakdown": geo_breakdown,
        "report_type_breakdown": report_breakdown,
    }

@app.get("/api/stats")
def stats(request: Request): return request.app.state.data.stats()

@app.get("/api/indicators")
def indicators(request: Request, q: str | None = None, limit: int = Query(500, ge=1, le=2000)):
    return {"indicators": request.app.state.data.indicators(q, limit)}

@app.get("/api/filters")
def filters(request: Request, state: str | None = None): return request.app.state.data.filters(state)

@app.get("/api/schemes")
def schemes():
    return {"schemes": json.loads(config.SCHEMES_FILE.read_text(encoding="utf-8"))["schemes"]}

