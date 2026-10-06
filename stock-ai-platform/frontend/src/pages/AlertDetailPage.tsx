import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getAlert, listAlertEvents, previewAlert, updateAlert } from "../services/alerts.ts";
import { ApiError } from "../services/http.ts";
import type { AlertEventRecord, AlertPreview, AlertRecord } from "../types/alerts.ts";
import { formatIst } from "../utils/quote.ts";

export function AlertDetailPage() {
  const { alertId = "" } = useParams();
  const [alert, setAlert] = useState<AlertRecord | null>(null);
  const [events, setEvents] = useState<AlertEventRecord[] | null>(null);
  const [preview, setPreview] = useState<AlertPreview | null>(null);
  const [threshold, setThreshold] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([getAlert(alertId), listAlertEvents(alertId)])
      .then(([row, page]) => {
        if (!cancelled) {
          setAlert(row);
          setThreshold(row.threshold_value ?? "");
          setNote(row.note ?? "");
          setEvents(page.results);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load alert history");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [alertId]);

  async function onPreview() {
    setError("");
    try {
      setPreview(await previewAlert(alertId));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not preview this alert");
    }
  }

  return (
    <div className="space-y-6">
      <Link className="text-sm text-slate-600" to="/alerts">Back to alerts</Link>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{alert ? `${alert.symbol} alert` : "Alert history"}</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">A preview checks the latest stored data and does not create a trigger. Editing a condition keeps existing trigger history.</p>
      </header>
      {alert ? (
        <form
          className="max-w-xl space-y-3 rounded-lg border border-slate-200 bg-white p-4"
          onSubmit={(event) => {
            event.preventDefault();
            void updateAlert(alert.id, { threshold_value: threshold || null, note: note || null })
              .then(setAlert)
              .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : "Could not update this alert"));
          }}
        >
          <p className="text-sm text-slate-700">{alert.category} · {alert.metric} {alert.operator} · {alert.status}</p>
          <label className="block text-sm text-slate-700">
            Value
            <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={threshold} onChange={(event) => setThreshold(event.target.value)} />
          </label>
          <label className="block text-sm text-slate-700">
            Note
            <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <button type="submit" className="rounded-md bg-slate-950 px-3 py-2 text-sm text-white">Save changes</button>
        </form>
      ) : null}
      {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
      <button type="button" className="rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={() => void onPreview()}>
        Preview current data
      </button>
      {preview ? (
        <section className="max-w-xl rounded-lg border border-slate-200 bg-white p-4 text-sm" aria-label="Preview">
          <p className="font-medium">{preview.state}</p>
          <p>{preview.explanation}</p>
          <p className="text-slate-600">{preview.value === null ? "Value unavailable" : `Value ${preview.value}`}</p>
          <p className="text-xs text-slate-500">{preview.would_trigger ? "This would trigger if evaluation ran now." : "This would not trigger."}</p>
        </section>
      ) : null}
      {events === null && !error ? <p className="text-sm text-slate-600">Loading history…</p> : null}
      {events !== null && events.length === 0 ? <p className="text-sm text-slate-600">No triggers yet</p> : null}
      <ul className="space-y-2">
        {(events ?? []).map((event) => (
          <li key={event.id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
            <p>{event.message}</p>
            <p className="text-xs text-slate-500">{formatIst(event.triggered_at)} · {event.data_status}</p>
            <Link className="text-xs text-slate-700" to={`/stocks/${event.stock_id}`}>Open stock</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
