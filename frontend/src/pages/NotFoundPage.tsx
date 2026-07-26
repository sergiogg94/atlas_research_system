import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="not-found-container">
      <h1 className="not-found-title">404</h1>
      <p className="mb-2">Page not found</p>
      <Link to="/" className="btn-link">
        Go Home
      </Link>
    </div>
  );
}
