import { useEffect, useState } from "react";

import { TechnicalChart } from "../charts/TechnicalChart.tsx";
import { ApiError } from "../../services/http.ts";
import { getTechnicalAnalysis } from "../../services/stocks.ts";
import type { PatternBlock, TechnicalAnalysis } from "../../types/technical.ts";
import { formatInr, formatIst, formatSignedPercent, formatVolume } from "../../utils/quote.ts";

type Status = "loading" | "ready" | "error" | "unavailable";

const CATEGORY_LABELS: Record<TechnicalAnalysis["conclusion"]["category"], string> = {
  bullish_evidence: "Bullish evidence",
  bearish_evidence: "Bearish evidence",
  mixed_evidence: "Mixed evidence",
  no_clear_direction: "No clear direction",
  insufficient_data: "Insufficient data",
};

const STATUS_LABELS: Record<PatternBlock["status"], string> = {
  developing: "Developing",
  confirmed: "Confirmed",
  invalidated: "Invalidated",
  completed: "Completed",
  uncertain: "Uncertain",
  insufficient_data: "Insufficient data",
};

export function TechnicalWorkspace({ stockId }: { stockId: string }) {
  const [status, setStatus] = useState<Status>("loading");
  const [message, setMessage] = useState("");
  const [analysis, setAnalysis] = useState<TechnicalAnalysis | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [showAverages, setShowAverages] = useState(true);
  const [showPattern, setShowPattern] = useState(true);
  const [showZones, setShowZones] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setAnalysis(null);
    setSelectedKey(null);
    async function load() {
      try {
        const body = await getTechnicalAnalysis(stockId);
        if (cancelled) {
          return;
        }
        setAnalysis(body);
        setSelectedKey(body.patterns[0] ? patternKey(body.patterns[0]) : null);
        setStatus("ready");
      } catch (caught) {
        if (cancelled) {
          return;
        }
        if (caught instanceof ApiError && caught.status === 503) {
          setStatus("unavailable");
          setMessage("Price history is not available, so technical analysis cannot run.");
          return;
        }
        setStatus("error");
        setMessage("Technical analysis could not be loaded.");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [stockId]);

  if (status === "loading") {
    return <p className="text-sm text-slate-600">Loading technical analysis…</p>;
  }
  if (status === "unavailable" || status === "error" || !analysis) {
    return <p className="text-sm text-slate-700">{message}</p>;
  }
  const selected = analysis.patterns.find((pattern) => patternKey(pattern) === selectedKey) ?? null;
  return (
    <section className="space-y-6" aria-labelledby="technical-heading">
      <div className="space-y-2">
        <h2 id="technical-heading" className="text-lg font-semibold">
          Technical analysis
        </h2>
        <p className="text-sm text-slate-600">
          {analysis.stock.symbol} · {analysis.stock.exchange} · {analysis.interval} bars
        </p>
        <p className="text-sm text-slate-700">
          Evidence: {CATEGORY_LABELS[analysis.conclusion.category]}
          {analysis.freshness === "stale" ? " · Stale prices" : ""}
          {analysis.freshness === "insufficient" ? " · Insufficient history" : ""}
        </p>
        <p className="max-w-3xl text-sm text-slate-800">{analysis.conclusion.text}</p>
        <p className="text-xs text-slate-500">
          Last price {analysis.price_as_of ? formatIst(analysis.price_as_of) : "unavailable"} · Calculated{" "}
          {formatIst(analysis.calculated_at)}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Toggle pressed={showAverages} onClick={() => setShowAverages((value) => !value)} label="Moving averages" />
        <Toggle pressed={showPattern} onClick={() => setShowPattern((value) => !value)} label="Pattern boundaries" />
        <Toggle pressed={showZones} onClick={() => setShowZones((value) => !value)} label="Support and resistance" />
      </div>
      {analysis.series.length > 0 ? (
        <TechnicalChart
          series={analysis.series}
          pattern={selected}
          zones={analysis.zones}
          showAverages={showAverages}
          showPattern={showPattern}
          showZones={showZones}
        />
      ) : (
        <p className="text-sm text-slate-600">No price series is available for this window.</p>
      )}
      <p className="text-xs text-slate-500">
        The price line uses close. Blue is the 20-session average and amber is the 50-session average. Dashed lines are the selected pattern boundaries. Shaded bands are zones.
      </p>

      <div className="space-y-3">
        <h3 className="text-base font-semibold">Detected formations</h3>
        {analysis.patterns.length === 0 ? <p className="text-sm text-slate-600">No reliable pattern detected.</p> : null}
        <ul className="grid gap-3 md:grid-cols-2">
          {analysis.patterns.map((pattern) => {
            const key = patternKey(pattern);
            const selectedPattern = key === selectedKey;
            return (
              <li key={key}>
                <button
                  type="button"
                  aria-pressed={selectedPattern}
                  onClick={() => setSelectedKey(key)}
                  className={`w-full rounded-md border px-3 py-3 text-left ${selectedPattern ? "border-slate-900" : "border-slate-200"}`}
                >
                  <span className="block text-sm font-medium text-slate-900">{label(pattern.pattern_type)}</span>
                  <span className="mt-1 block text-xs text-slate-600">
                    {STATUS_LABELS[pattern.status]} · {label(pattern.direction)} · {pattern.quality} evidence
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
        {selected ? <PatternDetail pattern={selected} /> : null}
      </div>

      <IndicatorGroups indicators={analysis.indicators} />
      <ZoneList zones={analysis.zones} />
      <LimitationList limitations={analysis.limitations} freshness={analysis.freshness} />
    </section>
  );
}

function PatternDetail({ pattern }: { pattern: PatternBlock }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-700">
      <h3 className="font-medium text-slate-900">{label(pattern.pattern_type)}</h3>
      <p className="mt-2">{pattern.definition}</p>
      <p className="mt-2">Status: {STATUS_LABELS[pattern.status]}. Confirmation {pattern.confirmation_met ? "has" : "has not"} been met.</p>
      <p className="mt-2">{pattern.evidence}</p>
      <p className="mt-2">Invalidation: {pattern.invalidation}</p>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        {Object.entries(pattern.levels).map(([key, value]) => (
          <div key={key}>
            <dt className="text-xs text-slate-500">{label(key)}</dt>
            <dd>{formatLevel(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        {formatIst(pattern.start_timestamp)} to {formatIst(pattern.end_timestamp)} · Detector {pattern.detector_version}
      </p>
      <p className="mt-2 text-xs text-slate-500">A detected formation is an interpretation of historical prices. It does not predict the next price.</p>
    </div>
  );
}

function IndicatorGroups({ indicators }: { indicators: TechnicalAnalysis["indicators"] }) {
  const groups = [
    {
      title: "Trend",
      items: [
        ["SMA 20", indicators.sma_20, "Mean of the last 20 closes."],
        ["SMA 50", indicators.sma_50, "Mean of the last 50 closes."],
        ["SMA 100", indicators.sma_100, "Mean of the last 100 closes."],
        ["SMA 200", indicators.sma_200, "Mean of the last 200 closes."],
        ["EMA 20", indicators.ema_20, "20-session exponential average of close."],
        ["EMA 50", indicators.ema_50, "50-session exponential average of close."],
      ],
    },
    {
      title: "Momentum",
      items: [
        ["RSI 14", indicators.rsi_14, "Wilder relative strength over 14 sessions."],
        ["MACD", indicators.macd, "12-session EMA minus 26-session EMA."],
        ["MACD signal", indicators.macd_signal, "9-session EMA of the MACD line."],
        ["MACD histogram", indicators.macd_histogram, "MACD line minus the signal line."],
      ],
    },
    {
      title: "Volume",
      items: [
        ["Volume", indicators.volume === null ? null : String(indicators.volume), "Shares on the latest bar."],
        ["Average volume", indicators.average_volume, "Mean volume over 20 sessions."],
      ],
    },
    {
      title: "Volatility and range",
      items: [
        ["Historical volatility", indicators.volatility, "Annualized percent from 20 log returns. Not implied volatility."],
        ["52-week high", indicators.week52_high, "Highest high in the last 252 sessions."],
        ["52-week low", indicators.week52_low, "Lowest low in the last 252 sessions."],
      ],
    },
  ] as const;
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Indicators</h3>
      {groups.map((group) => (
        <div key={group.title}>
          <h4 className="text-sm font-medium text-slate-800">{group.title}</h4>
          <dl className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {group.items.map(([name, value, description]) => (
              <div key={name} className="rounded-md border border-slate-200 px-3 py-2" title={description}>
                <dt className="text-xs text-slate-500">{name}</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900">{displayIndicator(name, value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
      <p className="text-xs text-slate-500">As of {indicators.as_of ? formatIst(indicators.as_of) : "unavailable"}.</p>
    </div>
  );
}

function ZoneList({ zones }: { zones: TechnicalAnalysis["zones"] }) {
  return (
    <div className="space-y-2">
      <h3 className="text-base font-semibold">Support and resistance</h3>
      {zones.length === 0 ? <p className="text-sm text-slate-600">No zone has more than one observed swing reaction.</p> : null}
      <ul className="space-y-2">
        {zones.map((zone) => (
          <li key={`${zone.kind}-${zone.lower}-${zone.upper}`} className="text-sm text-slate-700">
            {label(zone.kind)} {formatInr(zone.lower)} to {formatInr(zone.upper)} · {zone.tests} observed reactions · {zone.status}
            {zone.last_test ? ` · last test ${formatIst(zone.last_test)}` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

function LimitationList({ limitations, freshness }: { limitations: string[]; freshness: TechnicalAnalysis["freshness"] }) {
  return (
    <div className="space-y-2">
      <h3 className="text-base font-semibold">Data limitations</h3>
      {freshness === "stale" ? <p className="text-sm text-slate-700">The latest stored bar is older than seven days.</p> : null}
      {limitations.length === 0 ? <p className="text-sm text-slate-600">No additional data limitation was recorded for this window.</p> : null}
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
        {limitations.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function Toggle({ pressed, onClick, label: text }: { pressed: boolean; onClick: () => void; label: string }) {
  return (
    <button type="button" aria-pressed={pressed} onClick={onClick} className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-800">
      {text}
      {pressed ? " on" : " off"}
    </button>
  );
}

function patternKey(pattern: PatternBlock): string {
  return `${pattern.pattern_type}:${pattern.start_timestamp}`;
}

function label(value: string): string {
  return value.replaceAll("_", " ");
}

function formatLevel(value: string): string {
  if (value.includes(",")) {
    return value;
  }
  return formatInr(value) ?? value;
}

function displayIndicator(name: string, value: string | null): string {
  if (value === null) {
    return "Unavailable";
  }
  if (name === "Volume" || name === "Average volume") {
    const parsed = Number(value);
    return Number.isInteger(parsed) ? (formatVolume(parsed) ?? value) : value;
  }
  if (name === "RSI 14") {
    return value;
  }
  if (name === "Historical volatility") {
    return formatSignedPercent(value)?.replace("+", "") ?? value;
  }
  return formatInr(value) ?? value;
}
