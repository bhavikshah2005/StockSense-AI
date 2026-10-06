import { useId } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { PatternBlock, SeriesPoint, ZoneBlock } from "../../types/technical.ts";
import { formatInr, formatVolume } from "../../utils/quote.ts";

type Row = {
  label: string;
  timestamp: string;
  close: number;
  closeText: string;
  sma20: number | null;
  sma50: number | null;
  upper: number | null;
  lower: number | null;
  volume: number | null;
};

export function TechnicalChart({
  series,
  pattern,
  zones,
  showAverages,
  showPattern,
  showZones,
}: {
  series: SeriesPoint[];
  pattern: PatternBlock | null;
  zones: ZoneBlock[];
  showAverages: boolean;
  showPattern: boolean;
  showZones: boolean;
}) {
  const gradientId = useId().replace(/:/g, "");
  const rows = series.map((point) => toRow(point, showPattern ? pattern : null));
  const rising = rows.length > 1 && rows[rows.length - 1].close >= rows[0].close;
  const stroke = rising ? "#047857" : "#b91c1c";
  const zoneBands = showZones ? zones.slice(0, 3) : [];
  return (
    <div className="h-72 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} minTickGap={28} />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "#64748b" }} width={72} tickFormatter={(value: number) => value.toLocaleString("en-IN")} />
          <Tooltip content={<ChartTooltip />} />
          {zoneBands.map((zone) => (
            <ReferenceArea
              key={`${zone.kind}-${zone.lower}`}
              y1={Number(zone.lower)}
              y2={Number(zone.upper)}
              fill={zone.kind === "support" ? "#047857" : "#b45309"}
              fillOpacity={0.08}
              ifOverflow="extendDomain"
            />
          ))}
          <Area type="monotone" dataKey="close" stroke={stroke} fill={`url(#${gradientId})`} strokeWidth={2} dot={false} />
          {showAverages ? <Line type="monotone" dataKey="sma20" stroke="#1d4ed8" strokeWidth={1.5} dot={false} connectNulls name="SMA 20" /> : null}
          {showAverages ? <Line type="monotone" dataKey="sma50" stroke="#b45309" strokeWidth={1.5} dot={false} connectNulls name="SMA 50" /> : null}
          {showPattern ? <Line type="linear" dataKey="upper" stroke="#7c3aed" strokeDasharray="4 4" strokeWidth={1.5} dot={false} connectNulls name="Upper boundary" /> : null}
          {showPattern ? <Line type="linear" dataKey="lower" stroke="#0f766e" strokeDasharray="4 4" strokeWidth={1.5} dot={false} connectNulls name="Lower boundary" /> : null}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function toRow(point: SeriesPoint, pattern: PatternBlock | null): Row {
  const close = Number(point.close);
  return {
    label: new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", timeZone: "Asia/Kolkata" }).format(new Date(point.timestamp)),
    timestamp: point.timestamp,
    close,
    closeText: formatInr(point.close) ?? point.close,
    sma20: point.sma_20 === null ? null : Number(point.sma_20),
    sma50: point.sma_50 === null ? null : Number(point.sma_50),
    upper: boundaryAt(pattern, "upper", point.timestamp) ?? boundaryAt(pattern, "neckline", point.timestamp),
    lower: boundaryAt(pattern, "lower", point.timestamp),
    volume: point.volume,
  };
}

function boundaryAt(pattern: PatternBlock | null, name: string, timestamp: string): number | null {
  const points = pattern?.boundaries[name];
  if (!points) {
    return null;
  }
  const match = points.find((point) => point.timestamp === timestamp);
  return match ? Number(match.price) : null;
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload?: Row }> }) {
  if (!active || !payload?.length || !payload[0]?.payload) {
    return null;
  }
  const row = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm">
      <p className="font-medium text-slate-900">{row.label}</p>
      <p>Close: {row.closeText}</p>
      {row.volume !== null ? <p>Volume: {formatVolume(row.volume)}</p> : null}
    </div>
  );
}
