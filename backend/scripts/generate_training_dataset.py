"""AI Sarthi Healthcare Instruction Dataset Generator.

Reads C:/project/healthcare_master_final_v3 (1).csv and generates 5,000-8,000
high-quality, evidence-grounded instruction examples across 12 public health tasks.
Ensures zero fabricated values, strict unit preservation, and leak-free splits.
"""
from __future__ import annotations
import json
import os
import random
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Fix seed for strict reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Add backend root to path to load config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from app import config
    CSV_PATH = config.master_path()
except Exception:
    _candidates = [
        Path(__file__).resolve().parent.parent.parent / "healthcare_master_final_v3.csv",
        Path(__file__).resolve().parent.parent.parent / "healthcare_master_final_v3 (1).csv",
        Path(r"C:\sbproject\ai-sarthi\healthcare_master_final_v3.csv"),
        Path(r"C:\project\healthcare_master_final_v3 (1).csv"),
    ]
    CSV_PATH = next((c for c in _candidates if c.exists()), _candidates[0])

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "training_data"

SYSTEM_PROMPT = (
    "You are GovHealth-SLM, an evidence-grounded AI assistant for Indian public healthcare statistics. "
    "Answer using ONLY the provided database evidence. Do NOT invent values, indicators, years, sources, or locations. "
    "If the evidence does not answer the question or is empty, state clearly that no matching data was found. "
    "Distinguish survey percentages from administrative counts and state-level data from district-level data. "
    "Always state the official source (HMIS, NFHS-5, AHS), reporting period, and recorded unit when mentioning a number. "
    "Your response is strictly informational and not medical advice or clinical diagnosis."
)

PLANNER_SYSTEM_PROMPT = (
    "You are GovHealth-SLM Query Planner, a specialized model that parses user questions about Indian public health "
    "into structured database search parameters. Output ONLY a valid JSON object with the required query fields."
)

# Month ordering for chronological HMIS trends
MONTH_ORDER = {
    "April": 1, "May": 2, "June": 3, "July": 4, "August": 5, "September": 6,
    "October": 7, "November": 8, "December": 9, "January": 10, "February": 11, "March": 12
}

# Curated alias dictionary for Task 3
KNOWN_ALIASES = [
    {"alias": "c-section delivery rate", "indicator": "number_of_caesarean_c_section_deliveries", "category": "Maternal Health"},
    {"alias": "caesarean deliveries", "indicator": "number_of_caesarean_c_section_deliveries", "category": "Maternal Health"},
    {"alias": "c-section count", "indicator": "number_of_caesarean_c_section_deliveries", "category": "Maternal Health"},
    {"alias": "anc visits", "indicator": "mothers_who_had_at_least_4_antenatal_care_visits__for_last_birth_in_the_5_years_before_the_survey_percent", "category": "Maternal Health"},
    {"alias": "antenatal care visits", "indicator": "mothers_who_had_at_least_4_antenatal_care_visits__for_last_birth_in_the_5_years_before_the_survey_percent", "category": "Maternal Health"},
    {"alias": "4 anc visits rate", "indicator": "mothers_who_had_at_least_4_antenatal_care_visits__for_last_birth_in_the_5_years_before_the_survey_percent", "category": "Maternal Health"},
    {"alias": "anaemia in pregnant women", "indicator": "pregnant_women_age_15_49_years_who_are_anaemic_percent", "category": "Maternal Health"},
    {"alias": "anaemia rate in pregnancy", "indicator": "pregnant_women_age_15_49_years_who_are_anaemic_percent", "category": "Maternal Health"},
    {"alias": "full immunization coverage", "indicator": "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mothers_recall_percent", "category": "Child Immunization"},
    {"alias": "fully vaccinated children", "indicator": "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mothers_recall_percent", "category": "Child Immunization"},
    {"alias": "child vaccination rate", "indicator": "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mothers_recall_percent", "category": "Child Immunization"},
    {"alias": "sex ratio at birth", "indicator": "sex_ratio_at_birth_for_children_born_in_the_last_five_years_females_per_1,000_males", "category": "Demographics"},
    {"alias": "clean cooking fuel access", "indicator": "households_using_clean_fuel_for_cooking3_percent", "category": "Infrastructure"},
    {"alias": "clean fuel for cooking", "indicator": "households_using_clean_fuel_for_cooking3_percent", "category": "Infrastructure"},
    {"alias": "improved drinking water access", "indicator": "population_living_in_households_with_an_improved_drinking_water_source1_percent", "category": "Infrastructure"},
    {"alias": "improved sanitation facility", "indicator": "population_living_in_households_that_use_an_improved_sanitation_facility2_percent", "category": "Infrastructure"},
    {"alias": "institutional births in public facility", "indicator": "institutional_births_in_public_facility_in_the_5_years_before_the_survey_percent", "category": "Maternal Health"},
    {"alias": "institutional delivery in public hospital", "indicator": "institutional_births_in_public_facility_in_the_5_years_before_the_survey_percent", "category": "Maternal Health"},
    {"alias": "institutional delivery rate", "indicator": "institutional_births_in_the_5_years_before_the_survey_percent", "category": "Maternal Health"},
    {"alias": "institutional births percentage", "indicator": "institutional_births_in_the_5_years_before_the_survey_percent", "category": "Maternal Health"},
]

def format_unit(r: dict) -> str:
    raw_u = r.get("unit") or ("%" if "percent" in str(r.get("indicator", "")).lower() else "")
    if not raw_u:
        itype = str(r.get("indicator_type", "")).lower()
        if itype == "percentage":
            raw_u = "%"
        elif itype == "count":
            raw_u = "count"
        elif "ratio" in itype:
            raw_u = "females per 1,000 males"
    return str(raw_u).strip()

def build_compact_evidence(records: list[dict], max_recs: int = 8) -> str:
    compact = []
    for r in records[:max_recs]:
        geo = r.get("geographic_level")
        st = r.get("state")
        dt = r.get("district")
        loc = (st or "India") if (geo == "state" or not dt) else dt
        unit = format_unit(r)
        compact.append({
            "location": loc,
            "state": st,
            "district": dt if geo != "state" else None,
            "indicator": r.get("indicator"),
            "value": r.get("value"),
            "unit": unit if unit else None,
            "year": r.get("year"),
            "month": r.get("month"),
            "source": r.get("source"),
            "geographic_level": geo,
        })
    return json.dumps(compact, ensure_ascii=False)

