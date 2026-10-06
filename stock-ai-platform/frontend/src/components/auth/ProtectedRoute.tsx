import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../../context/AuthContext.tsx";

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="p-8 text-sm text-slate-600">Checking session…</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
