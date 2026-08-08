import { useCallback, useMemo, useState } from "react";
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

export default function TaskDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const navigate = useNavigate();
  const [liveDetail, setLiveDetail] = useState<ExecutionDetail | null>(null);
  const [liveMetrics, setLiveMetrics] = useState<ExecutionMetrics | null>(null);
  const [sseError, setSseError] = useState<string | null>(null);
  const { addToast } = useToast();

  const { data: detailData, isLoading, error: queryError, refetch } = useTaskDetail(traceId);
  const { data: metricsData } = useTaskMetrics(traceId);

  const detail = useMemo(() => detailData?.execution ?? null, [detailData]);
  const activeDetail = useMemo(() => liveDetail ?? detail, [liveDetail, detail]);
  const metrics = liveMetrics ?? metricsData?.metrics ?? null;

  const isActive = activeDetail?.status === "running" || activeDetail?.status === "pending";
  const sseUrl = traceId && isActive ? `${API_BASE}/tasks/${traceId}/stream` : null;

  const handleProgress = useCallback((data: unknown) => {
    const { status, steps, plan } = data as { status: string; steps: StepDetail[]; plan?: Plan | null };
    setLiveDetail(prev => mergeSteps(prev, status, steps, undefined, plan));
  }, []);

  const handleComplete = useCallback((data: unknown) => {
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
  }, [addToast]);

  const handleError = useCallback((message: string) => {
    setSseError(message);
    addToast(message, "error");
  }, [addToast]);

  useEventSource(sseUrl, {
    onProgress: handleProgress,
    onComplete: handleComplete,
    onError: handleError,
  });

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

  const planSteps = useMemo<TimelineStep[]>(() => {
    if (!detail?.plan?.steps) return [];
    return detail.plan.steps.map((step, i) => {
      const execStep = activeDetail?.steps?.[i];
      const status = execStep?.status === "completed" ? "completed"
        : execStep?.status === "failed" ? "failed"
        : execStep?.status === "running" ? "running"
        : "pending";
      return {
        type: step.step_type || "research",
        description: step.action || "",
        status,
      } as TimelineStep;
    });
  }, [detail?.plan, activeDetail?.steps]);

  if (isLoading) return <LoadingSpinner message="Loading task detail..." />;
  if (sseError) return <ErrorMessage message={sseError} onRetry={() => { setSseError(null); refetch(); }} />;
  if (queryError) return <ErrorMessage message={queryError.message} onRetry={refetch} />;
  if (!activeDetail) return <div style={{ padding: "1rem" }}>Task not found.</div>;

  return (
    <div>
      <Link to="/tasks" className="mb-1 inline-block">&larr; Back to History</Link>

      <h2>Task Detail</h2>
      <p className="text-muted mb-2">Trace ID: {activeDetail.trace_id}</p>

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
        <StatusBadge status={activeDetail.status} />
      </div>

      {activeDetail.status == "failed" && (
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
          {activeDetail.task_description}
        </p>
      </div>

      {activeDetail.plan && (
        <div className="detail-section">
          <PlanTimeLine
            objective={activeDetail.plan.objective}
            steps={planSteps}
          />
        </div>
      )}

      <h3>Execution Steps</h3>
      {activeDetail.steps.length === 0 ? (
        <p className="text-muted">No steps recorded.</p>
      ) : (
        <div className="steps-list">
          {activeDetail.steps.map((step) => {
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

      {activeDetail.report && (
        <div className="mt-2">
          <h3>Generated Report</h3>
          <div className="report-box">
            {activeDetail.report}
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

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="metric-card-label">{label}</div>
      <div className="metric-card-value">{value}</div>
    </div>
  );
}
