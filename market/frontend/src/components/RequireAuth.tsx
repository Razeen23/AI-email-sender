import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

export default function RequireAuth() {
  const { user, ready } = useAuth();
  if (!ready) return <p className="text-sm text-slate-500">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
