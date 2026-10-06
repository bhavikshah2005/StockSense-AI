import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { FormMessage, SubmitButton, TextField } from "../components/auth/AuthCard.tsx";
import {
  createAlert,
  deleteAlert,
  getAlertCatalog,
  listAlerts,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  pauseAlert,
  resumeAlert,
  type AlertDraft,
} from "../services/alerts.ts";
import { ApiError } from "../services/http.ts";
import { searchStocks } from "../services/stocks.ts";
import type { AlertCatalog, AlertRecord, NotificationRecord } from "../types/alerts.ts";
import type { StockSearchResult } from "../types/stock.ts";
import { formatIst } from "../utils/quote.ts";

export function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertRecord[] | null>(null);
  const [notes, setNotes] = useState<NotificationRecord[] | null>(null);
  const [catalog, setCatalog] = useState<AlertCatalog | null>(null);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [pending, setPending] = useState(false);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<StockSearchResult[]>([]);
  const [stock, setStock] = useState<StockSearchResult | null>(null);
  const [category, setCategory] = useState("price");
  const [metric, setMetric] = useState("price");
  const [operator, setOperator] = useState(">");
  const [threshold, setThreshold] = useState("");
  const [thresholdHigh, setThresholdHigh] = useState("");
  const [interval, setInterval] = useState("5d");
  const [patternType, setPatternType] = useState("double_top");
  const [patternStatus, setPatternStatus] = useState("confirmed");
  const [repeatMode, setRepeatMode] = useState("once");

  async function load() {
    const [alertPage, inbox, available] = await Promise.all([listAlerts(), listNotifications(), getAlertCatalog()]);
    setAlerts(alertPage.results);
    setNotes(inbox.results);
    setCatalog(available);
  }

  useEffect(() => {
    let cancelled = false;
    load().catch((caught: unknown) => {
      if (!cancelled) {
        setError(caught instanceof ApiError ? caught.message : "Could not load alerts");
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const metrics = category === "price" ? catalog?.price.metrics ?? [] : category === "fundamental" ? catalog?.fundamental ?? [] : catalog?.technical ?? [];
  const selected = metrics.find((item) => item.key === metric) ?? metrics[0];
  const operators = selected?.operators ?? [">", "<"];

  async function onSearch() {
    setMatches([]);
    if (!query.trim()) {
      return;
    }
    const found = await searchStocks(query.trim());
    setMatches(found.results);
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!stock) {
      setFormError("Choose a stock");
      return;
    }
    const draft: AlertDraft = {
      stock_id: stock.id,
      category,
      metric: category === "pattern" ? "pattern" : (selected?.key ?? metric),
      operator: category === "pattern" ? ">" : operator,
      threshold_type: "absolute",
      repeat_mode: repeatMode,
    };
    if (category === "pattern") {
      draft.pattern_type = patternType;
      draft.pattern_status = patternStatus;
    } else if (metric === "price_change_percent") {
      draft.threshold_type = "percentage";
      draft.percent_interval = interval;
      draft.threshold_value = threshold;
    } else {
      draft.threshold_value = threshold;
      if (operator === "between" || operator === "outside_range") {
        draft.threshold_high = thresholdHigh;
      }
    }
    setPending(true);
    try {
      await createAlert(draft);
      setThreshold("");
      setThresholdHigh("");
      await load();
    } catch (caught) {
      setFormError(caught instanceof ApiError ? caught.message : "Could not save the alert");
    } finally {
      setPending(false);
    }
  }

  async function onPause(alert: AlertRecord) {
    if (alert.status === "active") {
      await pauseAlert(alert.id);
    } else {
      await resumeAlert(alert.id);
    }
    await load();
  }

  async function onDelete(alert: AlertRecord) {
    if (!window.confirm(`Delete the ${alert.symbol} alert?`)) {
      return;
    }
    await deleteAlert(alert.id);
    await load();
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Alerts use stored prices, fundamentals, and technical readings. Evaluation runs on a schedule and is not a real-time guarantee. A trigger is not a trade instruction.
        </p>
      </header>
      {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
      <section className="space-y-3" aria-label="Notifications">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Notifications</h2>
          <button type="button" className="text-sm text-slate-700" onClick={() => void markAllNotificationsRead().then(load)}>
            Mark all read
          </button>
        </div>
        {notes === null ? <p className="text-sm text-slate-600">Loading notifications…</p> : null}
        {notes !== null && notes.length === 0 ? <p className="text-sm text-slate-600">No notifications</p> : null}
        <ul className="space-y-2">
          {(notes ?? []).map((note) => (
            <li key={note.id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
              <p className="font-medium">{note.symbol}</p>
              <p className="text-slate-700">{note.message}</p>
              <p className="text-xs text-slate-500">{formatIst(note.triggered_at)}</p>
              {note.read_at ? <p className="text-xs text-slate-500">Read</p> : (
                <button type="button" className="text-xs text-slate-700" onClick={() => void markNotificationRead(note.id).then(load)}>
                  Mark read
                </button>
              )}
              <Link className="ml-3 text-xs text-slate-700" to={`/alerts/${note.alert_id}`}>View alert</Link>
            </li>
          ))}
        </ul>
      </section>
      <form className="max-w-xl space-y-3 rounded-lg border border-slate-200 bg-white p-4" onSubmit={(event) => void onCreate(event)}>
        <h2 className="text-sm font-medium text-slate-500">New alert</h2>
        {formError ? <FormMessage tone="error">{formError}</FormMessage> : null}
        <div className="flex gap-2">
          <TextField label="Symbol or company" type="text" value={query} autoComplete="off" onChange={setQuery} />
          <button type="button" className="self-end rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={() => void onSearch()}>
            Search
          </button>
        </div>
        <ul className="divide-y divide-slate-200 rounded-md border border-slate-200">
          {matches.map((item) => (
            <li key={item.id}>
              <button type="button" className="block w-full px-3 py-2 text-left text-sm" onClick={() => setStock(item)}>
                {item.symbol} · {item.company_name} · {item.exchange}
              </button>
            </li>
          ))}
        </ul>
        {stock ? <p className="text-sm text-slate-700">Selected {stock.symbol} · {stock.exchange}</p> : null}
        <label className="block text-sm text-slate-700">
          Category
          <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="price">Price</option>
            <option value="fundamental">Fundamental</option>
            <option value="technical">Technical</option>
            <option value="pattern">Chart pattern</option>
          </select>
        </label>
        {category === "pattern" ? (
          <>
            <label className="block text-sm text-slate-700">
              Pattern
              <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={patternType} onChange={(event) => setPatternType(event.target.value)}>
                {(catalog?.pattern.types ?? [patternType]).map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
              </select>
            </label>
            <label className="block text-sm text-slate-700">
              Status
              <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={patternStatus} onChange={(event) => setPatternStatus(event.target.value)}>
                {(catalog?.pattern.statuses ?? ["confirmed"]).map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
          </>
        ) : (
          <>
            <label className="block text-sm text-slate-700">
              Metric
              <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={selected?.key ?? metric} onChange={(event) => setMetric(event.target.value)}>
                {metrics.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}
              </select>
            </label>
            <label className="block text-sm text-slate-700">
              Condition
              <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={operator} onChange={(event) => setOperator(event.target.value)}>
                {operators.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            {metric === "price_change_percent" ? (
              <label className="block text-sm text-slate-700">
                Interval
                <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={interval} onChange={(event) => setInterval(event.target.value)}>
                  {(selected?.intervals ?? ["1d", "5d", "20d"]).map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
            ) : null}
            <TextField label="Value" type="text" value={threshold} autoComplete="off" onChange={setThreshold} />
            {operator === "between" || operator === "outside_range" ? (
              <TextField label="Upper value" type="text" value={thresholdHigh} autoComplete="off" onChange={setThresholdHigh} />
            ) : null}
          </>
        )}
        <label className="block text-sm text-slate-700">
          Repeat
          <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={repeatMode} onChange={(event) => setRepeatMode(event.target.value)}>
            <option value="once">Once</option>
            <option value="repeat">Repeat after the condition clears</option>
          </select>
        </label>
        <SubmitButton pending={pending} label="Save alert" />
      </form>
      <section aria-label="Alert list">
        <h2 className="text-lg font-semibold">Your alerts</h2>
        {alerts === null && !error ? <p className="mt-2 text-sm text-slate-600">Loading alerts…</p> : null}
        {alerts !== null && alerts.length === 0 ? <p className="mt-2 text-sm text-slate-600">No alerts yet</p> : null}
        <ul className="mt-3 space-y-2">
          {(alerts ?? []).map((alert) => (
            <li key={alert.id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
              <p className="font-medium">{alert.symbol} · {alert.exchange}</p>
              <p>{alert.category} · {alert.metric} {alert.operator} {alert.threshold_value ?? alert.pattern_status ?? "sector threshold"}</p>
              <p className="text-slate-600">Status {alert.status}{alert.last_data_status ? ` · Last check ${alert.last_data_status}` : ""}</p>
              <div className="mt-2 flex gap-3">
                <Link to={`/alerts/${alert.id}`}>History</Link>
                <button type="button" onClick={() => void onPause(alert)}>{alert.status === "active" ? "Pause" : "Resume"}</button>
                <button type="button" onClick={() => void onDelete(alert)}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
