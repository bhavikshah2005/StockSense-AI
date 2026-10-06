import { NewsFeed } from "../news/NewsFeed.tsx";
import { useAuth } from "../../context/AuthContext.tsx";
import { WatchlistSummary } from "./WatchlistSummary.tsx";

export function DashboardHome() {
  const { user } = useAuth();
  const name = user?.full_name?.trim() || "there";

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome, {name}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          Search covers NSE and BSE listings. Open a stock to see its quote when market data is available.
        </p>
      </header>
      <WatchlistSummary />
      <NewsFeed compact />
    </div>
  );
}
