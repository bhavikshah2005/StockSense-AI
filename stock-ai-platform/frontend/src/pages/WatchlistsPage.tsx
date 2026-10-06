import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../services/http.ts";
import {
  createWatchlist,
  deleteWatchlist,
  listWatchlists,
  setDefaultWatchlist,
  updateWatchlist,
} from "../services/watchlists.ts";
import type { WatchlistSummary } from "../types/watchlist.ts";

type Editor = { id: string | null; name: string; description: string };

export function WatchlistsPage() {
  const [lists, setLists] = useState<WatchlistSummary[] | null>(null);
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<Editor | null>(null);
  const [pending, setPending] = useState(false);
  const [confirmId, setConfirmId] = useState("");

  async function refresh() {
    const body = await listWatchlists();
    setLists(body.results);
  }

  useEffect(() => {
    let cancelled = false;
    listWatchlists()
      .then((body) => {
        if (!cancelled) {
          setLists(body.results);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setLists([]);
          setError(caught instanceof ApiError ? caught.message : "Could not load watchlists");
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
        await updateWatchlist(editor.id, editor.name, editor.description);
      } else {
        await createWatchlist(editor.name, editor.description);
      }
      setEditor(null);
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the watchlist");
    } finally {
      setPending(false);
    }
  }

  async function makeDefault(id: string) {
    setError("");
    try {
      await setDefaultWatchlist(id);
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not set the default watchlist");
    }
  }

  async function remove(id: string) {
    setError("");
    setPending(true);
    try {
      await deleteWatchlist(id);
      setConfirmId("");
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete the watchlist");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Watchlists</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Named lists of Indian stocks. They stay with your account.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditor({ id: null, name: "", description: "" })}
          className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white"
        >
          New watchlist
        </button>
      </header>
      {lists === null ? <p className="text-sm text-slate-600">Loading watchlists…</p> : null}
      {error ? (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      {lists && lists.length === 0 ? (
        <div className="max-w-xl rounded-lg border border-dashed border-slate-300 p-6">
          <p className="text-sm text-slate-700">You do not have a watchlist yet.</p>
          <button
            type="button"
            onClick={() => setEditor({ id: null, name: "", description: "" })}
            className="mt-3 rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white"
          >
            Create your first watchlist
          </button>
        </div>
      ) : null}
      {lists && lists.length > 0 ? (
        <ul className="grid max-w-3xl gap-3">
          {lists.map((list) => (
            <li key={list.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-medium text-slate-900">
                    {list.name}
                    {list.is_default ? (
                      <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">Default</span>
                    ) : null}
                  </h2>
                  {list.description ? <p className="mt-1 text-sm text-slate-600">{list.description}</p> : null}
                  <p className="mt-1 text-sm text-slate-500">
                    {list.stock_count} {list.stock_count === 1 ? "stock" : "stocks"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link to={`/watchlist/${list.id}`} className="rounded-md bg-slate-950 px-3 py-1.5 text-sm text-white">
                    Open
                  </Link>
                  <button
                    type="button"
                    onClick={() => setEditor({ id: list.id, name: list.name, description: list.description ?? "" })}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-800"
                  >
                    Rename
                  </button>
                  {list.is_default ? null : (
                    <button
                      type="button"
                      onClick={() => {
                        void makeDefault(list.id);
                      }}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-800"
                    >
                      Set default
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setConfirmId(list.id)}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-800"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {confirmId === list.id ? (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <p className="text-sm text-slate-700">Delete this watchlist? The stocks stay in the catalog.</p>
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => {
                      void remove(list.id);
                    }}
                    className="rounded-md bg-red-700 px-3 py-1.5 text-sm text-white disabled:opacity-60"
                  >
                    Confirm delete
                  </button>
                  <button type="button" onClick={() => setConfirmId("")} className="text-sm text-slate-600">
                    Cancel
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {editor ? (
        <form
          onSubmit={(event) => void save(event)}
          className="max-w-xl space-y-3 rounded-lg border border-slate-200 bg-white p-4"
          role="dialog"
          aria-label={editor.id ? "Rename watchlist" : "Create watchlist"}
        >
          <h2 className="text-sm font-medium text-slate-900">{editor.id ? "Rename watchlist" : "Create watchlist"}</h2>
          <label className="block text-sm text-slate-700" htmlFor="watchlist-name">
            Name
          </label>
          <input
            id="watchlist-name"
            value={editor.name}
            onChange={(event) => setEditor({ ...editor, name: event.target.value })}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-base"
            required
          />
          <label className="block text-sm text-slate-700" htmlFor="watchlist-description">
            Description
          </label>
          <input
            id="watchlist-description"
            value={editor.description}
            onChange={(event) => setEditor({ ...editor, description: event.target.value })}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-base"
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={pending}
              className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {pending ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={() => setEditor(null)} className="text-sm text-slate-600">
              Cancel
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
