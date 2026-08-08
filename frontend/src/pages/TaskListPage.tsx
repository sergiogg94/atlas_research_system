import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorMessage } from "../components/ErrorMessage";
import { StatusBadge } from "../components/StatusBadge";

export default function TaskListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10));
  const statusFilter = searchParams.get("status") || "";
  const searchQuery = searchParams.get("q") || "";

  const [searchInput, setSearchInput] = useState(searchQuery);

  useEffect(() => {
    setSearchInput(searchQuery);
  }, [searchQuery]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (searchInput) next.set("q", searchInput);
        else next.delete("q");
        next.set("page", "1");
        return next;
      });
    }, 400);

    return () => window.clearTimeout(timer);
  }, [searchInput, setSearchParams]);

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["tasks", page, statusFilter, searchQuery],
    queryFn: () => api.listTasks(page, 20, statusFilter, searchQuery),
    placeholderData: keepPreviousData,
  });

  const executions = data?.executions ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  const setPage = (nextPage: number) => {
    const safePage = Math.max(1, nextPage);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("page", String(safePage));
      return next;
    });
  };

  if (isLoading && !data) return <LoadingSpinner message="Loading tasks..." />;

  return (
    <div>
      <h2>Execution History</h2>
      <p className="text-muted">{total} total executions</p>

      <input
        type="text"
        value={searchInput}
        onChange={(event) => setSearchInput(event.target.value)}
        placeholder="Search tasks..."
        className="form-control mb-3"
      />

      {isFetching && <p className="text-muted mt-1">Searching...</p>}

      {error ? (
        <ErrorMessage message={error.message} onRetry={refetch} />
      ) : executions.length === 0 ? (
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
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            className="btn btn-sm"
          >
            Previous
          </button>
          <span className="pagination-info">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage(page + 1)}
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
