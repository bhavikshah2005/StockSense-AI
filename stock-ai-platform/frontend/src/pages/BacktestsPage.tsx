import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { compareRuns, createRun, deleteRun, listRuns, listStrategies } from "../services/backtests.ts";
import { ApiError } from "../services/http.ts";
import { searchStocks } from "../services/stocks.ts";
import type { BacktestRun, CompareResult, StrategySpec } from "../types/backtest.ts";
import type { StockSearchResult } from "../types/stock.ts";

export function BacktestsPage() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<StrategySpec[] | null>(null);
  const [runs, setRuns] = useState<BacktestRun[] | null>(null);
  const [key, setKey] = useState("");
  const [parameters, setParameters] = useState<Record<string, string>>({});
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<StockSearchResult[]>([]);
  const [stock, setStock] = useState<StockSearchResult | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [capital, setCapital] = useState("100000");
  const [brokerage, setBrokerage] = useState("0.10");
  const [slippage, setSlippage] = useState("5");
  const [position, setPosition] = useState("100");
  const [stop, setStop] = useState("");
  const [target, setTarget] = useState("");
  const [hold, setHold] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [comparison, setComparison] = useState<CompareResult | null>(null);

  const selected = strategies?.find((item) => item.key === key) ?? null;

  useEffect(() => {
    let cancelled = false;
    Promise.all([listStrategies(), listRuns()])
      .then(([catalog, history]) => {
        if (cancelled) {
          return;
        }
        setStrategies(catalog);
        setRuns(history.results);
        const first = catalog[0];
        if (first) {
          setKey(first.key);
          setParameters(Object.fromEntries(first.parameters.map((item) => [item.name, String(item.default)])));
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setStrategies([]);
          setRuns([]);
          setError(caught instanceof ApiError ? caught.message : "Could not load backtests");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function chooseStrategy(next: string) {
    const spec = strategies?.find((item) => item.key === next);
    setKey(next);
    setParameters(spec ? Object.fromEntries(spec.parameters.map((item) => [item.name, String(item.default)])) : {});
  }

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const body = await searchStocks(query);
      setMatches(body.results);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not search stocks");
    }
  }

  async function onRun() {
    if (!selected || !stock) {
      return;
    }
    setPending(true);
    setError("");
    const parsed: Record<string, number> = {};
    for (const item of selected.parameters) {
      parsed[item.name] = Number(parameters[item.name]);
    }
    try {
      const run = await createRun({
        stock_id: stock.id,
        strategy_key: selected.key,
        strategy_version: selected.version,
        parameters: parsed,
        start_date: start,
        end_date: end,
        initial_capital: capital,
        brokerage_percent: brokerage,
        slippage_bps: slippage,
        position_percent: position,
        stop_loss_percent: stop === "" ? null : stop,
        take_profit_percent: target === "" ? null : target,
        max_hold_sessions: hold === "" ? null : Number(hold),
      });
      navigate(`/backtests/${run.id}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not run the backtest");
    } finally {
      setPending(false);
    }
  }

  async function onCompare() {
    if (!left || !right || left === right) {
      return;
    }
    setError("");
    try {
      setComparison(await compareRuns(left, right));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not compare those runs");
    }
  }

  async function onDelete(id: string) {
    setError("");
    try {
      await deleteRun(id);
      const history = await listRuns();
      setRuns(history.results);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete that run");
    }
  }

  const ready = Boolean(selected && stock && start && end && capital && brokerage !== "" && slippage !== "");

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Backtesting</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Test a fixed rule on stored daily bars for one Indian listing. This does not place trades, connect to a broker, or estimate future returns.
        </p>
      </header>
      {error ? <p className="text-sm text-red-700" role="alert">{error}</p> : null}
      <section className="max-w-3xl space-y-4 rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold">Assumptions</h2>
        <p className="text-sm leading-6 text-slate-600">
          The stock master lists current securities. A single-stock result does not account for historical universe selection, and delisted stocks are not included. Prices are raw opens and closes. Splits and dividends are not adjusted. No index history is stored, so there is no benchmark.
        </p>
        {strategies === null ? <p className="text-sm text-slate-600">Loading strategies…</p> : null}
        <label className="block text-sm">
          Strategy
          <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={key} onChange={(event) => chooseStrategy(event.target.value)}>
            {(strategies ?? []).map((item) => (
              <option key={item.key} value={item.key}>{item.name}</option>
            ))}
          </select>
        </label>
        {selected ? (
          <div className="space-y-2 text-sm leading-6 text-slate-700">
            <p>{selected.description}</p>
            <p>Entry: {selected.entry_rule}</p>
            <p>Exit: {selected.exit_rule}</p>
            <p>Direction: long only. Holds overnight. Missing sessions are not filled.</p>
          </div>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2">
          {selected?.parameters.map((item) => (
            <label key={item.name} className="block text-sm">
              {item.label}
              <input
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                inputMode="numeric"
                value={parameters[item.name] ?? ""}
                onChange={(event) => setParameters((current) => ({ ...current, [item.name]: event.target.value }))}
              />
              <span className="mt-1 block text-xs text-slate-500">{item.description} {item.minimum}–{item.maximum}.</span>
            </label>
          ))}
        </div>
        <form className="flex flex-wrap gap-2" onSubmit={onSearch}>
          <input className="min-w-48 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search NSE or BSE symbol" aria-label="Stock search" />
          <button type="submit" className="rounded-md border border-slate-300 px-3 py-2 text-sm">Search</button>
        </form>
        {stock ? <p className="text-sm">Selected: {stock.symbol} · {stock.exchange}</p> : <p className="text-sm text-slate-600">Select a listing from the stock master.</p>}
        <ul className="space-y-1">
          {matches.map((item) => (
            <li key={item.id}>
              <button type="button" className="text-sm text-slate-800 underline" onClick={() => setStock(item)}>
                {item.symbol} · {item.exchange} · {item.company_name}
              </button>
            </li>
          ))}
        </ul>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">Start<input type="date" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={start} onChange={(event) => setStart(event.target.value)} /></label>
          <label className="block text-sm">End<input type="date" className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
          <label className="block text-sm">Initial capital (INR)<input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={capital} onChange={(event) => setCapital(event.target.value)} /></label>
          <label className="block text-sm">Brokerage percent<input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={brokerage} onChange={(event) => setBrokerage(event.target.value)} /></label>
          <label className="block text-sm">Slippage (basis points)<input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={slippage} onChange={(event) => setSlippage(event.target.value)} /></label>
          <label className="block text-sm">Position percent<input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={position} onChange={(event) => setPosition(event.target.value)} /></label>
          <label className="block text-sm">Stop-loss percent (optional)<input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={stop} onChange={(event) => setStop(event.target.value)} /></label>
          <label className="block text-sm">Take-profit percent (optional)<input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={target} onChange={(event) => setTarget(event.target.value)} /></label>
          <label className="block text-sm">Max holding sessions (optional)<input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={hold} onChange={(event) => setHold(event.target.value)} /></label>
        </div>
        {ready && selected && stock ? (
          <div className="space-y-2 rounded-md bg-slate-50 p-3 text-sm leading-6 text-slate-700">
            <h3 className="font-semibold text-slate-900">Review before running</h3>
            <p>{selected.name} on {stock.symbol} ({stock.exchange}), {start} to {end}.</p>
            <p>Capital {capital} INR. Brokerage {brokerage}%. Slippage {slippage} basis points. Position size {position}% of cash. Whole shares. Long only.</p>
            <p>A completed session can signal. The simulated fill is the next stored session open. A stop is not a guarantee if the next open gaps through it. If one candle touches both a stop and a target, the stop is used.</p>
            <p>Zero brokerage and zero slippage are labeled gross. Any configured cost is labeled net. Coverage must already be stored; missing days are not invented.</p>
            <button type="button" className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-60" disabled={pending} onClick={() => void onRun()}>
              {pending ? "Running…" : "Run with these assumptions"}
            </button>
          </div>
        ) : null}
      </section>
      <section className="max-w-3xl space-y-3">
        <h2 className="text-lg font-semibold">Saved runs</h2>
        {runs === null ? <p className="text-sm text-slate-600">Loading runs…</p> : null}
        {runs && runs.length === 0 ? <p className="text-sm text-slate-600">No saved runs yet.</p> : null}
        <ul className="space-y-2">
          {runs?.map((run) => (
            <li key={run.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
              <Link to={`/backtests/${run.id}`} className="font-medium">{run.symbol} · {run.strategy_key} · {run.status}</Link>
              <span className="text-slate-500">{run.requested_start} to {run.requested_end}</span>
              <button type="button" className="text-red-700" onClick={() => void onDelete(run.id)}>Delete</button>
            </li>
          ))}
        </ul>
        {runs && runs.length > 1 ? (
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-sm">First run
              <select className="mt-1 block rounded-md border border-slate-300 px-2 py-2" value={left} onChange={(event) => setLeft(event.target.value)} aria-label="First run">
                <option value="">Select</option>
                {runs.map((run) => <option key={run.id} value={run.id}>{run.symbol} {run.requested_start}</option>)}
              </select>
            </label>
            <label className="text-sm">Second run
              <select className="mt-1 block rounded-md border border-slate-300 px-2 py-2" value={right} onChange={(event) => setRight(event.target.value)} aria-label="Second run">
                <option value="">Select</option>
                {runs.map((run) => <option key={run.id} value={run.id}>{run.symbol} {run.requested_start}</option>)}
              </select>
            </label>
            <button type="button" className="rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={() => void onCompare()}>View together</button>
          </div>
        ) : null}
        {comparison ? <p className="text-sm leading-6 text-slate-700">{comparison.note}</p> : null}
      </section>
    </div>
  );
}
