import { NavLink, useNavigate } from "react-router-dom";
import { clearToken } from "@/auth/token";

/**
 * Authenticated app shell: top nav (brand + links + logout) and a centered
 * container for page content. Wrap authed pages with this.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();

  function handleLogout() {
    clearToken();
    navigate("/login");
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    "app-nav__link" + (isActive ? " app-nav__link--active" : "");

  return (
    <>
      <nav className="app-nav">
        <div className="app-nav__inner">
          <span className="app-nav__brand">ClientLens</span>
          <NavLink to="/clients" className={linkClass}>Clients</NavLink>
          <NavLink to="/search" className={linkClass}>Search</NavLink>
          <span className="app-nav__spacer" />
          <button onClick={handleLogout}>Log out</button>
        </div>
      </nav>
      <main className="container">{children}</main>
    </>
  );
}
