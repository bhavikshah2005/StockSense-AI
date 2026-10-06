import { useEffect, useState } from "react";

import { StockPriceChart, type ChartPoint } from "./StockPriceChart.tsx";
import { ApiError } from "../../services/http.ts";
import { getHistory, getMarketStatus } from "../../services/stocks.ts";
import type { HistoryResponse } from "../../types/stock.ts";
import {
  formatCompactVolume,
  formatInr,
  formatIst,
  formatSignedInr,
  formatSignedPercent,
} from "../../utils/quote.ts";

const RANGES = [
  ["1d", "1D"],
  ["1w", "1W"],
  ["1m", "1M"],
  ["3m", "3M"],
  ["6m", "6M"],
  ["1y", "1Y"],
  ["3y", "3Y"],
  ["5y", "5Y"],
  ["max", "MAX"],
] as const;

type RangeId = (typeof RANGES)[number][0];
type HistoryState = "loading" | "ready" | "empty" | "error" | "unavailable";

const STATUS_LABELS: Record<string, string> = {
  open: "Market open",
  closed: "Market closed",
  "pre-open": "Pre-open",
  "post-market": "Post-market",
  holiday: "Holiday",
};

export function StockHistory({ stockId, exchange }: { stockId: string; exchange: string }) {
  const [range, setRange] = useState<RangeId>("1y");
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [state, setState] = useState<HistoryState>("loading");
  const [cached] = useState<Map<RangeId, HistoryResponse>>(() => new Map());
  const [sessionLabel, setSessionLabel] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMarketStatus(exchange)
      .then((body) => {
        if (!cancelled) {
          setSessionLabel(STATUS_LABELS[body.status] ?? null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSessionLabel(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [exchange]);

  useEffect(() => {
    const stored = cached.get(range);
    if (stored) {
      setHistory(stored);
      setState(stored.data.length === 0 ? "empty" : "ready");
      return;
    }
    let cancelled = false;
    setState("loading");
    setHistory(null);
    getHistory(stockId, range)
      .then((body) => {
        if (cancelled) {
          return;
        }
        cached.set(range, body);
        setHistory(body);
        setState(body.data.length === 0 ? "empty" : "ready");
      })
      .catch((caught: unknown) => {
        if (cancelled) {
          return;
        }
        setHistory(null);
        setState(caught instanceof ApiError && caught.status === 503 ? "unavailable" : "error");
      });
    return () => {
      cancelled = true;
    };
  }, [cached, range, stockId]);

  const points = history && state === "ready" ? toPoints(history) : [];
  const summary = history?.performance ?? null;
  const rising = summary ? Number(summary.change) >= 0 : true;
  const rangeLabel = RANGES.find(([id]) => id === range)?.[1] ?? range;
  const marketTime = history?.market_timestamp ? formatIst(history.market_timestamp) : null;
  const fetchedTime = history?.fetched_at ? formatIst(history.fetched_at) : null;

  return (
    <section className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {sessionLabel ? <p className="text-xs font-medium text-slate-600">{sessionLabel}</p> : null}
        <div className="flex flex-wrap gap-1">
          {RANGES.map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setRange(id)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                range === id ? "bg-slate-950 text-white" : "bg-white text-slate-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {state === "loading" ? <p className="text-sm text-slate-600">Loading historical data...</p> : null}
      {state === "empty" ? <p className="text-sm text-slate-600">No historical data available for this period.</p> : null}
      {state === "error" ? <p className="text-sm text-slate-700">Unable to load historical market data.</p> : null}
      {state === "unavailable" ? <p className="text-sm text-slate-700">Market data is temporarily unavailable.</p> : null}
      {state === "ready" && points.length > 0 ? <StockPriceChart points={points} rising={rising} /> : null}
      {state === "ready" && points.length === 0 ? (
        <p className="text-sm text-slate-700">Market data is temporarily unavailable.</p>
      ) : null}
      {state === "ready" && summary ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Stat label={`${rangeLabel} start`} value={formatInr(summary.start_price)} />
          <Stat label="Current" value={formatInr(summary.end_price)} />
          <Stat label="Change" value={formatSignedInr(summary.change)} />
          <Stat label="Return" value={formatSignedPercent(summary.change_percent)} />
          <Stat label={`${rangeLabel} high`} value={history?.period_high ? formatInr(history.period_high) : null} />
          <Stat label={`${rangeLabel} low`} value={history?.period_low ? formatInr(history.period_low) : null} />
        </div>
      ) : null}
      {state === "ready" && marketTime && fetchedTime ? (
        <div className="space-y-1 text-xs text-slate-500">
          <p>Last market data update: {marketTime}</p>
          <p>Fetched: {fetchedTime}</p>
        </div>
      ) : null}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string | null }) {
  if (value === null) {
    return null;
  }
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-medium text-slate-900">{value}</p>
    </div>
  );
}

function toPoints(history: HistoryResponse): ChartPoint[] {
  if (history.stock.currency !== "INR") {
    return [];
  }
  const points: ChartPoint[] = [];
  for (const bar of history.data) {
    const closeText = formatInr(bar.close);
    const openText = formatInr(bar.open);
    const highText = formatInr(bar.high);
    const lowText = formatInr(bar.low);
    const close = Number(bar.close);
    const stamp = new Date(bar.timestamp);
    if (
      closeText === null ||
      openText === null ||
      highText === null ||
      lowText === null ||
      !Number.isFinite(close) ||
      Number.isNaN(stamp.getTime())
    ) {
      return [];
    }
    points.push({
      time: stamp.getTime(),
      label: new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: history.interval === "1d" ? "2-digit" : "numeric",
        hour: history.interval === "1d" ? undefined : "2-digit",
        minute: history.interval === "1d" ? undefined : "2-digit",
        hourCycle: "h23",
      }).format(stamp),
      close,
      openText,
      highText,
      lowText,
      closeText,
      volume: bar.volume,
      volumeText: formatCompactVolume(bar.volume),
    });
  }
  return points;
}
