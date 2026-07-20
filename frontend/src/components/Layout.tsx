import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={{ background: "#1a1a2e", color: "white", padding: "1rem 2rem" }}>
        <nav style={{ display: "flex", gap: "2rem", alignItems: "center" }}>
          <h1 style={{ fontSize: "1.25rem", margin: 0 }}>Atlas Research System</h1>
          <Link to="/" style={{ color: "white", textDecoration: "none" }}>Home</Link>
          <Link to="/tasks" style={{ color: "white", textDecoration: "none" }}>History</Link>
        </nav>
      </header>
      <main style={{ flex: 1, padding: "2rem", maxWidth: "1200px", margin: "0 auto", width: "100%" }}>
        {children}
      </main>
      <footer style={{ textAlign: "center", padding: "1rem", color: "#666", fontSize: "0.875rem" }}>
        Atlas Research System v0.1.0
      </footer>
    </div>
  );
}
