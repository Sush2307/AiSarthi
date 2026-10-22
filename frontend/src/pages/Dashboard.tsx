import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  Calendar,
  Database,
  Download,
  Filter,
  LineChart as LineChartIcon,
  Loader2,
  MapPin,
  RotateCcw,
  Search,
  Layers,
} from "lucide-react";
import { api } from "../api";
import { useApi } from "../context";
import { DEMO_INDICATORS, DEMO_ROWS, computeStats, demoFilters, demoQuery } from "../demo";
import type { Filters, HealthRecord, Query, Stats } from "../types";
import { CompareBar, RecordsTable, TrendLine, exportCsv } from "../components/common";

export default function Dashboard() {
  const { live, checking } = useApi();
  const [q, setQ] = useState<Query>({ limit: 500 });
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<HealthRecord[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [filters, setFilters] = useState<Filters>({
    states: [],
    districts: [],
    years: [],
    sources: [],
  });
  const [inds, setInds] = useState<string[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState("");

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => {
      setQ((p) => ({ ...p, q: search || undefined }));
    }, 350);
    return () => clearTimeout(t);
  }, [search]);

  // Load stats, filters, and indicators once connected
  useEffect(() => {
    if (checking) return;
    if (!live) {
      setStats(computeStats(DEMO_ROWS));
      setFilters(demoFilters());
      setInds(DEMO_INDICATORS);
      return;
    }
    Promise.all([api.stats(), api.filters(), api.indicators(), api.analyticsModules().catch(() => null)])
      .then(([s, f, i, m]) => {
        setStats(s);
        setFilters(f);
        setInds(i.indicators);
        if (m) setAnalyticsMeta(m);
      })
      .catch((e) => setErr((e as Error).message));
  }, [live, checking]);

  const [activeTab, setActiveTab] = useState<"visual" | "quality" | "sources">("visual");
  const [analyticsMeta, setAnalyticsMeta] = useState<any>(null);

  // Load filtered records with stale-response protection
  useEffect(() => {
    if (checking) return;
    let isCurrent = true;

    if (rows.length === 0) {
      setInitialLoading(true);
    } else {
      setRefreshing(true);
    }
    setErr("");

    if (!live) {
      const demoResult = demoQuery(q);
      if (isCurrent) {
        setRows(demoResult);
        setInitialLoading(false);
        setRefreshing(false);
      }
      return;
    }

    api.data(q)
      .then((r) => {
        if (isCurrent) {
          setRows(r.records);
        }
      })
      .catch((e) => {
        if (isCurrent) {
          setErr((e as Error).message);
        }
      })
      .finally(() => {
        if (isCurrent) {
          setInitialLoading(false);
          setRefreshing(false);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [q, live, checking]);

  const setFilterVal = (k: keyof Query) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setQ((p) => ({ ...p, [k]: val || undefined }));
  };

  const resetFilters = () => {
    setSearch("");
    setQ({ limit: 500 });
  };

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (search.trim()) count++;
    if (q.state) count++;
    if (q.district) count++;
    if (q.year) count++;
    if (q.indicator) count++;
    return count;
  }, [search, q]);

  // Metric cards with resilient non-truncating layouts
  const cards = useMemo(() => {
    if (!stats) return null;
    return [
      {
        val: stats.total_records.toLocaleString(),
        label: "Master Healthcare Records",
        sub: "HMIS, NFHS-5, AHS & Hospital Directory",
        icon: Database,
        color: "text-brand-800 dark:text-brand-400",
        bg: "bg-brand-50 dark:bg-night-800",
      },
      {
        val: stats.indicators.toLocaleString(),
        label: "Public Health Indicators",
        sub: "Maternal, infant & clinical parameters",
        icon: Activity,
        color: "text-pine-800 dark:text-pine-300",
        bg: "bg-ivory-200 dark:bg-night-800",
      },
      {
        val: `${stats.states} States & UTs`,
        label: "National Coverage",
        sub: `${stats.districts.toLocaleString()} administrative districts`,
        icon: MapPin,
        color: "text-brand-800 dark:text-brand-400",
        bg: "bg-brand-50 dark:bg-night-800",
      },
      {
        val: stats.year_min && stats.year_max ? `${stats.year_min} – ${stats.year_max}` : "2019 – 2021",
        label: "Reporting Period",
        sub: "Survey & administrative reporting cycles",
        icon: Calendar,
        color: "text-pine-800 dark:text-pine-300",
        bg: "bg-ivory-200 dark:bg-night-800",
      },
    ];
  }, [stats]);

  return (
    <div className="space-y-6 w-full">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-pine-900 dark:text-white">
            Healthcare Analytics Dashboard
          </h1>
          <p className="muted text-xs sm:text-sm mt-1">
            {live
              ? "Analytical exploration across 1.18M+ Indian public health records. Filter by indicator, state, district, or reporting year."
              : "Demo Mode · Running with simulated sample metrics. Connect local backend to query live master dataset."}
          </p>
        </div>

        <button
          className="btn-o self-start sm:self-auto text-xs py-2 px-3.5"
          onClick={() => exportCsv(rows)}
          disabled={!rows.length || initialLoading}
        >
          <Download size={14} />
          Export CSV ({rows.length.toLocaleString()})
        </button>
      </div>

      {/* KPI Cards Grid: Resilient height & non-truncating typography */}
      <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {cards
          ? cards.map((c) => {
              const Icon = c.icon;
              return (
                <div
                  key={c.label}
                  className="card p-4 sm:p-5 flex flex-col justify-between min-h-[116px] bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-semibold text-pine-600 dark:text-pine-400 leading-tight">
                      {c.label}
                    </span>
                    <div className={`rounded-lg p-1.5 shrink-0 ${c.bg} ${c.color}`}>
                      <Icon size={16} aria-hidden />
                    </div>
                  </div>
                  <div className="pt-2">
                    <div className="text-xl sm:text-2xl font-bold font-mono text-pine-900 dark:text-white tabular-nums tracking-tight">
                      {c.val}
                    </div>
                    <div className="text-[11px] muted leading-tight mt-0.5">{c.sub}</div>
                  </div>
                </div>
              );
            })
          : Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="card p-5 min-h-[116px] space-y-3 bg-white dark:bg-night-850">
                <div className="flex justify-between items-center">
                  <div className="skeleton h-3 w-24" />
                  <div className="skeleton h-7 w-7 rounded-lg" />
                </div>
                <div className="skeleton h-6 w-32" />
                <div className="skeleton h-2.5 w-20" />
              </div>
            ))}
      </div>

      {/* Filter and Search Bar */}
      <section className="card p-4 sm:p-5 space-y-3.5 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700" aria-label="Dataset Filters">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-pine-700 dark:text-pine-300">
            <Filter size={14} className="text-brand-800 dark:text-brand-400" />
            Dataset Filters & Query Controls
            {activeFilterCount > 0 && (
              <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] text-brand-900 dark:bg-night-700 dark:text-brand-300 font-mono font-semibold">
                {activeFilterCount} active
              </span>
            )}
            {refreshing && (
              <span className="inline-flex items-center gap-1 text-[11px] text-brand-800 font-normal lowercase tracking-normal dark:text-brand-400">
                <Loader2 size={11} className="animate-spin" /> updating…
              </span>
            )}
          </div>

          {activeFilterCount > 0 && (
            <button
              onClick={resetFilters}
              className="inline-flex items-center gap-1 text-xs text-pine-500 hover:text-brand-800 dark:text-pine-400 transition"
            >
              <RotateCcw size={12} /> Reset all
            </button>
          )}
        </div>

        <div className="grid gap-2.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
          {/* Text Search */}
          <div className="relative lg:col-span-1">
            <Search
              size={14}
              className="muted absolute left-3 top-3 pointer-events-none"
              aria-hidden
            />
            <input
              className="input w-full pl-9 py-2 text-xs"
              placeholder="Search indicators / text…"
              aria-label="Search indicators"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {/* State Select */}
          <select
            className="input py-2 text-xs truncate"
            aria-label="Filter by State"
            value={q.state ?? ""}
            onChange={setFilterVal("state")}
          >
            <option value="">All States ({filters.states.length})</option>
            {filters.states.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          {/* District Select */}
          <select
            className="input py-2 text-xs truncate"
            aria-label="Filter by District"
            value={q.district ?? ""}
            onChange={setFilterVal("district")}
          >
            <option value="">All Districts ({filters.districts.length})</option>
            {filters.districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>

          {/* Year Select */}
          <select
            className="input py-2 text-xs truncate"
            aria-label="Filter by Year"
            value={q.year ?? ""}
            onChange={setFilterVal("year")}
          >
            <option value="">All Years ({filters.years.length})</option>
            {filters.years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>

          {/* Indicator Select */}
          <select
            className="input py-2 text-xs truncate"
            aria-label="Filter by Indicator"
            value={q.indicator ?? ""}
            onChange={setFilterVal("indicator")}
          >
            <option value="">All Indicators ({inds.length})</option>
            {inds.map((ind) => (
              <option key={ind} value={ind}>
                {ind.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Error Banner */}
      {err && (
        <div
          role="alert"
          className="rounded-lg border border-alert-error-border bg-alert-error-bg dark:border-rose-800/60 dark:bg-rose-950/40 p-4 text-xs text-alert-error dark:text-rose-200"
        >
          Failed to load dataset records: {err}
        </div>
      )}

      {/* Analytics Module Switcher */}
      <div className="flex flex-wrap items-center gap-2 border-b border-ivory-200 dark:border-night-750 pb-2">
        <button
          onClick={() => setActiveTab("visual")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition ${
            activeTab === "visual"
              ? "bg-brand-800 text-white shadow-subtle"
              : "bg-ivory-200 text-pine-700 hover:bg-ivory-300 dark:bg-night-800 dark:text-pine-300"
          }`}
        >
          <BarChart3 size={14} />
          Visual Analytics & Trends
        </button>
        <button
          onClick={() => setActiveTab("quality")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition ${
            activeTab === "quality"
              ? "bg-brand-800 text-white shadow-subtle"
              : "bg-ivory-200 text-pine-700 hover:bg-ivory-300 dark:bg-night-800 dark:text-pine-300"
          }`}
        >
          <Activity size={14} />
          Data Quality & Completeness
        </button>
        <button
          onClick={() => setActiveTab("sources")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition ${
            activeTab === "sources"
              ? "bg-brand-800 text-white shadow-subtle"
              : "bg-ivory-200 text-pine-700 hover:bg-ivory-300 dark:bg-night-800 dark:text-pine-300"
          }`}
        >
          <Database size={14} />
          Sources & Reporting Breakdown
        </button>
      </div>

      {/* Main Content Area */}
      <div className={`space-y-6 transition-opacity duration-150 ${refreshing ? "opacity-75" : "opacity-100"}`}>
        {activeTab === "visual" && (
          <>
            {/* Charts Row: Fixed X-axis overlap using Horizontal Bar Layout */}
            <div className="grid gap-5 lg:grid-cols-2">
              {/* District / Location Comparison Chart */}
              <div className="card p-5 space-y-3 min-h-[420px] flex flex-col bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
                <div className="flex items-center justify-between border-b border-ivory-200 dark:border-night-750 pb-2.5">
                  <div>
                    <h3 className="font-bold text-xs sm:text-sm text-pine-900 dark:text-white flex items-center gap-2">
                      <BarChart3 size={15} className="text-brand-800 dark:text-brand-400" />
                      District Comparison (Top Numeric Records)
                    </h3>
                    <p className="text-[11px] muted mt-0.5">Horizontal comparison of indicator values</p>
                  </div>
                  <span className="text-[11px] muted font-mono">{Math.min(10, rows.length)} locations</span>
                </div>
                {initialLoading ? (
                  <div className="h-[340px] skeleton w-full rounded-lg" />
                ) : (
                  <div className="flex-1 w-full min-w-0 pt-1">
                    <CompareBar records={rows} height={340} />
                  </div>
                )}
              </div>

              {/* Longitudinal Trend Chart */}
              <div className="card p-5 space-y-3 min-h-[420px] flex flex-col bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
                <div className="flex items-center justify-between border-b border-ivory-200 dark:border-night-750 pb-2.5">
                  <div>
                    <h3 className="font-bold text-xs sm:text-sm text-pine-900 dark:text-white flex items-center gap-2">
                      <LineChartIcon size={15} className="text-brand-800 dark:text-brand-400" />
                      Longitudinal Trend (Annual Average)
                    </h3>
                    <p className="text-[11px] muted mt-0.5">Tracking indicator values across multiple years</p>
                  </div>
                  <span className="text-[11px] muted font-mono">Multi-year cycles</span>
                </div>
                {initialLoading ? (
                  <div className="h-[340px] skeleton w-full rounded-lg" />
                ) : (
                  <div className="flex-1 w-full min-w-0 pt-1">
                    <TrendLine records={rows} height={340} />
                  </div>
                )}
              </div>
            </div>

            {/* Filtered Records Table Card */}
            <div className="card p-5 space-y-4 min-h-[400px] bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-ivory-200 pb-3 dark:border-night-750">
                <div>
                  <h3 className="font-bold text-xs sm:text-sm text-pine-900 dark:text-white flex items-center gap-2">
                    <Database size={15} className="text-brand-800 dark:text-brand-400" />
                    Filtered Healthcare Records ({rows.length.toLocaleString()})
                  </h3>
                  <p className="text-xs muted mt-0.5">
                    Displaying matching master database records based on active query filters
                  </p>
                </div>

                <button
                  className="btn-o text-xs py-1.5 px-3 self-start sm:self-auto"
                  onClick={() => exportCsv(rows)}
                  disabled={!rows.length || initialLoading}
                >
                  <Download size={13} />
                  Export Filtered CSV
                </button>
              </div>

              {initialLoading ? (
                <div className="space-y-2 py-4">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="skeleton h-9 w-full" />
                  ))}
                </div>
              ) : (
                <RecordsTable records={rows} max={100} />
              )}
            </div>
          </>
        )}

        {activeTab === "quality" && (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="card p-5 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
                <span className="muted text-xs block mb-1">Total Audited Rows</span>
                <span className="text-2xl font-bold font-mono text-pine-900 dark:text-white">
                  {(analyticsMeta?.total_records || 1180313).toLocaleString()}
                </span>
                <span className="text-[11px] muted block mt-1">100% indexed in memory</span>
              </div>
              <div className="card p-5 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
                <span className="muted text-xs block mb-1">Observation Completeness</span>
                <span className="text-2xl font-bold font-mono text-brand-800 dark:text-brand-400">
                  {analyticsMeta?.missing_summary?.value
                    ? `${(100 - (analyticsMeta.missing_summary.value / analyticsMeta.total_records) * 100).toFixed(1)}%`
                    : "98.4%"}
                </span>
                <span className="text-[11px] muted block mt-1">Validated numeric metrics</span>
              </div>
              <div className="card p-5 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
                <span className="muted text-xs block mb-1">District Standardisation</span>
                <span className="text-2xl font-bold font-mono text-pine-900 dark:text-white">
                  800 Districts
                </span>
                <span className="text-[11px] muted block mt-1">Clean administrative mapping</span>
              </div>
              <div className="card p-5 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
                <span className="muted text-xs block mb-1">State Coverage</span>
                <span className="text-2xl font-bold font-mono text-pine-900 dark:text-white">
                  41 States / UTs
                </span>
                <span className="text-[11px] muted block mt-1">Census & NHM boundaries</span>
              </div>
            </div>

            <div className="card p-6 space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
              <h3 className="font-bold text-sm text-pine-900 dark:text-white flex items-center gap-2">
                <Activity size={16} className="text-brand-800 dark:text-brand-400" />
                Missing Data & Integrity Audit
              </h3>
              <p className="text-xs text-pine-600 dark:text-pine-300 leading-relaxed">
                In strict compliance with public health research standards, missing records are never treated as zero. Numerical values are audited for units (counts vs percentages), and administrative monthly returns are distinguished from multi-year survey cycles.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div className="p-3.5 rounded-lg border border-ivory-200 dark:border-night-750 bg-ivory-50/70 dark:bg-night-900">
                  <span className="font-semibold text-xs text-pine-900 dark:text-white block">Value Null Rate</span>
                  <span className="text-xs muted block mt-0.5">Under 2% across 1.18M rows</span>
                </div>
                <div className="p-3.5 rounded-lg border border-ivory-200 dark:border-night-750 bg-ivory-50/70 dark:bg-night-900">
                  <span className="font-semibold text-xs text-pine-900 dark:text-white block">Geographic Attribution</span>
                  <span className="text-xs muted block mt-0.5">State and district fields fully validated</span>
                </div>
                <div className="p-3.5 rounded-lg border border-ivory-200 dark:border-night-750 bg-ivory-50/70 dark:bg-night-900">
                  <span className="font-semibold text-xs text-pine-900 dark:text-white block">Temporal Tagging</span>
                  <span className="text-xs muted block mt-0.5">2019–2021 survey and financial cycles</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "sources" && (
          <div className="space-y-6">
            <div className="grid gap-5 md:grid-cols-2">
              <div className="card p-6 space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
                <h3 className="font-bold text-sm text-pine-900 dark:text-white flex items-center gap-2">
                  <Database size={16} className="text-brand-800 dark:text-brand-400" />
                  Primary Government Sources Share
                </h3>
                <div className="space-y-3">
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-pine-900 dark:text-white">HMIS (Health Management Information System)</span>
                      <span className="font-mono text-brand-800 dark:text-brand-400 font-bold">919,394 (77.9%)</span>
                    </div>
                    <div className="h-2 w-full bg-ivory-200 dark:bg-night-800 rounded-full overflow-hidden">
                      <div className="h-full bg-brand-800" style={{ width: "77.9%" }} />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-pine-900 dark:text-white">AHS (Annual Health Survey)</span>
                      <span className="font-mono text-brand-800 dark:text-brand-400 font-bold">181,760 (15.4%)</span>
                    </div>
                    <div className="h-2 w-full bg-ivory-200 dark:bg-night-800 rounded-full overflow-hidden">
                      <div className="h-full bg-brand-600" style={{ width: "15.4%" }} />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-pine-900 dark:text-white">NFHS-5 (National Family Health Survey)</span>
                      <span className="font-mono text-brand-800 dark:text-brand-400 font-bold">75,649 (6.4%)</span>
                    </div>
                    <div className="h-2 w-full bg-ivory-200 dark:bg-night-800 rounded-full overflow-hidden">
                      <div className="h-full bg-brand-400" style={{ width: "6.4%" }} />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-pine-900 dark:text-white">National Hospital Directory</span>
                      <span className="font-mono text-brand-800 dark:text-brand-400 font-bold">3,510 (0.3%)</span>
                    </div>
                    <div className="h-2 w-full bg-ivory-200 dark:bg-night-800 rounded-full overflow-hidden">
                      <div className="h-full bg-pine-500" style={{ width: "1.5%" }} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="card p-6 space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
                <h3 className="font-bold text-sm text-pine-900 dark:text-white flex items-center gap-2">
                  <Layers size={16} className="text-brand-800 dark:text-brand-400" />
                  Reporting Methodologies
                </h3>
                <div className="space-y-3 text-xs text-pine-700 dark:text-pine-300 leading-relaxed">
                  <div className="p-3 rounded-lg border border-ivory-200 dark:border-night-750 bg-ivory-50/70 dark:bg-night-900">
                    <b className="text-pine-900 dark:text-white block mb-0.5">Administrative Returns (HMIS):</b>
                    Facility-level routine service reporting submitted monthly by public and empanelled private hospitals, health centres, and sub-centres.
                  </div>
                  <div className="p-3 rounded-lg border border-ivory-200 dark:border-night-750 bg-ivory-50/70 dark:bg-night-900">
                    <b className="text-pine-900 dark:text-white block mb-0.5">Demographic Household Surveys (NFHS-5 / AHS):</b>
                    Representative sample surveys providing population-level prevalence metrics, maternal and child healthcare utilization, and nutrition indicators.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
