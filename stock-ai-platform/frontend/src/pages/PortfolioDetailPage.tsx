import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../services/http.ts";
import { createCash, createTransaction, deleteTransaction, getHistory, getValuation, listTransactions } from "../services/portfolios.ts";
import { searchStocks } from "../services/stocks.ts";
import type { PortfolioHistory, PortfolioTransaction, Valuation } from "../types/portfolio.ts";
import { formatInr, formatIst, formatSignedInr, formatSignedPercent } from "../utils/quote.ts";

export function PortfolioDetailPage() {
  const { portfolioId = "" } = useParams();
  const [valuation, setValuation] = useState<Valuation | null>(null);
  const [history, setHistory] = useState<PortfolioHistory | null>(null);
  const [transactions, setTransactions] = useState<PortfolioTransaction[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<Array<{ id: string; symbol: string; exchange: string }>>([]);
  const [stockId, setStockId] = useState("");
  const [side, setSide] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [charges, setCharges] = useState("0");
  const [tradedAt, setTradedAt] = useState("");
  const [cashKind, setCashKind] = useState("deposit");
  const [cashAmount, setCashAmount] = useState("");

  async function refresh() {
    const [valued, past, rows] = await Promise.all([getValuation(portfolioId), getHistory(portfolioId), listTransactions(portfolioId)]);
    setValuation(valued);
    setHistory(past);
    setTransactions(rows);
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    refresh()
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load this portfolio");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  async function lookup() {
    const body = await searchStocks(query);
    setMatches(body.results.map((row) => ({ id: row.id, symbol: row.symbol, exchange: row.exchange })));
  }

  async function addTrade(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await createTransaction(portfolioId, {
        stock_id: stockId,
        side,
        quantity,
        price,
        charges: charges || "0",
        traded_at: new Date(tradedAt).toISOString(),
        note: null,
      });
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the transaction");
    }
  }

  async function addCash(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await createCash(portfolioId, { kind: cashKind, amount: cashAmount, occurred_at: new Date().toISOString(), note: null });
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the cash record");
    }
  }

  async function removeTrade(id: string) {
    setError("");
    try {
      await deleteTransaction(portfolioId, id);
      await refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete the transaction");
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/portfolio" className="text-sm text-slate-600">All portfolios</Link>
      {loading ? <p className="text-sm text-slate-600">Loading portfolio…</p> : null}
      {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
      {valuation ? (
        <>
          <header>
            <h1 className="text-2xl font-semibold">Holdings value</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">{valuation.basis} {valuation.benchmark_note}</p>
            <p className="mt-2 text-sm text-slate-500">As of {formatIst(valuation.as_of)}</p>
          </header>
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Market value" value={valuation.valuation_complete && valuation.market_value ? formatInr(valuation.market_value) ?? valuation.market_value : "Unavailable"} />
            <Metric label="Cash" value={formatInr(valuation.cash) ?? valuation.cash} />
            <Metric label="Realized P&L" value={formatSignedInr(valuation.realized_pnl) ?? valuation.realized_pnl} />
            <Metric label="Unrealized P&L" value={valuation.unrealized_pnl ? formatSignedInr(valuation.unrealized_pnl) ?? valuation.unrealized_pnl : "Unavailable"} />
            <Metric label="Total P&L" value={valuation.total_pnl ? formatSignedInr(valuation.total_pnl) ?? valuation.total_pnl : "Unavailable"} />
            <Metric label="Cost basis" value={formatInr(valuation.cost_basis) ?? valuation.cost_basis} />
          </div>
          {!valuation.valuation_complete ? <p className="text-sm text-amber-800">At least one holding has a missing or stale price, so market value and total P&L are not shown as a complete figure.</p> : null}
          <section className="overflow-x-auto">
            <h2 className="text-lg font-medium">Holdings</h2>
            {valuation.holdings.length === 0 ? <p className="mt-2 text-sm text-slate-600">No open holdings. Add a deposit, then a buy.</p> : null}
            <table className="mt-2 min-w-full text-left text-sm">
              <thead className="text-slate-500">
                <tr><th className="py-2 pr-3">Stock</th><th className="py-2 pr-3">Qty</th><th className="py-2 pr-3">Avg cost</th><th className="py-2 pr-3">Last price</th><th className="py-2 pr-3">Value</th><th className="py-2">P&L</th></tr>
              </thead>
              <tbody>
                {valuation.holdings.map((row) => (
                  <tr key={row.stock_id} className="border-t border-slate-100">
                    <td className="py-2 pr-3">
                      <Link className="underline" to={`/stocks/${row.stock_id}`}>{row.symbol}</Link>
                      <span className="block text-xs text-slate-500">{row.exchange} · stock detail includes technicals, fundamentals, news, and AI research</span>
                    </td>
                    <td className="py-2 pr-3">{row.quantity}</td>
                    <td className="py-2 pr-3">{formatInr(row.average_cost) ?? row.average_cost}</td>
                    <td className="py-2 pr-3">
                      {row.last_price ? formatInr(row.last_price) : "Price unavailable"}
                      <span className="block text-xs text-slate-500">{row.price_state}{row.price_timestamp ? ` · ${formatIst(row.price_timestamp)}` : ""}</span>
                    </td>
                    <td className="py-2 pr-3">{row.market_value ? formatInr(row.market_value) : "Not included"}</td>
                    <td className="py-2">{row.unrealized_pnl ? `${formatSignedInr(row.unrealized_pnl)} (${formatSignedPercent(row.unrealized_pnl_percent ?? "") ?? ""})` : "Unavailable"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section>
            <h2 className="text-lg font-medium">Allocation</h2>
            {valuation.allocation.status === "insufficient_data" ? <p className="mt-2 text-sm text-slate-600">Allocation needs a usable price for at least one holding.</p> : null}
            <ul className="mt-2 space-y-2">
              {valuation.allocation.by_stock.map((slice) => (
                <li key={slice.stock_id ?? slice.symbol}>
                  <div className="flex justify-between text-sm"><span>{slice.symbol}</span><span>{slice.weight_percent}%</span></div>
                  <div className="h-2 rounded bg-slate-100"><div className="h-2 rounded bg-slate-800" style={{ width: `${slice.weight_percent}%` }} /></div>
                </li>
              ))}
            </ul>
            {valuation.allocation.by_sector.length > 0 ? (
              <ul className="mt-3 space-y-1 text-sm text-slate-700">
                {valuation.allocation.by_sector.map((slice) => <li key={slice.sector}>{slice.sector}: {slice.weight_percent}%</li>)}
              </ul>
            ) : null}
            {valuation.allocation.unpriced_symbols.length > 0 ? <p className="mt-2 text-sm text-amber-800">Not included in the weights: {valuation.allocation.unpriced_symbols.join(", ")}.</p> : null}
          </section>
          <section>
            <h2 className="text-lg font-medium">Value history</h2>
            <p className="mt-2 text-sm text-slate-600">{history?.message}</p>
            {history && history.points.length > 0 ? (
              <ul className="mt-2 text-sm text-slate-700">
                {history.points.slice(-5).map((point) => <li key={point.date}>{point.date}: {formatInr(point.holdings_value)}</li>)}
              </ul>
            ) : null}
          </section>
        </>
      ) : null}
      <form className="max-w-xl space-y-3 rounded-lg border border-slate-200 bg-white p-4" onSubmit={(event) => void addCash(event)}>
        <h2 className="font-medium">Cash</h2>
        <p className="text-sm text-slate-600">Cash starts at zero. A buy uses cash. A sell adds the proceeds after charges. A withdrawal cannot make cash negative.</p>
        <label className="block text-sm">Kind
          <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={cashKind} onChange={(event) => setCashKind(event.target.value)}>
            <option value="deposit">Deposit</option>
            <option value="withdrawal">Withdrawal</option>
          </select>
        </label>
        <label className="block text-sm">Amount (INR)
          <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={cashAmount} onChange={(event) => setCashAmount(event.target.value)} required />
        </label>
        <button type="submit" className="rounded-md bg-slate-950 px-3 py-2 text-sm text-white">Save cash record</button>
      </form>
      <form className="max-w-xl space-y-3 rounded-lg border border-slate-200 bg-white p-4" onSubmit={(event) => void addTrade(event)}>
        <h2 className="font-medium">Transaction</h2>
        <div className="flex gap-2">
          <input aria-label="Find stock" className="w-full rounded-md border border-slate-300 px-3 py-2" value={query} onChange={(event) => setQuery(event.target.value)} />
          <button type="button" className="rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={() => void lookup()}>Find</button>
        </div>
        {matches.length > 0 ? (
          <ul className="text-sm">
            {matches.map((match) => (
              <li key={match.id}><button type="button" className="underline" onClick={() => setStockId(match.id)}>{match.symbol} · {match.exchange}</button></li>
            ))}
          </ul>
        ) : null}
        <label className="block text-sm">Side
          <select aria-label="Side" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={side} onChange={(event) => setSide(event.target.value)}>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </label>
        <label className="block text-sm">Quantity
          <input aria-label="Quantity" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
        </label>
        <label className="block text-sm">Price (INR)
          <input aria-label="Price" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={price} onChange={(event) => setPrice(event.target.value)} required />
        </label>
        <label className="block text-sm">Charges (INR)
          <input aria-label="Charges" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={charges} onChange={(event) => setCharges(event.target.value)} />
        </label>
        <label className="block text-sm">Trade time
          <input aria-label="Trade time" type="datetime-local" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={tradedAt} onChange={(event) => setTradedAt(event.target.value)} required />
        </label>
        <button type="submit" className="rounded-md bg-slate-950 px-3 py-2 text-sm text-white">Save transaction</button>
      </form>
      <section>
        <h2 className="text-lg font-medium">Transactions</h2>
        {transactions.length === 0 ? <p className="mt-2 text-sm text-slate-600">No transactions yet.</p> : null}
        <ul className="mt-2 space-y-2 text-sm">
          {transactions.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 px-3 py-2">
              <span>{row.side} {row.quantity} {row.symbol} at {formatInr(row.price) ?? row.price} · charges {formatInr(row.charges) ?? row.charges}</span>
              <span className="flex gap-2">
                <Link className="underline" to={`/stocks/${row.stock_id}`}>Stock</Link>
                <Link className="underline" to="/alerts">Alerts</Link>
                <button type="button" className="underline" onClick={() => void removeTrade(row.id)}>Delete</button>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-medium">{value}</p>
    </div>
  );
}
