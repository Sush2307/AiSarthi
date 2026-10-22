import { AlertTriangle, Download, Info } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HealthRecord } from "../types";

export const Disclaimer = () => (
  <aside
    role="note"
    aria-label="Medical disclaimer"
    className="flex items-start gap-3 rounded-xl border border-alert-warning-border bg-alert-warning-bg p-4 text-xs leading-relaxed text-alert-warning shadow-subtle dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300 transition-colors"
  >
    <div className="rounded-md bg-amber-100/90 dark:bg-amber-900/50 p-1 text-alert-warning dark:text-amber-400 shrink-0 mt-0.5">
      <AlertTriangle size={15} aria-hidden />
    </div>
    <div>
      <span className="font-bold block text-pine-950 dark:text-amber-200 mb-0.5">
        Medical & Public Policy Information Notice
      </span>
      <span className="text-amber-900 dark:text-amber-200/90">
        This platform is an informational public-health analytics tool, not a clinical diagnostic system. It does not provide medical advice, diagnosis, or clinical prescriptions. Statistics are derived directly from published aggregate government datasets (HMIS, NFHS-5, AHS). Always consult licensed medical professionals for healthcare decisions.
      </span>
    </div>
  </aside>
);

export const loc = (r: HealthRecord) => r.district || r.state;
const numeric = (rs: HealthRecord[]) => rs.filter((r) => typeof r.value === "number");

