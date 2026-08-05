import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { ExecutionStats } from "../types/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorMessage } from "../components/ErrorMessage";
import { StatusBadge } from "../components/StatusBadge";

export default function DashboardPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["stats"],
    queryFn: () => api.getStats() as Promise<{ stats: ExecutionStats }>,
  });

  if (isLoading) return <LoadingSpinner message="Loading dashboard..." />;
  if (error) return <ErrorMessage message={String(error)} onRetry={refetch} />;

  const stats = data?.stats;

  return (
    <div>
      <h2>Dashboard</h2>

      <div className="metric-grid">
        <MetricCard label="Total Tasks" value={String(stats?.total ?? "-")} />
        <MetricCard label="Completed" value={String(stats?.completed ?? "-")} />
        <MetricCard label="Failed" value={String(stats?.failed ?? "-")} />
        <MetricCard label="Success Rate" value={stats?.success_rate != null ? `${stats.success_rate}%` : "-"} />
        <MetricCard label="Avg Duration" value={stats?.avg_duration_ms ? `${(stats.avg_duration_ms / 1000).toFixed(1)}s` : "-"} />
        <MetricCard label="Timeouts" value={String(stats?.timeout ?? "-")} />
      </div>

      <h3 style={{ marginTop: "2rem" }}>Recent Executions</h3>
      {stats?.recent_executions && stats.recent_executions.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {stats.recent_executions.map((exec) => (
              <tr key={exec.trace_id}>
                <td>{exec.task_description}</td>
                <td><StatusBadge status={exec.status} /></td>
                <td>{exec.created_at ? new Date(exec.created_at).toLocaleString() : "-"}</td>
                <td>
                  <Link to={`/tasks/${exec.trace_id}`}>View</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-muted">No executions yet.</p>
      )}
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="metric-card-label">{label}</div>
      <div className="metric-card-value">{value}</div>
    </div>
  );
}
