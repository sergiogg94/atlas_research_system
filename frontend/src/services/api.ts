import type {
  ExecuteTaskResponse,
  ExecutionDetailResponse,
  ExecutionListResponse,
  ExecutionMetricsResponse,
  StatsResponse,
} from "../types/api";

export const API_BASE = "http://localhost:8000/api/v1";

export class ApiError extends Error {
  statusCode?: number;
  body?: unknown;

  constructor(
    message: string,
    statusCode?: number,
    body?: unknown,
  ) {
    super(message);
    this.statusCode = statusCode;
    this.body = body;
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorBody: string;
    try {
      errorBody = await response.text();
    } catch {
      errorBody = "Unable to read error response";
    }
    throw new ApiError(
      `HTTP ${response.status}: ${errorBody.slice(0, 200)}`,
      response.status,
      errorBody,
    );
  }
  return response.json();
}

async function fetchWithTimeout(url: string, options: RequestInit, timeoutMs = 30000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

export const api = {
  /** Executes a complite task (Planner → Research → Data → Synthesis) */
  async executeTask(taskDescription: string) {
    const response = await fetchWithTimeout(`${API_BASE}/execute-task`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_description: taskDescription }),
    }, 600000); // 10 minutes for the complete pupeline
    return handleResponse<ExecuteTaskResponse>(response);
  },

  /** List history of executions */
  async listTasks(page = 1, pageSize = 20, status?: string, q?: string) {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) params.set("status", status);
    if (q) params.set("q", q);
    const response = await fetch(`${API_BASE}/tasks?${params}`);
    return handleResponse<ExecutionListResponse>(response);
  },

  /** Get execution details by trace_id */
  async getTaskDetail(traceId: string) {
    const response = await fetch(`${API_BASE}/tasks/${traceId}`);
    return handleResponse<ExecutionDetailResponse>(response);
  },

  /** Obtain metrics from an execution */
  async getTaskMetrics(traceId: string) {
    const response = await fetch(`${API_BASE}/tasks/${traceId}/metrics`);
    return handleResponse<ExecutionMetricsResponse>(response);
  },

  /** Obtain execution stats */
  async getStats() {
    const response = await fetch(`${API_BASE}/stats`)
    return handleResponse<StatsResponse>(response);
  },

  /** Retry a failed execution */
  async retryTask(traceId: string) {
    const response = await fetch(`${API_BASE}/task/${traceId}/retry`);
    return handleResponse<ExecuteTaskResponse>(response);
  }
};
