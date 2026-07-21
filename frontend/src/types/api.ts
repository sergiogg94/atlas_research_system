// For backend/app/schemas/orchestrator.py
export interface ExecuteTaskRequest {
  task_description: string;
}

export interface ExecuteTaskResponse {
  status: string;
  timestamp: string;
  task_id:  string;
  objective: string;
  plan: Record<string, unknown> | null;
  research_findings: unknown[] | null;
  data_results: unknown[] | null;
  report: string | null;
  error: string | null;
  total_steps: number;
}


// For backend/app/schemas/hisory.py
export interface ExecutionSummary {
  id: string;
  trace_id: string;
  task_description: string;
  objective: string | null;
  status: string;
  total_steps: number;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionListResponse {
  status: string;
  timestamp: string;
  executions: ExecutionSummary[];
  total: number;
  page: number;
  page_size: number;
}
