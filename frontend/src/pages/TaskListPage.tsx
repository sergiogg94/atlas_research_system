import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { ExecutionSummary } from "../types/api";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";

export function TaskListPage() {
  const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setIsLoading(true);
        const response = await api.listTasks(page);
        if (!cancelled) {
          setExecutions(response.executions);
          setTotal(response.total);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load tasks");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    load();
    return () => { cancelled = true; }; // Avoid calling setState if the component has unmounted
  }, [page]);

  const totalPages = Math.ceil(total / 20);

  if (isLoading) return <LoadingSpinner message="Loading tasks..." />;
  if (error) return <ErrorMessage message={error} onRetry={() => { setError(null); setPage(1); }} />;

  return (
    <div>
      <h2>Execution History</h2>
      <p className="text-muted">{total} total executions</p>

      {executions.length === 0 ? (
        <p className="mt-2 text-muted">No executions yet. Create one from the home page.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Status</th>
              <th>Steps</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {executions.map((exec) => (
              <tr key={exec.id}>
                <td>{exec.task_description.slice(0, 80)}...</td>
                <td>
                  <StatusBadge status={exec.status} />
                </td>
                <td>{exec.total_steps}</td>
                <td>{exec.created_at ? new Date(exec.created_at).toLocaleString() : "-"}</td>
                <td>
                  <Link to={`/tasks/${exec.trace_id}`}>View Details</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {totalPages > 1 && (
        <div className="pagination">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="btn btn-sm"
          >
            Previous
          </button>
          <span className="pagination-info">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="btn btn-sm"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
