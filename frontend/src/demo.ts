// DEMO DATA: invented placeholder values used ONLY to demonstrate the interface in demo mode.
// They are NOT real healthcare statistics. Live mode uses your actual dataset via the backend.
import type {
  ExplorerQuery,
  ExplorerResponse,
  Filters,
  HealthRecord,
  Query,
  Scheme,
  Stats,
  WorkspaceCompareRequest,
  WorkspaceCompareResponse,
} from "./types";

const rows: [string, string, string, string, number][] = [
  ["State A", "District 1", "2019", "Institutional births (%)", 70],
  ["State A", "District 1", "2020", "Institutional births (%)", 74],
  ["State A", "District 1", "2021", "Institutional births (%)", 79],
  ["State A", "District 2", "2020", "Institutional births (%)", 65],
  ["State A", "District 2", "2021", "Institutional births (%)", 69],
  ["State B", "District 3", "2020", "Institutional births (%)", 82],
  ["State B", "District 3", "2021", "Institutional births (%)", 85],
  ["State B", "District 4", "2020", "Anaemia in pregnancy (%)", 41],
  ["State B", "District 4", "2021", "Anaemia in pregnancy (%)", 38],
];
export const DEMO_ROWS: HealthRecord[] = rows.map(([state, district, year, indicator, value]) => ({
  state, district, year, indicator, value, source: "DEMO SAMPLE (not real)",
}));

export function demoQuery(q: Query): HealthRecord[] {
  const words = (q.q ?? "").toLowerCase().split(/\W+/).filter((w) => w.length > 2);
  return DEMO_ROWS.filter(
    (r) =>
      (!q.state || r.state === q.state) && (!q.district || r.district === q.district) &&
      (!q.year || r.year === q.year) && (!q.indicator || r.indicator === q.indicator) &&
      (!words.length || words.some((w) => (r.indicator + " " + r.district + " " + r.state).toLowerCase().includes(w))),
  );
}
export function computeStats(rs: HealthRecord[]): Stats {
  const u = (f: (r: HealthRecord) => string | null) => [...new Set(rs.map(f).filter(Boolean))] as string[];
  const years = u((r) => r.year).sort();
  return { total_records: rs.length, indicators: u((r) => r.indicator).length, states: u((r) => r.state).length,
    districts: u((r) => r.district).length, year_min: years[0] ?? null, year_max: years.at(-1) ?? null };
}
export function demoFilters(): Filters {
  const u = (f: (r: HealthRecord) => string | null) => ([...new Set(DEMO_ROWS.map(f).filter(Boolean))] as string[]).sort();
  return { states: u((r) => r.state), districts: u((r) => r.district), years: u((r) => r.year), sources: [] };
}

export const DEMO_INDICATORS = [...new Set(DEMO_ROWS.map((r) => r.indicator))];

export function demoExplorer(q: ExplorerQuery): ExplorerResponse {
  const filtered = demoQuery(q);
  const total = filtered.length;
  const page_size = q.page_size || 25;
  const total_pages = Math.max(1, Math.ceil(total / page_size));
  const page = Math.max(1, Math.min(q.page || 1, total_pages));
  const offset = (page - 1) * page_size;
  return {
    total_records: total,
    page,
    page_size,
    total_pages,
    records: filtered.slice(offset, offset + page_size),
  };
}

export function demoWorkspaceCompare(body: WorkspaceCompareRequest): WorkspaceCompareResponse {
  const matched = DEMO_ROWS.filter(
    (r) =>
      r.indicator.toLowerCase() === body.indicator.toLowerCase() &&
      body.locations.some((l) => r.district.toLowerCase().includes(l.toLowerCase()) || r.state.toLowerCase().includes(l.toLowerCase()))
  );
  const vals = matched.map((r) => r.value).filter((v): v is number => typeof v === "number");
  const matchedLocs = body.locations.filter((l) => matched.some((r) => r.district.toLowerCase().includes(l.toLowerCase()) || r.state.toLowerCase().includes(l.toLowerCase())));
  const missingLocs = body.locations.filter((l) => !matchedLocs.includes(l));
  return {
    indicator: body.indicator,
    canonical_indicator: body.indicator,
    display_label: body.indicator.replace(/_/g, " "),
    found: matched.length > 0,
    records: matched,
    matched_locations: matchedLocs,
    missing_locations: missingLocs,
    year: body.year || "2021",
    available_years: ["2021", "2020"],
    source: body.source || "NFHS-5",
    available_sources: ["NFHS-5", "HMIS"],
    statistics: vals.length
      ? {
          count: vals.length,
          min: Math.min(...vals),
          max: Math.max(...vals),
          mean: +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2),
          median: vals.sort((a, b) => a - b)[Math.floor(vals.length / 2)],
          range: +(Math.max(...vals) - Math.min(...vals)).toFixed(2),
        }
      : null,
    methodology: "Simulated deterministic comparative extraction for demonstration purposes.",
    reproducibility_signature: "SARTHI-QUERY-DEMO-SIMULATED",
  };
}

export const DEMO_SCHEMES: Scheme[] = [
  {
    id: "pmjay",
    name: "Ayushman Bharat Pradhan Mantri Jan Arogya Yojana (PM-JAY)",
    official_url: "https://pmjay.gov.in",
    authority: "National Health Authority (NHA) / MoHFW",
    summary: "Flagship health assurance scheme providing a health cover of ₹5 lakh per family per year for secondary and tertiary care hospitalisation.",
    eligibility: "Bottom 40% vulnerable population identified through Socio-Economic Caste Census (SECC 2011).",
    benefits: "Cashless and paperless access to services across 28,000+ empanelled public and private hospitals nationwide.",
    how_to_apply: "Verification via official portal (mera.pmjay.gov.in) or at any empanelled hospital with Aadhaar and Ration Card.",
    last_verified: "2024-04-15",
  },
  {
    id: "pmsma",
    name: "Pradhan Mantri Surakshit Matritva Abhiyan (PMSMA)",
    official_url: "https://pmsma.mohfw.gov.in",
    authority: "Ministry of Health and Family Welfare (MoHFW)",
    summary: "National initiative guaranteeing assured, comprehensive and quality antenatal care free of cost to all pregnant women on the 9th of every month.",
    eligibility: "All pregnant women in their 2nd or 3rd trimesters visiting designated public health facilities.",
    benefits: "Minimum package of antenatal care services including specialist consultation, sonography, and blood diagnostics.",
    how_to_apply: "Walk-in registration on the 9th of each month at any designated PHC, CHC, or District Hospital.",
    last_verified: "2024-03-20",
  },
  {
    id: "jsy",
    name: "Janani Suraksha Yojana (JSY)",
    official_url: "https://nhm.gov.in",
    authority: "National Health Mission (NHM) / MoHFW",
    summary: "Safe motherhood intervention promoting institutional delivery among poor pregnant women through conditional cash transfers.",
    eligibility: "All pregnant women delivering in government health centres or accredited private facilities.",
    benefits: "Cash assistance ranging from ₹1,000 to ₹1,400 for rural mothers upon institutional delivery.",
    how_to_apply: "Registration at nearest Anganwadi centre or Sub-centre during early pregnancy.",
    last_verified: "2024-02-10",
  },
];

