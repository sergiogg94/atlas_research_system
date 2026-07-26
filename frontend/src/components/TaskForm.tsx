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
    <form onSubmit={handleSubmit} className="form">
      <div className="form-group">
        <label htmlFor="task" className="form-label">
          Task Description
        </label>
        <textarea
          id="task"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe the research task you want to execute..."
          rows={4}
          className="form-textarea"
        />
        <small className={isValidLength ? "char-count" : "char-count--warn"}>
          {charCount}/10 characters {isValidLength ? "\u2713" : "(minimum)"}
        </small>
      </div>

      <button
        type="submit"
        disabled={isLoading || !isValidLength}
        className="btn"
      >
        {isLoading ? "Executing..." : "Execute Task"}
      </button>

      {error && (
        <div className="error-box" style={{ marginTop: "1rem" }}>
          Error: {error}
        </div>
      )}
    </form>
  );
}
