import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../services/api"

export function useTasks(page = 1, status = "") {
  return useQuery({
    queryKey: ["tasks", page, status],
    queryFn: () => api.listTasks(page, 20, status),
  });
}

export function useTaskDetail(traceId: string | undefined) {
  return useQuery({
    queryKey: ["task", traceId],
    queryFn: () => api.getTaskDetail(traceId!),
    enabled: !!traceId,
  });
}

export function useTaskMetrics(traceId: string | undefined) {
  return useQuery({
    queryKey: ["metrics", traceId],
    queryFn: () => api.getTaskMetrics(traceId!),
    enabled: !!traceId,
  });
}

export function useExecuteTask() {
  return useMutation({
    mutationFn: (description: string) => api.executeTask(description),
  });
}
