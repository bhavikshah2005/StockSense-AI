import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../services/http.ts";
import { archivePortfolio, createPortfolio, deletePortfolio, listPortfolios, updatePortfolio } from "../services/portfolios.ts";
import type { PortfolioSummary } from "../types/portfolio.ts";
import { formatInr } from "../utils/quote.ts";

type Editor = { id: string | null; name: string; description: string };

export function PortfoliosPage() {
  const [rows, setRows] = useState<PortfolioSummary[] | null>(null);
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<Editor | null>(null);
  const [confirmId, setConfirmId] = useState("");
  const [pending, setPending] = useState(false);

  async function refresh() {
    const body = await listPortfolios();
    setRows(body.results);
  }

  useEffect(() => {
    let cancelled = false;
    listPortfolios()
      .then((body) => {
        if (!cancelled) {
          setRows(body.results);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setRows([]);
          setError(caught instanceof ApiError ? caught.message : "Could not load portfolios");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!editor) {
      return;
    }
    setPending(true);
    setError("");
    try {
      if (editor.id) {
        await updatePortfolio(editor.id, editor.name, editor.description);
      } else {
        await createPortfolio(editor.name, editor.description);
      }
      setEditor(null);
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the portfolio");
    } finally {
      setPending(false);
    }
  }

  async function remove(id: string) {
    setPending(true);
    setError("");
    try {
      await deletePortfolio(id);
      setConfirmId("");
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete the portfolio");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Portfolios</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Track Indian share holdings from the transactions you enter. This does not place trades or connect to a broker. Market value is holdings only and does not include cash.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/portfolio/planning" className="rounded-md border border-slate-300 px-3 py-2 text-sm">Position size</Link>
          <button type="button" className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white" onClick={() => setEditor({ id: null, name: "", description: "" })}>
            New portfolio
          </button>
        </div>
      </header>
      {rows === null ? <p className="text-sm text-slate-600">Loading portfolios…</p> : null}
      {error ? <p className="text-sm text-red-700" role="alert">{error}</p> : null}
      {rows && rows.length === 0 ? <p className="text-sm text-slate-600">You do not have a portfolio yet.</p> : null}
      <ul className="grid max-w-3xl gap-3">
        {rows?.map((row) => (
          <li key={row.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-medium">{row.name}{row.archived_at ? <span className="ml-2 text-xs text-slate-500">Archived</span> : null}</h2>
                {row.description ? <p className="mt-1 text-sm text-slate-600">{row.description}</p> : null}
                <p className="mt-1 text-sm text-slate-500">{row.holding_count} holdings · Cash {formatInr(row.cash) ?? row.cash}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to={`/portfolio/${row.id}`} className="rounded-md bg-slate-950 px-3 py-1.5 text-sm text-white">Open</Link>
                <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={() => setEditor({ id: row.id, name: row.name, description: row.description ?? "" })}>Rename</button>
                {row.archived_at ? null : <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={() => void archivePortfolio(row.id).then(refresh).catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : "Could not archive"))}>Archive</button>}
                <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={() => setConfirmId(row.id)}>Delete</button>
              </div>
            </div>
            {confirmId === row.id ? (
              <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm">
                <p>Deleting removes this portfolio, its transactions, cash records, and derived holdings. Archive it if you want to keep the records.</p>
                <div className="mt-2 flex gap-2">
                  <button type="button" className="rounded-md bg-red-700 px-3 py-1.5 text-white" disabled={pending} onClick={() => void remove(row.id)}>Delete records</button>
                  <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5" onClick={() => setConfirmId("")}>Cancel</button>
                </div>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
      {editor ? (
        <form className="max-w-lg space-y-3 rounded-lg border border-slate-200 bg-white p-4" onSubmit={(event) => void save(event)}>
          <h2 className="font-medium">{editor.id ? "Rename portfolio" : "New portfolio"}</h2>
          <label className="block text-sm">Name
            <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={editor.name} onChange={(event) => setEditor({ ...editor, name: event.target.value })} required />
          </label>
          <label className="block text-sm">Description
            <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={editor.description} onChange={(event) => setEditor({ ...editor, description: event.target.value })} />
          </label>
          <div className="flex gap-2">
            <button type="submit" className="rounded-md bg-slate-950 px-3 py-2 text-sm text-white" disabled={pending}>Save</button>
            <button type="button" className="rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={() => setEditor(null)}>Cancel</button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
