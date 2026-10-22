import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Database,
  FileText,
  Layers,
  MessageSquare,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "../api";
import { useApi } from "../context";
import { SAMPLES, TECH_STACK, WORKFLOW_STEPS } from "../constants";
import type { Stats } from "../types";

const features = [
  {
    icon: MessageSquare,
    title: "Evidence-Grounded AI Chat",
    desc: "Inquire over maternal health, infant mortality, and immunization data with verified citations back to primary government records.",
    to: "/chat",
    tag: "Grounded SLM",
  },
  {
    icon: Database,
    title: "Master Data Explorer",
    desc: "Direct record-level access across 1.18M+ rows with backend pagination, multi-attribute filtering, and instant CSV exports.",
    to: "/explorer",
    tag: "Public Catalog",
  },
  {
    icon: BarChart3,
    title: "Analytics Dashboard",
    desc: "Structured exploratory modules, temporal trend comparisons, geographic breakdowns, and data completeness metrics.",
    to: "/dashboard",
    tag: "Visual Analytics",
  },
  {
    icon: Layers,
    title: "Research Workspace",
    desc: "Formulate reproducible comparative analyses across districts, review mathematical spreads, and save local analytical models.",
    to: "/workspace",
    tag: "Reproducibility",
  },
];

export default function Home() {
  const nav = useNavigate();
  const { live, recordsCount } = useApi();
  const [stats, setStats] = useState<Stats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    if (live) {
      api.stats()
        .then(setStats)
        .catch(() => {
          /* ignore error, fallback to defaults */
        });
    }
  }, [live]);

  const handleHeroSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    nav("/chat", { state: { prompt: searchQuery.trim() } });
  };

  return (
    <div className="space-y-12 sm:space-y-16 w-full">
      {/* Hero Section: Editorial Institutional Design */}
      <section className="rounded-2xl border border-ivory-300 bg-white p-6 sm:p-10 lg:p-12 shadow-subtle dark:border-[#2D3F37] dark:bg-[#16231E]">
        <div className="max-w-4xl lg:max-w-5xl space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-900 dark:border-brand-800 dark:bg-brand-950 dark:text-brand-300">
            <Sparkles size={13} className="text-brand-700 dark:text-brand-400" />
            National Healthcare Intelligence Platform
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-pine-900 sm:text-4xl lg:text-5xl dark:text-white leading-[1.15]">
            India's Public Health Data. <span className="text-brand-800 dark:text-brand-400">Clearer Evidence.</span> Better Decisions.
          </h1>

          <p className="text-sm sm:text-base leading-relaxed text-pine-600 dark:text-pine-300 max-w-4xl">
            Explore healthcare indicators across Indian states and districts. Ask questions in natural language, compare available observations, and trace statistical findings back to their source records over <b>1,180,313 public health records</b> across HMIS, NFHS-5, and AHS datasets.
          </p>

          {/* Prominent Natural-Language Search Box */}
          <form onSubmit={handleHeroSubmit} className="relative max-w-3xl pt-2">
            <Search size={18} className="muted absolute left-4 top-5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Ask about maternal health, immunisation, institutional births, district-level statistics…"
              className="input w-full pl-11 pr-28 py-3 text-xs sm:text-sm rounded-xl shadow-subtle"
            />
            <button
              type="submit"
              className="btn absolute right-1.5 top-3.5 py-2 px-4 text-xs rounded-lg"
            >
              Ask Sarthi
            </button>
          </form>

          {/* Quick-start Action Links */}
          <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
            <span className="muted text-[11px] font-semibold uppercase tracking-wider">Quick Explorations:</span>
            <button
              onClick={() => nav("/chat", { state: { prompt: "Institutional births in Pune vs Mumbai" } })}
              className="chip py-1 px-2.5 text-xs"
            >
              Institutional births Pune vs Mumbai
            </button>
            <button
              onClick={() => nav("/explorer", { state: { indicator: "anaemia" } })}
              className="chip py-1 px-2.5 text-xs"
            >
              Browse 1.18M Records
            </button>
            <button
              onClick={() => nav("/workspace")}
              className="chip py-1 px-2.5 text-xs"
            >
              Open Research Workspace
            </button>
            <button
              onClick={() => nav("/schemes")}
              className="chip py-1 px-2.5 text-xs"
            >
              Health Schemes Directory
            </button>
          </div>
        </div>

        {/* Live Metrics Ribbon: Fixed wrapping, clean grid with ample breathing room */}
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8 border-t border-ivory-200 pt-8 dark:border-[#2D3F37]">
          <div className="space-y-1">
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-brand-800 dark:text-brand-400 tabular-nums">
              {stats?.total_records
                ? stats.total_records.toLocaleString()
                : recordsCount
                ? recordsCount.toLocaleString()
                : "1,180,313"}
            </div>
            <div className="text-xs font-semibold text-pine-900 dark:text-pine-100">
              Master Healthcare Records
            </div>
            <div className="text-[11px] muted">Indexed public data points</div>
          </div>

          <div className="space-y-1">
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-pine-900 dark:text-white tabular-nums">
              {stats?.indicators ? stats.indicators.toLocaleString() : "778"}
            </div>
            <div className="text-xs font-semibold text-pine-900 dark:text-pine-100">
              Public Health Indicators
            </div>
            <div className="text-[11px] muted">Maternal, child & clinic indicators</div>
          </div>

          <div className="space-y-1">
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-pine-900 dark:text-white tabular-nums">
              41 States & UTs
            </div>
            <div className="text-xs font-semibold text-pine-900 dark:text-pine-100">
              800 Administrative Districts
            </div>
            <div className="text-[11px] muted">Complete national coverage</div>
          </div>

          <div className="space-y-1">
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-pine-900 dark:text-white tabular-nums">
              HMIS · NFHS-5 · AHS
            </div>
            <div className="text-xs font-semibold text-pine-900 dark:text-pine-100">
              Government Data Sources
            </div>
            <div className="text-[11px] muted">MoHFW & Survey cycles (2019–2021)</div>
          </div>
        </div>
      </section>

      {/* Suggested Questions Section */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-pine-900 dark:text-white flex items-center gap-2">
            <Search size={16} className="text-brand-800 dark:text-brand-400" />
            Example Queries for Instant Exploration
          </h2>
          <span className="text-xs text-pine-500 dark:text-pine-400 hidden sm:inline">
            Click to launch instant query in Chat
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((sample) => (
            <button
              key={sample}
              className="chip py-2 px-3.5 hover:border-brand-600 hover:text-brand-900 text-xs sm:text-sm font-medium"
              onClick={() => nav("/chat", { state: { prompt: sample } })}
            >
              <span>{sample}</span>
              <ArrowRight size={12} className="text-brand-700 dark:text-brand-400" />
            </button>
          ))}
        </div>
      </section>

      {/* Core Platform Capabilities */}
      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-pine-900 dark:text-white">
            Analytical Tools & Capabilities
          </h2>
          <p className="muted text-xs sm:text-sm mt-0.5">
            Structured public health exploration tools designed for rigorous research and analysis.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map(({ icon: Icon, title, desc, to, tag }) => (
            <Link
              key={title}
              to={to}
              className="card card-hover flex flex-col justify-between group p-5 bg-white dark:bg-night-850"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="rounded-lg bg-brand-50 p-2.5 text-brand-800 dark:bg-brand-950 dark:text-brand-300">
                    <Icon size={19} aria-hidden />
                  </div>
                  <span className="rounded bg-ivory-200 px-2 py-0.5 text-[10px] font-semibold text-pine-700 dark:bg-night-800 dark:text-pine-300">
                    {tag}
                  </span>
                </div>
                <h3 className="font-bold text-pine-900 dark:text-white text-sm sm:text-base group-hover:text-brand-800 transition-colors">
                  {title}
                </h3>
                <p className="muted text-xs leading-relaxed">{desc}</p>
              </div>

              <div className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-brand-800 dark:text-brand-400 group-hover:translate-x-0.5 transition-transform">
                Open Capability <ArrowRight size={13} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Evidence-Grounded Architecture */}
      <section className="rounded-xl border border-ivory-300 bg-white p-6 sm:p-8 dark:border-night-700 dark:bg-night-850 space-y-6">
        <div className="max-w-2xl space-y-1.5">
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-brand-800 dark:text-brand-400">
            <ShieldCheck size={15} />
            Evidence-Grounded Retrieval Workflow
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-pine-900 dark:text-white">
            Transparent, Citation-Backed Health Intelligence
          </h2>
          <p className="muted text-xs sm:text-sm leading-relaxed">
            AI Sarthi binds answers directly to verified rows in the master healthcare database rather than generating unverified statistical assertions.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {WORKFLOW_STEPS.map((w) => (
            <div
              key={w.step}
              className="rounded-lg border border-ivory-200 bg-ivory-50/70 p-4 dark:border-night-800 dark:bg-night-900 space-y-1.5"
            >
              <span className="font-mono text-xs font-bold text-brand-800 dark:text-brand-400">{w.step}</span>
              <h4 className="text-xs font-bold text-pine-900 dark:text-white">{w.title}</h4>
              <p className="text-[11px] muted leading-relaxed">{w.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Technical Specifications */}
      <section className="space-y-3">
        <h2 className="text-base font-bold text-pine-900 dark:text-white flex items-center gap-2">
          <Layers size={16} className="text-brand-800 dark:text-brand-400" />
          Technical Stack
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
          {TECH_STACK.map((t) => (
            <div
              key={t.name}
              className="rounded-lg border border-ivory-300 bg-white p-3 text-center dark:border-night-700 dark:bg-night-850 shadow-subtle"
            >
              <div className="font-semibold text-xs text-pine-900 dark:text-white truncate">
                {t.name}
              </div>
              <div className="text-[10px] muted truncate">{t.category}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
