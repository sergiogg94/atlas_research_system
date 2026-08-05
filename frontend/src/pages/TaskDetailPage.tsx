import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api, API_BASE } from "../services/api";
import { useEventSource } from "../hooks/useEventSource";
import { useTaskDetail, useTaskMetrics } from "../hooks/useTasks";
import type { ExecutionDetail, ExecutionMetrics, Plan, StepDetail } from "../types/api";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";
import { PlanTimeLine, type PlanStep as TimelineStep } from "../components/PlanTimeLine";
import { useToast } from "../components/ToastProvider";

export function TaskDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const navigate = useNavigate();
  const [liveDetail, setLiveDetail] = useState<ExecutionDetail | null>(null);
  const [liveMetrics, setLiveMetrics] = useState<ExecutionMetrics | null>(null);
  const [sseError, setSseError] = useState<string | null>(null);
  const { addToast } = useToast();

  const { data: detailData, isLoading, error: queryError, refetch } = useTaskDetail(traceId);
  const { data: metricsData } = useTaskMetrics(traceId);

  const detail = liveDetail ?? detailData?.execution ?? null;
  const metrics = liveMetrics ?? metricsData?.metrics ?? null;

  const isActive = detail?.status === "running" || detail?.status === "pending";
  const sseUrl = traceId && isActive ? `${API_BASE}/tasks/${traceId}/stream` : null;

  useEventSource(sseUrl, {
    onProgress: (data) => {
      const { status, steps, plan } = data as { status: string; steps: StepDetail[]; plan?: Plan | null };
      setLiveDetail(prev => mergeSteps(prev, status, steps, undefined, plan));
    },
    onComplete: (data) => {
      const { status, steps, metrics, report, plan } = data as {
        status: string; steps: StepDetail[]; metrics?: Partial<ExecutionMetrics>; report?: string; plan?: Plan | null;
      };
      setLiveDetail(prev => mergeSteps(prev, status, steps, report, plan));
      if (metrics) {
        setLiveMetrics(prev => (prev ? { ...prev, ...metrics } : { ...metrics } as ExecutionMetrics));
        if (metrics.error_count && metrics.error_count > 0) {
          addToast(`Task completed with ${metrics.error_count} error(s)`, "error");
        } else {
          addToast("Task completed successfully", "success");
        }
      } else {
        addToast("Task completed successfully", "success");
      }
    },
    onError: (message) => {
      setSseError(message);
      addToast(message, "error");
    },
  });

  if (isLoading) return <LoadingSpinner message="Loading task detail..." />;
  if (sseError) return <ErrorMessage message={sseError} onRetry={() => { setSseError(null); refetch(); }} />;
  if (queryError) return <ErrorMessage message={queryError.message} onRetry={refetch} />;
  if (!detail) return <div style={{ padding: "1rem" }}>Task not found.</div>;

  const retryMutation = useMutation({
    mutationFn: () => api.retryTask(traceId!),
    onSuccess: (data) => {
      addToast("Task re-execution started", "success");
      navigate(`/tasks/${data.task_id}`);
    },
    onError: (err) => {
      addToast(err instanceof Error ? err.message : "Retry failed", "error");
    },
  });

  return (
    <div>
      <Link to="/tasks" className="mb-1 inline-block">&larr; Back to History</Link>

      <h2>Task Detail</h2>
      <p className="text-muted mb-2">Trace ID: {detail.trace_id}</p>

      {/* <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button onClick={() => addToast("Operación exitosa", "success")}>Toast Success</button>
        <button onClick={() => addToast("Algo salió mal", "error")}>Toast Error</button>
        <button onClick={() => addToast("Información útil", "info")}>Toast Info</button>
      </div> */}

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

      {detail.status == "failed" && (
        <button
          onClick={() => retryMutation.mutate()}
          disabled={retryMutation.isPending}
          className="btn"
          style={{ marginLeft: "1rem" }}
        >
          {retryMutation.isPending ? "Retrying..." : "Retry Task"}
        </button>
      )}

      <div className="detail-section">
        <strong>Task Description:</strong>
        <p className="detail-description">
          {detail.task_description}
        </p>
      </div>

      {detail.plan && (
        <div className="detail-section">
          <PlanTimeLine
            objective={detail.plan.objective}
            steps={toTimelineSteps(detail)}
          />
        </div>
      )}

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

function mergeSteps(
  prev: ExecutionDetail | null,
  status: string,
  newSteps: StepDetail[],
  report?: string,
  plan?: Plan | null,
): ExecutionDetail | null {
  if (!prev) return prev;
  const stepsMap = new Map(prev.steps.map(s => [s.id, s]));
  for (const s of newSteps) {
    stepsMap.set(s.id, { ...stepsMap.get(s.id), ...s } as StepDetail);
  }
  return {
    ...prev,
    status,
    steps: [...stepsMap.values()],
    ...(report !== undefined ? { report } : {}),
    ...(plan !== undefined ? { plan } : {}),
  };
}

const EXEC_TO_PLAN_STEP_TYPE: Record<string, string> = {
  planning: "scoping",
  research: "research",
  data_analysis: "analysis",
  synthesis: "synthesis",
};

function toTimelineSteps(detail: ExecutionDetail): TimelineStep[] {
  if (!detail.plan) return [];
  const planSteps = [...detail.plan.steps].sort((a, b) => a.step - b.step);

  if (detail.status === "completed") {
    return planSteps.map(s => ({ type: s.step_type, description: s.action, status: "completed" as const }));
  }

  // Cada agente registra una fila "running" y luego una fila con estado final
  // (completed/failed) sin actualizar la primera; los steps llegan ordenados
  // por created_at, así que el último registro por step_type es la verdad.
  const lastStatusByPlanType = new Map<string, TimelineStep["status"]>();
  for (const step of detail.steps) {
    const planType = step.step_type ? EXEC_TO_PLAN_STEP_TYPE[step.step_type] : undefined;
    if (!planType) continue;
    if (step.status === "running" || step.status === "completed" || step.status === "failed") {
      lastStatusByPlanType.set(planType, step.status);
    }
  }

  return planSteps.map(s => ({
    type: s.step_type,
    description: s.action,
    status: lastStatusByPlanType.get(s.step_type) ?? "pending",
  }));
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="metric-card-label">{label}</div>
      <div className="metric-card-value">{value}</div>
    </div>
  );
}
