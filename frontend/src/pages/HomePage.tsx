import { useNavigate } from "react-router-dom";
import { TaskForm } from "../components/TaskForm";

export function HomePage() {
  const navigate = useNavigate();

  function handleTaskCreated(taskId: string) {
    navigate(`/tasks/${taskId}`);
  }

  return (
    <div>
      <h2>Welcome to Atlas Research System</h2>
      <p>
        Describe a research task and let the multi-agent system analyze it for you.
      </p>
      <TaskForm onTaskCreated={handleTaskCreated} />
    </div>
  );
}
