import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { AddToWatchlist } from "../components/watchlist/AddToWatchlist.tsx";
import { searchStocks } from "../services/stocks.ts";
import { ApiError } from "../services/http.ts";
import type { StockSearchResult } from "../types/stock.ts";

export function StockSearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const term = query.trim();
    if (term.length === 0) {
      setError("Enter a symbol or company name");
      setResults([]);
      setSearched(false);
      return;
    }
    setPending(true);
    setError("");
    try {
      const body = await searchStocks(term);
      setResults(body.results);
      setSearched(true);
    } catch (caught) {
      setResults([]);
      setSearched(false);
      setError(caught instanceof ApiError ? caught.message : "Search failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Stocks</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Search Indian equities listed on NSE and BSE. Open a listing to see its quote.
        </p>
      </header>
      <form className="flex max-w-xl gap-2" onSubmit={onSubmit}>
        <label className="sr-only" htmlFor="stock-query">
          Symbol or company
        </label>
        <input
          id="stock-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="TCS, Reliance, HDFC"
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 outline-none focus:border-emerald-600"
        />
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {pending ? "Searching…" : "Search"}
        </button>
      </form>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {searched && results.length === 0 ? (
        <p className="text-sm text-slate-600">No Indian listings matched that search.</p>
      ) : null}
      {results.length > 0 ? (
      <ul className="max-w-xl divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
        {results.map((stock) => (
          <li key={stock.id} className="px-4 py-3">
            <Link to={`/stocks/${stock.id}`} className="block rounded-md hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-600">
              <p className="font-medium text-slate-900">{stock.symbol}</p>
              <p className="text-sm text-slate-700">{stock.company_name}</p>
              <p className="mt-1 text-sm text-slate-500">
                {stock.exchange} • {stock.country_name} • {stock.currency}
              </p>
              {stock.sector ? (
                <p className="text-xs text-slate-500">
                  {stock.sector}
                  {stock.industry ? ` · ${stock.industry}` : ""}
                </p>
              ) : null}
            </Link>
            <AddToWatchlist stockId={stock.id} />
          </li>
        ))}
      </ul>
      ) : null}
    </div>
  );
}
