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

// For history details
export interface StepDetail {
  id: string;
  agent_name: string;
  step_type: string | null;
  input_summary: string | null;
  output_summary: string | null;
  status: string;
  error: string | null;
  latency_ms: number | null;
  created_at: string;
}

export interface ExecutionDetail extends ExecutionSummary {
  steps: StepDetail[];
  report: string | null;
}

export interface ExecutionDetailResponse {
  status: string;
  timestamp: string;
  execution: ExecutionDetail;
}

export interface ExecutionMetrics {
  execution_id: string;
  trace_id: string;
  total_duration_ms: number | null;
  total_llm_calls: number;
  total_tool_calls: number;
  total_steps: number;
  total_tokens_input: number;
  total_tokens_output: number;
  estimated_cost_usd: number;
  avg_step_latency_ms: number | null;
  avg_llm_latency_ms: number | null;
  error_count: number;
}

export interface ExecutionMetricsResponse {
  status: string;
  timestamp: string;
  metrics: ExecutionMetrics;
}
