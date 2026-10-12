import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateMeetingForm } from "./CreateMeetingForm";
import * as apiClient from "@/api/client";
import { QueryWrapper } from "@/test/utils";

describe("CreateMeetingForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("submits the typed title + transcript with the client id and an ISO timestamp", async () => {
    const postSpy = vi
      .spyOn(apiClient, "apiPost")
      .mockResolvedValue({ id: "m1", status: "CREATED" });

    render(<CreateMeetingForm clientId="client-9" />, { wrapper: QueryWrapper });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/meeting title/i), "Q3 portfolio review");
    await user.type(screen.getByLabelText(/transcript/i), "client wants to retire");
    await user.click(screen.getByRole("button", { name: /add meeting/i }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledOnce());

    const [path, payload] = postSpy.mock.calls[0] as [string, Record<string, string>];
    expect(path).toBe("/api/v1/meetings");
    expect(payload.client_id).toBe("client-9");
    expect(payload.title).toBe("Q3 portfolio review");
    expect(payload.transcript).toBe("client wants to retire");
    // occurred_at must be a valid ISO 8601 datetime (what the backend expects).
    expect(() => new Date(payload.occurred_at).toISOString()).not.toThrow();
    expect(payload.occurred_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("clears the inputs after a successful submit", async () => {
    vi.spyOn(apiClient, "apiPost").mockResolvedValue({ id: "m1" });

    render(<CreateMeetingForm clientId="c1" />, { wrapper: QueryWrapper });

    const user = userEvent.setup();
    const title = screen.getByLabelText(/meeting title/i) as HTMLInputElement;
    const transcript = screen.getByLabelText(/transcript/i) as HTMLTextAreaElement;

    await user.type(title, "A meeting");
    await user.type(transcript, "some notes");
    await user.click(screen.getByRole("button", { name: /add meeting/i }));

    await waitFor(() => expect(title.value).toBe(""));
    expect(transcript.value).toBe("");
  });

  it("shows the error message when the request fails", async () => {
    vi.spyOn(apiClient, "apiPost").mockRejectedValue(new Error("404: Client not found"));

    render(<CreateMeetingForm clientId="c1" />, { wrapper: QueryWrapper });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/meeting title/i), "x");
    await user.type(screen.getByLabelText(/transcript/i), "y");
    await user.click(screen.getByRole("button", { name: /add meeting/i }));

    expect(await screen.findByText("404: Client not found")).toBeInTheDocument();
  });
});
