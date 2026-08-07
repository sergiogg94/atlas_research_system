import { render, screen } from "@testing-library/react";
import { PlanTimeLine, type PlanStep } from "./PlanTimeLine";

describe("PlanTimeLine", () => {
  const steps: PlanStep[] = [
    { type: "scoping", description: "Define scope", status: "completed" },
    { type: "research", description: "Look for data", status: "running" },
    { type: "custom_type", description: "Unknown type", status: "pending" },
  ];

  it("renders the objective", () => {
    render(<PlanTimeLine objective="Test objective" steps={steps} />);
    expect(screen.getByText("Test objective")).toBeInTheDocument();
  });

  it.each([
    ["scoping", "🎯"],
    ["research", "🔍"],
    ["analysis", "📊"],
    ["synthesis", "📝"],
  ])("the type %s uses the icon %s", (type, icon) => {
    render(
      <PlanTimeLine
        objective="Objective"
        steps={[{type, description: "d", status: "pending"}]}
      />
    );
    expect(screen.getByText(icon)).toBeInTheDocument();
  });

  it("uses • as fallback for unknown types", () => {
    render(
      <PlanTimeLine
        objective="Objective"
        steps={[{ type: "unknown", description: "d", status: "pending" }]}
      />
    );
    expect(screen.getByText("•")).toBeInTheDocument();
  });

  it("apply the state class to each step and display the state text", () => {
    const { container } = render(<PlanTimeLine objective="Objective" steps={steps} />);

    for (const step of steps) {
      const stepEl = container.querySelector(`.plan-step--${step.status}`);
      expect(stepEl).not.toBeNull();
    }

    expect(screen.getAllByText("completed").length).toBe(1);
    expect(screen.getAllByText("running").length).toBe(1);
    expect(screen.getAllByText("pending").length).toBe(1);
  });
});
