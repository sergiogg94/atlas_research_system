import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { ExecutionSummary } from "../types/api";

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

  if (isLoading) return <div style={{ textAlign: "center", padding: "3rem" }}>Loading tasks...</div>;
  if (error) return (
    <div
      style={{
        padding: "1rem",
        background: "var(--accent-bg)",
        color: "var(--accent)",
        border: "1px solid var(--accent-border)",
        borderRadius: "0.5rem",
      }}
    >
      Error: {error}
    </div>
  );

  return (
    <div>
      <h2>Execution History</h2>
      <p style={{ color: "var(--text)" }}>{total} total executions</p>

      {executions.length === 0 ? (
        <p style={{ marginTop: "2rem", color: "var(--text)" }}>No executions yet. Create one from the home page.</p>
      ) : (
        <table style={{ width: "100%", marginTop: "1rem", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "2px solid var(--border)" }}>
              <th style={{ padding: "0.75rem" }}>Task</th>
              <th style={{ padding: "0.75rem" }}>Status</th>
              <th style={{ padding: "0.75rem" }}>Steps</th>
              <th style={{ padding: "0.75rem" }}>Created</th>
              <th style={{ padding: "0.75rem" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {executions.map((exec) => (
              <tr key={exec.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "0.75rem" }}>{exec.task_description.slice(0, 80)}...</td>
                <td style={{ padding: "0.75rem" }}>
                  <span style={{
                    padding: "0.25rem 0.5rem",
                    borderRadius: "4px",
                    fontSize: "0.875rem",
                    background: exec.status === "completed" ? "#dfd" : exec.status === "failed" ? "#fdd" : "#ffd",
                    color: exec.status === "completed" ? "#090" : exec.status === "failed" ? "#c00" : "#960",
                  }}>
                    {exec.status}
                  </span>
                </td>
                <td style={{ padding: "0.75rem" }}>{exec.total_steps}</td>
                <td style={{ padding: "0.75rem" }}>{exec.created_at ? new Date(exec.created_at).toLocaleString() : "-"}</td>
                <td style={{ padding: "0.75rem" }}>
                  <Link to={`/tasks/${exec.trace_id}`}>View Details</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Paginación simple */}
      {totalPages > 1 && (
        <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", justifyContent: "center" }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            style={{
              padding: "0.5rem 1rem",
              background: page <= 1 ? "var(--border)" : "var(--accent)",
              color: "var(--text-h)",
              border: "1px solid var(--accent-border)",
              borderRadius: "0.5rem",
              cursor: page <= 1 ? "not-allowed" : "pointer",
            }}
          >
            Previous
          </button>
          <span style={{ padding: "0.5rem", color: "var(--text)" }}>Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            style={{
              padding: "0.5rem 1rem",
              background: page >= totalPages ? "var(--border)" : "var(--accent)",
              color: "var(--text-h)",
              border: "1px solid var(--accent-border)",
              borderRadius: "0.5rem",
              cursor: page >= totalPages ? "not-allowed" : "pointer",
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
