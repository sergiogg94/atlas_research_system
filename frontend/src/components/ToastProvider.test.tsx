import { act, fireEvent, render, screen } from "@testing-library/react";
import { ToastProvider, useToast } from "./ToastProvider";

function Probe() {
  const { addToast } = useToast();
  return <button onClick={() => addToast("Hello", "success")}>add</button>;
}

describe("ToastProvider", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("addToast add the toast with the message and the success icon", () => {
    render(
      <ToastProvider>
        <Probe />
      </ToastProvider>
    );

    expect(screen.queryByText("Hello")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "add" }));

    expect(screen.getByText("✓ Hello")).toBeInTheDocument();
  });

  it("auto-dismiss after 4000ms", () => {
    render(
      <ToastProvider>
        <Probe />
      </ToastProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "add" }));
    expect(screen.getByText("✓ Hello")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3999);
    });
    expect(screen.getByText("✓ Hello")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByText("✓ Hello")).not.toBeInTheDocument();
  });

  it("clicking the toast removes it instantly", () => {
    render(
      <ToastProvider>
        <Probe />
      </ToastProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "add" }));

    const toastEl = screen.getByText("✓ Hello");
    fireEvent.click(toastEl);

    expect(screen.queryByText("✓ Hello")).not.toBeInTheDocument();
  });
});
