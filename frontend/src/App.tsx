import { Routes, Route, Navigate } from "react-router-dom";
import { Login } from "./pages/Login";
import { getToken } from "./auth/token";
import { ClientsPage } from "./pages/ClientsPage";
import { ClientDetail } from "./pages/ClientDetail";
import { SearchPage } from "./pages/SearchPage";

// A wrapper component: render children only if logged in, else redirect to /login.
function RequireAuth({ children }: { children: React.ReactNode }) {
  return getToken() ? <>{children}</> : <Navigate to="/login" replace />;
}


// Minimal placeholder app shell. YOU will build the real routes/pages:
//   /login, /clients, /clients/:id, /meetings/:id, /search
export function App() {
  return (
    <Routes>
      <Route path="/" element={<Placeholder />} />
      <Route path="/login" element={<Login />} />
      <Route
        path="/clients"
        element={
          <RequireAuth>
            <ClientsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/search"
        element={
          <RequireAuth>
            <SearchPage />
          </RequireAuth>
        }
      />
      <Route path="/clients/:id" element={<RequireAuth><ClientDetail /></RequireAuth>} />
    </Routes>
  );
}

function Placeholder() {
  return <h1>ClientLens — frontend scaffold ready</h1>;
}
