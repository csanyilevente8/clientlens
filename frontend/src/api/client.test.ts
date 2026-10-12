import { describe, it, expect, beforeEach, vi } from "vitest";
import { apiGet, apiPost } from "./client";
import { setToken, clearToken } from "@/auth/token";

// Helper: build a Response-like object the way our wrapper consumes it (res.ok,
// res.status, res.json()). We only implement what apiFetch actually reads.
function mockResponse(body: unknown, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    statusText: "Mock Status",
    json: async () => body,
  } as Response;
}

describe("api/client", () => {
  beforeEach(() => {
    clearToken();
    vi.restoreAllMocks();
  });

  it("sends an Authorization header when a token is present", async () => {
    setToken("abc123");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockResponse({ ok: true }));

    await apiGet("/api/v1/clients");

    const [, init] = fetchMock.mock.calls[0];
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer abc123");
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("omits the Authorization header when there is no token", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockResponse({ data: [] }));

    await apiGet("/api/v1/clients");

    const [, init] = fetchMock.mock.calls[0];
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("serializes the body and uses POST for apiPost", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockResponse({ id: "1" }));

    await apiPost("/api/v1/clients", { name: "Jane" });

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/v1/clients");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify({ name: "Jane" }));
  });

  it("returns the parsed JSON body on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse({ id: "42", name: "Acme" }),
    );

    const result = await apiGet<{ id: string; name: string }>("/api/v1/clients/42");
    expect(result).toEqual({ id: "42", name: "Acme" });
  });

  it("throws with the backend 'detail' message on an error response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse({ detail: "Client not found" }, { ok: false, status: 404 }),
    );

    await expect(apiGet("/api/v1/clients/nope")).rejects.toThrow(
      "404: Client not found",
    );
  });

  it("falls back to statusText when the error body has no 'detail'", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse({}, { ok: false, status: 500 }),
    );

    await expect(apiGet("/api/v1/clients")).rejects.toThrow("500: Mock Status");
  });
});
