import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./components/auth/ProtectedRoute.tsx";
import { AuthProvider } from "./context/AuthContext.tsx";
import { AppLayout } from "./layouts/AppLayout.tsx";
import { AlertDetailPage } from "./pages/AlertDetailPage.tsx";
import { BacktestDetailPage } from "./pages/BacktestDetailPage.tsx";
import { BacktestsPage } from "./pages/BacktestsPage.tsx";
import { AlertsPage } from "./pages/AlertsPage.tsx";
import { PortfolioDetailPage } from "./pages/PortfolioDetailPage.tsx";
import { PortfoliosPage } from "./pages/PortfoliosPage.tsx";
import { PositionSizePage } from "./pages/PositionSizePage.tsx";
import { DashboardPage } from "./pages/DashboardPage.tsx";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage.tsx";
import { LoginPage } from "./pages/LoginPage.tsx";
import { NewsPage } from "./pages/NewsPage.tsx";
import { RegisterPage } from "./pages/RegisterPage.tsx";
import { ResetPasswordPage } from "./pages/ResetPasswordPage.tsx";
import { SettingsPage } from "./pages/SettingsPage.tsx";
import { StockDetailPage } from "./pages/StockDetailPage.tsx";
import { StockSearchPage } from "./pages/StockSearchPage.tsx";
import { ThresholdsPage } from "./pages/ThresholdsPage.tsx";
import { WatchlistDetailPage } from "./pages/WatchlistDetailPage.tsx";
import { WatchlistsPage } from "./pages/WatchlistsPage.tsx";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/stocks" element={<StockSearchPage />} />
              <Route path="/stocks/:stockId" element={<StockDetailPage />} />
              <Route path="/watchlist" element={<WatchlistsPage />} />
              <Route path="/watchlist/:watchlistId" element={<WatchlistDetailPage />} />
              <Route path="/thresholds" element={<ThresholdsPage />} />
              <Route path="/news" element={<NewsPage />} />
              <Route path="/backtests" element={<BacktestsPage />} />
              <Route path="/backtests/:runId" element={<BacktestDetailPage />} />
              <Route path="/portfolio" element={<PortfoliosPage />} />
              <Route path="/portfolio/planning" element={<PositionSizePage />} />
              <Route path="/portfolio/:portfolioId" element={<PortfolioDetailPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Route>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
