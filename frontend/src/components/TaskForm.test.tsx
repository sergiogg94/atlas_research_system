import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "./ToastProvider";
import { TaskForm } from "./TaskForm";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: { executeTask: vi.fn() },
}));

const mockedApi = vi.mocked(api.executeTask);
const DESCRIPTION = "Research the coffee market in Mexico City";

function renderTaskForm(onTaskCreated: (id: string) => void = vi.fn()) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}
    >
      <ToastProvider>
        <TaskForm onTaskCreated={onTaskCreated} />
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe("TaskForm", () => {
  afterEach(() => vi.clearAllMocks());

  it("the button is disabled when there are fewer than 10 characters and does not call the API", async () => {
    const user = userEvent.setup();
    const onTaskCreated = vi.fn();
    renderTaskForm(onTaskCreated);

    const button = screen.getByRole("button", { name: "Execute Task" });
    const textarea = screen.getByLabelText("Task Description");

    expect(button).toBeDisabled();

    await user.type(textarea, "short"); // 5 characters

    expect(button).toBeDisabled();
    expect(screen.getByText("5/10 characters (minimum)")).toBeInTheDocument();
    expect(mockedApi).not.toHaveBeenCalled();

    await user.click(button); // Click on disabled button: does nothing
    expect(mockedApi).not.toHaveBeenCalled();
  });

  it("send the description and call onTaskCreated with the task_id", async () => {
    const user = userEvent.setup();
    const onTaskCreated = vi.fn();
    mockedApi.mockResolvedValue({
      status: "success",
      timestamp: "2026-01-01",
      task_id: "task-123",
      objective: "obj",
      plan: null,
      research_findings: null,
      data_results: null,
      report: null,
      error: null,
      total_steps: 0,
    });
    renderTaskForm(onTaskCreated);

    await user.type(screen.getByLabelText("Task Description"), DESCRIPTION);
    await user.click(screen.getByRole("button", { name: "Execute Task" }));

    await waitFor(() => expect(mockedApi).toHaveBeenCalledWith(DESCRIPTION));
    await waitFor(() => expect(onTaskCreated).toHaveBeenCalledWith("task-123"));
    expect(screen.getByLabelText("Task Description")).toHaveValue("");
    expect(screen.getByText("✓ Task created successfully")).toBeInTheDocument();
  });

  it("displays an error toast when the API fails", async () => {
    const user = userEvent.setup();
    const onTaskCreated = vi.fn();
    mockedApi.mockRejectedValue(new Error("boom of the API"));
    renderTaskForm(onTaskCreated);

    await user.type(screen.getByLabelText("Task Description"), DESCRIPTION);
    await user.click(screen.getByRole("button", { name: "Execute Task" }));

    await waitFor(() => expect(onTaskCreated).not.toHaveBeenCalled());
    expect(await screen.findByText("✗ boom of the API")).toBeInTheDocument();
  });
});
