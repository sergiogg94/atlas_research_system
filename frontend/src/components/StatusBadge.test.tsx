import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

const STATUSES = [
  ["completed", "badge--completed"],
  ["failed", "badge--failed"],
  ["running", "badge--running"],
  ["pending", "badge--pending"],
  ["timeout", "badge--timeout"],
] as const;


describe('StatusBadge', () => {
  it.each(STATUSES)('renders %s with class %s', (status, className) => {
    render(<StatusBadge status={status} />);

    const badge = screen.getByText(status);
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("badge");
    expect(badge).toHaveClass(className);
  });

  it("no extra class applies for an unknown status", () => {
    render(<StatusBadge status="weird" />);

    const badge = screen.getByText("weird");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("badge");
    expect(badge).not.toHaveClass(/badge--/);
  });
});
