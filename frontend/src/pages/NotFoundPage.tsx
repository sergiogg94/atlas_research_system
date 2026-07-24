import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div style={{ textAlign: "center", padding: "4rem" }}>
      <h1 style={{ fontSize: "4rem", marginBottom: "1rem" }}>404</h1>
      <p style={{ marginBottom: "2rem" }}>Page not found</p>
      <Link to="/" style={{ padding: "0.75rem 2rem", background: "var(--accent)", color: "var(--text-h)", border: "1px solid var(--accent-border)", textDecoration: "none", borderRadius: "4px" }}>
        Go Home
      </Link>
    </div>
  );
}
