import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../services/http.ts";
import {
  createThreshold,
  deleteThreshold,
  evaluateMetrics,
  getMetricRegistry,
  listThresholds,
  updateThreshold,
} from "../services/metrics.ts";
import { searchStocks } from "../services/stocks.ts";
import type { MetricDefinition, MetricEvaluation, ThresholdRecord } from "../types/metrics.ts";
import type { StockSearchResult } from "../types/stock.ts";
import { formatInr, formatIst } from "../utils/quote.ts";

const OPERATOR_LABELS: Record<string, string> = {
  ">": "Greater than",
  ">=": "Greater than or equal",
  "<": "Less than",
  "<=": "Less than or equal",
  between: "Between",
  outside_range: "Outside range",
  crosses_above: "Crosses above",
  crosses_below: "Crosses below",
};

const STATE_LABELS: Record<string, string> = {
  met: "Condition met",
  not_met: "Condition not met",
  insufficient_data: "Data unavailable",
  context_unavailable: "Context unavailable",
  no_threshold_configured: "No threshold configured",
  stale_data: "Stored data is stale",
};

export function ThresholdsPage() {
  const [metrics, setMetrics] = useState<MetricDefinition[] | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
  const [rows, setRows] = useState<ThresholdRecord[] | null>(null);
  const [error, setError] = useState("");
  const [operator, setOperator] = useState("");
  const [basis, setBasis] = useState("absolute");
  const [low, setLow] = useState("");
  const [high, setHigh] = useState("");
  const [note, setNote] = useState("");
  const [pending, setPending] = useState(false);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<StockSearchResult[]>([]);
  const [stock, setStock] = useState<StockSearchResult | null>(null);
  const [evaluation, setEvaluation] = useState<MetricEvaluation | null>(null);

  const selected = metrics?.find((item) => item.key === selectedKey) ?? null;

  async function loadRows(key: string) {
    const body = await listThresholds(key);
    setRows(body.results);
  }

  useEffect(() => {
    let cancelled = false;
    getMetricRegistry()
      .then((body) => {
        if (cancelled) {
          return;
        }
        setMetrics(body.metrics);
        const first = body.metrics[0];
        if (first) {
          setSelectedKey(first.key);
          setOperator(first.operators[0] ?? "");
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load metrics");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedKey) {
      return;
    }
    let cancelled = false;
    setRows(null);
    setEvaluation(null);
    listThresholds(selectedKey)
      .then((body) => {
        if (!cancelled) {
          setRows(body.results);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setRows([]);
          setError(caught instanceof ApiError ? caught.message : "Could not load thresholds");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedKey]);

  function choose(metric: MetricDefinition) {
    setSelectedKey(metric.key);
    setOperator(metric.operators[0] ?? "");
    setBasis("absolute");
    setLow("");
    setHigh("");
    setError("");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!selected) {
      return;
    }
    setPending(true);
    setError("");
    try {
      await createThreshold({
        metric_key: selected.key,
        operator,
        basis,
        threshold_value: basis === "sector_benchmark" || selected.event_kind === "pair" ? null : low || null,
        threshold_high: operator === "between" || operator === "outside_range" ? high || null : null,
        description: note.trim() ? note : null,
      });
      setLow("");
      setHigh("");
      setNote("");
      await loadRows(selected.key);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the threshold");
    } finally {
      setPending(false);
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    const term = query.trim();
    if (!term) {
      setError("Enter a symbol or company name");
      return;
    }
    setError("");
    try {
      const body = await searchStocks(term);
      setMatches(body.results);
    } catch (caught) {
      setMatches([]);
      setError(caught instanceof ApiError ? caught.message : "Search failed");
    }
  }

  async function preview(listing: StockSearchResult) {
    if (!selected) {
      return;
    }
    setStock(listing);
    setPending(true);
    setError("");
    try {
      const body = await evaluateMetrics(listing.id, [selected.key]);
      setEvaluation(body.results[0] ?? null);
    } catch (caught) {
      setEvaluation(null);
      setError(caught instanceof ApiError ? caught.message : "Could not evaluate this metric");
    } finally {
      setPending(false);
    }
  }

  const groups = [
    ["fundamental", "Fundamentals"],
    ["technical", "Technical"],
  ] as const;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Thresholds</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Screening rules for stored fundamental and technical metrics. A result is not a trade instruction, and it does not create an alert.
        </p>
      </header>
      {metrics === null && !error ? <p className="text-sm text-slate-600">Loading metrics…</p> : null}
      {error ? (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      {metrics ? (
        <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
          <div className="space-y-4">
            {groups.map(([category, label]) => (
              <section key={category}>
                <h2 className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</h2>
                <ul className="mt-2 space-y-1">
                  {metrics
                    .filter((item) => item.category === category)
                    .map((item) => (
                      <li key={item.key}>
                        <button
                          type="button"
                          onClick={() => choose(item)}
                          className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${
                            item.key === selectedKey ? "bg-slate-950 text-white" : "text-slate-800"
                          }`}
                        >
                          {item.name}
                        </button>
                      </li>
                    ))}
                </ul>
              </section>
            ))}
          </div>
          {selected ? (
            <div className="space-y-6">
              <section className="space-y-2">
                <h2 className="text-lg font-medium">{selected.name}</h2>
                <p className="text-sm text-slate-600">{selected.description}</p>
                <p className="text-xs text-slate-500">
                  Unit: {selected.unit}. Source: {selected.source}. Preference: {selected.preference}.
                </p>
              </section>
              <section className="space-y-2" aria-label="Applicable thresholds">
                <h3 className="text-sm font-medium">Applicable thresholds</h3>
                {rows === null ? <p className="text-sm text-slate-600">Loading thresholds…</p> : null}
                {rows && rows.length === 0 ? <p className="text-sm text-slate-600">No threshold is configured for this metric.</p> : null}
                {rows && rows.length > 0 ? (
                  <ul className="space-y-2">
                    {rows.map((row) => (
                      <li key={row.id} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
                        <p className="font-medium text-slate-900">
                          {scopeLabel(row)} · {OPERATOR_LABELS[row.operator] ?? row.operator}
                          {row.basis === "sector_benchmark" ? " sector benchmark" : ""}
                          {row.is_active ? "" : " · disabled"}
                        </p>
                        <p className="text-slate-600">{boundText(row)}</p>
                        {row.description ? <p className="text-slate-500">{row.description}</p> : null}
                        {row.owned ? (
                          <div className="mt-2 flex gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                void updateThreshold(row.id, { is_active: !row.is_active })
                                  .then(() => loadRows(selected.key))
                                  .catch((caught: unknown) => {
                                    setError(caught instanceof ApiError ? caught.message : "Could not update the threshold");
                                  });
                              }}
                              className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                            >
                              {row.is_active ? "Disable" : "Enable"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                void deleteThreshold(row.id)
                                  .then(() => loadRows(selected.key))
                                  .catch((caught: unknown) => {
                                    setError(caught instanceof ApiError ? caught.message : "Could not delete the threshold");
                                  });
                              }}
                              className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                            >
                              Delete
                            </button>
                          </div>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
              <form onSubmit={(event) => void save(event)} className="max-w-xl space-y-3 rounded-lg border border-slate-200 bg-white p-4">
                <h3 className="text-sm font-medium">Personal threshold</h3>
                <label className="block text-sm text-slate-700" htmlFor="threshold-operator">
                  Condition
                </label>
                <select
                  id="threshold-operator"
                  value={operator}
                  onChange={(event) => setOperator(event.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                >
                  {selected.operators.map((item) => (
                    <option key={item} value={item}>
                      {OPERATOR_LABELS[item] ?? item}
                    </option>
                  ))}
                </select>
                {selected.sector_benchmark ? (
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={basis === "sector_benchmark"}
                      onChange={(event) => setBasis(event.target.checked ? "sector_benchmark" : "absolute")}
                    />
                    Compare with the sector benchmark
                  </label>
                ) : null}
                {basis === "absolute" && selected.event_kind !== "pair" ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="text-sm text-slate-700">
                      {operator === "between" || operator === "outside_range" ? "Lower bound" : "Value"}
                      <input
                        value={low}
                        onChange={(event) => setLow(event.target.value)}
                        inputMode="decimal"
                        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                      />
                    </label>
                    {operator === "between" || operator === "outside_range" ? (
                      <label className="text-sm text-slate-700">
                        Upper bound
                        <input
                          value={high}
                          onChange={(event) => setHigh(event.target.value)}
                          inputMode="decimal"
                          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                        />
                      </label>
                    ) : null}
                  </div>
                ) : null}
                <label className="block text-sm text-slate-700" htmlFor="threshold-note">
                  Note
                </label>
                <input
                  id="threshold-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
                <button
                  type="submit"
                  disabled={pending}
                  className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                >
                  {pending ? "Saving…" : "Save threshold"}
                </button>
              </form>
              <section className="space-y-3" aria-label="Evaluation preview">
                <h3 className="text-sm font-medium">Preview for a stock</h3>
                <form className="flex max-w-xl gap-2" onSubmit={(event) => void search(event)}>
                  <label className="sr-only" htmlFor="threshold-stock-query">
                    Symbol or company
                  </label>
                  <input
                    id="threshold-stock-query"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="TCS, Infosys"
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                  <button type="submit" className="rounded-md bg-slate-950 px-3 py-2 text-sm text-white">
                    Search
                  </button>
                </form>
                {matches.length > 0 ? (
                  <ul className="max-w-xl divide-y divide-slate-200 rounded-md border border-slate-200 bg-white">
                    {matches.map((item) => (
                      <li key={item.id}>
                        <button type="button" onClick={() => void preview(item)} className="block w-full px-3 py-2 text-left text-sm">
                          {item.symbol} · {item.company_name} · {item.exchange}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
                {stock && !evaluation && pending ? <p className="text-sm text-slate-600">Evaluating…</p> : null}
                {evaluation ? <EvaluationCard evaluation={evaluation} /> : null}
              </section>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function EvaluationCard({ evaluation }: { evaluation: MetricEvaluation }) {
  const asOf = evaluation.as_of ? formatIst(evaluation.as_of) : null;
  return (
    <div className="max-w-xl space-y-2 rounded-lg border border-slate-200 bg-white p-4" role="status">
      <p className="text-sm font-medium text-slate-900">{STATE_LABELS[evaluation.state] ?? evaluation.state}</p>
      <p className="text-sm text-slate-700">{evaluation.explanation}</p>
      <p className="text-sm text-slate-800">Latest stored value: {displayValue(evaluation)}</p>
      {evaluation.threshold ? (
        <p className="text-xs text-slate-500">
          {evaluation.threshold.scope} threshold · {evaluation.threshold.definition_version}. {evaluation.threshold.reason}
        </p>
      ) : null}
      {asOf ? <p className="text-xs text-slate-500">Data as of {asOf}</p> : null}
      {evaluation.source ? <p className="text-xs text-slate-500">Source: {evaluation.source}</p> : null}
    </div>
  );
}

function displayValue(evaluation: MetricEvaluation): string {
  if (evaluation.value === null) {
    return "Unavailable";
  }
  if (evaluation.unit === "inr") {
    return formatInr(evaluation.value) ?? evaluation.value;
  }
  if (evaluation.unit === "percent") {
    return `${evaluation.value}%`;
  }
  return evaluation.value;
}

function scopeLabel(row: ThresholdRecord): string {
  if (row.scope === "global") {
    return "Platform";
  }
  if (row.scope === "country") {
    return row.country ? `Market ${row.country}` : "Market";
  }
  if (row.scope === "sector") {
    return row.sector ? `Sector ${row.sector}` : "Sector";
  }
  return row.owned ? "Your threshold" : "User";
}

function boundText(row: ThresholdRecord): string {
  if (row.basis === "sector_benchmark") {
    return "Compared with the sector benchmark";
  }
  if (row.operator === "between" || row.operator === "outside_range") {
    return `${row.threshold_value ?? "—"} to ${row.threshold_high ?? "—"}`;
  }
  if (row.threshold_value === null) {
    return "Uses the previous and current readings";
  }
  return row.threshold_value;
}
