import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { StockSearchAdd } from "../components/watchlist/StockSearchAdd.tsx";
import { WatchlistQuoteText } from "../components/watchlist/WatchlistQuoteText.tsx";
import { ApiError } from "../services/http.ts";
import { getWatchlist, removeWatchlistStock, reorderWatchlist } from "../services/watchlists.ts";
import type { WatchlistDetail, WatchlistEntry } from "../types/watchlist.ts";

const QUOTE_REFRESH_MS = 15_000;

function formatAdded(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown date";
  }
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(parsed);
}

export function WatchlistDetailPage() {
  const { watchlistId = "" } = useParams();
  const [detail, setDetail] = useState<WatchlistDetail | null>(null);
  const [error, setError] = useState("");
  const [missing, setMissing] = useState(false);
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);

  const load = useCallback(async () => {
    const body = await getWatchlist(watchlistId);
    setDetail(body);
    setMissing(false);
  }, [watchlistId]);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError("");
    setMissing(false);
    getWatchlist(watchlistId)
      .then((body) => {
        if (!cancelled) {
          setDetail(body);
        }
      })
      .catch((caught: unknown) => {
        if (cancelled) {
          return;
        }
        if (caught instanceof ApiError && caught.status === 404) {
          setMissing(true);
          return;
        }
        setError(caught instanceof ApiError ? caught.message : "Could not load this watchlist");
      });
    return () => {
      cancelled = true;
    };
  }, [watchlistId]);

  useEffect(() => {
    if (!watchlistId) {
      return;
    }
    async function refreshQuotes() {
      if (document.visibilityState === "hidden" || pendingRef.current) {
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
  }, [watchlistId]);

  async function move(index: number, direction: -1 | 1) {
    if (!detail) {
      return;
    }
    const next = index + direction;
    if (next < 0 || next >= detail.stocks.length) {
      return;
    }
    const ids = detail.stocks.map((stock) => stock.stock_id);
    const [moved] = ids.splice(index, 1);
    ids.splice(next, 0, moved);
    pendingRef.current = true;
    setPending(true);
    setError("");
    try {
      const body = await reorderWatchlist(detail.id, ids);
      setDetail(body);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the new order");
      try {
        await load();
      } catch {
        setDetail(detail);
      }
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  }

  async function remove(stockId: string) {
    if (!detail) {
      return;
    }
    pendingRef.current = true;
    setPending(true);
    setError("");
    try {
      await removeWatchlistStock(detail.id, stockId);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not remove this stock");
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/watchlist" className="text-sm text-slate-600">
        All watchlists
      </Link>
      {!detail && !missing && !error ? <p className="text-sm text-slate-600">Loading watchlist…</p> : null}
      {missing ? <p className="text-sm text-slate-700">Watchlist not found.</p> : null}
      {error ? (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      {detail ? (
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">
            {detail.name}
            {detail.is_default ? (
              <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-normal text-slate-600">Default</span>
            ) : null}
          </h1>
          {detail.description ? <p className="mt-2 text-sm text-slate-600">{detail.description}</p> : null}
          <p className="mt-1 text-sm text-slate-500">
            {detail.stock_count} {detail.stock_count === 1 ? "stock" : "stocks"}
          </p>
        </header>
      ) : null}
      {detail && detail.stocks.length === 0 ? (
        <p className="text-sm text-slate-600">This watchlist is empty. Search below to add an Indian listing.</p>
      ) : null}
      {detail && detail.stocks.length > 0 ? (
        <>
          <div className="hidden overflow-x-auto md:block" data-testid="watchlist-table">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className="py-2 pr-3 font-medium">Company</th>
                  <th className="py-2 pr-3 font-medium">Symbol</th>
                  <th className="py-2 pr-3 font-medium">Exchange</th>
                  <th className="py-2 pr-3 font-medium">Quote</th>
                  <th className="py-2 pr-3 font-medium">Sector</th>
                  <th className="py-2 pr-3 font-medium">Added</th>
                  <th className="py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {detail.stocks.map((stock, index) => (
                  <tr key={stock.stock_id} className="border-t border-slate-100">
                    <td className="py-3 pr-3">
                      <Link to={`/stocks/${stock.stock_id}`} className="text-slate-900 underline">
                        {stock.company_name}
                      </Link>
                    </td>
                    <td className="py-3 pr-3">{stock.symbol}</td>
                    <td className="py-3 pr-3">{stock.exchange}</td>
                    <td className="py-3 pr-3">
                      <WatchlistQuoteText quote={stock.quote} />
                    </td>
                    <td className="py-3 pr-3 text-slate-600">{stock.sector ?? "—"}</td>
                    <td className="py-3 pr-3 text-slate-600">{formatAdded(stock.added_at)}</td>
                    <td className="py-3">
                      <RowActions
                        stock={stock}
                        index={index}
                        total={detail.stocks.length}
                        pending={pending}
                        onMove={(direction) => void move(index, direction)}
                        onRemove={() => void remove(stock.stock_id)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="space-y-3 md:hidden" data-testid="watchlist-cards">
            {detail.stocks.map((stock, index) => (
              <li key={stock.stock_id} className="rounded-lg border border-slate-200 bg-white p-4">
                <Link to={`/stocks/${stock.stock_id}`} className="font-medium text-slate-900">
                  {stock.company_name}
                </Link>
                <p className="text-sm text-slate-700">
                  {stock.symbol} · {stock.exchange}
                </p>
                {stock.sector ? <p className="text-xs text-slate-500">{stock.sector}</p> : null}
                <div className="mt-2">
                  <WatchlistQuoteText quote={stock.quote} />
                </div>
                <p className="mt-1 text-xs text-slate-500">Added {formatAdded(stock.added_at)}</p>
                <div className="mt-3">
                  <RowActions
                    stock={stock}
                    index={index}
                    total={detail.stocks.length}
                    pending={pending}
                    onMove={(direction) => void move(index, direction)}
                    onRemove={() => void remove(stock.stock_id)}
                  />
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {detail ? (
        <StockSearchAdd
          watchlistId={detail.id}
          memberIds={detail.stocks.map((stock) => stock.stock_id)}
          onAdded={async () => {
            await load();
          }}
        />
      ) : null}
    </div>
  );
}

function RowActions({
  stock,
  index,
  total,
  pending,
  onMove,
  onRemove,
}: {
  stock: WatchlistEntry;
  index: number;
  total: number;
  pending: boolean;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        aria-label={`Move ${stock.symbol} up`}
        disabled={pending || index === 0}
        onClick={() => onMove(-1)}
        className="rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-40"
      >
        Up
      </button>
      <button
        type="button"
        aria-label={`Move ${stock.symbol} down`}
        disabled={pending || index === total - 1}
        onClick={() => onMove(1)}
        className="rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-40"
      >
        Down
      </button>
      <button
        type="button"
        aria-label={`Remove ${stock.symbol}`}
        disabled={pending}
        onClick={onRemove}
        className="rounded-md border border-slate-300 px-2 py-1 text-xs disabled:opacity-40"
      >
        Remove
      </button>
    </div>
  );
}
