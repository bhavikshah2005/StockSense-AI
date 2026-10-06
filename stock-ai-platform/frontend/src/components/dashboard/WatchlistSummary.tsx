import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { WatchlistQuoteText } from "../watchlist/WatchlistQuoteText.tsx";
import { ApiError } from "../../services/http.ts";
import { getWatchlist, listWatchlists } from "../../services/watchlists.ts";
import type { WatchlistDetail } from "../../types/watchlist.ts";

const QUOTE_REFRESH_MS = 15_000;

export function WatchlistSummary() {
  const [detail, setDetail] = useState<WatchlistDetail | null>(null);
  const [empty, setEmpty] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const lists = await listWatchlists();
        const chosen = lists.results.find((item) => item.is_default) ?? lists.results[0];
        if (!chosen) {
          if (!cancelled) {
            setEmpty(true);
            setLoading(false);
          }
          return;
        }
        const body = await getWatchlist(chosen.id);
        if (!cancelled) {
          setDetail(body);
          setLoading(false);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load your watchlist");
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const watchlistId = detail?.id;
    if (!watchlistId) {
      return;
    }
    async function refreshQuotes() {
      if (document.visibilityState === "hidden") {
        return;
      }
      try {
        setDetail(await getWatchlist(watchlistId));
      } catch {
        return;
      }
    }
    const timer = window.setInterval(() => {
      void refreshQuotes();
    }, QUOTE_REFRESH_MS);
    function onVisible() {
      if (document.visibilityState === "visible") {
        void refreshQuotes();
      }
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [detail?.id]);

  return (
    <section className="max-w-xl space-y-3 rounded-lg border border-slate-200 bg-white p-4" aria-label="Watchlist summary">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-medium text-slate-900">{detail ? detail.name : "Watchlist"}</h2>
        {detail ? (
          <Link to={`/watchlist/${detail.id}`} className="text-sm text-slate-700 underline">
            View watchlist
          </Link>
        ) : null}
      </div>
      {loading ? <p className="text-sm text-slate-600">Loading watchlist…</p> : null}
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {empty ? (
        <p className="text-sm text-slate-600">
          No watchlist yet.{" "}
          <Link to="/watchlist" className="underline">
            Create one
          </Link>
        </p>
      ) : null}
      {detail && detail.stocks.length === 0 ? <p className="text-sm text-slate-600">This watchlist has no stocks yet.</p> : null}
      {detail && detail.stocks.length > 0 ? (
        <ul className="divide-y divide-slate-100">
          {detail.stocks.slice(0, 4).map((stock) => (
            <li key={stock.stock_id} className="flex items-start justify-between gap-3 py-2">
              <div>
                <Link to={`/stocks/${stock.stock_id}`} className="text-sm font-medium text-slate-900">
                  {stock.symbol}
                </Link>
                <p className="text-xs text-slate-500">
                  {stock.exchange}
                  {stock.company_name ? ` · ${stock.company_name}` : ""}
                </p>
              </div>
              <WatchlistQuoteText quote={stock.quote} />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
