export const SAMPLES = [
  "Explain Ayushman Bharat PM-JAY.",
  "Institutional births in Kerala.",
  "Compare healthcare indicators across districts.",
  "Show me available maternal healthcare statistics in Uttar Pradesh.",
  "What is the anaemia prevalence in pregnancy in Bihar?",
];

export const TECH_STACK = [
  { name: "Python FastAPI", category: "Backend Framework" },
  { name: "Pandas & NumPy", category: "Data Processing" },
  { name: "Qwen3-1.7B", category: "Base SLM" },
  { name: "QLoRA (PEFT)", category: "Fine-Tuning" },
  { name: "React 18 & TypeScript", category: "Frontend Core" },
  { name: "Tailwind CSS", category: "Design System" },
  { name: "Recharts", category: "Visualizations" },
];

export const WORKFLOW_STEPS = [
  {
    step: "01",
    title: "User Query",
    desc: "Natural-language query expressing indicator or health questions",
  },
  {
    step: "02",
    title: "Location & Intent Detection",
    desc: "Rule-based entity extraction for 41 States/UTs and 800 Districts",
  },
  {
    step: "03",
    title: "Keyword & Filter Retrieval",
    desc: "Indexed search over 1.18M records across HMIS, NFHS-5, AHS",
  },
  {
    step: "04",
    title: "Grounded SLM Inference",
    desc: "Strict context evidence grounding using Qwen3-1.7B (or dataset mode)",
  },
  {
    step: "05",
    title: "Transparent Sourced Output",
    desc: "Answer coupled with verified records table & interactive charts",
  },
];
