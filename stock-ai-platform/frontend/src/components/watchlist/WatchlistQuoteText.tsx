import type { WatchlistQuote } from "../../types/watchlist.ts";
import { formatInr, formatIst, formatSignedInr, formatSignedPercent } from "../../utils/quote.ts";

export function WatchlistQuoteText({ quote }: { quote: WatchlistQuote }) {
  if (!quote.available || quote.current_price === null || quote.currency !== "INR") {
    return <p className="text-sm text-slate-600">Quote unavailable</p>;
  }
  const price = formatInr(quote.current_price);
  if (price === null) {
    return <p className="text-sm text-slate-600">Quote unavailable</p>;
  }
  const fetched = quote.fetched_at ? formatIst(quote.fetched_at) : null;
  const change = quote.change === null ? null : formatSignedInr(quote.change);
  const percent = quote.change_percent === null ? null : formatSignedPercent(quote.change_percent);
  const direction = quote.change === null ? "flat" : Number(quote.change) > 0 ? "up" : Number(quote.change) < 0 ? "down" : "flat";
  const changeClass = direction === "up" ? "text-emerald-700" : direction === "down" ? "text-red-700" : "text-slate-700";

  return (
    <div>
      <p className="text-sm text-slate-900">
        {price}
        {change || percent ? (
          <span className={`ml-2 ${changeClass}`}>
            {change}
            {percent ? ` (${percent})` : ""}
          </span>
        ) : null}
      </p>
      {fetched ? <p className="text-xs text-slate-500">{fetched}</p> : null}
    </div>
  );
}
