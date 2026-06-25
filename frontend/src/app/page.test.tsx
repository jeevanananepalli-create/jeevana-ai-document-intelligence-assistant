/**
 * Component test for the home page.
 *
 * Mirrors the backend's health test: the very first frontend test proves the
 * toolchain (Jest + SWC transform + Testing Library) renders a real component.
 * It asserts on the accessible role/name, not on markup details, so it stays
 * robust to styling changes.
 */
import { render, screen } from "@testing-library/react";

import HomePage from "./page";

describe("HomePage", () => {
  it("renders the main heading", () => {
    render(<HomePage />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /document intelligence assistant/i,
      }),
    ).toBeInTheDocument();
  });
});
