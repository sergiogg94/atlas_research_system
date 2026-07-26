import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../services/api";
import type { ExecutionDetail, ExecutionMetrics } from "../types/api";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";

export function TaskDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [metrics, setMetrics] = useState<ExecutionMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!traceId) return;

    const resolvedTraceId = traceId;
    let cancelled = false;

    async function load() {
      type TaskDetailResponse = { execution: ExecutionDetail };
      type TaskMetricsResponse = { metrics: ExecutionMetrics };

      try {
        setIsLoading(true);
        const [detailResp, metricsResp] = await Promise.all([
          api.getTaskDetail(resolvedTraceId) as Promise<TaskDetailResponse>,
          api.getTaskMetrics(resolvedTraceId) as Promise<TaskMetricsResponse>,
        ]);
        if (!cancelled) {
          setDetail(detailResp.execution);
          setMetrics(metricsResp.metrics);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load task detail");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [traceId, retryCount]);

  useEffect(() => {
    if (!traceId) return;

    const isActive = detail?.status === "running" || detail?.status === "pending";
    if (!isActive) return;

    const interval = setInterval(async () => {
      try {
        const response = await (api.getTaskDetail(traceId) as Promise<{ execution: ExecutionDetail }>);
        setDetail(response.execution);
      } catch {
        // Silently retry on next interval
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [traceId, detail?.status]);

  if (isLoading) return <LoadingSpinner message="Loading task detail..." />;
  if (error) return <ErrorMessage message={error} onRetry={() => { setError(null); setRetryCount(c => c + 1); }} />;
  if (!detail) return <div style={{ padding: "1rem" }}>Task not found.</div>;

  return (
    <div>
      <Link to="/tasks" className="mb-1 inline-block">&larr; Back to History</Link>

      <h2>Task Detail</h2>
      <p className="text-muted mb-2">Trace ID: {detail.trace_id}</p>

      <div className="metric-grid">
        {metrics && (
          <>
            <MetricCard label="Duration" value={metrics.total_duration_ms ? `${(metrics.total_duration_ms / 1000).toFixed(1)}s` : "-"} />
            <MetricCard label="LLM Calls" value={String(metrics.total_llm_calls)} />
            <MetricCard label="Tool Calls" value={String(metrics.total_tool_calls)} />
            <MetricCard label="Total Tokens" value={String(metrics.total_tokens_input + metrics.total_tokens_output)} />
            <MetricCard label="Est. Cost" value={`$${metrics.estimated_cost_usd.toFixed(6)}`} />
            <MetricCard label="Errors" value={String(metrics.error_count)} />
          </>
        )}
      </div>

      <div className="detail-section">
        <strong>Status: </strong>
        <StatusBadge status={detail.status} />
      </div>

      <div className="detail-section">
        <strong>Task Description:</strong>
        <p className="detail-description">
          {detail.task_description}
        </p>
      </div>

      <h3>Execution Steps</h3>
      {detail.steps.length === 0 ? (
        <p className="text-muted">No steps recorded.</p>
      ) : (
        <div className="steps-list">
          {detail.steps.map((step) => {
            const statusClass = step.status === "completed" ? "step-card--completed" : step.status === "failed" ? "step-card--failed" : "step-card--default";
            return (
              <div key={step.id} className={`step-card ${statusClass}`}>
                <div className="step-card-header">
                  <strong>{step.agent_name}</strong>
                  <span className="step-card-meta">
                    {step.latency_ms ? `${step.latency_ms}ms` : "-"} | {step.step_type || "-"}
                  </span>
                </div>
                {step.error && (
                  <div className="step-card-error">
                    Error: {step.error}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {detail.report && (
        <div className="mt-2">
          <h3>Generated Report</h3>
          <div className="report-box">
            {detail.report}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="metric-card-label">{label}</div>
      <div className="metric-card-value">{value}</div>
    </div>
  );
}
