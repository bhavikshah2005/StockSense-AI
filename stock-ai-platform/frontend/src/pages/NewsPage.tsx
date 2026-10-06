import { NewsFeed } from "../components/news/NewsFeed.tsx";

export function NewsPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">News</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Indian market headlines from configured feeds. Open the original publisher for the full story. Sentiment does not predict a price move.
        </p>
      </header>
      <NewsFeed />
    </div>
  );
}
