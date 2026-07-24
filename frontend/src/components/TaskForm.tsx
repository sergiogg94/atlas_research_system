import { useState } from "react";
import { api } from "../services/api";

interface TaskFormProps {
  onTaskCreated: (taskId: string) => void;
}

export function TaskForm({ onTaskCreated }: TaskFormProps) {
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const charCount = description.length;
  const isValidLength = charCount >= 10;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValidLength) return;

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
        <small style={{ color: isValidLength ? "var(--accent)" : "var(--text-h)" }}>
          {charCount}/10 characters {isValidLength ? "✓" : "(minimum)"}
        </small>
      </div>

      <button
        type="submit"
        disabled={isLoading || !isValidLength}
        style={{
          padding: "0.75rem 2rem",
          background: isValidLength ? "var(--accent)" : "var(--border)",
          color: "var(--text-h)",
          border: "1px solid var(--accent-border)",
          borderRadius: "4px",
          cursor: isValidLength ? "pointer" : "not-allowed",
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
