import { useId } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type ChartPoint = {
  time: number;
  label: string;
  close: number;
  openText: string;
  highText: string;
  lowText: string;
  closeText: string;
  volume: number | null;
  volumeText: string | null;
};

type TooltipProps = {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: ChartPoint }>;
};

export function StockPriceChart({ points, rising }: { points: ChartPoint[]; rising: boolean }) {
  const gradientId = useId().replace(/:/g, "");
  const stroke = rising ? "#047857" : "#b91c1c";
  const showVolume = points.some((point) => point.volume !== null);
  return (
    <div className="space-y-2">
      <div className="h-64 w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} minTickGap={28} />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "#64748b" }}
              width={64}
              tickFormatter={(value: number) => value.toLocaleString("en-IN")}
            />
            <Tooltip content={<PriceTooltip />} />
            <Area type="monotone" dataKey="close" stroke={stroke} fill={`url(#${gradientId})`} strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      {showVolume ? (
        <div className="h-20 w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={points} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="label" hide />
              <YAxis hide />
              <Tooltip content={<VolumeTooltip />} />
              <Bar dataKey="volume" fill="#94a3b8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : null}
    </div>
  );
}

function PriceTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length || !payload[0]?.payload) {
    return null;
  }
  const point = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm">
      <p className="font-medium text-slate-900">{point.label}</p>
      <p>Open: {point.openText}</p>
      <p>High: {point.highText}</p>
      <p>Low: {point.lowText}</p>
      <p>Close: {point.closeText}</p>
      {point.volumeText ? <p>Volume: {point.volumeText}</p> : null}
    </div>
  );
}

function VolumeTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length || !payload[0]?.payload?.volumeText) {
    return null;
  }
  const point = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm">
      <p>{point.label}</p>
      <p>Volume: {point.volumeText}</p>
    </div>
  );
}
