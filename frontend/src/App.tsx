import { Routes, Route } from "react-router-dom";
import { Login } from "./pages/Login";

// Minimal placeholder app shell. YOU will build the real routes/pages:
//   /login, /clients, /clients/:id, /meetings/:id, /search
export function App() {
  return (
    <Routes>
      <Route path="/" element={<Placeholder />} />
      <Route path="/login" element={<Login />} />
    </Routes>
  );
}

function Placeholder() {
  return <h1>ClientLens — frontend scaffold ready</h1>;
}
