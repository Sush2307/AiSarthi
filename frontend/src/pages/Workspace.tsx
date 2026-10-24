import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  BarChart2,
  Bookmark,
  CheckCircle2,
  Clock,
  Compass,
  Download,
  ExternalLink,
  FileSpreadsheet,
  Filter,
  FlaskConical,
  Hash,
  HelpCircle,
  Layers,
  Loader2,
  MapPin,
  Plus,
  RefreshCw,
  Search,
  Sliders,
  Sparkles,
  Trash2,
  TrendingUp,
  X,
} from "lucide-react";
import { api } from "../api";
import { useApi } from "../context";
import { demoFilters, demoWorkspaceCompare } from "../demo";
import type {
  Filters,
  HealthRecord,
  IndicatorMeta,
  LocationMeta,
  SavedAnalysis,
  WorkspaceCompareResponse,
} from "../types";
import { CompareBar, exportCsv } from "../components/common";

const WORKSPACE_STORAGE_KEY = "infomed-saved-research";

// Curated high-impact public health indicators for fast 1-click comparison
const CURATED_INDICATORS = [
  {
    indicator: "institutional_births_in_the_5_years_before_the_survey_percent",
    label: "Institutional births in public/pvt facility (%)",
    unit: "%",
    source: "NFHS-5",
    cycle: "2019-2021",
  },
  {
    indicator: "mothers_who_had_at_least_4_antenatal_care_visits__for_last_birth_in_the_5_years_before_the_survey_percent",
    label: "Mothers with 4+ Antenatal Care (ANC) visits (%)",
    unit: "%",
    source: "NFHS-5",
    cycle: "2019-2021",
  },
  {
    indicator: "children_age_12_23_months_fully_vaccinated_based_on_information_from_either_vaccination_card_or_mothers_recall_percent",
    label: "Full child immunisation (12-23 months) (%)",
    unit: "%",
    source: "NFHS-5",
    cycle: "2019-2021",
  },
  {
    indicator: "population_living_in_households_with_electricity_percent",
    label: "Households with electricity access (%)",
    unit: "%",
    source: "NFHS-5",
    cycle: "2019-2021",
  },
  {
    indicator: "households_using_clean_fuel_for_cooking3_percent",
    label: "Households using clean cooking fuel (%)",
    unit: "%",
    source: "NFHS-5",
    cycle: "2019-2021",
  },
  {
    indicator: "sex_ratio_at_birth_for_children_born_in_the_last_five_years_females_per_1,000_males",
    label: "Sex ratio at birth (females per 1,000 males)",
    unit: "per 1,000",
    source: "NFHS-5",
    cycle: "2019-2021",
  },
  {
    indicator: "number_of_households_surveyed",
    label: "Number of households surveyed (sample size)",
    unit: "count",
    source: "NFHS-5",
    cycle: "2019-2021",
  },
];

const PRESET_LOCATION_GROUPS = [
  {
    label: "Western Hubs",
    scope: "district",
    locations: ["Pune", "Mumbai", "Nagpur"],
  },
  {
    label: "Southern Metros",
    scope: "district",
    locations: ["Bengaluru", "Chennai", "Hyderabad"],
  },
  {
    label: "Northern Districts",
    scope: "district",
    locations: ["Lucknow", "Varanasi", "Patna"],
  },
  {
    label: "State Comparison",
    scope: "state",
    locations: ["Maharashtra", "Kerala", "Bihar"],
  },
];

