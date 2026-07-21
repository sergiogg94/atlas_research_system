import { useState } from "react";
import { api } from "../services/api";

interface TaskFormProps {
  onTaskCreated: (taskId: string) => void;
}

export function TaskForm({ onTaskCreated }: TaskFormProps) {
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (description.length < 10) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await api.executeTask(description);
      onTaskCreated(response.task_id);
      setDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: "600px", margin: "2rem 0" }}>
      <div style={{ marginBottom: "1rem" }}>
        <label
          htmlFor="task"
          style={{ display: "block", marginBottom: "0.5rem", fontWeight: 600, color: "var(--text-h)" }}
        >
          Task Description
        </label>
        <textarea
          id="task"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe the research task you want to execute..."
          rows={4}
          style={{
            width: "100%",
            padding: "0.75rem",
            border: "1px solid var(--border)",
            borderRadius: "4px",
            fontFamily: "inherit",
            fontSize: "1rem",
            background: "var(--bg)",
            color: "var(--text-h)",
            boxShadow: "inset 0 0 0 1px var(--accent-border)",
          }}
        />
        <small style={{ color: description.length < 10 ? "var(--accent)" : "var(--text-h)" }}>
          {description.length}/10 minimum characters
        </small>
      </div>

      <button
        type="submit"
        disabled={isLoading || description.length < 10}
        style={{
          padding: "0.75rem 2rem",
          background: description.length >= 10 ? "var(--accent)" : "var(--border)",
          color: "var(--text-h)",
          border: "1px solid var(--accent-border)",
          borderRadius: "4px",
          cursor: description.length >= 10 ? "pointer" : "not-allowed",
          fontSize: "1rem",
        }}
      >
        {isLoading ? "Executing..." : "Execute Task"}
      </button>

      {error && (
        <div
          style={{
            marginTop: "1rem",
            padding: "0.75rem",
            background: "var(--accent-bg)",
            color: "var(--accent)",
            border: "1px solid var(--accent-border)",
            borderRadius: "4px",
          }}
        >
          Error: {error}
        </div>
      )}
    </form>
  );
}
