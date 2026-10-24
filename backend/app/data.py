"""Dataset loading, filtering, keyword retrieval and statistics (mirrors notebook logic)."""
from __future__ import annotations
import re
from pathlib import Path
import numpy as np
import pandas as pd

COLS = ["state", "district", "year", "month", "source", "indicator", "parameter",
        "category", "value", "geographic_level", "report_type", "indicator_type"]
STOP = {
    "what", "which", "where", "when", "does", "show", "give", "tell", "find", "data",
    "about", "from", "with", "for", "the", "and", "are", "was", "were", "metric",
    "metrics", "indicator", "indicators", "district", "districts", "state", "states",
    "parameter", "parameters", "value", "values", "number", "numbers", "level", "levels",
    "available", "record", "records", "how", "many", "much", "is", "in", "of", "to",
    "can", "help", "me", "you", "ai", "sarthi", "infomed", "please", "could", "would", "will",
    "this", "that", "these", "those", "have", "has", "had", "summarize", "summary",
    "explain", "explanation", "mean", "meaning", "results", "result", "retrieved",
    "healthcare", "health", "simple", "language", "terms", "say", "get", "there",
    "count", "counts", "rate", "rates",
}

class Dataset:
    def __init__(self, path: Path):
        if not Path(path).exists():
            raise FileNotFoundError(f"Master dataset not found: {path}")
        df = pd.read_csv(path, low_memory=False, dtype={"year": "string", "month": "string"})
        for c in df.select_dtypes(include=["object", "string"]).columns:
            df[c] = df[c].fillna("").astype(str)
        for c in COLS + ["state_standard", "district_clean"]:
            if c not in df.columns:
                df[c] = np.nan if c == "value" else ""
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        self.df = df
        self._text = (df["indicator"] + " " + df["parameter"]).str.lower()
        self._states = sorted(s for s in df["state_standard"].unique() if s)
        self._districts = sorted(s for s in df["district_clean"].unique() if len(s) >= 4)
        self._indicators = sorted(df["indicator"].unique())
        self._indicator_set = set(self._indicators)
        self._indicator_lower_map = {i.lower(): i for i in self._indicators}
        self._indicators_meta_cache = None
        self._locations_cache = {}
        # Precomputed index mappings for sub-millisecond filtering across 1.18M rows
        self._state_groups = df.groupby(df["state_standard"].str.lower()).indices
        self._district_groups = df.groupby(df["district_clean"].str.lower()).indices
        self._indicator_groups = df.groupby(df["indicator"].str.lower()).indices
        self._source_groups = df.groupby(df["source"].str.lower()).indices

    def filter(self, state=None, district=None, source=None, year=None, indicator=None,
               geographic_level=None, category=None) -> pd.DataFrame:
        candidates = []
        if state and str(state).lower() in self._state_groups:
            candidates.append(self._state_groups[str(state).lower()])
        if district and str(district).lower() in self._district_groups:
            candidates.append(self._district_groups[str(district).lower()])
        if indicator and str(indicator).lower() in self._indicator_groups:
            candidates.append(self._indicator_groups[str(indicator).lower()])
        if source and str(source).lower() in self._source_groups:
            candidates.append(self._source_groups[str(source).lower()])

        if candidates:
            common_idx = candidates[0]
            for c in candidates[1:]:
                common_idx = np.intersect1d(common_idx, c, assume_unique=True)
            subset = self.df.iloc[common_idx]
            mask = pd.Series(True, index=subset.index)
            if year: mask &= subset["year"] == str(year)
            if geographic_level: mask &= subset["geographic_level"].str.lower() == str(geographic_level).lower()
            if category: mask &= subset["category"].str.contains(category, case=False, regex=False, na=False)
            return subset[mask]

        # Safe fallback for unindexed / partial wildcard queries
        d = self.df
        def has(col, val): return d[col].str.contains(val, case=False, regex=False, na=False)
        mask = pd.Series(True, index=d.index)
        if state: mask &= has("state_standard", state) | has("state", state)
        if district: mask &= has("district_clean", district) | has("district", district)
        if source: mask &= has("source", source)
        if year: mask &= d["year"] == str(year)
        if indicator: mask &= d["indicator"].str.lower() == str(indicator).lower()
        if geographic_level: mask &= d["geographic_level"].str.lower() == str(geographic_level).lower()
        if category: mask &= has("category", category)
        return d[mask]

    def detect_locations(self, question: str) -> dict:
        q = question.lower()
        detected_states = []
        for s in sorted(self._states, key=len, reverse=True):
            if re.search(rf"\b{re.escape(s.lower())}\b", q):
                if s not in detected_states:
                    detected_states.append(s)

        detected_districts = []
        for d in sorted(self._districts, key=len, reverse=True):
            if re.search(rf"\b{re.escape(d.lower())}\b", q):
                if d not in detected_districts:
                    detected_districts.append(d)

        # Check district aliases
        DISTRICT_ALIASES = {
            "bombay": "Mumbai",
            "bangalore": "Bengaluru",
            "calcutta": "Kolkata",
            "madras": "Chennai",
            "poona": "Pune",
            "baroda": "Vadodara",
            "trivandrum": "Thiruvananthapuram",
            "cochin": "Ernakulam",
            "gurgaon": "Gurugram",
        }
        for alias, target in DISTRICT_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", q):
                matched = next((d for d in self._districts if d.lower() == target.lower()), target)
                if matched not in detected_districts:
                    detected_districts.append(matched)

        # Check state aliases with word boundary checks
        STATE_ALIASES = {
            "mh": "Maharashtra",
            "up": "Uttar Pradesh",
            "mp": "Madhya Pradesh",
            "tn": "Tamil Nadu",
            "ap": "Andhra Pradesh",
            "wb": "West Bengal",
            "kl": "Kerala",
            "ka": "Karnataka",
            "gj": "Gujarat",
            "rj": "Rajasthan",
            "dl": "Delhi",
            "pb": "Punjab",
            "hr": "Haryana",
            "jh": "Jharkhand",
            "uk": "Uttarakhand",
            "ut": "Uttarakhand",
            "hp": "Himachal Pradesh",
            "ts": "Telangana",
            "orissa": "Odisha",
            "odisha": "Odisha",
            "br": "Bihar",
            "bihar": "Bihar",
            "assam": "Assam",
            "ct": "Chhattisgarh",
            "chhattisgarh": "Chhattisgarh",
            "jk": "Jammu and Kashmir",
            "j&k": "Jammu and Kashmir",
            "py": "Puducherry",
            "pondicherry": "Puducherry",
            "ga": "Goa",
        }
        for alias, target in STATE_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", q):
                matched = next((s for s in self._states if s.lower() == target.lower()), target)
                if matched not in detected_states:
                    detected_states.append(matched)

        # Case-sensitive check for two-letter state abbreviations that collide with common English words ('OR', 'AS')
        for code, target in [("OR", "Odisha"), ("AS", "Assam")]:
            if re.search(rf"\b{code}\b", question):
                matched = next((s for s in self._states if s.lower() == target.lower()), target)
                if matched not in detected_states:
                    detected_states.append(matched)

        # Check for explicitly named unknown district (e.g. "Atlantis District", "District of Atlantis")
        if not detected_districts:
            m_dist = re.search(r"\b([a-zA-Z]{3,30})\s+district\b", q)
            if not m_dist:
                m_dist = re.search(r"\bdistrict\s+(?:of\s+)?([a-zA-Z]{3,30})\b", q)
            if m_dist:
                cand = m_dist.group(1).strip().title()
                if cand.lower() not in ["which", "what", "any", "this", "each", "every", "all", "the", "selected", "reporting", "level"]:
                    detected_districts.append(cand)

        return {
            "state": detected_states[0] if detected_states else None,
            "district": detected_districts[0] if detected_districts else None,
            "all_states": detected_states,
            "all_districts": detected_districts,
        }

    def detect_filters(self, question: str) -> dict:
        q_lower = question.lower()
        locs = self.detect_locations(question)
        state = locs.get("state")
        district = locs.get("district")

        source = None
        if "nfhs-5" in q_lower or "nfhs 5" in q_lower or "nfhs5" in q_lower or "nfhs" in q_lower:
            source = "NFHS-5"
        elif "hmis" in q_lower:
            source = "HMIS"
        elif "ahs" in q_lower or "annual health survey" in q_lower:
            source = "AHS"
        elif "hospital directory" in q_lower:
            source = "Hospital Directory"

        year = None
        for yr_pattern in ["2019-2021", "2019-2020", "2019-20", "2019-21"]:
            if yr_pattern in q_lower:
                year = "2019-2021" if "2019-2" in yr_pattern or "2019-21" in yr_pattern else yr_pattern
                break
        if not year:
            four_digits = re.findall(r"\b(19\d\d|20\d\d)\b", q_lower)
            if four_digits:
                year = four_digits[0]

        geo_level = None
        if "district level" in q_lower or "district-level" in q_lower:
            geo_level = "district"
        elif "state level" in q_lower or "state-level" in q_lower:
            geo_level = "state"

        resolved_ind = self.resolve_indicator(question, source=source)

        return {
            "state": state,
            "district": district,
            "all_states": locs.get("all_states", []),
            "all_districts": locs.get("all_districts", []),
            "source": source,
            "year": year,
            "geographic_level": geo_level,
            "indicator": resolved_ind,
        }

    def classify_intent(self, question: str, detected_locations: dict | None = None) -> str:
        q_lower = question.lower()
        filters = detected_locations if (detected_locations and "source" in detected_locations) else self.detect_filters(question)
        locs = {"state": filters.get("state"), "district": filters.get("district"), "all_states": filters.get("all_states", []), "all_districts": filters.get("all_districts", [])}

        if any(k in q_lower for k in ["pmjay", "pm-jay", "ayushman", "janani", "jsy", "pmssy", "rbsk", "eligibility", "scheme"]):
            return "scheme_info"

        # 1. Evidence Summary Query
        if any(w in q_lower for w in [
            "summarize", "summarise", "summary of", "explain these results", "explain these records",
            "in simple language", "in simple terms", "plain language", "what do these numbers mean",
            "what does this number mean", "what do these statistics mean", "break this down", "simplify this", "simplify these"
        ]):
            return "evidence_summary"

        # 2. Metadata / Source Explanation Query
        if any(w in q_lower for w in [
            "what is the source", "where is this data from", "where are these records from",
            "who collected this", "how was this collected", "what reporting period is this",
            "what reporting period does this cover", "tell me about the source"
        ]):
            return "metadata_explanation"

        # 3. Sources discovery query
        if any(w in q_lower for w in ["what source", "which source", "data source", "sources available", "sources for", "sources in"]):
            return "available_sources"

        # 4. Years discovery query
        if any(w in q_lower for w in ["what year", "which year", "years available", "reporting period", "survey period", "years are available"]):
            return "available_years"

        # 5. Districts discovery query
        if any(w in q_lower for w in ["which district", "what district", "districts have records", "districts are covered", "districts available"]):
            return "available_districts"

        # 6. Indicators discovery query
        is_discovery = any(
            k in q_lower for k in [
                "available indicator", "indicator available", "indicators available",
                "indicators are available", "indicators in", "indicators for",
                "what indicator", "which indicator", "list indicator", "show indicator",
                "what data is available", "what metrics", "what variables", "what health data",
                "maternal-health indicator", "maternal health indicator", "child health indicator",
            ]
        ) or bool(re.search(r"indicators?\s+(?:are\s+)?available", q_lower)) or bool(
            re.search(r"available\s+(?:healthcare\s+|health\s+)?indicators?", q_lower)
        )
        if is_discovery and not any(k in q_lower for k in ["compare", " vs ", "trend", "rank"]):
            return "available_indicators"

        # 7. Ranking query
        if any(w in q_lower for w in [
            "top 5", "top 10", "top 3", "top district", "highest district", "lowest district",
            "bottom district", "best performing", "worst performing", "rank districts", "rank the districts",
            "which district has the highest", "which district has the lowest", "districts with highest",
            "districts with lowest", "ranking of districts"
        ]):
            return "ranking"

        # 8. Aggregation query
        if any(w in q_lower for w in [
            "average", "mean", "statewide average", "overall average", "total across", "aggregate across"
        ]) and any(w in q_lower for w in ["districts", "across", "overall", "all", "statewide", "state"]):
            return "aggregation"

        # 9. Comparison query
        is_compare = any(k in q_lower for k in ["compare", " vs ", " versus ", "difference between", "higher than", "lower than"]) or (
            len(locs.get("all_districts", [])) >= 2 or len(locs.get("all_states", [])) >= 2
        )
        if is_compare:
            return "comparison"

        # 10. Trend query
        is_trend = any(k in q_lower for k in ["trend", "over time", "progress", "growth", "annual", "change over", "historical"])
        if is_trend:
            return "trend"

        if locs.get("district"):
            return "district_lookup"
        if locs.get("state"):
            return "state_lookup"

        return "exact_statistic"

    def retrieve(self, query: str, state=None, district=None, source=None, year=None,
                 indicator=None, limit: int = 8, intent: str | None = None,
                 all_locations: list[str] | None = None) -> pd.DataFrame:
        query_lower = query.lower()

        # 1. Handle Sources Discovery
        if intent == "available_sources":
            base = self.filter(state=state, district=district)
            if not base.empty:
                sampled_rows = []
                for _, grp in base.groupby("source", sort=False):
                    sampled_rows.append(grp.iloc[0])
                if sampled_rows:
                    return pd.DataFrame(sampled_rows).head(limit)

        # 2. Handle Years / Reporting Periods Discovery
        if intent == "available_years":
            ind_val = indicator or self.resolve_indicator(query, source=source)
            base = self.filter(state=state, district=district, indicator=ind_val)
            if not base.empty:
                return base.drop_duplicates(subset=["source", "year"]).head(limit)

        # 3. Handle Districts Coverage Discovery
        if intent == "available_districts":
            ind_val = indicator or self.resolve_indicator(query, source=source)
            base = self.filter(state=state, indicator=ind_val)
            if not base.empty:
                valid_dist = base[base["district_clean"] != ""].drop_duplicates(subset=["district_clean"])
                if not valid_dist.empty:
                    return valid_dist.head(max(limit, 20))

        # 4. Handle Indicator Discovery Queries (e.g. "What healthcare indicators are available for Maharashtra?")
        is_discovery = (intent == "available_indicators") or any(
            p in query_lower for p in ["available indicators", "what indicators", "which indicators", "list indicators"]
        )
        if is_discovery:
            base = self.filter(state=state, district=district, source=source, year=year)
            if not base.empty:
                sampled_rows = []
                if not district and state:
                    # Collect key indicators across sources without binding to a single district
                    # 1. State-level records (e.g. HMIS)
                    state_recs = base[(base["geographic_level"] == "state") | (base["district_clean"] == "") | (base["district"].isna())]
                    for _, grp in state_recs.groupby("indicator", sort=False):
                        non_null = grp[grp["value"].notna()]
                        sampled_rows.append(non_null.iloc[0] if not non_null.empty else grp.iloc[0])
                        if len(sampled_rows) >= 6:
                            break
                    # 2. Representative indicators from district surveys (e.g. NFHS-5) across the state
                    dist_recs = base[base["geographic_level"] == "district"]
                    if not dist_recs.empty:
                        for _, grp in dist_recs.groupby("indicator", sort=False):
                            non_null = grp[grp["value"].notna()]
                            row = (non_null.iloc[0] if not non_null.empty else grp.iloc[0]).copy()
                            # Ensure state-level discovery presents this as statewide survey coverage
                            row["district"] = ""
                            row["district_clean"] = ""
                            row["geographic_level"] = "state"
                            row["state"] = state
                            row["state_standard"] = state
                            sampled_rows.append(row)
                            if len(sampled_rows) >= max(limit, 12):
                                break
                else:
                    for _, grp in base.groupby("indicator", sort=False):
                        non_null = grp[grp["value"].notna()]
                        sampled_rows.append(non_null.iloc[0] if not non_null.empty else grp.iloc[0])
                        if len(sampled_rows) >= max(limit, 10):
                            break
                if sampled_rows:
                    return pd.DataFrame(sampled_rows).head(limit)

        # 5. Handle Rankings (e.g. top 5 districts in Maharashtra)
        if intent == "ranking":
            ind_val = indicator or self.resolve_indicator(query, source=source)
            base = self.filter(state=state, source=source, year=year, indicator=ind_val)
            if not base.empty:
                dist_base = base[(base["district_clean"] != "") & (base["value"].notna())].drop_duplicates(subset=["district_clean"])
                is_ascending = any(k in query_lower for k in ["lowest", "bottom", "least", "worst", "smallest"])
                sorted_dist = dist_base.sort_values("value", ascending=is_ascending)
                return sorted_dist.head(limit or 5)

        # 6. Handle Aggregations (e.g. average across districts)
        if intent == "aggregation":
            ind_val = indicator or self.resolve_indicator(query, source=source)
            base = self.filter(state=state, source=source, year=year, indicator=ind_val)
            if not base.empty:
                dist_base = base[(base["district_clean"] != "") & (base["value"].notna())].drop_duplicates(subset=["district_clean"])
                return dist_base

        # 7. Handle Comparisons across Multiple Locations (e.g. Pune vs Nashik)
        if all_locations and len(all_locations) >= 2:
            d = self.df
            loc_masks = []
            for loc in all_locations:
                loc_masks.append(
                    (d["district_clean"].str.lower() == loc.lower()) |
                    (d["state_standard"].str.lower() == loc.lower()) |
                    (d["district"].str.lower() == loc.lower()) |
                    (d["state"].str.lower() == loc.lower())
                )
            combined_loc_mask = pd.Series(False, index=d.index)
            for m in loc_masks:
                combined_loc_mask |= m
            base = d[combined_loc_mask]
            if source:
                base = base[base["source"].str.contains(source, case=False, regex=False, na=False)]
            if year:
                base = base[base["year"] == str(year)]
            if indicator:
                base = base[base["indicator"].str.lower() == str(indicator).lower()]
        else:
            base = self.filter(state, district, source, year, indicator)

        if base.empty:
            return base

        # 8. Direct indicator resolution
        resolved_ind = self.resolve_indicator(indicator or query, source=source)
        if resolved_ind:
            ind_base = base[base["indicator"] == resolved_ind]
            if not ind_base.empty:
                return ind_base.sort_values("year", ascending=False).head(limit)

        # 9. Keyword search scoring
        terms = [t for t in re.findall(r"[a-z0-9]+", query_lower) if len(t) >= 3 and t not in STOP]
        if not terms:
            return base.head(limit) if resolved_ind else base.head(0)

        text = self._text.loc[base.index]
        score = pd.Series(0, index=base.index, dtype="int64")
        for t in terms:
            score += text.str.contains(t, regex=False, na=False).astype("int64")

        min_score = 2 if len(terms) >= 3 else 1
        hit = base.loc[score >= min_score].assign(_s=score[score >= min_score]).sort_values(["_s", "year"], ascending=[False, False])
        return hit.drop(columns="_s").head(limit)

    def explorer_query(
        self,
        q: str = "",
        state: str | None = None,
        district: str | None = None,
        year: str | None = None,
        source: str | None = None,
        indicator: str | None = None,
        geographic_level: str | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "year",
        sort_order: str = "desc",
    ) -> dict:
        base = self.filter(state, district, source, year, indicator, geographic_level, category)
        if q and q.strip():
            terms = [t for t in re.findall(r"[a-z0-9]+", q.lower()) if len(t) >= 2 and t not in STOP]
            if terms:
                text = self._text.loc[base.index]
                score = pd.Series(0, index=base.index, dtype="int64")
                for t in terms:
                    score += text.str.contains(t, regex=False, na=False).astype("int64")
                base = base.loc[score > 0].assign(_s=score[score > 0]).sort_values("_s", ascending=False).drop(columns="_s")
            else:
                base = base.head(0)

        total_records = len(base)
        page_size = max(1, min(100, page_size))
        total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
        page = max(1, min(page, total_pages))

        # Safe sorting if user provided a valid column
        valid_cols = [c for c in COLS if c in base.columns]
        if sort_by in valid_cols and (not q or not q.strip()):
            ascending = sort_order.lower() == "asc"
            base = base.sort_values(sort_by, ascending=ascending, na_position="last")

        offset = (page - 1) * page_size
        slice_df = base.iloc[offset : offset + page_size]

        return {
            "total_records": int(total_records),
            "page": int(page),
            "page_size": int(page_size),
            "total_pages": int(total_pages),
            "records": self.to_records(slice_df),
        }

    def resolve_indicator(self, ind_query: str, source: str | None = None) -> str | None:
        """Resolves user or friendly indicator query to a canonical dataset indicator."""
        if not ind_query or not str(ind_query).strip():
            return None
        
        q = str(ind_query).strip()
        q_lower = q.lower()
        
        # 1. Exact match
        if q in self._indicator_set:
            return q
        
        # 2. Case-insensitive exact match
        if q_lower in self._indicator_lower_map:
            return self._indicator_lower_map[q_lower]

        # 2b. Source-specific canonical aliases (e.g. HMIS)
        if source and str(source).upper() == "HMIS":
            HMIS_ALIASES = {
                "institutional deliveries conducted": "M2 [Deliveries]",
                "institutional deliveries": "M2 [Deliveries]",
                "institutional delivery": "M2 [Deliveries]",
                "institutional births": "M2 [Deliveries]",
                "institutional birth": "M2 [Deliveries]",
                "deliveries": "M2 [Deliveries]",
                "delivery": "M2 [Deliveries]",
                "caesarean section in public facility": "M3 [Number of Caesarean (C-Section) deliveries]",
                "caesarean section in private facility": "M3 [Number of Caesarean (C-Section) deliveries]",
                "number of caesarean deliveries": "M3 [Number of Caesarean (C-Section) deliveries]",
                "number of caesarean": "M3 [Number of Caesarean (C-Section) deliveries]",
                "caesarean deliveries": "M3 [Number of Caesarean (C-Section) deliveries]",
                "caesarean delivery": "M3 [Number of Caesarean (C-Section) deliveries]",
                "caesarean section": "M3 [Number of Caesarean (C-Section) deliveries]",
                "caesarean births": "M3 [Number of Caesarean (C-Section) deliveries]",
                "caesarean": "M3 [Number of Caesarean (C-Section) deliveries]",
                "c section deliveries": "M3 [Number of Caesarean (C-Section) deliveries]",
                "c section delivery": "M3 [Number of Caesarean (C-Section) deliveries]",
                "c-section deliveries": "M3 [Number of Caesarean (C-Section) deliveries]",
                "c-section delivery": "M3 [Number of Caesarean (C-Section) deliveries]",
                "c section": "M3 [Number of Caesarean (C-Section) deliveries]",
                "c-section": "M3 [Number of Caesarean (C-Section) deliveries]",
            }
            for alias in sorted(HMIS_ALIASES.keys(), key=len, reverse=True):
                if re.search(rf"\b{re.escape(alias)}\b", q_lower):
                    target = HMIS_ALIASES[alias]
                    if target in self._indicator_set:
                        return target
        
        # 3. Known canonical aliases (NFHS-5, AHS, cross-dataset)
        ALIASES = {
            # Caesarean / C-Section
            "c section deliveries": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "c section delivery": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "c section births": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "c section": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "c-section deliveries": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "c-section delivery": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "c-section births": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "c-section": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "caesarean section in public facility": "births_in_a_public_health_facility_that_were_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "caesarean section in private facility": "births_in_a_private_health_facility_that_were_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "caesarean section": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "caesarean deliveries": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "caesarean delivery": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "caesarean births": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "caesarean": "births_delivered_by_caesarean_section_in_the_5_years_before_the_survey_percent",
            "number of caesarean deliveries": "M3 [Number of Caesarean (C-Section) deliveries]",
            "number of caesarean": "M3 [Number of Caesarean (C-Section) deliveries]",

            # Institutional Births / Deliveries
            "institutional births (%)": "institutional_births_in_the_5_years_before_the_survey_percent",
            "institutional births": "institutional_births_in_the_5_years_before_the_survey_percent",
            "institutional delivery": "institutional_births_in_the_5_years_before_the_survey_percent",
            "institutional deliveries": "institutional_births_in_the_5_years_before_the_survey_percent",
            "institutional deliveries conducted": "institutional_births_in_the_5_years_before_the_survey_percent",
            "institutional births in public facility": "institutional_births_in_public_facility_in_the_5_years_before_the_survey_percent",
            "institutional delivery in public facility": "institutional_births_in_public_facility_in_the_5_years_before_the_survey_percent",

            # Nutrition: Stunting, Wasting, Underweight
            "stunting in children": "children_under_5_years_who_are_stunted_height_for_age18_percent",
            "stunted children": "children_under_5_years_who_are_stunted_height_for_age18_percent",
            "child stunting": "children_under_5_years_who_are_stunted_height_for_age18_percent",
            "stunting": "children_under_5_years_who_are_stunted_height_for_age18_percent",
            "stunted": "children_under_5_years_who_are_stunted_height_for_age18_percent",
            "wasting in children": "children_under_5_years_who_are_wasted_weight_for_height18_percent",
            "wasted children": "children_under_5_years_who_are_wasted_weight_for_height18_percent",
            "child wasting": "children_under_5_years_who_are_wasted_weight_for_height18_percent",
            "wasting": "children_under_5_years_who_are_wasted_weight_for_height18_percent",
            "wasted": "children_under_5_years_who_are_wasted_weight_for_height18_percent",
            "severely wasted children": "children_under_5_years_who_are_severely_wasted_weight_for_height19_percent",
            "severe wasting": "children_under_5_years_who_are_severely_wasted_weight_for_height19_percent",
            "underweight in children": "children_under_5_years_who_are_underweight_weight_for_age18_percent",
            "underweight children": "children_under_5_years_who_are_underweight_weight_for_age18_percent",
            "child underweight": "children_under_5_years_who_are_underweight_weight_for_age18_percent",
            "underweight": "children_under_5_years_who_are_underweight_weight_for_age18_percent",

            # Anaemia
            "anaemia in pregnant women": "pregnant_women_age_15_49_years_who_are_anaemic_<11.0_g_dl22_percent",
            "anemia in pregnant women": "pregnant_women_age_15_49_years_who_are_anaemic_<11.0_g_dl22_percent",
            "pregnant women anaemic": "pregnant_women_age_15_49_years_who_are_anaemic_<11.0_g_dl22_percent",
            "pregnant women anemia": "pregnant_women_age_15_49_years_who_are_anaemic_<11.0_g_dl22_percent",
            "anaemia in pregnancy": "pregnant_women_age_15_49_years_who_are_anaemic_<11.0_g_dl22_percent",
            "anemia in pregnancy": "pregnant_women_age_15_49_years_who_are_anaemic_<11.0_g_dl22_percent",
            "anaemia in children": "children_age_6_59_months_who_are_anaemic_<11.0_g_dl22_percent",
            "anemia in children": "children_age_6_59_months_who_are_anaemic_<11.0_g_dl22_percent",
            "child anaemia": "children_age_6_59_months_who_are_anaemic_<11.0_g_dl22_percent",
            "child anemia": "children_age_6_59_months_who_are_anaemic_<11.0_g_dl22_percent",
            "women anaemic": "all_women_age_15_49_years_who_are_anaemic22_percent",
            "women anemia": "all_women_age_15_49_years_who_are_anaemic22_percent",
            "anaemia in women": "all_women_age_15_49_years_who_are_anaemic22_percent",
            "anemia in women": "all_women_age_15_49_years_who_are_anaemic22_percent",
            "anaemia": "all_women_age_15_49_years_who_are_anaemic22_percent",
            "anemia": "all_women_age_15_49_years_who_are_anaemic22_percent",

            # Immunization
            "full immunization": "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mother's_recall11_percent",
            "fully vaccinated": "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mother's_recall11_percent",
            "child immunization": "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mother's_recall11_percent",
            "child vaccination": "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mother's_recall11_percent",
            "immunization": "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mother's_recall11_percent",
            "polio vaccine": "children_age_12_23_months_who_have_received_3_doses_of_polio_vaccine13_percent",
            "measles vaccine": "children_age_12_23_months_who_have_received_the_first_dose_of_measles_containing_vaccine_mcv_percent",
            "dpt vaccine": "children_age_12_23_months_who_have_received_3_doses_of_penta_or_dpt_vaccine_percent",
            "hepatitis b vaccine": "children_age_12_23_months_who_have_received_3_doses_of_penta_or_hepatitis_b_vaccine_percent",

            # Maternal Health & Sex Ratio
            "maternal health": "mothers_who_had_at_least_4_antenatal_care_visits__for_last_birth_in_the_5_years_before_the_survey_percent",
            "antenatal care": "mothers_who_had_at_least_4_antenatal_care_visits__for_last_birth_in_the_5_years_before_the_survey_percent",
            "anc visits": "mothers_who_had_at_least_4_antenatal_care_visits__for_last_birth_in_the_5_years_before_the_survey_percent",
            "4 anc visits": "mothers_who_had_at_least_4_antenatal_care_visits__for_last_birth_in_the_5_years_before_the_survey_percent",
            "sex ratio at birth": "sex_ratio_at_birth_for_children_born_in_the_last_five_years_females_per_1,000_males",
            "sex ratio": "sex_ratio_at_birth_for_children_born_in_the_last_five_years_females_per_1,000_males",

            # Household Amenities
            "electricity": "population_living_in_households_with_electricity_percent",
            "clean fuel": "households_using_clean_fuel_for_cooking3_percent",
            "cooking fuel": "households_using_clean_fuel_for_cooking3_percent",
            "drinking water": "population_living_in_households_with_an_improved_drinking_water_source1_percent",
            "improved drinking water": "population_living_in_households_with_an_improved_drinking_water_source1_percent",
            "sanitation": "population_living_in_households_that_use_an_improved_sanitation_facility2_percent",
            "improved sanitation": "population_living_in_households_that_use_an_improved_sanitation_facility2_percent",
            "iodized salt": "households_using_iodized_salt_percent",
            "households surveyed": "number_of_households_surveyed",
            "women interviewed": "number_of_women_age_15_49_years_interviewed",
            "men interviewed": "number_of_men_age_15_54_years_interviewed",
        }

        # Match aliases sorted by length descending using strict word boundaries
        for alias in sorted(ALIASES.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", q_lower):
                target = ALIASES[alias]
                if target in self._indicator_set:
                    return target
        
        # 4. Normalized match (remove punctuation/percent, replace spaces with underscores)
        norm = re.sub(r"[()%,]", "", q_lower).strip()
        norm_underscored = re.sub(r"[\s\-]+", "_", norm)
        if norm_underscored in self._indicator_set:
            return norm_underscored
        if norm_underscored in self._indicator_lower_map:
            return self._indicator_lower_map[norm_underscored]
        if f"{norm_underscored}_percent" in self._indicator_set:
            return f"{norm_underscored}_percent"
        
        # 5. Keyword match across all indicator names
        terms = [t for t in re.findall(r"[a-z0-9]+", q_lower) if len(t) >= 3 and t not in STOP]
        if terms:
            best_match = None
            best_score = 0
            for ind in self._indicators:
                ind_clean = ind.lower().replace("_", " ")
                score = sum(1 for t in terms if t in ind_clean)
                if score > best_score:
                    best_score = score
                    best_match = ind
            if best_match and best_score >= max(1, len(terms) // 2):
                return best_match
        
        return None

    def indicators_meta(self) -> list[dict]:
        """Returns structured metadata for all indicators with human-friendly labels and available cycles."""
        if self._indicators_meta_cache is not None:
            return self._indicators_meta_cache
        
        d = self.df
        meta_list = []
        for ind, grp in d.groupby("indicator"):
            if not ind:
                continue
            first_row = grp.iloc[0]
            src = str(first_row.get("source", ""))
            itype = str(first_row.get("indicator_type", "other"))
            cat = str(first_row.get("category", ""))
            years = sorted(set(y for y in grp["year"].unique() if y), reverse=True)
            geo_levels = sorted(set(g for g in grp["geographic_level"].unique() if g))
            
            clean_name = ind.replace("_", " ").strip()
            unit = "%"
            if itype == "percentage" or "_percent" in ind:
                unit = "%"
                label = clean_name.replace(" percent", "").title() + " (%)"
            elif "ratio_per_1000" in itype or "per_1,000" in ind:
                unit = "per 1,000"
                label = clean_name.title()
            elif itype == "count":
                unit = "count"
                label = clean_name.title()
            elif itype == "rate":
                unit = "rate"
                label = clean_name.title()
            else:
                unit = "value"
                label = clean_name.title()
            
            meta_list.append({
                "indicator": ind,
                "label": label,
                "indicator_type": itype,
                "unit": unit,
                "source": src,
                "category": cat,
                "years": years,
                "geographic_levels": geo_levels,
                "records_count": int(len(grp)),
            })
        
        meta_list.sort(key=lambda x: x["records_count"], reverse=True)
        self._indicators_meta_cache = meta_list
        return meta_list

    def locations_list(self, scope: str = "district") -> list[dict]:
        """Returns verified locations list for a given geographic scope."""
        scope_key = scope.lower().strip()
        if scope_key in self._locations_cache:
            return self._locations_cache[scope_key]
        
        d = self.df
        if scope_key == "state":
            states = sorted(s for s in d["state_standard"].unique() if s)
            res = [{"id": s, "name": s, "state": s, "label": s} for s in states]
        else:
            sub = d[d["district_clean"] != ""][["district_clean", "state_standard"]].drop_duplicates().sort_values("district_clean")
            res = []
            for _, r in sub.iterrows():
                dist = r["district_clean"]
                st = r["state_standard"]
                label = f"{dist} ({st})" if st else dist
                res.append({
                    "id": dist,
                    "name": dist,
                    "state": st,
                    "label": label,
                })
        
        self._locations_cache[scope_key] = res
        return res

    def workspace_compare(
        self,
        indicator: str,
        locations: list[str],
        year: str | None = None,
        source: str | None = None,
        geographic_scope: str | None = "district",
    ) -> dict:
        import hashlib
        canonical_ind = self.resolve_indicator(indicator)
        if not canonical_ind:
            return {
                "indicator": indicator,
                "canonical_indicator": None,
                "found": False,
                "records": [],
                "matched_locations": [],
                "missing_locations": locations,
                "statistics": None,
                "methodology": f"The indicator '{indicator}' could not be matched to verified records in this public health dataset.",
                "reproducibility_signature": "SIG-UNRESOLVED-INDICATOR",
            }

        d = self.df
        ind_rows = d[d["indicator"] == canonical_ind]
        available_years = sorted(set(y for y in ind_rows["year"].unique() if y), reverse=True)
        available_sources = sorted(set(s for s in ind_rows["source"].unique() if s))
        
        active_year = year
        methodology_notes = []

        # If user picked a year that does not exist for this indicator, explain and resolve to available cycle
        if year and str(year).strip():
            year_str = str(year).strip()
            if available_years and year_str not in available_years:
                active_year = available_years[0]
                methodology_notes.append(
                    f"Note: Indicator '{canonical_ind}' is indexed under reporting cycle '{active_year}' (no records exist under requested cycle '{year_str}')."
                )
            else:
                active_year = year_str
        elif available_years:
            active_year = available_years[0]

        active_source = source
        if source and str(source).strip() and available_sources:
            src_str = str(source).strip()
            matched_src = [s for s in available_sources if s.lower() == src_str.lower()]
            if not matched_src:
                active_source = available_sources[0]
                methodology_notes.append(
                    f"Note: Indicator '{canonical_ind}' is sourced from '{active_source}' (not '{src_str}')."
                )
            else:
                active_source = matched_src[0]

        mask = d["indicator"] == canonical_ind
        if year and str(year).strip() and active_year:
            mask &= d["year"] == str(active_year)
        if active_source:
            mask &= d["source"].str.lower() == str(active_source).lower()

        sub = d[mask]
        matched_rows = []
        matched_locs = []
        missing_locs = []

        for loc in locations:
            loc_clean = loc.strip().lower()
            if not loc_clean:
                continue
            
            # Match district or state
            loc_match = sub[
                (sub["district_clean"].str.lower() == loc_clean) |
                (sub["district"].str.lower() == loc_clean) |
                (sub["state_standard"].str.lower() == loc_clean) |
                (sub["state"].str.lower() == loc_clean) |
                sub["district_clean"].str.lower().str.contains(loc_clean, regex=False, na=False) |
                sub["state_standard"].str.lower().str.contains(loc_clean, regex=False, na=False)
            ]

            if not loc_match.empty:
                # Prioritize valid numeric observation over null
                loc_match_sorted = loc_match.sort_values(by=["value"], ascending=False, na_position="last")
                top_row = loc_match_sorted.iloc[0]
                matched_rows.append(top_row)
                matched_locs.append(loc)
            else:
                missing_locs.append(loc)

        if not matched_rows:
            return {
                "indicator": indicator,
                "canonical_indicator": canonical_ind,
                "found": False,
                "year": active_year,
                "available_years": available_years,
                "source": active_source,
                "available_sources": available_sources,
                "records": [],
                "matched_locations": [],
                "missing_locations": locations,
                "statistics": None,
                "methodology": f"No matching observations found for '{canonical_ind}' in cycle '{active_year}' for requested locations: {', '.join(locations)}.",
                "reproducibility_signature": "SIG-EMPTY-RESULT",
            }

        comp_df = pd.DataFrame(matched_rows)
        numeric_vals = [float(v) for v in comp_df["value"].dropna().tolist() if isinstance(v, (int, float, np.number))]

        stats = None
        if numeric_vals:
            stats = {
                "count": len(numeric_vals),
                "min": float(round(float(np.min(numeric_vals)), 2)),
                "max": float(round(float(np.max(numeric_vals)), 2)),
                "mean": float(round(float(np.mean(numeric_vals)), 2)),
                "median": float(round(float(np.median(numeric_vals)), 2)),
                "range": float(round(float(np.max(numeric_vals) - np.min(numeric_vals)), 2)),
            }

        # Format records for frontend
        formatted_records = []
        first_row = comp_df.iloc[0]
        ind_type = str(first_row.get("indicator_type", "other"))
        clean_label = canonical_ind.replace("_", " ").title()
        unit = "%" if ind_type == "percentage" or "_percent" in canonical_ind else ("per 1,000" if "ratio_per_1000" in ind_type else "count")

        for idx, row in comp_df.iterrows():
            loc_name = str(row.get("district_clean") or row.get("district") or row.get("state_standard") or row.get("state") or f"Location {idx}")
            st_name = str(row.get("state_standard") or row.get("state") or "")
            ev_id = f"ev_{hashlib.md5(f'{loc_name}_{canonical_ind}_{active_year}'.encode()).hexdigest()[:8]}"
            formatted_records.append({
                "location": loc_name,
                "state": st_name,
                "district": str(row.get("district_clean") or row.get("district") or ""),
                "indicator": canonical_ind,
                "display_label": clean_label,
                "value": float(row["value"]) if pd.notna(row["value"]) else None,
                "indicator_type": ind_type,
                "unit": unit,
                "year": str(row.get("year", active_year or "")),
                "source": str(row.get("source", active_source or "")),
                "geographic_level": str(row.get("geographic_level", "district")),
                "parameter": str(row.get("parameter", "")),
                "category": str(row.get("category", "")),
                "evidence_id": ev_id,
            })

        # Canonical reproducibility signature
        query_sig_payload = f"{canonical_ind}|{active_year}|{active_source}|{','.join(sorted(matched_locs))}"
        sig_hash = hashlib.sha256(query_sig_payload.encode()).hexdigest()[:16]
        reproducibility_sig = f"INFOMED-QUERY-{sig_hash.upper()}"

        methodology_text = (
            f"Deterministic comparative extraction of '{canonical_ind}' across {len(matched_rows)} verified location observations. "
            f"Sourced from {active_source or 'official healthcare reporting systems'} ({active_year or 'primary reporting cycle'}). "
            f"Values are unweighted district observations recorded directly in source reporting partitions."
        )
        if methodology_notes:
            methodology_text += " " + " ".join(methodology_notes)

        return {
            "indicator": canonical_ind,
            "canonical_indicator": canonical_ind,
            "display_label": clean_label,
            "found": True,
            "year": active_year,
            "available_years": available_years,
            "source": active_source,
            "available_sources": available_sources,
            "records": formatted_records,
            "matched_locations": matched_locs,
            "missing_locations": missing_locs,
            "statistics": stats,
            "methodology": methodology_text,
            "reproducibility_signature": reproducibility_sig,
        }

    @staticmethod
    def to_records(df: pd.DataFrame) -> list[dict]:
        sub = df[[c for c in COLS if c in df.columns]]
        return sub.astype(object).where(sub.notna(), None).to_dict("records")

    def stats(self) -> dict:
        d = self.df
        years = sorted(y for y in d["year"].unique() if y)
        return {
            "total_records": int(len(d)),
            "indicators": int(d["indicator"].nunique()),
            "states": int(d.loc[d["state_standard"] != "", "state_standard"].nunique()),
            "districts": int(d.loc[d["district_clean"] != "", "district_clean"].nunique()),
            "year_min": years[0] if years else None,
            "year_max": years[-1] if years else None,
            "sources": {k: int(v) for k, v in d["source"].value_counts().items()},
        }

    def filters(self, state=None) -> dict:
        d = self.df if not state else self.filter(state=state)
        return {
            "states": self._states,
            "districts": sorted(s for s in d["district_clean"].unique() if s),
            "years": sorted(y for y in self.df["year"].unique() if y),
            "sources": sorted(s for s in self.df["source"].unique() if s),
        }

    def indicators(self, q: str | None = None, limit: int = 500) -> list[str]:
        vals = sorted(self.df["indicator"].unique())
        if q: vals = [v for v in vals if q.lower() in v.lower()]
        return vals[:limit]
