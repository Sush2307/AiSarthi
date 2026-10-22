import {
  ArrowRight,
  Brain,
  Cpu,
  Database,
  FileCheck2,
  Layers,
  Lightbulb,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { TECH_STACK, WORKFLOW_STEPS } from "../constants";

export default function About() {
  return (
    <div className="space-y-8 w-full">
      {/* Title */}
      <div>
        <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-brand-800 dark:text-brand-400 mb-1.5">
          <Brain size={14} />
          System Architecture & Documentation
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-pine-900 dark:text-white">
          About AI Sarthi (GovHealth-SLM)
        </h1>
        <p className="muted text-xs sm:text-sm mt-1 leading-relaxed">
          An open healthcare intelligence assistant engineered to make Indian public healthcare statistics accessible, searchable, and strictly grounded in official records.
        </p>
      </div>

      {/* Visual Pipeline Flow */}
      <section className="card p-6 space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
        <h2 className="text-sm sm:text-base font-bold text-pine-900 dark:text-white flex items-center gap-2">
          <Sparkles size={16} className="text-brand-800 dark:text-brand-400" />
          End-to-End Evidence Retrieval Pipeline
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {WORKFLOW_STEPS.map((w, idx) => (
            <div
              key={w.step}
              className="relative flex flex-col justify-between rounded-lg border border-ivory-200 bg-ivory-50/70 p-4 dark:border-night-800 dark:bg-night-900"
            >
              <div className="space-y-1.5">
                <span className="font-mono text-xs font-bold text-brand-800 dark:text-brand-400">{w.step}</span>
                <h4 className="text-xs font-bold text-pine-900 dark:text-white">{w.title}</h4>
                <p className="text-[11px] muted leading-relaxed">{w.desc}</p>
              </div>
              {idx < WORKFLOW_STEPS.length - 1 && (
                <div className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 z-10 text-brand-600 dark:text-brand-400">
                  <ArrowRight size={13} />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Core Documentation Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Problem Statement */}
        <section className="card p-6 space-y-3 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
          <div className="flex items-center gap-2 text-brand-800 dark:text-brand-400 font-bold text-sm">
            <Lightbulb size={16} />
            Problem Statement
          </div>
          <p className="text-xs sm:text-sm text-pine-700 dark:text-pine-300 leading-relaxed">
            Public healthcare data in India (HMIS, NFHS-5, AHS) is extensive but dispersed across thousands of large tabular reports. Healthcare researchers, local administrators, and civil society actors often struggle to quickly extract district-level statistics or correlate metrics across years without custom statistical software.
          </p>
        </section>

        {/* Project Objectives */}
        <section className="card p-6 space-y-3 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
          <div className="flex items-center gap-2 text-brand-800 dark:text-brand-400 font-bold text-sm">
            <FileCheck2 size={16} />
            Core Objectives
          </div>
          <ul className="text-xs sm:text-sm text-pine-700 dark:text-pine-300 space-y-1.5 list-disc list-inside leading-relaxed">
            <li>Enable natural-language inquiries over 1.18M+ Indian public health records.</li>
            <li>Eliminate hallucinations by bounding SLM responses to retrieved evidence.</li>
            <li>Maintain full transparency: every figure is attributed to source, year, and district.</li>
            <li>Provide reliable dataset fallback when GPU or AI weights are offline.</li>
          </ul>
        </section>

        {/* Dataset & Retrieval */}
        <section className="card p-6 space-y-3 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
          <div className="flex items-center gap-2 text-brand-800 dark:text-brand-400 font-bold text-sm">
            <Database size={16} />
            Master Healthcare Dataset
          </div>
          <div className="text-xs sm:text-sm text-pine-700 dark:text-pine-300 space-y-2 leading-relaxed">
            <p>
              The backend indexes <code className="font-mono text-brand-800 dark:text-brand-400 font-semibold">healthcare_master_final_v3.csv</code> (~195 MB), comprising over <b>1,180,313 records</b>:
            </p>
            <ul className="list-disc list-inside text-xs space-y-1 muted">
              <li><b>HMIS:</b> Health Management Information System (919,394 rows)</li>
              <li><b>AHS:</b> Annual Health Survey (181,760 rows)</li>
              <li><b>NFHS-5:</b> National Family Health Survey 2019–2021 (75,649 rows)</li>
              <li><b>Hospital Directory:</b> Infrastructure and facility catalog (3,510 rows)</li>
            </ul>
          </div>
        </section>

        {/* Model Architecture */}
        <section className="card p-6 space-y-3 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
          <div className="flex items-center gap-2 text-brand-800 dark:text-brand-400 font-bold text-sm">
            <Cpu size={16} />
            Model & SLM Inference Architecture
          </div>
          <div className="text-xs sm:text-sm text-pine-700 dark:text-pine-300 space-y-2 leading-relaxed">
            <p>
              <b>Base Model:</b> Qwen/Qwen3-1.7B fine-tuned with a domain-adapted <b>QLoRA</b> adapter (PEFT).
            </p>
            <ul className="list-disc list-inside text-xs space-y-1 muted">
              <li><b>GPU Mode:</b> 4-bit NormalFloat (NF4) quantization with FP16 compute for edge deployment.</li>
              <li><b>CPU Fallback:</b> Full-precision CPU execution when no NVIDIA GPU is detected.</li>
              <li><b>Dataset Mode:</b> Gracefully serves raw verified records when weights are unmounted.</li>
            </ul>
          </div>
        </section>
      </div>

      {/* Technology Stack Badges */}
      <section className="card p-6 space-y-4 bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
        <h3 className="font-bold text-xs sm:text-sm text-pine-900 dark:text-white flex items-center gap-2">
          <Layers size={16} className="text-brand-800 dark:text-brand-400" />
          Technical Stack
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
          {TECH_STACK.map((t) => (
            <div
              key={t.name}
              className="rounded-lg border border-ivory-200 bg-ivory-50/70 p-3 text-center dark:border-night-800 dark:bg-night-900"
            >
              <div className="font-semibold text-xs text-pine-900 dark:text-white truncate">
                {t.name}
              </div>
              <div className="text-[10px] muted truncate">{t.category}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Limitations and Responsible AI */}
      <section className="rounded-xl p-6 space-y-3.5 border border-amber-300 bg-amber-50/80 dark:border-amber-700/60 dark:bg-amber-950/30 transition-colors">
        <div className="flex items-center gap-2 text-amber-900 dark:text-amber-300 font-bold text-xs sm:text-sm">
          <ShieldAlert size={18} className="text-amber-700 dark:text-amber-400 shrink-0" />
          Responsible Use & Research Limitations
        </div>
        <div className="text-xs sm:text-sm text-amber-950/90 dark:text-amber-100/95 space-y-2.5 leading-relaxed">
          <p>
            <strong className="font-semibold text-amber-950 dark:text-white">1. Lexical Scoring Scope:</strong> Keyword retrieval may occasionally miss regional synonyms or clinical abbreviations. Ongoing iterations are evaluating dense vector embeddings.
          </p>
          <p>
            <strong className="font-semibold text-amber-950 dark:text-white">2. Anonymized Public Data:</strong> The system indexes exclusively public aggregate survey records; no identifiable patient records are stored or processed.
          </p>
          <p>
            <strong className="font-semibold text-amber-950 dark:text-white">3. Policy Guidelines:</strong> Welfare scheme eligibility changes per central and state gazettes; consult primary government resources before submitting claims.
          </p>
        </div>
      </section>
    </div>
  );
}
