import { useEffect, useState, useMemo } from "react";
import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  Eye,
  Filter,
  Layers,
  Loader2,
  RotateCcw,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { api } from "../api";
import { useApi } from "../context";
import { demoExplorer, demoFilters, demoQuery } from "../demo";
import type { ExplorerQuery, Filters, HealthRecord } from "../types";
import { loc } from "../components/common";

export default function Explorer() {
  const { live, checking } = useApi();

  const [query, setQuery] = useState<ExplorerQuery>({
    page: 1,
    page_size: 25,
    sort_by: "year",
    sort_order: "desc",
  });
  const [searchTerm, setSearchTerm] = useState("");
  const [records, setRecords] = useState<HealthRecord[]>([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [selectedRecord, setSelectedRecord] = useState<HealthRecord | null>(null);

  const [filters, setFilters] = useState<Filters>({
    states: [],
    districts: [],
    years: [],
    sources: [],
  });

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery((p) => ({ ...p, q: searchTerm.trim() || undefined, page: 1 }));
    }, 350);
    return () => clearTimeout(t);
  }, [searchTerm]);

  // Load filter lists
  useEffect(() => {
    if (checking) return;
    if (!live) {
      setFilters(demoFilters());
      return;
    }
    api.filters(query.state)
      .then(setFilters)
      .catch(() => setFilters(demoFilters()));
  }, [live, checking, query.state]);

  // Fetch paginated records from backend
  useEffect(() => {
    if (checking) return;
    let isCurrent = true;
    setLoading(true);
    setErr("");

    if (!live) {
      const demoRes = demoExplorer(query);
      if (isCurrent) {
        setRecords(demoRes.records);
        setTotalRecords(demoRes.total_records);
        setTotalPages(demoRes.total_pages);
        setLoading(false);
      }
      return;
    }

    api.explorer(query)
      .then((res) => {
        if (isCurrent) {
          setRecords(res.records);
          setTotalRecords(res.total_records);
          setTotalPages(res.total_pages);
        }
      })
      .catch((e) => {
        if (isCurrent) setErr((e as Error).message);
      })
      .finally(() => {
        if (isCurrent) setLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [live, checking, query]);

  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (query.q) count++;
    if (query.state) count++;
    if (query.district) count++;
    if (query.year) count++;
    if (query.source) count++;
    if (query.indicator) count++;
    if (query.geographic_level) count++;
    return count;
  }, [query]);

  const resetFilters = () => {
    setSearchTerm("");
    setQuery({
      page: 1,
      page_size: 25,
      sort_by: "year",
      sort_order: "desc",
    });
  };

  const handleSort = (col: string) => {
    setQuery((p) => ({
      ...p,
      sort_by: col,
      sort_order: p.sort_by === col && p.sort_order === "desc" ? "asc" : "desc",
      page: 1,
    }));
  };

  return (
    <div className="space-y-6 w-full">
      {/* Header & Export Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-brand-800 dark:text-brand-400 mb-1">
            <Database size={14} />
            Master Dataset Explorer
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-pine-900 dark:text-white">
            Public Health Record Directory
          </h1>
          <p className="muted text-xs sm:text-sm mt-0.5 max-w-3xl">
            Direct record-level access across 1,180,313 indexed observations. Filter, sort, inspect full metadata attributes, and download subset records without client memory bottlenecks.
          </p>
        </div>

        <a
          href={live ? api.exportCsvUrl(query) : "#"}
          className="btn self-start sm:self-auto text-xs py-2 px-4 shadow-subtle shrink-0"
          download="ai-sarthi-healthcare-records.csv"
          title="Direct streaming CSV download from backend"
        >
          <Download size={14} />
          Export Query CSV ({totalRecords.toLocaleString()})
        </a>
      </div>

      {/* Query & Filter Panel */}
      <section className="card p-4 sm:p-5 space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ivory-200 dark:border-night-750 pb-3">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-pine-700 dark:text-pine-300">
            <SlidersHorizontal size={14} className="text-brand-800 dark:text-brand-400" />
            Query Criteria & Filters
            {activeFiltersCount > 0 && (
              <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] text-brand-900 dark:bg-night-700 dark:text-brand-300 font-mono font-semibold">
                {activeFiltersCount} active
              </span>
            )}
            {loading && (
              <span className="inline-flex items-center gap-1 text-[11px] text-brand-800 font-normal lowercase tracking-normal dark:text-brand-400 ml-2">
                <Loader2 size={12} className="animate-spin" /> Querying index…
              </span>
            )}
          </div>

          {activeFiltersCount > 0 && (
            <button
              onClick={resetFilters}
              className="inline-flex items-center gap-1 text-xs text-pine-500 hover:text-brand-800 dark:text-pine-400 transition"
            >
              <RotateCcw size={12} /> Reset criteria
            </button>
          )}
        </div>

        {/* Filter Inputs Grid */}
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
          {/* Keyword Search */}
          <div className="relative sm:col-span-2">
            <Search size={14} className="muted absolute left-3 top-3 pointer-events-none" />
            <input
              className="input w-full pl-9 py-2 text-xs"
              placeholder="Search keyword (e.g. 'immunization', 'infant')…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {/* State Filter */}
          <select
            className="input py-2 text-xs truncate"
            value={query.state ?? ""}
            onChange={(e) =>
              setQuery((p) => ({
                ...p,
                state: e.target.value || undefined,
                district: undefined,
                page: 1,
              }))
            }
          >
            <option value="">All States ({filters.states.length})</option>
            {filters.states.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          {/* District Filter */}
          <select
            className="input py-2 text-xs truncate"
            value={query.district ?? ""}
            onChange={(e) =>
              setQuery((p) => ({
                ...p,
                district: e.target.value || undefined,
                page: 1,
              }))
            }
          >
            <option value="">All Districts ({filters.districts.length})</option>
            {filters.districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>

          {/* Year Filter */}
          <select
            className="input py-2 text-xs truncate"
            value={query.year ?? ""}
            onChange={(e) =>
              setQuery((p) => ({
                ...p,
                year: e.target.value || undefined,
                page: 1,
              }))
            }
          >
            <option value="">All Reporting Cycles</option>
            {filters.years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>

          {/* Source Filter */}
          <select
            className="input py-2 text-xs truncate"
            value={query.source ?? ""}
            onChange={(e) =>
              setQuery((p) => ({
                ...p,
                source: e.target.value || undefined,
                page: 1,
              }))
            }
          >
            <option value="">All Sources</option>
            {filters.sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Secondary Filters & Page Size */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1 text-xs">
          <div className="flex items-center gap-2">
            <span className="muted text-[11px]">Geographic Scope:</span>
            {["all", "district", "state", "national"].map((lvl) => {
              const active =
                (lvl === "all" && !query.geographic_level) ||
                query.geographic_level === lvl;
              return (
                <button
                  key={lvl}
                  onClick={() =>
                    setQuery((p) => ({
                      ...p,
                      geographic_level: lvl === "all" ? undefined : lvl,
                      page: 1,
                    }))
                  }
                  className={`px-2.5 py-1 rounded text-xs transition ${
                    active
                      ? "bg-brand-800 text-white font-semibold"
                      : "bg-ivory-200 text-pine-700 hover:bg-ivory-300 dark:bg-night-800 dark:text-pine-300"
                  }`}
                >
                  {lvl.toUpperCase()}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-2">
            <span className="muted text-[11px]">Rows per page:</span>
            {[25, 50, 100].map((sz) => (
              <button
                key={sz}
                onClick={() => setQuery((p) => ({ ...p, page_size: sz, page: 1 }))}
                className={`px-2 py-0.5 rounded text-xs font-mono transition ${
                  query.page_size === sz
                    ? "bg-brand-100 text-brand-900 font-bold border border-brand-300 dark:bg-night-700 dark:text-brand-300"
                    : "muted hover:text-pine-900 dark:hover:text-white"
                }`}
              >
                {sz}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Error state */}
      {err && (
        <div className="card border-alert-error-border bg-alert-error-bg dark:border-rose-800/60 dark:bg-rose-950/40 p-4 text-xs text-alert-error dark:text-rose-200">
          <b>Query Error:</b> {err}. Please adjust filter parameters.
        </div>
      )}

      {/* Records Table View */}
      <section className="card p-0 overflow-hidden bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm border-collapse">
            <thead>
              <tr className="border-b border-ivory-300 bg-ivory-50 text-[11px] font-semibold uppercase tracking-wider text-pine-600 dark:border-night-700 dark:bg-night-900 dark:text-pine-300">
                <th className="px-4 py-3 cursor-pointer hover:text-brand-800" onClick={() => handleSort("state")}>
                  <div className="flex items-center gap-1">
                    Location {query.sort_by === "state" && (query.sort_order === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                  </div>
                </th>
                <th className="px-4 py-3 cursor-pointer hover:text-brand-800" onClick={() => handleSort("indicator")}>
                  <div className="flex items-center gap-1">
                    Indicator & Parameter {query.sort_by === "indicator" && (query.sort_order === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                  </div>
                </th>
                <th className="px-4 py-3 text-center cursor-pointer hover:text-brand-800" onClick={() => handleSort("year")}>
                  <div className="flex items-center justify-center gap-1">
                    Cycle {query.sort_by === "year" && (query.sort_order === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                  </div>
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-brand-800" onClick={() => handleSort("value")}>
                  <div className="flex items-center justify-end gap-1">
                    Value {query.sort_by === "value" && (query.sort_order === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                  </div>
                </th>
                <th className="px-4 py-3 text-center">Level / Type</th>
                <th className="px-4 py-3 text-center">Source</th>
                <th className="px-4 py-3 text-center">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ivory-200 dark:divide-night-800 bg-white dark:bg-night-850">
              {loading && !records.length ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-4 py-3"><div className="skeleton h-4 w-28" /></td>
                    <td className="px-4 py-3"><div className="skeleton h-4 w-64" /></td>
                    <td className="px-4 py-3 text-center"><div className="skeleton h-4 w-12 mx-auto" /></td>
                    <td className="px-4 py-3 text-right"><div className="skeleton h-4 w-16 ml-auto" /></td>
                    <td className="px-4 py-3 text-center"><div className="skeleton h-4 w-16 mx-auto" /></td>
                    <td className="px-4 py-3 text-center"><div className="skeleton h-4 w-16 mx-auto" /></td>
                    <td className="px-4 py-3 text-center"><div className="skeleton h-4 w-8 mx-auto" /></td>
                  </tr>
                ))
              ) : !records.length ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-xs muted">
                    No matching healthcare records found for the applied criteria.
                  </td>
                </tr>
              ) : (
                records.map((r, i) => (
                  <tr
                    key={i}
                    className="hover:bg-ivory-50/80 dark:hover:bg-night-800/60 transition-colors"
                  >
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-pine-900 dark:text-pine-100">
                      {loc(r)}
                      {r.district && r.state && r.district !== r.state && (
                        <span className="muted text-xs font-normal ml-1">· {r.state}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-pine-800 dark:text-pine-200">
                      <div className="max-w-md line-clamp-2 leading-snug font-medium" title={r.indicator}>
                        {r.indicator.replace(/_/g, " ")}
                      </div>
                      {r.parameter && (
                        <div className="text-[11px] muted line-clamp-1">{r.parameter}</div>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center text-xs font-mono text-pine-600 dark:text-pine-400">
                      {r.year ?? "–"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-mono font-bold text-pine-900 dark:text-white tabular-nums">
                      {r.value !== null && r.value !== undefined ? r.value.toLocaleString() : "–"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center text-[11px] text-pine-600 dark:text-pine-300">
                      <span className="capitalize">{r.geographic_level || "district"}</span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center">
                      <span className="inline-block rounded bg-brand-100 px-2 py-0.5 text-[11px] font-semibold text-brand-900 dark:bg-night-800 dark:text-brand-300 border border-brand-200 dark:border-night-700">
                        {r.source}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center">
                      <button
                        onClick={() => setSelectedRecord(r)}
                        className="btn-o p-1.5 rounded-lg text-pine-600 hover:text-brand-800 dark:text-pine-300"
                        title="Inspect full record parameters"
                      >
                        <Eye size={14} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Real Backend Pagination Controls */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3.5 border-t border-ivory-200 dark:border-night-750 text-xs">
          <div className="muted font-mono">
            Showing Page <b>{query.page}</b> of <b>{totalPages.toLocaleString()}</b> (<b>{totalRecords.toLocaleString()}</b> matching observations)
          </div>

          <div className="flex items-center gap-2">
            <button
              className="btn-o px-3 py-1.5 text-xs disabled:opacity-40"
              disabled={query.page <= 1 || loading}
              onClick={() => setQuery((p) => ({ ...p, page: p.page - 1 }))}
            >
              <ChevronLeft size={14} /> Previous
            </button>
            <span className="font-mono text-xs text-pine-800 dark:text-pine-200 px-1">
              {query.page} / {totalPages}
            </span>
            <button
              className="btn-o px-3 py-1.5 text-xs disabled:opacity-40"
              disabled={query.page >= totalPages || loading}
              onClick={() => setQuery((p) => ({ ...p, page: p.page + 1 }))}
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </section>

      {/* Record Inspection Modal / Drawer */}
      {selectedRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 space-y-5 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-elevated">
            <div className="flex items-start justify-between border-b border-ivory-200 dark:border-night-750 pb-3">
              <div>
                <span className="rounded bg-brand-100 px-2 py-0.5 text-[10px] font-mono font-bold text-brand-900 dark:bg-night-800 dark:text-brand-300">
                  {selectedRecord.source} RECORD
                </span>
                <h3 className="text-base font-bold text-pine-900 dark:text-white mt-1">
                  {selectedRecord.indicator.replace(/_/g, " ")}
                </h3>
              </div>
              <button
                onClick={() => setSelectedRecord(null)}
                className="btn-o p-1.5 rounded-lg text-pine-500 hover:text-pine-900"
              >
                <X size={16} />
              </button>
            </div>

            <dl className="grid grid-cols-2 gap-4 text-xs sm:text-sm">
              <div className="space-y-0.5">
                <dt className="muted text-[11px] uppercase tracking-wider">State / Union Territory</dt>
                <dd className="font-semibold text-pine-900 dark:text-white">{selectedRecord.state || "–"}</dd>
              </div>
              <div className="space-y-0.5">
                <dt className="muted text-[11px] uppercase tracking-wider">District</dt>
                <dd className="font-semibold text-pine-900 dark:text-white">{selectedRecord.district || "–"}</dd>
              </div>
              <div className="space-y-0.5">
                <dt className="muted text-[11px] uppercase tracking-wider">Reporting Cycle / Year</dt>
                <dd className="font-mono font-semibold text-pine-900 dark:text-white">{selectedRecord.year || "–"}</dd>
              </div>
              <div className="space-y-0.5">
                <dt className="muted text-[11px] uppercase tracking-wider">Recorded Observation Value</dt>
                <dd className="font-mono text-base font-bold text-brand-800 dark:text-brand-400">
                  {selectedRecord.value !== null && selectedRecord.value !== undefined ? selectedRecord.value.toLocaleString() : "N/A"}
                </dd>
              </div>
              <div className="space-y-0.5">
                <dt className="muted text-[11px] uppercase tracking-wider">Geographic Level</dt>
                <dd className="capitalize text-pine-800 dark:text-pine-200">{selectedRecord.geographic_level || "district"}</dd>
              </div>
              <div className="space-y-0.5">
                <dt className="muted text-[11px] uppercase tracking-wider">Report Source Type</dt>
                <dd className="capitalize text-pine-800 dark:text-pine-200">{selectedRecord.report_type || "survey / aggregate"}</dd>
              </div>
              {selectedRecord.parameter && (
                <div className="col-span-2 space-y-0.5">
                  <dt className="muted text-[11px] uppercase tracking-wider">Sub-Parameter / Demographic Breakup</dt>
                  <dd className="text-pine-800 dark:text-pine-200 leading-relaxed">{selectedRecord.parameter}</dd>
                </div>
              )}
              {selectedRecord.category && (
                <div className="col-span-2 space-y-0.5">
                  <dt className="muted text-[11px] uppercase tracking-wider">Healthcare Category</dt>
                  <dd className="text-pine-800 dark:text-pine-200">{selectedRecord.category}</dd>
                </div>
              )}
            </dl>

            <div className="pt-3 border-t border-ivory-200 dark:border-night-750 flex items-center justify-between text-xs">
              <span className="muted font-mono text-[11px]">Audit: Verifiable against master CSV partition</span>
              <button onClick={() => setSelectedRecord(null)} className="btn px-4 py-2">
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
