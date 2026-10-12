// Vitest setup: runs once before the test suite.
// Adds jest-dom matchers (toBeInTheDocument, toBeDisabled, ...) and clears mocks.
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Unmount React trees and reset mocks between tests so they don't leak state.
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
