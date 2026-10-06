import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../services/http.ts";
import { searchStocks } from "../../services/stocks.ts";
import { addWatchlistStock } from "../../services/watchlists.ts";
import type { StockSearchResult } from "../../types/stock.ts";

const SUGGESTION_DELAY_MS = 200;

export function StockSearchAdd({
  watchlistId,
  memberIds,
  onAdded,
}: {
  watchlistId: string;
  memberIds: string[];
  onAdded: () => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [matchedQuery, setMatchedQuery] = useState("");
  const [active, setActive] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [searching, setSearching] = useState(false);
  const [pending, setPending] = useState(false);
  const requestId = useRef(0);

  const term = query.trim();
  const suggestions =
    term.length === 0
      ? []
      : results.filter((stock) => {
          const needle = term.toLowerCase();
          return (
            stock.symbol.toLowerCase().includes(needle) ||
            stock.company_name.toLowerCase().includes(needle) ||
            (stock.isin ?? "").toLowerCase().includes(needle)
          );
        });

  const runSearch = useCallback(async (nextTerm: string) => {
    const id = ++requestId.current;
    setSearching(true);
    setError("");
    try {
      const body = await searchStocks(nextTerm);
      if (id !== requestId.current) {
        return;
      }
      setResults(body.results);
      setMatchedQuery(nextTerm);
      setActive(0);
    } catch (caught) {
      if (id !== requestId.current) {
        return;
      }
      setResults([]);
      setMatchedQuery(nextTerm);
      setError(caught instanceof ApiError ? caught.message : "Search failed");
    } finally {
      if (id === requestId.current) {
        setSearching(false);
      }
    }
  }, []);

  useEffect(() => {
    if (term.length === 0) {
      requestId.current += 1;
      setResults([]);
      setMatchedQuery("");
      setSearching(false);
      setError("");
      return;
    }
    const timer = window.setTimeout(() => {
      void runSearch(term);
    }, SUGGESTION_DELAY_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [term, runSearch]);

  function searchNow(event: FormEvent) {
    event.preventDefault();
    if (term.length === 0) {
      setError("Enter a symbol or company name");
      setResults([]);
      setMatchedQuery("");
      return;
    }
    void runSearch(term);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (suggestions.length === 0) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((value) => Math.min(value + 1, suggestions.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const stock = suggestions[active];
      if (stock) {
        void add(stock);
      }
    }
  }

  async function add(stock: StockSearchResult) {
    if (memberIds.includes(stock.id)) {
      setNotice("That stock is already on this watchlist");
      setError("");
      return;
    }
    setPending(true);
    setError("");
    setNotice("");
    try {
      await addWatchlistStock(watchlistId, stock.id);
      setNotice(`Added ${stock.symbol}`);
      await onAdded();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not add this stock");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="space-y-3" aria-label="Add a stock">
      <h2 className="text-sm font-medium text-slate-900">Add a stock</h2>
      <form className="flex max-w-xl gap-2" onSubmit={searchNow}>
        <label className="sr-only" htmlFor="watchlist-stock-query">
          Symbol or company
        </label>
        <input
          id="watchlist-stock-query"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setNotice("");
          }}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={suggestions.length > 0}
          aria-controls="watchlist-stock-results"
          aria-activedescendant={suggestions[active] ? `watchlist-option-${suggestions[active].id}` : undefined}
          placeholder="TCS, Reliance, HDFC"
          autoComplete="off"
          spellCheck={false}
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 outline-none focus:border-emerald-600"
        />
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          Search
        </button>
      </form>
      {error ? (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="text-sm text-emerald-700" role="status">
          {notice}
        </p>
      ) : null}
      {searching && suggestions.length === 0 ? (
        <p className="text-sm text-slate-600" role="status">
          Searching…
        </p>
      ) : null}
      {!searching && matchedQuery === term && term.length > 0 && suggestions.length === 0 ? (
        <p className="text-sm text-slate-600">No Indian listings matched that search.</p>
      ) : null}
      {suggestions.length > 0 ? (
        <ul id="watchlist-stock-results" role="listbox" className="max-w-xl divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {suggestions.map((stock, index) => {
            const already = memberIds.includes(stock.id);
            return (
              <li
                key={stock.id}
                id={`watchlist-option-${stock.id}`}
                role="option"
                aria-selected={index === active}
                className={`flex items-start justify-between gap-3 px-4 py-3 ${index === active ? "bg-slate-50" : ""}`}
              >
                <div>
                  <p className="font-medium text-slate-900">{stock.symbol}</p>
                  <p className="text-sm text-slate-700">{stock.company_name}</p>
                  <p className="text-sm text-slate-500">{stock.exchange}</p>
                  <Link to={`/stocks/${stock.id}`} className="mt-1 inline-block text-sm text-slate-700 underline">
                    Open {stock.symbol}
                  </Link>
                </div>
                <button
                  type="button"
                  disabled={pending || already}
                  onClick={() => {
                    void add(stock);
                  }}
                  className="rounded-md bg-slate-950 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
                >
                  {already ? "Already on this watchlist" : "Add"}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
