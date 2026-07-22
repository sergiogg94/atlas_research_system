const API_BASE = "http://localhost:8000/api/v1";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorBody}`);
  }
  return response.json();
}

export const api = {
  /** Executes a complite task (Planner → Research → Data → Synthesis) */
  async executeTask(taskDescription: string) {
    const response = await fetch(`${API_BASE}/execute-task`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_description: taskDescription }),
    });
    return handleResponse<import("../types/api").ExecuteTaskResponse>(response);
  },

  /** List history of executions */
  async listTasks(page = 1, pageSize = 20) {
    const response = await fetch(`${API_BASE}/tasks?page=${page}&page_size=${pageSize}`);
    return handleResponse<import("../types/api").ExecutionListResponse>(response);
  },

  /** Get execution details by trace_id */
  async getTaskDetail(traceId: string) {
    const response = await fetch(`${API_BASE}/tasks/${traceId}`);
    return handleResponse(response);
  },

  /** Obtain metrics from an execution */
  async getTaskMetrics(traceId: string) {
    const response = await fetch(`${API_BASE}/tasks/${traceId}/metrics`);
    return handleResponse(response);
  },
};
