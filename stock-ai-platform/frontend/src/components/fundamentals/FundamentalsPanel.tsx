import { useEffect, useState } from "react";

import { MetricCard } from "../metrics/MetricCard.tsx";
import { ApiError } from "../../services/http.ts";
import { getFundamentals, getSectorComparison, getValuation } from "../../services/stocks.ts";
import type { FundamentalReport, SectorComparison, ValuationSnapshot } from "../../types/fundamentals.ts";
import { formatMetricValue, formatReportDay, formatSnapshotDay } from "../../utils/fundamentals.ts";
import { formatIst } from "../../utils/quote.ts";
import {
  GROWTH_KEYS,
  HEALTH_KEYS,
  METRIC_DEFINITIONS,
  PROFITABILITY_KEYS,
  SNAPSHOT_KEYS,
  VALUATION_KEYS,
} from "./definitions.ts";

type PanelStatus = "loading" | "ready" | "empty" | "unconfigured" | "error";

type Loaded = {
  status: PanelStatus;
  message: string;
  report: FundamentalReport | null;
  valuation: ValuationSnapshot | null;
  sector: SectorComparison | null;
};

const LOADING: Loaded = {
  status: "loading",
  message: "",
  report: null,
  valuation: null,
  sector: null,
};

export function FundamentalsPanel({ stockId }: { stockId: string }) {
  const [loaded, setLoaded] = useState<Loaded>(LOADING);

  useEffect(() => {
    let cancelled = false;
    setLoaded(LOADING);
    async function load() {
      const [reportResult, valuationResult, sectorResult] = await Promise.allSettled([
        getFundamentals(stockId),
        getValuation(stockId),
        getSectorComparison(stockId),
      ]);
      if (cancelled) {
        return;
      }
      setLoaded(combine(reportResult, valuationResult, sectorResult));
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [stockId]);

  if (loaded.status === "loading") {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Fundamentals</h2>
        <p className="text-sm text-slate-600">Loading fundamentals…</p>
      </section>
    );
  }

  if (loaded.status === "unconfigured") {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Fundamentals</h2>
        <p className="text-sm text-slate-700">Provider not configured</p>
      </section>
    );
  }

  if (loaded.status === "error") {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Fundamentals</h2>
        <p className="text-sm text-slate-700">{loaded.message || "Fundamental data is temporarily unavailable."}</p>
      </section>
    );
  }

  if (loaded.status === "empty") {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Fundamentals</h2>
        <p className="text-sm text-slate-700">Fundamental data unavailable</p>
      </section>
    );
  }

  const report = loaded.report;
  const valuation = loaded.valuation;
  const reportedOn = report?.period?.filing_date ? formatReportDay(report.period.filing_date) : null;
  const valuationDay = valuation?.snapshot_at ? formatSnapshotDay(valuation.snapshot_at) : null;
  const updated = report?.metadata.data_as_of ? formatIst(report.metadata.data_as_of) : null;

  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Fundamentals</h2>
        {report?.period ? <p className="text-sm text-slate-600">Reported for {report.period.fiscal_period}</p> : null}
        {report?.metadata.supplemented_from_period ? (
          <p className="text-xs text-slate-500">
            Balance-sheet and cash-flow figures missing from this period are from {report.metadata.supplemented_from_period}.
          </p>
        ) : null}
        {reportedOn ? <p className="text-sm text-slate-600">Reported on {reportedOn}</p> : null}
        {report?.metadata.is_available && !report.metadata.filing_date_known ? (
          <p className="text-xs text-slate-500">Publication date was not supplied. Availability uses the provider retrieval time.</p>
        ) : null}
        {valuationDay ? <p className="text-sm text-slate-600">Valuation as of {valuationDay}</p> : null}
        {updated ? <p className="text-xs text-slate-500">Data last updated: {updated}</p> : null}
        {report?.metadata.is_stale || valuation?.metadata.is_stale ? (
          <p className="text-xs text-amber-800">Stored data is older than the freshness window.</p>
        ) : null}
      </div>
      <MetricGroup title="Valuation" keys={VALUATION_KEYS} values={valuation?.data ?? {}} />
      <MetricGroup title="Growth" keys={GROWTH_KEYS} values={report?.data ?? {}} />
      <MetricGroup title="Profitability" keys={PROFITABILITY_KEYS} values={report?.data ?? {}} />
      <MetricGroup title="Financial health" keys={HEALTH_KEYS} values={report?.data ?? {}} />
      <MetricGroup
        title="Financial snapshot"
        keys={SNAPSHOT_KEYS}
        values={{
          ...(report?.data ?? {}),
          market_cap: valuation?.data.market_cap ?? null,
          enterprise_value: valuation?.data.enterprise_value ?? null,
        }}
      />
      <SectorBlock comparison={loaded.sector} />
    </section>
  );
}

