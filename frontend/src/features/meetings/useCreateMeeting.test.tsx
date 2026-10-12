import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useCreateMeeting } from "./useCreateMeeting";
import * as apiClient from "@/api/client";
import { createTestQueryClient } from "@/test/utils";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";

describe("useCreateMeeting", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs the payload to /api/v1/meetings and invalidates the client's meetings", async () => {
    const postSpy = vi
      .spyOn(apiClient, "apiPost")
      .mockResolvedValue({ id: "m1", status: "CREATED" });

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useCreateMeeting("client-7"), { wrapper });

    const payload = {
      client_id: "client-7",
      title: "Q3 review",
      occurred_at: "2026-10-12T12:00:00.000Z",
      transcript: "discussed retirement",
    };
    result.current.mutate(payload);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Posted the exact payload (not wrapped in an extra object).
    expect(postSpy).toHaveBeenCalledWith("/api/v1/meetings", payload);
    // Invalidated only THIS client's meetings list.
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["meetings", "client-7"],
    });
  });

  it("surfaces an error when the request fails", async () => {
    vi.spyOn(apiClient, "apiPost").mockRejectedValue(new Error("400: bad request"));

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useCreateMeeting("c1"), { wrapper });
    result.current.mutate({
      client_id: "c1",
      title: "x",
      occurred_at: "2026-10-12T12:00:00.000Z",
      transcript: "y",
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("400: bad request");
  });
});