export function RecordsTable({
  records,
  max = 100,
}: {
  records: HealthRecord[];
  max?: number;
}) {
  if (!records.length) {
    return (
      <div className="py-12 text-center">
        <Info className="mx-auto mb-2 text-pine-400" size={24} />
        <p className="text-sm font-semibold text-pine-800 dark:text-pine-200">No matching healthcare records found.</p>
        <p className="muted text-xs mt-1">Try broadening your search term or adjusting location/year filters.</p>
      </div>
    );
  }

  const displayed = records.slice(0, max);

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-lg border border-ivory-300 dark:border-night-700">
        <table className="w-full text-left text-xs sm:text-sm border-collapse">
          <thead>
            <tr className="border-b border-ivory-300 bg-ivory-50 text-[11px] font-semibold uppercase tracking-wider text-pine-600 dark:border-night-700 dark:bg-night-900 dark:text-pine-300">
              <th className="px-3.5 py-2.5">Location</th>
              <th className="px-3.5 py-2.5">Indicator</th>
              <th className="px-3.5 py-2.5 text-center">Year</th>
              <th className="px-3.5 py-2.5 text-right">Value</th>
              <th className="px-3.5 py-2.5 text-center">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ivory-200 dark:divide-night-800 bg-white dark:bg-night-850">
            {displayed.map((r, i) => (
              <tr
                key={i}
                className="transition-colors hover:bg-ivory-50/80 dark:hover:bg-night-800/60"
              >
                <td className="whitespace-nowrap px-3.5 py-2.5 font-medium text-pine-900 dark:text-pine-100">
                  {loc(r)}
                  {r.district && r.state && r.district !== r.state && (
                    <span className="muted text-xs font-normal ml-1">· {r.state}</span>
                  )}
                </td>
                <td className="px-3.5 py-2.5 text-pine-800 dark:text-pine-200">
                  <div className="max-w-md line-clamp-2 leading-snug" title={r.indicator}>
                    {r.indicator.replace(/_/g, " ")}
                  </div>
                </td>
                <td className="whitespace-nowrap px-3.5 py-2.5 text-center text-xs text-pine-500 dark:text-pine-400 font-mono">
                  {r.year ?? "–"}
                </td>
                <td className="whitespace-nowrap px-3.5 py-2.5 text-right font-mono font-bold text-pine-900 dark:text-white tabular-nums">
                  {r.value !== null && r.value !== undefined ? r.value.toLocaleString() : "n/a"}
                </td>
                <td className="whitespace-nowrap px-3.5 py-2.5 text-center">
                  <span className="inline-block rounded bg-brand-100 px-2 py-0.5 text-[11px] font-medium text-brand-900 dark:bg-brand-950 dark:text-brand-300 border border-brand-200 dark:border-brand-800">
                    {r.source}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {records.length > max && (
        <p className="text-right text-xs muted font-mono">
          Showing first {max} of {records.length.toLocaleString()} matching records
        </p>
      )}
    </div>
  );
}

export function CompareBar({
  records,
  height = 320,
  showContext = true,
}: {
  records: HealthRecord[];
  height?: number;
  showContext?: boolean;
}) {
  // Methodological comparability: ensure observations represent the same indicator
  const validNumeric = numeric(records);
  const indCounts = new Map<string, number>();
  validNumeric.forEach((r) => {
    if (r.indicator) indCounts.set(r.indicator, (indCounts.get(r.indicator) || 0) + 1);
  });
  const topInd = [...indCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  const comparableRecords = topInd ? validNumeric.filter((r) => r.indicator === topInd) : validNumeric;

  const data = comparableRecords
    .slice(0, 10)
    .map((r) => {
      const locationName = loc(r) || "Record";
      const unit = r.unit || (r.indicator.includes("percent") || r.indicator.includes("%") ? "%" : "");
      return {
        name: locationName.length > 20 ? locationName.slice(0, 18) + "…" : locationName,
        fullName: locationName,
        state: r.state || "",
        value: +(r.value as number).toFixed(2),
        indicator: r.display_label || r.indicator.replace(/_/g, " "),
        year: r.year ?? "",
        source: r.source ?? "",
        unit,
      };
    });

  if (!data.length) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-ivory-300 dark:border-night-700 bg-ivory-50/50 dark:bg-night-900/50">
        <p className="muted text-xs sm:text-sm font-medium">No numeric indicator values available to compare.</p>
      </div>
    );
  }

  // Ensure comfortable bar spacing without label overlapping
  const chartHeight = Math.max(height, data.length * 32 + 50);
  const unitStr = data[0]?.unit || "";

  return (
    <div className="w-full min-w-0 space-y-2 text-pine-800 dark:text-pine-200">
      {showContext && data[0]?.indicator && (
        <div className="flex flex-wrap items-center justify-between text-[11px] px-1 text-pine-600 dark:text-pine-400 border-b border-ivory-200/60 dark:border-night-750/60 pb-1.5">
          <span className="truncate max-w-[80%]">
            Indicator: <span className="font-semibold text-pine-900 dark:text-white capitalize">{data[0].indicator}</span>
          </span>
          {unitStr && (
            <span className="font-mono text-[10px] bg-ivory-200/80 dark:bg-night-800 text-pine-700 dark:text-emerald-300 px-1.5 py-0.5 rounded font-bold">
              Unit: {unitStr}
            </span>
          )}
        </div>
      )}

      <div style={{ height: chartHeight }} className="w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 6, right: 48, left: 10, bottom: 6 }}
          >
            <defs>
              <linearGradient id="sarthiBarGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#0d9488" stopOpacity={0.88} />
                <stop offset="100%" stopColor="#059669" stopOpacity={1} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="currentColor"
              opacity={0.12}
              horizontal={false}
              vertical={true}
            />
            <XAxis
              type="number"
              domain={[0, (dataMax: number) => (dataMax > 0 ? Math.ceil(dataMax * 1.15) : 100)]}
              tick={{ fontSize: 10, fill: "currentColor" }}
              tickLine={false}
              axisLine={{ stroke: "currentColor", opacity: 0.2 }}
              className="text-pine-500 dark:text-pine-400 font-mono"
            />
            <YAxis
              type="category"
              dataKey="name"
              interval={0}
              width={130}
              tick={{ fontSize: 11, fill: "currentColor" }}
              tickLine={false}
              axisLine={{ stroke: "currentColor", opacity: 0.2 }}
              className="text-pine-800 dark:text-pine-200 font-medium"
            />
            <Tooltip
              cursor={{ fill: "rgba(16, 185, 129, 0.08)" }}
              contentStyle={{
                backgroundColor: "#0f231c",
                border: "1px solid #10b981",
                borderRadius: "0.5rem",
                fontSize: "0.75rem",
                color: "#f8fafc",
                boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.3)",
                padding: "8px 12px",
              }}
              formatter={(val: any, _name: any, props: any) => [
                `${Number(val ?? 0).toLocaleString()}${props?.payload?.unit ?? ""}`,
                "Recorded Value",
              ]}
              labelFormatter={(_label: any, payload: any) => {
                const item = payload?.[0]?.payload;
                if (!item) return String(_label ?? "");
                const stateInfo = item.state ? `, ${item.state}` : "";
                const cycleInfo = item.year ? ` • ${item.year}` : "";
                const sourceInfo = item.source ? ` (${item.source})` : "";
                return `${item.fullName}${stateInfo}${sourceInfo}${cycleInfo}`;
              }}
            />
            <Bar
              dataKey="value"
              fill="url(#sarthiBarGrad)"
              radius={[0, 5, 5, 0]}
              maxBarSize={22}
            >
              <LabelList
                dataKey="value"
                position="right"
                offset={8}
                className="fill-pine-900 dark:fill-pine-100 font-mono text-[11px] font-semibold"
                formatter={(v: any) => `${Number(v).toLocaleString()}${unitStr}`}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function TrendLine({
  records,
  height = 320,
}: {
  records: HealthRecord[];
  height?: number;
}) {
  const by = new Map<string, number[]>();
  numeric(records).forEach((r) => {
    if (r.year) {
      by.set(r.year, [...(by.get(r.year) ?? []), r.value as number]);
    }
  });

  const data = [...by]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([year, v]) => ({
      year,
      average: +(v.reduce((a, b) => a + b, 0) / v.length).toFixed(2),
      count: v.length,
    }));

  if (data.length < 2) {
    return (
      <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-ivory-300 dark:border-night-700 bg-ivory-50/50 dark:bg-night-900/50 p-6 text-center">
        <Info className="mx-auto mb-2 text-pine-400" size={20} />
        <p className="text-xs sm:text-sm font-semibold text-pine-800 dark:text-pine-200">
          Single Timepoint Observation
        </p>
        <p className="muted text-xs mt-1 max-w-sm">
          The filtered dataset records share one survey or reporting cycle ({data[0]?.year ?? "current"}). A longitudinal trend line requires records spanning at least 2 distinct reporting years.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full min-w-0 text-pine-800 dark:text-pine-200" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 16, right: 28, left: -5, bottom: 12 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.12} vertical={false} />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 11, fill: "currentColor" }}
            tickLine={false}
            axisLine={{ stroke: "currentColor", opacity: 0.2 }}
            className="text-pine-500 dark:text-pine-400 font-mono"
          />
          <YAxis
            tick={{ fontSize: 11, fill: "currentColor" }}
            tickLine={false}
            axisLine={{ stroke: "currentColor", opacity: 0.2 }}
            className="text-pine-500 dark:text-pine-400 font-mono"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f231c",
              border: "1px solid #10b981",
              borderRadius: "0.5rem",
              fontSize: "0.75rem",
              color: "#f8fafc",
              boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.3)",
              padding: "8px 12px",
            }}
            formatter={(val: number, _name: any, props: any) => [
              `${val.toLocaleString()} (across ${props?.payload?.count ?? 1} records)`,
              "Annual Average",
            ]}
          />
          <Line
            type="monotone"
            dataKey="average"
            stroke="#059669"
            strokeWidth={3}
            dot={{ r: 4.5, fill: "#059669", strokeWidth: 2, stroke: "#ffffff" }}
            activeDot={{ r: 6.5, strokeWidth: 0, fill: "#10b981" }}
          >
            <LabelList
              dataKey="average"
              position="top"
              offset={10}
              className="fill-pine-900 dark:fill-pine-100 font-mono text-[10px] font-semibold"
              formatter={(v: any) => Number(v).toLocaleString()}
            />
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function exportCsv(records: HealthRecord[], name = "ai-sarthi-healthcare-data.csv") {
  const h = ["state", "district", "year", "indicator", "value", "source"] as const;
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = [h.join(","), ...records.map((r) => h.map((k) => esc(r[k])).join(","))].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

export const ExportIcon = Download;
