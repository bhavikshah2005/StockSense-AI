import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { getEquity, getRun, getTrades } from "../services/backtests.ts";
import { ApiError } from "../services/http.ts";
import type { BacktestRun, BacktestTrade, EquityPoint } from "../types/backtest.ts";
import { formatInr, formatIst, formatSignedPercent } from "../utils/quote.ts";

function metric(label: string, value: string | null, reason: string | null) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-medium">{value ?? "Unavailable"}</p>
      {value === null && reason ? <p className="mt-1 text-xs leading-5 text-slate-500">{reason}</p> : null}
    </div>
  );
}

export function BacktestDetailPage() {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<BacktestRun | null>(null);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([getRun(runId), getTrades(runId), getEquity(runId)])
      .then(([saved, tradePage, equityPage]) => {
        if (cancelled) {
          return;
        }
        setRun(saved);
        setTrades(tradePage.results);
        setEquity(equityPage.results);
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load this backtest");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  if (error) {
    return <p className="text-sm text-red-700" role="alert">{error}</p>;
  }
  if (!run) {
    return <p className="text-sm text-slate-600">Loading backtest…</p>;
  }
  const summary = run.summary;
  const points = equity.map((point) => ({
    label: formatIst(point.point_at) ?? point.point_at,
    equity: Number(point.equity),
    drawdown: Number(point.drawdown_percent),
  }));

  return (
    <div className="space-y-6">
      <header>
        <Link to="/backtests" className="text-sm text-slate-600">Back to runs</Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{run.symbol} · {run.exchange}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          {run.strategy_key} version {run.strategy_version}. Status {run.status}. Engine {run.engine_version}. Source {run.data_source}. Price basis {run.price_basis}.
        </p>
      </header>
      {run.warnings.map((warning) => (
        <p key={warning} className="max-w-3xl text-sm leading-6 text-amber-900">{warning}</p>
      ))}
      {run.error_detail ? <p className="max-w-3xl text-sm leading-6 text-slate-700">{run.error_detail}</p> : null}
      {run.status === "insufficient_data" ? <p className="text-sm text-slate-700">No performance figures were calculated for this period.</p> : null}
      {summary ? (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {metric("Result basis", summary.result_basis, null)}
          {metric("Final equity", formatInr(summary.final_equity) ?? summary.final_equity, null)}
          {metric("Total return", summary.total_return_percent ? formatSignedPercent(summary.total_return_percent) ?? summary.total_return_percent : null, null)}
          {metric("Annualized return", summary.annualized_return_percent ? formatSignedPercent(summary.annualized_return_percent) ?? summary.annualized_return_percent : null, summary.annualized_return_reason)}
          {metric("Max drawdown", summary.max_drawdown_percent ? `${summary.max_drawdown_percent}%` : null, null)}
          {metric("Win rate", summary.win_rate_percent ? `${summary.win_rate_percent}%` : null, summary.win_rate_reason)}
          {metric("Profit factor", summary.profit_factor, summary.profit_factor_reason)}
          {metric("Costs", formatInr(summary.transaction_costs_inr) ?? summary.transaction_costs_inr, null)}
          {metric("Benchmark", summary.benchmark.available ? "Available" : null, summary.benchmark.reason)}
        </section>
      ) : null}
      {points.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Equity and drawdown</h2>
          <p className="text-sm text-slate-600">Ending equity {formatInr(equity[equity.length - 1].equity) ?? equity[equity.length - 1].equity}. Largest stored drawdown {equity.reduce((max, point) => Math.max(max, Number(point.drawdown_percent)), 0).toFixed(2)}%.</p>
          <div className="h-56 w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="label" hide />
                <YAxis tick={{ fontSize: 12 }} width={72} />
                <Tooltip />
                <Area dataKey="equity" stroke="#0f172a" fill="#e2e8f0" name="Equity" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="h-40 w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="label" hide />
                <YAxis tick={{ fontSize: 12 }} width={72} />
                <Tooltip />
                <Area dataKey="drawdown" stroke="#b45309" fill="#ffedd5" name="Drawdown %" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Trades</h2>
        {trades.length === 0 ? <p className="text-sm text-slate-600">No simulated trades were stored for this run.</p> : null}
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-2 py-2">#</th>
                <th className="px-2 py-2">Signal</th>
                <th className="px-2 py-2">Entry</th>
                <th className="px-2 py-2">Exit</th>
                <th className="px-2 py-2">Shares</th>
                <th className="px-2 py-2">Prices</th>
                <th className="px-2 py-2">Charges</th>
                <th className="px-2 py-2">Reason</th>
                <th className="px-2 py-2">P&L</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr key={trade.trade_number} className="border-b border-slate-100">
                  <td className="px-2 py-2">{trade.trade_number}</td>
                  <td className="px-2 py-2">{formatIst(trade.signal_at) ?? trade.signal_at}</td>
                  <td className="px-2 py-2">{formatIst(trade.entry_at) ?? trade.entry_at}</td>
                  <td className="px-2 py-2">{formatIst(trade.exit_at) ?? trade.exit_at}</td>
                  <td className="px-2 py-2">{trade.shares}</td>
                  <td className="px-2 py-2">{trade.entry_price} → {trade.exit_price}</td>
                  <td className="px-2 py-2">{trade.entry_charges} + {trade.exit_charges}</td>
                  <td className="px-2 py-2">{trade.exit_reason}</td>
                  <td className="px-2 py-2">{formatInr(trade.pnl) ?? trade.pnl}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
