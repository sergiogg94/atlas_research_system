import { render, screen } from "@testing-library/react";

it("smoke: jsdom + jest-dom funcionan", () => {
  render(<div>hola</div>);
  expect(screen.getByText("hola")).toBeInTheDocument();
});
