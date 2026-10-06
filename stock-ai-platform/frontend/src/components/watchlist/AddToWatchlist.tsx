import { useState } from "react";

import { ApiError } from "../../services/http.ts";
import { addWatchlistStock, listWatchlists, removeWatchlistStock } from "../../services/watchlists.ts";
import type { WatchlistSummary } from "../../types/watchlist.ts";

export function AddToWatchlist({ stockId }: { stockId: string }) {
  const [open, setOpen] = useState(false);
  const [lists, setLists] = useState<WatchlistSummary[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState("");

  async function load() {
    setError("");
    try {
      const body = await listWatchlists(stockId);
      setLists(body.results);
    } catch (caught) {
      setLists([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load watchlists");
    }
  }

  async function toggle() {
    const next = !open;
    setOpen(next);
    setNotice("");
    if (next) {
      await load();
    }
  }

  async function add(watchlistId: string) {
    setBusyId(watchlistId);
    setError("");
    setNotice("");
    try {
      await addWatchlistStock(watchlistId, stockId);
      setNotice("Added to watchlist");
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not add this stock");
    } finally {
      setBusyId("");
    }
  }

  async function remove(watchlistId: string) {
    setBusyId(watchlistId);
    setError("");
    setNotice("");
    try {
      await removeWatchlistStock(watchlistId, stockId);
      setNotice("Removed from watchlist");
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not remove this stock");
    } finally {
      setBusyId("");
    }
  }

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => {
          void toggle();
        }}
        className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800"
        aria-expanded={open}
      >
        Add to watchlist
      </button>
      {open ? (
        <div className="mt-2 max-w-md rounded-md border border-slate-200 bg-white p-3" role="region" aria-label="Watchlists">
          {lists === null ? <p className="text-sm text-slate-600">Loading watchlists…</p> : null}
          {lists && lists.length === 0 ? (
            <p className="text-sm text-slate-600">Create a watchlist before adding this stock.</p>
          ) : null}
          {lists && lists.length > 0 ? (
            <ul className="space-y-2">
              {lists.map((list) => (
                <li key={list.id} className="flex items-center justify-between gap-3">
                  <span className="text-sm text-slate-800">
                    {list.name}
                    {list.contains_stock ? <span className="ml-2 text-xs text-slate-500">Already on this watchlist</span> : null}
                  </span>
                  {list.contains_stock ? (
                    <button
                      type="button"
                      disabled={busyId === list.id}
                      onClick={() => {
                        void remove(list.id);
                      }}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 disabled:opacity-60"
                    >
                      Remove
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={busyId === list.id}
                      onClick={() => {
                        void add(list.id);
                      }}
                      className="rounded-md bg-slate-950 px-2 py-1 text-xs text-white disabled:opacity-60"
                    >
                      Add
                    </button>
                  )}
                </li>
              ))}
            </ul>
          ) : null}
          {notice ? (
            <p className="mt-2 text-sm text-emerald-700" role="status">
              {notice}
            </p>
          ) : null}
          {error ? (
            <p className="mt-2 text-sm text-red-700" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
