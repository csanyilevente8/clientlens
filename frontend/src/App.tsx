import { Routes, Route, Navigate } from "react-router-dom";
import { Login } from "./pages/Login";
import { getToken } from "./auth/token";
import { ClientsPage } from "./pages/ClientsPage";
import { ClientDetail } from "./pages/ClientDetail";
import { SearchPage } from "./pages/SearchPage";
import { AppShell } from "./components/AppShell";

// Render children only if logged in (inside the app shell), else redirect to /login.
function RequireAuth({ children }: { children: React.ReactNode }) {
  return getToken() ? <AppShell>{children}</AppShell> : <Navigate to="/login" replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/clients" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/clients" element={<RequireAuth><ClientsPage /></RequireAuth>} />
      <Route path="/clients/:id" element={<RequireAuth><ClientDetail /></RequireAuth>} />
      <Route path="/search" element={<RequireAuth><SearchPage /></RequireAuth>} />
    </Routes>
  );
}
