import { Link, NavLink } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { Logo } from "./Logo";
export function Header() {
  const auth = useAuth();
  const [error, setError] = useState("");
  return (
    <>
      <header>
        <Link to="/" className="brand">
          <Logo />
        </Link>
        <nav className="section-nav" aria-label="Main navigation">
          <NavLink to="/" end>
            Idea Incubation
          </NavLink>
          <NavLink to="/members">Members</NavLink>
          <NavLink to="/sambhav">Sambhav</NavLink>
        </nav>
        <div className="account">
          <span>{auth.user}</span>
          <button
            onClick={() =>
              auth
                .logout()
                .catch(() => setError("Unable to logout. Please try again."))
            }
          >
            Logout
          </button>
        </div>
      </header>
      {error && <p role="alert">{error}</p>}
    </>
  );
}
