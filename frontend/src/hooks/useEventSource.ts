import { useEffect, useRef, useCallback } from "react";

interface SSEOptions {
  onProgress?: (data: unknown) => void;
  onComplete?: (data: unknown) => void;
  onError?: (error: string) => void;
  enabled?: boolean;
}

export function useEventSource(
  url: string | null,
  { onProgress, onComplete, onError, enabled = true }: SSEOptions,
) {
  const eventSourceRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!url || !enabled) return;

    const es = new EventSource(url);
    eventSourceRef.current = es;
    let completed = false;

    es.addEventListener("progress", (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        onProgress?.(data);
      } catch {
        // Silently ignore malformed data
      }
    });

    es.addEventListener("complete", (event: MessageEvent) => {
      completed = true;
      try {
        const data = JSON.parse(event.data);
        onComplete?.(data);
      } catch {
        // Silently ignore
      }
      es.close();
    });

    es.addEventListener("error", () => {
      if (completed) return;
      onError?.("SSE connection lost");
      es.close();
    });

    return () => {
      es.close();
    };
  }, [url, enabled, onProgress, onComplete, onError]);

  return { close };
}
