/**
 * Component test for the home page.
 *
 * Mirrors the backend's health test: the very first frontend test proves the
 * toolchain (Jest + SWC transform + Testing Library) renders a real component.
 * It asserts on the accessible role/name, not on markup details, so it stays
 * robust to styling changes.
 */
import { render, screen } from "@testing-library/react";

import ChatPage from "./chat/page";
import DashboardPage from "./dashboard/page";
import HomePage from "./page";
import SearchPage from "./search/page";

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

  it("shows quick actions for the dashboard workflow", () => {
    render(<HomePage />);
    expect(screen.getByRole("link", { name: /open dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /document library/i })).toBeInTheDocument();
  });
});

describe("Phase 5 dashboard UI", () => {
  it("renders the dashboard overview and document actions", () => {
    render(<DashboardPage />);

    expect(screen.getByRole("heading", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /upload document/i })).toBeInTheDocument();
    expect(screen.getByText(/recent uploads/i)).toBeInTheDocument();
  });

  it("renders the chat interface for Q&A", () => {
    render(<ChatPage />);

    expect(screen.getByRole("heading", { name: /chat/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/ask about your documents/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });

  it("renders the semantic search page", () => {
    render(<SearchPage />);

    expect(screen.getByRole("heading", { name: /search/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/search your documents/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /search/i })).toBeInTheDocument();
  });
});
