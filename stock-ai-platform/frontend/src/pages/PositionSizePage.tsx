import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../services/http.ts";
import { calculatePositionSize, getRiskSettings, saveRiskSettings } from "../services/portfolios.ts";
import type { RiskSettings, SizeResult } from "../types/portfolio.ts";
import { formatInr, formatSignedPercent } from "../utils/quote.ts";

const empty: RiskSettings = {
  capital_inr: null,
  max_risk_inr: null,
  max_risk_percent: null,
  max_allocation_percent: null,
  max_shares: null,
};

export function PositionSizePage() {
  const [settings, setSettings] = useState<RiskSettings>(empty);
  const [capital, setCapital] = useState("");
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [riskInr, setRiskInr] = useState("");
  const [riskPercent, setRiskPercent] = useState("");
  const [allocation, setAllocation] = useState("");
  const [shares, setShares] = useState("");
  const [result, setResult] = useState<SizeResult | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    let cancelled = false;
    getRiskSettings()
      .then((row) => {
        if (cancelled) {
          return;
        }
        setSettings(row);
        setCapital(row.capital_inr ?? "");
        setRiskInr(row.max_risk_inr ?? "");
        setRiskPercent(row.max_risk_percent ?? "");
        setAllocation(row.max_allocation_percent ?? "");
        setShares(row.max_shares === null ? "" : String(row.max_shares));
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load planning limits");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function persist() {
    setError("");
    setSaved("");
    const body: RiskSettings = {
      capital_inr: capital || null,
      max_risk_inr: riskInr || null,
      max_risk_percent: riskPercent || null,
      max_allocation_percent: allocation || null,
      max_shares: shares ? Number(shares) : null,
    };
    try {
      const row = await saveRiskSettings(body);
      setSettings(row);
      setSaved("Planning limits saved. They are constraints you entered, not a suggestion.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save planning limits");
    }
  }

  async function calculate(event: FormEvent) {
    event.preventDefault();
    setError("");
    setResult(null);
    try {
      const body = await calculatePositionSize({
        capital,
        entry,
        stop,
        max_risk_inr: riskInr || null,
        max_risk_percent: riskPercent || null,
        max_allocation_percent: allocation || null,
        max_shares: shares ? Number(shares) : null,
      });
      setResult(body);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not calculate a quantity");
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/portfolio" className="text-sm text-slate-600">All portfolios</Link>
      <header>
        <h1 className="text-2xl font-semibold">Position size</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          A hypothetical long-only share count for Indian cash equities. It does not place an order and it is not added to a portfolio unless you record a transaction yourself.
        </p>
      </header>
      {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
      {saved ? <p className="text-sm text-slate-700">{saved}</p> : null}
      <form className="max-w-xl space-y-3" onSubmit={(event) => void calculate(event)}>
        <Field label="Hypothetical capital (INR)" value={capital} onChange={setCapital} />
        <Field label="Entry price (INR)" value={entry} onChange={setEntry} />
        <Field label="Stop price (INR)" value={stop} onChange={setStop} />
        <Field label="Maximum risk (INR)" value={riskInr} onChange={setRiskInr} />
        <Field label="Maximum risk (%)" value={riskPercent} onChange={setRiskPercent} />
        <Field label="Maximum allocation to one stock (%)" value={allocation} onChange={setAllocation} />
        <Field label="Maximum shares" value={shares} onChange={setShares} />
        <div className="flex gap-2">
          <button type="submit" className="rounded-md bg-slate-950 px-3 py-2 text-sm text-white">Calculate</button>
          <button type="button" className="rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={() => void persist()}>Save limits</button>
        </div>
      </form>
      <p className="max-w-2xl text-sm text-slate-600">Saved capital {settings.capital_inr ?? "not set"}. These fields do not change a portfolio.</p>
      {result ? (
        <section className="max-w-xl space-y-2 rounded-lg border border-slate-200 bg-white p-4 text-sm">
          <h2 className="font-medium">{result.quantity} shares</h2>
          <p>Position value {formatInr(result.position_value)}. Per-share risk {formatInr(result.per_share_risk)}. Scenario risk {formatInr(result.total_risk)}.</p>
          <p>Capital used {formatSignedPercent(result.capital_utilization_percent) ?? `${result.capital_utilization_percent}%`}. Binding limit: {result.binding_constraint}.</p>
          <p>{result.assumptions}</p>
          <p className="text-amber-800">{result.warning} A stop may not execute at the price you entered. Gaps, slippage, and fees can make the loss larger.</p>
        </section>
      ) : null}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm">{label}
      <input aria-label={label} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
