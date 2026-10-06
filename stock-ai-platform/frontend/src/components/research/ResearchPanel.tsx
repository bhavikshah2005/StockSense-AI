import { useEffect, useState } from "react";

import { ApiError } from "../../services/http.ts";
import { getLatestResearch, getResearchMethodology, listResearch, requestResearch } from "../../services/research.ts";
import type { ResearchMethodology, ResearchRun } from "../../types/research.ts";
import { formatIst } from "../../utils/quote.ts";

export function ResearchPanel({ stockId }: { stockId: string }) {
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [history, setHistory] = useState<ResearchRun[]>([]);
  const [method, setMethod] = useState<ResearchMethodology | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([getResearchMethodology(), listResearch(stockId)])
      .then(async ([methodology, past]) => {
        if (cancelled) {
          return;
        }
        setMethod(methodology);
        setHistory(past.results);
        try {
          const latest = await getLatestResearch(stockId);
          if (!cancelled) {
            setRun(latest);
          }
        } catch (caught) {
          if (caught instanceof ApiError && caught.status === 404) {
            if (!cancelled) {
              setRun(null);
            }
          } else {
            throw caught;
          }
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load research");
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
  }, [stockId]);

  async function onRequest(refresh: boolean) {
    setPending(true);
    setError("");
    try {
      const created = await requestResearch(stockId, refresh);
      setRun(created);
      const past = await listResearch(stockId);
      setHistory(past.results);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not run research");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="space-y-3" aria-label="AI analysis">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">AI analysis</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            Research explains stored evidence. It is not a forecast, a target price, or a buy or sell instruction.
          </p>
        </div>
        <button
          type="button"
          className="rounded-md bg-slate-950 px-3 py-2 text-sm text-white disabled:opacity-60"
          disabled={pending}
          onClick={() => void onRequest(run !== null)}
        >
          {pending ? "Running…" : run ? "Refresh analysis" : "Request analysis"}
        </button>
      </div>
      {method ? <p className="text-xs text-slate-500">{method.scoring_note}</p> : null}
      {loading ? <p className="text-sm text-slate-600">Loading research…</p> : null}
      {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
      {!loading && !run && !error ? <p className="text-sm text-slate-600">No analysis has been stored for this stock.</p> : null}
      {run ? <ResearchBody run={run} /> : null}
      {history.length > 1 ? (
        <div>
          <h3 className="text-sm font-medium text-slate-700">Earlier runs</h3>
          <ul className="mt-1 space-y-1 text-xs text-slate-500">
            {history.slice(1).map((item) => (
              <li key={item.id}>{formatIst(item.analysis_timestamp)} · {item.status}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function ResearchBody({ run }: { run: ResearchRun }) {
  const technical = run.evidence.technical;
  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <p className="text-xs text-slate-500">
        Status {run.status} · As of {formatIst(run.analysis_timestamp)} · {run.scoring_version}
        {run.provider === "unconfigured" ? " · AI explanation unavailable" : ` · ${run.model_name}`}
      </p>
      {run.status === "ai_unavailable" ? (
        <p className="text-slate-700">No model is configured, so this run has no generated narrative.</p>
      ) : null}
      {run.explanation?.summary ? (
        <p><span className="font-medium">Interpretation. </span>{run.explanation.summary}</p>
      ) : null}
      <div>
        <h3 className="font-medium">Fundamentals</h3>
        {run.explanation?.fundamental ? <p className="text-slate-700">Interpretation. {run.explanation.fundamental}</p> : null}
        {(run.evidence.fundamental ?? []).length === 0 ? (
          <p className="text-slate-600">No fundamental comparisons are stored.</p>
        ) : (
          <ul className="list-disc pl-5 text-slate-700">
            {(run.evidence.fundamental ?? []).map((item) => (
              <li key={`${item.metric_name}-${item.as_of ?? "none"}`}>
                {item.metric_name}: {item.state}
                {item.as_of ? ` · ${formatIst(item.as_of)}` : ""}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="font-medium">Technical evidence</h3>
        {technical?.text ? <p className="text-slate-700">Detector output. {technical.text}</p> : <p className="text-slate-600">Technical conclusion unavailable.</p>}
        {technical?.freshness === "stale" ? <p className="text-xs text-amber-800">The technical reading is stale.</p> : null}
      </div>
      <Block title="Patterns" text={run.explanation?.patterns} empty={patternLine(run)} />
      <div>
        <h3 className="font-medium">News</h3>
        {(run.evidence.news ?? []).length === 0 ? <p className="text-slate-600">No linked articles.</p> : null}
        <ul className="space-y-1">
          {(run.evidence.news ?? []).map((article) => (
            <li key={article.url}>
              {article.url && (article.url.startsWith("https://") || article.url.startsWith("http://")) ? (
                <a className="underline" href={article.url} target="_blank" rel="noreferrer noopener">{article.title}</a>
              ) : (
                <span>{article.title}</span>
              )}
              <span className="text-xs text-slate-500"> · {article.source} · {article.sentiment ?? "sentiment unavailable"}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="font-medium">Coverage</h3>
        <p className="text-slate-700">{run.score.note}</p>
        <p className="text-slate-600">Aggregate {run.score.aggregate}. No numeric score is shown.</p>
        <ul className="mt-1 list-disc pl-5 text-slate-700">
          {Object.entries(run.score.categories ?? {}).map(([name, item]) => (
            <li key={name}>
              {name}: {item.status}
              {item.category ? ` (${item.category})` : ""}. {item.reason}
            </li>
          ))}
        </ul>
      </div>
      {(run.evidence.gaps ?? []).length > 0 ? (
        <div>
          <h3 className="font-medium">Data quality</h3>
          <ul className="list-disc pl-5 text-slate-700">
            {run.evidence.gaps?.map((gap) => <li key={gap}>{gap}</li>)}
          </ul>
        </div>
      ) : null}
      {run.explanation?.limitations ? <p className="text-slate-700">Limitations. {run.explanation.limitations}</p> : null}
    </div>
  );
}

function Block({ title, text, empty }: { title: string; text: string | undefined; empty: string }) {
  return (
    <div>
      <h3 className="font-medium">{title}</h3>
      <p className="text-slate-700">{text ? `Interpretation. ${text}` : empty}</p>
    </div>
  );
}

function patternLine(run: ResearchRun): string {
  const patterns = run.evidence.patterns ?? [];
  if (patterns.length === 0) {
    return "No confirmed pattern status is stored.";
  }
  return patterns.map((pattern) => `${pattern.pattern_type ?? "pattern"} is ${pattern.status ?? "unknown"}`).join(". ");
}
