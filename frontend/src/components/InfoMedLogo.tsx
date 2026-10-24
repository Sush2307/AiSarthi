import React from "react";

interface InfoMedLogoProps {
  size?: number | string;
  className?: string;
  showText?: boolean;
  textSize?: "sm" | "md" | "lg" | "xl";
  subtext?: string;
}

export function InfoMedIcon({ size = 32, className = "" }: { size?: number | string; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 transition-transform duration-200 group-hover:scale-105 ${className}`}
      aria-label="InfoMed Logo Icon"
    >
      <defs>
        <linearGradient id="infomedIconBg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#064E3B" />
          <stop offset="50%" stopColor="#0F766E" />
          <stop offset="100%" stopColor="#047857" />
        </linearGradient>
        <linearGradient id="infomedCross" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="100%" stopColor="#E6FFFA" />
        </linearGradient>
        <linearGradient id="infomedPulse" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#34D399" />
          <stop offset="50%" stopColor="#22D3EE" />
          <stop offset="100%" stopColor="#67E8F9" />
        </linearGradient>
        <filter id="infomedGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="10" floodColor="#064E3B" floodOpacity="0.4" />
        </filter>
      </defs>

      {/* Rounded Squircle Background */}
      <rect x="32" y="32" width="448" height="448" rx="112" fill="url(#infomedIconBg)" filter="url(#infomedGlow)" />
      <rect x="34" y="34" width="444" height="444" rx="110" fill="none" stroke="#34D399" strokeWidth="4" strokeOpacity="0.35" />

      {/* The Information "i" Dot */}
      <circle cx="256" cy="144" r="28" fill="#A7F3D0" />
      <circle cx="256" cy="144" r="14" fill="#047857" />

      {/* Medical Cross Vertical Pillar */}
      <rect x="220" y="196" width="72" height="196" rx="36" fill="url(#infomedCross)" />
      {/* Medical Cross Horizontal Arm */}
      <rect x="148" y="244" width="216" height="72" rx="36" fill="url(#infomedCross)" />

      {/* Live ECG Pulse Wave */}
      <path
        d="M 124 280 L 192 280 L 220 236 L 244 324 L 272 250 L 296 280 L 388 280"
        fill="none"
        stroke="url(#infomedPulse)"
        strokeWidth="14"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function InfoMedLogo({
  size = 36,
  className = "",
  showText = true,
  textSize = "md",
  subtext = "GovHealth-SLM",
}: InfoMedLogoProps) {
  const textClass = {
    sm: "text-base",
    md: "text-lg sm:text-xl",
    lg: "text-2xl",
    xl: "text-3xl",
  }[textSize];

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <InfoMedIcon size={size} />
      {showText && (
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className={`font-black tracking-tight ${textClass} leading-tight text-pine-900 dark:text-white`}>
              Info<span className="text-brand-700 dark:text-brand-400">Med</span>
            </span>
            {subtext && (
              <span className="rounded bg-ivory-200 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wider text-brand-900 dark:bg-[#1D2D27] dark:text-[#A2C7B1]">
                {subtext}
              </span>
            )}
          </div>
          <p className="text-[11px] text-pine-500 dark:text-[#ABC1B7] hidden sm:block">
            Indian Public Healthcare Intelligence Platform
          </p>
        </div>
      )}
    </div>
  );
}

export default InfoMedLogo;
