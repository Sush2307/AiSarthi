import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Activity, BarChart3, Database, FileText, FlaskConical, Info, Menu, MessageSquare, Moon, Sun, X } from "lucide-react";
import { useApi } from "../context";
import { Disclaimer } from "./common";

const links = [
  { to: "/", label: "Home", icon: Activity },
  { to: "/chat", label: "AI Chat", icon: MessageSquare },
  { to: "/explorer", label: "Data Explorer", icon: Database },
  { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { to: "/workspace", label: "Workspace", icon: FlaskConical },
  { to: "/schemes", label: "Schemes", icon: FileText },
  { to: "/about", label: "About", icon: Info },
];

export function ModeBadge() {
  const { live, modelLoaded, checking, recordsCount } = useApi();

  if (checking) {
    return (
      <div className="inline-flex h-7 items-center gap-1.5 rounded-full border border-ivory-300 bg-ivory-100 px-3 text-xs font-medium text-pine-600 dark:border-night-700 dark:bg-night-800 dark:text-pine-300 min-w-[125px] justify-center">
        <span className="h-1.5 w-1.5 rounded-full bg-pine-400 animate-pulse" />
        Checking API…
      </div>
    );
  }

  if (!live) {
    return (
      <div className="inline-flex h-7 items-center gap-1.5 rounded-full border border-alert-warning-border bg-alert-warning-bg px-3 text-xs font-semibold text-alert-warning shadow-subtle dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-300 min-w-[155px] justify-center">
        <span className="h-1.5 w-1.5 rounded-full bg-alert-warning animate-pulse" />
        Demo Mode · Sample Data
      </div>
    );
  }

  if (modelLoaded) {
    return (
      <div className="inline-flex h-7 items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-3 text-xs font-semibold text-brand-800 shadow-subtle dark:border-brand-700/60 dark:bg-brand-950/70 dark:text-brand-300 min-w-[160px] justify-center">
        <span className="h-1.5 w-1.5 rounded-full bg-brand-600 animate-pulse" />
        Live · Dataset + AI Model
      </div>
    );
  }

  return (
    <div
      className="inline-flex h-7 items-center gap-1.5 rounded-full border border-brand-200 bg-brand-100 px-3 text-xs font-semibold text-brand-900 shadow-subtle dark:border-brand-700/60 dark:bg-brand-950/70 dark:text-brand-300 min-w-[145px] justify-center"
      title={`${recordsCount.toLocaleString()} records loaded in master dataset`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-brand-600 animate-pulse" />
      Live · Dataset Only
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const [dark, setDark] = useState(() => {
    try {
      const t = localStorage.getItem("theme");
      if (t) return t === "dark";
    } catch {
      /* ignore */
    }
    // Default to the new Forest & Ivory light theme
    return false;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("theme", dark ? "dark" : "light");
    } catch {
      /* ignore */
    }
  }, [dark]);

  // Close mobile nav on route change
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs sm:text-sm font-medium transition-all duration-150 ${
      isActive
        ? "bg-brand-100 text-brand-900 font-semibold border border-brand-200/90 shadow-subtle dark:bg-[#1D2D27] dark:text-[#A2C7B1] dark:border-[#2D3F37]"
        : "text-pine-600 hover:bg-ivory-200 hover:text-pine-900 dark:text-[#ABC1B7] dark:hover:bg-[#16231E] dark:hover:text-white"
    }`;

  return (
    <div className="flex min-h-screen flex-col bg-ivory-100 text-pine-900 dark:bg-[#0A110E] dark:text-[#EDF4F0] transition-colors">
      {/* Sticky Header with fixed height to eliminate vertical layout jumps */}
      <header className="sticky top-0 z-30 h-16 border-b border-ivory-300 bg-white/95 backdrop-blur-md dark:border-[#2D3F37] dark:bg-[#101A16]/95 shadow-subtle transition-colors">
        <div className="mx-auto flex h-full max-w-page items-center justify-between gap-4 px-4 sm:px-8 lg:px-12 w-full">
          {/* Logo / Brand */}
          <Link
            to="/"
            className="flex items-center gap-3 shrink-0 focus-visible:rounded-lg focus-visible:outline-none"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-800 text-white shadow-subtle">
              <Activity size={18} className="stroke-[2.5]" aria-hidden />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold tracking-tight text-pine-900 dark:text-white text-base sm:text-lg">
                  AI Sarthi
                </span>
                <span className="rounded bg-ivory-200 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wider text-brand-900 dark:bg-[#1D2D27] dark:text-[#A2C7B1]">
                  GovHealth-SLM
                </span>
              </div>
              <p className="text-[11px] text-pine-500 dark:text-[#ABC1B7] hidden sm:block">
                Indian Public Healthcare Intelligence Platform
              </p>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav aria-label="Main" className="hidden md:flex items-center gap-1.5">
            {links.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === "/"} className={navLinkClass}>
                <Icon size={15} aria-hidden />
                {label}
              </NavLink>
            ))}
          </nav>

          {/* Right Controls */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="hidden lg:block">
              <ModeBadge />
            </div>

            {/* Dark Mode Toggle */}
            <button
              className="btn-o h-8 w-8 p-0 flex items-center justify-center rounded-lg"
              onClick={() => setDark(!dark)}
              aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
              title={dark ? "Switch to Forest & Ivory light theme" : "Switch to institutional dark theme"}
            >
              {dark ? <Sun size={15} className="text-amber-400" /> : <Moon size={15} className="text-pine-600" />}
            </button>

            {/* Mobile Menu Toggle */}
            <button
              className="btn-o h-8 w-8 p-0 flex items-center justify-center md:hidden rounded-lg"
              onClick={() => setOpen(!open)}
              aria-label="Toggle navigation menu"
              aria-expanded={open}
            >
              {open ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {open && (
          <div className="border-t border-ivory-300 bg-white/98 p-4 dark:border-[#2D3F37] dark:bg-[#101A16]/98 md:hidden shadow-elevated">
            <div className="mb-3">
              <ModeBadge />
            </div>
            <nav aria-label="Mobile" className="flex flex-col gap-1.5">
              {links.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} end={to === "/"} className={navLinkClass}>
                  <Icon size={16} aria-hidden />
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
        )}
      </header>

      {/* Main Page Body */}
      <main className="mx-auto w-full max-w-page flex-1 px-4 sm:px-8 lg:px-12 py-6 sm:py-8 min-h-[calc(100vh-14rem)]">
        {children}
      </main>

      {/* Institutional Footer */}
      <footer className="border-t border-ivory-300 bg-white/70 dark:border-[#2D3F37] dark:bg-[#0A110E]/90 py-8 mt-12 transition-colors">
        <div className="mx-auto max-w-page px-4 sm:px-8 lg:px-12 space-y-5 w-full">
          <Disclaimer />
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs muted pt-3 border-t border-ivory-200 dark:border-[#2D3F37]">
            <p>
              <b className="text-pine-900 dark:text-[#EDF4F0]">AI Sarthi (GovHealth-SLM)</b> · National Public Healthcare Retrieval & Grounded Intelligence.
            </p>
            <p className="font-mono text-pine-500 dark:text-[#ABC1B7]">
              HMIS · NFHS-5 · AHS · Qwen3-1.7B QLoRA · FastAPI · React 18
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