export default function Workspace() {
  const { live, checking } = useApi();

  // Core Query State
  const [indicator, setIndicator] = useState(
    "institutional_births_in_the_5_years_before_the_survey_percent"
  );
  const [indicatorSearch, setIndicatorSearch] = useState("");
  const [showIndicatorPicker, setShowIndicatorPicker] = useState(false);

  const [geographicScope, setGeographicScope] = useState<"district" | "state">(
    "district"
  );
  const [selectedLocations, setSelectedLocations] = useState<string[]>([
    "Pune",
    "Mumbai",
    "Nagpur",
  ]);
  const [locationSearch, setLocationSearch] = useState("");
  const [showLocationPicker, setShowLocationPicker] = useState(false);

  const [year, setYear] = useState("2019-2021");
  const [source, setSource] = useState("");

  // Raw text entry mode toggle (for power users pasting 20+ locations)
  const [rawTextMode, setRawTextMode] = useState(false);
  const [rawLocationText, setRawLocationText] = useState("Pune, Mumbai, Nagpur");

  // Metadata caches from backend
  const [allIndicators, setAllIndicators] = useState<IndicatorMeta[]>([]);
  const [allLocations, setAllLocations] = useState<LocationMeta[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(false);

  // Analysis Result State
  const [result, setResult] = useState<WorkspaceCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  // Saved Analyses (localStorage)
  const [saved, setSaved] = useState<SavedAnalysis[]>(() => {
    try {
      const raw = localStorage.getItem(WORKSPACE_STORAGE_KEY) || localStorage.getItem("sarthi-saved-research");
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });

  // Save to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(saved));
    } catch {
      /* ignore quota */
    }
  }, [saved]);

  // Load indicator metadata on mount
  useEffect(() => {
    if (checking || !live) return;
    setLoadingMeta(true);
    api
      .workspaceIndicators()
      .then((data) => {
        setAllIndicators(data);
      })
      .catch(() => {
        /* fallback to curated */
      })
      .finally(() => setLoadingMeta(false));
  }, [live, checking]);

  // Load locations when geographic scope changes
  useEffect(() => {
    if (checking || !live) return;
    api
      .workspaceLocations(geographicScope)
      .then((locs) => {
        setAllLocations(locs);
      })
      .catch(() => setAllLocations([]));
  }, [geographicScope, live, checking]);

  // Find currently active indicator metadata object
  const currentIndicatorMeta = useMemo(() => {
    return allIndicators.find((i) => i.indicator === indicator);
  }, [allIndicators, indicator]);

  // Available reporting cycles for current indicator
  const availableYears = useMemo(() => {
    if (currentIndicatorMeta && currentIndicatorMeta.years.length > 0) {
      return currentIndicatorMeta.years;
    }
    if (result && result.available_years && result.available_years.length > 0) {
      return result.available_years;
    }
    return ["2019-2021", "2019-2020"];
  }, [currentIndicatorMeta, result]);

  // Filtered indicator list for search picker
  const filteredIndicators = useMemo(() => {
    if (!indicatorSearch.trim()) return allIndicators.slice(0, 50);
    const q = indicatorSearch.toLowerCase();
    return allIndicators
      .filter(
        (i) =>
          i.label.toLowerCase().includes(q) ||
          i.indicator.toLowerCase().includes(q) ||
          i.source.toLowerCase().includes(q)
      )
      .slice(0, 50);
  }, [allIndicators, indicatorSearch]);

  // Filtered locations for location picker
  const filteredLocations = useMemo(() => {
    if (!locationSearch.trim()) return allLocations.slice(0, 40);
    const q = locationSearch.toLowerCase();
    return allLocations
      .filter(
        (l) =>
          l.name.toLowerCase().includes(q) ||
          l.state.toLowerCase().includes(q) ||
          l.label.toLowerCase().includes(q)
      )
      .slice(0, 40);
  }, [allLocations, locationSearch]);

  // Run Comparative Analysis
  const runAnalysis = async (
    targetLocations = selectedLocations,
    targetIndicator = indicator,
    targetYear = year,
    targetSource = source
  ) => {
    const locs = rawTextMode
      ? rawLocationText
          .split(/[,;\n]+/)
          .map((s) => s.trim())
          .filter((s) => s.length > 0)
      : targetLocations;

    if (!locs.length || !targetIndicator.trim()) return;

    setLoading(true);
    setErr("");

    try {
      if (live) {
        const res = await api.workspaceCompare({
          indicator: targetIndicator.trim(),
          locations: locs,
          year: targetYear || undefined,
          source: targetSource || undefined,
          geographic_scope: geographicScope,
        });
        setResult(res);
        if (res.year && res.year !== targetYear) {
          setYear(res.year);
        }
      } else {
        const demoRes = demoWorkspaceCompare({
          indicator: targetIndicator.trim(),
          locations: locs,
          year: targetYear || undefined,
          source: targetSource || undefined,
          geographic_scope: geographicScope,
        });
        setResult(demoRes);
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // Run on first load
  useEffect(() => {
    runAnalysis();
  }, []);

  // Handlers for location management
  const addLocation = (locName: string) => {
    if (!selectedLocations.includes(locName)) {
      const next = [...selectedLocations, locName];
      setSelectedLocations(next);
      setRawLocationText(next.join(", "));
    }
    setLocationSearch("");
    setShowLocationPicker(false);
  };

  const removeLocation = (locName: string) => {
    const next = selectedLocations.filter((l) => l !== locName);
    setSelectedLocations(next);
    setRawLocationText(next.join(", "));
  };

  const selectIndicator = (canonical: string, defaultCycle?: string) => {
    setIndicator(canonical);
    setIndicatorSearch("");
    setShowIndicatorPicker(false);

    const meta = allIndicators.find((i) => i.indicator === canonical);
    const chosenYear = defaultCycle || (meta && meta.years[0]) || "";
    setYear(chosenYear);

    runAnalysis(selectedLocations, canonical, chosenYear, source);
  };

  const applyPreset = (group: (typeof PRESET_LOCATION_GROUPS)[0]) => {
    setGeographicScope(group.scope as "district" | "state");
    setSelectedLocations(group.locations);
    setRawLocationText(group.locations.join(", "));
    runAnalysis(group.locations, indicator, year, source);
  };

  const saveCurrentAnalysis = () => {
    if (!result || !result.found) return;
    const newSaved: SavedAnalysis = {
      id: Date.now().toString(),
      title: `${result.display_label || result.indicator} (${selectedLocations.slice(0, 2).join(", ")}${selectedLocations.length > 2 ? ` +${selectedLocations.length - 2}` : ""})`,
      createdAt: new Date().toLocaleDateString("en-IN", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }),
      indicator,
      locations: selectedLocations,
      year: year || undefined,
      source: source || undefined,
      response: result,
    };

    setSaved((prev) => [newSaved, ...prev.slice(0, 19)]);
  };

  const loadSaved = (item: SavedAnalysis) => {
    setIndicator(item.indicator);
    setSelectedLocations(item.locations);
    setRawLocationText(item.locations.join(", "));
    setYear(item.year || "");
    setSource(item.source || "");
    setResult(item.response);
  };

  const deleteSaved = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSaved((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <div className="space-y-6 w-full max-w-[1500px] mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-ivory-200 dark:border-night-750 pb-4">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-brand-800 dark:text-brand-400 mb-1">
            <FlaskConical size={14} />
            Reproducible Public Health Analytics
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-pine-900 dark:text-white">
            Research Workspace
          </h1>
          <p className="muted text-xs sm:text-sm mt-0.5 max-w-3xl">
            Conduct multi-district comparative extractions, verify arithmetic spreads, inspect source reporting partitions, and preserve reproducible study models.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-ivory-300 bg-ivory-100 px-3 py-1 text-xs font-mono font-medium text-pine-600 dark:border-night-700 dark:bg-night-800 dark:text-pine-300">
            <Bookmark size={13} className="text-brand-700 dark:text-brand-400" />
            <span>Local Browser Storage</span>
          </div>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="grid gap-6 lg:grid-cols-[420px_1fr] items-start">
        {/* Left Control Panel */}
        <div className="space-y-5">
          {/* Query Formulation Section */}
          <section className="card p-5 space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
            <div className="flex items-center justify-between border-b border-ivory-200 dark:border-night-750 pb-3">
              <h2 className="text-sm font-bold text-pine-900 dark:text-white flex items-center gap-2">
                <Sliders size={15} className="text-brand-800 dark:text-brand-400" />
                Comparison Parameters
              </h2>
              <span className="text-[11px] font-mono muted">
                {selectedLocations.length} locations
              </span>
            </div>

            <div className="space-y-4">
              {/* 1. Healthcare Indicator Selector */}
              <div className="relative">
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold text-pine-800 dark:text-pine-200">
                    Healthcare Indicator
                  </label>
                  <span className="text-[10px] font-mono muted">
                    {allIndicators.length ? `${allIndicators.length} indicators` : "778 in dataset"}
                  </span>
                </div>

                {/* Selected Indicator Pill */}
                <div
                  onClick={() => setShowIndicatorPicker(!showIndicatorPicker)}
                  className="flex items-center justify-between p-2.5 rounded-lg border border-ivory-300 bg-ivory-50/60 dark:border-night-700 dark:bg-night-900 cursor-pointer hover:border-brand-500 transition"
                >
                  <div className="min-w-0 pr-2">
                    <div className="text-xs font-semibold text-pine-900 dark:text-white truncate">
                      {currentIndicatorMeta?.label ||
                        result?.display_label ||
                        indicator.replace(/_/g, " ")}
                    </div>
                    <div className="flex items-center gap-2 text-[10px] muted mt-0.5">
                      <span className="font-mono text-brand-700 dark:text-brand-400">
                        {currentIndicatorMeta?.source || result?.source || "NFHS-5"}
                      </span>
                      <span>·</span>
                      <span className="font-mono">
                        Unit: {currentIndicatorMeta?.unit || "%"}
                      </span>
                    </div>
                  </div>
                  <Search size={14} className="text-pine-400 shrink-0" />
                </div>

                {/* Searchable Combobox Dropdown */}
                {showIndicatorPicker && (
                  <div className="absolute top-full left-0 right-0 z-30 mt-1.5 rounded-xl border border-ivory-300 bg-white dark:border-night-700 dark:bg-night-900 shadow-elevated p-2 space-y-2 max-h-72 overflow-hidden flex flex-col">
                    <div className="relative">
                      <Search
                        size={13}
                        className="absolute left-2.5 top-1/2 -translate-y-1/2 text-pine-400"
                      />
                      <input
                        autoFocus
                        className="input w-full text-xs pl-8 py-1.5"
                        placeholder="Search 778 indicators by name, topic…"
                        value={indicatorSearch}
                        onChange={(e) => setIndicatorSearch(e.target.value)}
                      />
                    </div>

                    <div className="overflow-y-auto flex-1 space-y-1 pr-1">
                      {filteredIndicators.map((item) => (
                        <div
                          key={item.indicator}
                          onClick={() => selectIndicator(item.indicator, item.years[0])}
                          className="p-2 rounded-lg hover:bg-ivory-100 dark:hover:bg-night-800 cursor-pointer transition text-left"
                        >
                          <div className="text-xs font-semibold text-pine-900 dark:text-white truncate">
                            {item.label}
                          </div>
                          <div className="flex items-center gap-2 text-[10px] muted mt-0.5 font-mono">
                            <span className="text-brand-700 dark:text-brand-400">
                              {item.source}
                            </span>
                            <span>·</span>
                            <span>{item.unit}</span>
                            <span>·</span>
                            <span>{item.years.join(", ") || "Aggregate"}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Curated Indicator Fast Chips */}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {CURATED_INDICATORS.slice(0, 4).map((c) => (
                    <button
                      key={c.indicator}
                      onClick={() => selectIndicator(c.indicator, c.cycle)}
                      className={`text-[10px] px-2 py-1 rounded-md border transition ${
                        indicator === c.indicator
                          ? "border-brand-600 bg-brand-50 text-brand-900 dark:bg-brand-950/70 dark:text-brand-300 font-semibold"
                          : "border-ivory-300 bg-white text-pine-700 dark:border-night-700 dark:bg-night-900 dark:text-pine-300 hover:border-brand-400"
                      }`}
                    >
                      {c.label.split("(")[0].trim()}
                    </button>
                  ))}
                </div>
              </div>

              {/* 2. Geographic Scope & Location Picker */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-pine-800 dark:text-pine-200">
                    Locations to Compare
                  </label>
                  <div className="inline-flex rounded-lg border border-ivory-300 bg-ivory-100 p-0.5 text-[11px] font-medium dark:border-night-700 dark:bg-night-900">
                    <button
                      onClick={() => {
                        setGeographicScope("district");
                        setSelectedLocations(["Pune", "Mumbai", "Nagpur"]);
                      }}
                      className={`px-2.5 py-0.5 rounded-md transition ${
                        geographicScope === "district"
                          ? "bg-white font-semibold text-pine-900 dark:bg-night-800 dark:text-white shadow-xs"
                          : "text-pine-600 dark:text-pine-400"
                      }`}
                    >
                      Districts
                    </button>
                    <button
                      onClick={() => {
                        setGeographicScope("state");
                        setSelectedLocations(["Maharashtra", "Kerala", "Bihar"]);
                      }}
                      className={`px-2.5 py-0.5 rounded-md transition ${
                        geographicScope === "state"
                          ? "bg-white font-semibold text-pine-900 dark:bg-night-800 dark:text-white shadow-xs"
                          : "text-pine-600 dark:text-pine-400"
                      }`}
                    >
                      States
                    </button>
                  </div>
                </div>

                {!rawTextMode ? (
                  <div className="space-y-2">
                    {/* Location Chips */}
                    <div className="flex flex-wrap gap-1.5 min-h-[44px] p-2 rounded-lg border border-ivory-300 bg-ivory-50/40 dark:border-night-700 dark:bg-night-900">
                      {selectedLocations.map((loc) => (
                        <span
                          key={loc}
                          className="inline-flex items-center gap-1.5 rounded-md bg-brand-100/80 px-2.5 py-1 text-xs font-medium text-brand-900 dark:bg-night-800 dark:text-brand-300 border border-brand-200 dark:border-night-700"
                        >
                          <MapPin size={11} className="text-brand-700 dark:text-brand-400" />
                          <span>{loc}</span>
                          <button
                            onClick={() => removeLocation(loc)}
                            className="hover:text-alert-error"
                            title={`Remove ${loc}`}
                          >
                            <X size={11} />
                          </button>
                        </span>
                      ))}

                      {/* Add Location Search Input */}
                      <div className="relative flex-1 min-w-[120px]">
                        <input
                          className="w-full bg-transparent text-xs outline-none px-1 py-0.5 text-pine-900 dark:text-white placeholder:text-pine-400"
                          placeholder={
                            selectedLocations.length === 0
                              ? "Type district name…"
                              : "+ Add location…"
                          }
                          value={locationSearch}
                          onFocus={() => setShowLocationPicker(true)}
                          onChange={(e) => {
                            setLocationSearch(e.target.value);
                            setShowLocationPicker(true);
                          }}
                        />

                        {showLocationPicker && (
                          <div className="absolute top-full left-0 z-30 mt-1 w-64 rounded-xl border border-ivory-300 bg-white dark:border-night-700 dark:bg-night-900 shadow-elevated p-1.5 max-h-48 overflow-y-auto">
                            {filteredLocations.length ? (
                              filteredLocations.map((l) => (
                                <div
                                  key={l.id + l.state}
                                  onClick={() => addLocation(l.name)}
                                  className="p-1.5 rounded-md hover:bg-ivory-100 dark:hover:bg-night-800 text-xs cursor-pointer flex items-center justify-between text-pine-900 dark:text-white"
                                >
                                  <span className="font-medium">{l.name}</span>
                                  <span className="text-[10px] muted font-mono">
                                    {l.state}
                                  </span>
                                </div>
                              ))
                            ) : (
                              <div className="text-[11px] muted p-2 text-center">
                                No matching {geographicScope} found.
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Presets Row */}
                    <div className="flex items-center justify-between pt-0.5">
                      <div className="flex flex-wrap gap-1.5">
                        {PRESET_LOCATION_GROUPS.map((g) => (
                          <button
                            key={g.label}
                            onClick={() => applyPreset(g)}
                            className="text-[10px] px-2 py-0.5 rounded border border-ivory-200 dark:border-night-700 bg-white dark:bg-night-900 text-pine-600 dark:text-pine-400 hover:text-brand-800 hover:border-brand-500 transition"
                          >
                            {g.label}
                          </button>
                        ))}
                      </div>

                      <button
                        onClick={() => setRawTextMode(true)}
                        className="text-[10px] text-brand-700 dark:text-brand-400 underline hover:text-brand-900"
                      >
                        Edit as text
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <textarea
                      className="input w-full text-xs h-20 resize-none font-sans"
                      placeholder="e.g. Pune, Mumbai, Nagpur, Thane"
                      value={rawLocationText}
                      onChange={(e) => {
                        setRawLocationText(e.target.value);
                        setSelectedLocations(
                          e.target.value
                            .split(/[,;\n]+/)
                            .map((s) => s.trim())
                            .filter(Boolean)
                        );
                      }}
                    />
                    <div className="flex items-center justify-between mt-1 text-[10px] muted">
                      <span>Separate names with commas or line breaks</span>
                      <button
                        onClick={() => setRawTextMode(false)}
                        className="text-brand-700 dark:text-brand-400 underline font-medium"
                      >
                        Done (Switch to chips)
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* 3. Reporting Cycle & Data Source */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-pine-800 dark:text-pine-200 mb-1">
                    Reporting Cycle
                  </label>
                  <select
                    className="input w-full text-xs truncate"
                    value={year}
                    onChange={(e) => setYear(e.target.value)}
                  >
                    <option value="">Any Cycle (Latest Available)</option>
                    {availableYears.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-pine-800 dark:text-pine-200 mb-1">
                    Data Source
                  </label>
                  <select
                    className="input w-full text-xs truncate"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                  >
                    <option value="">Any Source (Auto)</option>
                    <option value="NFHS-5">NFHS-5 (2019-2021)</option>
                    <option value="HMIS">HMIS (2019-2020)</option>
                    <option value="AHS">AHS</option>
                  </select>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => runAnalysis()}
                disabled={loading || !indicator.trim() || !selectedLocations.length}
                className="btn w-full text-xs py-2.5 mt-2 justify-center"
              >
                {loading ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <RefreshCw size={14} />
                )}
                Run Comparative Extraction
              </button>
            </div>
          </section>

          {/* Saved Analyses Drawer */}
          <section className="card p-5 space-y-3 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
            <div className="flex items-center justify-between border-b border-ivory-200 dark:border-night-750 pb-2.5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-pine-700 dark:text-pine-300 flex items-center gap-1.5">
                <Bookmark size={13} className="text-brand-800 dark:text-brand-400" />
                Saved Studies ({saved.length})
              </h3>
              <span className="text-[10px] muted font-mono">Browser Local</span>
            </div>

            {!saved.length ? (
              <p className="text-xs muted py-3 text-center leading-relaxed">
                No saved analyses yet. Configure a study above and click "Save Model" to preserve it for rapid recall.
              </p>
            ) : (
              <ul className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                {saved.map((item) => (
                  <li key={item.id}>
                    <div
                      onClick={() => loadSaved(item)}
                      className="group flex items-center justify-between p-2.5 rounded-lg border border-ivory-200 bg-ivory-50/60 dark:border-night-750 dark:bg-night-900 hover:border-brand-500 cursor-pointer transition"
                    >
                      <div className="min-w-0 pr-2">
                        <div className="text-xs font-semibold text-pine-900 dark:text-white truncate">
                          {item.title}
                        </div>
                        <div className="text-[10px] muted">Saved on {item.createdAt}</div>
                      </div>
                      <button
                        onClick={(e) => deleteSaved(item.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-pine-400 hover:text-alert-error transition"
                        title="Delete saved analysis"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        {/* Right Analytics Workspace */}
        <div className="space-y-5">
          {err && (
            <div className="card border-alert-error-border bg-alert-error-bg dark:border-rose-800/60 dark:bg-rose-950/40 p-4 text-xs text-alert-error dark:text-rose-200">
              <b>Extraction Error:</b> {err}
            </div>
          )}

          {loading ? (
            <div className="card p-12 text-center space-y-3 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
              <Loader2 size={24} className="animate-spin text-brand-700 dark:text-brand-400 mx-auto" />
              <div className="text-sm font-semibold text-pine-900 dark:text-white">
                Querying Master Healthcare Records…
              </div>
              <p className="text-xs muted max-w-sm mx-auto">
                Scanning verified partitions across Indian district observations for deterministic statistical calculations.
              </p>
            </div>
          ) : result && result.found && result.records.length > 0 ? (
            <>
              {/* Partial Location Warning (if some locations had no records) */}
              {result.missing_locations && result.missing_locations.length > 0 && (
                <div className="rounded-xl border border-amber-300 bg-amber-50/80 dark:border-amber-700/60 dark:bg-amber-950/30 p-3.5 flex items-start gap-2.5 text-xs text-amber-900 dark:text-amber-200">
                  <AlertCircle size={16} className="text-amber-700 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <b>Partial Match Notice:</b> Verified observations were found for{" "}
                    <b>{result.matched_locations?.join(", ")}</b>. No records were observed in this cycle for{" "}
                    <b>{result.missing_locations.join(", ")}</b>.
                  </div>
                </div>
              )}

              {/* Statistical Summary Ribbon */}
              {result.statistics && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
                  <div className="card p-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
                    <span className="muted text-[11px] block font-medium">Mean Observed</span>
                    <span className="font-mono text-xl sm:text-2xl font-bold text-pine-900 dark:text-white">
                      {result.statistics.mean.toLocaleString()}
                      {result.records[0]?.unit === "%" ? "%" : ""}
                    </span>
                    <span className="text-[10px] muted block mt-0.5">
                      Unweighted district avg
                    </span>
                  </div>
                  <div className="card p-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
                    <span className="muted text-[11px] block font-medium">Median Value</span>
                    <span className="font-mono text-xl sm:text-2xl font-bold text-pine-900 dark:text-white">
                      {result.statistics.median.toLocaleString()}
                      {result.records[0]?.unit === "%" ? "%" : ""}
                    </span>
                    <span className="text-[10px] muted block mt-0.5">50th percentile</span>
                  </div>
                  <div className="card p-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
                    <span className="muted text-[11px] block font-medium">Spread (Max - Min)</span>
                    <span className="font-mono text-xl sm:text-2xl font-bold text-brand-800 dark:text-brand-400">
                      ±{result.statistics.range.toLocaleString()}
                    </span>
                    <span className="text-[10px] muted block mt-0.5">
                      Min: {result.statistics.min} · Max: {result.statistics.max}
                    </span>
                  </div>
                  <div className="card p-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
                    <span className="muted text-[11px] block font-medium">Observations</span>
                    <span className="font-mono text-xl sm:text-2xl font-bold text-pine-900 dark:text-white">
                      {result.statistics.count} / {selectedLocations.length}
                    </span>
                    <span className="text-[10px] muted block mt-0.5">Valid data points</span>
                  </div>
                </div>
              )}

              {/* Visual Comparison Chart */}
              <section className="card p-5 space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-ivory-200 dark:border-night-750 pb-3">
                  <div>
                    <h3 className="text-sm font-bold text-pine-900 dark:text-white flex items-center gap-2">
                      <BarChart2 size={16} className="text-brand-800 dark:text-brand-400" />
                      Comparative Indicator Distribution
                    </h3>
                    <p className="text-[11px] muted">
                      {result.display_label || result.indicator} ·{" "}
                      {result.year ? `Cycle: ${result.year}` : "Latest available"} ·{" "}
                      {result.source || "Official records"}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={saveCurrentAnalysis}
                      className="btn-o text-xs py-1.5 px-3"
                      title="Save this analysis definition locally"
                    >
                      <Bookmark size={13} /> Save Model
                    </button>
                    <button
                      onClick={() =>
                        exportCsv(result.records, "workspace-comparative-study.csv")
                      }
                      className="btn text-xs py-1.5 px-3"
                    >
                      <Download size={13} /> Export CSV
                    </button>
                  </div>
                </div>

                <CompareBar records={result.records} height={280} />
              </section>

              {/* Structured Comparison Data Table */}
              <section className="card p-0 overflow-hidden bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700 shadow-subtle">
                <div className="p-4 border-b border-ivory-200 dark:border-night-750 flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-pine-700 dark:text-pine-300">
                    Grounded Observations Table ({result.records.length} records)
                  </h4>
                  <span className="text-[11px] muted font-mono">
                    Deterministic Source Evidence
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs sm:text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-ivory-300 bg-ivory-50 text-[11px] font-semibold uppercase tracking-wider text-pine-600 dark:border-night-700 dark:bg-night-900 dark:text-pine-300">
                        <th className="px-4 py-2.5">Location</th>
                        <th className="px-4 py-2.5">State / UT</th>
                        <th className="px-4 py-2.5">Indicator</th>
                        <th className="px-4 py-2.5 text-center">Cycle</th>
                        <th className="px-4 py-2.5 text-right">Recorded Value</th>
                        <th className="px-4 py-2.5 text-center">Source</th>
                        <th className="px-4 py-2.5 text-center">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ivory-200 dark:divide-night-800 bg-white dark:bg-night-850">
                      {result.records.map((r, i) => (
                        <tr
                          key={i}
                          className="hover:bg-ivory-50/80 dark:hover:bg-night-800/60 transition-colors"
                        >
                          <td className="px-4 py-2.5 font-medium text-pine-900 dark:text-white">
                            {r.district || r.state}
                          </td>
                          <td className="px-4 py-2.5 text-pine-600 dark:text-pine-400">
                            {r.state || "–"}
                          </td>
                          <td className="px-4 py-2.5 text-pine-800 dark:text-pine-200">
                            {r.display_label || r.indicator.replace(/_/g, " ")}
                          </td>
                          <td className="px-4 py-2.5 text-center font-mono text-pine-600 dark:text-pine-400">
                            {r.year || "–"}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono font-bold text-brand-800 dark:text-brand-400">
                            {r.value !== null && r.value !== undefined
                              ? `${r.value.toLocaleString()} ${r.unit || ""}`
                              : "Missing (null)"}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <span className="inline-block rounded bg-brand-100 px-2 py-0.5 text-[10px] font-semibold text-brand-900 dark:bg-night-800 dark:text-brand-300 border border-brand-200 dark:border-night-700">
                              {r.source}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <Link
                              to={`/explorer?indicator=${encodeURIComponent(r.indicator)}&district=${encodeURIComponent(r.district || "")}`}
                              className="inline-flex items-center gap-1 text-[11px] text-brand-700 dark:text-brand-400 hover:underline font-medium"
                              title="Inspect this record and surrounding metadata in Data Explorer"
                            >
                              Inspect <ExternalLink size={11} />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Truthful Methodology & Reproducibility Panel */}
              <section className="card p-5 space-y-3 bg-ivory-50/70 dark:bg-night-900 border-ivory-200 dark:border-night-750">
                <div className="flex items-center justify-between border-b border-ivory-200 dark:border-night-800 pb-2.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-pine-900 dark:text-white">
                    <CheckCircle2 size={16} className="text-brand-700 dark:text-brand-400" />
                    Methodology & Reproducibility Audit
                  </div>
                  <div className="text-[10px] font-mono muted">
                    Fingerprint: healthcare_master_final_v3.csv (1.18M rows)
                  </div>
                </div>

                <p className="text-xs text-pine-700 dark:text-pine-300 leading-relaxed">
                  {result.methodology}
                </p>

                <div className="grid gap-2 sm:grid-cols-2 pt-2 border-t border-ivory-200 dark:border-night-800 text-[11px]">
                  <div>
                    <span className="muted block">Canonical Indicator Identifier:</span>
                    <span className="font-mono font-medium text-pine-900 dark:text-white">
                      {result.canonical_indicator || result.indicator}
                    </span>
                  </div>
                  <div>
                    <span className="muted block">Reproducibility Signature:</span>
                    <span className="font-mono font-semibold text-brand-800 dark:text-brand-400">
                      {result.reproducibility_signature || "INFOMED-QUERY-DETERMINISTIC"}
                    </span>
                  </div>
                </div>
              </section>
            </>
          ) : (
            /* Informative Empty State with Actionable Guidance */
            <section className="card p-8 text-center space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
              <div className="w-12 h-12 rounded-full bg-ivory-100 dark:bg-night-800 flex items-center justify-center mx-auto text-pine-500">
                <HelpCircle size={24} />
              </div>

              <div className="space-y-1.5 max-w-md mx-auto">
                <h3 className="text-sm sm:text-base font-bold text-pine-900 dark:text-white">
                  No Observations Matched These Query Parameters
                </h3>
                <p className="text-xs muted leading-relaxed">
                  {result?.methodology ||
                    "The requested combination of indicator, locations, and reporting cycle returned zero observations in this public health dataset."}
                </p>
              </div>

              {/* Actionable Suggestions */}
              <div className="pt-2 flex flex-wrap items-center justify-center gap-2">
                {availableYears.length > 0 && availableYears[0] !== year && (
                  <button
                    onClick={() => {
                      setYear(availableYears[0]);
                      runAnalysis(selectedLocations, indicator, availableYears[0], source);
                    }}
                    className="btn text-xs py-1.5 px-3"
                  >
                    Switch to Cycle: {availableYears[0]}
                  </button>
                )}
                <button
                  onClick={() => {
                    setIndicator("institutional_births_in_the_5_years_before_the_survey_percent");
                    setYear("2019-2021");
                    setSelectedLocations(["Pune", "Mumbai", "Nagpur"]);
                    runAnalysis(["Pune", "Mumbai", "Nagpur"], "institutional_births_in_the_5_years_before_the_survey_percent", "2019-2021", "");
                  }}
                  className="btn-o text-xs py-1.5 px-3"
                >
                  Reset to Verified Preset (Pune · Mumbai · Nagpur)
                </button>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