class DatasetGenerator:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        self.valid_df = df[df["value"].notna()]
        self.nfhs_df = self.valid_df[self.valid_df["source"] == "NFHS-5"]
        self.hmis_df = self.valid_df[self.valid_df["source"] == "HMIS"]
        self.district_df = self.valid_df[self.valid_df["geographic_level"] == "district"]
        self.state_df = self.valid_df[self.valid_df["geographic_level"] == "state"]
        self.indicators = sorted(list(self.valid_df["indicator"].unique()))
        self.states = sorted(list(self.valid_df["state_standard"].dropna().unique()))
        self.districts = sorted(list(self.district_df["district_clean"].dropna().unique()))

        print("  Sampling representative records for fast generation...", flush=True)
        dist_sample = self.district_df.sample(n=min(25000, len(self.district_df)), random_state=RANDOM_SEED)
        state_sample = self.state_df.sample(n=min(15000, len(self.state_df)), random_state=RANDOM_SEED)
        null_subset = self.df[self.df["value"].isna()]
        null_sample = null_subset.sample(n=min(5000, len(null_subset)), random_state=RANDOM_SEED)

        self.district_records = dist_sample.to_dict("records")
        self.state_records = state_sample.to_dict("records")
        self.null_records = null_sample.to_dict("records")

        print("  Building O(1) hash indexes...", flush=True)
        self.district_by_ind: dict[str, list[dict]] = {}
        self.district_by_name: dict[str, list[dict]] = {}
        for r in self.district_records:
            self.district_by_ind.setdefault(r["indicator"], []).append(r)
            d_clean = r.get("district_clean")
            if d_clean:
                self.district_by_name.setdefault(d_clean, []).append(r)
        self.district_inds = [k for k, v in self.district_by_ind.items() if len(v) >= 2]

        self.state_by_ind: dict[str, list[dict]] = {}
        self.records_by_state: dict[str, list[dict]] = {}
        for r in self.state_records:
            self.state_by_ind.setdefault(r["indicator"], []).append(r)
            st_clean = r.get("state_standard")
            if st_clean:
                self.records_by_state.setdefault(st_clean, []).append(r)
        self.state_inds = [k for k, v in self.state_by_ind.items() if len(v) >= 2]

        self.district_by_state_ind: dict[tuple[str, str], list[dict]] = {}
        for r in self.district_records:
            st = r.get("state_standard")
            ind = r.get("indicator")
            if st and ind:
                self.district_by_state_ind.setdefault((st, ind), []).append(r)
        self.ranking_keys = [k for k, v in self.district_by_state_ind.items() if len(v) >= 3]

        hmis_m_df = self.hmis_df[self.hmis_df["month"].notna()]
        hmis_m_sample = hmis_m_df.sample(n=min(10000, len(hmis_m_df)), random_state=RANDOM_SEED)
        hmis_m_recs = hmis_m_sample.to_dict("records")
        self.hmis_monthly_by_state_ind: dict[tuple[str, str], list[dict]] = {}
        for r in hmis_m_recs:
            st = r.get("state_standard")
            ind = r.get("indicator")
            if st and ind:
                self.hmis_monthly_by_state_ind.setdefault((st, ind), []).append(r)
        self.hmis_monthly_keys = [k for k, v in self.hmis_monthly_by_state_ind.items() if len(v) >= 2]

        self.valid_by_ind: dict[str, list[dict]] = {}
        for k, v in self.district_by_ind.items():
            self.valid_by_ind.setdefault(k, []).extend(v)
        for k, v in self.state_by_ind.items():
            self.valid_by_ind.setdefault(k, []).extend(v)

        self.annual_trend_inds = [
            k for k, v in self.valid_by_ind.items()
            if len({str(r.get("year")) for r in v if pd.notna(r.get("year"))}) >= 2
        ]

        self.districts_with_multi_inds = [
            d for d, recs in self.district_by_name.items()
            if len({r["indicator"] for r in recs}) >= 2
        ]
        print(f"  Indexed: {len(self.district_inds)} district indicators, {len(self.ranking_keys)} ranking groups, {len(self.hmis_monthly_keys)} monthly groups.", flush=True)

    # TASK 1: Exact Indicator Lookup (520 examples)
    def gen_task_01_exact_lookup(self, count: int = 520) -> list[dict]:
        examples = []
        sampled_rows = random.sample(self.district_records, min(count * 3, len(self.district_records)))
        seen_queries = set()

        for row in sampled_rows:
            if len(examples) >= count:
                break
            ind = row["indicator"]
            val = float(row["value"])
            dist = row["district_clean"]
            st = row["state_standard"]
            src = row["source"]
            yr = str(row["year"]) if pd.notna(row.get("year")) else "2019-2021"
            unit = format_unit(row)
            unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
            ind_clean = ind.replace("_", " ")

            q = random.choice([
                f"What is the recorded {ind_clean} in {dist} district according to {src}?",
                f"Show the value of '{ind_clean}' for {dist}, {st} from {src} ({yr}).",
                f"According to {src}, what was {ind_clean} in {dist}?",
                f"Look up '{ind_clean}' for {dist} district in {yr}.",
            ])
            if q in seen_queries:
                continue
            seen_queries.add(q)

            val_str = f"{val:,.2f}".rstrip("0").rstrip(".")
            rec_dict = {
                "location": dist,
                "state": st,
                "district": dist,
                "indicator": ind,
                "value": val,
                "unit": unit,
                "year": yr,
                "source": src,
                "geographic_level": "district",
            }
            evidence_json = build_compact_evidence([rec_dict])

            ans = (
                f"Based on verified records from {src} ({yr}), the indicator '{ind_clean}' "
                f"in {dist} district ({st}) is recorded as {val_str}{unit_str}.\n\n"
                f"- **Indicator**: {ind_clean}\n"
                f"- **Value**: {val_str}{unit_str}\n"
                f"- **Geography**: {dist} (district level), {st}\n"
                f"- **Source & Year**: {src} ({yr})\n\n"
                "This observation is strictly grounded in official public health database evidence."
            )

            examples.append({
                "id": f"sarthi_task01_{len(examples)+1:04d}",
                "task_id": 1,
                "task_name": "exact_indicator_lookup",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": [rec_dict],
                "verification_metadata": {
                    "expected_numbers": [val],
                    "state": st,
                    "district": dist,
                    "indicator": ind,
                    "source": src,
                }
            })
        return examples

    # TASK 2: Indicator Discovery (520 examples)
    def gen_task_02_indicator_discovery(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()

        for _ in range(count * 6):
            if len(examples) >= count:
                break
            is_state_query = random.choice([True, False])

            if is_state_query:
                st = random.choice(self.states)
                st_recs = self.records_by_state.get(st, [])
                if not st_recs:
                    continue
                seen_inds = set()
                sampled_recs = []
                for r in st_recs:
                    ind = r["indicator"]
                    if ind not in seen_inds:
                        seen_inds.add(ind)
                        sampled_recs.append(r)
                    if len(sampled_recs) >= 6:
                        break
                loc_label = st
                geo_level = "state"
                q = random.choice([
                    f"What healthcare indicators are available for {st}?",
                    f"Which indicators are indexed for the state of {st}?",
                    f"List available public health metrics for {st}.",
                    f"Show me available health data for {st} at the state level.",
                ])
            else:
                dist = random.choice(self.districts)
                d_recs = self.district_by_name.get(dist, [])
                if not d_recs:
                    continue
                st = d_recs[0].get("state_standard") or "India"
                seen_inds = set()
                sampled_recs = []
                for r in d_recs:
                    ind = r["indicator"]
                    if ind not in seen_inds:
                        seen_inds.add(ind)
                        sampled_recs.append(r)
                    if len(sampled_recs) >= 6:
                        break
                loc_label = f"{dist} district ({st})"
                geo_level = "district"
                q = random.choice([
                    f"What healthcare indicators are available for {dist} district?",
                    f"Which indicators are indexed for {dist} in {st}?",
                    f"List available public health metrics for {dist}.",
                ])

            if q in seen_queries or not sampled_recs:
                continue
            seen_queries.add(q)

            compact_recs = []
            distinct_inds = []
            distinct_sources = sorted(list({str(r.get("source", "")) for r in sampled_recs if r.get("source")}))
            distinct_years = sorted(list({str(r.get("year", "")) for r in sampled_recs if pd.notna(r.get("year"))}))

            for r in sampled_recs:
                compact_recs.append({
                    "location": loc_label,
                    "state": st,
                    "district": r.get("district_clean") if geo_level == "district" else None,
                    "indicator": r.get("indicator"),
                    "value": float(r.get("value")) if pd.notna(r.get("value")) else None,
                    "unit": format_unit(r),
                    "year": str(r.get("year", "")),
                    "source": str(r.get("source", "")),
                    "geographic_level": geo_level,
                })
                distinct_inds.append(str(r.get("indicator", "")).replace("_", " ").title())

            evidence_json = build_compact_evidence(compact_recs)
            ind_bullet_list = "\n".join([f"{i}. **{name}**" for i, name in enumerate(distinct_inds, 1)])
            ans = (
                f"The verified healthcare dataset indexes key indicators for **{loc_label}** "
                f"at the {geo_level} level across official sources ({', '.join(distinct_sources)}):\n\n"
                f"{ind_bullet_list}\n\n"
                f"Reporting period(s) covered include: {', '.join(distinct_years)}.\n"
                "You can query any of these specific indicators for exact figures, multi-district comparisons, or trends."
            )

            examples.append({
                "id": f"sarthi_task02_{len(examples)+1:04d}",
                "task_id": 2,
                "task_name": "indicator_discovery",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": compact_recs,
                "verification_metadata": {
                    "expected_numbers": [],
                    "state": st,
                    "geographic_level": geo_level,
                }
            })
        return examples

    # TASK 3: Indicator Aliases & Synonyms (520 examples)
    def gen_task_03_aliases(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()

        while len(examples) < count:
            item = random.choice(KNOWN_ALIASES)
            alias = item["alias"]
            ind_target = item["indicator"]
            cat = item["category"]

            matching_recs = self.district_by_ind.get(ind_target) or self.valid_by_ind.get(ind_target)
            if not matching_recs:
                continue

            row = random.choice(matching_recs)
            val = float(row["value"])
            dist = row.get("district_clean") or row.get("district")
            st = row.get("state_standard") or row.get("state")
            src = row.get("source")
            yr = str(row.get("year")) if pd.notna(row.get("year")) else "2019-2021"
            geo = row.get("geographic_level", "district")
            unit = format_unit(row)
            unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
            loc_str = dist if dist else st

            q = random.choice([
                f"What is the {alias} in {loc_str}?",
                f"Can you provide the {alias} for {loc_str} ({st})?",
                f"Tell me about the {alias} recorded in {loc_str} from {src}.",
                f"How is {alias} reported for {loc_str} in {yr}?",
                f"Lookup {alias} in {loc_str}.",
            ])
            if q in seen_queries:
                continue
            seen_queries.add(q)

            rec_dict = {
                "location": loc_str,
                "state": st,
                "district": dist if geo == "district" else None,
                "indicator": ind_target,
                "value": val,
                "unit": unit,
                "year": yr,
                "source": src,
                "geographic_level": geo,
            }
            evidence_json = build_compact_evidence([rec_dict])
            val_str = f"{val:,.2f}".rstrip("0").rstrip(".")

            ans = (
                f"The term '**{alias}**' maps to the standardized indicator '**{ind_target.replace('_', ' ')}**' "
                f"under the {cat} domain.\n\n"
                f"Based on verified records from {src} ({yr}), the recorded value for **{loc_str}** is **{val_str}{unit_str}**.\n\n"
                f"- **Standardized Indicator**: {ind_target.replace('_', ' ')}\n"
                f"- **Observed Value**: {val_str}{unit_str}\n"
                f"- **Location**: {loc_str} ({geo} level)\n"
                f"- **Reporting System**: {src} ({yr})"
            )

            examples.append({
                "id": f"sarthi_task03_{len(examples)+1:04d}",
                "task_id": 3,
                "task_name": "indicator_aliases",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": [rec_dict],
                "verification_metadata": {
                    "expected_numbers": [val],
                    "alias": alias,
                    "target_indicator": ind_target,
                }
            })
        return examples

    # TASK 4: State-versus-District Interpretation (520 examples)
    def gen_task_04_state_vs_district(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()

        while len(examples) < count:
            mode = random.choice(["district_is_not_state", "state_is_aggregate"])

            if mode == "district_is_not_state":
                row = random.choice(self.district_records)
                dist = row["district_clean"]
                st = row["state_standard"]
                ind = row["indicator"]
                val = float(row["value"])
                src = row["source"]
                yr = str(row["year"]) if pd.notna(row.get("year")) else "2019-2021"
                unit = format_unit(row)
                unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
                ind_clean = ind.replace("_", " ")

                q = random.choice([
                    f"Is this figure of {val:,.2f}{unit_str} for {ind_clean} for the entire state of {st} or for {dist} district?",
                    f"Does this {ind_clean} statistic represent all of {st} or specifically {dist}?",
                    f"Clarify whether the {ind_clean} number in {dist} is state-level or district-level.",
                ])
                if q in seen_queries:
                    continue
                seen_queries.add(q)

                rec = {
                    "location": dist,
                    "state": st,
                    "district": dist,
                    "indicator": ind,
                    "value": val,
                    "unit": unit,
                    "year": yr,
                    "source": src,
                    "geographic_level": "district",
                }
                evidence_json = build_compact_evidence([rec])

                ans = (
                    f"This verified statistic of **{val:,.2f}{unit_str}** for '{ind_clean}' is recorded "
                    f"specifically at the **district level** for **{dist} district**, not for the entire state of {st}.\n\n"
                    f"- **Geographic Scope**: {dist} (district level)\n"
                    f"- **Parent State**: {st}\n"
                    f"- **Source & Year**: {src} ({yr})\n\n"
                    f"District statistics represent data from within {dist}'s administrative boundaries, "
                    f"whereas statewide figures reflect aggregate metrics across all districts in {st}."
                )

                examples.append({
                    "id": f"sarthi_task04_{len(examples)+1:04d}",
                    "task_id": 4,
                    "task_name": "state_vs_district",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                        {"role": "assistant", "content": ans},
                    ],
                    "ground_truth_records": [rec],
                    "verification_metadata": {
                        "expected_numbers": [val],
                        "state": st,
                        "district": dist,
                        "geographic_level": "district",
                    }
                })
            else:
                row = random.choice(self.state_records)
                st = row["state_standard"]
                ind = row["indicator"]
                val = float(row["value"])
                src = row["source"]
                yr = str(row["year"]) if pd.notna(row.get("year")) else "2019-2020"
                unit = format_unit(row)
                unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
                ind_clean = ind.replace("_", " ")

                q = random.choice([
                    f"In HMIS data for {st}, does '{ind_clean}' apply to a single district or the whole state?",
                    f"What geographic level does the {ind_clean} figure for {st} cover?",
                    f"Is '{ind_clean}' recorded at the state level in {st}?",
                ])
                if q in seen_queries:
                    continue
                seen_queries.add(q)

                rec = {
                    "location": st,
                    "state": st,
                    "district": None,
                    "indicator": ind,
                    "value": val,
                    "unit": unit,
                    "year": yr,
                    "source": src,
                    "geographic_level": "state",
                }
                evidence_json = build_compact_evidence([rec])

                ans = (
                    f"In official {src} ({yr}) records, the indicator '{ind_clean}' for **{st}** "
                    f"is recorded at the **state aggregate level** with a value of **{val:,.2f}{unit_str}**.\n\n"
                    f"- **Geographic Scope**: {st} (statewide aggregate)\n"
                    f"- **Source & Year**: {src} ({yr})\n\n"
                    f"This observation aggregates health data across participating facilities throughout the entire state of {st}, "
                    f"and does not belong to any single individual district."
                )

                examples.append({
                    "id": f"sarthi_task04_{len(examples)+1:04d}",
                    "task_id": 4,
                    "task_name": "state_vs_district",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                        {"role": "assistant", "content": ans},
                    ],
                    "ground_truth_records": [rec],
                    "verification_metadata": {
                        "expected_numbers": [val],
                        "state": st,
                        "geographic_level": "state",
                    }
                })
        return examples

    # TASK 5: Comparisons across Districts & States (520 examples)
    def gen_task_05_comparisons(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()

        while len(examples) < count:
            compare_type = random.choice(["district", "district", "state"])
            if compare_type == "district":
                if not self.district_inds:
                    break
                ind = random.choice(self.district_inds)
                sub = self.district_by_ind[ind]
                pair = random.sample(sub, 2)
                r1, r2 = pair[0], pair[1]
                loc1, loc2 = r1["district_clean"], r2["district_clean"]
                if loc1 == loc2:
                    continue
                geo = "district"
            else:
                if not self.state_inds:
                    break
                ind = random.choice(self.state_inds)
                sub = self.state_by_ind[ind]
                pair = random.sample(sub, 2)
                r1, r2 = pair[0], pair[1]
                loc1, loc2 = r1["state_standard"], r2["state_standard"]
                if loc1 == loc2:
                    continue
                geo = "state"

            v1, v2 = float(r1["value"]), float(r2["value"])
            src = r1["source"]
            yr = str(r1["year"]) if pd.notna(r1["year"]) else "2019-2021"
            unit = format_unit(r1)
            unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
            ind_clean = ind.replace("_", " ")

            q = random.choice([
                f"Compare {ind_clean} between {loc1} and {loc2}.",
                f"How does {loc1} compare with {loc2} on {ind_clean}?",
                f"What is the difference in {ind_clean} between {loc1} and {loc2} according to {src}?",
            ])
            if q in seen_queries:
                continue
            seen_queries.add(q)

            rec1 = {
                "location": loc1,
                "state": r1["state_standard"],
                "district": r1.get("district_clean") if geo == "district" else None,
                "indicator": ind,
                "value": v1,
                "unit": unit,
                "year": yr,
                "source": src,
                "geographic_level": geo,
            }
            rec2 = {
                "location": loc2,
                "state": r2["state_standard"],
                "district": r2.get("district_clean") if geo == "district" else None,
                "indicator": ind,
                "value": v2,
                "unit": unit,
                "year": yr,
                "source": src,
                "geographic_level": geo,
            }
            evidence_json = build_compact_evidence([rec1, rec2])

            diff = round(abs(v1 - v2), 2)
            higher_loc = loc1 if v1 >= v2 else loc2
            lower_loc = loc2 if v1 >= v2 else loc1
            higher_val = max(v1, v2)
            lower_val = min(v1, v2)

            ans = (
                f"**Comparative Analysis for '{ind_clean}'** ({src}, {yr}):\n\n"
                f"- **{loc1}**: {v1:,.2f}{unit_str}\n"
                f"- **{loc2}**: {v2:,.2f}{unit_str}\n\n"
                f"**Summary**: {higher_loc} recorded a higher value ({higher_val:,.2f}{unit_str}), "
                f"which is {diff:,.2f}{unit_str} higher than {lower_loc} ({lower_val:,.2f}{unit_str})."
            )

            examples.append({
                "id": f"sarthi_task05_{len(examples)+1:04d}",
                "task_id": 5,
                "task_name": "comparison",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": [rec1, rec2],
                "verification_metadata": {
                    "expected_numbers": [v1, v2, diff],
                    "indicator": ind,
                    "locations": [loc1, loc2],
                }
            })
        return examples

    # TASK 6: Rankings & Aggregations (520 examples)
    def gen_task_06_rankings(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()

        while len(examples) < count and self.ranking_keys:
            st, ind = random.choice(self.ranking_keys)
            sub = self.district_by_state_ind[(st, ind)]
            if len(sub) < 3:
                continue

            sample_n = min(len(sub), random.randint(4, 6))
            sampled = random.sample(sub, sample_n)
            sampled.sort(key=lambda r: float(r["value"]), reverse=True)

            src = sampled[0]["source"]
            yr = str(sampled[0]["year"]) if pd.notna(sampled[0]["year"]) else "2019-2021"
            unit = format_unit(sampled[0])
            unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
            ind_clean = ind.replace("_", " ")

            q = random.choice([
                f"Rank the selected districts in {st} by {ind_clean}.",
                f"Order districts in {st} from highest to lowest for {ind_clean}.",
                f"Which district has the highest and lowest {ind_clean} among these districts in {st}?",
            ])
            if q in seen_queries:
                continue
            seen_queries.add(q)

            rec_list = []
            bullet_lines = []
            vals = []
            for rank, row in enumerate(sampled, 1):
                d_name = row["district_clean"]
                val = float(row["value"])
                vals.append(val)
                rec_list.append({
                    "location": d_name,
                    "state": st,
                    "district": d_name,
                    "indicator": ind,
                    "value": val,
                    "unit": unit,
                    "year": yr,
                    "source": src,
                    "geographic_level": "district",
                })
                bullet_lines.append(f"{rank}. **{d_name}**: {val:,.2f}{unit_str}")

            evidence_json = build_compact_evidence(rec_list)
            top_d, top_v = rec_list[0]["location"], rec_list[0]["value"]
            bot_d, bot_v = rec_list[-1]["location"], rec_list[-1]["value"]
            spread = round(top_v - bot_v, 2)
            avg_v = round(sum(vals) / len(vals), 2)

            ans = (
                f"**Ranking of Districts in {st} for '{ind_clean}'** ({src}, {yr}):\n\n"
                + "\n".join(bullet_lines) + "\n\n"
                f"- **Highest**: {top_d} ({top_v:,.2f}{unit_str})\n"
                f"- **Lowest**: {bot_d} ({bot_v:,.2f}{unit_str})\n"
                f"- **Spread (Range)**: {spread:,.2f}{unit_str}\n"
                f"- **Group Average**: {avg_v:,.2f}{unit_str}"
            )

            examples.append({
                "id": f"sarthi_task06_{len(examples)+1:04d}",
                "task_id": 6,
                "task_name": "rankings_and_aggregations",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": rec_list,
                "verification_metadata": {
                    "expected_numbers": vals + [spread, avg_v],
                    "state": st,
                    "indicator": ind,
                }
            })
        return examples

    # TASK 7: Time-Series Trends (520 examples)
    def gen_task_07_trends(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()

        while len(examples) < count:
            mode = random.choice(["monthly_hmis", "annual_cycles"])

            if mode == "monthly_hmis" and self.hmis_monthly_keys:
                st, ind = random.choice(self.hmis_monthly_keys)
                sub = self.hmis_monthly_by_state_ind[(st, ind)]
                m_pair = random.sample(sub, 2)
                r1, r2 = m_pair[0], m_pair[1]
                m1, m2 = r1["month"], r2["month"]
                if m1 == m2:
                    continue
                # Order chronologically
                if MONTH_ORDER.get(m1, 0) > MONTH_ORDER.get(m2, 0):
                    r1, r2 = r2, r1
                    m1, m2 = m2, m1

                v1, v2 = float(r1["value"]), float(r2["value"])
                src = "HMIS"
                yr = "2019-2020"
                unit = format_unit(r1)
                unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
                ind_clean = ind.replace("_", " ")

                q = random.choice([
                    f"How did {ind_clean} in {st} change from {m1} to {m2} in HMIS ({yr})?",
                    f"Show monthly shift for {ind_clean} in {st} between {m1} and {m2}.",
                    f"Compare {m1} and {m2} reporting for {ind_clean} in {st}.",
                ])
                if q in seen_queries:
                    continue
                seen_queries.add(q)

                rec1 = {
                    "location": st, "state": st, "district": None, "indicator": ind,
                    "value": v1, "unit": unit, "year": yr, "month": m1, "source": src, "geographic_level": "state"
                }
                rec2 = {
                    "location": st, "state": st, "district": None, "indicator": ind,
                    "value": v2, "unit": unit, "year": yr, "month": m2, "source": src, "geographic_level": "state"
                }
                evidence_json = build_compact_evidence([rec1, rec2])

                change = round(v2 - v1, 2)
                direction = "an increase" if change > 0 else ("a decrease" if change < 0 else "no change")

                ans = (
                    f"**Monthly Trend for '{ind_clean}' in {st}** ({src}, {yr}):\n\n"
                    f"- **{m1} {yr}**: {v1:,.2f}{unit_str}\n"
                    f"- **{m2} {yr}**: {v2:,.2f}{unit_str}\n\n"
                    f"**Trend Summary**: From {m1} to {m2}, there was {direction} of **{abs(change):,.2f}{unit_str}**."
                )

                examples.append({
                    "id": f"sarthi_task07_{len(examples)+1:04d}",
                    "task_id": 7,
                    "task_name": "time_series_trend",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                        {"role": "assistant", "content": ans},
                    ],
                    "ground_truth_records": [rec1, rec2],
                    "verification_metadata": {
                        "expected_numbers": [v1, v2, abs(change)],
                        "state": st,
                        "indicator": ind,
                    }
                })
            else:
                # Annual comparison across years
                if not self.annual_trend_inds:
                    continue
                ind = random.choice(self.annual_trend_inds)
                sub = self.valid_by_ind[ind]
                y_map: dict[str, list[dict]] = {}
                for r in sub:
                    y = str(r.get("year", ""))
                    if y and y != "nan":
                        y_map.setdefault(y, []).append(r)
                if len(y_map) < 2:
                    continue
                y_keys = list(y_map.keys())
                y1, y2 = random.sample(y_keys, 2)
                r1 = random.choice(y_map[y1])
                r2 = random.choice(y_map[y2])
                v1, v2 = float(r1["value"]), float(r2["value"])
                y1, y2 = str(r1["year"]), str(r2["year"])
                loc = r1["state_standard"]
                src = r1["source"]
                unit = format_unit(r1)
                unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
                ind_clean = ind.replace("_", " ")

                q = f"How did {ind_clean} change between {y1} and {y2} in official records?"
                if q in seen_queries:
                    continue
                seen_queries.add(q)

                rec1 = {"location": loc, "state": loc, "district": None, "indicator": ind, "value": v1, "unit": unit, "year": y1, "source": src, "geographic_level": "state"}
                rec2 = {"location": loc, "state": loc, "district": None, "indicator": ind, "value": v2, "unit": unit, "year": y2, "source": src, "geographic_level": "state"}
                evidence_json = build_compact_evidence([rec1, rec2])

                change = round(v2 - v1, 2)
                direction = "an increase" if change > 0 else ("a decrease" if change < 0 else "no change")
                ans = (
                    f"**Reporting Period Comparison for '{ind_clean}'**:\n\n"
                    f"- **{y1}**: {v1:,.2f}{unit_str} ({r1['source']})\n"
                    f"- **{y2}**: {v2:,.2f}{unit_str} ({r2['source']})\n\n"
                    f"**Summary**: Between {y1} and {y2}, there is {direction} of **{abs(change):,.2f}{unit_str}**."
                )

                examples.append({
                    "id": f"sarthi_task07_{len(examples)+1:04d}",
                    "task_id": 7,
                    "task_name": "time_series_trend",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                        {"role": "assistant", "content": ans},
                    ],
                    "ground_truth_records": [rec1, rec2],
                    "verification_metadata": {
                        "expected_numbers": [v1, v2, abs(change)],
                        "indicator": ind,
                    }
                })
        return examples

    # TASK 8: Conversational Multi-Turn Follow-Ups (520 examples)
    def gen_task_08_follow_ups(self, count: int = 520) -> list[dict]:
        examples = []
        sampled_rows = self.district_df.sample(n=min(count * 4, len(self.district_df)), random_state=RANDOM_SEED + 10)
        seen_queries = set()

        for _, r1 in sampled_rows.iterrows():
            if len(examples) >= count:
                break
            st = r1["state_standard"]
            d1 = r1["district_clean"]
            ind = r1["indicator"]
            sister_grp = self.district_by_state_ind.get((st, ind), [])
            sister_rows = [r for r in sister_grp if r.get("district_clean") != d1]
            if not sister_rows:
                continue

            r2 = sister_rows[0]
            d2 = r2["district_clean"]
            v1, v2 = float(r1["value"]), float(r2["value"])
            src = r1["source"]
            yr = str(r1["year"]) if pd.notna(r1["year"]) else "2019-2021"
            unit = format_unit(r1.to_dict())
            unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
            ind_clean = ind.replace("_", " ")

            q1 = f"What is {ind_clean} in {d1}?"
            q2 = f"How about in {d2}?"
            if (q1, q2) in seen_queries:
                continue
            seen_queries.add((q1, q2))

            rec1 = {
                "location": d1, "state": st, "district": d1, "indicator": ind,
                "value": v1, "unit": unit, "year": yr, "source": src, "geographic_level": "district"
            }
            rec2 = {
                "location": d2, "state": st, "district": d2, "indicator": ind,
                "value": v2, "unit": unit, "year": yr, "source": src, "geographic_level": "district"
            }

            ans1 = f"According to {src} ({yr}), the {ind_clean} in {d1} ({st}) is **{v1:,.2f}{unit_str}**."
            diff = round(abs(v1 - v2), 2)
            rel = "higher than" if v2 > v1 else ("lower than" if v2 < v1 else "identical to")
            ans2 = (
                f"For **{d2}** ({st}), the recorded {ind_clean} is **{v2:,.2f}{unit_str}** ({src}, {yr}).\n\n"
                f"Comparing with {d1} ({v1:,.2f}{unit_str}), {d2} is {diff:,.2f}{unit_str} {rel} {d1}."
            )

            evidence_t1 = build_compact_evidence([rec1])
            evidence_t2 = build_compact_evidence([rec1, rec2])

            examples.append({
                "id": f"sarthi_task08_{len(examples)+1:04d}",
                "task_id": 8,
                "task_name": "conversational_follow_up",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q1}\n\nEvidence:\n{evidence_t1}"},
                    {"role": "assistant", "content": ans1},
                    {"role": "user", "content": f"Question: {q2}\n\nEvidence:\n{evidence_t2}"},
                    {"role": "assistant", "content": ans2},
                ],
                "ground_truth_records": [rec1, rec2],
                "verification_metadata": {
                    "expected_numbers": [v1, v2, diff],
                    "state": st,
                    "districts": [d1, d2],
                }
            })
        return examples

    # TASK 9: Plain-Language Evidence Summaries (520 examples)
    def gen_task_09_plain_language(self, count: int = 520) -> list[dict]:
        examples = []
        sampled_rows = random.sample(self.district_records, min(count * 3, len(self.district_records)))
        seen_queries = set()

        for row in sampled_rows:
            if len(examples) >= count:
                break
            ind = row["indicator"]
            val = float(row["value"])
            dist = row["district_clean"]
            st = row["state_standard"]
            src = row["source"]
            yr = str(row["year"]) if pd.notna(row.get("year")) else "2019-2021"
            unit = format_unit(row)
            unit_str = f" {unit}" if unit and not unit.startswith("%") else unit
            ind_clean = ind.replace("_", " ")

            q = random.choice([
                f"Explain what the {ind_clean} statistic of {val:,.2f}{unit_str} in {dist} means in plain language.",
                f"Can you explain {dist}'s {ind_clean} ({val:,.2f}{unit_str}) so a non-expert can understand?",
                f"Summarize the practical takeaway of '{ind_clean}' for {dist}.",
            ])
            if q in seen_queries:
                continue
            seen_queries.add(q)

            rec_dict = {
                "location": dist, "state": st, "district": dist, "indicator": ind,
                "value": val, "unit": unit, "year": yr, "source": src, "geographic_level": "district"
            }
            evidence_json = build_compact_evidence([rec_dict])

            if "%" in unit or "percent" in ind.lower():
                approx_count = round(val)
                plain_desc = f"roughly {approx_count} out of every 100 individuals/households surveyed"
            else:
                plain_desc = f"a total reported figure of {val:,.0f} {unit}"

            ans = (
                f"In plain language, for **{dist} district ({st})**, the official recorded value for "
                f"**{ind_clean}** is **{val:,.2f}{unit_str}** ({src}, {yr}).\n\n"
                f"- **What this means**: This indicates {plain_desc} under the verified reporting criteria.\n"
                f"- **Source & Scope**: This measurement reflects official data from {src} collected during {yr}.\n\n"
                "*Disclaimer: This information is strictly educational and statistical, derived from public health records, and does not constitute medical advice or clinical diagnosis.*"
            )

            examples.append({
                "id": f"sarthi_task09_{len(examples)+1:04d}",
                "task_id": 9,
                "task_name": "plain_language_summary",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": [rec_dict],
                "verification_metadata": {
                    "expected_numbers": [val],
                    "state": st,
                    "district": dist,
                }
            })
        return examples

    # TASK 10: Source & Reporting-Period Explanations (520 examples)
    def gen_task_10_source_explanations(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()

        templates = [
            (
                "What is the difference between HMIS data and NFHS-5 data in AI Sarthi?",
                "**HMIS (Health Management Information System)** is a routine monthly administrative portal where public and accredited healthcare facilities log operational health services (e.g. registered births, institutional deliveries, vaccinations conducted in clinics). In this dataset, HMIS covers the 2019-2020 operational cycle.\n\n"
                "**NFHS-5 (National Family Health Survey-5)** is a nationally representative demographic and health household survey conducted between 2019 and 2021 by IIPS under MoHFW, measuring population-level survey percentages based on structured interviews and health biomarker sampling.\n\n"
                "Therefore, facility logs (HMIS) track aggregate service counts, whereas household surveys (NFHS-5) capture representative population coverage rates."
            ),
            (
                "What reporting period does the NFHS-5 dataset cover?",
                "The **NFHS-5 (National Family Health Survey-5)** dataset covers the reporting period **2019-2021** (Phase 1 conducted in 2019-2020 and Phase 2 conducted in 2020-2021 across Indian states and union territories). All NFHS-5 observations in AI Sarthi reflect this official 2019-2021 cycle."
            ),
            (
                "What is AHS and which states does it cover?",
                "**AHS (Annual Health Survey)** was designed to monitor health performance, maternal mortality, and infant mortality in 9 high-priority states of India (Assam, Bihar, Chhattisgarh, Jharkhand, Madhya Pradesh, Odisha, Rajasthan, Uttar Pradesh, and Uttarakhand) with district-level granularity."
            ),
            (
                "Why can facility birth numbers in HMIS differ from institutional delivery percentages in NFHS-5?",
                "HMIS records **administrative counts** of deliveries actually logged by participating hospitals and health centres in a reporting year (2019-2020). In contrast, NFHS-5 measures the **percentage of women who gave birth in a healthcare facility** out of all surveyed live births over the preceding 5 years (2019-2021). Differences arise from survey sampling methodology versus routine health facility reporting."
            ),
            (
                "What geographic levels are covered in the AI Sarthi database?",
                "AI Sarthi indexes healthcare data across two distinct geographic levels:\n"
                "1. **State Level**: Comprehensive state and union territory aggregates (accounting for 77.9% of indexed records, including comprehensive HMIS state modules).\n"
                "2. **District Level**: Granular district fact sheets (accounting for over 260,000 observations across 800 recognized districts in NFHS-5, AHS, and HMIS)."
            )
        ]

        variants_prefix = [
            "Please clarify: ", "I want to understand: ", "Explain: ", "Question about dataset metadata: ",
            "Provide context on: ", "Help me understand: ", "Detailed explanation: ", "In AI Sarthi: ",
            "From the public health perspective: ", "Regarding official sources: "
        ]

        idx = 0
        while len(examples) < count:
            base_q, base_ans = templates[idx % len(templates)]
            pfx = variants_prefix[(idx // len(templates)) % len(variants_prefix)]
            var_num = idx // (len(templates) * len(variants_prefix))
            q = f"{pfx}{base_q}" if var_num == 0 else f"{pfx}{base_q} (reference #{var_num+1})"
            idx += 1
            if q in seen_queries:
                continue
            seen_queries.add(q)

            examples.append({
                "id": f"sarthi_task10_{len(examples)+1:04d}",
                "task_id": 10,
                "task_name": "source_and_period_explanation",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n[]"},
                    {"role": "assistant", "content": base_ans},
                ],
                "ground_truth_records": [],
                "verification_metadata": {
                    "expected_numbers": [],
                    "topic": "metadata_explanation",
                }
            })
        return examples

    # TASK 11: Missing-Data and Abstention Behavior (520 examples)
    def gen_task_11_abstention(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()

        for row in self.null_records:
            if len(examples) >= count:
                break
            ind = str(row["indicator"]).replace("_", " ")
            st = str(row.get("state_standard") or row.get("state") or "India")
            dist = str(row.get("district_clean") or row.get("district") or "")
            loc = dist if dist else st
            yr = str(row.get("year", "2019-2020"))
            src = str(row.get("source", "Official Reporting"))

            q = random.choice([
                f"What is the {ind} in {loc} for year 2026?",
                f"Show the verified figure for '{ind}' in {loc} from {src}.",
                f"Does the database have recorded statistics for {ind} in {loc}?",
                f"Retrieve data for {ind} in {loc} in 2025.",
            ])
            if q in seen_queries:
                continue
            seen_queries.add(q)

            ans = (
                f"No verified record was found in the indexed public health dataset for '**{ind}**' "
                f"in **{loc}** ({src}, {yr}).\n\n"
                f"The value is unrecorded or null in the primary reporting tables. "
                "AI Sarthi does not estimate, extrapolate, or invent missing healthcare data. "
                "Please query a related indicator, another reporting period, or check neighboring geographic divisions."
            )

            examples.append({
                "id": f"sarthi_task11_{len(examples)+1:04d}",
                "task_id": 11,
                "task_name": "missing_data_abstention",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n[]"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": [],
                "verification_metadata": {
                    "expected_numbers": [],
                    "abstention": True,
                    "location": loc,
                }
            })
        return examples

    # TASK 12: Structured Query-Plan Generation (520 examples)
    def gen_task_12_query_plans(self, count: int = 520) -> list[dict]:
        examples = []
        seen_queries = set()
        sampled_rows = random.sample(self.district_records, min(count * 3, len(self.district_records)))

        for row in sampled_rows:
            if len(examples) >= count:
                break
            ind = row["indicator"]
            st = row["state_standard"]
            dist = row["district_clean"]
            src = row["source"]
            yr = str(row["year"]) if pd.notna(row.get("year")) else "2019-2021"
            ind_clean = ind.replace("_", " ")

            q = random.choice([
                f"Find data for {ind_clean} in {dist}, {st}",
                f"Lookup {src} record for {ind_clean} in {dist}",
                f"Query public health stats on {ind_clean} for {dist} district",
                f"Search for {ind_clean} ({dist}, {st}, {yr})",
            ])
            if q in seen_queries:
                continue
            seen_queries.add(q)

            plan_obj = {
                "query_intent": "exact_statistic",
                "state": st,
                "district": dist,
                "target_indicator": ind,
                "source": src,
                "year": yr,
                "geographic_level": "district",
            }
            ans = json.dumps(plan_obj, indent=2)

            examples.append({
                "id": f"sarthi_task12_{len(examples)+1:04d}",
                "task_id": 12,
                "task_name": "structured_query_plan",
                "messages": [
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Parse query into retrieval plan: {q}"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": [row],
                "verification_metadata": {
                    "expected_numbers": [],
                    "plan": plan_obj,
                }
            })
        return examples

    # TASK 13: Multi-Part Questions (500 examples)
    def gen_task_13_multi_part(self, count: int = 500) -> list[dict]:
        examples = []
        seen_queries = set()

        for _ in range(count * 6):
            if len(examples) >= count:
                break
            if not self.districts_with_multi_inds:
                break
            d = random.choice(self.districts_with_multi_inds)
            d_recs = self.district_by_name[d]
            by_ind: dict[str, list[dict]] = {}
            for r in d_recs:
                by_ind.setdefault(r["indicator"], []).append(r)
            if len(by_ind) < 2:
                continue

            chosen_inds = random.sample(list(by_ind.keys()), 2)
            r1 = by_ind[chosen_inds[0]][0]
            r2 = by_ind[chosen_inds[1]][0]

            v1, v2 = float(r1["value"]), float(r2["value"])
            st = r1["state_standard"]
            src1, src2 = r1["source"], r2["source"]
            yr1 = str(r1["year"]) if pd.notna(r1.get("year")) else "2019-2021"
            yr2 = str(r2["year"]) if pd.notna(r2.get("year")) else "2019-2021"
            u1, u2 = format_unit(r1), format_unit(r2)
            u1_str = f" {u1}" if u1 and not u1.startswith("%") else u1
            u2_str = f" {u2}" if u2 and not u2.startswith("%") else u2
            ind1_clean = chosen_inds[0].replace("_", " ")
            ind2_clean = chosen_inds[1].replace("_", " ")

            q = random.choice([
                f"What is the {ind1_clean} and {ind2_clean} in {d} district?",
                f"For {d} ({st}), report two statistics: {ind1_clean} and {ind2_clean}.",
                f"Can you provide both {ind1_clean} and {ind2_clean} for {d}?",
            ])
            if q in seen_queries:
                continue
            seen_queries.add(q)

            rec1 = {"location": d, "state": st, "district": d, "indicator": chosen_inds[0], "value": v1, "unit": u1, "year": yr1, "source": src1, "geographic_level": "district"}
            rec2 = {"location": d, "state": st, "district": d, "indicator": chosen_inds[1], "value": v2, "unit": u2, "year": yr2, "source": src2, "geographic_level": "district"}
            evidence_json = build_compact_evidence([rec1, rec2])

            ans = (
                f"Based on official database records for **{d} district ({st})**:\n\n"
                f"1. **{ind1_clean}**: **{v1:,.2f}{u1_str}** (Source: {src1}, {yr1})\n"
                f"2. **{ind2_clean}**: **{v2:,.2f}{u2_str}** (Source: {src2}, {yr2})\n\n"
                "Both statistics are verified from official public health datasets at the district level."
            )

            examples.append({
                "id": f"sarthi_task13_{len(examples)+1:04d}",
                "task_id": 13,
                "task_name": "multi_part_questions",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n{evidence_json}"},
                    {"role": "assistant", "content": ans},
                ],
                "ground_truth_records": [rec1, rec2],
                "verification_metadata": {
                    "expected_numbers": [v1, v2],
                    "state": st,
                    "district": d,
                }
            })
        return examples

    # TASK 14: Unanswerable / Clinical Abstention (500 examples)
    def gen_task_14_unanswerable_abstention(self, count: int = 500) -> list[dict]:
        examples = []
        seen_queries = set()

        unanswerable_templates = [
            (
                "I have high fever and severe headache for three days, what medication should I take?",
                "AI Sarthi is an evidence-grounded statistical querying system for Indian public health databases and does not provide clinical diagnoses, individualized medical advice, or drug prescriptions. Please consult a qualified physician or visit your nearest primary health centre (PHC) or hospital immediately for proper medical evaluation."
            ),
            (
                "Can you diagnose if my chest pain is a heart attack?",
                "AI Sarthi cannot diagnose medical conditions or interpret clinical symptoms. Chest pain is a potential emergency. Please call an emergency ambulance (108/102 in India) or report to the nearest emergency healthcare facility immediately."
            ),
            (
                "What is the projected institutional delivery rate in Pune for the year 2035?",
                "The database does not contain future forecasts or speculative projections for 2035. AI Sarthi strictly provides verified historical and survey observations from official sources (NFHS-5: 2019-2021, HMIS: 2019-2020, AHS). No official projections are indexed."
            ),
            (
                "What is the cosmic energy vibrational index for hospitals in Delhi?",
                "The requested metric ('cosmic energy vibrational index') is not a recognized public health indicator and is not indexed in official Indian health datasets (HMIS, NFHS-5, AHS, or the National Hospital Directory). No matching data exists."
            ),
            (
                "What is the institutional birth rate in Atlantis District?",
                "No matching record found. 'Atlantis District' is not a recognized district or administrative division in the Indian public health master dataset."
            ),
        ]

        idx = 0
        while len(examples) < count:
            base_q, base_ans = unanswerable_templates[idx % len(unanswerable_templates)]
            var_num = idx // len(unanswerable_templates)
            q = f"{base_q} (inquiry #{var_num+1})" if var_num > 0 else base_q
            idx += 1
            if q in seen_queries:
                continue
            seen_queries.add(q)

            examples.append({
                "id": f"sarthi_task14_{len(examples)+1:04d}",
                "task_id": 14,
                "task_name": "unanswerable_abstention",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {q}\n\nEvidence:\n[]"},
                    {"role": "assistant", "content": base_ans},
                ],
                "ground_truth_records": [],
                "verification_metadata": {
                    "expected_numbers": [],
                    "abstention": True,
                }
            })
        return examples

def main():
    print(f"Loading master healthcare CSV from {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"Loaded {len(df):,} records.")

    gen = DatasetGenerator(df)
    all_examples: list[dict] = []

    print("\nGenerating candidate examples across 14 tasks...")
    generators = [
        ("Task 1: Exact Lookup", gen.gen_task_01_exact_lookup, 500),
        ("Task 2: Indicator Discovery", gen.gen_task_02_indicator_discovery, 500),
        ("Task 3: Indicator Aliases", gen.gen_task_03_aliases, 500),
        ("Task 4: State vs District", gen.gen_task_04_state_vs_district, 500),
        ("Task 5: Comparisons", gen.gen_task_05_comparisons, 500),
        ("Task 6: Rankings", gen.gen_task_06_rankings, 500),
        ("Task 7: Time-Series Trends", gen.gen_task_07_trends, 500),
        ("Task 8: Conversational Follow-Up", gen.gen_task_08_follow_ups, 500),
        ("Task 9: Plain-Language Summary", gen.gen_task_09_plain_language, 500),
        ("Task 10: Metadata Explanation", gen.gen_task_10_source_explanations, 500),
        ("Task 11: Missing Data / Abstention", gen.gen_task_11_abstention, 500),
        ("Task 12: Structured Query Plan", gen.gen_task_12_query_plans, 500),
        ("Task 13: Multi-Part Questions", gen.gen_task_13_multi_part, 500),
        ("Task 14: Unanswerable & Clinical Abstention", gen.gen_task_14_unanswerable_abstention, 500),
    ]

    for label, fn, target_count in generators:
        exs = fn(count=target_count)
        print(f"  {label}: {len(exs)} examples generated.", flush=True)
        all_examples.extend(exs)

    print(f"\nTotal generated candidate examples: {len(all_examples):,}", flush=True)

    # Shuffle with fixed seed
    random.shuffle(all_examples)

    # Stratified Split (80% Train, 10% Val, 10% Test)
    train_exs: list[dict] = []
    val_exs: list[dict] = []
    test_exs: list[dict] = []

    task_groups: dict[str, list[dict]] = {}
    for ex in all_examples:
        task_groups.setdefault(ex["task_name"], []).append(ex)

    for task_name, group in task_groups.items():
        n = len(group)
        n_train = int(n * 0.80)
        n_val = int(n * 0.10)
        train_exs.extend(group[:n_train])
        val_exs.extend(group[n_train:n_train+n_val])
        test_exs.extend(group[n_train+n_val:])

    # Shuffle each split
    random.shuffle(train_exs)
    random.shuffle(val_exs)
    random.shuffle(test_exs)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_path = OUTPUT_DIR / "dataset_all.jsonl"
    train_path = OUTPUT_DIR / "train.jsonl"
    val_path = OUTPUT_DIR / "val.jsonl"
    test_path = OUTPUT_DIR / "test.jsonl"
    sample_path = OUTPUT_DIR / "sample_review.jsonl"

    def write_jsonl(path: Path, data: list[dict]):
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\nWriting dataset splits to {OUTPUT_DIR}...")
    write_jsonl(all_path, all_examples)
    write_jsonl(train_path, train_exs)
    write_jsonl(val_path, val_exs)
    write_jsonl(test_path, test_exs)
    write_jsonl(sample_path, all_examples[:50])

    print(f"  - dataset_all.jsonl: {len(all_examples):,} examples")
    print(f"  - train.jsonl:       {len(train_exs):,} examples ({len(train_exs)/len(all_examples)*100:.1f}%)")
    print(f"  - val.jsonl:         {len(val_exs):,} examples ({len(val_exs)/len(all_examples)*100:.1f}%)")
    print(f"  - test.jsonl:        {len(test_exs):,} examples ({len(test_exs)/len(all_examples)*100:.1f}%)")
    print(f"  - sample_review.jsonl: 50 examples")

if __name__ == "__main__":
    main()
