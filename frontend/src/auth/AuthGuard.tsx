import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { LoadingState } from "../components/States";
export function AuthGuard() {
  const { user, loading, authorized } = useAuth();
  return loading ? (
    <LoadingState />
  ) : user && authorized ? (
    <Outlet />
  ) : (
    <Navigate to="/login" replace />
  );
}
