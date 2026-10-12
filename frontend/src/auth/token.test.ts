import { describe, it, expect, beforeEach } from "vitest";
import { getToken, setToken, clearToken } from "./token";

describe("auth/token", () => {
  beforeEach(() => clearToken());

  it("returns null when no token is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("stores and retrieves a token", () => {
    setToken("abc123");
    expect(getToken()).toBe("abc123");
  });

  it("clears the token", () => {
    setToken("abc123");
    clearToken();
    expect(getToken()).toBeNull();
  });
});
