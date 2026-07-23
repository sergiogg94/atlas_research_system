import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../services/api";
import type { ExecutionDetail, ExecutionMetrics } from "../types/api";

export function TaskDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [metrics, setMetrics] = useState<ExecutionMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
  }, [traceId]);

  if (isLoading) return <div style={{ textAlign: "center", padding: "3rem" }}>Loading task detail...</div>;
  if (error) return <div style={{ padding: "1rem", background: "var(--accent-bg)", color: "var(--accent)" }}>Error: {error}</div>;
  if (!detail) return <div style={{ padding: "1rem" }}>Task not found.</div>;

  return (
    <div>
      <Link to="/tasks" style={{ marginBottom: "1rem", display: "inline-block" }}>&larr; Back to History</Link>

      <h2>Task Detail</h2>
      <p style={{ color: "var(--text)", marginBottom: "2rem" }}>Trace ID: {detail.trace_id}</p>

      {/* Quiqk metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
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

      {/* Status and description */}
      <div style={{ marginBottom: "2rem" }}>
        <strong>Status: </strong>
        <span style={{
          padding: "0.25rem 0.5rem",
          borderRadius: "4px",
          background: detail.status === "completed" ? "#dfd" : detail.status === "failed" ? "#fdd" : "#ffd",
        }}>
          {detail.status}
        </span>
      </div>

      <div style={{ marginBottom: "2rem" }}>
        <strong>Task Description:</strong>
        <p style={{ marginTop: "0.5rem", background: "var(--accent-bg)", padding: "1rem", borderRadius: "4px" }}>
          {detail.task_description}
        </p>
      </div>

      {/* Execution steps */}
      <h3>Execution Steps</h3>
      {detail.steps.length === 0 ? (
        <p style={{ color: "var(--text)" }}>No steps recorded.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "1rem" }}>
          {detail.steps.map((step) => (
            <div key={step.id} style={{
              padding: "1rem",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              background: step.status === "completed" ? "#dfd" : step.status === "failed" ? "#fdd" : "#ffd",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                <strong>{step.agent_name}</strong>
                <span style={{ fontSize: "0.875rem", color: "var(--text)" }}>
                  {step.latency_ms ? `${step.latency_ms}ms` : "-"} | {step.step_type || "-"}
                </span>
              </div>
              {step.error && (
                <div style={{ color: "#c00", fontSize: "0.875rem", marginTop: "0.25rem" }}>
                  Error: {step.error}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Final report */}
      {detail.report && (
        <div style={{ marginTop: "2rem" }}>
          <h3>Generated Report</h3>
          <div style={{
            marginTop: "0.5rem",
            padding: "1rem",
            background: "var(--accent-bg)",
            borderRadius: "4px",
            whiteSpace: "pre-wrap",
            fontFamily: "monospace",
            fontSize: "0.875rem",
          }}>
            {detail.report}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: "1rem", background: "var(--accent-bg)", borderRadius: "4px", textAlign: "center" }}>
      <div style={{ fontSize: "0.75rem", color: "var(--text)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: "1.5rem", fontWeight: 700, marginTop: "0.25rem" }}>{value}</div>
    </div>
  );
}
