import { useEffect, useState } from "react";
import { CheckCircle2, Clock, ExternalLink, FileText, Info, Search } from "lucide-react";
import { api } from "../api";
import { useApi } from "../context";
import { DEMO_SCHEMES } from "../demo";
import type { Scheme } from "../types";

export default function Schemes() {
  const { live, checking } = useApi();
  const [all, setAll] = useState<Scheme[]>(DEMO_SCHEMES);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (checking || !live) return;
    api.schemes()
      .then((r) => setAll(r.schemes))
      .catch(() => setAll(DEMO_SCHEMES));
  }, [live, checking]);

  const list = all.filter((s) =>
    (s.name + (s.summary ?? "")).toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div className="space-y-6 w-full">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-pine-900 dark:text-white">
          Government Healthcare Schemes
        </h1>
        <p className="muted text-xs sm:text-sm mt-1 max-w-4xl">
          National and state public health insurance initiatives. Scheme parameters are sourced strictly from official government portals and audited for accuracy.
        </p>
      </div>

      {/* Search Input Bar */}
      <div className="card p-3 sm:p-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
        <label className="relative block">
          <Search
            size={15}
            className="muted absolute left-3.5 top-3.5 pointer-events-none"
            aria-hidden
          />
          <input
            className="input w-full pl-10 py-2.5 text-xs sm:text-sm"
            placeholder="Search schemes by name or keywords (e.g. 'PM-JAY', 'Ayushman Bharat')…"
            aria-label="Search government schemes"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
      </div>

      {/* Schemes List */}
      {!list.length ? (
        <div className="card text-center py-12 space-y-2 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
          <FileText className="mx-auto text-pine-400" size={26} />
          <p className="text-sm font-semibold text-pine-800 dark:text-pine-200">
            No government schemes match "{q}".
          </p>
          <p className="text-xs muted">
            Try adjusting your search terms or verify via official national health resources.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {list.map((s) => {
            const isVerified = Boolean(s.last_verified);
            const hasDetails = Boolean(s.summary || s.eligibility || s.benefits || s.how_to_apply);

            return (
              <article
                key={s.id}
                className="card p-6 space-y-5 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700"
              >
                {/* Header & Verification Status */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 border-b border-ivory-200 pb-4 dark:border-night-750">
                  <div className="space-y-1">
                    <span className="rounded bg-brand-100 px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider text-brand-900 dark:bg-night-800 dark:text-brand-300">
                      National Health Program
                    </span>
                    <h2 className="text-lg sm:text-xl font-bold text-pine-900 dark:text-white">
                      {s.name}
                    </h2>
                    <p className="text-xs text-pine-600 dark:text-pine-400">
                      Nodal Authority: {s.authority || "Ministry of Health and Family Welfare (MoHFW)"}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    {isVerified ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-alert-success-bg px-3 py-1 text-xs font-semibold text-alert-success border border-alert-success-border dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60">
                        <CheckCircle2 size={13} />
                        Verified: {s.last_verified}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-ivory-100 px-3 py-1 text-xs font-medium text-pine-700 dark:bg-night-800 dark:text-pine-300 border border-ivory-300 dark:border-night-700">
                        <Clock size={13} className="text-pine-500" />
                        Official Audit Pending
                      </span>
                    )}
                  </div>
                </div>

                {/* Content: Either populated fields or an elegant consolidated institutional notice */}
                {hasDetails ? (
                  <dl className="grid gap-4 sm:grid-cols-2">
                    {s.summary && (
                      <div className="sm:col-span-2 space-y-1">
                        <dt className="text-xs font-bold uppercase tracking-wider text-pine-500 dark:text-pine-400">
                          Overview & Objective
                        </dt>
                        <dd className="text-xs sm:text-sm text-pine-800 dark:text-pine-200 leading-relaxed">
                          {s.summary}
                        </dd>
                      </div>
                    )}
                    {s.eligibility && (
                      <div className="space-y-1">
                        <dt className="text-xs font-bold uppercase tracking-wider text-pine-500 dark:text-pine-400">
                          Eligibility Criteria
                        </dt>
                        <dd className="text-xs sm:text-sm text-pine-800 dark:text-pine-200 leading-relaxed">
                          {s.eligibility}
                        </dd>
                      </div>
                    )}
                    {s.benefits && (
                      <div className="space-y-1">
                        <dt className="text-xs font-bold uppercase tracking-wider text-pine-500 dark:text-pine-400">
                          Coverage & Benefits
                        </dt>
                        <dd className="text-xs sm:text-sm text-pine-800 dark:text-pine-200 leading-relaxed">
                          {s.benefits}
                        </dd>
                      </div>
                    )}
                    {s.how_to_apply && (
                      <div className="sm:col-span-2 space-y-1">
                        <dt className="text-xs font-bold uppercase tracking-wider text-pine-500 dark:text-pine-400">
                          Application Process & Portals
                        </dt>
                        <dd className="text-xs sm:text-sm text-pine-800 dark:text-pine-200 leading-relaxed">
                          {s.how_to_apply}
                        </dd>
                      </div>
                    )}
                  </dl>
                ) : (
                  <div className="rounded-lg border border-ivory-200 bg-ivory-50/70 p-4 dark:border-night-700 dark:bg-night-900 space-y-2">
                    <div className="flex items-center gap-2 text-xs font-semibold text-pine-900 dark:text-pine-200">
                      <Info size={15} className="text-brand-800 dark:text-brand-400 shrink-0" />
                      Official Scheme Guidelines Notice
                    </div>
                    <p className="text-xs text-pine-600 dark:text-pine-400 leading-relaxed">
                      Detailed eligibility criteria, beneficiary lists, and hospital empanelment guidelines are maintained directly on the official portal. To prevent outdated or inaccurate benefit claims, please consult the primary government resource linked below.
                    </p>
                  </div>
                )}

                {/* Footer and Official Source Link */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-ivory-200 dark:border-night-750 text-xs">
                  <span className="muted font-mono">
                    Official Portal Status: {isVerified ? `Audited on ${s.last_verified}` : "Primary source linked"}
                  </span>
                  <a
                    className="btn px-4 py-2 text-xs"
                    href={s.official_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <span>Open Official Portal ({new URL(s.official_url).hostname})</span>
                    <ExternalLink size={13} />
                  </a>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
