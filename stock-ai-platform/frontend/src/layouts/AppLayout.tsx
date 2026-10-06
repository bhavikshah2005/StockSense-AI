import { Bell, Briefcase, LayoutDashboard, LineChart, Newspaper, Search, Settings, SlidersHorizontal, Star } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { useEffect, useState } from "react";

import { NotificationPopup } from "../components/alerts/NotificationPopup.tsx";
import { useAuth } from "../context/AuthContext.tsx";
import { listNotifications, markNotificationRead } from "../services/alerts.ts";
import type { NotificationRecord } from "../types/alerts.ts";

const NAV_ITEMS = [
  { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
  { label: "Stocks", to: "/stocks", icon: Search },
  { label: "Watchlist", to: "/watchlist", icon: Star },
  { label: "Thresholds", to: "/thresholds", icon: SlidersHorizontal },
  { label: "News", to: "/news", icon: Newspaper },
  { label: "Alerts", to: "/alerts", icon: Bell },
  { label: "Portfolio", to: "/portfolio", icon: Briefcase },
  { label: "Backtests", to: "/backtests", icon: LineChart },
  { label: "Settings", to: "/settings", icon: Settings },
] as const;

export function AppLayout() {
  const { user, logout } = useAuth();
  const [unread, setUnread] = useState(0);
  const [popup, setPopup] = useState<NotificationRecord | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const page = await listNotifications();
        if (cancelled) {
          return;
        }
        setUnread(page.unread);
        setPopup(page.results.find((item) => item.read_at === null) ?? null);
      } catch {
        if (!cancelled) {
          setUnread(0);
        }
      }
    }

    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  function dismissPopup() {
    if (!popup) {
      return;
    }
    const current = popup;
    setPopup(null);
    setUnread((count) => Math.max(0, count - 1));
    void markNotificationRead(current.id).catch(() => {
      setPopup(current);
    });
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col md:flex-row">
        <aside className="border-b border-slate-200 bg-slate-950 text-slate-100 md:flex md:w-60 md:flex-col md:border-b-0 md:border-r">
          <div className="px-5 py-5">
            <p className="text-xs font-medium tracking-wide text-emerald-300 uppercase">StockSense AI</p>
            <p className="mt-1 text-sm text-slate-400">{user?.full_name || user?.email}</p>
          </div>
          <nav className="flex gap-2 overflow-x-auto px-3 pb-4 md:flex-col md:px-3">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-left text-sm ${
                      isActive ? "bg-slate-800 text-white" : "text-slate-300"
                    }`
                  }
                >
                  <Icon aria-hidden="true" size={16} />
                  {item.label}
                  {item.to === "/alerts" && unread > 0 ? <span className="rounded bg-emerald-400 px-1.5 text-xs text-slate-950">{unread}</span> : null}
                </NavLink>
              );
            })}
          </nav>
          <p className="px-5 pb-3 text-xs leading-5 text-slate-400 md:mt-auto">
            For education and research. Data can be delayed or incomplete. This is not a forecast or a personal recommendation.
          </p>
          <div className="px-3 pb-4">
            <button
              type="button"
              onClick={() => {
                void logout();
              }}
              className="rounded-md px-3 py-2 text-sm text-slate-300"
            >
              Log out
            </button>
          </div>
        </aside>
        <main className="flex-1 px-5 py-8 md:px-8">
          <Outlet />
        </main>
      </div>
      {popup ? <NotificationPopup note={popup} onDismiss={dismissPopup} /> : null}
    </div>
  );
}
