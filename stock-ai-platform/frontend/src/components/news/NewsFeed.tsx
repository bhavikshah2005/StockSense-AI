import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getNewsFacets, getNewsStatus, listNews } from "../../services/news.ts";
import { ApiError } from "../../services/http.ts";
import type { NewsCard, NewsFacets, NewsStatus } from "../../types/news.ts";
import { formatIst } from "../../utils/quote.ts";

export function NewsFeed({
  stockId,
  compact = false,
}: {
  stockId?: string;
  compact?: boolean;
}) {
  const [status, setStatus] = useState<NewsStatus | null>(null);
  const [facets, setFacets] = useState<NewsFacets | null>(null);
  const [articles, setArticles] = useState<NewsCard[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sector, setSector] = useState("");
  const [source, setSource] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [error, setError] = useState("");
  const limit = compact ? 5 : 20;

  useEffect(() => {
    let cancelled = false;
    if (offset === 0) {
      setArticles(null);
    }
    setError("");
    Promise.all([
      getNewsStatus(),
      compact ? Promise.resolve(null) : getNewsFacets(),
      listNews({ stockId, sector, source, sentiment, limit, offset }),
    ])
      .then(([feed, available, page]) => {
        if (cancelled) {
          return;
        }
        setStatus(feed);
        setFacets(available);
        setArticles((current) => (offset === 0 ? page.results : [...(current ?? []), ...page.results]));
        setTotal(page.total);
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load news");
          setArticles([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [stockId, sector, source, sentiment, limit, offset, compact]);

  return (
    <section className="space-y-3" aria-label={stockId ? "Stock news" : "Market news"}>
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{stockId ? "News" : "Market news"}</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            {status?.message ?? "Headlines are stored from configured feeds. Sentiment is automated and is not a forecast."}
          </p>
        </div>
        {compact ? (
          <Link className="text-sm text-slate-700" to="/news">
            All news
          </Link>
        ) : null}
      </div>
      {status?.last_success_at ? (
        <p className="text-xs text-slate-500">Last ingest {formatIst(status.last_success_at)}</p>
      ) : null}
      {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
      {!compact ? (
        <div className="flex flex-wrap gap-2">
          <Filter label="Sector" value={sector} options={facets?.sectors ?? []} onChange={(value) => { setOffset(0); setSector(value); }} />
          <Filter label="Source" value={source} options={facets?.sources ?? []} onChange={(value) => { setOffset(0); setSource(value); }} />
          <label className="text-sm text-slate-700">
            Sentiment
            <select className="mt-1 block rounded-md border border-slate-300 px-2 py-1" value={sentiment} onChange={(event) => { setOffset(0); setSentiment(event.target.value); }}>
              <option value="">Any</option>
              <option value="positive">Positive</option>
              <option value="negative">Negative</option>
              <option value="neutral">Neutral</option>
              <option value="uncertain">Uncertain</option>
              <option value="unavailable">Unavailable</option>
            </select>
          </label>
        </div>
      ) : null}
      {articles === null && !error ? <p className="text-sm text-slate-600">Loading news…</p> : null}
      {articles !== null && articles.length === 0 && !error ? (
        <p className="text-sm text-slate-600">
          {status && !status.configured ? "No news provider is configured." : "No stored articles match these filters."}
        </p>
      ) : null}
      <ul className="space-y-2">
        {(articles ?? []).map((article) => (
          <li key={article.id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
            <p className="font-medium text-slate-900">{article.title}</p>
            {article.summary ? <p className="mt-1 text-slate-700">{article.summary}</p> : null}
            <p className="mt-1 text-xs text-slate-500">
              {article.source}
              {formatIst(article.published_at) ? ` · Published ${formatIst(article.published_at)}` : ""}
            </p>
            {safeUrl(article.url) ? (
              <a className="text-xs text-slate-700 underline" href={article.url} target="_blank" rel="noreferrer noopener">
                Original article
              </a>
            ) : (
              <p className="text-xs text-slate-500">Original link unavailable</p>
            )}
            <SentimentBadge label={article.sentiment} explanation={article.sentiment_explanation} />
            {article.stocks.length > 0 ? (
              <p className="mt-1 text-xs text-slate-600">
                {article.stocks.map((stock) => (
                  <Link key={stock.stock_id} className="mr-2" to={`/stocks/${stock.stock_id}`}>
                    {stock.symbol} · {stock.exchange}
                  </Link>
                ))}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      {!compact && articles !== null && offset + articles.length < total ? (
        <button type="button" className="text-sm text-slate-700" onClick={() => setOffset(offset + limit)}>
          Load more
        </button>
      ) : null}
    </section>
  );
}

function Filter({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-sm text-slate-700">
      {label}
      <select className="mt-1 block rounded-md border border-slate-300 px-2 py-1" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Any</option>
        {options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    </label>
  );
}

function SentimentBadge({ label, explanation }: { label: string | null; explanation: string | null }) {
  if (!label) {
    return <p className="mt-1 text-xs text-slate-500">Sentiment unavailable</p>;
  }
  return (
    <p className="mt-1 text-xs text-slate-600">
      Automated sentiment: {label}. {explanation ?? "This is not a forecast."}
    </p>
  );
}

function safeUrl(url: string): boolean {
  return url.startsWith("https://") || url.startsWith("http://");
}
