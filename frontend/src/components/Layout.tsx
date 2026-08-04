import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="layout-wrapper">
      <header className="layout-header">
        <nav className="layout-nav">
          <h1 className="layout-title">Atlas Research System</h1>
          <Link to="/" className="layout-nav-link">Home</Link>
          <Link to="/tasks" className="layout-nav-link">History</Link>
          <Link to="/dashboard" className='layout-nav-link'>Dashboard</Link>
        </nav>
      </header>
      <main className="layout-main">
        {children}
      </main>
      <footer className="layout-footer">
        Atlas Research System v0.1.0
      </footer>
    </div>
  );
}