function MetricGroup({
  title,
  keys,
  values,
}: {
  title: string;
  keys: readonly string[];
  values: Partial<Record<string, string | null>>;
}) {
  const cards = keys.flatMap((key) => {
    const definition = METRIC_DEFINITIONS[key];
    const formatted = definition ? formatMetricValue(definition.unit, values[key] ?? null) : null;
    if (!definition || formatted === null) {
      return [];
    }
    return [{ key, definition, formatted }];
  });
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-slate-800">{title}</h3>
      {cards.length === 0 ? <p className="text-sm text-slate-500">Fundamental data unavailable</p> : null}
      {cards.length > 0 && cards.length < keys.length ? (
        <p className="text-xs text-slate-500">Some metrics were not supplied.</p>
      ) : null}
      {cards.length > 0 ? (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {cards.map((card) => (
            <MetricCard
              key={card.key}
              label={card.definition.label}
              value={card.formatted}
              description={card.definition.description}
            />
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function SectorBlock({ comparison }: { comparison: SectorComparison | null }) {
  if (comparison === null) {
    return null;
  }
  if (!comparison.benchmark_available) {
    return <p className="text-sm text-slate-600">Sector benchmark unavailable</p>;
  }
  const rows = comparison.metrics.filter((metric) => metric.stock_value !== null || metric.benchmark_value !== null);
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-slate-800">Sector comparison</h3>
      {comparison.sector ? <p className="text-xs text-slate-500">{comparison.sector}</p> : null}
      {comparison.calculation_date ? (
        <p className="text-xs text-slate-500">Benchmark calculated {formatReportDay(comparison.calculation_date)}</p>
      ) : null}
      <dl className="grid grid-cols-1 gap-2">
        {rows.map((metric) => {
          const definition = METRIC_DEFINITIONS[metric.metric];
          if (!definition) {
            return null;
          }
          const stockValue = formatMetricValue(definition.unit, metric.stock_value);
          const benchmarkValue = formatMetricValue(definition.unit, metric.benchmark_value);
          const difference = formatMetricValue(definition.unit, metric.difference);
          return (
            <div key={metric.metric} className="text-sm text-slate-700">
              <span className="font-medium">{definition.label}</span>
              {stockValue ? <span>{` · Stock ${stockValue}`}</span> : null}
              {benchmarkValue ? <span>{` · Sector ${benchmarkValue}`}</span> : null}
              {difference ? <span>{` · Difference ${difference}`}</span> : null}
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function combine(
  reportResult: PromiseSettledResult<FundamentalReport>,
  valuationResult: PromiseSettledResult<ValuationSnapshot>,
  sectorResult: PromiseSettledResult<SectorComparison>,
): Loaded {
  const report = settledValue(reportResult);
  const valuation = settledValue(valuationResult);
  const sector = settledValue(sectorResult);
  const failures = [reportResult, valuationResult].filter((item) => item.status === "rejected");
  if (report === null && valuation === null && failures.length > 0) {
    const reason = failures[0]?.status === "rejected" ? failures[0].reason : null;
    if (reason instanceof ApiError && reason.status === 503) {
      return { status: "unconfigured", message: reason.message, report: null, valuation: null, sector };
    }
    return {
      status: "error",
      message: reason instanceof ApiError ? reason.message : "Fundamental data is temporarily unavailable.",
      report: null,
      valuation: null,
      sector,
    };
  }
  const reportReady = report?.metadata.is_available === true;
  const valuationReady = valuation?.metadata.is_available === true;
  if (!reportReady && !valuationReady && failures.length === 0) {
    return { status: "empty", message: "", report, valuation, sector };
  }
  return { status: "ready", message: "", report, valuation, sector };
}

function settledValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}
