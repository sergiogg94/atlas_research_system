import { useState } from "react";
import { useExecuteTask } from "../hooks/useTasks";
import { useToast } from "./ToastProvider";

interface TaskFormProps {
  onTaskCreated: (taskId: string) => void;
}

export function TaskForm({ onTaskCreated }: TaskFormProps) {
  const [description, setDescription] = useState("");
  const charCount = description.length;
  const isValidLength = charCount >= 10;
  const { addToast } = useToast()
  const { mutate, isPending, error } = useExecuteTask();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValidLength) return;

    mutate(description, {
      onSuccess: (response) => {
        onTaskCreated(response.task_id);
        setDescription("");
        addToast("Task created successfully", "success");
      },
      onError: (err) => {
        addToast(err instanceof Error ? err.message : "Failed to create task", "error");
      },
    });
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
        disabled={isPending || !isValidLength}
        className="btn"
      >
        {isPending ? "Executing..." : "Execute Task"}
      </button>

      {error && (
        <div className="error-box" style={{ marginTop: "1rem" }}>
          Error: {error instanceof Error ? error.message : "Failed to create task"}
        </div>
      )}
    </form>
  );
}
