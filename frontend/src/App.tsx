import { Routes, Route, Navigate } from "react-router-dom";
import { AuthGuard } from "./auth/AuthGuard";
import { LoginPage } from "./pages/LoginPage";
import { ProfileList } from "./pages/ProfileList";
import { Sambhav, SambhavDetail } from "./pages/Sambhav";
import { ProfileDetail } from "./pages/ProfileDetail";
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage key="login" />} />
      <Route path="/signup" element={<LoginPage key="signup" signup />} />
      <Route element={<AuthGuard />}>
        <Route path="/" element={<ProfileList />} />
        <Route path="/sambhav" element={<Sambhav />} />
        <Route
          path="/sambhav/domains/:domainSlug"
          element={<SambhavDetail />}
        />
        <Route
          path="/sambhav/domains/:domainSlug/ideas/:ideaId"
          element={<SambhavDetail />}
        />
        <Route path="/members" element={<ProfileList members />} />
        <Route path="/members/:id" element={<ProfileDetail members />} />
        <Route path="/profiles/:id" element={<ProfileDetail />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
