import { useState } from "react";
import { Link } from "react-router-dom";
import { useTasks } from "../hooks/useTasks";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";

export function TaskListPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useTasks(page);

  const executions = data?.executions ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  if (isLoading) return <LoadingSpinner message="Loading tasks..." />;
  if (error) return <ErrorMessage message={error.message} onRetry={refetch} />;

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
