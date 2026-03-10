import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

vi.stubEnv("VITE_API_BASE_URL", "http://127.0.0.1:8000/api/v1");
vi.stubEnv("VITE_API_KEY", "");
vi.stubEnv("VITE_DEFAULT_EMPLOYEE_ID", "1");

class ResizeObserverShim {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Recharts relies on ResizeObserver, which is absent in jsdom.
globalThis.ResizeObserver = ResizeObserverShim as unknown as typeof ResizeObserver;
