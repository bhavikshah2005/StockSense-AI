import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { StockHistory } from "../components/charts/StockHistory.tsx";
import { AddToWatchlist } from "../components/watchlist/AddToWatchlist.tsx";
import { FundamentalsPanel } from "../components/fundamentals/FundamentalsPanel.tsx";
import { NewsFeed } from "../components/news/NewsFeed.tsx";
import { ResearchPanel } from "../components/research/ResearchPanel.tsx";
import { TechnicalWorkspace } from "../components/technical/TechnicalWorkspace.tsx";
import { ApiError } from "../services/http.ts";
import { getQuote, getStock } from "../services/stocks.ts";
import type { Quote, StockDetail } from "../types/stock.ts";
import { formatInr, formatIst, formatSignedInr, formatSignedPercent, formatVolume } from "../utils/quote.ts";

type QuoteState = "loading" | "ready" | "unavailable";

export function StockDetailPage() {
  const { stockId = "" } = useParams();
  const [stock, setStock] = useState<StockDetail | null>(null);
  const [stockError, setStockError] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteState, setQuoteState] = useState<QuoteState>("loading");
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setStock(null);
    setStockError("");
    setQuote(null);
    setQuoteState("loading");

    async function load() {
      try {
        const listing = await getStock(stockId);
        if (cancelled) {
          return;
        }
        setStock(listing);
        const body = await getQuote(stockId);
        if (cancelled) {
          return;
        }
        setQuote(body);
        setQuoteState("ready");
      } catch (caught) {
        if (cancelled) {
          return;
        }
        if (caught instanceof ApiError && (caught.status === 404 || caught.status === 422)) {
          setStockError(caught.status === 404 ? "This stock was not found." : "Exchange is not supported");
          setQuoteState("unavailable");
          return;
        }
        setQuote(null);
        setQuoteState("unavailable");
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [stockId]);

  useEffect(() => {
    if (quoteState !== "ready") {
      return;
    }
    async function refreshQuote() {
      if (document.visibilityState === "hidden") {
        return;
      }
      try {
        setQuote(await getQuote(stockId));
      } catch {
        return;
      }
    }
    const timer = window.setInterval(() => {
      void refreshQuote();
    }, 15_000);
    function onVisible() {
      if (document.visibilityState === "visible") {
        void refreshQuote();
      }
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [quoteState, stockId]);

  async function refresh() {
    setRefreshing(true);
    try {
      const body = await getQuote(stockId);
      setQuote(body);
      setQuoteState("ready");
    } catch {
      setQuote(null);
      setQuoteState("unavailable");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/stocks" className="text-sm text-slate-600">
        Back to search
      </Link>
      {!stock && !stockError ? <p className="text-sm text-slate-600">Loading stock…</p> : null}
      {stockError ? <p className="text-sm text-slate-700">{stockError}</p> : null}
      {stock ? (
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">{stock.company_name}</h1>
          <p className="mt-1 text-lg text-slate-900">{stock.symbol}</p>
          <p className="mt-1 text-sm text-slate-500">
            {stock.exchange} • {stock.country_name} • {stock.currency}
          </p>
          {stock.sector ? (
            <p className="text-xs text-slate-500">
              {stock.sector}
              {stock.industry ? ` · ${stock.industry}` : ""}
            </p>
          ) : null}
          <AddToWatchlist stockId={stock.id} />
        </header>
      ) : null}
      {stock && quoteState === "loading" ? <p className="text-sm text-slate-600">Loading quote…</p> : null}
      {stock && !stockError && quoteState === "unavailable" ? (
        <div className="max-w-xl space-y-3">
          <p className="text-sm text-slate-700">Market data is temporarily unavailable.</p>
          <button
            type="button"
            onClick={() => {
              void refresh();
            }}
            disabled={refreshing}
            className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      ) : null}
      {stock && quote && quoteState === "ready" ? <QuotePanel quote={quote} refreshing={refreshing} onRefresh={() => void refresh()} /> : null}
      {stock && !stockError ? <StockHistory stockId={stock.id} exchange={stock.exchange} /> : null}
      {stock && !stockError ? <TechnicalWorkspace stockId={stock.id} /> : null}
      {stock && !stockError ? <FundamentalsPanel stockId={stock.id} /> : null}
      {stock && !stockError ? <NewsFeed stockId={stock.id} compact /> : null}
      {stock && !stockError ? <ResearchPanel stockId={stock.id} /> : null}
    </div>
  );
}

function QuotePanel({
  quote,
  refreshing,
  onRefresh,
}: {
  quote: Quote;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const price = quote.currency === "INR" ? formatInr(quote.current_price) : null;
  const fetchedTime = formatIst(quote.fetched_at);
  if (price === null || fetchedTime === null) {
    return <p className="text-sm text-slate-700">Market data is temporarily unavailable.</p>;
  }
  const change = quote.change === null ? null : formatSignedInr(quote.change);
  const percent = quote.change_percent === null ? null : formatSignedPercent(quote.change_percent);
  const direction = quote.change === null ? "flat" : Number(quote.change) > 0 ? "up" : Number(quote.change) < 0 ? "down" : "flat";
  const changeClass = direction === "up" ? "text-emerald-700" : direction === "down" ? "text-red-700" : "text-slate-700";
  const fields = [
    ["Open", money(quote.open)],
    ["High", money(quote.high)],
    ["Low", money(quote.low)],
    ["Previous close", money(quote.previous_close)],
    ["Volume", quote.volume === null ? null : formatVolume(quote.volume)],
  ].filter((field): field is [string, string] => field[1] !== null);

  return (
    <section className="max-w-xl space-y-4">
      <p className="text-3xl font-semibold tracking-tight text-slate-950">{price}</p>
      {change && percent ? <p className={`text-sm font-medium ${changeClass}`}>{`${change} (${percent})`}</p> : null}
      {fields.length > 0 ? (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {fields.map(([label, value]) => (
            <div key={label} className="rounded-md border border-slate-200 bg-white px-3 py-2">
              <dt className="text-xs text-slate-500">{label}</dt>
              <dd className="mt-1 text-sm font-medium text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <p className="text-xs text-slate-500">{fetchedTime}</p>
      <button
        type="button"
        onClick={onRefresh}
        disabled={refreshing}
        className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {refreshing ? "Refreshing…" : "Refresh"}
      </button>
    </section>
  );
}

function money(value: string | null): string | null {
  if (value === null) {
    return null;
  }
  return formatInr(value);
}
